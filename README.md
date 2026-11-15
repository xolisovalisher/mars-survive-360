# MARS SURVIVE 360

**Interplanetary Survival Guide — Martian Mission Planning & Intelligence Platform**
NASA Space Apps 2026 · Challenge *"Interplanetary Survival Guide: Martian Map"* · Region: **Jezero crater**

A web application (Streamlit + Folium + Plotly, with a FastAPI REST core) that turns a Mars elevation model into
a *survivable EVA plan*: four alternative routes, hazards, oxygen and energy budgets, the last safe turn-back point,
GPS-free navigation accuracy, radio coverage and relay windows, a risk matrix, an emergency simulation and an
exportable mission report — in **18 languages** (switcher in the top-right corner, Arabic right-to-left).

> Decision support for a prototype. Simplified models, clearly labelled — **not** certified astronaut safety guidance.

## What makes it different
* **Survival, not just a map.** Every route answers *"can the crew get back alive?"*: O₂ and energy along the route,
  the **survival envelope** (time out + fastest return) and the **last safe turn-back point**.
* **Real Mars terrain from the first start.** On its first start the app fetches the USGS Mars 2020 CTX DEM of
  Jezero crater (20 m, Calef et al. 2021) by HTTP range reads and builds the 50 m analysis grid (< 1 MB, cached).
  If the USGS server cannot be reached, the labelled demo relief is used and the header says so.
* **Honest data labels.** Every module shows **Real / Synthetic / Simulated / User Supplied**; DEM values are never
  altered and presented as Mars data.
* **Supervised ML in the planner.** A traversability model (logistic regression vs gradient boosting vs PyTorch
  network) is trained and tested on spatially held-out map blocks in module 07; its probability map enters the
  route cost. Labels come from DEM rules — stated openly in the model card.
* **NASA live data where the crew needs it:** DONKI space weather → EVA radiation flag → risk matrix;
  Perseverance's real traverse and raw images → "what the astronaut will see" at each route point.
* **27 working modules on one engine** — the same functions serve the UI, the REST API and the tests.

## Interface — one map-centred workspace
* **Mission Planner** (home): mission setup on the left, the **map in the centre** (routes, hazard zones, science
  points, AI traversability, Perseverance traverse as toggles), route analysis on the right — distance, time,
  elevation gain/loss, O₂, turn-back margin, hazard alerts, terrain profile, the AI recommendation with its reasons,
  mission summary and PDF/GeoJSON export.
* **Data Layers · Route Analysis · Mission Summary**: the 27 modules as connected tools on the same mission state;
  settings, languages and the self-check sit behind the gear icon. Old links (`?page=route`) still work.

## Quick start
**Windows 10/11:** install Python 3.10–3.13 (python.org, tick *Add to PATH*), then double-click
`scripts\setup_windows.bat` once, and `scripts\start_windows.bat` to run (the browser opens automatically).

**Linux / macOS:**
```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh          # or: python main.py ui
```
Optional real data (USGS CTX DEM, ~87 MB): `python scripts/download_data.py` · REST API: `python main.py api` →
http://localhost:8601/docs · Tests: `python scripts/run_tests.py`. Optional ML/GIS extras (PyTorch CPU,
GeoPandas): answer *y* in the setup script or see `requirements-optional.txt`. Put a free NASA key from
https://api.nasa.gov into `.env` (`NASA_API_KEY=`) for DONKI.

### Publish on GitHub (needs your account)
The folder is already a git repository with one commit. Create an empty repository on github.com, then:
```bash
git remote add origin https://github.com/<your-account>/mars-survive-360.git
git push -u origin main
```

### O‘zbekcha qisqacha
1. Windows: `scripts\setup_windows.bat` (bir marta), so‘ng `scripts\start_windows.bat`.
2. Til: yuqori o‘ng burchakdagi 🌐 ro‘yxatdan **O‘zbekcha** ni tanlang — butun ilova shu tilga o‘tadi.
3. Haqiqiy relyef: `python scripts/download_data.py` (yoki 04-modulda yuklab olish). Shu vaqtgacha **SINTETIK DEM** belgisi ko‘rinadi.

## Demo scenario (5 min)
1. Switch language to **O‘zbekcha** (top-right).
2. **05 Route Planning** → click the map to set start/goal (or keep the defaults) → *Compute routes* → four routes
   (shortest, lowest slope, lowest hazard, balanced) with distance, slope, hazard, energy.
3. **02 Mars 2D/3D Map** → **Mars globe** (real NASA imagery, works offline): click Jezero → the globe zooms to the
   crater and the local 3D terrain opens; then 2D layers (NASA Trek basemaps, hillshade, slope, hazards; THEMIS thermal when loaded) and the **3D terrain** tab.
4. **15 Oxygen** / **16 Energy** / **17 Timeline** → budgets, depletion forecast, turn-back point.
5. **07 AI → Traversability model** → *Train and evaluate* → metrics on unseen blocks; back in **05** set the
   *ML weight* and recompute.
6. **13 MEDA → Space weather (DONKI)** → *Example (synthetic)* or live with an api.nasa.gov key → radiation flag.
7. **18 Science Targets → Perseverance** → traverse, distance from your route, raw images of the nearest sol.
8. **27 Integrated Mission Intelligence** → *Run integrated analysis* → scored recommendation with explanation.
9. **19 Simulation** → choose *Oxygen shortage* → see the abort decision.
10. **23 Mission Reports** → *Generate report* → download **PDF** (Uzbek), HTML, CSV, JSON, Excel, and the GIS
    **GeoPackage** in the Mars CRS.

## Documentation
| | |
|---|---|
| [PROJECT_BRIEF — EN](docs/PROJECT_BRIEF_en.md) · [RU](docs/PROJECT_BRIEF_ru.md) · [UZ](docs/PROJECT_BRIEF_uz.md) | The organisers' four questions + assessment of scientific correctness |
| [INSTALLATION_GUIDE](docs/INSTALLATION_GUIDE.md) | Windows / Linux setup, troubleshooting |
| [USER_MANUAL](docs/USER_MANUAL.md) | How to use every screen |
| [MODULES](docs/MODULES.md) | The 27 modules: inputs, outputs, limitations |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Layers, folders, data flow, security |
| [SCIENTIFIC_METHODS](docs/SCIENTIFIC_METHODS.md) | Formulas, constants and their sources |
| [DATA_SOURCES](docs/DATA_SOURCES.md) | NASA/USGS datasets and how they are processed |
| [API_DOCUMENTATION](docs/API_DOCUMENTATION.md) | REST endpoints |
| [TEST_REPORT](docs/TEST_REPORT.md) | Real test numbers |
| [LIMITATIONS](docs/LIMITATIONS.md) | What is simplified or not verified |
| [CHANGELOG](CHANGELOG.md) | Versions |

License: MIT (code). Fonts: see `assets/fonts/LICENSES.md`. NASA/USGS data are public domain; see DATA_SOURCES.
