"""17 Mission Timeline."""
from __future__ import annotations

from datetime import datetime, time, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.relay.orbits import DEFAULT_ORBITERS, multi_contact
from mars_survive.timeline.planner import build

COLORS = {"start": "#1d4ed8", "movement": "#2ec4b6", "observation": "#ffd166", "communication": "#9b5de5",
          "rest": "#8fa1bd", "return": "#e4572e", "emergency": "#ef476f"}


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("timeline", tr, ["Simulated"])
    r, prof, cuts = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    with ui.params(tr):
        c = st.columns(5)
        d = c[0].date_input(tr("spice.date"), datetime(2035, 3, 1).date())
        t0 = c[1].time_input(tr("tl.start_time"), time(8, 0))
        prep = c[2].number_input(tr("tl.prep"), 0, 120, 20)
        every = c[3].number_input(tr("tl.rest_every"), 0.5, 6.0, 2.0, 0.5)
        rest = c[4].number_input(tr("tl.rest_min"), 0, 60, 10)
    start = datetime.combine(d, t0, tzinfo=timezone.utc)
    cw = multi_contact(DEFAULT_ORBITERS, ss.start[0], ss.start[1], hours=24.66)
    df = build(prof, cuts, cw["windows"], prep, every, rest, start)
    df["phase_tr"] = df["phase"].map(lambda p: tr("phase." + p))
    total_h = (df["end_s"].max() - df["start_s"].min()) / 3600
    tb = state.turnback(ctx)
    c = st.columns(4)
    c[0].metric(tr("tl.total"), f"{total_h:.2f} h", tr("kpi.of_budget", b=f"{mp.budget_h:.1f}"), delta_color="off")
    c[1].metric(tr("tl.phases"), len(df))
    c[2].metric(tr("tl.comm_windows"), int((df.phase == "communication").sum()))
    c[3].metric(tr("tl.last_tbp"), f"{prof['t_s'][tb['tbp_idx']] / 3600:.2f} h" if tb and tb["tbp_idx"] is not None else tr("tl.none_needed"))
    fig = px.timeline(df, x_start="start", x_end="end", y="phase_tr", color="phase",
                      color_discrete_map=COLORS, hover_data=["label", "duration_min"])
    fig.update_yaxes(autorange="reversed", title="")
    fig.update_layout(height=360, title=tr("tl.gantt"), showlegend=False)
    ui.plotly(fig, key="tl_gantt")
    th = prof["t_s"] / 3600 + prep / 60
    f2 = go.Figure()
    if mp.scenario == "astronaut":
        f2.add_trace(go.Scatter(x=th, y=100 * (1 - prof["o2_l"] / mp.o2_capacity_l), name=tr("kpi.o2_reserve") + " %"))
    else:
        f2.add_trace(go.Scatter(x=th, y=100 * (1 - prof["e_j"] / 3600 / mp.rover.battery_wh), name=tr("kpi.energy_reserve") + " %"))
    if tb:
        f2.add_trace(go.Scatter(x=th, y=tb["margin_s"] / 3600, name=tr("tl.abort_margin"), yaxis="y2", line=dict(dash="dash")))
    f2.add_trace(go.Scatter(x=th, y=prof["dose_msv"] * 1000, name=tr("tl.dose_usv"), yaxis="y3", line=dict(width=1)))
    f2.update_layout(height=300, xaxis_title=tr("lbl.mission_time_h"), yaxis=dict(title="%"),
                     yaxis2=dict(overlaying="y", side="right", title="h"),
                     yaxis3=dict(overlaying="y", side="right", position=0.97, visible=False), title=tr("tl.resources"))
    ui.plotly(f2, key="tl_res")
    out = df[["phase_tr", "label", "start", "end", "duration_min"]].rename(columns={"phase_tr": "phase"}).copy()
    out["start"] = out["start"].dt.strftime("%H:%M")
    out["end"] = out["end"].dt.strftime("%H:%M")
    ui.df_show(ui.tr_cols(out.round(1), tr), height=260)
    ui.export_buttons(tr, "timeline", df.drop(columns=["phase_tr"]).astype({"start": str, "end": str}))
    ui.footer("timeline", tr, "phases from the route resource profile: movement legs, science dwell, rests inserted every N h,\n"
                              "relay passes from module 11, return = last leg; abort margin from the turn-back analysis",
              ["modules 05, 11, 15/16"])
