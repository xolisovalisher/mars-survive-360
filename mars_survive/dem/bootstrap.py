"""Real-terrain bootstrap: on the first start the app fetches the USGS Mars 2020
CTX DEM of Jezero crater (20 m/pixel, Calef et al. 2021, USGS Astrogeology) and
turns it into the 50 m analysis grid, so judges and users see REAL Mars
elevation without any manual step.

How: GDAL reads the remote GeoTIFF over HTTP range requests (/vsicurl/), so only
the blocks covering the analysis window are transferred. If range reads are not
possible, the whole 87 MB file is downloaded once (resumable) and processed.
The result (data/processed/jezero_dem.npz, < 1 MB) is reused on every later start.
Nothing is ever reported as REAL unless the pixels really came from the USGS file
and passed the quality check; on any failure the app keeps the labelled
SYNTHETIC relief and says why.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import config as C
from mars_survive.common import DataClass, get_logger

from .loader import PROCESSED_NPZ, build_grid_from_dem, download

log = get_logger("dem.bootstrap")
STATUS = C.DATA_PROCESSED / "real_dem_status.json"
RETRY_AFTER_S = 6 * 3600          # after a failure, do not retry on every page load
SOURCES = (C.CTX_DTM_URL, C.CTX_DTM_MIRROR_URL)
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
                GDAL_HTTP_TIMEOUT="30", GDAL_HTTP_MAX_RETRY="2", GDAL_HTTP_RETRY_DELAY="1", VSI_CACHE="TRUE")


def status() -> dict:
    try:
        return json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(d: dict):
    try:
        STATUS.parent.mkdir(parents=True, exist_ok=True)
        STATUS.write_text(json.dumps(d, indent=1), encoding="utf-8")
    except OSError:
        pass


def _ca_bundle() -> dict:
    """GDAL's curl needs a CA file on some Linux hosts (e.g. Streamlit Community Cloud)."""
    import os
    for k in ("CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        if os.environ.get(k):
            return {"CURL_CA_BUNDLE": os.environ[k]}
    try:
        import certifi
        return {"CURL_CA_BUNDLE": certifi.where()}
    except ImportError:
        return {}


def _from_remote(url: str):
    import rasterio
    with rasterio.Env(**GDAL_ENV, **_ca_bundle()):
        g, meta = build_grid_from_dem("/vsicurl/" + url, data_class=DataClass.REAL, save=False)
    return g, meta


def _from_download(url: str, progress=None):
    dest = C.DATA_RAW / Path(url).name
    download(url, dest, progress=progress, timeout=60)
    return build_grid_from_dem(dest, data_class=DataClass.REAL, save=False)


def ensure_real_dem(force: bool = False, sources=SOURCES, progress=None) -> dict:
    """Make sure a REAL processed DEM exists. Returns a status dict
    {"state": "ready"|"fetched"|"failed"|"skipped", ...}. Never raises."""
    if PROCESSED_NPZ.exists() and not force:
        return {"state": "ready"}
    if C.BROWSER or not C.AUTO_REAL_DEM:
        return {"state": "skipped", "reason": "browser" if C.BROWSER else "disabled"}
    st = status()
    if not force and st.get("state") == "failed" and time.time() - st.get("time", 0) < RETRY_AFTER_S:
        return {"state": "skipped", "reason": "recent_failure", "errors": st.get("errors", [])}
    errors = []
    t0 = time.time()
    for url in sources:
        for how, fn in (("range", _from_remote), ("download", _from_download)):
            try:
                g, meta = fn(url) if how == "range" else fn(url, progress)
            except Exception as e:  # noqa: BLE001 - every failure is reported, never hidden
                errors.append(f"{how} {url.split('/')[2]}: {e.__class__.__name__}: {str(e)[:160]}")
                log.warning("real DEM %s via %s failed: %s", url, how, e)
                continue
            g.source = f"USGS Mars 2020 CTX DEM, Jezero crater, 20 m (Calef et al. 2021) — resampled to {C.ANALYSIS_RES_M:.0f} m"
            g.meta.update({"url": url, "access": how, "fetched_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())})
            from .loader import save_grid
            save_grid(g, PROCESSED_NPZ)
            d = {"state": "fetched", "url": url, "access": how, "seconds": round(time.time() - t0, 1),
                 "quality": meta.get("quality", {}), "time": time.time()}
            _write_status(d)
            log.info("real DEM ready from %s (%s) in %.1f s", url, how, d["seconds"])
            return d
    d = {"state": "failed", "errors": errors, "time": time.time()}
    _write_status(d)
    return d
