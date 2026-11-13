"""04 DEM Data Management."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config as C
from frontend.components import state, ui
from mars_survive.common import DataClass, ModuleError
from mars_survive.dem import loader
from mars_survive.ingestion.importer import safe_name, validate


def _use_dem(ctx, path, dc):
    g, meta = loader.build_grid_from_dem(path, data_class=dc)
    state.reset_engine()
    return meta


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    g = ctx.g
    ui.header("dem", tr, [g.data_class])
    if g.is_real:
        st.success(tr("dem.active_real", src=g.source))
    else:
        st.warning(tr("msg.synthetic_dem"))
    c = st.columns(5)
    c[0].metric(tr("lbl.grid"), f"{g.shape[0]} × {g.shape[1]}")
    c[1].metric(tr("lbl.cell"), f"{g.dy:.1f} m")
    (s, w), (n, e) = g.bounds
    c[2].metric(tr("lbl.lat_range"), f"{s:.2f}…{n:.2f}°")
    c[3].metric(tr("lbl.lon_range"), f"{w:.2f}…{e:.2f}°")
    c[4].metric(tr("lbl.data_class"), tr("dc." + {"Real": "real", "Synthetic": "synthetic", "Simulated": "simulated",
                                                 "User Supplied": "user"}[g.data_class.value]))
    q = loader.quality_report(g.z)
    meta = {**{k: v for k, v in g.meta.items() if k not in ("dem_info", "quality")}, **q}
    with st.expander(tr("dem.current_meta")):
        st.json(meta)
        if g.meta.get("dem_info"):
            st.json(g.meta["dem_info"])

    t1, t2, t3, t4 = st.tabs(["🌐 " + tr("dem.download"), "📁 " + tr("dem.local"), "⬆️ " + tr("dem.upload"),
                              "🏷️ " + tr("dem.label")])
    with t1:
        st.markdown(tr("dem.download_text"))
        st.code(C.CTX_DTM_URL)
        st.caption(tr("dem.catalog") + ": " + C.CTX_DTM_CATALOG)
        if st.button("⬇️ " + tr("btn.download_dem"), type="primary"):
            dest = C.DATA_RAW / "M20_JezeroCrater_CTXDEM_20m.tif"
            bar = st.progress(0.0, text=tr("ui.computing"))

            def prog(done, total):
                bar.progress(min(done / total, 1.0) if total else 0.0, text=f"{done / 1e6:.1f} / {total / 1e6:.1f} MB")
            try:
                res = loader.download(C.CTX_DTM_URL, dest, progress=prog)
                st.success(tr("dem.downloaded", mb=f"{res['bytes'] / 1e6:.1f}"))
                try:
                    xml = loader.download(C.CTX_DTM_XML_URL, C.DATA_RAW / "M20_JezeroCrater_CTXDEM_20m.xml")
                    st.caption(f"XML: {xml['path']}")
                except ModuleError as e:
                    st.caption(f"XML: {tr(e.key)} {e.detail}")
                meta = ui.run_safely(tr, _use_dem, ctx, dest, DataClass.REAL)
                if meta:
                    st.success(tr("dem.processed", v=f"{meta['quality']['valid_fraction'] * 100:.1f}"))
                    st.rerun()
            except ModuleError as e:
                st.error(f"{tr(e.key)} — {e.detail}")
                st.info(tr("dem.offline_hint"))
    with t2:
        path = st.text_input(tr("dem.local_path"), value=ss.settings.dem_path or str(C.DATA_RAW / "M20_JezeroCrater_CTXDEM_20m.tif"))
        c1, c2 = st.columns(2)
        if c1.button("🔍 " + tr("btn.inspect")):
            info = ui.run_safely(tr, loader.inspect_geotiff, path)
            if info:
                st.json(info)
                (st.success if info["crs_is_mars"] else st.warning)(tr("dem.crs_ok") if info["crs_is_mars"] else tr("dem.crs_warn"))
        if c2.button("✅ " + tr("btn.use_dem"), type="primary"):
            meta = ui.run_safely(tr, _use_dem, ctx, path, DataClass.REAL)
            if meta:
                st.rerun()
    with t3:
        up = st.file_uploader(tr("dem.upload_tif"), type=["tif", "tiff"])
        cls = st.radio(tr("lbl.data_class"), ["user", "real"], format_func=lambda x: tr("dc." + x), horizontal=True)
        if up is not None and st.button("✅ " + tr("btn.use_dem")):
            try:
                info = validate(up.name, up.getvalue())
                dest = C.DATA_UPLOADS / safe_name(up.name)
                dest.write_bytes(up.getvalue())
                meta = ui.run_safely(tr, _use_dem, ctx, dest, DataClass.USER if cls == "user" else DataClass.REAL)
                if meta:
                    st.success(tr("dem.processed", v=f"{meta['quality']['valid_fraction'] * 100:.1f}"))
                    st.rerun()
            except ModuleError as e:
                st.error(f"{tr(e.key)} — {e.detail}")
        if loader.PROCESSED_NPZ.exists() and st.button("↩️ " + tr("btn.revert_synthetic")):
            loader.PROCESSED_NPZ.rename(loader.PROCESSED_NPZ.with_suffix(".npz.bak"))
            state.reset_engine()
            st.rerun()
    with t4:
        upx = st.file_uploader(tr("dem.upload_xml"), type=["xml"])
        lp = C.DATA_RAW / "M20_JezeroCrater_CTXDEM_20m.xml"
        lab = None
        if upx is not None:
            lab = ui.run_safely(tr, loader.parse_label_xml, upx.getvalue()[:5_000_000])
        elif lp.exists():
            lab = ui.run_safely(tr, loader.parse_label_xml, str(lp))
        if lab:
            st.write(tr("dem.label_type", t=lab["root"], p=tr("ui.yes") if lab["is_pds4"] else tr("ui.no")))
            ui.df_show(pd.DataFrame([{"field": k, "value": v} for k, v in lab["fields"].items()]))
        else:
            st.info(tr("dem.no_label"))
    ui.footer("dem", tr, "rasterio.warp.reproject(window → lat/lon grid on sphere R=3396190 m, Resampling.average)\n"
                         "QC: valid fraction, NoData, >200 m jumps between 50 m cells, plausible Mars range -8.5..22 km",
              ["USGS Astrogeology: Mars 2020 Science Investigation CTX DEM Mosaic (20 m)", C.CTX_DTM_CATALOG])
