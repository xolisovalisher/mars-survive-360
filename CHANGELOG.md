# Changelog

## 1.2.0 — 2026-11-14
* **3-D Mars globe (module 02, first tab):** rotatable/zoomable sphere with real NASA imagery — USGS/NASA Viking colour
  mosaic bundled (public domain, works offline, checked against known albedo features); optional sharper NASA Mars
  Trek Viking MDIM 2.1 texture stitched from WMTS tiles and cached; 30° graticule; Jezero crater, Perseverance and
  Curiosity landing sites (numbered); DEM analysis window. Click Jezero/Perseverance (or choose in the list) → zoom to
  the crater with DEM hillshade + local 3-D terrain with routes below ("planet → crater"). Curiosity: explained that no
  local DEM is loaded.
* 21 new interface strings in 18 languages; module 02 description updated.
* Tests: 9 unit tests (texture georeference, sites, Trek stitching with injected tiles, failure keeps the bundled
  texture, deck layers) + 1 UI test (Jezero → 3-D, Curiosity → explanation).

## 1.1.0 — 2026-11-13
* **Supervised ML (module 07):** traversability classifier — logistic regression, gradient boosting, PyTorch MLP;
  neighbourhood-only features, spatial block split, validation-based selection, test metrics (P/R/F1/ROC-AUC/
  PR-AUC/Brier), confusion matrix, permutation importance, learning curve, model card; probability map used by
  route planning through an ML weight (module 05) and shown as a map layer.
* **NASA DONKI space weather (module 13):** live client, saved-file import, synthetic format example; EVA
  radiation flag feeds the risk matrix (module 20).
* **Perseverance (module 18):** traverse loader (live / file / example), map layer in 02/05/18, route ↔ traverse
  distance (Shapely point-to-polyline), raw images of the nearest sol with camera filter.
* **GIS / 3-D:** GeoPackage + GeoJSON export in IAU_2015:49900 (GeoPandas); deck.gl 3-D scene (PyDeck) with true
  Mars scale; astropy leap seconds for TT − UTC (fixes dates before 1999).
* Reports: CSV now contains table rows; tiny files show size in bytes.
* Tests: regression snapshot and performance budgets as separate suites; new unit and UI tests (ML training by
  button, DONKI example, Perseverance example).
* Docs: PROJECT_BRIEF in English, Russian and Uzbek (four questions + scientific assessment).
* Fixed in the browser review: deck.gl coordinate-system error (scene was blank), truncated model name,
  misleading "deck.gl from the internet" note.

## 1.0.0 — 2026-11-13
* 27 modules on a shared computational core (terrain, hazards, 4-strategy routing with A*/Weighted A*/Dijkstra,
  oxygen/energy, survival envelope and turn-back point, EKF navigation + Monte Carlo, link budget + terrain LOS,
  relay orbits + store-and-forward, Mars24/SPICE, MEDA analysis, suit telemetry, risk matrix, simulation, timeline,
  science targets, AI/CV, integrated recommendation, reports, provenance, ingestion, settings, diagnostics).
* 18-language UI with top-right switcher, URL-persistent language, Arabic RTL; locale build/validation script.
* Data-class labels everywhere; SYNTHETIC DEM badge until a real DEM is loaded.
* FastAPI REST API (health, terrain stats, route, link budget, oxygen, Mars time).
* Reports: PDF (Unicode shaping: Latin, Cyrillic, Arabic, Devanagari, CJK via system font), HTML, CSV, JSON, Excel.
* Windows/Linux setup and start scripts, system check, test runner with honest JSON results.
* UI/UX review in a real browser: compact header, left-aligned navigation, legends no longer overlap titles,
  risk-matrix markers numbered, RTL numbers fixed, empty values shown as "—", real light theme, translated risk
  metrics/basis and footer source, confirmation before deleting targets, DEM backup before overwrite.
