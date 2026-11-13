"""Thin service layer: the API calls the same mars_survive functions as the Streamlit UI (no duplicated science)."""
from __future__ import annotations

import functools
from dataclasses import replace

import numpy as np

from mars_survive.communication.link import PRESETS, link_budget
from mars_survive.dem import get_active_grid
from mars_survive.integration.engine import Engine
from mars_survive.integration.mission import MissionParams
from mars_survive.oxygen.manager import AstronautParams, o2_litres_from_energy, walk_segments
from mars_survive.routing.planner import STRATEGIES
from mars_survive.spice.mars_time import mars_time, season_name
from mars_survive.terrain.analysis import stats


@functools.lru_cache(maxsize=1)
def engine() -> Engine:
    return Engine(get_active_grid())


def grid_info() -> dict:
    g = engine().g
    b = g.bounds() if callable(g.bounds) else g.bounds
    (s, w), (n, e) = b
    return {"source": g.source, "data_class": getattr(g.data_class, "value", str(g.data_class)),
            "shape": list(g.shape), "cell_m": round(float(g.dy), 2),
            "bounds": {"lat_min": float(s), "lat_max": float(n), "lon_min": float(w), "lon_max": float(e)}}


def terrain_stats() -> dict:
    eng = engine()
    T = eng.T
    out = {}
    for name in ("slope", "roughness", "tri", "relief", "curvature"):
        arr = getattr(T, name, None)
        if arr is not None:
            out[name] = {k: (None if v is None else float(v)) for k, v in stats(arr).items()}
    out["elevation"] = {k: (None if v is None else float(v)) for k, v in stats(eng.g.z).items()}
    return {"grid": grid_info(), "layers": out}


def route(req) -> dict:
    eng = engine()
    for p in (req.start, req.goal):
        if eng.cell(p.lat, p.lon) is None:
            raise ValueError(f"point {p.lat},{p.lon} is outside the active DEM")
    mp = MissionParams(scenario=req.scenario, slope_limit_deg=req.slope_limit_deg, algorithm=req.algorithm)
    eng.set_slope_limit(req.slope_limit_deg)
    res = eng.plan_four((req.start.lat, req.start.lon), (req.goal.lat, req.goal.lon), mp)
    wanted = STRATEGIES if req.strategy == "all" else [req.strategy]
    routes = []
    for s in wanted:
        r = res[s]
        item = r.summary()
        if r.found:
            prof = eng.resources(r, mp)
            item["duration_h"] = float(prof["t_s"][-1] / 3600)
            item["energy_kwh"] = float(prof["e_j"][-1] / 3.6e6)
            item["o2_l"] = float(prof["o2_l"][-1])
            if req.include_path:
                item["path"] = [[float(a), float(b)] for a, b in zip(r.lat, r.lon)]
        routes.append(item)
    return {"grid": grid_info(), "routes": routes}


def link(req) -> dict:
    p = PRESETS[req.preset]
    over = {k: v for k, v in req.model_dump().items() if k != "preset" and v is not None}
    p = replace(p, **over)
    out = link_budget(p)
    def _j(v):
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        return float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v
    return {"params": p.as_dict(), "result": {k: _j(v) for k, v in out.items()}}


def oxygen(req) -> dict:
    ap = AstronautParams(body_mass_kg=req.body_mass_kg, suit_mass_kg=req.suit_mass_kg, payload_kg=req.payload_kg,
                         suit_factor=req.suit_factor)
    n = max(1, int(req.distance_m // 10))
    dh = np.full(n, req.distance_m / n)
    dz = np.full(n, req.elev_gain_m / n)
    if req.round_trip:
        dh = np.concatenate([dh, dh]); dz = np.concatenate([dz, -dz[::-1]])
    w = walk_segments(dh, dz, np.zeros_like(dh), ap)
    t, e = w["t_s"], w["e_j"]
    o2 = float(np.sum(o2_litres_from_energy(e)))
    usable = req.capacity_l * (1 - req.reserve_frac)
    status = "ok" if o2 <= 0.8 * usable else "warning" if o2 <= usable else "critical"
    return {"time_h": float(np.sum(t) / 3600), "energy_kj": float(np.sum(e) / 1000), "o2_used_l": o2,
            "usable_l": usable, "remaining_l": req.capacity_l - o2, "status": status, "data_class": "Simulated"}


def mars_clock(req) -> dict:
    mt = mars_time(req.utc, req.lon_east)
    out = {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in mt.items()}
    out["season_north"] = season_name(mt["Ls"]) if "Ls" in mt else None
    return out
