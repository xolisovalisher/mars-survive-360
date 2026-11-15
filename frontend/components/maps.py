"""Map helpers used by several pages."""
from __future__ import annotations

import numpy as np
import streamlit as st

import config as C
from mars_survive.mapping import views as V

from . import state


@st.cache_data(show_spinner=False, max_entries=64)
def overlay_png(dem_key: str, name: str, slope_limit: float, ml_key: float = 0.0) -> str:
    eng = state.engine()
    eng.set_slope_limit(slope_limit)
    g, T, H = eng.g, eng.T, eng.H
    if name == "hillshade":
        return V.png_url(V.to_rgba(T.hillshade, "gray", 0, 1, alpha=0.9))
    if name == "elevation":
        return V.png_url(V.to_rgba(g.z, "gist_earth", alpha=0.65))
    if name == "slope":
        return V.png_url(V.to_rgba(T.slope, "magma_r", 0, 30, alpha=0.65))
    if name == "aspect":
        return V.png_url(V.to_rgba(T.aspect, "twilight", 0, 360, alpha=0.6))
    if name == "curvature":
        return V.png_url(V.to_rgba(T.curvature, "RdBu_r", alpha=0.6))
    if name == "roughness":
        return V.png_url(V.to_rgba(T.roughness, "viridis", alpha=0.6))
    if name == "tri":
        return V.png_url(V.to_rgba(T.tri, "cividis", alpha=0.6))
    if name == "relief":
        return V.png_url(V.to_rgba(T.relief, "plasma", alpha=0.6))
    if name == "variability":
        return V.png_url(V.to_rgba(T.variability, "inferno", alpha=0.6))
    if name == "complexity":
        return V.png_url(V.to_rgba(T.complexity, "YlOrRd", 0, 1, alpha=0.6))
    if name == "hazard":
        return V.png_url(V.classes_rgba(H.level, V.HAZARD_PALETTE, 0.6))
    if name == "thermal" and g.thermal is not None:
        return V.png_url(V.to_rgba(g.thermal, "inferno", alpha=0.7))
    if name == "ml":
        pm = eng.ml_prob()
        if pm is None:
            raise ValueError("no ML model")
        return V.png_url(V.to_rgba(pm, "RdYlGn_r", 0, 1, alpha=0.6))
    if name == "nodata":
        return V.png_url(V.classes_rgba((~np.isfinite(g.z)).astype(np.uint8), {1: "#7b2cbf"}, 0.8))
    raise ValueError(name)


def layers(ctx, names: list[str], show: set[str]) -> dict:
    key = state._dem_key()
    out = {}
    from mars_survive.ai import traversability as TV
    mk = TV.MODEL_PATH.stat().st_mtime if TV.MODEL_PATH.exists() else 0.0
    for n in names:
        if n == "thermal" and ctx.g.thermal is None:
            continue
        if n == "ml" and (not mk or ctx.eng.ml_prob() is None):   # missing or unreadable model: no layer, no crash
            continue
        out[ctx.tr("layer." + n)] = (overlay_png(key, n, ctx.mp.slope_limit_deg, mk if n == "ml" else 0.0), n in show)
    return out


def mission_map(ctx, layer_names=("hillshade", "elevation", "slope", "hazard"), show=("hillshade", "hazard"),
                routes: dict | None = None, active: str | None = None, points=True, targets=None, extra=None,
                height=540, key="map", clickable=False, picker=True, fit=None):
    ss = st.session_state
    m = V.base_map(ctx.g, layers(ctx, list(layer_names), set(show)), zoom=ctx.settings.map_zoom,
                   basemap=ctx.settings.map_basemap)
    for name, r in (routes or {}).items():
        if r is not None and r.found:
            V.add_route(m, r.lat, r.lon, V.ROUTE_COLORS.get(name, "#fff"), 5 if name == active else 2,
                        ctx.tr("strat." + name))
    if points:
        m.add_child(_marker(ss.start, "A", "#2ec4b6", ctx.tr("lbl.start")))
        m.add_child(_marker(ss.goal, "B", "#e4572e", ctx.tr("lbl.goal")))
        if ss.base != ss.start:
            m.add_child(_marker(ss.base, "⌂", "#1d4ed8", ctx.tr("lbl.base"), fg="#fff"))
        for i, p in enumerate(ss.stops, 1):
            m.add_child(_marker(p, str(i), "#ffd166", f"{ctx.tr('lbl.stop')} {i}"))
    taken = {(round(ss.start[0], 4), round(ss.start[1], 4)), (round(ss.goal[0], 4), round(ss.goal[1], 4))} if points else set()
    for t in targets or []:
        if (round(float(t["lat"]), 4), round(float(t["lon"]), 4)) in taken:   # A/B marker already shows this place
            continue
        m.add_child(_marker((t["lat"], t["lon"]), "★", "#9b5de5", t["name"], fg="#fff", size=20))
    trav = ss.get("m20_trav")
    if trav is not None and len(trav) and C.BROWSER:
        m.route(trav["lat"], trav["lon"], "#00e5ff", 2.5,
                f"{ctx.tr('pv.layer')} · {ctx.tr('dc.' + ss.get('m20_trav_class', 'synthetic'))}")
    elif trav is not None and len(trav):
        import folium
        fg = folium.FeatureGroup(name=ctx.tr("pv.layer"), show=True)
        folium.PolyLine(list(zip(trav["lat"], trav["lon"])), color="#00e5ff", weight=2.5, opacity=0.9, dash_array="6 4",
                        tooltip=f"{ctx.tr('pv.layer')} · {ctx.tr('dc.' + ss.get('m20_trav_class', 'synthetic'))}").add_to(fg)
        fg.add_to(m)
    if extra:
        extra(m)
    if fit and not C.BROWSER:            # frame the planned walk instead of the whole analysis window
        la = [p[0] for p in fit]
        lo = [p[1] for p in fit]
        pad = max(0.012, 0.45 * max(max(la) - min(la), max(lo) - min(lo)))
        m.fit_bounds([[min(la) - pad, min(lo) - pad], [max(la) + pad, max(lo) + pad]])
    V.finish(m)
    return render_map(m, height=height, key=key, clickable=clickable, tr=ctx.tr if picker else None)


def render_map(m, height=540, key="map", clickable=False, tr=None):
    """Draw a map from V.base_map: Folium on the desktop, deck.gl in the browser build."""
    if not C.BROWSER:
        from streamlit_folium import st_folium
        ret = ["last_clicked"] if clickable else []
        return st_folium(m, height=height, use_container_width=True, returned_objects=ret, key=key)
    from mars_survive.mapping import deckmap
    names = [n for n, _, _ in m.overlays]
    on = [n for n, _, s in m.overlays if s]
    shown = set(on)
    if len(names) > len(on) and tr is not None:
        shown = set(st.multiselect(tr("map.visible_layers"), names, default=on, key=f"{key}_layers"))
    deck = m.deck(height=height, clickable=clickable, show=shown)
    if clickable:
        ev = st.pydeck_chart(deck, height=height, width="stretch", on_select="rerun",
                             selection_mode="single-object", key=key)
        return deckmap.picked_point(ev)
    st.pydeck_chart(deck, height=height, width="stretch", key=key)
    return None


def _marker(p, text, bg, tip, fg="#111", size=24):
    if C.BROWSER:
        from mars_survive.mapping.deckmap import Marker
        t = {"⌂": "B", "★": "*", "⌖": "+", "•": "o"}.get(text, text)
        return Marker(float(p[0]), float(p[1]), t, bg, tip, fg, size)
    import folium
    return folium.Marker(list(p), tooltip=tip, icon=V.div_marker(text, bg, fg, size))


def clicked(out, key: str):
    """Return (lat, lon) of a NEW click on this map, else None."""
    if not out or not out.get("last_clicked"):
        return None
    lc = out["last_clicked"]
    p = (round(lc["lat"], 6), round(lc["lng"], 6))
    if st.session_state.get(f"_click_{key}") == p:
        return None
    st.session_state[f"_click_{key}"] = p
    return p
