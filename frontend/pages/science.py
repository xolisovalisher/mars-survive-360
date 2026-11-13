"""18 Science Target Catalog."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.science import catalog as cat


def render(ctx):
    tr = ctx.tr
    ui.header("science", tr, ["Real", "User Supplied", "Synthetic"])
    t1, t2 = st.tabs(["🎯 " + tr("sci.tab_catalog"), "🛞 " + tr("pv.tab")])
    with t1:
        _catalog(ctx)
    with t2:
        from frontend.components import perseverance_tab
        perseverance_tab.render(ctx)
    ui.footer("science", tr, "distance to route = min great-circle distance to route vertices (R = 3389.5 km); "
              "traverse proximity = nearest traverse vertex (haversine)",
              ["NASA/JPL Mars 2020 (landing site coordinate)", "approximate locations — verify in NASA Mars Trek",
               "NASA/JPL MMGIS M20 traverse; mars.nasa.gov raw-image feed (when reachable)", "user entries"])


def _catalog(ctx):
    tr, ss = ctx.tr, st.session_state
    tg = cat.all_targets()
    r, _, _ = state.active(ctx)
    dist = cat.distance_to_route(tg, r.lat, r.lon) if r is not None else tg
    c1, c2 = st.columns([3, 2])
    with c1:
        out = maps.mission_map(ctx, routes={ss.strategy: r} if r else {}, active=ss.strategy, targets=tg, height=430,
                               key="sci_map", clickable=True)
        p = maps.clicked(out, "sci_map")
        if p:
            ss.sci_pick = p
    with c2:
        with st.form("add_target"):
            st.markdown("**" + tr("sci.add") + "**")
            pk = ss.get("sci_pick", ss.goal)
            name = st.text_input(tr("sci.name"), max_chars=120)
            a, b = st.columns(2)
            lat = a.number_input("lat (°N)", -90.0, 90.0, float(pk[0]), format="%.5f")
            lon = b.number_input("lon (°E)", -180.0, 360.0, float(pk[1]), format="%.5f")
            kind = st.selectbox(tr("sci.kind"), cat.KINDS, format_func=lambda k: tr("kind." + k))
            prio = st.slider(tr("sci.priority"), 1, 5, 3)
            desc = st.text_area(tr("lbl.description"), max_chars=1000)
            if st.form_submit_button("➕ " + tr("btn.add_target"), type="primary"):
                try:
                    cat.add(name, lat, lon, kind, desc, prio)
                    st.success(tr("sci.added"))
                    st.rerun()
                except ValueError as e:
                    st.error(f"{tr('err.invalid')}: {e}")
        st.caption(tr("sci.click_hint"))
    for origin in ("published", "approximate", "user"):
        part = [t for t in dist if t["origin"] == origin]
        ui.section(f"{tr('origin.' + origin)} ({len(part)})")
        if not part:
            st.caption("—")
            continue
        df = pd.DataFrame(part)
        cols = [c for c in ["id", "name", "lat", "lon", "kind", "priority", "status", "route_distance_m", "source"] if c in df]
        show = df[cols].copy()
        show["kind"] = show["kind"].map(lambda k: tr("kind." + k))
        show["status"] = show["status"].map(lambda s: tr("tstatus." + s))
        ui.df_show(ui.tr_cols(show.round({"lat": 5, "lon": 5, "route_distance_m": 0}), tr))
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    ids = [t["id"] for t in tg]
    sel = c1.selectbox(tr("sci.select"), ids, format_func=lambda i: next(f"#{t['id']} {t['name']}" for t in tg if t["id"] == i))
    t = next(x for x in tg if x["id"] == sel)
    stt = c2.selectbox(tr("lbl.status"), cat.STATUSES, index=cat.STATUSES.index(t["status"]), format_func=lambda s: tr("tstatus." + s))
    if c2.button(tr("btn.update_status")):
        cat.set_status(sel, stt)
        st.rerun()
    if c3.button("📍 " + tr("btn.add_waypoint"), width="stretch"):
        p = (t["lat"], t["lon"])
        if ctx.g.valid(*ctx.g.rowcol(*p)):
            ss.stops = ss.stops + [p]
            st.success(tr("sci.waypoint_added"))
        else:
            st.error(tr("map.outside"))
    sure = c4.checkbox(tr("ui.confirm_delete"), key=f"conf_del_{sel}", disabled=t["origin"] != "user")
    if c4.button("🗑 " + tr("btn.delete"), width="stretch", disabled=t["origin"] != "user" or not sure):
        cat.delete(sel)
        st.rerun()
    st.markdown("**" + tr("sci.tasks", n=t["name"]) + "**")
    for task in cat.observation_tasks(t):
        st.markdown(f"- {tr('task.' + task.replace(' ', '_').replace('+', 'and'))}")
    ui.export_buttons(tr, "science_targets", pd.DataFrame(dist))
