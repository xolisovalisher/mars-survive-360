"""25 User Settings & Configuration."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import streamlit as st

import config as C
from frontend.components import ui
from mars_survive.localization.i18n import LANGUAGES
from mars_survive.settings import store


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("settings", tr)
    s = ss.settings
    with st.form("settings_form"):
        c = st.columns(4)
        lang = c[0].selectbox(tr("top.language"), list(LANGUAGES), index=list(LANGUAGES).index(ctx.lang),
                              format_func=lambda x: LANGUAGES[x][0])
        theme = c[1].selectbox(tr("set.theme"), ["dark", "light"], index=["dark", "light"].index(s.theme),
                               format_func=lambda x: tr("theme." + x))
        du = c[2].selectbox(tr("set.distance_unit"), ["km", "mi"], index=["km", "mi"].index(s.distance_unit))
        tu = c[3].selectbox(tr("set.temp_unit"), ["C", "K"], index=["C", "K"].index(s.temperature_unit))
        c = st.columns(2)
        bm = c[0].selectbox(tr("set.basemap"), list(C.TREK_LAYERS), index=list(C.TREK_LAYERS).index(s.map_basemap)
                            if s.map_basemap in C.TREK_LAYERS else 0)
        zm = c[1].slider(tr("set.zoom"), 8, 14, int(s.map_zoom))
        st.markdown("**" + tr("set.paths") + "**")
        c = st.columns(2)
        dem = c[0].text_input(tr("set.dem_path"), s.dem_path)
        ai = c[1].text_input(tr("set.ai_path"), s.ai_model_path)
        c = st.columns(2)
        sp = c[0].text_input(tr("set.spice_dir"), s.spice_dir)
        dd = c[1].text_input(tr("set.data_dir"), s.data_dir)
        st.markdown("**" + tr("set.mission_defaults") + "**")
        c = st.columns(2)
        bh = c[0].number_input(tr("lbl.duration_h"), 1.0, 200.0, float(s.default_budget_h), 0.5)
        sl = c[1].number_input(tr("lbl.slope_limit"), 5.0, 35.0, float(s.default_slope_limit), 1.0)
        if st.form_submit_button("💾 " + tr("btn.save_settings"), type="primary"):
            errs = [p for p in (dem,) if p and not Path(p).exists()]
            new = store.Settings(language=lang, theme=theme, distance_unit=du, temperature_unit=tu, map_basemap=bm, map_zoom=zm,
                                 dem_path=dem, ai_model_path=ai, spice_dir=sp, data_dir=dd, default_budget_h=bh,
                                 default_slope_limit=sl)
            store.save(new)
            ss.settings, ss.lang = new, lang
            st.query_params["lang"] = lang
            ss._qp_lang = lang
            if errs:
                st.warning(tr("set.path_missing", p=", ".join(errs)))
            st.success(tr("set.saved"))
            st.rerun()
    st.markdown("**" + tr("set.current") + "**")
    st.json(asdict(s))
    c = st.columns(2)
    c[0].metric(tr("set.example_distance"), store.fmt_dist(12345.0, s.distance_unit))
    c[1].metric(tr("set.example_temp"), store.fmt_temp(-63.0, s.temperature_unit))
    ui.export_buttons(tr, "settings", obj=asdict(s))
    ui.footer("settings", tr, "settings persisted to data/settings.json (UTF-8); secrets only via .env, never stored here",
              ["data/settings.json", ".env (API keys)"])
