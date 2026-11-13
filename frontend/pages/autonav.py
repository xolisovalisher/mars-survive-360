"""08 Autonomous Navigation (EKF)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from mars_survive.navigation import ekf as nav
from mars_survive.navigation.metrics import error_ellipse, errors, summarize


def run_nav(ctx, p: nav.NavParams, spacing: float):
    r, _, _ = state.active(ctx)
    x, y = state.grid_xy(ctx, r.lat, r.lon)
    spd = ctx.mp.rover.speed_ms if ctx.mp.scenario == "rover" else ctx.mp.astronaut.v_flat_ms
    pose, v, w = nav.path_to_controls(x, y, spd, p.dt)
    lms = nav.landmarks_along(pose, spacing_m=spacing) if spacing > 0 else []
    sim = nav.simulate(pose, v, w, lms, p)
    return sim, lms, (x, y)


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("autonav", tr, ["Simulated"])
    st.info(tr("nav.sim_notice"))
    r, _, _ = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    spd = ctx.mp.rover.speed_ms if ctx.mp.scenario == "rover" else ctx.mp.astronaut.v_flat_ms
    with ui.params(tr):
        c1, c2, c3, c4 = st.columns(4)
        odo = c1.slider(tr("nav.odo_noise"), 0.0, 0.10, 0.02, 0.005, format="%.3f")
        slip = c2.slider(tr("nav.slip"), 0.0, 0.30, 0.05, 0.01)
        gb = c3.number_input(tr("nav.gyro_bias"), 0.0, 20.0, 1.0, 0.5)
        vo = c4.toggle(tr("nav.vo"), True)
        c5, c6, c7, c8 = st.columns(4)
        spacing = c5.slider(tr("nav.lm_spacing"), 0, 1000, 150, 25)
        rng = c6.slider(tr("nav.lm_range"), 10, 300, 80, 10)
        rs = c7.slider(tr("nav.range_sigma"), 0.1, 10.0, 1.0, 0.1)
        seed = c8.number_input(tr("nav.seed"), 0, 9999, 1)
    p = nav.NavParams(dt=max(1.0, 5.0 / spd), odo_sigma=odo, slip_bias=slip, gyro_bias_deg_s=gb / 3600,
                      vo_enabled=vo, landmark_range_m=rng, range_sigma_m=rs, seed=int(seed))
    res = ui.run_safely(tr, run_nav, ctx, p, spacing)
    if not res:
        return
    sim, lms, _ = res
    s = summarize(sim)
    ss.nav_summary, ss.nav_key, ss.nav_sim = s, ss.get("routes_key"), sim
    c = st.columns(5)
    c[0].metric(tr("nav.final_err_ekf"), f"{s['ekf']['final_error_m']:.2f} m")
    c[1].metric(tr("nav.final_err_dr"), f"{s['dr']['final_error_m']:.1f} m")
    c[2].metric(tr("nav.sigma_final"), f"± {s['ekf']['position_sigma_final_m']:.2f} m")
    c[3].metric(tr("nav.updates"), s["landmark_updates"])
    c[4].metric(tr("nav.drift_dr"), f"{s['dr']['drift_pct']:.2f} %")
    t, dr, ek = sim["true"], sim["dr"], sim["ekf"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t[:, 0], y=t[:, 1], name=tr("nav.true"), line=dict(color="#ffffff", width=2)))
    fig.add_trace(go.Scatter(x=dr[:, 0], y=dr[:, 1], name=tr("nav.dr"), line=dict(color="#ef476f", dash="dot")))
    fig.add_trace(go.Scatter(x=ek[:, 0], y=ek[:, 1], name="EKF", line=dict(color="#2ec4b6")))
    if lms:
        L = np.array(lms)
        fig.add_trace(go.Scatter(x=L[:, 0], y=L[:, 1], mode="markers", name=tr("nav.landmarks"),
                                 marker=dict(symbol="triangle-up", size=8, color="#ffd166")))
    for i in np.linspace(0, len(ek) - 1, 8).astype(int):
        el = error_ellipse(sim["cov"][i][:2, :2], 2.0) * 10
        fig.add_trace(go.Scatter(x=ek[i, 0] + el[:, 0], y=ek[i, 1] + el[:, 1], mode="lines", showlegend=bool(i == 0),
                                 name=tr("nav.ellipse"), line=dict(color="#9b5de5", width=1)))
    fig.update_layout(height=470, xaxis_title="E (m)", yaxis_title="N (m)", yaxis_scaleanchor="x")
    ui.plotly(fig, key="nav_traj")
    e_dr, h_dr = errors(t, dr)
    e_ek, h_ek = errors(t, ek)
    sig = np.sqrt(np.maximum(sim["cov"][:, 0, 0] + sim["cov"][:, 1, 1], 0))
    dist = np.concatenate([[0], np.cumsum(np.hypot(np.diff(t[:, 0]), np.diff(t[:, 1])))]) / 1000
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dist, y=e_dr, name=tr("nav.dr"), line=dict(color="#ef476f")))
    fig2.add_trace(go.Scatter(x=dist, y=e_ek, name="EKF", line=dict(color="#2ec4b6")))
    fig2.add_trace(go.Scatter(x=dist, y=2 * sig, name="EKF 2σ", line=dict(color="#9b5de5", dash="dash")))
    fig2.update_layout(height=280, xaxis_title="km", yaxis_title=tr("nav.pos_error") + " (m)", yaxis_type="log")
    ui.plotly(fig2, key="nav_err")
    df = pd.DataFrame({"t_s": np.arange(len(t)) * p.dt, "true_x": t[:, 0], "true_y": t[:, 1], "ekf_x": ek[:, 0],
                       "ekf_y": ek[:, 1], "dr_x": dr[:, 0], "dr_y": dr[:, 1], "sigma_m": sig})
    ui.export_buttons(tr, "navigation_ekf", df, s)
    st.caption(tr("nav.ellipse_note"))
    ui.footer("autonav", tr,
              "state [x, y, θ]; predict: x+=v·dt·cosθ, y+=v·dt·sinθ, θ+=ω·dt; P = F P Fᵀ + G Q Gᵀ\n"
              "update (range, bearing to landmark): K = P Hᵀ (H P Hᵀ + R)⁻¹; slip = speed bias; VO fused 50/50",
              ["Thrun, Burgard & Fox, Probabilistic Robotics (2005), ch. 7", "Maimone et al. 2007 (MER visual odometry)"])
