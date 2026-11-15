"""02 Mars 2D/3D Map."""
from __future__ import annotations

import json

import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.mapping import coords
from mars_survive.mapping import views as V
from mars_survive.science import catalog

ALL_LAYERS = ["hillshade", "elevation", "slope", "roughness", "hazard", "ml", "thermal", "nodata"]


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("map", tr, [ctx.g.data_class, "Real"])
    routes = state.ensure_routes(ctx)
    tgl, t2d, t3d, tdk = st.tabs([tr("map.tab_globe"), tr("map.tab2d"), tr("map.tab3d"),
                                  tr("map.tab_deck")])
    with tgl:
        from frontend.components import globe_tab
        globe_tab.render(ctx, routes, ui_surface)
    with t2d:
        with ui.params(tr):
            c1, c2, c3 = st.columns([2, 2, 2])
            show = c1.multiselect(tr("map.visible_layers"), ALL_LAYERS, default=["hillshade", "hazard"],
                                  format_func=lambda n: tr("layer." + n))
            mode = c2.radio(tr("map.click_mode"), ["marker", "start", "goal", "stop", "base"], horizontal=True,
                            format_func=lambda m: tr("click." + m))
            q = c3.text_input(tr("map.search_coord"), placeholder="18.4447, 77.4508  |  18.44N 282.55W")
            if q:
                try:
                    lat, lon = coords.parse_coordinate(q)
                    ss.search_pt = (lat, lon)
                    inside = ctx.g.inside(*ctx.g.rowcol(lat, lon))
                    st.caption(tr("map.found_coord", lat=f"{lat:.5f}", lon=f"{lon:.5f}") +
                               ("" if inside else " — " + tr("map.outside")))
                except ValueError as e:
                    st.error(f"{tr('err.coord')}: {e}")
        tg = catalog.all_targets()

        def extra(m):
            if ss.get("search_pt"):
                m.add_child(maps._marker(ss.search_pt, "⌖", "#ffffff", tr("map.search_result")))
            for i, p in enumerate(ss.get("user_marks", []), 1):
                m.add_child(maps._marker(p, "•", "#00e5ff", f"{tr('click.marker')} {i}", size=16))

        out = maps.mission_map(ctx, layer_names=ALL_LAYERS, show=set(show) or {"hillshade"}, routes=routes,
                               active=ss.strategy, targets=tg, extra=extra, height=560, key="map2d", clickable=True,
                               picker=False)
        p = maps.clicked(out, "map2d")
        if p:
            if not ctx.g.inside(*ctx.g.rowcol(*p)):
                st.toast(tr("map.outside"))
            else:
                if mode == "marker":
                    ss.setdefault("user_marks", []).append(p)
                elif mode == "stop":
                    ss.stops = ss.stops + [p]
                else:
                    setattr(ss, mode, p)
                    if mode == "start" and ss.base == ss.get("_old_start", ss.start):
                        pass
                st.rerun()
        # info about the clicked point
        lp = ss.get("_click_map2d")
        if lp:
            z = ctx.g.sample(ctx.g.z, *lp)
            sl = ctx.g.sample(ctx.eng.T.slope, *lp)
            r, c = ctx.g.rowcol(*lp)
            lv = int(ctx.eng.H.level[r, c]) if ctx.g.inside(r, c) else 4
            c = st.columns(5)
            c[0].metric(tr("lbl.lat_c"), f"{lp[0]:.5f}°")
            c[1].metric(tr("lbl.lon_e"), f"{lp[1]:.5f}°", f"{coords.east_to_west(lp[1]):.4f}° W", delta_color="off")
            c[2].metric(tr("lbl.lat_g"), f"{coords.centric_to_graphic(lp[0]):.5f}°")
            c[3].metric(tr("lbl.elevation"), f"{z:.1f} m" if z == z else tr("lbl.nodata"))
            c[4].metric(tr("lbl.slope"), f"{sl:.1f}°" if sl == sl else "—", tr("hz." + ["safe", "caution", "high", "no-go", "unknown"][lv]),
                        delta_color="off")
        c1, c2, c3 = st.columns(3)
        if c1.button(tr("btn.clear_marks")):
            ss.user_marks, ss.stops = [], []
            st.rerun()
        gj = V.route_geojson(routes)
        gj["features"] += V.points_geojson([{"lat": t["lat"], "lon": t["lon"], "name": t["name"], "origin": t["origin"]}
                                            for t in tg])["features"]
        c2.download_button("GeoJSON", json.dumps(gj), "mars_survive_map.geojson", "application/geo+json")
        up = c3.file_uploader(tr("map.import_geojson"), type=["geojson", "json"], key="gj_up")
        if up is not None and ss.get("_gj_name") != up.name:
            try:
                pts = V.parse_geojson_points(up.getvalue()[:5_000_000].decode("utf-8"))
                pts = [p for p in pts if ctx.g.inside(*ctx.g.rowcol(p["lat"], p["lon"]))][:20]
                ss.stops = [(p["lat"], p["lon"]) for p in pts]
                ss._gj_name = up.name
                st.success(tr("map.imported", n=len(pts)))
            except (ValueError, KeyError, UnicodeDecodeError) as e:
                st.error(f"{tr('err.geojson')}: {e}")
    with t3d:
        with ui.params(tr, expanded=False):
            c1, c2, c3 = st.columns(3)
            ex = c1.slider(tr("map.exaggeration"), 1.0, 10.0, 3.0, 0.5)
            res = c2.slider(tr("map.resolution"), 60, 240, 150, 10)
            colr = c3.radio(tr("map.color_by"), ["elevation", "hazard"], format_func=lambda n: tr("layer." + n),
                            horizontal=True)
        fig = ui_surface(ctx, routes, ex, res, colr)
        ui.plotly(fig, key="map3d")
        st.caption(tr("map.3d_note"))
    with tdk:
        c1, c2 = st.columns(2)
        ex2 = c1.slider(tr("map.exaggeration"), 1.0, 10.0, 3.0, 0.5, key="deck_ex")
        col2 = c2.radio(tr("map.color_by"), ["elevation", "hazard"], format_func=lambda n: tr("layer." + n),
                        horizontal=True, key="deck_col")
        deck = V.deck_3d(ctx.g, routes, ctx.eng.H.index if col2 == "hazard" else None, ex2,
                         traverse=st.session_state.get("m20_trav"))
        if deck is None:
            st.info(tr("map.deck_missing"))
        else:
            st.pydeck_chart(deck, height=560)
            st.caption(tr("map.deck_note"))
    ui.footer("map", tr, "Leaflet CRS EPSG:4326 (equirectangular) + Mars Trek WMTS default028mm {z}/{row}/{col};\n"
                         "3-D: DEM elevations on local E/N km grid, vertical exaggeration user-set",
              ["NASA JPL Mars Trek (Viking MDIM 2.1, MGS MOLA)", ctx.g.source])


def ui_surface(ctx, routes, ex, res, colr):
    hz = ctx.eng.H.index if colr == "hazard" else None
    return V.surface_3d(ctx.g, routes, max_cells=res, exaggeration=ex, hazard=hz)
