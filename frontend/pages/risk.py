"""20 Risk Assessment."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.communication.link import PRESETS, link_budget
from mars_survive.relay.orbits import DEFAULT_ORBITERS, multi_contact, store_and_forward
from mars_survive.risk.assessment import assess, overall


def collect(ctx) -> dict:
    ss, mp = st.session_state, ctx.mp
    r, prof, _ = state.active(ctx)
    m = {}
    if r is None:
        return m
    s = r.summary()
    m["max_slope_frac"] = s["max_slope_deg"] / mp.slope_limit_deg
    m["hazard_mean"] = s["hazard_mean"]
    if mp.scenario == "rover":
        m["energy_margin_frac"] = 1 - prof["e_j"][-1] / 3600 / mp.rover.battery_wh
        m["energy_metric"] = "battery margin"
    else:
        m["energy_margin_frac"] = 1 - prof["duration_h"] / mp.budget_h
        m["energy_metric"] = "EVA time-budget margin"
        m["o2_margin_frac"] = 1 - prof["o2_total_l"] / mp.o2_capacity_l
    rs = ss.get("relay_summary")
    if not rs:
        cw = multi_contact(DEFAULT_ORBITERS, ss.start[0], ss.start[1])
        sf = store_and_forward(20_000, cw["windows"], [w["rate_bps"] for w in cw["windows"]], 24.66)
        rs = {"availability": cw["availability"], "max_gap_h": sf["max_gap_h"]}
    m["comm_availability"] = rs["availability"]
    m["max_comm_gap_h"] = rs["max_gap_h"]
    if ss.get("nav_summary"):
        m["nav_final_sigma_m"] = ss.nav_summary["ekf"]["position_sigma_final_m"]
    if ss.get("meda_risk"):
        m["env_level"] = ss.meda_risk["level"]
    if ss.get("suit_alerts") is not None:
        m["suit_alerts"] = ss.suit_alerts
    m["dose_msv"] = prof["dose_total_msv"]
    if ss.get("sw_assessment") is not None:
        m["sw_level"] = ss.sw_assessment.level
    return m


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("risk", tr, [ctx.g.data_class, "Simulated"])
    m = collect(ctx)
    if not m:
        st.warning(tr("alert.no_route"))
        return
    missing = [k for k in ("nav_final_sigma_m", "env_level", "suit_alerts") if k not in m]
    if missing:
        st.info(tr("risk.missing", m=", ".join(tr("risk.src." + k) for k in missing)))
    df = assess(m)
    ov = overall(df)
    ss.risk_df, ss.risk_overall = df, ov
    c = st.columns(3)
    c[0].metric(tr("risk.overall"), tr("lv." + ov["level"]))
    c[1].metric(tr("risk.max_score"), f"{ov['max_score']} / 25")
    c[2].metric(tr("risk.top"), tr("rf." + ov["top_factor"]))
    left, right = st.columns([2, 3])
    with left:
        z = np.array([[l * i for l in range(1, 6)] for i in range(1, 6)])
        fig = go.Figure(go.Heatmap(z=z, x=[1, 2, 3, 4, 5], y=[1, 2, 3, 4, 5], showscale=False,
                                   colorscale=[[0, "#1b4332"], [0.2, "#2d6a4f"], [0.36, "#e9c46a"], [0.64, "#f4a261"], [1, "#9d0208"]]))
        jit = np.linspace(-0.25, 0.25, len(df))
        fig.add_trace(go.Scatter(x=df["likelihood"] + jit, y=df["impact"] + jit[::-1], mode="markers+text",
                                 text=[str(i + 1) for i in range(len(df))], textposition="middle center",
                                 textfont=dict(color="#000", size=11),
                                 hovertext=[tr("rf." + f) for f in df["factor"]], hoverinfo="text",
                                 marker=dict(size=20, color="#fff", line=dict(color="#000", width=1)), showlegend=False))
        fig.update_layout(height=420, xaxis_title=tr("risk.likelihood"), yaxis_title=tr("risk.impact"), title=tr("risk.matrix"))
        ui.plotly(fig, key="risk_mx")
    with right:
        show = df.reset_index(drop=True).assign(factor=[f"{i + 1}. {tr('rf.' + f)}" for i, f in enumerate(df["factor"])], level=df["level"].map(lambda l: tr("lv." + l)),
                         mitigation=df["factor"].map(lambda f: tr("mit." + f)),
                         metric=df["mkey"].map(lambda k: tr("rm." + k)),
                         value=[tr("lv." + v) if f == "environment" else v for f, v in zip(df["factor"], df["value"])])
        ui.df_show(ui.tr_cols(show[["factor", "metric", "value", "likelihood", "impact", "score", "level", "mitigation"]], tr), height=420)
    with st.expander(tr("risk.basis")):
        ui.df_show(ui.tr_cols(df.assign(basis=df["factor"].map(lambda f: tr("rb." + f)), factor=df["factor"].map(lambda f: tr("rf." + f)))[["factor", "basis"]], tr))
    ui.export_buttons(tr, "risk_assessment", df, {"metrics": m, "overall": ov})
    ui.footer("risk", tr, "score = likelihood (1-5, from documented metric bands) × impact (1-5, fixed per factor)\n"
                          "levels: ≤4 low, ≤9 medium, ≤16 high, ≥20 critical; overall = max score",
              ["computed metrics of modules 05, 09, 11, 13, 14, 15/16", "ISO 31000-style 5×5 matrix"])
