"""Entry point of the one-file browser build (stlite / Pyodide). Not used by the desktop app.

Pyodide downloads every Python package over the network, so the big ones that only a few pages
need (OpenCV, GDAL/rasterio, PROJ, GeoPandas, Shapely, Astropy — about half of all the download)
are installed the first time such a page is opened, not at start-up. Then app.py runs as usual.
"""
import importlib.util
import runpy
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent

# page id -> (import name, Pyodide package name)
_OPENCV = ("cv2", "opencv-python")
_RASTERIO = ("rasterio", "rasterio")
_GIS = [("shapely", "shapely"), ("pyproj", "pyproj"), ("geopandas", "geopandas")]
_ASTROPY = ("astropy", "astropy")
PAGE_PACKAGES = {
    "ai": [_OPENCV],
    "dem": [_RASTERIO],
    "ingest": [_RASTERIO],
    "terrain": [_RASTERIO],
    "reports": _GIS,
    "science": [("shapely", "shapely")],
    "spice": [_ASTROPY],
    "diagnostics": [_OPENCV, _RASTERIO, _ASTROPY] + _GIS,
}

_page = st.session_state.get("page") or st.query_params.get("page") or "dashboard"
if "page" in st.query_params and st.session_state.get("_qp_page") != st.query_params["page"]:
    _page = st.query_params["page"]
_missing = [pkg for mod, pkg in PAGE_PACKAGES.get(_page, []) if importlib.util.find_spec(mod) is None]
if _missing:
    import micropip
    with st.spinner("⏳ " + ", ".join(_missing) + " …"):
        await micropip.install(_missing)  # noqa: F704 - stlite runs this script with top-level await
    importlib.invalidate_caches()

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
