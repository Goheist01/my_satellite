# My_Satellite

A mobile-first, indie-game-styled globe that shows real public Earth
Observation satellites, positioned live from their actual current orbits —
not illustrations, not a fixed animation loop. Drag to roam a stylized
"little planet," tap any satellite to read what it is, and where the data
exists, see its most recent real image.

**Live app:** `https://goheist01.github.io/my_satellite/web/index.html`
**Built by:** [Jose Escobar](https://goheist01.github.io/jose-escobar-cv/)

---

## What this is, and who it's for

This project exists to make an otherwise invisible piece of infrastructure
tangible: dozens of public satellites are watching Earth right now, run by
NASA, NOAA, ESA, and JAXA, feeding weather forecasts, disaster response, and
climate records — and almost nobody who isn't in the field has ever seen
them as individual, real, currently-orbiting objects.

Two audiences, honestly:

1. **Anyone curious what's actually up there** — the app itself, no
   technical background required. Drag, look, tap, read.
2. **Anyone evaluating my engineering work** — this README, and the
   debugging journey below in particular. The visual polish is the easy
   part to demonstrate; the harder, more specific claim is genuine EO
   domain literacy and the discipline to verify rather than assume, which
   is what the rest of this document is actually for.

## From the original vision to what shipped

The original plan (see `docs/vision.md` if still present, or the project's
git history) was a horizontal-scroll strip along a flat stylized Earth
surface. That was deliberately replaced early on with a fully 3D "little
planet" — a small rotatable globe with a true trackball camera (Rodrigues
rotation), satellites receding into a perspective horizon band. The pivot
was a considered creative decision, not scope creep: it kept every original
non-negotiable (real orbital data drives placement, static-site-only, no
backend, mobile data budget matters) while giving the interaction far more
depth than a fixed-axis scroll ever could.

All six original stages are complete:

| Stage | What it was                                   | Status                                                                                                  |
| ----- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1     | Curated satellite catalog, verified NORAD IDs | Done — 25 satellites across NASA, NOAA, ESA, JAXA                                                       |
| 2     | Live position math (SGP4)                     | Done — client-side via satellite.js                                                                     |
| 3     | Stylized rendering surface                    | Done — pivoted to the little-planet trackball                                                           |
| 4     | Clickable satellites, info panel              | Done — plus search/filter, live capture imagery, instrument explainers (well beyond original MVP scope) |
| 5     | Decorative lattice between satellites         | Done — nearest-neighbor (k=2), recalculated every frame                                                 |
| 6     | Package & deploy                              | This document                                                                                           |

## Architecture

### Client — `web/index.html`

A single static file, no build step, no framework. Deliberately: this keeps
the "zero-cost, zero-backend, deploy to GitHub Pages" story completely
literal, and means anyone can read the entire client in one file rather
than hunting through a bundler's output.

- **Rendering:** Pixi.js v8. All satellite sprites, the whale easter egg,
  the sun/moon, and the starfield are procedurally generated pixel art
  drawn in code — no image assets, which matters for the mobile data budget
  and sidesteps licensing entirely.
- **Orbital math:** satellite.js running SGP4 propagation directly in the
  browser from the TLE data the pipeline below fetches.
- **Camera:** a true 3D trackball (unit-quaternion-free, plain Rodrigues
  axis-angle rotation) — see the debugging section below for what it took
  to get this actually correct near the poles.
- **Audio:** entirely synthesized via the Web Audio API — a self-built
  convolution reverb (a noise burst shaped by an exponential decay, which
  is literally what a reverb impulse response is), procedural whale song,
  wind/water noise layers, flute and mallet runs. Zero audio files.

### Data pipeline — `scripts/refresh_data.py` + `.github/workflows/refresh.yml`

This is the part that keeps the app honest about the word "live." A
GitHub Action runs **every 6 hours** and does two genuinely different jobs
on two genuinely different cadences, on purpose:

- **TLE refresh is self-throttled to roughly every 48 hours**, even though
  the Action itself wakes up every 6. This isn't laziness — CelesTrak's own
  usage guidance explicitly asks integrators not to poll more than
  necessary ("daily usually suffices... every 3 days is fine for a stable
  orbit"), and refreshing 4x more often than a free, community-run service
  says is useful would be inconsiderate for no real accuracy benefit at
  this catalog's orbital regime.
- **Capture-image resolution runs every time the Action wakes up** (every
  6h), since there's no equivalent "please don't check so often" guidance
  for the imagery sources, and a new scene can appear at any point in a
  multi-day revisit window.
- **A `status.json` heartbeat is written on every single run, unconditionally** —
  even when nothing else changed. This does two jobs: it's the
  staleness-monitoring signal the app reads to show "last checked," and it
  keeps the repository's commit history active enough that GitHub's
  automatic 60-day disable of inactive scheduled workflows (public repos)
  never triggers, even through a long stretch where the actual data
  happens not to change.
- Every data file write is diff-gated — content is only committed when it
  actually changed, so routine "checked, nothing new" runs don't pollute
  the commit history with noise.

### Why some satellites show "Data" instead of a picture

Four of the catalog's satellites are fundamentally non-imaging: **ICESat-2**
(laser altimetry), **Sentinel-6 Michael Freilich** (radar altimetry, sea
level), **Sentinel-5P** (atmospheric spectrometer), and **SMAP** (soil-moisture
radiometer). None of these produce a 2D picture no matter how the data gets
rendered — an altimeter measures a height profile, a spectrometer measures
a gas concentration.

A larger group of genuinely imaging satellites — Terra, Aqua, the VIIRS
series (Suomi NPP, NOAA-20/21), CBERS-4, ALOS-2/4, Sentinel-1's SAR trio,
and Sentinel-3's ocean-colour instrument — don't yet have a resolver built
for their specific data source. Each lives in its own archive with its own
API shape (NASA GIBS for MODIS/VIIRS, different rendering considerations
for raw SAR), and building each one is real, separate work (see "Known
limitations" below), not an afternoon's extension of what already exists.

For all of these, the dex panel shows a **"See data"** button instead of
"See last capture": the instrument type, a plain-language explanation of
how it actually works, and the satellite's own live position. **Turning
that raw instrument data into its own genuine visualization — an actual
sea-level anomaly plot, a real ice-thickness time series — is legitimate
future work, explicitly scoped as a separate later stage, not attempted
here.** This is an honest design choice, not a placeholder apologizing for
missing work.

Where a picture _is_ available, it comes from one of two genuinely
different mechanisms:

- **GOES (16/19):** a stable, always-current URL straight from NOAA's own
  CDN. No caching, no scheduled fetch — it's live by construction, so the
  overlay says "live," not a specific timestamp.
- **Sentinel-2 and Landsat:** resolved via Earth Search's STAC API against
  each satellite's live current position, filtered by platform (so
  "Sentinel-2C's last capture" is genuinely a 2C scene, not whichever
  Sentinel-2 satellite happened to pass nearest), and filtered for scene
  quality (see the nodata-vs-cloud-cover bug below) before picking the
  most recent usable result.

## Repository structure

```
my_satellite/
├── .github/
│   └── workflows/
│       └── refresh.yml        # scheduled Action: every 6h, see above
├── catalog/
│   ├── satellites.py           # hand-curated source of truth -- edit THIS to add/remove satellites
│   └── build_catalog.py        # validates satellites.py, writes data/satellites.json
├── data/
│   ├── satellites.json         # generated FROM catalog/, committed since the static site fetches it at runtime
│   ├── tle.json                 # live orbital elements (generated, self-throttled ~48h)
│   ├── captures.json            # resolved "last capture" imagery pointers (generated)
│   └── status.json              # heartbeat + per-source success/error tracking (generated)
├── scripts/
│   └── refresh_data.py         # the scheduled fetch/resolve script -- see below
├── web/
│   └── index.html              # the entire client app -- single file, no build step
├── requirements.txt             # skyfield, sgp4 -- refresh_data.py's only dependencies
├── LICENSE
└── README.md                    # this file
```

## What each script does

**`catalog/satellites.py`** — the actual hand-curated source of truth. A
plain Python list of dicts, one per satellite, each with a NORAD ID, agency,
launch year, data type, a one-line description, and an optional status note
for anything in a notable transitional state (e.g. Terra winding down toward
end of mission). Every NORAD ID here was cross-checked against a primary
source before being added — the file's own docstring is explicit that a
wrong ID means the whole pipeline propagates the wrong object entirely, not
a graceful failure. It also documents _exclusions on purpose_ — Landsat 7
and the original NOAA-19 (both decommissioned), GOES-17 (in-orbit backup,
not a primary source), Sentinel-1B (failed 2021) — so a later editor
doesn't accidentally re-add something that was deliberately left out.

**`catalog/build_catalog.py`** — validates `satellites.py` before writing
`data/satellites.json`, the artifact the live app actually fetches. Checks
every required field is present and correctly typed, NORAD IDs are in a
plausible range (extended to 6 digits for CelesTrak's post-2026 catalog
numbers), no duplicate NORAD ID _or_ duplicate name, launch years fall
between 1957 and now, and descriptions stay under ~200 characters so they
actually fit a one-line info panel. Run this after hand-editing
`satellites.py`, before anything else touches the result:

```bash
python3 catalog/build_catalog.py
```

**`scripts/refresh_data.py`** — the scheduled pipeline, entirely separate
from the catalog above. Fetches TLEs from CelesTrak (self-throttled, see
above), resolves capture imagery for Sentinel-2 and Landsat via Earth
Search STAC (platform-filtered, quality-filtered), and writes the status
heartbeat. Safe to run manually:

```bash
pip install -r requirements.txt
python3 scripts/refresh_data.py              # normal run, respects the TLE throttle
python3 scripts/refresh_data.py --force-tle   # bypass the throttle, force a fresh TLE fetch
```

## What didn't work the first time, and how it actually got fixed

This is the part most READMEs skip, and it's the part that actually
demonstrates the engineering more than any feature list could. Every one of
these was a real bug, caught and fixed with a numerical test proving the
fix — not just "tried something, seemed fine."

**Gimbal lock at the poles, three separate times.** The camera's rotation
math was correct from the start (a straight vertical drag provably traces a
true great circle — verified analytically and numerically). The actual bugs
were all in code _around_ that math: the nadir mini-map's steering function
rebuilt its east/north basis from world-Z each frame, which degenerates
exactly at the poles; the mini-map's _drawing_ code had the identical bug,
independently, because fixing the steering code didn't touch the separate
function that renders it; and the auto-snap-to-nearest-satellite behavior
had a hard ceiling at ~82° latitude, because the catalog's sun-synchronous
satellites genuinely never orbit closer to the pole than that — so the
snap had nothing to center on above that latitude and kept pulling the view
back down. Each was found by building a debug HUD that reports which code
path (drag, wheel, or snap) is actually moving the view each frame, rather
than continuing to guess.

**Orbital position math was silently missing Earth's rotation.** An early
version of the server-side position calculation converted a satellite's raw
SGP4 output directly to longitude — but that raw output is in an _inertial_
reference frame that doesn't rotate with the Earth. The bug was invisible
in a spot-check and only showed up when tested across a time gap: the same
satellite, propagated 6 hours apart, should show roughly 90° of apparent
longitude drift from Earth's rotation alone, and the naive version showed
none. Fixed using `skyfield`'s proper frame conversion instead of hand-rolled
trigonometry.

**CelesTrak's `FORMAT=JSON` doesn't contain TLE lines.** It returns OMM-style
numeric orbital elements — a different _representation_ of the same orbit,
not TLE text with a different wrapper. `FORMAT=TLE` was the actual fix,
verified against a live response before trusting it.

**Landsat's thumbnail asset is requester-pays and unusable from a browser.**
Confirmed directly against Element84's own published example: the asset
href is an `s3://` URL explicitly flagged `storage:requester_pays: true`,
which needs AWS credentials no visitor's browser can provide. The fix uses
Earth Search's separate, publicly-served `/thumbnail` API link instead —
verified the resolver correctly avoids the trap using a test built from
that exact real example, including the bad URL, to prove it never leaks
through.

**A "most recent" scene isn't the same as a usable one.** A real capture
came back as a flat white image despite loading successfully — direct
inspection confirmed it wasn't a rendering bug, the source image itself was
genuinely blank. The cause: Sentinel-2's STAC metadata tracks cloud cover
and no-data percentage as two _independent_ dimensions — a real example
item had 0.4% cloud cover and 77% no-data simultaneously, an edge-of-swath
tile that passed a naive cloud check while being almost entirely empty. The
fix filters on both and prefers the most recent scene that clears a
reasonable bar on each, falling back to the best available if nothing in
the search window clears it — a flawed real image still beats reporting no
capture at all.

**An absolute-path bug that only breaks on the real deployment target.**
Every data fetch used a leading-slash path (`/data/tle.json`), which
resolves against the browser's _origin_, not wherever the page happens to
sit. That's invisible testing locally, because a local dev server run from
the project root makes the origin and the project root coincide by
accident. GitHub Pages serves project sites from a subpath
(`username.github.io/repo-name/...`), which breaks that coincidence — the
absolute path would have silently pointed at the wrong location on first
deploy, with every data fetch failing on a real visitor's very first look.
Fixed to relative paths, verified against both the local and live URL
shapes using the actual browser URL-resolution algorithm before shipping.

## Known limitations — honest, not hidden

- **Capture image coverage is partial.** As of this writing, only
  Sentinel-2, Landsat, and GOES have resolvers built — roughly a third of
  the catalog. Everything else shows the plain-language "Data" explainer
  described above. This is accurately represented in the app, not
  papered over.
- **The polar cap has a real ceiling.** Since the catalog is dominated by
  sun-synchronous orbits (~98° inclination), no satellite's ground track
  ever gets closer than ~82° to either pole. Above that latitude there's
  genuinely nothing to auto-center on.
- **Mobile has been checked via Chrome DevTools' device emulation, not yet
  on a physical device.** Emulation is a meaningful check — it caught real
  layout issues — but it doesn't perfectly replicate real touch latency or,
  notably, iOS Safari's specific audio-unlock behavior, which is stricter
  than desktop Chrome's. Worth a real-device pass before treating audio-on-mobile
  as fully confirmed.
- **The debug HUD (press `D`) is intentionally left live**, not forgotten.
  It's the actual instrumentation used to diagnose the pole-navigation bugs
  above — included as a small, honest artifact of the debugging process
  rather than removed for a falsely polished appearance.

## Local development

```bash
python3 -m http.server 8000   # from the project root
```

Then open `http://localhost:8000/web/index.html`.

## License

MIT — see [`LICENSE`](./LICENSE). Covers this repository's own code only;
data fetched at runtime remains governed by each source's own terms (below).

## Data sources & attribution

- **Orbital elements:** [CelesTrak](https://celestrak.org) (public domain)
- **Sentinel-2 / Landsat imagery:** [Earth Search](https://earth-search.aws.element84.com) by Element 84, indexing Copernicus (ESA) and USGS/NASA open data
- **GOES imagery:** [NOAA STAR](https://www.star.nesdis.noaa.gov/)
- **Coastlines:** [Natural Earth](https://www.naturalearthdata.com/) 110m, public domain
