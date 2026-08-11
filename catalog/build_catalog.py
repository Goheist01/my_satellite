#!/usr/bin/env python3
"""
Stage 1 build script.

Validates the curated SATELLITES list in satellites.py and writes it out as
data/satellites.json -- the static metadata file the frontend (Stage 4) will
fetch to populate info panels. This script does NOT touch the network; it
only validates and serializes data that's already been hand-curated.

Run:
    python3 catalog/build_catalog.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from satellites import SATELLITES

REQUIRED_FIELDS = {
    "norad_id": int,
    "name": str,
    "agency": str,
    "launch_year": int,
    "data_type": str,
    "description": str,
    "status_note": str,
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "satellites.json"


def validate() -> list[str]:
    """Return a list of validation error strings (empty list = all good)."""
    errors = []
    seen_ids = set()
    seen_names = set()
    current_year = datetime.now().year

    if not SATELLITES:
        errors.append("SATELLITES list is empty.")
        return errors

    for i, sat in enumerate(SATELLITES):
        label = sat.get("name", f"entry #{i}")

        # Required fields present and correctly typed
        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in sat:
                errors.append(f"[{label}] missing required field '{field}'")
                continue
            if not isinstance(sat[field], expected_type):
                errors.append(
                    f"[{label}] field '{field}' should be {expected_type.__name__}, "
                    f"got {type(sat[field]).__name__}"
                )

        if "norad_id" not in sat or "name" not in sat:
            continue  # can't do further checks without these

        # NORAD ID sanity: positive, 5-6 digits (post-2026 objects can be 6 digits)
        norad_id = sat["norad_id"]
        if not (1 <= norad_id <= 999999):
            errors.append(f"[{label}] norad_id {norad_id} out of plausible range")

        # Duplicate detection
        if norad_id in seen_ids:
            errors.append(f"[{label}] duplicate norad_id {norad_id}")
        seen_ids.add(norad_id)

        if sat["name"] in seen_names:
            errors.append(f"[{label}] duplicate name '{sat['name']}'")
        seen_names.add(sat["name"])

        # Launch year sanity
        launch_year = sat.get("launch_year")
        if isinstance(launch_year, int) and not (1957 <= launch_year <= current_year):
            errors.append(f"[{label}] launch_year {launch_year} looks wrong")

        # Description length -- keep panels tight per the one-line design rule
        desc = sat.get("description", "")
        if isinstance(desc, str) and len(desc) > 200:
            errors.append(
                f"[{label}] description is {len(desc)} chars -- keep it to one line (~200 max)"
            )

    return errors


def build() -> None:
    errors = validate()
    if errors:
        print(f"Validation failed with {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(SATELLITES),
        "satellites": sorted(SATELLITES, key=lambda s: s["name"]),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")

    print(f"Validated {len(SATELLITES)} satellites -- no errors.")
    print(f"Wrote {OUTPUT_PATH.relative_to(OUTPUT_PATH.parent.parent)} "
          f"({OUTPUT_PATH.stat().st_size:,} bytes)")

    agencies = sorted({s["agency"] for s in SATELLITES})
    print(f"Agencies represented ({len(agencies)}): {', '.join(agencies)}")


if __name__ == "__main__":
    build()
