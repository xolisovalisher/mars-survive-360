# MARS SURVIVE 360 — Project brief and scientific assessment

NASA Space Apps 2026 · *Interplanetary Survival Guide: Martian Map* · Region: Jezero crater

> This is a prototype for decision support and education. Its models are simplified and openly labelled; its
> outputs are **not** safety recommendations for astronauts.

---

## Part A — The organisers' four questions

### 1. What problem does the product solve?
NASA tools such as JPL Mars Trek and the USGS geologic maps let you layer data over **regional and global** maps
of Mars. A Marswalk, however, is planned at the scale of a few kilometres and a few hours, and the crew has to
answer these questions:
- Which way should we go?
- What will we see there?
- Will our oxygen and power last?
- Can we always get back, and when must we turn around?
- Will the radio work?
- Is the Sun quiet today?

MARS SURVIVE 360 brings those answers together for one location, Jezero crater, in a single tool:
- terrain and hazards;
- four alternative routes;
- consumables along each route;
- the last safe turn-back point;
- GPS-free navigation accuracy;
- radio and relay coverage;
- space weather;
- what the Perseverance rover saw at each point;
- a risk matrix, an emergency simulation and an exportable mission report.

### 2. Which real NASA data are used?

| NASA / USGS source | How the app uses it | Status in the delivered build |
|---|---|---|
| USGS Astrogeology **Mars 2020 CTX DEM mosaic of Jezero** (20 m/px) | Elevation → slope, roughness, hazards, routes, 3D view | Downloader and processor implemented. NASA servers were unreachable from the build machine, so the delivered tests run on a clearly labelled **SYNTHETIC DEM** until the user downloads the real one. |
| **NASA JPL Mars Trek** WMTS: Viking MDIM 2.1 colour and MGS MOLA shaded relief | Optical and topographic basemaps | Tiles are loaded live by the browser. |
| **NASA DONKI** (flares, SEP, CME with WSA-ENLIL Mars arrivals, storms) | EVA radiation flag; feeds the risk matrix | Live client implemented; works with an api.nasa.gov key. |
| **Perseverance traverse** (NASA/JPL MMGIS M20 GeoJSON) | Ground truth: the route's proximity to terrain a rover really drove | Live client implemented; a saved file can also be loaded. |
| **Perseverance raw images** (mars.nasa.gov feed) | "What the astronaut will see" at route points | Live client implemented. |
| **Curiosity RAD** surface dose (Hassler et al. 2014) | Baseline radiation dose | Published value. |
| **NASA GISS Mars24** algorithm (Allison & McEwen 2000) | Mars time, season, Sun elevation | Validated against the paper's worked example. |
| **NAIF SPICE** kernels (LSK, PCK, SPK) | Sun geometry cross-check | Optional; used when the user adds the kernel files. |
| **Perseverance MEDA** format | Weather analysis | Accepts MEDA-style CSV uploads; the bundled sample is synthetic. |
| **THEMIS** IR day mosaic | Thermal layer | Optional. |

The challenge asks for at least three kinds of data. This build covers:
- **topographic** (DEM, MOLA);
- **optical** (Viking colour mosaic, rover raw images);
- **radiation and space weather** (RAD dose, DONKI);
- **atmospheric** (MEDA);
- **thermal** (THEMIS, optional).

Every result in the interface carries a badge: **Real**, **Synthetic**, **Simulated** or **User Supplied**.

### 3. What makes the solution different?
1. **Survival first, not just a map.** Every route is judged by whether the crew can get back. For each route
   the app computes:
   - oxygen and energy along the route;
   - the *survival envelope*: time out plus the fastest return time;
   - the **last safe turn-back point**.
2. **A supervised ML model inside the planner.** A traversability classifier is compared with two other models
   on map blocks it never saw in training:
   - the models: logistic regression, gradient boosting, and a PyTorch neural network;
   - the metrics: precision, recall, F1, ROC-AUC and PR-AUC.

   Its probability map feeds directly into the route cost. The model and its weaknesses are documented in a
   model card.
3. **Ground truth from a real rover.** Routes are compared with Perseverance's real path, and the raw images of
   the nearest sol show the crew what the terrain looks like.
4. **Space weather in the go/no-go decision.** DONKI events, including CME arrivals forecast for Mars, raise
   the radiation risk in the risk matrix.
5. **Honesty by design.** Data classes are shown everywhere. A **SYNTHETIC DEM** badge appears until real data
   are loaded, and no synthetic number is presented as a Mars measurement.
6. **Practical for a team.**
   - 27 working modules, a REST API and 18 interface languages, with Arabic right-to-left.
   - Reports in PDF, HTML, CSV, JSON and Excel.
   - A GIS GeoPackage in the Mars coordinate system IAU_2015:49900.
   - Windows and Linux one-click scripts.
   - 174 automated tests, all passing.

### 4. How will it help future Mars explorers?
- **Before the EVA (in the habitat):**
  - pick a route among four candidates with explicit trade-offs;
  - see the turn-back time and the oxygen reserve;
  - check radio shadows and relay windows;
  - read the space-weather flag;
  - look at real rover images of the places to be visited.
- **Rehearsal:** run emergency scenarios (oxygen leak, power loss, communication loss, navigation drift, terrain
  detour) and see the abort decision and the margins.
- **Science:** link science targets to the route and generate observation tasks.
- **After real data arrive:** retrain the ML model on the real DEM in one click. The same code then runs for
  any other landing site with a DEM.

---

## Part B — Assessment of scientific correctness

**Verdict.** The geometry, timekeeping and radio physics are standard and verified. The physiological, rover and
radiation models are first-order approximations, and they are labelled as such. The ML model is methodologically
sound, but its labels come from rules rather than field truth. The tool is therefore suitable for demonstration,
education and comparing options. It is **not** suitable for operational safety decisions.

### B1. What is correct and verified

| Area | Method | Evidence |
|---|---|---|
| Coordinates | Planetocentric latitude and east longitude, as used by the USGS Jezero products; planetographic latitude shown for reference | Unit test of the centric→graphic offset (0.204° at Jezero) |
| Distances | Haversine on the Mars mean sphere R = 3389.5 km; 3D length per edge √(dh² + dz²) | Error versus the ellipsoid is under 0.3 % over a few km, which is negligible against a 50 m grid; tested against an exported route geometry |
| Slope | Gradients on the true cell sizes, with dx = R·cos φ·Δλ | Analytic-surface tests |
| Routing | A* with an admissible heuristic (cost factor ≥ 1), so the result equals the Dijkstra optimum; no corner cutting through blocked cells | Unit tests |
| Mars time | Mars24 algorithm; TT − UTC from astropy's leap-second table | Matches Allison & McEwen (2000), with Ls = 277.18759°; astropy also corrects pre-1999 dates |
| Radio | Free-space path loss, Eb/N0 and link margin; terrain line of sight with a curvature bulge | Doubling the distance adds +6.02 dB (test) |
| Orbits | Two-body circular orbits, period 2π√(a³/GM) | Standard |
| Navigation | Extended Kalman filter (x, y, ψ) with 2σ consistency check | Monte Carlo statistics |
| GIS | GeoPackage in IAU_2015:49900 (a Mars datum, not WGS84) | Read back with GeoPandas in the tests |

### B2. Accepted simplifications (labelled in the app)
- **Human walking on Mars.** The Minetti metabolic cost and the Tobler speed were measured on Earth without a
  suit. They are scaled by g_Mars / g_Earth and by a suit factor of 1.6 (an assumption). Real suited locomotion
  in 0.38 g is not a linear scaling. The oxygen numbers are therefore indicative, roughly ±30 %.
- **Radiation.** The RAD baseline of 0.64 mSv/day is scaled by atmospheric column, with an assumed exponent.
  Solar particle events are not modelled numerically. They enter only through the DONKI flag, which is a
  heuristic: DONKI is Earth-centric, and only ENLIL impacts that name Mars are counted.
- **Rover energy.** Rolling resistance and slope traction are standard, but the parameters are illustrative.
  Night and thermal loads are simplified.
- **Relay.** The three orbiters are synthetic. Availability numbers show how the method works; they are not
  predictions for MRO, Odyssey or TGO.
- **Hazards.** Thresholds on terrain metrics, partly relative to scene percentiles. This is not a validated
  classifier.
- **Risk matrix.** Likelihood × impact on 1–5 ordinal scales. The product ranks risks; it is not a probability.
- **Integrated score.** Weighted min–max normalisation. The recommendation depends on the weights, which are
  therefore user-adjustable and shown in the explanation.

### B3. The machine-learning model: what its numbers mean

**What is done correctly:**
- the model never sees a cell's own slope or roughness;
- the train, validation and test sets are spatially disjoint blocks, so there is no leakage from
  auto-correlated neighbours;
- the model and the decision threshold are chosen on validation, and the test set is used once;
- the metrics are reported against a prevalence baseline;
- three model families are compared;
- permutation importance shows what the model relies on.

**The limitation:**
- **The labels are produced by explicit rules** on the DEM (slope > 15° or roughness > 2 m), not by human
  annotation or field outcomes. The model therefore learns to predict those rules from the neighbourhood. Its
  test score measures how well it generalises to new map blocks, not whether a real astronaut could walk there.
- On the SYNTHETIC DEM the scores are very high (F1 ≈ 0.97) because the procedural terrain is smooth. This is
  stated in the app, and the numbers will be lower on real terrain.

**How to make it scientifically strong:**
1. Retrain on the real CTX DEM (one click in module 07).
2. Use human-labelled terrain classes, for example NASA-JPL's crowd-labelled AI4Mars rover-image dataset, or
   HiRISE-based traversability maps.
3. Validate against Perseverance drive outcomes, such as slip and actual paths, which are available through the
   traverse module.

### B4. Resolution limits
A 50 m analysis grid, and even the 20 m CTX DEM, cannot see boulders, small scarps or sand ripples, which are
the obstacles that actually stop a walker. A real EVA plan needs HiRISE DEMs (about 1 m) and orbital rock
counts. The app's architecture accepts any GeoTIFF DEM, but this resolution was not tested here.

### B5. What was not verified in this build
- the real NASA downloads, because the servers were unreachable from the build machine;
- SPICE with real kernels;
- YOLO training;
- the Windows `.bat` scripts on a real Windows PC (the Linux equivalents were run).

These limits are also listed in `LIMITATIONS.md` and `TEST_REPORT.md`.
