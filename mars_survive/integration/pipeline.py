"""Integrated Mission Intelligence (module 27).

Runs the full chain for one start/goal pair and returns an explainable
recommendation. The route is NOT chosen by distance alone: each candidate gets
a weighted score of normalised criteria (lower = better):
  time, energy/O2, mean hazard, max slope ratio, communication blind fraction,
  navigation error proxy (path length x drift) - weights are user parameters.
Every number in the explanation is re-computable from the returned tables.
"""
from __future__ import annotations

import time

import numpy as np

import config as C
from mars_survive.communication.link import LinkParams, PRESETS, link_budget, visibility_along_route
from mars_survive.navigation import ekf as nav
from mars_survive.navigation.metrics import summarize
from mars_survive.relay.orbits import DEFAULT_ORBITERS, multi_contact, store_and_forward
from mars_survive.risk.assessment import assess, overall
from mars_survive.routing.eva import turnback
from mars_survive.simulation.engine import SimConfig, run as simulate

from .engine import Engine
from .mission import MissionParams

DEFAULT_WEIGHTS = {"time": 1.0, "energy": 1.0, "hazard": 2.0, "slope": 1.0, "comm": 1.0, "nav": 0.5}


def local_xy(lat, lon, lat0, lon0):
    x = np.radians(np.asarray(lon) - lon0) * C.R_MARS_MEAN * np.cos(np.radians(lat0))
    y = np.radians(np.asarray(lat) - lat0) * C.R_MARS_MEAN
    return x, y


def run(engine: Engine, start, goal, mp: MissionParams, weights: dict | None = None, base=None,
        orbiters=None) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    base = base or start
    steps = []

    def step(name, fn):
        t0 = time.perf_counter()
        try:
            out = fn()
            steps.append({"step": name, "status": "ok", "ms": round(1000 * (time.perf_counter() - t0))})
            return out
        except Exception as e:  # noqa: BLE001 - a failing step is reported, the chain continues
            steps.append({"step": name, "status": f"error: {e.__class__.__name__}: {e}", "ms": None})
            return None

    step("terrain", lambda: engine.T)
    step("hazards", lambda: engine.set_slope_limit(mp.slope_limit_deg))
    routes = step("routes", lambda: engine.plan_four(start, goal, mp)) or {}
    found = {k: r for k, r in routes.items() if r.found}
    res = {}
    for k, r in found.items():
        res[k] = engine.resources(r, mp)
    step("energy", lambda: [res[k]["energy_kwh"] for k in res])
    step("oxygen", lambda: [res[k]["o2_total_l"] for k in res])

    # communication: LOS to base along each route + relay availability
    vis = {}
    for k, r in found.items():
        v = step(f"comm_{k}", lambda r=r: visibility_along_route(engine.g, r.lat, r.lon, base[0], base[1], step=6))
        vis[k] = float(np.mean([x[1] is True for x in v])) if v else 0.0
    orbs = orbiters or DEFAULT_ORBITERS
    cw = step("relay", lambda: multi_contact(orbs, start[0], start[1], hours=24.66))
    lb = step("link_budget", lambda: link_budget(LinkParams(**{**PRESETS["uhf_orbiter"].as_dict(),
                                                              "distance_m": (cw["windows"][0]["min_range_km"] * 1e3
                                                                             if cw and cw["windows"] else 1.0e6)})))

    # score candidates
    table = []
    for k, r in found.items():
        s = r.summary()
        pr = res[k]
        table.append({"strategy": k, "distance_3d_km": s["distance_3d_km"], "duration_h": pr["duration_h"],
                      "energy_kwh": pr["energy_kwh"], "o2_l": pr["o2_total_l"], "hazard_mean": s["hazard_mean"],
                      "max_slope_ratio": s["max_slope_deg"] / mp.slope_limit_deg, "comm_blind_frac": 1 - vis.get(k, 0),
                      "nav_proxy": s["distance_3d_km"]})
    if table:
        crit = {"time": "duration_h", "energy": "energy_kwh", "hazard": "hazard_mean", "slope": "max_slope_ratio",
                "comm": "comm_blind_frac", "nav": "nav_proxy"}
        for c, col in crit.items():
            vals = np.array([row[col] for row in table], float)
            lo, hi = vals.min(), vals.max()
            for row, v in zip(table, vals):
                row[f"n_{c}"] = 0.0 if hi - lo < 1e-12 else float((v - lo) / (hi - lo))
        wsum = sum(weights.values())
        for row in table:
            row["score"] = sum(weights[c] * row[f"n_{c}"] for c in crit) / wsum
        table.sort(key=lambda r: r["score"])
    best = table[0]["strategy"] if table else None

    out = {"steps": steps, "routes": routes, "profiles": res, "table": table, "recommended": best,
           "weights": weights, "relay": cw, "link": lb, "visibility": vis}
    if best is None:
        out["explanation"] = ["no_route"]
        return out
    r = found[best]
    pr = res[best]
    # navigation on recommended route
    x, y = local_xy(r.lat, r.lon, r.lat[0], r.lon[0])
    def _nav():
        speed = mp.rover.speed_ms if mp.scenario == "rover" else mp.astronaut.v_flat_ms
        pose, v, w = nav.path_to_controls(x, y, speed, dt=max(1.0, 5.0 / speed))
        lms = nav.landmarks_along(pose)
        sim = nav.simulate(pose, v, w, lms, nav.NavParams(dt=max(1.0, 5.0 / speed)))
        return summarize(sim)
    nv = step("navigation", _nav)
    out["navigation"] = nv
    # survival / turn-back
    t_out, t_ret = engine.eva_fields(base, mp)
    tb = step("turnback", lambda: turnback(pr["t_s"], r.nodes, t_ret, mp.budget_h, mp.reserve_frac))
    out["turnback"] = tb
    # relay store & forward
    sf = step("store_forward", lambda: store_and_forward(20_000, cw["windows"], [w["rate_bps"] for w in cw["windows"]],
                                                         24.66)) if cw else None
    out["store_forward"] = sf
    # risk
    e_cap_j = mp.rover.battery_wh * 3600 if mp.scenario == "rover" else float("inf")
    e_margin = 1 - (pr["e_j"][-1] / e_cap_j) if mp.scenario == "rover" else 1 - (pr["duration_h"] / mp.budget_h)
    o2_margin = 1 - pr["o2_total_l"] / mp.o2_capacity_l if mp.scenario == "astronaut" else 1.0
    metrics = {"max_slope_frac": r.summary()["max_slope_deg"] / mp.slope_limit_deg, "hazard_mean": r.summary()["hazard_mean"],
               "energy_margin_frac": e_margin, "o2_margin_frac": o2_margin,
               "energy_metric": "battery margin" if mp.scenario == "rover" else "EVA time-budget margin",
               "comm_availability": cw["availability"] if cw else 0.0, "max_comm_gap_h": sf["max_gap_h"] if sf else 24,
               "nav_final_sigma_m": nv["ekf"]["position_sigma_final_m"] if nv else 50, "dose_msv": pr["dose_total_msv"]}
    rk = step("risk", lambda: assess(metrics))
    out["risk"] = rk
    out["risk_overall"] = overall(rk) if rk is not None else None
    out["metrics"] = metrics
    sim = step("simulation", lambda: simulate(pr, t_ret[np.asarray(r.nodes)],
                                              mp.o2_capacity_l if mp.scenario == "astronaut" else 0.0,
                                              e_cap_j, SimConfig("normal"),
                                              time_budget_s=mp.budget_h * 3600 * (1 - mp.reserve_frac)))
    out["simulation"] = sim
    step("report_ready", lambda: True)
    # explanation (keys + values, translated in the UI)
    row = table[0]
    expl = [("expl.best", {"s": best, "score": f"{row['score']:.2f}"})]
    if len(table) > 1:
        second = table[1]
        expl.append(("expl.vs", {"s2": second["strategy"], "d": f"{second['score'] - row['score']:.2f}"}))
    expl.append(("expl.metrics", {"km": f"{row['distance_3d_km']:.2f}", "h": f"{row['duration_h']:.2f}",
                                  "haz": f"{row['hazard_mean']:.2f}", "sl": f"{row['max_slope_ratio'] * mp.slope_limit_deg:.1f}"}))
    if tb:
        expl.append(("expl.turnback_ok" if tb["feasible"] else "expl.turnback_bad", {"m": f"{tb['min_margin_h']:.2f}"}))
    if out["risk_overall"]:
        expl.append(("expl.risk", {"lv": out["risk_overall"]["level"], "f": out["risk_overall"]["top_factor"]}))
    out["explanation"] = expl
    return out
