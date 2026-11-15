"""Module 02 tab: 3-D Mars globe with NASA imagery → click Jezero → local 3-D terrain (planet → crater)."""
from __future__ import annotations

import html

import streamlit as st

import config as C

from frontend.components import maps, state, ui
from mars_survive.common import ModuleError
from mars_survive.mapping import globe as G


@st.cache_data(show_spinner=False, max_entries=4)
def _tex_url(key: str, prefer_trek: bool):
    t = G.best_texture(prefer_trek)
    return G.data_url(t), t.source, t.data_class, round(t.resolution_km, 1), t.image.size


def render(ctx, routes, surface_fn):
    tr, ss = ctx.tr, st.session_state
    st.info(tr("globe.intro"))
    trek_key = str(G.TREK_CACHE.stat().st_mtime) if G.TREK_CACHE.exists() else "none"
    with ui.params(tr, expanded=False):
        c1, c2, c3 = st.columns([2, 1, 2])
        if C.BROWSER:
            prefer_trek = False
            c1.caption(tr("browser.no_trek"))
        else:
            prefer_trek = c1.toggle(tr("globe.prefer_trek"), value=True, help=tr("globe.prefer_trek_help"))
        show_grid = c2.toggle(tr("globe.grid"), value=True)
        if not C.BROWSER and c3.button(tr("globe.fetch_trek"), width="stretch"):
            bar = st.progress(0.0, text=tr("globe.fetching"))
            try:
                G.fetch_trek_texture(progress=lambda f: bar.progress(min(1.0, f), text=tr("globe.fetching")))
                bar.empty()
                st.success(tr("globe.trek_ok"))
                _tex_url.clear()
                trek_key = str(G.TREK_CACHE.stat().st_mtime)
            except ModuleError as e:
                bar.empty()
                st.warning(tr("globe.trek_failed") + f" ({tr(e.key)} — {e.detail})")
    try:
        url, src, dc, res_km, size = _tex_url(trek_key, prefer_trek)
    except ModuleError as e:
        st.error(f"{tr(e.key)} — {e.detail}")
        return
    labels = {s.key: tr("globe.site." + s.key) for s in G.SITES}
    keys = [s.key for s in G.SITES]
    sel = ss.get("globe_site")
    focus = next((s for s in G.SITES if s.key == sel), None)
    st.markdown(ui.badge(dc, tr) + f" &nbsp;<small>{html.escape(src)} · ≈ {res_km} km/px · {size[0]}×{size[1]}</small>",
                unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        ov = maps.overlay_png(state._dem_key(), "hillshade", ctx.mp.slope_limit_deg) if focus and focus.has_dem else None
        ev = st.pydeck_chart(G.deck(url, labels, ctx.g, focus, show_grid, sel, ov), height=560, on_select="rerun",
                             selection_mode="single-object", key=f"globe_{sel or 'all'}")
    picked = None
    try:
        objs = (ev or {}).get("selection", {}).get("objects", {}).get("sites") or []
        picked = objs[0]["key"] if objs else None
    except Exception:  # noqa: BLE001
        picked = None
    with c2:
        st.caption(tr("globe.click_hint"))
        if "_globe_radio_pending" in ss:                     # sync the list with a click on the globe
            ss.globe_radio = ss.pop("_globe_radio_pending")
        choice = st.radio(tr("globe.or_choose"), ["—"] + keys, index=(keys.index(sel) + 1) if sel in keys else 0,
                          format_func=lambda k: "—" if k == "—" else f"{keys.index(k) + 1}. {labels[k]}",
                          key="globe_radio")
        for i, s in enumerate(G.SITES, 1):
            st.markdown(f"<small>{'🟠' if s.kind == 'crater' else '🔵'} <b>{i}. {html.escape(labels[s.key])}</b><br>"
                        f"{abs(s.lat):.4f}°{'N' if s.lat >= 0 else 'S'}, {s.lon:.4f}°E<br>"
                        f"<span style='opacity:.7'>{html.escape(s.source)}</span></small>", unsafe_allow_html=True)
        if sel:
            st.button(tr("globe.back"), width="stretch", on_click=_reset)
    new = picked or (choice if choice != "—" else None)
    if new != sel and (picked or choice != "—"):
        ss.globe_site = new
        if picked:
            ss["_globe_radio_pending"] = picked
        st.rerun()
    st.caption(tr("globe.note"))
    if focus is not None and focus.has_dem:
        st.markdown(ui.badge(getattr(ctx.g.data_class, "value", str(ctx.g.data_class)), tr)
                    + f" &nbsp;<small>{html.escape(tr('globe.dem_overlay'))}</small>", unsafe_allow_html=True)
    if not sel:
        return
    site = focus
    ui.section(tr("globe.to_crater", s=labels[site.key]))
    if not site.has_dem:
        st.info(tr("globe.no_dem", s=labels[site.key]))
        return
    st.success(tr("globe.zoomed", s=labels[site.key]))
    c1, c2, c3 = st.columns(3)
    ex = c1.slider(tr("map.exaggeration"), 1.0, 10.0, 3.0, 0.5, key="globe_ex")
    res = c2.slider(tr("map.resolution"), 60, 240, 150, 10, key="globe_res")
    colr = c3.radio(tr("map.color_by"), ["elevation", "hazard"], format_func=lambda n: tr("layer." + n),
                    horizontal=True, key="globe_col")
    ui.plotly(surface_fn(ctx, routes, ex, res, colr), key="globe_local3d")
    st.caption(tr("map.3d_note"))


def _reset():
    st.session_state.globe_site = None
    st.session_state.globe_radio = "—"
