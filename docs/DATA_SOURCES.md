# Data sources

| Dataset | Class | Provider | Use | Access |
|---|---|---|---|---|
| Mars 2020 Science Investigation **CTX DEM mosaic**, Jezero, 20 m/px (`M20_JezeroCrater_CTXDEM_20m.tif` + XML label) | Real | USGS Astrogeology / NASA JPL | elevation → all terrain, hazards, routes | `scripts/download_data.py` or module 04 · catalog: https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic |
| THEMIS IR Day mosaic 100 m (optional) | Real | USGS / ASU / NASA | thermal layer on the map | URL in `config.THEMIS_DAY_URL` |
| Viking MDIM 2.1 colour, MOLA shaded relief (WMTS tiles) | Real | NASA JPL **Mars Trek** | basemaps (module 02) | https://trek.nasa.gov/mars/ — loaded live by the browser |
| Octavia E. Butler landing site 18.4447° N, 77.4508° E | Real (published) | NASA/JPL | default start point | — |
| Curiosity RAD surface dose 0.64 mSv/day | Real (published) | Hassler et al. 2014, Science 343 | dose model | doi:10.1126/science.1244797 |
| NAIF SPICE kernels naif0012.tls, pck00011.tpc, de440s.bsp (optional) | Real | NASA NAIF | Sun geometry (module 12) | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/ |
| MEDA-like weather CSV | User Supplied (upload) / Synthetic (sample) | user / generated | module 13 | NASA PDS Atmospheres node for real MEDA data |
| Surface images for CV | User Supplied / Synthetic test scene | user / generated | module 07 | e.g. Perseverance raw images https://mars.nasa.gov/mars2020/multimedia/raw-images/ |
| **SYNTHETIC DEM** (procedural craters, delta, NoData patch) | Synthetic | this project | used only until a real DEM is loaded; badge shown on every page | generated in code |
| Relay orbits, navigation sensors, suit telemetry | Simulated | this project | modules 08–11, 14 | models |
| **NASA DONKI** space weather (FLR, SEP, CME + WSA-ENLIL, GST) | Real (fetched) / User Supplied (file) / Synthetic (bundled format example) | NASA CCMC / M2M SWAO via api.nasa.gov | EVA radiation flag (module 13 → 20) | https://api.nasa.gov/ — key in `.env` as `NASA_API_KEY` |
| **Perseverance traverse** (MMGIS `M20_traverse.json`) | Real (fetched) / User Supplied / Synthetic (bundled example near the landing site) | NASA/JPL | ground-truth proximity, map layer (modules 02, 18) | https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json |
| **Perseverance raw images** feed | Real (fetched) / User Supplied | NASA/JPL-Caltech (ASU for Mastcam-Z) | "what the astronaut will see" (module 18) | https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&sol=N |
| Traversability model labels | Simulated (rule-derived from the active DEM) | this project | supervised ML (module 07) | — |
| Science targets: delta front, Séítah, crater floor | approximate (labelled "verify") | user / NASA public maps | module 18 | verify in Mars Trek |

## How the DEM is processed (no value changes)
1. HTTP download with resume, status and size checks (`mars_survive/dem/loader.py::download`).
2. The XML/PDS4 label is parsed with `defusedxml` (safe against XML attacks).
3. Only a window around Jezero (±0.18° around 18.44° N, 77.45° E) is **reprojected/resampled** with rasterio
   (bilinear) to a planetocentric lat/lon grid at 50 m — elevations are interpolated, never edited, offset or smoothed.
   NoData stays NoData.
4. A quality report (valid fraction, NoData count, spike check) and a SHA-256 hash are stored in the provenance
   registry (module 22). The grid is saved to `data/processed/` and the app switches the badge to **REAL**.

## Bundled synthetic examples
`mars_survive/nasa_live/examples/` contains small files **in the formats** of DONKI, the M20 traverse and the raw-image
feed. Their identifiers start with `SYNTH-`, they carry a note "not NASA data", and the app labels them SYNTHETIC.
They exist so the modules can be demonstrated and tested offline; they are never shown as NASA data.

## Not reachable from the development sandbox
The build environment had no access to NASA/USGS servers (DEM, DONKI, traverse, raw images), so all screenshots and tests here use the SYNTHETIC DEM and the synthetic format examples.
The download/processing code is covered by unit tests on a locally generated GeoTIFF; the real download must be run
once on your computer.
