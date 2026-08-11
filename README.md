# Public EO Satellite Orbit Visualizer

Mobile-first, indie-game-styled scroll along Earth's surface, showing real
public Earth Observation satellites as they actually orbit. See project
vision doc for full scope, tech stack, and design principles.

## Status: Stage 1 complete (2026-08-07)

- `catalog/satellites.py` -- curated list of 25 public EO satellites, every
  NORAD ID verified against current sources (not pulled from memory).
  Covers NASA (Terra, Aqua, Landsat 8/9, SMAP, ICESat-2), NOAA/JPSS
  (Suomi NPP, NOAA-20/21, GOES-16/18/19), ESA Copernicus (Sentinel-1A/C/D,
  2A/B/C, 3A/B, 5P, 6), JAXA (ALOS-2/4), and CNSA/INPE (CBERS-4).
- `catalog/build_catalog.py` -- validates the curated list (types, duplicate
  IDs, plausible launch years, description length) and writes
  `data/satellites.json`.
- `data/satellites.json` -- the Stage 1 output. 25 satellites, ~8KB.
- `scripts/validate_tle.py` -- early Stage 2 smoke test. Fetches a live TLE
  from CelesTrak for a given NORAD ID and propagates it with skyfield/sgp4
  to print current lat/lon/altitude. **Needs real internet access** --
  wasn't runnable in the sandbox that built this (celestrak.org isn't on
  its network allowlist), so run it locally before trusting it further:

  ```bash
  pip install -r requirements.txt
  python3 scripts/validate_tle.py                 # ISS, sanity-check against a public tracker
  python3 scripts/validate_tle.py --norad 49260    # Landsat 9
  ```

  If the ISS position looks right (compare to https://spotthestation.nasa.gov/),
  the SGP4 pipeline is trustworthy and Stage 2 proper (satellite.js in the
  browser, same math) is low-risk.

## A few things worth knowing before Stage 2

- **Terra and Aqua are winding down.** Both are in their final mission phase
  (planned end of science ~2027). Still real, active, publicly-accessible
  data sources today, so they're included -- but don't be surprised if they
  need a "legacy" visual treatment or eventual removal down the line.
- **CelesTrak hit its 5-digit catalog number ceiling in mid-2026.** New
  objects now get 6-digit NORAD IDs, which aren't available in classic TLE
  format (only newer OMM/JSON formats). Doesn't affect anything in this
  catalog -- all 25 satellites have long-standing 5-digit IDs -- but if you
  add a very recently launched satellite later, check whether it has a
  5-digit ID before assuming `FORMAT=TLE` will return it.
- Excluded on purpose: Landsat 7 and NOAA-19 (both decommissioned in 2025),
  GOES-17 (in-orbit backup, not a primary data source), Sentinel-1B (failed
  2021). See the docstring in `satellites.py` for the full exclusion list.

## Next up: Stage 2

Pull live TLEs for all 25 catalog NORAD IDs (not just one at a time), and
get satellite.js doing the same propagation client-side in the browser.
Once that's validated, Stage 3 starts on the actual Pixi.js scrolling
surface.
