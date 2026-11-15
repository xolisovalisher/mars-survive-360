"""01 Mission Dashboard."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive import storage
from mars_survive.communication.link import PRESETS, link_budget
from mars_survive.dashboard.kpis import kpis
from mars_survive.integration.mission import MissionParams
from mars_survive.navigation import ekf as nav
from mars_survive.navigation.metrics import summarize
from mars_survive.science import catalog


def _quick_nav(ctx, r):
    ss = st.session_state
    if ss.get("nav_key") == ss.get("routes_key") and ss.get("nav_summary"):
        return ss.nav_summary
    x, y = state.grid_xy(ctx, r.lat, r.lon)
    spd = ctx.mp.rover.speed_ms if ctx.mp.scenario == "rover" else ctx.mp.astronaut.v_flat_ms
    dt = max(1.0, 5.0 / spd)
    pose, v, w = nav.path_to_controls(x, y, spd, dt)
    sim = nav.simulate(pose, v, w, nav.landmarks_along(pose), nav.NavParams(dt=dt))
    ss.nav_summary, ss.nav_key = summarize(sim), ss.get("routes_key")
    return ss.nav_summary


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("dashboard", tr, [ctx.g.data_class])
    if not ctx.g.is_real:
        st.warning(tr("msg.synthetic_dem"))

    # ---------------- mission management
    tab_status, tab_new, tab_list = st.tabs([tr("dash.status"), tr("dash.new_mission"),
                                             tr("dash.missions")])
    with tab_new:
        with st.form("new_mission"):
            c1, c2 = st.columns(2)
            name = c1.text_input(tr("lbl.mission_name"), value=ctx.mp.name, max_chars=120)
            scen = c2.selectbox(tr("lbl.scenario"), ["astronaut", "rover"], format_func=lambda s: tr("scen." + s),
                                index=0 if ctx.mp.scenario == "astronaut" else 1)
            desc = st.text_area(tr("lbl.description"), max_chars=2000, value=tr("dash.default_desc"))
            c3, c4, c5 = st.columns(3)
            dur = c3.number_input(tr("lbl.duration_h"), 1.0, 200.0, float(ctx.mp.budget_h), 0.5)
            o2 = c4.number_input(tr("lbl.o2_capacity_l"), 100.0, 5000.0, float(ctx.mp.o2_capacity_l), 50.0)
            bat = c5.number_input(tr("lbl.battery_wh"), 100.0, 20000.0, float(ctx.mp.rover.battery_wh), 100.0)
            c6, c7 = st.columns(2)
            res = c6.slider(tr("lbl.reserve_pct"), 0, 50, int(ctx.mp.reserve_frac * 100), 5)
            sl = c7.slider(tr("lbl.slope_limit"), 5, 35, int(ctx.mp.slope_limit_deg))
            st.text_input(tr("lbl.region"), tr("region.jezero"), disabled=True)
            if st.form_submit_button(tr("btn.create_mission"), type="primary"):
                mp = MissionParams.from_dict({**ctx.mp.to_dict(), "name": name.strip() or ctx.mp.name,
                                              "scenario": scen, "budget_h": dur, "o2_capacity_l": o2,
                                              "reserve_frac": res / 100, "slope_limit_deg": float(sl)})
                mp.rover.battery_wh = bat
                try:
                    mid = storage.create_mission(mp.name, desc, "Jezero Crater", scen, dur, mp.to_dict())
                    ss.mp, ss.mission_id = mp, mid
                    ss.pop("routes_key", None)
                    st.success(tr("msg.mission_saved", id=mid))
                except ValueError:
                    st.error(tr("err.empty_name"))
    with tab_list:
        ms = storage.list_missions()
        if not ms:
            st.info(tr("msg.no_missions"))
        else:
            df = pd.DataFrame([{k: m[k] for k in ("id", "name", "scenario", "duration_h", "status", "updated")} for m in ms])
            ui.df_show(ui.tr_cols(df, tr))
            c1, c2, c3 = st.columns([2, 1, 1])
            sel = c1.selectbox(tr("lbl.select_mission"), [m["id"] for m in ms],
                               format_func=lambda i: next(f"#{m['id']} {m['name']}" for m in ms if m["id"] == i))
            if c2.button(tr("btn.activate"), width="stretch"):
                m = next(x for x in ms if x["id"] == sel)
                ss.mp, ss.mission_id = MissionParams.from_dict(m["params"]), sel
                storage.update_mission(sel, status="active")
                ss.pop("routes_key", None)
                st.rerun()
            stt = c3.selectbox(tr("lbl.status"), ["planning", "active", "completed", "aborted"],
                               format_func=lambda s: tr("mstatus." + s))
            if c3.button(tr("btn.update_status"), width="stretch"):
                storage.update_mission(sel, status=stt)
                st.rerun()

    with tab_status:
        r, prof, cuts = state.active(ctx)
        nav_s = _quick_nav(ctx, r) if r is not None else None
        if "link_result" not in ss:
            ss.link_result = link_budget(PRESETS["uhf_orbiter"])
        tgts = catalog.all_targets()
        ss.targets = tgts
        ss.hazard_objects = ctx.eng.H.objects
        ss.route = r
        ss.turnback = state.turnback(ctx)
        k = kpis(ss)
        c = st.columns(4)
        ui.card(c[0], tr("kpi.active_route"), tr("strat." + ss.strategy) if r else "—", tr("kpi.from_route_module"))
        ui.card(c[1], tr("kpi.distance"), f"{k['distance_km']:.2f} km" if k["distance_km"] else "—", tr("lbl.dist3d"))
        ui.card(c[2], tr("kpi.duration"), f"{k['duration_h']:.2f} h" if k["duration_h"] else "—",
                tr("kpi.of_budget", b=f"{ctx.mp.budget_h:.1f}"))
        if ctx.mp.scenario == "astronaut":
            ui.card(c[3], tr("kpi.o2_reserve"), f"{k['o2_remaining_pct']:.0f} %" if k["o2_remaining_pct"] is not None else "—",
                    f"{prof['o2_total_l']:.0f} / {ctx.mp.o2_capacity_l:.0f} L" if prof else "")
        else:
            ui.card(c[3], tr("kpi.energy_reserve"),
                    f"{k['energy_remaining_pct']:.0f} %" if k["energy_remaining_pct"] is not None else "—",
                    f"{prof['e_j'][-1] / 3600:.0f} / {ctx.mp.rover.battery_wh:.0f} Wh" if prof else "")
        c = st.columns(4)
        ui.card(c[0], tr("kpi.energy"), f"{k['energy_kwh']:.2f} kWh" if k["energy_kwh"] else "—",
                tr("kpi.metabolic") if ctx.mp.scenario == "astronaut" else tr("kpi.electric"))
        ui.card(c[1], tr("kpi.nav_accuracy"), f"± {nav_s['ekf']['position_sigma_final_m']:.1f} m" if nav_s else "—",
                tr("kpi.ekf_sim"))
        ui.card(c[2], tr("kpi.comm"), tr("status." + ss.link_result["status"]),
                f"{tr('lbl.margin')}: {ss.link_result['margin_db']:.1f} dB")
        ui.card(c[3], tr("kpi.hazards_targets"), f"{k['hazards']} / {k['targets']}", tr("kpi.hazard_objects"))

        st.markdown("")
        left, right = st.columns([3, 2])
        with left:
            maps.mission_map(ctx, routes={ss.strategy: r} if r else {}, active=ss.strategy, targets=tgts,
                             height=430, key="dash_map")
        with right:
            ui.section(tr("dash.alerts"))
            alerts = list(k["alerts"])
            if not ctx.g.is_real:
                alerts.insert(0, ("alert.synthetic", {}))
            if r is None:
                alerts.append(("alert.no_route", {}))
            if not alerts:
                st.success(tr("dash.no_alerts"))
            for key, kw in alerts:
                st.warning(tr(key, **kw))
            if ss.turnback:
                if ss.turnback["feasible"]:
                    st.success(tr("expl.turnback_ok", m=f"{ss.turnback['min_margin_h']:.2f}"))
                else:
                    st.error(tr("expl.turnback_bad", m=f"{ss.turnback['min_margin_h']:.2f}"))
            ui.section(tr("dash.targets"))
            ui.df_show(ui.tr_cols(pd.DataFrame([{"name": t["name"], "origin": tr("origin." + t["origin"]),
                                                  "priority": t["priority"]} for t in tgts]), tr), height=180)
        if prof:
            ui.export_buttons(tr, "dashboard_kpis", pd.DataFrame([{kk: v for kk, v in k.items()
                                                                   if kk not in ("alerts", "sources")}]))
    ui.footer("dashboard", tr, "KPI = values computed by modules 05, 08/09, 10, 15/16 for the active route",
              ["SQLite missions table (data/mars_survive.sqlite3)", "routing / oxygen / energy / EKF / link-budget modules"])
