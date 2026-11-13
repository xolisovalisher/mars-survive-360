# Scientific methods

Every simplification is stated. Numbers marked **ASSUMPTION** in `config.py` / the code are modelling choices, not
measurements. Where a value is illustrative it is labelled *Simulated* in the UI.

## 1. Mars geometry and constants (`config.py`)
| Quantity | Value | Source |
|---|---|---|
| Equatorial radius | 3 396 190 m | IAU/IAG 2015 (Mars 2000 ellipsoid) |
| Polar radius | 3 376 200 m | IAU/IAG 2015 |
| Mean radius (used for distances) | 3 389 500 m | NASA Mars Fact Sheet |
| Surface gravity | 3.721 m/s² | NASA Mars Fact Sheet |
| GM | 4.282837×10¹³ m³/s² | NASA Mars Fact Sheet |
| Sidereal day / mean sol | 88 642.663 s / 88 775.244 s | IAU 2015 / Allison & McEwen 2000 |
| Atmospheric scale height | 11.1 km | NASA Mars Fact Sheet |

**Coordinates.** Latitudes are *planetocentric*, longitudes *east-positive* (the convention of the USGS Jezero
products and Mars 2020). Planetographic latitude is shown for reference:
`tan φg = (a²/b²)·tan φc` (≈ +0.20° at Jezero). Landing site: 18.4447° N, 77.4508° E.

**Distances.** Great-circle (haversine) on the mean sphere; error vs. the ellipsoid < 0.3 % over a few km —
negligible against the 50 m grid. Route length is 3-D: `d3 = √(dh² + dz²)` per edge.

## 2. Terrain (module 03)
On the analysis grid (default 50 m, planetocentric lat/lon, true cell sizes `dx = R·cos φ·Δλ`, `dy = R·Δφ`):
* **Slope** `= atan(√(∂z/∂x² + ∂z/∂y²))` with central differences (`numpy.gradient`) on the true cell sizes.
* **Aspect** (downslope direction), **curvature** (Laplacian), **roughness** (RMS of the residual after a Gaussian
  low-pass, σ = 2 px, 5×5 window), **TRI** (Riley 1999), **local relief** (max − min in a 9×9 window),
  **TPI** (z − mean within 10 px), **hillshade** (sun azimuth 315°, altitude 40°).
* NoData cells are filled only temporarily for the derivatives and are masked again afterwards; they are never
  turned into "safe" terrain.

## 3. Hazards (module 06)
Rules per cell (thresholds relative to the scene percentiles, so they adapt to the DEM):
* caution: slope ≥ 0.6 × limit (steep), roughness ≥ p95 (rough);
* high: TRI ≥ p95 and roughness ≥ p90 (rocky), curvature ≥ p97 and relief ≥ min relief (crater edge),
  relief ≥ 3 × p90 (discontinuity);
* no-go: slope ≥ limit; *unknown*: NoData and its 1-cell border.

Hazard index `H = clip(0.55·s/s_lim + 0.25·r/r95 + 0.20·relief/(3·rel90), 0, 1)`, set to 1 for no-go/unknown.
Connected components (≥ N cells) become hazard objects with type, level, area and confidence.

## 4. Routing (module 05)
16-neighbour grid graph (8 king + 8 knight moves; knight moves cut the metric error from 8.2 % to 2.75 %).
Diagonal/knight moves are refused if they would cut a blocked corner. Edge cost = `d3 × factor`, factor ≥ 1:

| Strategy | factor |
|---|---|
| shortest | 1 |
| lowest slope | 1 + 4·w_s·(s/s_lim)² |
| lowest hazard | 1 + 6·w_h·H |
| balanced | 1 + 1.5·w_s·(s/s_lim)² + 2.5·w_h·H + w_e·5·max(grade,0) |

Because factor ≥ 1, the straight-line 3-D distance is an **admissible** heuristic: A* and Dijkstra return the same
optimum (checked in tests); Weighted A* (ε = 1.5) trades optimality (≤ 1.5×) for speed. Impassable: NoData,
slope > limit, no-go and unknown cells.

## 5. Astronaut walking, energy and oxygen (module 15)
* **Speed:** Tobler hiking function `v = v₀·exp(−3.5·(|g + 0.05| − 0.05))` (normalised so that v = v₀ on flat ground; v₀ = 1.0 m/s, ASSUMPTION for a suited crew),
  slowed by `1 + 0.1·roughness` (ASSUMPTION).
* **Metabolic cost of transport:** Minetti et al. (2002) polynomial
  `C(i) = 280.5 i⁵ − 58.7 i⁴ − 76.8 i³ + 51.9 i² + 19.6 i + 2.5` J/(kg·m), scaled by `g_Mars/g_Earth`
  and a suit factor 1.6 (ASSUMPTION), plus basal 100 W. Mass = body + suit + payload.
  *Simplification:* Minetti is measured on Earth without a suit; scaling by gravity is a first-order approximation.
* **Oxygen:** 20.1 kJ per litre O₂ (respiratory equivalent, RQ ≈ 0.82). Usable = capacity × (1 − reserve).
  Tank option: ideal gas `n = pV/RT` → litres at STP.
* **Turn-back point (module 17/27):** two Dijkstra runs on the time graph give the fastest time from the base
  (`t_out`) and back to it (`t_ret`, transpose graph). At route point k, margin = usable − (elapsed_k + t_ret(k));
  the last point with margin ≥ 0 is the **last safe turn-back point**.

## 6. Rover energy (module 16)
Traction force `F = m·g·(Crr·(1 + k·roughness)·cos θ + sin θ)` (Crr = 0.15, k ASSUMPTION), power
`P = F·v/η + P_idle + P_instr`; when `F·v/η` exceeds the motor limit the speed is reduced; battery state integrated over time with RTG/solar
recharge. Default values are illustrative (Perseverance-class mass 1025 kg, 0.042 m/s).

## 7. Navigation without GPS (modules 08–09)
Simulated sensors along the planned route: wheel odometry (scale noise + slip), gyroscope (bias ~1°/h + noise),
visual odometry, range-bearing landmarks. An **Extended Kalman Filter** (state x, y, ψ) fuses them; metrics:
RMSE, p95, final error, 1σ/2σ ellipses, heading RMSE, 2σ consistency. Module 09 repeats this in a Monte Carlo
loop for four sensor configurations. All sensor data are *Simulated*.

## 8. Communication (module 10)
Link budget: `FSPL = 20 log₁₀(4πd/λ)`, `EIRP = P_tx + G_tx − L_tx`, `C/N₀ = P_rx − 10 log₁₀(k·T_sys)`,
`Eb/N₀ = C/N₀ − 10 log₁₀(R)`, margin = Eb/N₀ − required − implementation loss. Presets are illustrative.
Terrain line of sight: the ray between antennas vs. DEM profile + Mars curvature bulge `d₁d₂/(2R)`;
radio horizon `√(2Rh₁) + √(2Rh₂)`.

## 9. Relay orbits (module 11)
Circular two-body orbits (`T = 2π√(a³/GM)`), Mars rotation at the sidereal rate; contact when elevation ≥ mask.
Store-and-forward queue: data generated continuously, drained at the link rate during passes, dropped when the
buffer is full. The three orbiters are **synthetic** (MRO/Odyssey/TGO-like altitudes and inclinations), not ephemerides.

## 10. Mars time and Sun (module 12)
Mars24 algorithm (Allison & McEwen 2000; NASA GISS Mars24): Ls, MSD, MTC, LMST, LTST, equation of time, solar
declination, elevation/azimuth. Validated against the paper's worked example (2000-01-06 00:00 UTC:
M = 21.74558°, Ls = 277.18759°) in the unit tests. TT − UTC comes from astropy's bundled IERS leap-second table
(no network access); a built-in table is the fallback (astropy also corrects dates before 1999). With NAIF kernels (LSK, PCK, SPK) and `spiceypy`, the app also
computes the Sun direction with SPICE and shows the difference.

## 11. Environment, suit, risk, simulation
* **MEDA (13):** column mapping, statistics, robust z-score anomalies (median/MAD on a moving window),
  share of samples outside EVA bands → low/medium/high.
* **Suit (14):** physical consumables (O₂ tank from metabolic rate, battery, cooling water, CO₂, temperature) with
  injected faults; threshold alerts + Isolation Forest anomaly score. *Generic suit model.*
* **Radiation dose:** 0.64 mSv/day at Gale (Hassler et al. 2014), scaled by column pressure
  `(P_Gale/P)^0.2` with `P ∝ exp(−z/H)` (exponent ASSUMPTION). Solar particle events are not modelled.
* **Risk (20):** likelihood 1–5 from documented metric bands × impact 1–5 per factor (5×5 matrix, ISO 31000 style);
  overall = max score.
* **Simulation (19):** time-stepped replay of the resource profile with events (O₂ leak, power loss, comm outage,
  terrain detour, navigation drift); flight rules abort to the base when the return reserve would be violated.

## 12. Integrated recommendation (module 27)
For the four routes: time, energy, hazard, slope, comm availability and navigation error are min–max normalised and
combined with user weights (default hazard 2, navigation 0.5, others 1); lowest score wins. The explanation lists
the numbers behind the choice and the runner-up difference.

## 13. AI / computer vision (module 07)
* **Heuristic CV** (untrained): downscale, background subtraction and thresholds for rocks, Hough circles for craters.
  Labelled *not a trained model*.
* **YOLO**: dataset split / training / inference via `ultralytics` only when installed and weights exist; metrics
  P, R, F1, mAP50, mAP50-95 are computed against supplied labels only.
* **Terrain units:** K-Means on standardised terrain features with silhouette score — unsupervised clusters, not geology.

## 14. Supervised traversability model (module 07 → routing, module 05)
* **Target:** P(cell not traversable on foot). **Labels (weak supervision):** slope > 15° OR roughness > 2 m OR
  NoData — explicit rules on the DEM, user-adjustable; *not* human annotation or field outcomes.
* **Features (13):** neighbourhood only — ring mean/max of slope and roughness (3×3 without the centre), 7×7
  mean/std of slope, 7×7 mean roughness, TRI, local relief, |curvature|, TPI, slope variability, 5×5 elevation
  spread. A unit test checks that changing a cell's own slope/roughness does not change its ring features.
* **Split:** 5×5 spatial blocks; test, validation and training blocks are disjoint (no leakage through
  auto-correlated neighbours); every set contains both classes.
* **Models:** logistic regression (baseline), HistGradientBoosting (class-weighted), PyTorch MLP 64-32
  (ReLU, dropout 0.1, Adam, weighted BCE; scikit-learn MLP fallback). Selection and decision threshold (max F1)
  on validation; the test set is used once.
* **Metrics:** precision, recall, F1, ROC-AUC, PR-AUC (compared with the class prevalence), Brier score,
  confusion matrix, permutation importance (drop in PR-AUC).
* **Use in routing:** hazard in the edge cost `H = (1 − a)·H_rules + a·P_ml`, `a` = ML weight (0…1).
* Result on the SYNTHETIC DEM (seed 42): gradient boosting, test F1 ≈ 0.97, ROC-AUC ≈ 1.00 — high because the
  procedural terrain is smooth; see PROJECT_BRIEF Part B3 for the interpretation.

## 15. Space weather (NASA DONKI, module 13 → risk, module 20)
Events FLR, SEP, CME (with WSA-ENLIL impact lists), GST in a date range. EVA radiation flag:
**high** — a CME arrival at Mars forecast within ±1 day of the EVA (ENLIL entry naming Mars/MAVEN/rovers) or any
SEP event in the look-back window; **medium** — an X-class flare or a CME ≥ 1000 km/s (direction unknown);
**low** — otherwise. In module 20 the radiation likelihood becomes max(dose band, 3 for medium, 5 for high).
A planning heuristic, not a dose forecast.

## 16. Perseverance traverse and raw images (module 18)
Traverse GeoJSON → ordered vertices with sol; driven distance by haversine (jumps > 2 km between features are
not counted). Route ↔ traverse distance: point-to-polyline in local metres on the Mars sphere (Shapely); without
Shapely the nearest vertex. The sol of the nearest vertex selects raw images from the mars.nasa.gov feed
(camera filter). Proximity means "a 1-tonne rover drove here", not "safe for a walking astronaut".

## 17. GIS and 3-D
* GeoPackage / GeoJSON export with GeoPandas in **IAU_2015:49900** (Mars 2015 sphere, planetocentric,
  east-positive). GeoJSON (RFC 7946) cannot store a non-Earth CRS; its coordinates are Mars lon/lat.
* deck.gl scene (PyDeck): local metres on the Mars sphere re-expressed as equivalent degrees on deck.gl's
  sphere around the scene centre, so horizontal and vertical scales are consistent.

## References
Allison M., McEwen M. (2000) Planet. Space Sci. 48, 215–235 · Minetti A. et al. (2002) J. Appl. Physiol. 93,
1039–1046 · Tobler W. (1993) Three presentations on geographical analysis and modeling · Hassler D. et al. (2014)
Science 343, 1244797 · Swan R. M. et al. (2021) AI4Mars: A dataset for terrain-aware autonomous driving on Mars, CVPR Workshops ·
Riley S. et al. (1999) Intermountain J. Sci. 5, 23–27 · Archinal B. et al. (2018) Celest.
Mech. Dyn. Astron. 130:22 (IAU 2015) · NASA Mars Fact Sheet (NSSDCA).
