"""15 Oxygen Management."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.oxygen.manager import OxygenPlan, o2_kg_to_litres_stp, tank_o2_kg


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("oxygen", tr, ["Simulated"])
    with ui.params(tr):
        c = st.columns(4)
        mode = c[0].radio(tr("o2.capacity_from"), ["litres", "tank"], format_func=lambda m: tr("o2.cap." + m))
        if mode == "tank":
            pk = c[1].number_input(tr("suit.tank_kpa"), 500.0, 40000.0, 20000.0, 500.0)
            vol = c[2].number_input(tr("suit.tank_l"), 0.5, 50.0, 6.0, 0.5)
            cap = o2_kg_to_litres_stp(tank_o2_kg(pk, vol))
            c[3].metric(tr("o2.capacity"), f"{cap:.0f} L")
        else:
            cap = c[1].number_input(tr("lbl.o2_capacity_l"), 100.0, 10000.0, float(mp.o2_capacity_l), 50.0)
        mp.o2_capacity_l = float(cap)
        c = st.columns(3)
        mp.reserve_frac = c[0].slider(tr("lbl.reserve_pct"), 0, 50, int(mp.reserve_frac * 100), 5) / 100
        mp.astronaut.body_mass_kg = c[1].number_input(tr("o2.body_mass"), 40.0, 130.0, float(mp.astronaut.body_mass_kg))
        mp.astronaut.suit_mass_kg = c[2].number_input(tr("o2.suit_mass"), 0.0, 150.0, float(mp.astronaut.suit_mass_kg))
        c = st.columns(3)
        mp.astronaut.payload_kg = c[0].number_input(tr("o2.payload"), 0.0, 60.0, float(mp.astronaut.payload_kg))
        mp.astronaut.suit_factor = c[1].number_input(tr("o2.suit_factor"), 1.0, 3.0, float(mp.astronaut.suit_factor), 0.1)
        mp.astronaut.v_flat_ms = c[2].number_input(tr("o2.v_flat"), 0.2, 2.0, float(mp.astronaut.v_flat_ms), 0.1)
    if mp.scenario != "astronaut":
        st.info(tr("o2.rover_note"))
    r, prof, cuts = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    if mp.scenario != "astronaut":
        return
    tb = state.turnback(ctx)
    rate_lph = prof["o2_total_l"] / max(prof["duration_h"], 1e-9)
    ret_need = float(np.max(tb["return_s"])) / 3600 * rate_lph if tb else 0.0
    rep = OxygenPlan(cap, mp.reserve_frac, prof["o2_total_l"], ret_need, prof["duration_h"]).report()
    ss.o2_report = rep
    c = st.columns(6)
    c[0].metric(tr("o2.capacity"), f"{rep['capacity_l']:.0f} L")
    c[1].metric(tr("o2.usable"), f"{rep['usable_l']:.0f} L")
    c[2].metric(tr("o2.mission"), f"{rep['mission_o2_l']:.0f} L")
    c[3].metric(tr("o2.remaining"), f"{rep['remaining_l']:.0f} L", tr("status." + rep["status"]), delta_color="off")
    c[4].metric(tr("o2.rate"), f"{rep['avg_rate_l_per_h']:.1f} L/h", f"{rep['avg_rate_l_per_h'] / 60:.2f} L/min", delta_color="off")
    c[5].metric(tr("o2.endurance"), f"{rep['endurance_h']:.1f} h")
    st.metric(tr("o2.min_return"), f"{rep['min_return_reserve_l']:.0f} L", tr("o2.min_return_note"), delta_color="off")
    (st.success if rep["status"] == "ok" else st.warning if rep["status"] == "warning" else st.error)(tr("o2.verdict." + rep["status"]))
    usable = rep["usable_l"]
    th = prof["t_s"] / 3600
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=th, y=usable - prof["o2_l"], name=tr("o2.remaining"), line=dict(color="#2ec4b6", width=3)))
    if tb:
        need = tb["return_s"] / 3600 * rate_lph
        fig.add_trace(go.Scatter(x=th, y=need, name=tr("o2.need_return"), line=dict(color="#ef476f", dash="dash")))
    fig.add_hline(y=0, line_color="#888")
    for i in cuts[1:-1]:
        fig.add_vline(x=th[i], line_dash="dot", line_color="#ffd166")
    fig.update_layout(height=330, xaxis_title=tr("lbl.mission_time_h"), yaxis_title="L (STP)", title=tr("o2.depletion"))
    ui.plotly(fig, key="o2_curve")
    st.caption(tr("o2.curve_note", r=f"{mp.reserve_frac * 100:.0f}"))
    st.latex(r"\dot V_{O_2}=\frac{P_{met}\cdot 60}{20.1\,\mathrm{kJ/L}\cdot 1000}\;[\mathrm{L/min}],\quad "
             r"C_{Mars}=C_{Minetti}(i)\,\frac{g_M}{g_E}\,f_{suit},\quad m_{O_2}=\frac{pVM}{RT}")
    df = pd.DataFrame({"t_h": th, "o2_used_l": prof["o2_l"], "o2_remaining_l": usable - prof["o2_l"]})
    ui.export_buttons(tr, "oxygen_plan", df, rep)
    ui.footer("oxygen", tr, "C(i) Minetti 2002 × (3.721/9.807) × suit factor × (body+suit+payload) + basal; O2 = E/20.1 kJ/L\n"
                            "min. return reserve = max fastest-return time along the route × average O2 rate",
              ["Minetti et al. 2002, J. Appl. Physiol. 93:1039", "Tobler 1993 (walking speed)", "NASA-STD-3001 (reserve concept)"])
