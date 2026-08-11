#!/usr/bin/env python3
"""
Stage 2 smoke test (early derisking, not the full Stage 2 build).

Fetches a live TLE from CelesTrak for a given NORAD ID, propagates it with
skyfield/sgp4, and prints the satellite's current subpoint (lat/lon/altitude).

Run against the ISS first (NORAD 25544) since its position is very easy to
sanity-check by eye against any public tracker (e.g. https://spotthestation.nasa.gov/).
Once that looks right, run it against a couple of satellites from our own
catalog to confirm the client-side math (satellite.js will do the JS version
of this same SGP4 propagation) will get sane real longitude/altitude values
for Stage 3's horizontal-scroll placement.

NOTE: this needs outbound network access to celestrak.org. If you're running
this from an environment that blocks that domain, it'll fail with a network
error -- that's expected, run it somewhere with normal internet access
(your own machine, or the GitHub Action in Stage 6).

Usage:
    python3 scripts/validate_tle.py                  # defaults to ISS
    python3 scripts/validate_tle.py --norad 49260     # Landsat 9, e.g.
"""

import argparse
import sys

import requests
from skyfield.api import EarthSatellite, load, wgs84

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php"
ISS_NORAD_ID = 25544


def fetch_tle(norad_id: int) -> tuple[str, str, str]:
    """Fetch (name, line1, line2) for a NORAD ID from CelesTrak."""
    resp = requests.get(
        CELESTRAK_URL,
        params={"CATNR": norad_id, "FORMAT": "TLE"},
        timeout=15,
    )
    resp.raise_for_status()
    lines = [l for l in resp.text.strip().splitlines() if l.strip()]
    if len(lines) < 3:
        raise ValueError(
            f"CelesTrak returned no TLE for NORAD {norad_id} "
            f"(satellite may be decayed, or the ID is wrong). Raw response:\n{resp.text}"
        )
    name, line1, line2 = lines[0].strip(), lines[1], lines[2]
    return name, line1, line2


def propagate_and_print(norad_id: int) -> None:
    name, line1, line2 = fetch_tle(norad_id)
    ts = load.timescale()
    sat = EarthSatellite(line1, line2, name, ts)

    t = ts.now()
    geocentric = sat.at(t)
    subpoint = wgs84.subpoint(geocentric)

    print(f"{name} (NORAD {norad_id})")
    print(f"  time (UTC):  {t.utc_iso()}")
    print(f"  latitude:    {subpoint.latitude.degrees:.4f} deg")
    print(f"  longitude:   {subpoint.longitude.degrees:.4f} deg")
    print(f"  altitude:    {subpoint.elevation.km:.1f} km")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--norad", type=int, default=ISS_NORAD_ID,
        help=f"NORAD catalog number to test (default: {ISS_NORAD_ID}, the ISS)",
    )
    args = parser.parse_args()

    try:
        propagate_and_print(args.norad)
    except requests.RequestException as e:
        print(f"Network error reaching CelesTrak: {e}", file=sys.stderr)
        print(
            "This script needs outbound access to celestrak.org -- run it "
            "from your own machine or CI, not a network-restricted sandbox.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
