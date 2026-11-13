"""10 Communication System."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.communication.link import (PRESETS, LinkParams, link_budget, margin_vs_distance, radio_horizon_m,
                                             terrain_los, visibility_along_route)


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("comm", tr, [ctx.g.data_class, "Simulated"])
    t1, t2 = st.tabs(["📶 " + tr("comm.budget"), "⛰️ " + tr("comm.los")])
    with t1:
        with ui.params(tr):
            pre = st.selectbox(tr("comm.preset"), list(PRESETS), format_func=lambda k: tr("comm.preset." + k))
            b = PRESETS[pre]
            c = st.columns(4)
            f = c[0].number_input(tr("comm.freq_mhz"), 1.0, 40000.0, b.freq_hz / 1e6)
            ptx = c[1].number_input(tr("comm.ptx_w"), 0.01, 500.0, b.p_tx_w)
            gtx = c[2].number_input(tr("comm.gtx"), -10.0, 80.0, b.g_tx_dbi)
            grx = c[3].number_input(tr("comm.grx"), -10.0, 80.0, b.g_rx_dbi)
            c = st.columns(4)
            dist = c[0].number_input(tr("comm.distance_km"), 0.01, 4.0e8, b.distance_m / 1000, format="%.3f")
            tsys = c[1].number_input(tr("comm.tsys"), 10.0, 3000.0, b.t_sys_k)
            rate = c[2].number_input(tr("comm.rate_bps"), 10.0, 1e8, b.bitrate_bps)
            req = c[3].number_input(tr("comm.ebn0_req"), -2.0, 20.0, b.ebn0_req_db)
            c = st.columns(4)
            ltx = c[0].number_input(tr("comm.ltx"), 0.0, 10.0, b.l_tx_db)
            latm = c[1].number_input(tr("comm.latm"), 0.0, 10.0, b.l_atm_db)
            lmisc = c[2].number_input(tr("comm.lmisc"), 0.0, 20.0, b.l_misc_db)
            limp = c[3].number_input(tr("comm.limpl"), 0.0, 10.0, b.impl_loss_db)
        p = LinkParams(b.name, f * 1e6, ptx, gtx, grx, ltx, latm, lmisc, tsys, rate, req, limp, dist * 1000)
        lb = link_budget(p)
        ss.link_result = lb
        c = st.columns(5)
        c[0].metric("FSPL", f"{lb['fspl_db']:.1f} dB")
        c[1].metric("EIRP", f"{lb['eirp_dbw']:.1f} dBW")
        c[2].metric(tr("comm.prx"), f"{lb['prx_dbm']:.1f} dBm")
        c[3].metric("Eb/N0", f"{lb['ebn0_db']:.1f} dB")
        c[4].metric(tr("lbl.margin"), f"{lb['margin_db']:.1f} dB", tr("status." + lb["status"]), delta_color="off")
        (st.success if lb["status"] == "ok" else st.warning if lb["status"] == "marginal" else st.error)(
            tr("comm.verdict." + lb["status"], r=f"{lb['max_rate_bps_3db'] / 1000:.1f}"))
        tab = pd.DataFrame([{"item": k, "value": f"{v:.3f}" if isinstance(v, float) else str(v)} for k, v in lb.items()])
        c1, c2 = st.columns([2, 3])
        with c1:
            ui.df_show(tab)
        with c2:
            ds, m = margin_vs_distance(p, max(p.distance_m / 100, 10), p.distance_m * 30)
            fig = go.Figure(go.Scatter(x=ds / 1000, y=m, line=dict(color="#2ec4b6")))
            fig.add_hline(y=0, line_color="red", line_dash="dash")
            fig.add_vline(x=p.distance_m / 1000, line_color="#ffd166", line_dash="dot")
            fig.update_layout(height=300, xaxis_type="log", xaxis_title=tr("comm.distance_km"), yaxis_title=tr("lbl.margin") + " (dB)",
                              title=tr("comm.margin_vs_dist"))
            ui.plotly(fig, key="comm_md")
        ui.export_buttons(tr, "link_budget", tab, {"params": p.as_dict(), "result": lb})
    with t2:
        r, _, _ = state.active(ctx)
        with ui.params(tr):
            c = st.columns(3)
            ha = c[0].slider(tr("comm.ant_route"), 0.5, 10.0, 2.0, 0.5)
            hb = c[1].slider(tr("comm.ant_base"), 1.0, 50.0, 10.0, 1.0)
            stp = c[2].slider(tr("comm.sample_every"), 1, 20, 4)
        st.metric(tr("comm.horizon"), f"{radio_horizon_m(ha, hb) / 1000:.2f} km", tr("comm.horizon_note"), delta_color="off")
        if r is None:
            st.warning(tr("alert.no_route"))
        else:
            vis = ui.run_safely(tr, visibility_along_route, ctx.g, r.lat, r.lon, ss.base[0], ss.base[1], ha, hb, stp)
            if vis:
                idx = [v[0] for v in vis]
                ok = np.array([1 if v[1] else (0 if v[1] is False else np.nan) for v in vis], float)
                frac = np.nanmean(ok)
                c = st.columns(3)
                c[0].metric(tr("comm.visible_frac"), f"{frac * 100:.0f} %")
                c[1].metric(tr("comm.blind_points"), int(np.nansum(1 - ok)))
                c[2].metric(tr("comm.max_dist"), f"{max(v[2] for v in vis) / 1000:.2f} km")
                fig = go.Figure(go.Scatter(x=r.dist3d_m[idx] / 1000, y=ok, mode="markers+lines", line_shape="hv",
                                           marker=dict(color=["#2ec4b6" if o == 1 else "#ef476f" for o in ok])))
                fig.update_layout(height=230, yaxis=dict(tickvals=[0, 1], ticktext=[tr("comm.blocked"), tr("comm.visible")]),
                                  xaxis_title=tr("lbl.dist3d") + " (km)", title=tr("comm.los_route"))
                ui.plotly(fig, key="comm_los")
                worst = idx[int(np.nanargmin(ok))] if np.nanmin(ok) == 0 else idx[-1]
                los = terrain_los(ctx.g, r.lat[worst], r.lon[worst], ha, ss.base[0], ss.base[1], hb)
                if "dist" in los:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=los["dist"] / 1000, y=los["terrain"], fill="tozeroy", name=tr("comm.terrain_bulge"),
                                              line=dict(color="#8a5a44")))
                    fig2.add_trace(go.Scatter(x=los["dist"] / 1000, y=los["ray"], name=tr("comm.ray"), line=dict(color="#ffd166")))
                    fig2.update_layout(height=260, xaxis_title="km", yaxis_title="m", title=tr("comm.los_profile"))
                    ui.plotly(fig2, key="comm_prof")
                ui.export_buttons(tr, "los_along_route", pd.DataFrame(vis, columns=["index", "visible", "distance_m"]))
    ui.footer("comm", tr, "FSPL = 20log10(d)+20log10(f)+20log10(4π/c); EIRP = Ptx+Gtx−Ltx; Prx = EIRP−FSPL−Latm−Lmisc+Grx\n"
                          "N0 = 10log10(k·Tsys); C/N0 = Prx−N0; Eb/N0 = C/N0−10log10(Rb); margin = Eb/N0−req−Limpl\n"
                          "LOS: ray vs DEM + Mars curvature bulge d1·d2/(2R); horizon = √(2Rh1)+√(2Rh2)",
              ["ITU-R P.525 (free-space loss)", "CCSDS 401.0-B (RF/modulation)", ctx.g.source])
