# Architecture

```
Browser ──► Streamlit UI (app.py, frontend/)          REST clients ──► FastAPI (backend/api/main.py)
                    │                                                         │
                    └──────────────► mars_survive/  (computational core, no UI code) ◄─┘
                                       dem · terrain · hazards · routing · oxygen · energy · navigation
                                       communication · relay · spice · meda · telemetry · simulation · risk
                                       timeline · science · ai · integration · reporting · localization
                                       provenance · ingestion · storage (SQLite) · settings · diagnostics
                                       nasa_live (DONKI, Perseverance traverse + raw images) · ai.traversability
                                       reporting.gis (GeoPackage, IAU_2015:49900)
```

## Folders
| Path | Content |
|---|---|
| `app.py` | entry: theme, language switcher (top-right), sidebar navigation, page dispatch, footer status bar |
| `frontend/pages/<id>.py` | 27 modules, each `render(ctx)` (inputs → computation via core → charts/maps/tables → export) |
| `frontend/components/` | `ui.py` (header, badges, footer, exports, tables), `state.py` (session, cached engine), `maps.py` (Folium), `report_builder.py`, `ml_tab.py` (module 07 model), `spaceweather_tab.py` (13), `perseverance_tab.py` (18) |
| `mars_survive/nasa_live/` | safe JSON HTTP (timeouts, size cap, key redaction, cache in `data/cache/`), DONKI, Perseverance; `examples/` = synthetic format examples |
| `models/traversability/` | trained model (`model.joblib`, written by the app itself) + `model_card.json` |
| `frontend/styles/theme.css` | dark mission-control style (light theme override in `app.py`) |
| `mars_survive/` | core packages (see MODULES.md) |
| `mars_survive/localization/src/*.txt` → `locales/*.json` | 18 languages, built and validated by `scripts/build_locales.py` |
| `backend/` | FastAPI app, pydantic schemas, service layer |
| `config.py` | paths, constants with sources, data URLs, `.env` loading |
| `data/` | raw / processed DEM, uploads, SQLite (`mars_survive.sqlite3`), settings |
| `assets/fonts/` | DejaVu, Noto Arabic, Noto Devanagari (PDF Unicode) |
| `scripts/` | setup/start (Windows, Linux), `check_system.py`, `run_tests.py`, `download_data.py`, `build_locales.py` |
| `tests/` | unit, integration (pipeline + API), functional (demo scenario), regression (golden v1 snapshot), performance (time/memory budgets), ui (AppTest: all 27 pages, 5 languages, ML training, DONKI, Perseverance) |

## Data flow
`get_active_grid()` → `Engine(grid)` computes terrain layers and hazards once (cached per DEM file time) →
pages call `engine.plan_four / resources / eva_fields …` → results stored in `st.session_state`
(shared between modules: e.g. the active route feeds oxygen, energy, timeline, comm, risk, reports).
Module 27 runs the whole chain in `integration/pipeline.py`.

## Errors
Each page runs inside `try/except` in `app.py`: one failing module shows a translated error box and logs the trace to
`logs/app.log` (rotating); the rest of the app keeps working. Core functions raise `ModuleError(key, detail)` with a
translation key.

## Security
* Uploads: extension allow-list, size limit (200 MB), magic-byte check, safe file names, stored only under
  `data/uploads/` (no path traversal).
* XML via `defusedxml`; JSON via `json.loads` with size limits; GeoJSON validated before use.
* SQLite: parameterized queries only (`storage.execute`); no string-built SQL.
* User text is HTML-escaped before any `unsafe_allow_html` output and in HTML reports.
* Secrets only from environment / `.env` (git-ignored), never logged; API logs only exception class names.
* Destructive actions: deleting a user target needs a confirmation checkbox; loading a new DEM keeps a backup
  of the previous processed DEM (`.npz.bak`).
* Remote JSON (DONKI, traverse, raw-image feed): HTTPS only, 30 s timeout, 25 MB cap, status checks; image URLs
  are accepted only if they start with `https://`; `api_key` is redacted from logs and cached source fields.
* The ML model is stored with joblib (pickle) — `load()` only reads `models/traversability/model.joblib` written by
  the app; uploaded model files are never unpickled.
