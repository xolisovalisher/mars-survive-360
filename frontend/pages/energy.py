"""16 Energy Management."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.energy.model import RoverParams, battery_curve, power_budget, traction
from mars_survive.routing.planner import STRATEGIES


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("energy", tr, ["Simulated"])
    rp = mp.rover
    with ui.params(tr):
        c = st.columns(4)
        rp.mass_kg = c[0].number_input(tr("en.mass"), 50.0, 5000.0, float(rp.mass_kg))
        rp.speed_ms = c[1].number_input(tr("en.speed"), 0.01, 3.0, float(rp.speed_ms), 0.01, format="%.3f")
        rp.c_rr = c[2].number_input(tr("en.crr"), 0.01, 0.6, float(rp.c_rr), 0.01)
        rp.eta = c[3].number_input(tr("en.eta"), 0.05, 0.95, float(rp.eta), 0.05)
        c = st.columns(4)
        rp.p_idle_w = c[0].number_input(tr("en.idle"), 0.0, 1000.0, float(rp.p_idle_w))
        rp.p_instr_w = c[1].number_input(tr("en.instr"), 0.0, 1000.0, float(rp.p_instr_w))
        rp.motor_power_max_w = c[2].number_input(tr("en.motor"), 10.0, 20000.0, float(rp.motor_power_max_w))
        rp.battery_wh = c[3].number_input(tr("lbl.battery_wh"), 100.0, 100000.0, float(rp.battery_wh), 100.0)
        c = st.columns(3)
        rp.reserve_frac = c[0].slider(tr("lbl.reserve_pct"), 0, 60, int(rp.reserve_frac * 100), 5) / 100
        rp.recharge_w = c[1].number_input(tr("en.recharge"), 0.0, 5000.0, float(rp.recharge_w))
        rp.k_rough = c[2].number_input(tr("en.krough"), 0.0, 2.0, float(rp.k_rough), 0.05)
    routes = state.ensure_routes(ctx)
    rows = {}
    for k in STRATEGIES:
        r = routes[k]
        if not r.found:
            continue
        rough = ctx.eng.rough_along(r)
        seg = traction(np.diff(r.dist2d_m), np.diff(r.elev), 0.5 * (rough[:-1] + rough[1:]), rp)
        bud = power_budget(seg["e_j"].sum(), seg["t_s"].sum(), rp)
        rows[k] = (seg, bud)
    if not rows:
        st.warning(tr("alert.no_route"))
        return
    sel = ss.strategy if ss.strategy in rows else next(iter(rows))
    seg, bud = rows[sel]
    c = st.columns(6)
    c[0].metric(tr("en.energy"), f"{bud['energy_wh']:.0f} Wh")
    c[1].metric(tr("en.rtg_gain"), f"{bud['rtg_gain_wh']:.0f} Wh")
    c[2].metric(tr("en.net"), f"{bud['net_wh']:.0f} Wh")
    c[3].metric(tr("en.end_soc"), f"{bud['end_soc_wh']:.0f} Wh", tr("en.reserve_ok") if bud["reserve_ok"] else tr("en.reserve_bad"),
                delta_color="normal" if bud["reserve_ok"] else "inverse")
    c[4].metric(tr("en.avg_power"), f"{bud['avg_power_w']:.0f} W")
    c[5].metric(tr("en.drive_time"), f"{seg['t_s'].sum() / 3600:.1f} h")
    bc = battery_curve(seg["t_s"], seg["e_j"], rp)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bc["t_h"], y=bc["soc_wh"], name=tr("en.soc"), line=dict(color="#2ec4b6", width=3)))
    fig.add_hline(y=bc["reserve_wh"], line_dash="dash", line_color="#ef476f", annotation_text=tr("en.reserve"))
    fig.update_layout(height=300, xaxis_title=tr("lbl.mission_time_h"), yaxis_title="Wh", title=tr("en.battery", s=tr("strat." + sel)))
    ui.plotly(fig, key="en_bat")
    r = routes[sel]
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=r.dist3d_m[1:] / 1000, y=seg["power_w"], name=tr("en.power"), line=dict(color="#ffd166")))
    f2.add_trace(go.Scatter(x=r.dist3d_m[1:] / 1000, y=seg["theta_deg"], name=tr("en.grade"), yaxis="y2", line=dict(color="#9b5de5", width=1)))
    f2.update_layout(height=260, xaxis_title="km", yaxis_title="W", yaxis2=dict(overlaying="y", side="right", title="°"),
                     title=tr("en.power_profile"))
    ui.plotly(f2, key="en_pow")
    comp = pd.DataFrame([{"strategy": tr("strat." + k), "energy_wh": round(b["energy_wh"], 1), "net_wh": round(b["net_wh"], 1),
                          "drive_h": round(s["t_s"].sum() / 3600, 2), "avg_power_w": round(b["avg_power_w"], 1),
                          "reserve_ok": "✓" if b["reserve_ok"] else "✗"} for k, (s, b) in rows.items()])
    ui.section(tr("en.compare"))
    ui.df_show(ui.tr_cols(comp, tr))
    fig3 = go.Figure(go.Bar(x=comp["strategy"], y=comp["energy_wh"], marker_color="#e4572e"))
    fig3.update_layout(height=240, yaxis_title="Wh")
    ui.plotly(fig3, key="en_cmp")
    ui.export_buttons(tr, "energy_routes", comp, {"params": rp.as_dict(), "budget": bud})
    ui.footer("energy", tr, "F = m·g_M·(C_rr(1+k·rough)·cosθ + sinθ) ≥ 0; v = min(v_max, P_motor·η/F)\n"
                            "P = F·v/η + P_idle + P_instr; E = ΣP·Δt; SOC = E_bat − E + P_RTG·t (capped)",
              ["Perseverance mass 1025 kg, MMRTG ~110 W (NASA mission facts)", "other values: ASSUMPTIONS, user-editable"])
