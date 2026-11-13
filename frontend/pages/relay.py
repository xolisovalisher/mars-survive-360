"""11 Relay & Network Intelligence."""
from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from mars_survive.relay.orbits import DEFAULT_ORBITERS, Orbiter, contact_windows, merge_windows, store_and_forward


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("relay", tr, ["Simulated"])
    st.info(tr("relay.notice"))
    with ui.params(tr):
        df0 = pd.DataFrame([asdict(o) for o in DEFAULT_ORBITERS]) if "relay_df" not in ss else ss.relay_df
        ed = st.data_editor(df0, num_rows="dynamic", width="stretch", key="relay_editor",
                            column_config={"name": st.column_config.TextColumn(tr("orb.name"), max_chars=60),
                                           "altitude_km": st.column_config.NumberColumn(tr("orb.altitude_km"), min_value=150, max_value=20000),
                                           "inclination_deg": st.column_config.NumberColumn(tr("orb.inclination_deg"), min_value=0, max_value=180),
                                           "raan_deg": st.column_config.NumberColumn(tr("orb.raan_deg"), min_value=0, max_value=360),
                                           "phase_deg": st.column_config.NumberColumn(tr("orb.phase_deg"), min_value=0, max_value=360),
                                           "data_rate_bps": st.column_config.NumberColumn(tr("orb.data_rate_bps"), min_value=1),
                                           "min_elev_deg": st.column_config.NumberColumn(tr("orb.min_elev_deg"), min_value=0, max_value=60)})
        c = st.columns(4)
        hours = c[0].slider(tr("relay.hours"), 6.0, 74.0, 24.66, 0.5)
        gen = c[1].number_input(tr("relay.gen_kbps"), 0.1, 2000.0, 20.0)
        buf = c[2].number_input(tr("relay.buffer_mb"), 10.0, 100000.0, 2000.0)
        out_on = c[3].toggle(tr("relay.outage"), False)
        if out_on:
            o1, o2 = st.slider(tr("relay.outage_window"), 0.0, float(hours), (4.0, 10.0), 0.5)
    orbs = []
    for _, row in ed.dropna(subset=["altitude_km", "inclination_deg"]).iterrows():
        try:
            orbs.append(Orbiter(str(row["name"]), float(row["altitude_km"]), float(row["inclination_deg"]), float(row["raan_deg"]),
                                float(row["phase_deg"]), float(row["data_rate_bps"]), float(row["min_elev_deg"])))
        except (TypeError, ValueError):
            pass
    if not orbs:
        st.error(tr("relay.no_orbiters"))
        return
    lat, lon = ss.start
    res, allw = [], []
    fig = go.Figure()
    for o in orbs:
        cw = contact_windows(o, lat, lon, hours)
        for w in cw["windows"]:
            w["orbiter"], w["rate_bps"] = o.name, o.data_rate_bps
        allw += cw["windows"]
        res.append({"orbiter": o.name, "period_min": cw["period_min"], "passes": len(cw["windows"]),
                    "availability_pct": 100 * cw["availability"], "volume_mb": sum(w["volume_mb"] for w in cw["windows"])})
        fig.add_trace(go.Scatter(x=cw["t_s"] / 3600, y=cw["elev_deg"], name=o.name, mode="lines"))
    fig.add_hline(y=10, line_dash="dash", line_color="#ffd166")
    fig.update_layout(height=300, xaxis_title="h", yaxis_title=tr("relay.elev"), yaxis_range=[-5, 90], title=tr("relay.elev_title"))
    merged = merge_windows([allw])
    avail = sum(e - s for s, e in merged) / (hours * 3600)
    sf = store_and_forward(gen * 1000, allw, [w["rate_bps"] for w in allw], hours, buf, outage=(o1 * 3600, o2 * 3600) if out_on else None)
    c = st.columns(5)
    c[0].metric(tr("relay.passes"), len(allw))
    c[1].metric(tr("relay.availability"), f"{avail * 100:.1f} %")
    c[2].metric(tr("relay.max_gap"), f"{sf['max_gap_h']:.1f} h")
    c[3].metric(tr("relay.max_queue"), f"{sf['max_queue_mb']:.0f} MB")
    c[4].metric(tr("relay.dropped"), f"{sf['dropped_mb']:.0f} MB")
    ui.plotly(fig, key="relay_elev")
    c1, c2 = st.columns(2)
    with c1:
        ui.df_show(ui.tr_cols(pd.DataFrame(res).round(2), tr))
        wdf = pd.DataFrame(allw)
        if not wdf.empty:
            wdf = wdf.assign(start_h=wdf.start_s / 3600, end_h=wdf.end_s / 3600, duration_min=wdf.duration_s / 60)[
                ["orbiter", "start_h", "end_h", "duration_min", "max_elev_deg", "min_range_km", "volume_mb"]].round(2)
            ui.df_show(ui.tr_cols(wdf.sort_values("start_h"), tr), height=230)
    with c2:
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=sf["t_h"], y=sf["queue_mb"], name=tr("relay.queue"), fill="tozeroy", line=dict(color="#e4572e")))
        f2.add_trace(go.Scatter(x=sf["t_h"], y=sf["sent_mb"], name=tr("relay.sent"), line=dict(color="#2ec4b6")))
        f2.update_layout(height=300, xaxis_title="h", yaxis_title="MB", title=tr("relay.sf_title"))
        ui.plotly(f2, key="relay_sf")
    # topology
    nodes = [tr("relay.node.surface"), tr("relay.node.base")] + [o.name for o in orbs] + [tr("relay.node.earth")]
    n = len(nodes)
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xs, ys = np.cos(ang), np.sin(ang)
    f3 = go.Figure()
    edges = [(0, 1)] + [(0, 2 + i) for i in range(len(orbs))] + [(2 + i, n - 1) for i in range(len(orbs))] + [(1, n - 1)]
    for a, b in edges:
        f3.add_trace(go.Scatter(x=[xs[a], xs[b]], y=[ys[a], ys[b]], mode="lines", line=dict(color="#4a5875"), showlegend=False))
    f3.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=nodes, textposition="top center", showlegend=False,
                            marker=dict(size=18, color=["#2ec4b6", "#1d4ed8"] + ["#9b5de5"] * len(orbs) + ["#ffd166"])))
    f3.update_layout(height=320, title=tr("relay.topology"), xaxis=dict(visible=False), yaxis=dict(visible=False))
    ui.plotly(f3, key="relay_topo")
    ss.relay_summary = {"availability": avail, "max_gap_h": sf["max_gap_h"], "windows": allw}
    ui.export_buttons(tr, "relay_windows", pd.DataFrame(allw), {"orbiters": [asdict(o) for o in orbs], "summary": res})
    ui.footer("relay", tr, "two-body circular orbit: n = √(GM/a³); Mars-fixed frame via rotation 2π t / 88 642.663 s\n"
                           "elevation = asin((r_sat − r_site)·û / |r_sat − r_site|); window = elevation ≥ min_elev\n"
                           "store-and-forward queue: q(t+Δt) = q + gen·Δt − min(q, Σ rate·Δt in window)",
              ["SIMULATED orbits (MRO/Odyssey/TGO-like altitudes & inclinations, NOT ephemerides)", "GM_Mars = 4.282837e13 m³/s²"])
