"""06 Hazard Detection."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.hazards.detect import LEVELS, detect, summary


def render(ctx):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    ui.header("hazards", tr, [ctx.g.data_class])
    with ui.params(tr):
        c1, c2, c3 = st.columns(3)
        lim = c1.slider(tr("lbl.slope_limit"), 5, 35, int(mp.slope_limit_deg))
        rel = c2.slider(tr("hz.relief_min"), 5, 60, 15)
        mn = c3.slider(tr("hz.min_cells"), 1, 30, 4)
    if lim != mp.slope_limit_deg:
        mp.slope_limit_deg = float(lim)
    ctx.eng.set_slope_limit(mp.slope_limit_deg)
    H = ctx.eng.H if (rel == 15 and mn == 4) else ui.run_safely(tr, detect, ctx.g, ctx.eng.T, mp.slope_limit_deg, rel, mn)
    if H is None:
        return
    ss.hazard_objects = H.objects
    sm = summary(H)
    c = st.columns(6)
    c[0].metric(tr("hz.objects"), len(H.objects))
    for i, lv in enumerate(["safe", "caution", "high", "no-go", "unknown"], 1):
        c[i].metric(tr("hz." + lv), f"{sm[lv] * 100:.1f} %")
    r, prof, _ = state.active(ctx)
    left, right = st.columns([3, 2])
    with left:
        def extra(m):
            for o in H.objects[:150]:
                if o["level"] in ("high", "no-go"):
                    m.add_child(maps._marker((o["lat"], o["lon"]), "!", "#d7191c" if o["level"] == "no-go" else "#ff6a00",
                                             f"#{o['id']} {tr('hzt.' + o['type'])} · {tr('hz.' + o['level'])}", fg="#fff", size=16))
        maps.mission_map(ctx, layer_names=("hillshade", "hazard"), show={"hillshade", "hazard"},
                         routes={ss.strategy: r} if r else {}, active=ss.strategy, extra=extra, height=500, key="hz_map")
        st.caption(tr("hz.caution") + " · 🟧 " + tr("hz.high") + " · 🟥 " + tr("hz.no-go") + " · 🟪 " + tr("hz.unknown"))
    with right:
        types = pd.Series([o["type"] for o in H.objects]).value_counts()
        fig = go.Figure(go.Bar(x=[tr("hzt." + t) for t in types.index], y=types.values, marker_color="#e4572e"))
        fig.update_layout(height=250, title=tr("hz.by_type"))
        ui.plotly(fig, key="hz_types")
        if r is not None:
            ui.section(tr("hz.on_route"))
            rr, cc = np.divmod(np.asarray(r.nodes), ctx.g.shape[1])
            lv = H.level[rr, cc]
            on = {tr("hz." + LEVELS[k]): int((lv == k).sum()) for k in LEVELS}
            st.write(on)
            st.caption(tr("hz.route_hazard", m=f"{np.mean(r.hazard):.3f}", x=f"{np.max(r.hazard):.3f}"))
    df = pd.DataFrame(H.objects)
    if not df.empty:
        show = df.assign(type=ui.tr_vals(df["type"], tr, "hzt."), level=ui.tr_vals(df["level"], tr, "hz."))
        show = show.round({"lat": 5, "lon": 5, "area_km2": 4, "max_slope_deg": 1})
        ui.section(tr("hz.table"))
        ui.df_show(ui.tr_cols(show, tr), height=300)
        ui.export_buttons(tr, "hazards", df, {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": o, "geometry": {"type": "Point", "coordinates": [o["lon"], o["lat"]]}}
            for o in H.objects]})
    ui.footer("hazards", tr,
              "no-go: slope ≥ limit | caution: slope ≥ 0.6·limit or roughness ≥ p95 | high: TRI ≥ p95 & rough ≥ p90,\n"
              "curvature ≥ p97 & relief ≥ min (crater edge), relief ≥ 3·p90 (discontinuity) | unknown: NoData ±1 cell\n"
              "objects = connected components (8-conn.) ≥ min cells; confidence 0.9/0.6/0.3 (×0.6 if synthetic DEM)",
              [ctx.g.source])
