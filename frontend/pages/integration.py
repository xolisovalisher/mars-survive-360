"""27 Integrated Mission Intelligence."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.integration import pipeline


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("integration", tr, [ctx.g.data_class, "Simulated"])
    st.markdown(tr("int.chain"))
    with ui.params(tr):
        c = st.columns(6)
        w = {k: c[i].slider(tr("int.w." + k), 0.0, 5.0, float(pipeline.DEFAULT_WEIGHTS[k]), 0.5)
             for i, k in enumerate(pipeline.DEFAULT_WEIGHTS)}
        st.caption(tr("route.points", s=f"{ss.start[0]:.4f}, {ss.start[1]:.4f}", g=f"{ss.goal[0]:.4f}, {ss.goal[1]:.4f}", n=0))
    key = (ss.start, ss.goal, tuple(w.items()), mp.slope_limit_deg, mp.scenario, mp.budget_h, mp.o2_capacity_l)
    if st.button("🧠 " + tr("btn.run_pipeline"), type="primary") or ss.get("pipeline_key") != key:
        out = ui.run_safely(tr, pipeline.run, ctx.eng, ss.start, ss.goal, mp, w, ss.base)
        if out:
            ss.pipeline, ss.pipeline_key = out, key
            if out.get("navigation"):
                ss.nav_summary = out["navigation"]
            if out.get("link"):
                ss.link_result = out["link"]
    out = ss.get("pipeline")
    if not out:
        return
    steps = pd.DataFrame(out["steps"])
    ok = (steps["status"] == "ok").sum()
    c = st.columns(4)
    c[0].metric(tr("int.steps_ok"), f"{ok}/{len(steps)}")
    c[1].metric(tr("int.recommended"), tr("strat." + out["recommended"]) if out["recommended"] else "—")
    c[2].metric(tr("risk.overall"), tr("lv." + out["risk_overall"]["level"]) if out.get("risk_overall") else "—")
    c[3].metric(tr("int.sim"), tr("out." + out["simulation"]["outcome"]) if out.get("simulation") else "—")
    if out["recommended"] is None:
        st.error(tr("route.none_found"))
        return
    ui.section("🧾 " + tr("int.explanation"))
    for k, kw in out["explanation"]:
        if "s" in kw:
            kw = {**kw, "s": tr("strat." + kw["s"])}
        if "s2" in kw:
            kw = {**kw, "s2": tr("strat." + kw["s2"])}
        if "lv" in kw:
            kw = {**kw, "lv": tr("lv." + kw["lv"]), "f": tr("rf." + kw["f"])}
        st.markdown("• " + tr(k, **kw))
    st.caption(tr("rep.disclaimer"))
    left, right = st.columns([3, 2])
    with left:
        maps.mission_map(ctx, routes=out["routes"], active=out["recommended"], height=430, key="int_map")
    with right:
        tb = pd.DataFrame(out["table"])
        fig = go.Figure()
        for crit in pipeline.DEFAULT_WEIGHTS:
            fig.add_trace(go.Bar(x=[tr("strat." + s) for s in tb["strategy"]], y=tb[f"n_{crit}"] * w[crit] / sum(w.values()),
                                 name=tr("int.w." + crit)))
        fig.update_layout(barmode="stack", height=430, title=tr("int.score_breakdown"), yaxis_title=tr("int.score"))
        ui.plotly(fig, key="int_score")
    show = tb[["strategy", "distance_3d_km", "duration_h", "energy_kwh", "o2_l", "hazard_mean", "max_slope_ratio",
               "comm_blind_frac", "score"]].copy()
    show["strategy"] = show["strategy"].map(lambda s: tr("strat." + s))
    ui.df_show(ui.tr_cols(show.round(3), tr))
    with st.expander(tr("int.steps")):
        ui.df_show(steps)
    if out.get("risk") is not None:
        ui.df_show(ui.tr_cols(out["risk"].assign(factor=out["risk"].factor.map(lambda f: tr("rf." + f)),
                                                 level=out["risk"].level.map(lambda l: tr("lv." + l)))[
            ["factor", "value", "likelihood", "impact", "score", "level"]], tr))
    if st.button("✅ " + tr("btn.adopt_route")):
        ss.strategy = out["recommended"]
        st.success(tr("int.adopted"))
    ui.export_buttons(tr, "integrated_decision", tb, {"recommended": out["recommended"], "weights": out["weights"],
                                                       "table": out["table"], "steps": out["steps"],
                                                       "explanation": [[k, kw] for k, kw in out["explanation"]]})
    ui.footer("integration", tr, "terrain → hazards → 4 routes → energy/O2 → LOS + relay + link → EKF → turn-back → risk → simulation\n"
                                 "score = Σ w_c · normalised_c / Σ w  (min-max per criterion over candidate routes; lower is better)",
              ["all platform modules", ctx.g.source])
