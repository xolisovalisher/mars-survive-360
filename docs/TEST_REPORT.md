# Test report — v1.1.0

Generated from `docs/test_results.json`, which `scripts/run_tests.py` writes from pytest's JUnit XML. A failed or
errored test is never counted as passed. To re-run on your machine: `python scripts/run_tests.py`.

* Run: 2026-11-13 16:23 UTC · mode **full** · duration 69.7 s · Python 3.13.18 on Linux
* Libraries: streamlit 1.67.0, numpy 2.5.3, pandas 3.0.5, scikit-learn 1.9.1, torch 2.15.0, shapely 2.2.0, geopandas 1.2.0, astropy 8.0.2, pydeck 0.9.3, fastapi 0.162.5
* **Total: 174 tests — 174 passed, 0 failed, 0 errors, 0 skipped**

| Suite | Tests | Passed | Failed | Errors | Skipped |
|---|---|---|---|---|---|
| unit | 79 | 79 | 0 | 0 | 0 |
| integration | 13 | 13 | 0 | 0 | 0 |
| functional | 1 | 1 | 0 | 0 | 0 |
| regression | 8 | 8 | 0 | 0 | 0 |
| performance | 8 | 8 | 0 | 0 | 0 |
| ui | 65 | 65 | 0 | 0 | 0 |

## What the suites cover

**unit** — the core algorithms, data handling and security:
- **Geometry and terrain:** coordinates, haversine, terrain derivatives, hazards.
- **Routing:** A* equals the Dijkstra optimum, no corner-cutting, NoData is never traversed.
- **Resources and navigation:** oxygen, energy, EKF navigation.
- **Communications:** link budget (doubling the distance adds +6.02 dB), terrain line of sight, relay and
  store-and-forward.
- **Mars time:** Mars24 against the Allison & McEwen (2000) worked example; astropy leap seconds against the
  built-in table.
- **Environment, suit, risk:** MEDA, suit telemetry, risk matrix, simulation.
- **Security:**
  - upload validation: extension, size limit, empty file, magic bytes, path traversal, XML entity bomb;
  - SQL injection text is stored literally;
  - the API key is redacted from logs.
- **i18n:** all 18 languages have 100 % coverage and identical placeholders.
- **PDF:** Unicode output in 10 languages.
- **Traversability ML model** (`test_traversability.py`):
  - no leakage of a cell's own slope or roughness into its features;
  - spatially disjoint split;
  - NoData is labelled non-traversable;
  - beats the prevalence baseline and the linear model;
  - metrics agree with the confusion matrix;
  - the PyTorch MLP learns;
  - save/load round trip, and only the app's own model folder is loaded;
  - the probability map is used by routing.
- **NASA live clients** (`test_nasa_live.py`, offline, on format examples):
  - DONKI normalisation, Mars relevance, flag levels;
  - traverse parsing (longitudes 0–360, invalid GeoJSON);
  - raw-image URL safety;
  - the space-weather flag feeds the risk matrix.
- **Geo libraries** (`test_geo_libs.py`):
  - GeoPackage read back in the IAU 49900 Mars CRS, with the route length checked;
  - Shapely point-to-polyline distance;
  - the PyDeck scene.

**integration** — the full mission pipeline (module 27) and the REST API through FastAPI TestClient.

**functional** — the demo scenario: four routes, resources, risk and an Uzbek report in PDF, HTML, CSV, JSON
and XLSX.

**regression** — key numbers must equal the reviewed snapshot `tests/fixtures/golden_v1.json` (Mars time,
geometry, link budget, terrain statistics, hazard counts, four routes with duration and O₂). To regenerate,
review the change first and then run `python -m tests.regression.golden`.

**performance** — time and memory budgets (see below).

**ui** — Streamlit AppTest:
- all 27 pages render with no exception or error box, and each shows computed output;
- 6 key pages × 5 languages;
- language switch and sidebar navigation;
- integrated-analysis button;
- **ML training by button** (metrics shown, model saved);
- the ML weight slider in routing;
- the **DONKI example** gives the flag *High*, and the risk page then renders;
- the **Perseverance example** shows traverse metrics and the nearest point.

## Performance (this build machine: 2 vCPU, Linux; SYNTHETIC DEM 300×330 at 50 m)
| Measurement | Time / size |
|---|---|
| engine build (terrain + hazards, (300, 330)) | 0.07 s |
| 4 routes A* | 0.076 s |
| 4 routes Dijkstra | 0.507 s |
| 4 routes corner-to-corner | 2.30 s |
| terrain layers on (600, 660) (1.5 MB) | 0.24 s |
| ML probability map (300, 330) | 0.14 s |
| EKF over 2686 steps | 0.10 s |
| integrated pipeline (module 27) | 0.61 s |
| terrain layer memory | 3.8 MB |

## Traversability model on the SYNTHETIC DEM (trained 2026-11-13 16:19 UTC)
Split: spatial blocks 5x5: 5 test, 5 val, rest train (seed 42). Rows: train 58514, validation 19615, test 19495.
Share of non-traversable cells in the test blocks: 0.114.

| Model | F1 (val) | F1 (test) | Precision | Recall | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|
| LogisticRegression | 0.863 | 0.867 | 0.806 | 0.938 | 0.992 | 0.924 |
| HistGradientBoosting | 0.958 | 0.973 | 0.972 | 0.973 | 1.000 | 0.997 |
| PyTorch MLP 64-32 | 0.921 | 0.941 | 0.920 | 0.963 | 0.999 | 0.989 |

Selected on validation: **HistGradientBoosting**.

These scores are high because the synthetic terrain is smooth, and the labels come from rules. See
PROJECT_BRIEF part B3 before quoting them.

## Manual browser review (Chrome 1440×900)
- **v1.0.0:** all 27 modules were checked in EN, UZ, RU, AR and HI and in the light theme.
- **v1.1.0, new tabs** (ML model, DONKI, Perseverance, deck.gl 3D, GIS export): opened and used in the browser.
- **Found and fixed in v1.1.0:**
  - the deck.gl scene was blank (an invalid coordinate system in deck.gl 9);
  - the selected model name was truncated;
  - a radio-option mix-up in the review script;
  - the CSV report omitted tables;
  - the translations stated a wrong "deck.gl from the internet".

## Not tested here (environment limits)
- **Real NASA/USGS downloads** (DEM, DONKI, traverse, raw images): the build sandbox cannot reach those
  servers. The code paths are tested with local files and format examples.
- **SPICE with real NAIF kernels:** not tested. The Mars24 and astropy paths are tested.
- **YOLO training:** `ultralytics` is not installed.
- **Windows `.bat` scripts:** the build machine runs Linux. The Linux equivalents were executed.
- **CJK glyphs in PDF on Linux:** they depend on an installed Noto CJK font.
