"""Mission Planner — the map-centred main workspace.

Left: mission setup (goal, start, destination, data layers, generate).
Centre: the map; routes, hazard zones, science points and the AI traversability layer are drawn on it.
Right: route analysis, hazard alerts, terrain profile, AI mission insights, mission summary, export.
Every number comes from the same engine the 27 modules use (no separate demo values).
"""
from __future__ import annotations

import html

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.integration import pipeline
from mars_survive.mapping import views as V
from mars_survive.routing.planner import STRATEGIES
from mars_survive.science import catalog

LAYERS = [  # (toggle id, map layer or None, default)
    ("hillshade", "hillshade", True), ("elevation", "elevation", False), ("slope", "slope", False),
    ("hazard", "hazard", True), ("science", None, True), ("ml", "ml", False), ("traverse", None, True),
]


def _card(col, label, value, sub=""):
    col.markdown(f"<div class='ms-kpi'><div class='k'>{html.escape(label)}</div><div class='v'>{html.escape(value)}</div>"
                 f"<div class='s'>{html.escape(sub)}</div></div>", unsafe_allow_html=True)


def _panel(title: str, icon: str, key: str, right: str = ""):
    c = st.container(key=key, border=False)
    c.markdown(f"<div class='ms-ph'><span class='material-symbols-rounded'>{icon}</span>{html.escape(title)}"
               + (f"<span class='r'>{right}</span>" if right else "") + "</div>", unsafe_allow_html=True)
    return c


def _fmt_ll(p):
    return f"{p[0]:.4f}°N, {p[1]:.4f}°E"


def _pipeline(ctx):
    ss, mp = st.session_state, ctx.mp
    key = (ss.start, ss.goal, mp.slope_limit_deg, mp.scenario, mp.budget_h, mp.o2_capacity_l, state._dem_key())
    if ss.get("pipeline_key") != key or "pipeline" not in ss:
        out = ui.run_safely(ctx.tr, pipeline.run, ctx.eng, ss.start, ss.goal, mp, None, ss.base)
        if out:
            ss.pipeline, ss.pipeline_key = out, key
            if out.get("navigation"):
                ss.nav_summary = out["navigation"]
            if out.get("link"):
                ss.link_result = out["link"]
            if out.get("recommended") and not ss.get("_strategy_user"):
                ss.strategy = out["recommended"]
    return ss.get("pipeline")


def _setup(ctx, targets):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    with _panel(tr("ws.setup"), "tune", "ms_p_setup"):
        st.caption(tr("ws.setup_sub"))
        scen = st.selectbox(tr("ws.goal"), ["astronaut", "rover"], index=0 if mp.scenario == "astronaut" else 1,
                            format_func=lambda s: tr("ws.goal." + s))
        if scen != mp.scenario:
            mp.scenario = scen
        # start / destination from the science-target catalogue (published or clearly labelled approximate points)
        names = {t["name"]: (float(t["lat"]), float(t["lon"])) for t in targets}
        opts = list(names) + [tr("ws.custom_point")]

        def idx_of(p):
            for i, (n, q) in enumerate(names.items()):
                if abs(q[0] - p[0]) < 1e-5 and abs(q[1] - p[1]) < 1e-5:
                    return i
            return len(opts) - 1
        s_sel = st.selectbox(tr("ws.start"), opts, index=idx_of(ss.start), key="pl_start")
        g_sel = st.selectbox(tr("ws.dest"), opts, index=idx_of(ss.goal), key="pl_goal")
        changed = False
        if s_sel in names and names[s_sel] != tuple(ss.start):
            ss.start = ss.base = names[s_sel]
            changed = True
        if g_sel in names and names[g_sel] != tuple(ss.goal):
            ss.goal = names[g_sel]
            changed = True
        st.caption(f"A · {_fmt_ll(ss.start)}  \nB · {_fmt_ll(ss.goal)}")
        ss.pl_click = st.segmented_control(tr("ws.click_sets"), ["start", "goal"], default=ss.get("pl_click", "goal"),
                                           format_func=lambda m: tr("ws.click." + m), key="pl_click_ctl") or "goal"
        c1, c2 = st.columns(2)
        mp.budget_h = float(c1.number_input(tr("ws.budget_h"), 1.0, 24.0, float(mp.budget_h), 0.5))
        mp.slope_limit_deg = float(c2.number_input(tr("ws.slope_limit"), 5, 35, int(mp.slope_limit_deg), 1))
        if changed:
            ss._strategy_user = False
            st.rerun()

    with _panel(tr("ws.layers"), "layers", "ms_p_layers"):
        st.caption(tr("ws.layers_sub"))
        on = {}
        for lid, _, default in LAYERS:
            if lid == "ml" and ctx.eng.ml_prob() is None:
                continue
            if lid == "traverse" and ss.get("m20_trav") is None:
                continue
            on[lid] = st.toggle(tr("ws.layer." + lid), value=ss.get(f"pl_l_{lid}", default), key=f"pl_l_{lid}")
    gen = st.button(tr("ws.generate"), type="primary", icon=":material/route:", width="stretch", key="pl_generate")
    return on, gen


def _map(ctx, routes, active, targets, on):
    tr, ss = ctx.tr, st.session_state
    names = [layer for lid, layer, _ in LAYERS if layer and on.get(lid)]
    show = set(names)
    if not on.get("traverse", True):
        trav, ss["m20_trav"] = ss.get("m20_trav"), None
    else:
        trav = None
    out = maps.mission_map(ctx, layer_names=tuple(names) or ("hillshade",), show=show or {"hillshade"},
                           routes=routes, active=active, targets=targets if on.get("science") else None,
                           height=640, key="planner_map", clickable=True, picker=False, fit=_fit_points(routes, active))
    if trav is not None:
        ss["m20_trav"] = trav
    p = maps.clicked(out, "planner_map")
    if p:
        if not ctx.g.valid(*ctx.g.rowcol(*p)):
            st.toast(tr("map.outside"))
        else:
            if ss.get("pl_click", "goal") == "start":
                ss.start = ss.base = p
            else:
                ss.goal = p
            ss._strategy_user = False
            st.rerun()
    # legend + source line under the map
    rc = "".join(f"<span><i class='ln' style='background:{V.ROUTE_COLORS[s]}'></i>{html.escape(tr('strat.' + s))}"
                 f"{' ✓' if s == active else ''}</span>" for s in STRATEGIES if routes.get(s) is not None and routes[s].found)
    hz = "".join(f"<span><i class='sq' style='background:{c}'></i>{html.escape(tr('hz.' + n))}</span>"
                 for c, n in zip(V.HAZARD_PALETTE.values(), ["caution", "high", "no-go", "unknown"]))
    st.markdown(
        f"<div class='ms-legend'><div><b>{html.escape(tr('ws.legend.routes'))}</b>{rc}</div>"
        f"<div><b>{html.escape(tr('ws.legend.hazards'))}</b>{hz}</div>"
        f"<div><b>{html.escape(tr('ws.legend.points'))}</b><span><i class='pt' style='background:#2ec4b6'></i>A · "
        f"{html.escape(tr('lbl.start'))}</span><span><i class='pt' style='background:#e4572e'></i>B · "
        f"{html.escape(tr('lbl.goal'))}</span><span><i class='pt' style='background:#9b5de5'></i>"
        f"{html.escape(tr('ws.layer.science'))}</span></div></div>"
        f"<div class='ms-src'>{html.escape(tr('ws.map_source', s=ctx.g.source))}</div>", unsafe_allow_html=True)


TOOLS = [("route", "analysis"), ("hazards", "layers"), ("science", "layers"), ("ai", "analysis"),
         ("integration", "analysis"), ("risk", "analysis"), ("oxygen", "analysis"), ("comm", "analysis"),
         ("simulation", "analysis"), ("terrain", "layers"), ("dem", "layers"), ("reports", "summary")]


def _tools(ctx):
    """The map is the workspace; every detailed module opens from here with the same mission state."""
    tr, ss = ctx.tr, st.session_state
    with _panel(tr("ws.tools"), "apps", "ms_p_tools"):
        st.caption(tr("ws.tools_sub"))
        cols = st.columns(4)
        for i, (mid, ws) in enumerate(TOOLS):
            if cols[i % 4].button(tr("mod." + mid), key=f"pl_tool_{mid}", icon=ui.ICON[mid], width="stretch"):
                ss.ws, ss.page = ws, mid
                st.query_params["ws"], st.query_params["page"] = ws, mid
                ss._qp_ws, ss._qp_page = ws, mid
                st.rerun()


def _fit_points(routes, active):
    ss = st.session_state
    pts = [tuple(ss.start), tuple(ss.goal)]
    r = routes.get(active)
    if r is not None and r.found:
        pts += list(zip(np.asarray(r.lat)[::10], np.asarray(r.lon)[::10]))
    return pts


def _strategy_table(ctx, out, routes):
    tr, ss = ctx.tr, st.session_state
    if not out or not out.get("table"):
        return
    rows = {r["strategy"]: r for r in out["table"]}
    cols = st.columns(len(STRATEGIES))
    for c, s in zip(cols, STRATEGIES):
        r = rows.get(s)
        ok = routes.get(s) is not None and routes[s].found and r is not None
        rec = s == out.get("recommended")
        with c:
            st.markdown(
                f"<div class='ms-strat{' on' if s == ss.strategy else ''}'><div class='t'>"
                f"<i style='background:{V.ROUTE_COLORS[s]}'></i>{html.escape(tr('strat.' + s))}"
                f"{'<span class=rec>' + html.escape(tr('ws.recommended')) + '</span>' if rec else ''}</div>"
                + (f"<div class='m'>{r['distance_3d_km']:.2f} km · {r['duration_h']:.2f} h</div>"
                   f"<div class='m'>{html.escape(tr('ws.hazard_idx'))} {r['hazard_mean']:.2f} · "
                   f"{html.escape(tr('ws.score'))} {r['score']:.2f}</div>" if ok else
                   f"<div class='m'>{html.escape(tr('route.none_found'))}</div>") + "</div>", unsafe_allow_html=True)
            if ok and s != ss.strategy and st.button(tr("ws.select"), key=f"pl_sel_{s}", width="stretch",
                                                     icon=":material/visibility:"):
                ss.strategy, ss._strategy_user = s, True
                st.rerun()


def _analysis(ctx, r, prof, out, targets):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    with _panel(tr("ws.analysis"), "monitoring", "ms_p_analysis", html.escape(tr("strat." + ss.strategy))):
        if r is None or prof is None:
            st.error(tr("alert.no_route"))
            return
        st.caption(tr("ws.analysis_sub"))
        dz = np.diff(np.asarray(r.elev, float))
        dz = dz[np.isfinite(dz)]
        gain, loss = float(dz[dz > 0].sum()), float(-dz[dz < 0].sum())
        c = st.columns(2)
        _card(c[0], tr("ws.k.distance"), f"{r.dist3d_m[-1] / 1000:.2f} km", tr("ws.k.distance_sub"))
        _card(c[1], tr("ws.k.time"), f"{prof['duration_h']:.2f} h",
              tr("ws.k.time_sub", p=f"{100 * prof['duration_h'] / mp.budget_h:.0f}", b=f"{mp.budget_h:g}"))
        c = st.columns(2)
        _card(c[0], tr("ws.k.gain"), f"+{gain:,.0f} m", tr("ws.k.gain_sub"))
        _card(c[1], tr("ws.k.loss"), f"−{loss:,.0f} m", tr("ws.k.loss_sub"))
        c = st.columns(2)
        if mp.scenario == "astronaut":
            left = 100 * (1 - prof["o2_total_l"] / mp.o2_capacity_l)
            _card(c[0], tr("ws.k.o2"), f"{left:.0f} %", f"{prof['o2_total_l']:.0f} / {mp.o2_capacity_l:.0f} L")
        else:
            left = 100 * (1 - prof["e_j"][-1] / 3600 / mp.rover.battery_wh)
            _card(c[0], tr("ws.k.battery"), f"{left:.0f} %", f"{prof['e_j'][-1] / 3600:.0f} / {mp.rover.battery_wh:.0f} Wh")
        tb = ss.get("turnback")
        _card(c[1], tr("ws.k.turnback"), f"{tb['min_margin_h']:+.2f} h" if tb else "—",
              tr("ws.k.turnback_ok") if tb and tb["feasible"] else tr("ws.k.turnback_bad") if tb else "")

    alerts = _alerts(ctx, r, prof, out)
    with _panel(tr("ws.alerts"), "warning", "ms_p_alerts", f"{len(alerts)}"):
        if not alerts:
            st.markdown(f"<div class='ms-al ok'>{html.escape(tr('ws.no_alerts'))}</div>", unsafe_allow_html=True)
        for lvl, text in alerts:
            st.markdown(f"<div class='ms-al {lvl}'>{html.escape(text)}</div>", unsafe_allow_html=True)

    with _panel(tr("ws.profile"), "show_chart", "ms_p_profile"):
        x = np.asarray(r.dist3d_m) / 1000
        el = np.asarray(r.elev, float)
        lo, hi = float(np.nanmin(el)), float(np.nanmax(el))
        pad = max(5.0, 0.15 * (hi - lo))
        fig = go.Figure(go.Scatter(x=x, y=np.full_like(el, lo - pad), line=dict(width=0), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=el, fill="tonexty", line=dict(color="#ff8a3d", width=2),
                                 fillcolor="rgba(255,138,61,.18)", hovertemplate="%{x:.2f} km · %{y:.0f} m<extra></extra>"))
        steep = np.asarray(r.slope_deg) > mp.slope_limit_deg * 0.8
        if steep.any():
            fig.add_trace(go.Scatter(x=x[steep], y=np.asarray(r.elev)[steep], mode="markers",
                                     marker=dict(color="#ef476f", size=5), name=tr("ws.steep"),
                                     hovertemplate="%{x:.2f} km<extra></extra>"))
        fig.update_layout(**{**ui.PLOTLY_LAYOUT, "margin": dict(l=6, r=6, t=6, b=6)}, height=170, showlegend=False,
                          xaxis_title=None, yaxis_title=None)
        fig.update_xaxes(ticksuffix=" km", gridcolor="rgba(255,255,255,.06)")
        fig.update_yaxes(ticksuffix=" m", gridcolor="rgba(255,255,255,.06)", range=[lo - pad, hi + pad])
        ui.plotly(fig, key="pl_profile")

    with _panel(tr("ws.insights"), "psychology", "ms_p_ai", html.escape(tr("ws.ai_badge"))):
        if not out or out.get("recommended") is None:
            st.caption(tr("route.none_found"))
        else:
            for k, kw in out["explanation"][:5]:
                if "s" in kw:
                    kw = {**kw, "s": tr("strat." + kw["s"])}
                if "s2" in kw:
                    kw = {**kw, "s2": tr("strat." + kw["s2"])}
                if "lv" in kw:
                    kw = {**kw, "lv": tr("lv." + kw["lv"]), "f": tr("rf." + kw["f"])}
                st.markdown(f"<div class='ms-ins'>{html.escape(tr(k, **kw))}</div>", unsafe_allow_html=True)
            if out["recommended"] != ss.strategy:
                if st.button(tr("ws.adopt", s=tr("strat." + out["recommended"])), key="pl_adopt", width="stretch"):
                    ss.strategy, ss._strategy_user = out["recommended"], False
                    st.rerun()
            st.caption(tr("ws.ai_note"))

    with _panel(tr("ws.summary"), "summarize", "ms_p_summary"):
        near = sorted(targets, key=lambda t: (t["lat"] - ss.goal[0]) ** 2 + (t["lon"] - ss.goal[1]) ** 2)[:1]
        risk = out.get("risk_overall") if out else None
        rows = [(tr("lbl.mission_name"), mp.name), (tr("ws.goal"), tr("ws.goal." + mp.scenario)),
                (tr("ws.route"), f"{tr('strat.' + ss.strategy)} · {r.dist3d_m[-1] / 1000:.2f} km"),
                (tr("ws.k.time"), f"{prof['duration_h']:.2f} h / {mp.budget_h:g} h"),
                (tr("ws.target"), near[0]["name"] if near else "—"),
                (tr("ws.overall_risk"), (tr("lv." + risk["level"]) + " · " + tr("rf." + risk["top_factor"])) if risk else "—"),
                (tr("ws.dem"), tr("ws.dem_real") if ctx.g.is_real else tr("ws.dem_synthetic"))]
        st.markdown("<table class='ms-kv'>" + "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(str(b))}</td></tr>"
                                                       for a, b in rows) + "</table>", unsafe_allow_html=True)

    with _panel(tr("ws.export"), "download", "ms_p_export"):
        st.caption(tr("ws.export_sub"))
        c1, c2 = st.columns(2)
        if c1.button(tr("ws.make_pdf"), key="pl_pdf", icon=":material/picture_as_pdf:", width="stretch"):
            from frontend.components import report_builder as RB
            from mars_survive.reporting import export
            rep = ui.run_safely(tr, RB.build, ctx, RB.SECTIONS)
            pdf = ui.run_safely(tr, export.to_pdf, rep) if rep else None
            if pdf:
                ss.pl_pdf = pdf
        if ss.get("pl_pdf"):
            c1.download_button(tr("ws.download_pdf"), ss.pl_pdf, f"mars_survive_360_{ctx.lang}.pdf", "application/pdf",
                               key="pl_pdf_dl", width="stretch", type="primary")
        import json
        c2.download_button("GeoJSON", json.dumps(V.route_geojson({ss.strategy: r})), f"route_{ss.strategy}.geojson",
                           "application/geo+json", key="pl_geojson", width="stretch", icon=":material/map:")


def _alerts(ctx, r, prof, out):
    tr, ss, mp = ctx.tr, st.session_state, ctx.mp
    al = []
    if not ctx.g.is_real:
        al.append(("warn", tr("ws.al.synthetic")))
    sl = np.asarray(r.slope_deg, float)
    n_steep = int(np.sum(sl > 0.8 * mp.slope_limit_deg))
    if n_steep:
        al.append(("warn", tr("ws.al.steep", n=n_steep, m=f"{np.nanmax(sl):.1f}", lim=f"{mp.slope_limit_deg:g}")))
    hz = np.asarray(r.hazard, float)
    hi = float(np.mean(hz >= 0.5)) if hz.size else 0.0
    if hi > 0:
        al.append(("bad" if hi > 0.1 else "warn", tr("ws.al.hazard", p=f"{100 * hi:.0f}")))
    if prof["duration_h"] > mp.budget_h * (1 - mp.reserve_frac):
        al.append(("bad", tr("alert.duration", h=f"{prof['duration_h']:.1f}")))
    if mp.scenario == "astronaut" and 100 * (1 - prof["o2_total_l"] / mp.o2_capacity_l) < 25:
        al.append(("bad", tr("alert.o2", p=f"{100 * (1 - prof['o2_total_l'] / mp.o2_capacity_l):.0f}")))
    tb = ss.get("turnback")
    if tb and not tb["feasible"]:
        al.append(("bad", tr("alert.turnback")))
    if out is not None and out.get("risk") is not None:
        rk = out["risk"]
        for _, row in rk[rk.level.isin(["high", "critical"])].head(2).iterrows():
            al.append(("warn", tr("ws.al.risk", f=tr("rf." + row["factor"]), lv=tr("lv." + row["level"]))))
    return al


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    targets = catalog.all_targets()
    ss.targets = targets
    left, centre, right = st.columns([1.05, 2.9, 1.45], gap="small")
    with left:
        on, gen = _setup(ctx, targets)
    out = _pipeline(ctx)
    routes = ui.run_safely(tr, state.ensure_routes, ctx, bool(gen)) or {}
    if gen:
        ss._strategy_user = False
        if out and out.get("recommended"):
            ss.strategy = out["recommended"]
    r, prof, _ = state.active(ctx) if routes else (None, None, [])
    ss.route = r
    ss.turnback = state.turnback(ctx) if r is not None else None
    with centre:
        _map(ctx, routes, ss.strategy, targets, on)
        _strategy_table(ctx, out, routes)
        _tools(ctx)
    with right:
        _analysis(ctx, r, prof, out, targets)
