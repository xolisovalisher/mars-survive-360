# Modules (27)

Each module = user inputs → computation → displayed result + export. Data-class badges (Real / Synthetic / Simulated / User Supplied) are shown in every module header. Method / sources / limitations are also shown at the bottom of each page.

New in 1.2.0: 3-D Mars globe with NASA imagery and planet → crater navigation (02). New in 1.1.0: supervised traversability model (07, used by 05), NASA DONKI space weather (13 → 20), Perseverance traverse and raw images (18, layer in 02 and 05), deck.gl 3-D view (02), GIS GeoPackage in the Mars CRS (23).


## Mission

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 1 | 🛰️ Mission Dashboard | Create and select missions and see the computed status of the active plan. | KPIs are only as good as the models behind them; synthetic or simulated inputs are labelled. |
| 17 | 🕒 Mission Timeline | Mission phases, Gantt chart and resources over time. | Timing follows the model; operational constraints are not included. |
| 19 | 🎛️ Mission Simulation | Step-by-step replay of the plan under normal and emergency scenarios. | Events and decision rules are simplified flight-rule examples. |
| 20 | 🧯 Risk Assessment | Likelihood × impact matrix computed from the platform's results. | Scores depend on documented thresholds and assumptions; they are not safety certification. |
| 23 | 📄 Mission Reports | Mission report in PDF, HTML, CSV, JSON and Excel. | Reports repeat model results and their limitations; they are not mission approval documents. |
| 27 | 🧠 Integrated Mission Intelligence | Runs all modules for one start/goal pair and explains the recommended route. | The recommendation is decision support for a prototype, not real astronaut safety guidance. |

## Geospatial

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 2 | 🗺️ Mars 2D/3D Map | Rotatable 3D Mars globe with real NASA imagery and landing sites (click Jezero → local 3D terrain), interactive 2D map with NASA Mars Trek base maps and scientific layers, and 3D terrain from real elevations. | Base maps are low-resolution global mosaics; the browser's scale tools assume Earth and are not used. |
| 3 | ⛰️ Terrain Intelligence | DEM derivatives: slope, aspect, curvature, roughness, relief, variability and complexity, with profiles and quality checks. | A 50 m grid cannot show boulders or small scarps; real local slopes are steeper. |
| 4 | 🗂️ DEM Data Management | Load, inspect and validate the Jezero DEM (USGS CTX 20 m) or your own GeoTIFF. | Only the analysis window is resampled; vertical accuracy depends on the source DEM. |
| 5 | 🧭 Route Planning | Four route strategies computed with A*, Weighted A* or Dijkstra on a 16-neighbour terrain graph. | Routes are optimal only for the chosen cost model and grid; they are not certified traverse plans. |
| 6 | ⚠️ Hazard Detection | Rule-based detection of steep, rough, rocky, crater-edge, discontinuous and unknown terrain. | Thresholds are planning assumptions; rocks smaller than a cell are invisible to this method. |

## AI & Navigation

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 7 | 🤖 AI / Computer Vision | Supervised terrain-traversability model (trained and tested here), computer vision on surface images, unsupervised terrain units and an explanation assistant. | The heuristic detector is not a trained model; YOLO results exist only with real trained weights. |
| 8 | 🚙 Autonomous Navigation | GPS-free localisation: wheel odometry, gyroscope, visual odometry and landmarks fused by an EKF. | Sensor data are simulated; real wheel slip and terrain effects can be larger. |
| 9 | 🎯 Navigation Intelligence | Accuracy and uncertainty of navigation configurations compared by Monte Carlo. | Monte Carlo statistics describe the simulation model, not a real rover. |

## Comms & Space

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 10 | 📡 Communication System | Radio link budget and terrain line-of-sight between the crew and the base. | Preset link values are illustrative; multipath, antenna patterns and dust storms are simplified. |
| 11 | 🛰 Relay & Network | Orbiter contact windows and store-and-forward data flow. | Orbits are synthetic two-body circles, not NASA ephemerides. |
| 12 | ☀️ SPICE & Orbital Geometry | Mars time, season and Sun position (Mars24), with NASA SPICE when kernels are present. | Without kernels the analytic Mars24 algorithm is used (accuracy ~0.01° in Ls). |

## Crew & Resources

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 13 | 🌡️ MEDA Environment | Import and analyse MEDA-style weather data: statistics, anomalies and EVA environment level. | The sample dataset is synthetic; EVA bands are planning assumptions. |
| 14 | 🧑‍🚀 Suit Telemetry | Physics-based simulation of suit consumables with alerts and anomaly detection. | Generic suit model; not connected to any real NASA suit. |
| 15 | 🫁 Oxygen Management | Oxygen budget of the planned EVA, depletion forecast and minimum return reserve. | Earth physiology scaled to Mars; real suited metabolic costs vary widely. |
| 16 | 🔋 Energy Management | Rover traction energy, power budget and battery state along each route. | Rover parameters are illustrative; thermal and night-time loads are simplified. |
| 18 | 🔬 Science Targets | Catalog of science targets, linked to the route. | Approximate coordinates must be verified in NASA Mars Trek. |

## Data & System

| # | Module | What the user does → what is computed | Limitation |
|---|---|---|---|
| 21 | 📥 Data Ingestion | Safe upload and validation of GeoTIFF, XML/PDS4, CSV, JSON/GeoJSON and images. | Validation checks format and structure, not scientific correctness. |
| 22 | 🧾 Data Quality & Provenance | Origin, class and quality of every dataset in use. | Class labels are only as accurate as the information given at import. |
| 24 | 🌐 Multilingual System | Central translation service with 18 languages, fallback and right-to-left support. | Translations were prepared with AI assistance and should be reviewed by native speakers. |
| 25 | ⚙️ Settings | Language, theme, units, map and paths. | Some changes take effect after the next calculation. |
| 26 | 🩺 System Diagnostics | Libraries, modules, data, resources, tests and logs. | Checks cover this computer only. |
