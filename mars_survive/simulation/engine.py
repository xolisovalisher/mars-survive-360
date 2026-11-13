"""Mission Simulation (module 19): time-stepped execution of a planned route with
scenario events. Deterministic for a given seed. All runs are SIMULATED.

Scenarios: normal, energy_shortage, oxygen_shortage, communication_loss,
terrain_hazard, navigation_drift, emergency_return.
Decision rules (documented, re-computable):
  * abort & return when remaining consumable < (time to return x consumption rate) x 1.1
  * comm loss > comm_timeout_min  -> return (flight rule style)
  * nav uncertainty (2 sigma) > nav_limit_m -> stop and re-localise (adds time)
  * terrain hazard: blocked segment -> detour cost (+detour_frac of remaining path)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SCENARIOS = ["normal", "energy_shortage", "oxygen_shortage", "communication_loss", "terrain_hazard",
             "navigation_drift", "emergency_return"]


@dataclass
class SimConfig:
    scenario: str = "normal"
    step_s: float = 60.0
    event_at_frac: float = 0.4         # when (fraction of plan) the event happens
    leak_factor: float = 2.5           # O2 consumption multiplier after a leak
    power_factor: float = 1.8          # energy multiplier (e.g. heater failure)
    comm_outage_min: float = 45.0
    comm_timeout_min: float = 30.0
    nav_growth_m_per_min: float = 1.5
    nav_limit_m: float = 50.0
    detour_frac: float = 0.25
    seed: int = 0


def run(profile: dict, t_ret_s: np.ndarray, o2_capacity_l: float, energy_capacity_j: float, cfg: SimConfig,
        time_budget_s: float = np.inf) -> dict:
    """profile: from integration.mission.resource_profile; t_ret_s: return time at each route point.
    energy_capacity_j = inf for an astronaut (metabolic energy is not a battery); time_budget_s = usable EVA time."""
    T = profile["t_s"]
    E = profile["e_j"]
    O = profile["o2_l"]
    plan_end = T[-1]
    t_event = cfg.event_at_frac * plan_end
    t = 0.0
    prog = 0.0                 # progress in plan-time seconds
    used_o2 = used_e = 0.0
    nav_sigma = 2.0
    comm_lost_since = None
    events, rows = [], []
    status = "running"
    returning = False
    detour_added = False
    o2_rate_nominal = O[-1] / max(plan_end, 1)
    while status == "running" and t < 3 * plan_end + 3600:
        i = int(np.searchsorted(T, prog, side="right") - 1)
        i = min(max(i, 0), len(T) - 2)
        f_o2 = (O[i + 1] - O[i]) / max(T[i + 1] - T[i], 1e-9)
        f_e = (E[i + 1] - E[i]) / max(T[i + 1] - T[i], 1e-9)
        after = t >= t_event
        if cfg.scenario == "oxygen_shortage" and after:
            f_o2 *= cfg.leak_factor
        if cfg.scenario == "energy_shortage" and after:
            f_e *= cfg.power_factor
        comm_ok = not (cfg.scenario == "communication_loss" and t_event <= t <= t_event + cfg.comm_outage_min * 60)
        if cfg.scenario == "navigation_drift" and after:
            nav_sigma += cfg.nav_growth_m_per_min * cfg.step_s / 60
        else:
            nav_sigma = max(2.0, nav_sigma - 0.5 * cfg.step_s / 60)
        used_o2 += f_o2 * cfg.step_s
        used_e += f_e * cfg.step_s
        t += cfg.step_s
        speed = 1.0
        if nav_sigma > cfg.nav_limit_m:
            events.append({"t_h": t / 3600, "event": "relocalisation_stop", "detail": f"2-sigma {nav_sigma:.0f} m"})
            t += 10 * 60
            nav_sigma = 5.0
            speed = 0.0
        if cfg.scenario == "terrain_hazard" and after and not detour_added:
            extra = cfg.detour_frac * (plan_end - prog)
            events.append({"t_h": t / 3600, "event": "hazard_detour", "detail": f"+{extra / 60:.0f} min"})
            detour_added = True
            plan_end += extra   # the remaining path takes longer
            T = T.copy()
            T[i + 1:] += extra
        if not returning:
            prog += cfg.step_s * speed
        else:
            prog -= cfg.step_s * speed * 1.0   # walking back along the route
        # remaining needs
        idx = int(min(max(np.searchsorted(T, prog), 0), len(t_ret_s) - 1))
        t_back = float(t_ret_s[idx]) if not returning else max(prog, 0)
        need_o2 = t_back * max(f_o2, o2_rate_nominal) * 1.1
        need_e = t_back * f_e * 1.1
        if comm_ok:
            comm_lost_since = None
        elif comm_lost_since is None:
            comm_lost_since = t
            events.append({"t_h": t / 3600, "event": "comm_loss", "detail": "link down"})
        if cfg.scenario == "emergency_return" and after and not returning:
            returning = True
            events.append({"t_h": t / 3600, "event": "emergency_return", "detail": "commanded"})
        if not returning:
            if o2_capacity_l - used_o2 < need_o2 and o2_capacity_l > 0 and O[-1] > 0:
                returning = True
                events.append({"t_h": t / 3600, "event": "abort_o2", "detail": f"remaining {o2_capacity_l - used_o2:.0f} L"})
            elif t + t_back * 1.1 > time_budget_s:
                returning = True
                events.append({"t_h": t / 3600, "event": "abort_time", "detail": f"budget {time_budget_s / 3600:.1f} h"})
            elif energy_capacity_j - used_e < need_e:
                returning = True
                events.append({"t_h": t / 3600, "event": "abort_energy", "detail": f"remaining {(energy_capacity_j - used_e) / 3600:.0f} Wh"})
            elif comm_lost_since is not None and t - comm_lost_since > cfg.comm_timeout_min * 60:
                returning = True
                events.append({"t_h": t / 3600, "event": "abort_comm", "detail": f">{cfg.comm_timeout_min:.0f} min"})
        rows.append({"t_h": t / 3600, "progress_frac": min(prog / plan_end, 1) if plan_end else 1,
                     "o2_remaining_l": o2_capacity_l - used_o2, "energy_remaining_wh": (energy_capacity_j - used_e) / 3600 if np.isfinite(energy_capacity_j) else np.nan,
                     "nav_sigma_m": nav_sigma, "comm_ok": comm_ok, "returning": returning})
        if (o2_capacity_l > 0 and O[-1] > 0 and used_o2 >= o2_capacity_l) or used_e >= energy_capacity_j \
                or t > time_budget_s * 1.5:
            status = "failed"
            events.append({"t_h": t / 3600, "event": "resource_depleted", "detail": "consumable exhausted"})
        elif not returning and prog >= plan_end:
            status = "completed"
        elif returning and prog <= 0:
            status = "aborted_safe"
    df = pd.DataFrame(rows)
    risk = {"completed": "low", "aborted_safe": "medium", "failed": "high", "running": "high"}[status]
    if status == "completed" and len(events) > 0:
        risk = "medium"
    return {"timeline": df, "events": pd.DataFrame(events, columns=["t_h", "event", "detail"]), "outcome": status,
            "risk": risk, "duration_h": t / 3600, "o2_used_l": used_o2, "energy_used_wh": used_e / 3600,
            "max_nav_sigma_m": float(df["nav_sigma_m"].max()) if len(df) else 0.0}
