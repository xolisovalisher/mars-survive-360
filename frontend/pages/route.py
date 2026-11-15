"""05 Route Planning."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.mapping import views as V
from mars_survive.routing.planner import ALGORITHMS, STRATEGIES


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("route", tr, [ctx.g.data_class])
    with ui.params(tr):
        c1, c2, c3, c4 = st.columns(4)
        mp.algorithm = c1.selectbox(tr("route.algorithm"), ALGORITHMS, index=ALGORITHMS.index(mp.algorithm),
                                    format_func=lambda a: tr("alg." + a))
        mp.slope_limit_deg = float(c2.slider(tr("lbl.slope_limit"), 5, 35, int(mp.slope_limit_deg)))
        mp.scenario = c3.selectbox(tr("lbl.scenario"), ["astronaut", "rover"], index=0 if mp.scenario == "astronaut" else 1,
                                   format_func=lambda s: tr("scen." + s))
        mp.dwell_min = float(c4.number_input(tr("lbl.dwell_min"), 0.0, 240.0, float(mp.dwell_min), 5.0))
        c5, c6, c7, c8 = st.columns(4)
        mp.w_slope = c5.slider(tr("route.w_slope"), 0.0, 5.0, float(mp.w_slope), 0.1)
        mp.w_hazard = c6.slider(tr("route.w_hazard"), 0.0, 5.0, float(mp.w_hazard), 0.1)
        mp.w_energy = c7.slider(tr("route.w_energy"), 0.0, 5.0, float(mp.w_energy), 0.1)
        click = c8.radio(tr("map.click_mode"), ["start", "goal", "stop", "base"], horizontal=True,
                         format_func=lambda m: tr("click." + m))
        from mars_survive.ai import traversability as TV
        if TV.MODEL_PATH.exists() and ctx.eng.ml_prob() is not None:
            mp.ml_blend = st.slider(tr("ml.blend"), 0.0, 1.0, float(mp.ml_blend), 0.05, help=tr("ml.blend_help"))
        else:
            mp.ml_blend = 0.0
            st.caption(tr("ml.blend_none"))
        st.caption(tr("route.points", s=f"{ss.start[0]:.4f}, {ss.start[1]:.4f}", g=f"{ss.goal[0]:.4f}, {ss.goal[1]:.4f}",
                      n=len(ss.stops)))
    b1, b2, b3 = st.columns([1, 1, 3])
    force = b1.button(tr("btn.compute_routes"), type="primary", width="stretch")
    if b2.button(tr("btn.clear_stops"), width="stretch"):
        ss.stops = []
        st.rerun()
    routes = ui.run_safely(tr, state.ensure_routes, ctx, force)
    if routes is None:
        return
    found = {k: v for k, v in routes.items() if v.found}
    if not found:
        st.error(tr("route.none_found"))
    sel = b3.radio(tr("route.active"), STRATEGIES, index=STRATEGIES.index(ss.strategy), horizontal=True,
                   format_func=lambda s: tr("strat." + s))
    if sel != ss.strategy:
        ss.strategy = sel
        st.rerun()
    left, right = st.columns([3, 2])
    with left:
        out = maps.mission_map(ctx, layer_names=("hillshade", "slope", "hazard", "ml"), show={"hillshade", "hazard"},
                               routes=routes, active=ss.strategy, height=520, key="route_map", clickable=True)
        p = maps.clicked(out, "route_map")
        if p:
            if not ctx.g.valid(*ctx.g.rowcol(*p)):
                st.toast(tr("map.outside"))
            elif click == "stop":
                ss.stops = ss.stops + [p]
                st.rerun()
            else:
                setattr(ss, click, p)
                if click == "start":
                    ss.base = p
                st.rerun()
    with right:
        rows = []
        for k in STRATEGIES:
            r = routes[k]
            if not r.found:
                rows.append({"strategy": tr("strat." + k), "found": "✗ " + tr("route.reason." + (r.reason or "no_path"))})
                continue
            s = r.summary()
            rows.append({"strategy": tr("strat." + k), "found": "✓", "distance_2d_km": round(s["distance_2d_km"], 3),
                         "distance_3d_km": round(s["distance_3d_km"], 3), "mean_slope_deg": round(s["mean_slope_deg"], 2),
                         "max_slope_deg": round(s["max_slope_deg"], 2), "hazard_mean": round(s["hazard_mean"], 3),
                         "energy_kwh": round(ctx.eng.resources(r, mp, ss.stop_cuts[k][1:-1])["energy_kwh"], 3),
                         "expanded_nodes": s["expanded_nodes"], "compute_s": s["compute_s"]})
        df = pd.DataFrame(rows)
        tt = df.set_index("strategy").T.reset_index().rename(columns={"index": "metric"})
        tt["metric"] = ui.tr_vals(tt["metric"], tr, "col.")
        ui.df_show(ui.tr_cols(tt.astype(str), tr))
    if found:
        t1, t2 = st.tabs([tr("route.profiles"), tr("map.tab3d")])
        with t1:
            fig = go.Figure()
            for k, r in found.items():
                fig.add_trace(go.Scatter(x=r.dist3d_m / 1000, y=r.elev, name=tr("strat." + k),
                                         line=dict(color=V.ROUTE_COLORS[k], width=3 if k == ss.strategy else 1.5)))
            fig.update_layout(height=320, xaxis_title=tr("lbl.dist3d") + " (km)", yaxis_title=tr("lbl.elevation") + " (m)")
            ui.plotly(fig, key="route_prof")
            r = found.get(ss.strategy) or next(iter(found.values()))
            fig2 = go.Figure(go.Scatter(x=r.dist3d_m / 1000, y=r.slope_deg, fill="tozeroy", line=dict(color="#e4572e")))
            fig2.add_hline(y=mp.slope_limit_deg, line_dash="dash", line_color="red")
            fig2.update_layout(height=220, xaxis_title="km", yaxis_title=tr("lbl.slope") + " (°)",
                               title=tr("route.slope_along", s=tr("strat." + ss.strategy)))
            ui.plotly(fig2, key="route_slope")
        with t2:
            ui.plotly(V.surface_3d(ctx.g, found, max_cells=140, exaggeration=3.0), key="route3d")
        c1, c2 = st.columns(2)
        c1.download_button("GeoJSON", json.dumps(V.route_geojson(found)), "routes.geojson", "application/geo+json")
        r = found.get(ss.strategy) or next(iter(found.values()))
        pts = pd.DataFrame({"lat": r.lat, "lon": r.lon, "elev_m": r.elev, "dist3d_m": r.dist3d_m, "slope_deg": r.slope_deg,
                            "hazard": r.hazard})
        c2.download_button("CSV", pts.to_csv(index=False).encode(), f"route_{ss.strategy}.csv", "text/csv")
    ui.footer("route", tr,
              "A*: f = g + h, h = straight-line distance (admissible); Weighted A*: h·ε; Dijkstra: h = 0\n"
              "edge = 3-D length × factor(strategy) on a 16-neighbour grid; slope > limit, no-go and unknown cells removed\n"
              "factors: shortest 1 | slope 1+4w(s/s_lim)² | hazard 1+6wH | balanced 1+1.5w_s(s/s_lim)²+2.5w_hH+5w_e·max(grade,0)",
              [ctx.g.source, "Hart, Nilsson & Raphael 1968 (A*)", "Pohl 1970 (Weighted A*)"])
