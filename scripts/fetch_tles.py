#!/usr/bin/env python3
"""
Stage 2 batch TLE fetch.

Pulls a live TLE from CelesTrak for every NORAD ID in the curated catalog
(catalog/satellites.py), propagates each one with skyfield to sanity-check
it, and writes the result to data/tle.json.

This file is intentionally separate from data/satellites.json: the catalog
(name, agency, description...) barely ever changes, but TLEs go stale within
days. Splitting them means the weekly refresh (Stage 6) only has to touch
this file, and the frontend joins the two by norad_id at load time.

Needs outbound network access to celestrak.org -- same requirement as
scripts/validate_tle.py.

Usage:
    python3 scripts/fetch_tles.py
    python3 scripts/fetch_tles.py --delay 1.0       # slower, more polite
    python3 scripts/fetch_tles.py --limit 5          # test on a subset
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from skyfield.api import EarthSatellite, load, wgs84

# catalog/ is a sibling directory to scripts/ -- add it to the path so we
# can import the curated satellite list without turning this into a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "catalog"))
from satellites import SATELLITES  # noqa: E402

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "tle.json"
STALE_WARNING_DAYS = 7  # TLE accuracy degrades with age; flag anything older than this


def fetch_tle(norad_id: int) -> tuple[str, str, str]:
    """Fetch (name, line1, line2) for a single NORAD ID from CelesTrak."""
    resp = requests.get(
        CELESTRAK_URL,
        params={"CATNR": norad_id, "FORMAT": "TLE"},
        timeout=15,
    )
    resp.raise_for_status()
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    if len(lines) < 3:
        raise ValueError(f"no TLE returned (empty or malformed response: {resp.text[:200]!r})")
    return lines[0].strip(), lines[1], lines[2]


def build_entry(catalog_sat: dict, ts) -> dict:
    """Fetch + validate one satellite's TLE. Raises on any failure."""
    norad_id = catalog_sat["norad_id"]
    celestrak_name, line1, line2 = fetch_tle(norad_id)

    sat = EarthSatellite(line1, line2, celestrak_name, ts)

    # Sanity-propagate right now, same as validate_tle.py, so a bad TLE
    # fails loudly here rather than silently breaking the frontend later.
    now = ts.now()
    subpoint = wgs84.subpoint(sat.at(now))

    epoch_dt = sat.epoch.utc_datetime()
    age_days = (now.utc_datetime() - epoch_dt).total_seconds() / 86400

    return {
        "norad_id": norad_id,
        "name": catalog_sat["name"],
        "celestrak_name": celestrak_name,
        "line1": line1,
        "line2": line2,
        "epoch": epoch_dt.isoformat(),
        "tle_age_days": round(age_days, 2),
        "current_position": {
            "latitude_deg": round(subpoint.latitude.degrees, 4),
            "longitude_deg": round(subpoint.longitude.degrees, 4),
            "altitude_km": round(subpoint.elevation.km, 1),
        },
        "fetched_at": now.utc_iso(places=3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="seconds to wait between requests, be polite to CelesTrak (default: 0.5)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="only fetch the first N catalog entries (for quick testing)",
    )
    args = parser.parse_args()

    targets = SATELLITES[: args.limit] if args.limit else SATELLITES
    ts = load.timescale()

    results = []
    failures = []

    print(f"Fetching TLEs for {len(targets)} satellites from CelesTrak...")
    for i, catalog_sat in enumerate(targets, 1):
        label = f"{catalog_sat['name']} (NORAD {catalog_sat['norad_id']})"
        try:
            entry = build_entry(catalog_sat, ts)
            results.append(entry)
            age = entry["tle_age_days"]
            flag = " [STALE]" if age > STALE_WARNING_DAYS else ""
            print(f"  [{i}/{len(targets)}] OK   {label} -- TLE age {age:.1f}d{flag}")
        except (requests.RequestException, ValueError) as e:
            failures.append({"norad_id": catalog_sat["norad_id"], "name": catalog_sat["name"], "error": str(e)})
            print(f"  [{i}/{len(targets)}] FAIL {label} -- {e}", file=sys.stderr)

        if i < len(targets):
            time.sleep(args.delay)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "celestrak.org",
        "count": len(results),
        "failed_count": len(failures),
        "satellites": results,
        "failures": failures,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")

    print()
    print(f"Wrote {OUTPUT_PATH.relative_to(OUTPUT_PATH.parent.parent)} "
          f"({OUTPUT_PATH.stat().st_size:,} bytes)")
    print(f"  {len(results)} succeeded, {len(failures)} failed")

    stale = [r for r in results if r["tle_age_days"] > STALE_WARNING_DAYS]
    if stale:
        print(f"  {len(stale)} TLE(s) older than {STALE_WARNING_DAYS} days -- still usable, "
              f"but positions will drift more than freshly-fetched ones")

    if failures:
        sys.exit(1)  # non-zero exit so a CI job (Stage 6) notices


if __name__ == "__main__":
    main()
