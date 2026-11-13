"""19 Mission Simulation."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.simulation.engine import SCENARIOS, SimConfig, run


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("simulation", tr, ["Simulated"])
    r, prof, cuts = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    with ui.params(tr):
        c = st.columns(4)
        sc = c[0].selectbox(tr("sim.scenario"), SCENARIOS, format_func=lambda s: tr("scn." + s))
        at = c[1].slider(tr("sim.event_at"), 0.05, 0.95, 0.4, 0.05)
        step = c[2].select_slider(tr("sim.step"), [10, 30, 60, 120], 60)
        allsc = c[3].toggle(tr("sim.run_all"), False)
        c = st.columns(4)
        leak = c[0].slider(tr("sim.leak"), 1.0, 6.0, 2.5, 0.5)
        pwr = c[1].slider(tr("sim.power"), 1.0, 4.0, 1.8, 0.1)
        outage = c[2].slider(tr("sim.outage"), 5, 180, 45, 5)
        timeout = c[3].slider(tr("sim.timeout"), 5, 120, 30, 5)
    _, t_ret = ctx.eng.eva_fields(ss.base, mp)
    tr_route = t_ret[np.asarray(r.nodes)]
    o2cap = mp.o2_capacity_l if mp.scenario == "astronaut" else 0.0
    ecap = mp.rover.battery_wh * 3600 if mp.scenario == "rover" else float("inf")
    budget = mp.budget_h * 3600 * (1 - mp.reserve_frac) if mp.scenario == "astronaut" else float("inf")

    def one(s):
        return run(prof, tr_route, o2cap, ecap, SimConfig(s, float(step), at, leak, pwr, float(outage), float(timeout)), budget)

    res = ui.run_safely(tr, one, sc)
    if not res:
        return
    ss.sim_result = res
    col = {"completed": "success", "aborted_safe": "warning", "failed": "error"}[res["outcome"]]
    getattr(st, col)(tr("sim.outcome", o=tr("out." + res["outcome"]), r=tr("lv." + res["risk"]), h=f"{res['duration_h']:.2f}"))
    c = st.columns(4)
    c[0].metric(tr("sim.duration"), f"{res['duration_h']:.2f} h", f"{tr('sim.plan')}: {prof['duration_h']:.2f} h", delta_color="off")
    c[1].metric(tr("sim.o2_used"), f"{res['o2_used_l']:.0f} L" if mp.scenario == "astronaut" else "—")
    c[2].metric(tr("sim.energy_used"), f"{res['energy_used_wh']:.0f} Wh")
    c[3].metric(tr("sim.max_nav"), f"{res['max_nav_sigma_m']:.1f} m")
    tl = res["timeline"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tl["t_h"], y=tl["progress_frac"] * 100, name=tr("sim.progress") + " %"))
    if mp.scenario == "astronaut":
        fig.add_trace(go.Scatter(x=tl["t_h"], y=tl["o2_remaining_l"], name=tr("o2.remaining") + " (L)", yaxis="y2"))
    else:
        fig.add_trace(go.Scatter(x=tl["t_h"], y=tl["energy_remaining_wh"], name=tr("en.soc") + " (Wh)", yaxis="y2"))
    for _, e in res["events"].iterrows():
        fig.add_vline(x=e["t_h"], line_dash="dot", line_color="#ef476f")
    fig.update_layout(height=320, xaxis_title=tr("lbl.mission_time_h"), yaxis_title="%", yaxis2=dict(overlaying="y", side="right"),
                      title=tr("sim.timeline"), margin=dict(t=70),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    ui.plotly(fig, key="sim_tl")
    ev = res["events"].copy()
    if not ev.empty:
        ev["event"] = ev["event"].map(lambda e: tr("ev." + e))
        ui.df_show(ui.tr_cols(ev.round(3), tr))
    else:
        st.success(tr("sim.no_events"))
    if allsc:
        rows = []
        for s in SCENARIOS:
            rr = one(s)
            rows.append({"scenario": tr("scn." + s), "outcome": tr("out." + rr["outcome"]), "risk": tr("lv." + rr["risk"]),
                         "duration_h": round(rr["duration_h"], 2), "events": len(rr["events"])})
        ui.section(tr("sim.all"))
        ui.df_show(ui.tr_cols(pd.DataFrame(rows), tr))
    ui.export_buttons(tr, f"simulation_{sc}", tl, {"outcome": res["outcome"], "events": res["events"].to_dict("records")})
    ui.footer("simulation", tr, "time-stepped replay of the plan; abort if remaining < 1.1 × (return time × rate),\n"
                                "comm-loss > timeout → return, 2σ > limit → 10 min re-localisation, hazard → detour",
              ["SIMULATED events on top of the route resource profile (modules 05, 15, 16)"])
