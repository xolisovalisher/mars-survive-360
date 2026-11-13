# User manual

## Screen layout
* **Top bar:** mission name, region, **data badge** (REAL / SYNTHETIC / USER), number of healthy system modules, and
  the **🌐 language selector in the top-right corner** (18 languages; Arabic switches to right-to-left). The choice is
  saved and also kept in the URL (`?lang=uz`), so a bookmarked link opens in the same language.
* **Left sidebar:** the 27 modules grouped as Mission · Geospatial · AI & Navigation · Comms & Space ·
  Crew & Resources · Data & System. The active module is highlighted.
* **Module header:** number, name, data-class badges and a one-line description.
* **Parameters** panel (collapsible) → results (metrics, maps, charts, tables) → export buttons (CSV / Excel / JSON)
  → *Method, sources and limitations* (collapsible) at the bottom.
* **Footer status bar:** system state, data source, last update, computation time, warnings.

## Typical workflow
1. **04 DEM Data Management** — download/load the real Jezero DEM (until then everything is labelled SYNTHETIC).
2. **05 Route Planning** — choose *what a map click sets* (Start / Goal / Stop / Base) and click the map; choose the
   algorithm, slope limit, weights and scenario (astronaut EVA / rover); *Compute routes*. The table compares the four
   strategies; pick the *active strategy* used by all other modules.
3. **06 Hazards / 03 Terrain / 02 Map** — inspect why a route goes where it goes (slope, roughness, crater rims,
   unknown data). Module 02 has the 2D map with NASA Trek basemaps and a 3D terrain view.
4. **15 Oxygen, 16 Energy, 17 Timeline** — budgets, depletion forecast, minimum return reserve, last safe
   turn-back point, Gantt chart.
5. **08/09 Navigation, 10 Communication, 11 Relay** — GPS-free position error, line of sight to the base, relay
   windows and store-and-forward.
6. **13 MEDA, 14 Suit, 20 Risk** — environment check, simulated suit telemetry with fault injection, 5×5 risk matrix
   (open 08, 13 and 14 first for a complete assessment — the page tells you what is missing).
7. **19 Simulation** — replay the plan with an emergency (O₂ leak, power loss, comm loss, terrain, navigation drift).
8. **27 Integrated Mission Intelligence** — runs the whole chain, recommends a route and explains the numbers;
   *Use recommended route* makes it active everywhere.
9. **23 Mission Reports** — choose sections and formats → PDF / HTML / CSV / JSON / Excel in the current language.

## Other modules
* **01 Dashboard** — KPIs of the active plan, alerts, missions (save/load).
* **07 AI / Computer Vision** — first tab: **traversability model** — set the label rule (slope/roughness limits),
  spatial blocks and network epochs → *Train and evaluate* → model comparison, test metrics, confusion matrix,
  feature importance, learning curve, probability map; the model is then available in module 05 (*ML weight*).
  Other tabs: detection on a synthetic test scene or your image (heuristic, labelled untrained; YOLO only with real
  weights), K-Means terrain units, YOLO dataset split/training, route assistant.
* **13 MEDA → Space weather (DONKI)** — source *online* (needs internet; key in `.env`), *saved JSON* or
  *example (synthetic)*; date range, EVA date/time, look-back → EVA radiation flag with reasons, event timeline
  (★ = Mars-relevant), table and CSV/Excel export. The flag raises the radiation likelihood in module 20.
* **18 Science Targets → Perseverance** — load the traverse (online / saved GeoJSON / synthetic example) → cyan
  dashed layer on maps 02, 05, 18; share of your route near the traverse; nearest traverse point and sol for every
  route point and target; *What the astronaut will see*: raw images of that sol (online feed or saved JSON).
* **02 Map → 3D (deck.gl)** — rotatable point-cloud terrain with routes and the traverse, true Mars scale.
* **23 Reports → GIS export** — GeoPackage / GeoJSON with routes, targets, hazards and traverse in IAU_2015:49900.
* **12 SPICE** — Mars time, season and Sun position (Mars24; SPICE when kernels are present).
* **18 Science Targets** — add targets by map click, set status, add as route stop. Deleting a user target needs the
  confirmation checkbox.
* **21 Data Import / 22 Provenance** — validated uploads; registry of every dataset with class, source and hash.
* **24 Multilingual** — coverage of all 18 languages, side-by-side comparison of any text.
* **25 Settings** — language, dark/light theme, units, basemap, zoom, paths, mission defaults.
* **26 Diagnostics** — libraries, modules, folders, resources, last test run (button runs the quick suite), log tail.

## Reading the badges
**REAL** official NASA/USGS data · **SYNTHETIC** generated demo data · **SIMULATED** model output ·
**USER SUPPLIED** your upload. A result is only as real as its weakest input.
