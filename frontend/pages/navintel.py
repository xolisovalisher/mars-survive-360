"""09 Navigation Intelligence."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import state, ui
from frontend.pages.autonav import run_nav
from mars_survive.navigation import ekf as nav
from mars_survive.navigation.metrics import errors, summarize, trajectory_deviation


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("navintel", tr, ["Simulated"])
    r, _, _ = state.active(ctx)
    if r is None:
        st.warning(tr("alert.no_route"))
        return
    spd = ctx.mp.rover.speed_ms if ctx.mp.scenario == "rover" else ctx.mp.astronaut.v_flat_ms
    with ui.params(tr):
        c1, c2, c3 = st.columns(3)
        n_mc = c1.slider(tr("ni.mc_runs"), 3, 50, 8, 1)
        slip = c2.slider(tr("nav.slip"), 0.0, 0.3, 0.05, 0.01)
        spacing = c3.slider(tr("nav.lm_spacing"), 50, 1000, 150, 25)
    configs = {"ekf_vo_lm": dict(vo_enabled=True, sp=spacing), "ekf_lm": dict(vo_enabled=False, sp=spacing),
               "ekf_vo": dict(vo_enabled=True, sp=0), "odometry": dict(vo_enabled=False, sp=0)}
    if st.button(tr("btn.run_compare"), type="primary") or ss.get("ni_key") != (n_mc, slip, spacing, ss.get("routes_key")):
        rows, curves = [], {}
        prog = st.progress(0.0)
        for j, (name, cfg) in enumerate(configs.items()):
            rm, fin, sig = [], [], []
            for k in range(n_mc):
                p = nav.NavParams(dt=max(1.0, 5.0 / spd), slip_bias=slip, vo_enabled=cfg["vo_enabled"], seed=k)
                sim, _, xy = run_nav(ctx, p, cfg["sp"])
                s = summarize(sim)
                key = "dr" if name == "odometry" else "ekf"
                rm.append(s[key]["rmse_m"])
                fin.append(s[key]["final_error_m"])
                if key == "ekf":
                    sig.append(s["ekf"]["position_sigma_final_m"])
                if k == 0:
                    est = sim[key]
                    curves[name] = (sim, est, xy)
                prog.progress((j * n_mc + k + 1) / (len(configs) * n_mc))
            dev = trajectory_deviation(np.stack(curves[name][2], 1), curves[name][1][:, :2])
            rows.append({"config": name, "rmse_mean_m": np.mean(rm), "rmse_p95_m": np.percentile(rm, 95),
                         "final_err_mean_m": np.mean(fin), "sigma_final_m": np.mean(sig) if sig else np.nan,
                         "heading_rmse_deg": summarize(curves[name][0])["dr" if name == "odometry" else "ekf"]["heading_rmse_deg"],
                         "max_deviation_m": float(dev.max()),
                         "consistency": summarize(curves[name][0])["ekf"]["consistency_2sigma"] if name != "odometry" else np.nan})
        prog.empty()
        ss.ni_rows, ss.ni_curves, ss.ni_key = rows, curves, (n_mc, slip, spacing, ss.get("routes_key"))
    rows, curves = ss.ni_rows, ss.ni_curves
    df = pd.DataFrame(rows)
    best = df.sort_values("rmse_mean_m").iloc[0]["config"]
    c = st.columns(4)
    for i, rw in enumerate(rows):
        c[i].metric(tr("ni.cfg." + rw["config"]), f"{rw['rmse_mean_m']:.2f} m", f"p95 {rw['rmse_p95_m']:.1f} m", delta_color="off")
    st.success(tr("ni.best", c=tr("ni.cfg." + best)))
    show = df.assign(config=df["config"].map(lambda c_: tr("ni.cfg." + c_))).round(3)
    ui.df_show(ui.tr_cols(show, tr))
    fig = go.Figure()
    for name, (sim, est, _) in curves.items():
        e, _ = errors(sim["true"], est)
        dist = np.concatenate([[0], np.cumsum(np.hypot(np.diff(sim["true"][:, 0]), np.diff(sim["true"][:, 1])))]) / 1000
        fig.add_trace(go.Scatter(x=dist, y=e, name=tr("ni.cfg." + name)))
    fig.update_layout(height=300, xaxis_title="km", yaxis_title=tr("nav.pos_error") + " (m)", yaxis_type="log",
                      title=tr("ni.error_growth"))
    ui.plotly(fig, key="ni_err")
    sim = curves["ekf_vo_lm"][0]
    hs = np.degrees(np.sqrt(np.maximum(sim["cov"][:, 2, 2], 0)))
    ps = np.sqrt(np.maximum(sim["cov"][:, 0, 0] + sim["cov"][:, 1, 1], 0))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(y=ps, name=tr("ni.pos_unc") + " (m)"))
    fig2.add_trace(go.Scatter(y=hs, name=tr("ni.head_unc") + " (°)", yaxis="y2"))
    fig2.update_layout(height=260, xaxis_title=tr("ni.step"), yaxis2=dict(overlaying="y", side="right"),
                       title=tr("ni.uncertainty"))
    ui.plotly(fig2, key="ni_unc")
    ui.export_buttons(tr, "navigation_comparison", df)
    ui.footer("navintel", tr, "Monte Carlo over sensor-noise seeds; RMSE = √mean(|p̂−p|²); drift = final error / path length;\n"
                              "consistency = share of steps with error ≤ 2σ; deviation = cross-track distance to the plan",
              ["SYNTHETIC SIMULATION of wheel odometry, gyro, visual odometry and landmark range-bearing"])
