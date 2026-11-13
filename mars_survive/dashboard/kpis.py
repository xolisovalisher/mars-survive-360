"""Mission Dashboard (module 1): KPI aggregation from the shared mission state."""
from __future__ import annotations


def kpis(state: dict) -> dict:
    """state = st.session_state-like dict. Every KPI states where it comes from; missing -> None."""
    route = state.get("route")
    prof = state.get("profile")
    mp = state.get("mp")
    k = {"distance_km": None, "duration_h": None, "energy_kwh": None, "o2_remaining_pct": None,
         "energy_remaining_pct": None, "nav_sigma_m": None, "comm": None, "hazards": None, "targets": None,
         "alerts": [], "sources": {}}
    if route is not None and route.found:
        k["distance_km"] = float(route.dist3d_m[-1] / 1000)
        k["sources"]["distance_km"] = "routing"
    if prof is not None and mp is not None:
        k["duration_h"] = prof["duration_h"]
        k["energy_kwh"] = prof["energy_kwh"]
        if mp.scenario == "astronaut":
            k["o2_remaining_pct"] = 100 * (1 - prof["o2_total_l"] / mp.o2_capacity_l)
        else:
            k["energy_remaining_pct"] = 100 * (1 - prof["e_j"][-1] / 3600 / mp.rover.battery_wh)
        k["sources"]["resources"] = "oxygen/energy models"
        if k["duration_h"] > mp.budget_h * (1 - mp.reserve_frac):
            k["alerts"].append(("alert.duration", {"h": f"{k['duration_h']:.1f}"}))
        if k["o2_remaining_pct"] is not None and k["o2_remaining_pct"] < 25:
            k["alerts"].append(("alert.o2", {"p": f"{k['o2_remaining_pct']:.0f}"}))
    nav = state.get("nav_summary")
    if nav:
        k["nav_sigma_m"] = nav["ekf"]["position_sigma_final_m"]
    lb = state.get("link_result")
    if lb:
        k["comm"] = lb["status"]
        if lb["status"] == "fail":
            k["alerts"].append(("alert.comm", {"m": f"{lb['margin_db']:.1f}"}))
    hz = state.get("hazard_objects")
    if hz is not None:
        k["hazards"] = len(hz)
    tg = state.get("targets")
    if tg is not None:
        k["targets"] = len(tg)
    tb = state.get("turnback")
    if tb and not tb["feasible"]:
        k["alerts"].append(("alert.turnback", {}))
    return k
