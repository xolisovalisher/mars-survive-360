# REST API

Start: `python main.py api` (or `uvicorn backend.api.main:app --port 8601`). Interactive docs (OpenAPI/Swagger):
http://localhost:8601/docs. All endpoints call the same core functions as the UI. Validation errors → HTTP 422
`{"error": "invalid_input", "detail": ...}`; unexpected errors → 500 with the exception class only (no internals).

| Method | Path | Body (JSON) | Returns |
|---|---|---|---|
| GET | `/api/health` | – | status, version, active DEM (source, data_class, shape, cell size, bounds) |
| GET | `/api/terrain/stats` | – | mean/std/min/p50/p90/max of elevation, slope, roughness, TRI, local relief, curvature |
| POST | `/api/route` | `start{lat,lon}`, `goal{lat,lon}`, `strategy` (shortest/lowest_slope/lowest_hazard/balanced/all), `algorithm` (astar/weighted_astar/dijkstra), `slope_limit_deg`, `scenario` (astronaut/rover), `include_path` | per strategy: found, 2D/3D distance, slopes, hazard, elevation gain/loss, duration_h, energy_kwh, o2_l, optional path |
| POST | `/api/link-budget` | `preset` (uhf_orbiter/base_vhf_local/x_band_dte) + optional overrides `freq_hz, p_tx_w, g_tx_dbi, g_rx_dbi, distance_m, bitrate_bps, t_sys_k, ebn0_req_db` | FSPL, EIRP, received power, C/N0, Eb/N0, margin, max rate at 3 dB, status |
| POST | `/api/oxygen` | `distance_m`, `elev_gain_m`, `capacity_l`, `reserve_frac`, masses, `suit_factor`, `round_trip` | time, energy, O₂ used, usable, remaining, status (ok/warning/critical), data_class |
| POST | `/api/mars-time` | `utc` (ISO 8601), `lon_east` | Mars24 quantities (Ls, MSD, MST/MTC, LMST, LTST, equation of time, solar declination, subsolar longitude) and northern season |

Example:
```bash
curl -X POST localhost:8601/api/route -H "Content-Type: application/json" \
  -d '{"start":{"lat":18.4447,"lon":77.4508},"goal":{"lat":18.455,"lon":77.405},"strategy":"balanced"}'
```
Coordinates: planetocentric latitude, east longitude. Points outside the active DEM → 422.
