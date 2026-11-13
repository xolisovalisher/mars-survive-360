"""23 Mission Reports."""
from __future__ import annotations

import streamlit as st
import base64

from frontend.components import report_builder as RB
from frontend.components import ui
from mars_survive.reporting import export


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("reports", tr, [ctx.g.data_class])
    with ui.params(tr):
        secs = st.multiselect(tr("rep.sections"), RB.SECTIONS[1:], default=RB.SECTIONS[1:],
                              format_func=lambda s: tr("rep.s." + s))
        fmts = st.multiselect(tr("rep.formats"), ["pdf", "html", "csv", "json", "xlsx"], default=["pdf", "html", "csv", "json", "xlsx"])
    if st.button("📄 " + tr("btn.generate_report"), type="primary") or "report" not in ss or ss.get("report_lang") != ctx.lang:
        rep = ui.run_safely(tr, RB.build, ctx, ["mission"] + secs)
        if rep:
            files = {}
            for f in fmts:
                fn = {"pdf": export.to_pdf, "html": export.to_html, "csv": export.to_csv, "json": export.to_json,
                      "xlsx": export.to_excel}[f]
                b = ui.run_safely(tr, fn, rep)
                if b:
                    files[f] = b
            ss.report, ss.report_files, ss.report_lang = rep, files, ctx.lang
    files = ss.get("report_files", {})
    if files:
        st.success(tr("rep.ready", n=len(files), s=len(ss.report["sections"])))
        mime = {"pdf": "application/pdf", "html": "text/html", "csv": "text/csv", "json": "application/json",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        cols = st.columns(len(files))
        for c, (f, b) in zip(cols, files.items()):
            sz = f"{len(b) / 1024:.0f} KB" if len(b) >= 1024 else f"{len(b)} B"
            c.download_button(f"⬇️ {f.upper()} ({sz})", b, f"mars_survive_report_{ctx.lang}.{f}", mime[f],
                              width="stretch", key=f"rep_{f}")
    _gis(ctx)
    if files:
        if "html" in files:
            ui.section(tr("rep.preview"))
            st.iframe("data:text/html;base64," + base64.b64encode(files["html"]).decode(), height=650)
    ui.footer("reports", tr, "PDF: fpdf2 + Unicode TTF fonts (DejaVu, Noto Arabic/Devanagari, system CJK) with HarfBuzz shaping\n"
                             "HTML: every value escaped; CSV/Excel/JSON: same content in tabular form",
              ["all modules' current results", "fonts: DejaVu (free licence), Noto (SIL OFL 1.1)"])


def _gis(ctx):
    """GeoPackage / GeoJSON of the mission layers in the Mars CRS IAU_2015:49900."""
    from mars_survive.reporting import gis
    from mars_survive.science import catalog as cat
    tr, ss = ctx.tr, st.session_state
    ui.section("🗺️ " + tr("rep.gis"))
    if not gis.available():
        st.caption(tr("rep.gis_missing"))
        return
    routes = ss.get("routes") or {}
    haz = [o for o in (ctx.eng.H.objects or []) if "lat" in o][:500]
    layers = ui.run_safely(tr, gis.mission_layers, routes, cat.all_targets(), haz, ss.get("m20_trav"),
                           getattr(ctx.g.data_class, "value", str(ctx.g.data_class)))
    if not layers:
        return
    st.caption(tr("rep.gis_note", crs=gis.MARS_CRS, n=len(layers), l=", ".join(layers)))
    c1, c2 = st.columns(2)
    gp = ui.run_safely(tr, gis.to_geopackage, layers)
    if gp:
        c1.download_button("⬇️ GeoPackage (.gpkg)", gp, "mars_survive_mission.gpkg", "application/geopackage+sqlite3",
                           width="stretch", key="rep_gpkg")
    gj = ui.run_safely(tr, gis.to_geojson, layers)
    if gj:
        c2.download_button("⬇️ GeoJSON", gj, "mars_survive_mission.geojson", "application/geo+json",
                           width="stretch", key="rep_gjson")
