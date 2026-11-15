"""03 Terrain Intelligence."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, ui
from mars_survive.dem.loader import quality_report
from mars_survive.terrain.analysis import profile, stats

LAYERS = {"slope": "°", "aspect": "°", "curvature": "1/m", "roughness": "m", "tri": "m", "relief": "m",
          "variability": "°", "complexity": "0-1"}


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("terrain", tr, [ctx.g.data_class])
    T = ctx.eng.T
    with ui.params(tr):
        c1, c2 = st.columns(2)
        lay = c1.selectbox(tr("ter.layer"), list(LAYERS), format_func=lambda n: f"{tr('layer.' + n)} ({LAYERS[n]})")
        src = c2.radio(tr("ter.profile_between"), ["route_ends", "custom"], format_func=lambda s: tr("ter." + s),
                       horizontal=True)
        if src == "custom":
            c3, c4, c5, c6 = st.columns(4)
            la1 = c3.number_input("lat 1", value=float(ss.start[0]), format="%.5f")
            lo1 = c4.number_input("lon 1", value=float(ss.start[1]), format="%.5f")
            la2 = c5.number_input("lat 2", value=float(ss.goal[0]), format="%.5f")
            lo2 = c6.number_input("lon 2", value=float(ss.goal[1]), format="%.5f")
        else:
            (la1, lo1), (la2, lo2) = ss.start, ss.goal
    arr = getattr(T, lay)
    left, right = st.columns([3, 2])
    with left:
        maps.mission_map(ctx, layer_names=("hillshade", lay, "nodata"), show={"hillshade", lay, "nodata"},
                         height=470, key="ter_map")
    with right:
        st_ = stats(arr)
        ui.section(tr("ter.statistics"))
        ui.df_show(ui.tr_cols(pd.DataFrame([{"layer": tr("layer." + n), "unit": LAYERS[n],
                                             **{k: (round(v, 4) if v is not None else None) for k, v in stats(getattr(T, n)).items()}}
                                            for n in LAYERS]), tr))
        v = arr[np.isfinite(arr)]
        fig = go.Figure(go.Histogram(x=v, nbinsx=60, marker_color="#e4572e"))
        fig.update_layout(title=f"{tr('ter.histogram')}: {tr('layer.' + lay)}", height=230, xaxis_title=LAYERS[lay])
        ui.plotly(fig, key="ter_hist")
        if st_["mean"] is None:
            st.error(tr("lbl.nodata"))
    ui.section(tr("ter.profile"))
    p = ui.run_safely(tr, profile, ctx.g, la1, lo1, la2, lo2, 300)
    if p:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=p["dist_m"] / 1000, y=p["elev"], name=tr("lbl.elevation"), line=dict(color="#ff8a5c")))
        fig.add_trace(go.Scatter(x=p["dist_m"] / 1000, y=p["slope_deg"], name=tr("lbl.slope") + " (°)", yaxis="y2",
                                 line=dict(color="#2ec4b6", width=1)))
        fig.update_layout(height=300, xaxis_title="km", yaxis_title="m", yaxis2=dict(overlaying="y", side="right", title="°"))
        ui.plotly(fig, key="ter_prof")
        c = st.columns(5)
        c[0].metric(tr("lbl.dist2d"), f"{p['dist2d_m'] / 1000:.3f} km")
        c[1].metric(tr("lbl.dist3d"), f"{p['dist3d_m'] / 1000:.3f} km")
        c[2].metric(tr("lbl.gain"), f"{p['gain_m']:.0f} m")
        c[3].metric(tr("lbl.loss"), f"{p['loss_m']:.0f} m")
        c[4].metric(tr("lbl.nodata_samples"), str(p["nodata_samples"]))
        df = pd.DataFrame({"dist_km": p["dist_m"] / 1000, "lat": p["lat"], "lon": p["lon"], "elev_m": p["elev"],
                           "slope_deg": p["slope_deg"]})
        ui.export_buttons(tr, "terrain_profile", df)
    ui.section(tr("ter.quality"))
    q = quality_report(ctx.g.z)
    c = st.columns(5)
    c[0].metric(tr("lbl.valid"), f"{q['valid_fraction'] * 100:.1f} %")
    c[1].metric(tr("lbl.nodata_cells"), f"{q['nodata_cells']}")
    c[2].metric(tr("lbl.spikes"), f"{q.get('spike_cells', 0)}")
    c[3].metric(tr("lbl.range"), f"{q.get('min_m', 0):.0f} … {q.get('max_m', 0):.0f} m")
    c[4].metric(tr("lbl.quality"), tr("q." + q["status"]))
    st.caption(tr("ter.crs_note", crs=ctx.g.meta.get("crs", "Mars sphere R=3396190 m"), res=f"{ctx.g.dy:.1f}"))
    ui.footer("terrain", tr,
              "dx = R·Δλ·cos φ, dy = R·Δφ (R = 3 396 190 m)\nslope = atan(√(z_x²+z_y²)); aspect = atan2(-z_x, -z_y)\n"
              "curvature = -(z_xx + z_yy); TRI = mean|Δz| (Riley 1999); relief = max-min (9×9)\n"
              "roughness = std(z - Gauss(z, σ=2 px)) in 5×5; complexity = mean of normalised slope/rough/relief/var",
              [ctx.g.source, "Riley et al. 1999 (TRI)", "Zevenbergen & Thorne 1987 (curvature concept)"])
