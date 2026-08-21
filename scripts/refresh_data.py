#!/usr/bin/env python3
"""
Scheduled data refresh for the Action running every 6 hours (see
.github/workflows/refresh.yml). Writes three files under data/:

  tle.json       -- live orbital elements, only rewritten if content changed
  captures.json  -- "last capture" imagery pointers, only rewritten if changed
  status.json    -- ALWAYS rewritten every run (heartbeat + per-source timing)

WHY TWO DIFFERENT CADENCES IN ONE SCRIPT, NOT ONE SCHEDULE:
CelesTrak's own usage guidance (checked directly against their docs, not
assumed) asks integrators not to poll more than necessary: "CelesTrak does
not update any data more often than every 2 hours... daily usually
suffices... every 3 days is fine for a stable orbit." Running a fresh TLE
fetch every 6 hours would be 4x more often than their own service says is
useful. So TLEs are self-throttled here (only re-fetched if the last
successful fetch was >48h ago, tracked via status.json) even though the
Action itself runs every 6h. Sentinel-2 capture checks run every time --
Earth Search doesn't carry the same "please don't" guidance, and a new
scene can appear at any point in a multi-day revisit window, so there's no
similarly-justified reason to throttle it.

WHY GOES ISN'T HERE AT ALL:
NOAA STAR's GeoColor imagery lives at a STABLE url per satellite --
https://cdn.star.nesdis.noaa.gov/GOES{n}/ABI/FD/GEOCOLOR/339x339.jpg always
serves whatever is currently latest. There's nothing to discover or cache;
the browser can point straight at it. Routing that through this pipeline
would only add staleness (capped at your refresh cadence) instead of
removing it. That's a small addition to the dex UI directly, not something
this script needs to touch.

Run locally to test before trusting the Action:
    pip install -r requirements.txt
    python3 scripts/refresh_data.py
    python3 scripts/refresh_data.py --force-tle    # bypass the 48h throttle

I could not run this against the live APIs from my own sandbox (CelesTrak,
NOAA, and Earth Search aren't reachable from there) -- the URL shapes and
JSON structures below are verified against current documentation and code
examples, not against a live response I've personally seen. Treat the first
real run as the actual test.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CATALOG_PATH = DATA / "satellites.json"
TLE_PATH = DATA / "tle.json"
CAPTURES_PATH = DATA / "captures.json"
STATUS_PATH = DATA / "status.json"

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"
# NOTE: originally this used FORMAT=JSON, on the assumption that CelesTrak's
# JSON response would include convenient TLE_LINE1/TLE_LINE2 strings. A real
# response proved that wrong: FORMAT=JSON returns OMM-style numeric fields
# (MEAN_MOTION, ECCENTRICITY, INCLINATION, etc.), not TLE line text at all --
# which is exactly what satellite.js on the client needs
# (twoline2satrec(line1, line2)). FORMAT=TLE gives the real 3-line text
# directly, confirmed against a live response before this was written.
STAC_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
TLE_THROTTLE_HOURS = 48  # re-fetch at most ~every 2 days; see module docstring
STAC_SEARCH_WINDOW_DAYS = 30  # wide enough to span Sentinel-2's multi-day revisit
HTTP_TIMEOUT = 15
UA = {"User-Agent": "my-satellite-refresh/1.0 (github actions, personal project)"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def write_if_changed(path, data):
    """Sorted, stable JSON so real changes are visible in git diffs and
    identical content never produces spurious ones. Returns True if the
    file's content actually changed (caller decides whether to commit)."""
    new_text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() == new_text:
        return False
    path.write_text(new_text)
    return True


def fetch_json(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA)
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode())


def fetch_text(url):
    """For CelesTrak's FORMAT=TLE, which is plain text, not JSON."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read().decode()


# ---------------- TLEs ----------------


def fetch_tles(catalog, status):
    """One request per satellite -- CelesTrak's CATNR query is single-object,
    and the catalog spans multiple agencies so there's no single GROUP query
    that covers it. A short delay between requests is a courtesy on top of
    the daily throttle, not a substitute for it.

    Response is 3-line TLE text: name, then two 69-character element lines,
    CRLF-separated with a trailing CRLF (confirmed against a live response --
    e.g. 'ISS (ZARYA)             \\r\\n1 25544U ... \\r\\n2 25544 ... \\r\\n').
    splitlines() is used rather than splitting on a literal '\\r\\n' so this
    doesn't silently break if CelesTrak ever normalizes to bare '\\n'."""
    out = {}
    errors = {}
    for sat in catalog:
        norad = sat["norad_id"]
        try:
            text = fetch_text(CELESTRAK_URL.format(norad=norad))
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if len(lines) < 3:
                errors[str(norad)] = f"expected 3 TLE lines, got {len(lines)}: {lines!r}"
                continue
            name, line1, line2 = lines[0], lines[1], lines[2]
            if not line1.startswith("1 ") or not line2.startswith("2 "):
                errors[str(norad)] = (
                    f"unexpected TLE line prefixes: {line1[:12]!r} / {line2[:12]!r}"
                )
                continue
            out[str(norad)] = {"line1": line1, "line2": line2, "name": name}
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            errors[str(norad)] = str(e)
        time.sleep(0.5)
    return out, errors


def should_refresh_tles(status, force):
    if force:
        return True
    last = status.get("tle", {}).get("last_success_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.now(timezone.utc) - last_dt > timedelta(hours=TLE_THROTTLE_HOURS)


# ---------------- propagation (to know WHERE each satellite is right now,
# needed to search Earth Search by location) ----------------

_TS = None  # skyfield timescale, loaded lazily and reused across calls


def propagate_now(tle_entry):
    """Returns (lat, lon) in degrees, or None if propagation fails.

    Uses skyfield rather than raw sgp4 output. This matters: sgp4's raw
    result is in the TEME frame, which is INERTIAL -- it does not rotate
    with the Earth. Converting that straight to longitude via atan2(y, x)
    silently ignores Earth's rotation since the TLE's epoch and gives a
    systematically wrong location (verified numerically: a naive version of
    this function showed a large, non-physical longitude jump between two
    calls a few hours apart, since it was missing the ~15deg/hour rotation
    entirely). skyfield's wgs84.geographic_position_of() does the correct
    TEME -> ITRS -> geodetic conversion, which is why it's used here even
    though the client-side app uses satellite.js's own eciToGeodetic
    instead -- same physics, different library on each side of the stack.
    """
    global _TS
    from skyfield.api import EarthSatellite, load, wgs84

    if _TS is None:
        _TS = load.timescale()
    try:
        sat = EarthSatellite(tle_entry["line1"], tle_entry["line2"], "sat", _TS)
        t = _TS.now()
        geocentric = sat.at(t)
        subpoint = wgs84.geographic_position_of(geocentric)
        return subpoint.latitude.degrees, subpoint.longitude.degrees
    except (ValueError, KeyError) as e:
        print(f"  propagation failed: {e}", file=sys.stderr)
        return None


# ---------------- captures: Sentinel-2 via Earth Search STAC ----------------


def sentinel2_id_prefix(name):
    """'Sentinel-2A' -> 'S2A_', matching Earth Search's item id convention --
    confirmed against many real item ids (e.g. S2A_18TYM_20230926_0_L2A,
    S2B_31TGM_20201230_0_L2A). Returns None for anything that isn't a named
    Sentinel-2 satellite."""
    name = (name or "").strip()
    if not name.lower().startswith("sentinel-2"):
        return None
    suffix = name[len("Sentinel-2"):].strip()
    if not suffix or not suffix[0].isalpha():
        return None
    return f"S2{suffix[0].upper()}_"


# Thresholds are deliberately loose -- the goal is filtering out clearly-bad
# candidates (near-total cloud, near-total nodata), not hunting for a
# picture-perfect scene. A real capture found in testing passed through
# with eo:cloud_cover fine but was a flat white image -- confirmed via a
# real STAC example item that s2:nodata_pixel_percentage is a SEPARATE
# quality dimension from cloud cover (one real item had 0.4% cloud cover
# and 77% nodata simultaneously), which cloud-cover-only filtering would
# have completely missed.
CLOUD_COVER_MAX = 50
NODATA_MAX = 20


def _stac_quality_ok(props):
    cloud = props.get("eo:cloud_cover")
    if cloud is not None and cloud > CLOUD_COVER_MAX:
        return False
    nodata = props.get("s2:nodata_pixel_percentage")
    if nodata is not None and nodata > NODATA_MAX:
        return False
    return True


def _pick_best_scene(features):
    """Most recent scene that clears the quality bar; if NOTHING clears it,
    falls back to pure most-recent regardless -- a flawed real image still
    beats reporting no capture at all. Never returns nothing just because
    every candidate in the window happened to be imperfect."""
    if not features:
        return None
    quality = [f for f in features if _stac_quality_ok(f.get("properties", {}))]
    pool = quality if quality else features
    return max(pool, key=lambda f: f.get("properties", {}).get("datetime", ""))


def resolve_sentinel2_capture(lat, lon, id_prefix):
    """POST search, then the highest-quality recent scene within
    STAC_SEARCH_WINDOW_DAYS near the satellite's current sub-point (see
    _pick_best_scene) -- picked client-side rather than relying on
    server-side sort/filter support, which wasn't something I could verify
    directly.

    id_prefix filters results to scenes actually captured by THIS satellite
    (e.g. 'S2A_') -- without this, the search returns whatever's nearest in
    the shared sentinel-2-l2a collection regardless of which of the (up to
    3) Sentinel-2 satellites actually took it, so "Sentinel-2C's last
    capture" could silently be a 2A or 2B scene instead. Sentinel-2's
    constellation revisit is a few days combined but longer per-satellite,
    so this filter means fewer matches per satellite, not zero -- see the
    module docstring's search window if this needs widening."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=STAC_SEARCH_WINDOW_DAYS)
    pad = 0.5  # degrees, roughly a wide net around the sub-point
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [lon - pad, lat - pad, lon + pad, lat + pad],
        "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "limit": 20,  # raised from 10: filtering by platform first shrinks the usable pool
    }
    data = fetch_json(STAC_SEARCH_URL, method="POST", body=body)
    features = [f for f in data.get("features", []) if f.get("id", "").startswith(id_prefix)]
    best = _pick_best_scene(features)
    if not best:
        return None
    thumb = best.get("assets", {}).get("thumbnail", {}).get("href")
    if not thumb:
        return None
    return {
        "url": thumb,
        "captured_at": best.get("properties", {}).get("datetime"),
        "scene_id": best.get("id"),
        "resolved_at": now_iso(),
    }


# ---------------- captures: Landsat via Earth Search STAC ----------------


def landsat_id_prefix(name):
    """'Landsat 8' -> 'LC08_', 'Landsat 9' -> 'LC09_', matching Earth Search's
    Landsat item id convention (e.g. LC09_L2SR_145060_20230307_02_T1).
    Earlier Landsats (4/5/7) use different sensor prefixes (LT/LE) -- not
    handled here since none are in this catalog, but that's why this isn't
    just 'L' + the number."""
    name = (name or "").strip()
    if not name.lower().startswith("landsat "):
        return None
    num = name.split()[-1].strip()
    if not num.isdigit():
        return None
    return f"LC{int(num):02d}_"


def resolve_landsat_capture(lat, lon, id_prefix):
    """Same search shape as Sentinel-2, but the URL extraction is genuinely
    different, not just copy-pasted: Landsat's assets.thumbnail.href points
    into a REQUESTER-PAYS S3 bucket (confirmed directly against Element84's
    own published example item -- storage:requester_pays: true on that
    asset), which needs AWS credentials a browser can never provide. Earth
    Search separately publishes an API-rendered thumbnail via a 'thumbnail'
    link relation (a plain public HTTPS endpoint under the item's own API
    path), which is what actually works here. Falls back to constructing
    that same URL shape directly if the link isn't present in the response
    for some reason, since the shape itself is a documented, stable Earth
    Search convention, not a guess."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=STAC_SEARCH_WINDOW_DAYS)
    pad = 0.5
    body = {
        "collections": ["landsat-c2-l2"],
        "bbox": [lon - pad, lat - pad, lon + pad, lat + pad],
        "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "limit": 20,
    }
    data = fetch_json(STAC_SEARCH_URL, method="POST", body=body)
    features = [f for f in data.get("features", []) if f.get("id", "").startswith(id_prefix)]
    # Reuses the same quality bar as Sentinel-2. Only eo:cloud_cover is
    # confirmed present on Landsat items (verified against documentation);
    # s2:nodata_pixel_percentage is a Sentinel-2-specific property name and
    # likely won't be present here, but _stac_quality_ok() already treats a
    # missing property as "doesn't fail that check" rather than erroring, so
    # this safely degrades to a cloud-cover-only filter for Landsat without
    # guessing at a property name I haven't verified exists for it.
    best = _pick_best_scene(features)
    if not best:
        return None

    thumb = None
    for link in best.get("links", []):
        if link.get("rel") == "thumbnail":
            thumb = link.get("href")
            break
    if not thumb:
        self_href = STAC_SEARCH_URL.rsplit("/search", 1)[0]
        thumb = f"{self_href}/collections/landsat-c2-l2/items/{best.get('id')}/thumbnail"

    return {
        "url": thumb,
        "captured_at": best.get("properties", {}).get("datetime"),
        "scene_id": best.get("id"),
        "resolved_at": now_iso(),
    }


def resolve_captures(catalog, tle_data, status):
    out = {}
    errors = {}
    for sat in catalog:
        norad = str(sat["norad_id"])
        name = sat.get("name") or ""

        s2_prefix = sentinel2_id_prefix(name)
        ls_prefix = landsat_id_prefix(name)
        if not s2_prefix and not ls_prefix:
            continue  # no resolver for this type yet -- see module docstring re: GOES

        tle = tle_data.get(norad)
        if not tle:
            errors[norad] = "no TLE available to compute current position"
            continue
        pos = propagate_now(tle)
        if not pos:
            errors[norad] = "propagation failed"
            continue
        try:
            if s2_prefix:
                cap = resolve_sentinel2_capture(*pos, s2_prefix)
                label = s2_prefix.rstrip("_")
            else:
                cap = resolve_landsat_capture(*pos, ls_prefix)
                label = ls_prefix.rstrip("_")
            if cap:
                out[norad] = cap
            else:
                errors[norad] = f"no recent {label} scene found in search window"
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            errors[norad] = str(e)
        time.sleep(0.5)
    return out, errors


# ---------------- main ----------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-tle", action="store_true", help="bypass the 48h throttle")
    args = parser.parse_args()

    catalog = load_json(CATALOG_PATH, {}).get("satellites", [])
    if not catalog:
        print(f"No catalog found at {CATALOG_PATH} -- nothing to refresh.", file=sys.stderr)
        sys.exit(1)

    status = load_json(STATUS_PATH, {})
    existing_tle = load_json(TLE_PATH, {})
    existing_captures = load_json(CAPTURES_PATH, {})

    tle_changed = False
    tle_errors = {}
    fresh_tle = {}  # always defined, even when refresh is skipped this run
    will_refresh_tle = should_refresh_tles(status, args.force_tle)  # decided ONCE, reused below
    if will_refresh_tle:
        print(f"Refreshing TLEs for {len(catalog)} satellites...")
        fresh_tle, tle_errors = fetch_tles(catalog, status)
        merged_tle = {**existing_tle, **fresh_tle}  # keep last-known-good for anyone that failed this run
        tle_changed = write_if_changed(TLE_PATH, merged_tle)
        tle_success = len(fresh_tle) > 0
    else:
        print("TLE refresh skipped (last success <48h ago). Use --force-tle to override.")
        merged_tle = existing_tle
        tle_success = True  # not attempted this run isn't a failure

    print("Resolving Sentinel-2 captures...")
    fresh_captures, cap_errors = resolve_captures(catalog, merged_tle, status)
    # Merge deliberately, not a blanket overwrite: resolve_captures() stamps
    # a fresh resolved_at on EVERY successful check, even when the actual
    # scene hasn't changed (Sentinel-2's multi-day revisit means most checks
    # find the same scene as last time). A naive {**existing, **fresh} merge
    # would treat "we re-checked" as "content changed" and commit every
    # single run forever -- exactly the noise the diff-gate exists to avoid.
    # Only actually update an entry when the scene_id genuinely changed.
    merged_captures = dict(existing_captures)
    for norad, cap in fresh_captures.items():
        prior = existing_captures.get(norad)
        if not prior or prior.get("scene_id") != cap.get("scene_id"):
            merged_captures[norad] = cap
    captures_changed = write_if_changed(CAPTURES_PATH, merged_captures)

    # status.json is written EVERY run, unconditionally -- this is both the
    # staleness-monitoring artifact and what keeps the repo's commit history
    # active enough that GitHub's 60-day scheduled-workflow auto-disable
    # (public repos only) never triggers even during a long stable stretch
    # with no real data changes.
    t = now_iso()
    new_status = dict(status)
    new_status["last_checked_at"] = t
    if will_refresh_tle:
        new_status["tle"] = {
            "last_attempt_at": t,
            "last_success_at": t if tle_success else status.get("tle", {}).get("last_success_at"),
            "successes": len(fresh_tle),
            "errors": tle_errors,
        }
    new_status["captures"] = {
        "last_attempt_at": t,
        "last_success_at": t if fresh_captures else status.get("captures", {}).get("last_success_at"),
        "successes": len(fresh_captures),
        "errors": cap_errors,
    }
    write_if_changed(STATUS_PATH, new_status)  # return value ignored: always written regardless

    print(f"tle.json {'changed' if tle_changed else 'unchanged'}, "
          f"captures.json {'changed' if captures_changed else 'unchanged'}, "
          f"status.json always written.")

    # Fail loudly (non-zero exit -> GitHub emails on Action failure by
    # default) only if TLE refresh was attempted this run and got NOTHING --
    # a total outage is worth flagging; a few individual satellite failures
    # among many successes is not.
    if will_refresh_tle and not tle_success:
        print("TLE refresh attempted and failed for every satellite.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()