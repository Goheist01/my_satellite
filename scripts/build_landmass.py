#!/usr/bin/env python3
"""
Build the stylized landmass file used by the visualizer's earth surface.

Source: Natural Earth 110m "land" polygons (public domain), pulled from the
natural-earth-vector GitHub mirror. Raw 110m data is already coarse, but it's
still far more detail than a stylized indie-game surface needs -- and every
extra vertex costs mobile bandwidth and per-frame projection math. So this
script simplifies aggressively (Douglas-Peucker) and drops tiny islands,
keeping only what reads as recognizable continent shapes.

The goal is "you can tell that's Africa", not cartographic accuracy.

Output: data/land.json
    {
      "generated_at": ...,
      "source": ...,
      "polygon_count": N,
      "vertex_count": M,
      "polygons": [ [[lon, lat], [lon, lat], ...], ... ]
    }

Run:
    python3 scripts/build_landmass.py
    python3 scripts/build_landmass.py --tolerance 1.5 --min-area 8
"""

import argparse
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_land.geojson"
)
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "land.json"


def perpendicular_distance(pt, start, end):
    """Distance from pt to the segment start-end, in degrees."""
    (x, y), (x1, y1), (x2, y2) = pt, start, end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return math.hypot(x - px, y - py)


def douglas_peucker(points, tolerance):
    """Classic polyline simplification. Iterative, to avoid recursion limits."""
    if len(points) < 3:
        return points[:]

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]

    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        max_dist, index = 0.0, first
        for i in range(first + 1, last):
            d = perpendicular_distance(points[i], points[first], points[last])
            if d > max_dist:
                max_dist, index = d, i
        if max_dist > tolerance:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))

    return [p for p, k in zip(points, keep) if k]


def ring_area_deg2(ring):
    """Shoelace area in square degrees -- a rough size proxy, good enough for
    filtering out specks. Not real surface area (no latitude correction)."""
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def crosses_antimeridian(ring):
    """True if consecutive vertices jump more than 180 deg of longitude --
    these polygons wrap the date line and tear badly when projected, so they
    get dropped rather than rendered wrong."""
    for i in range(len(ring) - 1):
        if abs(ring[i + 1][0] - ring[i][0]) > 180:
            return True
    return False


def extract_rings(geojson):
    """Yield outer rings from Polygon / MultiPolygon features (holes ignored --
    lakes aren't worth the vertices at this scale)."""
    for feature in geojson["features"]:
        geom = feature.get("geometry") or {}
        gtype = geom.get("type")
        if gtype == "Polygon":
            if geom["coordinates"]:
                yield geom["coordinates"][0]
        elif gtype == "MultiPolygon":
            for poly in geom["coordinates"]:
                if poly:
                    yield poly[0]


def build(tolerance: float, min_area: float, max_vertices_per_poly: int) -> None:
    print(f"Fetching {SOURCE_URL} ...")
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            geojson = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 -- surface any network/parse failure plainly
        print(f"Failed to fetch source data: {e}", file=sys.stderr)
        print("This script needs outbound access to raw.githubusercontent.com.", file=sys.stderr)
        sys.exit(1)

    raw_rings = list(extract_rings(geojson))
    print(f"  {len(raw_rings)} raw rings")

    polygons = []
    dropped_small = dropped_wrap = 0
    for ring in raw_rings:
        pts = [(float(x), float(y)) for x, y in ring]
        if crosses_antimeridian(pts):
            dropped_wrap += 1
            continue
        if ring_area_deg2(pts) < min_area:
            dropped_small += 1
            continue

        simplified = douglas_peucker(pts, tolerance)

        # progressively coarsen anything still over budget
        t = tolerance
        while len(simplified) > max_vertices_per_poly and t < 20:
            t *= 1.5
            simplified = douglas_peucker(pts, t)

        if len(simplified) < 4:
            dropped_small += 1
            continue

        # close the ring, round to 2dp (~1km at the equator; plenty here)
        rounded = [[round(x, 2), round(y, 2)] for x, y in simplified]
        if rounded[0] != rounded[-1]:
            rounded.append(rounded[0])
        polygons.append(rounded)

    polygons.sort(key=len, reverse=True)
    vertex_count = sum(len(p) for p in polygons)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Natural Earth 110m land (public domain)",
        "simplification": {
            "tolerance_deg": tolerance,
            "min_area_deg2": min_area,
            "max_vertices_per_polygon": max_vertices_per_poly,
        },
        "polygon_count": len(polygons),
        "vertex_count": vertex_count,
        "polygons": polygons,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, separators=(",", ":")) + "\n")

    print(f"  dropped {dropped_small} small, {dropped_wrap} antimeridian-crossing")
    print(f"Wrote {OUTPUT_PATH.name}: {len(polygons)} polygons, "
          f"{vertex_count} vertices, {OUTPUT_PATH.stat().st_size:,} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tolerance", type=float, default=1.2,
                        help="Douglas-Peucker tolerance in degrees (higher = blockier, default 1.2)")
    parser.add_argument("--min-area", type=float, default=6.0,
                        help="drop polygons smaller than this many square degrees (default 6)")
    parser.add_argument("--max-vertices", type=int, default=90,
                        help="per-polygon vertex ceiling (default 90)")
    args = parser.parse_args()
    build(args.tolerance, args.min_area, args.max_vertices)


if __name__ == "__main__":
    main()
