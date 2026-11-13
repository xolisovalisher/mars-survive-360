"""14 Suit Telemetry (simulation)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from frontend.components import state, ui
from mars_survive.integration.mission import power_series
from mars_survive.telemetry import suit

CH = [("o2_tank_kpa", "kPa"), ("battery_pct", "%"), ("co2_kpa", "kPa"), ("suit_temp_c", "°C"), ("humidity_pct", "%"),
      ("suit_pressure_kpa", "kPa"), ("o2_lpm", "L/min"), ("water_kg", "kg")]


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("suit", tr, ["Simulated"])
    st.info(tr("suit.notice"))
    r, prof, _ = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    if ctx.mp.scenario != "astronaut":
        st.warning(tr("suit.rover_note"))
    with ui.params(tr):
        c = st.columns(4)
        tank = c[0].number_input(tr("suit.tank_l"), 1.0, 20.0, 7.8, 0.1)
        p0 = c[1].number_input(tr("suit.tank_kpa"), 1000.0, 30000.0, 6200.0, 100.0)
        bat = c[2].number_input(tr("suit.battery_wh"), 100.0, 5000.0, 1100.0, 50.0)
        water = c[3].number_input(tr("suit.water_kg"), 0.5, 10.0, 3.6, 0.1)
        st.markdown("**" + tr("suit.faults") + "**")
        c = st.columns(4)
        leak = c[0].toggle(tr("suit.f.leak"))
        fan = c[1].toggle(tr("suit.f.fan"))
        com = c[2].toggle(tr("suit.f.comm"))
        deg = c[3].slider(tr("suit.f.batt"), 0, 60, 0, 5)
    dur = prof["t_s"][-1]
    faults = {}
    if leak:
        faults.update(o2_leak_start_s=0.4 * dur, o2_leak_lpm=2.0)
    if fan:
        faults["fan_fail_s"] = 0.6 * dur
    if com:
        faults["comm_loss"] = (0.3 * dur, 0.3 * dur + 1800)
    if deg:
        faults["battery_degradation"] = deg / 100
    t, pw = power_series(prof)
    if ctx.mp.scenario != "astronaut":
        pw = pw * 0 + 250.0     # astronaut riding: light activity (ASSUMPTION)
    df = suit.simulate(t, pw, suit.SuitParams(o2_tank_l=tank, o2_tank_kpa=p0, battery_wh=bat, water_kg=water), faults)
    al = suit.alerts(df)
    score, flag = suit.anomaly_scores(df)
    status = suit.safety_status(al)
    ss.suit_alerts = len(al)
    c = st.columns(5)
    c[0].metric(tr("suit.status"), tr("suit.st." + status))
    c[1].metric(tr("suit.o2_end"), f"{df['o2_tank_kpa'].iloc[-1]:.0f} kPa")
    c[2].metric(tr("suit.batt_end"), f"{df['battery_pct'].iloc[-1]:.0f} %")
    c[3].metric(tr("suit.alerts"), len(al))
    c[4].metric(tr("suit.anomalies"), int(flag.sum()))
    fig = make_subplots(rows=4, cols=2, shared_xaxes=True, subplot_titles=[f"{tr('suit.ch.' + k)} ({u})" for k, u in CH],
                        vertical_spacing=0.08)
    for i, (k, u) in enumerate(CH):
        fig.add_trace(go.Scatter(x=df["t_h"], y=df[k], showlegend=False, line=dict(width=1.5)), row=i // 2 + 1, col=i % 2 + 1)
        if k in suit.THRESHOLDS:
            fig.add_hline(y=suit.THRESHOLDS[k][1], line_dash="dot", line_color="#ffb000", row=i // 2 + 1, col=i % 2 + 1)
            fig.add_hline(y=suit.THRESHOLDS[k][2], line_dash="dash", line_color="#ef476f", row=i // 2 + 1, col=i % 2 + 1)
    fig.update_layout(height=720, title=tr("suit.channels"))
    ui.plotly(fig, key="suit_ch")
    c1, c2 = st.columns(2)
    with c1:
        ui.section(tr("suit.alerts"))
        if al.empty:
            st.success(tr("suit.no_alerts"))
        else:
            ui.df_show(ui.tr_cols(al.assign(parameter=al["parameter"].map(lambda p: tr("suit.ch." + p))).round(2), tr))
    with c2:
        f2 = go.Figure(go.Scatter(x=df["t_h"], y=score, line=dict(color="#9b5de5"), name="score"))
        f2.add_trace(go.Scatter(x=df["t_h"][flag], y=score[flag], mode="markers", marker=dict(color="#ef476f"), name=tr("suit.anomalies")))
        f2.update_layout(height=260, title=tr("suit.iforest"), xaxis_title="h")
        ui.plotly(f2, key="suit_if")
    ui.export_buttons(tr, "suit_telemetry", df.round(4))
    ui.footer("suit", tr, "V̇O2 = P_met·60/20 100 L/min; tank p = (n0 − n_used)·R·T/V; P_suit = P_base + k·P_met\n"
                          "water = heat/2.45 MJ/kg; alerts = thresholds; anomalies = Isolation Forest (contamination 2 %)",
              ["metabolic power from the route model (module 15)", "generic EVA suit values — ASSUMPTIONS"])
