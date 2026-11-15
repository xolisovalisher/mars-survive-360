"""Module 18 tab: Perseverance traverse (ground truth) and raw images — what the crew will see at route points."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.common import ModuleError
from mars_survive.nasa_live import http
from mars_survive.nasa_live import perseverance as P
from mars_survive.science import catalog as cat

CLASS_KEY = {"Real": "real", "User Supplied": "user", "Synthetic": "synthetic"}


def _load_traverse(tr, src):
    ss = st.session_state
    if src == "live":
        if st.button(tr("pv.fetch"), type="primary"):
            try:
                with st.spinner(tr("ui.computing")):
                    c = P.fetch_traverse()
                ss.m20_trav, ss.m20_trav_class, ss.m20_trav_meta = P.parse_traverse(c["payload"]), "real", c["fetched_utc"]
            except ModuleError as e:
                st.error(f"{tr('pv.fetch_failed')}: {tr(e.key)} — {e.detail}")
    elif src == "upload":
        up = st.file_uploader(tr("pv.upload"), type=["json", "geojson"], key="pv_up")
        if up is not None:
            try:
                ss.m20_trav = P.parse_traverse(http.parse_json_bytes(up.getvalue()))
                ss.m20_trav_class, ss.m20_trav_meta = "user", up.name[:80]
            except ModuleError as e:
                st.error(f"{tr(e.key)} — {e.detail}")
    else:
        if ss.get("m20_trav_class") != "synthetic":
            ss.m20_trav, ss.m20_trav_class, ss.m20_trav_meta = P.parse_traverse(P.example_traverse()), "synthetic", ""
        st.warning(tr("pv.example_note"))


def _points(ctx):
    ss = st.session_state
    pts = [(ctx.tr("lbl.start"), ss.start)] + [(f"{ctx.tr('lbl.stop')} {i}", p) for i, p in enumerate(ss.stops, 1)] \
        + [(ctx.tr("lbl.goal"), ss.goal)]
    pts += [(f"★ {t['name']}", (t["lat"], t["lon"])) for t in cat.all_targets()]
    return pts


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    st.info(tr("pv.intro"))
    with ui.params(tr):
        c1, c2 = st.columns([2, 3])
        src = c1.radio(tr("pv.source"), ["live", "upload", "example"], format_func=lambda s: tr("pv.src." + s),
                       key="pv_src")
        near_m = c2.slider(tr("pv.near_m"), 50, 2000, 300, 50)
    _load_traverse(tr, src)
    trav = ss.get("m20_trav")
    if trav is None or (src == "live" and ss.get("m20_trav_class") != "real") or \
            (src == "upload" and ss.get("m20_trav_class") != "user"):
        st.info(tr("pv.need_data"))
        return
    cls = ss.m20_trav_class
    s = P.summary(trav)
    inside = np.mean([ctx.g.inside(*ctx.g.rowcol(a, b)) for a, b in zip(trav["lat"], trav["lon"])])
    st.markdown(ui.badge({"real": "Real", "user": "User Supplied", "synthetic": "Synthetic"}[cls], tr)
                + (f" <small>{tr('sw.fetched_at')}: {ss.get('m20_trav_meta', '')}</small>" if cls != "synthetic" else ""),
                unsafe_allow_html=True)
    k = st.columns(4)
    k[0].metric(tr("pv.vertices"), s["vertices"])
    k[1].metric(tr("pv.sols"), f"{s['sol_min']}–{s['sol_max']}" if s["sol_min"] is not None else "—")
    k[2].metric(tr("pv.driven"), f"{s['driven_km']:.2f} km")
    k[3].metric(tr("pv.inside_dem"), f"{inside * 100:.0f} %")
    if inside == 0:
        st.warning(tr("pv.outside"))
    r, _, _ = state.active(ctx)
    c1, c2 = st.columns([3, 2])
    with c1:
        maps.mission_map(ctx, routes={ss.strategy: r} if r else {}, active=ss.strategy, height=420, key="pv_map")
    with c2:
        if r is not None:
            rv = P.route_vs_traverse(trav, r.lat[::3], r.lon[::3])
            share = float((rv["dist_to_traverse_m"] <= near_m).mean())
            st.metric(tr("pv.route_share", m=near_m), f"{share * 100:.0f} %", help=tr("pv.route_share_help"))
            st.metric(tr("pv.route_min"), f"{rv['dist_to_traverse_m'].min():.0f} m")
        pts = _points(ctx)
        rows = []
        for name, p in pts:
            n = P.nearest(trav, *p)
            rows.append({"name": name, "lat": p[0], "lon": p[1], "dist_to_traverse_m": round(n["distance_m"]), "sol": n["sol"]})
        near_df = pd.DataFrame(rows)
        ui.df_show(ui.tr_cols(near_df[["name", "dist_to_traverse_m", "sol"]], tr), height=260)
    ui.section(tr("pv.see_title"))
    names = [n for n, _ in pts]
    c1, c2, c3 = st.columns([2, 2, 1])
    pick = c1.selectbox(tr("pv.point"), names, key="pv_pick")
    row = near_df[near_df["name"] == pick].iloc[0]
    cams = c2.multiselect(tr("pv.cameras"), list(P.CAMERA_GROUPS), default=["navcam", "mastcam", "hazcam"],
                          format_func=lambda c: tr("cam." + c))
    sol = row["sol"]
    if sol is None or pd.isna(sol):
        st.info(tr("pv.no_sol"))
        return
    sol = int(sol)
    d = float(row["dist_to_traverse_m"])
    (st.success if d <= near_m else st.warning)(
        tr("pv.what_see", p=pick, s=sol, d=f"{d:.0f}") if d <= near_m else tr("pv.far", p=pick, d=f"{d / 1000:.2f}", s=sol))
    payload, img_cls = None, None
    if cls == "synthetic":
        payload, img_cls = P.example_raw(), "Synthetic"
    else:
        if c3.button(tr("pv.load_images"), key="pv_img"):
            try:
                with st.spinner(tr("ui.computing")):
                    ss[f"pv_raw_{sol}"] = P.fetch_raw_images(sol)
            except ModuleError as e:
                st.error(f"{tr('pv.fetch_failed')}: {tr(e.key)} — {e.detail}")
        up = st.file_uploader(tr("pv.upload_raw"), type=["json"], key="pv_raw_up")
        if up is not None:
            try:
                payload, img_cls = http.parse_json_bytes(up.getvalue()), "User Supplied"
            except ModuleError as e:
                st.error(f"{tr(e.key)} — {e.detail}")
        if payload is None and ss.get(f"pv_raw_{sol}"):
            payload, img_cls = ss[f"pv_raw_{sol}"]["payload"], "Real"
    if payload is None:
        st.caption(tr("pv.images_hint", s=sol))
        return
    imgs = P.filter_cameras(P.parse_raw_images(payload), cams)
    st.markdown(ui.badge(img_cls, tr) + f" &nbsp; {tr('pv.images', s=sol)}: <b>{len(imgs)}</b>", unsafe_allow_html=True)
    if not len(imgs):
        st.info(tr("pv.no_images"))
        return
    cols = st.columns(4)
    for i, (_, im) in enumerate(imgs.head(16).iterrows()):
        with cols[i % 4]:
            cap = f"{im['instrument']} · LMST {im['lmst'] or '—'}"
            if im["thumb"]:
                st.image(im["thumb"], caption=cap, width="stretch")
                st.markdown(f"[{tr('pv.open')}]({im['full'] or im['page']})")
            else:
                st.markdown(f"<div class='ms-card'><small>{ui.html.escape(cap)}</small><br>"
                            f"<i>{ui.html.escape(tr('pv.no_thumb'))}</i></div>", unsafe_allow_html=True)
    st.caption(tr("pv.raw_note"))
    ui.export_buttons(tr, f"m20_raw_sol{sol}", imgs, key="pvraw")
