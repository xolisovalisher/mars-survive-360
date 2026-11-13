"""Assemble the mission report dict from the shared state (used by module 23 and the API)."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

from mars_survive.reporting import export

from . import state

SECTIONS = ["mission", "route", "profile", "hazards", "resources", "navigation", "communication", "science", "risk",
            "recommendations", "provenance", "limitations"]


def build(ctx, sections: list[str]) -> dict:
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    r, prof, cuts = state.active(ctx)
    routes = state.ensure_routes(ctx)
    rep = {"title": f"MARS SURVIVE 360 — {tr('rep.title')}: {mp.name}", "lang": ctx.lang, "rtl": ctx.rtl,
           "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "region": tr("region.jezero"),
           "data_class": tr("rep.dem") + ": " + ctx.g.data_class.value,
           "mission": {tr("lbl.mission_name"): mp.name, tr("lbl.scenario"): tr("scen." + mp.scenario),
                       tr("lbl.duration_h"): mp.budget_h, tr("lbl.reserve_pct"): f"{mp.reserve_frac * 100:.0f}",
                       tr("lbl.slope_limit"): mp.slope_limit_deg, tr("lbl.start"): f"{ss.start[0]:.5f}, {ss.start[1]:.5f}",
                       tr("lbl.goal"): f"{ss.goal[0]:.5f}, {ss.goal[1]:.5f}", tr("route.algorithm"): tr("alg." + mp.algorithm)},
           "sections": []}
    add = rep["sections"].append
    if "route" in sections and r is not None:
        rows = [{"strategy": tr("strat." + k), **{kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.summary().items()
                                                   if kk not in ("strategy", "algorithm", "found")}}
                for k, v in routes.items() if v.found]
        s = r.summary()
        add({"key": "route", "title": tr("rep.s.route"),
             "kv": {tr("route.active"): tr("strat." + ss.strategy), tr("lbl.dist2d"): f"{s['distance_2d_km']:.3f} km",
                    tr("lbl.dist3d"): f"{s['distance_3d_km']:.3f} km", tr("col.max_slope_deg"): f"{s['max_slope_deg']:.1f}°",
                    tr("col.hazard_mean"): f"{s['hazard_mean']:.3f}"},
             "table": rows, "image": export.map_png(ctx.g, ctx.eng.T.hillshade, routes, ctx.eng.H.level, ss.get("targets"))})
    if "profile" in sections and r is not None:
        add({"key": "profile", "title": tr("rep.s.profile"),
             "image": export.chart_png(r.dist3d_m / 1000, {"z (m)": r.elev}, "km", "m"),
             "kv": {tr("lbl.gain"): f"{r.summary()['elev_gain_m']:.0f} m", tr("lbl.loss"): f"{r.summary()['elev_loss_m']:.0f} m"}})
    if "hazards" in sections:
        hz = pd.DataFrame(ctx.eng.H.objects)
        add({"key": "hazards", "title": tr("rep.s.hazards"), "kv": {tr("hz.objects"): len(hz)},
             "table": hz.head(25)[["id", "type", "level", "lat", "lon", "area_km2", "confidence"]].round(4).to_dict("records")
             if not hz.empty else []})
    if "resources" in sections and prof is not None:
        kv = {tr("kpi.duration"): f"{prof['duration_h']:.2f} h", tr("kpi.energy"): f"{prof['energy_kwh']:.2f} kWh",
              tr("tl.dose_usv"): f"{prof['dose_total_msv'] * 1000:.0f}"}
        if mp.scenario == "astronaut":
            kv[tr("o2.mission")] = f"{prof['o2_total_l']:.0f} L / {mp.o2_capacity_l:.0f} L"
        tb = state.turnback(ctx)
        if tb:
            kv[tr("tl.abort_margin")] = f"{tb['min_margin_h']:.2f} h ({tr('ui.yes') if tb['feasible'] else tr('ui.no')})"
        ys = {"O2 (L)": prof["o2_l"]} if mp.scenario == "astronaut" else {"E (Wh)": prof["e_j"] / 3600}
        add({"key": "resources", "title": tr("rep.s.resources"), "kv": kv,
             "image": export.chart_png(prof["t_s"] / 3600, ys, "h", "")})
    if "navigation" in sections and ss.get("nav_summary"):
        n = ss.nav_summary
        add({"key": "navigation", "title": tr("rep.s.navigation"),
             "kv": {"EKF RMSE": f"{n['ekf']['rmse_m']:.2f} m", tr("nav.sigma_final"): f"{n['ekf']['position_sigma_final_m']:.2f} m",
                    tr("nav.final_err_dr"): f"{n['dr']['final_error_m']:.1f} m", tr("nav.drift_dr"): f"{n['dr']['drift_pct']:.2f} %"},
             "notes": [tr("nav.sim_notice")]})
    if "communication" in sections and ss.get("link_result"):
        lb = ss.link_result
        add({"key": "communication", "title": tr("rep.s.communication"),
             "kv": {"Eb/N0": f"{lb['ebn0_db']:.1f} dB", tr("lbl.margin"): f"{lb['margin_db']:.1f} dB",
                    tr("lbl.status"): tr("status." + lb["status"])}})
    if "science" in sections and ss.get("targets"):
        add({"key": "science", "title": tr("rep.s.science"),
             "table": [{"name": t["name"], "lat": t["lat"], "lon": t["lon"], "origin": tr("origin." + t["origin"]),
                        "priority": t["priority"]} for t in ss.targets]})
    if "risk" in sections:
        from frontend.pages.risk import collect
        from mars_survive.risk.assessment import assess, overall
        df = assess(collect(ctx))
        ov = overall(df)
        add({"key": "risk", "title": tr("rep.s.risk"), "kv": {tr("risk.overall"): tr("lv." + ov["level"])},
             "table": df.assign(factor=df.factor.map(lambda f: tr("rf." + f)), level=df.level.map(lambda l: tr("lv." + l)))[
                 ["factor", "value", "likelihood", "impact", "score", "level"]].to_dict("records")})
    if "recommendations" in sections:
        notes = []
        pipe = ss.get("pipeline")
        if pipe and pipe.get("explanation") and pipe["explanation"] != ["no_route"]:
            notes = [tr(k, **kw) for k, kw in pipe["explanation"]]
        elif r is not None:
            notes = [tr("expl.metrics", km=f"{r.summary()['distance_3d_km']:.2f}", h=f"{prof['duration_h']:.2f}",
                        haz=f"{r.summary()['hazard_mean']:.2f}", sl=f"{r.summary()['max_slope_deg']:.1f}")]
        add({"key": "recommendations", "title": tr("rep.s.recommendations"), "notes": notes + [tr("rep.disclaimer")]})
    if "provenance" in sections:
        from mars_survive.provenance.registry import all_datasets
        add({"key": "provenance", "title": tr("rep.s.provenance"),
             "table": [{"name": d["name"], "class": d["data_class"], "provider": d["provider"], "quality": d["quality"]}
                       for d in all_datasets()]})
    if "limitations" in sections:
        add({"key": "limitations", "title": tr("rep.s.limitations"),
             "notes": [tr("lim." + m) for m in ("route", "hazards", "oxygen", "autonav", "relay", "risk")]})
    return rep
