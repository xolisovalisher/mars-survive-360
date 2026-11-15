"""21 Data Ingestion."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config as C
from frontend.components import state, ui
from mars_survive.common import DataClass, ModuleError
from mars_survive.dem.loader import build_grid_from_dem
from mars_survive.ingestion.importer import parse, store


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("ingest", tr, ["User Supplied"])
    st.caption(tr("ing.allowed", e=", ".join(sorted(C.ALLOWED_UPLOAD_EXT)), m=C.MAX_UPLOAD_MB))
    ups = st.file_uploader(tr("ing.files"), accept_multiple_files=True,
                           type=[e.lstrip(".") for e in C.ALLOWED_UPLOAD_EXT])
    results = ss.setdefault("ingest_results", [])
    if ups and st.button(tr("btn.validate_import"), type="primary"):
        results.clear()
        for u in ups:
            data = u.getvalue()
            try:
                info = parse(u.name, data)
                path = store(info, data)
                info["stored"] = str(path.relative_to(C.ROOT))
            except ModuleError as e:
                info = {"name": u.name, "valid": False, "errors": [f"{tr(e.key)} {e.detail}"], "size_bytes": len(data)}
            results.append(info)
    if not results:
        st.info(tr("ing.hint"))
    else:
        df = pd.DataFrame([{"file": r.get("name"), "format": r.get("format"), "size_kb": round(r.get("size_bytes", 0) / 1024, 1),
                            "crs": r.get("crs"), "units": r.get("units"), "valid": "✓" if r.get("valid") else "✗",
                            "errors": "; ".join(r.get("errors", [])), "sha256": (r.get("sha256") or "")[:16]} for r in results])
        ui.df_show(ui.tr_cols(df, tr))
        for r in results:
            with st.expander(f"{r.get('name')} — {tr('ing.metadata')}"):
                st.json(r.get("metadata", {}))
                if r.get("valid") and r.get("format") == "GeoTIFF" and st.button(tr("btn.use_dem"), key=f"use_{r['name']}"):
                    res = ui.run_safely(tr, build_grid_from_dem, C.ROOT / r["stored"], data_class=DataClass.USER)
                    if res:
                        state.reset_engine()
                        st.success(tr("dem.processed", v=f"{res[1]['quality']['valid_fraction'] * 100:.1f}"))
        ui.export_buttons(tr, "ingestion_log", df)
    ui.footer("ingest", tr, "whitelist ext + size ≤ limit + magic bytes; safe file names (no path traversal);\n"
                            "XML via defusedxml (no entities/DTD); GeoTIFF via rasterio MemoryFile; JSON/GeoJSON schema check",
              ["user files → data/uploads + provenance registry (class: User Supplied)"])
