"""Real DEM handling: metadata inspection, window re-projection, quality checks,
PDS4/XML labels, processed-grid cache, resumable download.

Large rasters are never read fully: only the window covering the analysis box
is warped (GDAL reads just the needed blocks).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

import config as C
from mars_survive.common import DataClass, ModuleError, get_logger

from .grid import Grid

log = get_logger("dem")
PROCESSED_NPZ = C.DATA_PROCESSED / "jezero_dem.npz"
MARS_GEO_PROJ4 = f"+proj=longlat +R={C.R_MARS_DTM} +no_defs"


# ---------------------------------------------------------------- metadata
def inspect_geotiff(path: str | Path) -> dict:
    """Read header-level metadata only (no pixel data)."""
    import rasterio
    try:
        with rasterio.open(str(path)) as src:
            crs = src.crs
            info = {
                "file": Path(str(path)).name,
                "driver": src.driver,
                "width": src.width, "height": src.height, "bands": src.count,
                "dtype": src.dtypes[0],
                "crs": crs.to_string() if crs else None,
                "crs_is_mars": bool(crs and ("3396190" in crs.to_wkt() or "Mars" in crs.to_wkt()
                                             or "3389500" in crs.to_wkt())),
                "pixel_size": [abs(src.res[0]), abs(src.res[1])],
                "units_horizontal": (crs.linear_units if crs and crs.is_projected else "degree") if crs else None,
                "units_vertical": src.units[0] if src.units and src.units[0] else "m (assumed, not in header)",
                "nodata": src.nodata,
                "bounds": list(src.bounds),
                "transform": list(src.transform)[:6],
                "tiled": bool(src.profile.get("tiled", False)),
                "overviews": src.overviews(1),
                "tags": dict(list(src.tags().items())[:20]),
            }
            info["size_mb"] = round(Path(str(path)).stat().st_size / 1e6, 2) if Path(str(path)).exists() else None
            return info
    except Exception as e:  # noqa: BLE001
        raise ModuleError("err.dem_open", str(e)) from e


def parse_label_xml(path_or_bytes) -> dict:
    """Safely parse a PDS4 / ISO XML label (defusedxml: no entity expansion, no external refs)."""
    from defusedxml import ElementTree as ET
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            root = ET.fromstring(path_or_bytes)
        else:
            root = ET.parse(str(path_or_bytes)).getroot()
    except Exception as e:  # noqa: BLE001
        raise ModuleError("err.xml_parse", str(e)) from e

    def local(tag):
        return tag.split("}", 1)[-1]

    out = {"root": local(root.tag), "is_pds4": local(root.tag).startswith("Product_"), "fields": {}}
    wanted = {"title", "logical_identifier", "version_id", "start_date_time", "stop_date_time",
              "target_name", "a_axis_radius", "b_axis_radius", "c_axis_radius", "map_projection_name",
              "pixel_resolution_x", "pixel_resolution_y", "unit", "missing_constant", "westernmost_longitude",
              "easternmost_longitude", "northernmost_latitude", "southernmost_latitude", "longitude_direction",
              "latitude_type", "abstract", "resTitle", "westBL", "eastBL", "northBL", "southBL"}
    for el in root.iter():
        name = local(el.tag)
        if name in wanted and el.text and el.text.strip():
            out["fields"].setdefault(name, el.text.strip()[:300])
    return out


# ---------------------------------------------------------------- re-projection
def target_grid_spec(lat_c: float, lon_c: float, half: float, res_m: float) -> dict:
    dlat = math.degrees(res_m / C.R_MARS_DTM)
    dlon = dlat / math.cos(math.radians(lat_c))
    h = int(round(2 * half / dlat))
    w = int(round(2 * half / dlon * math.cos(math.radians(lat_c))))
    lat_top = lat_c + half - dlat / 2
    lon_left = lon_c - (w / 2) * dlon + dlon / 2
    return dict(h=h, w=w, lat_top=lat_top, lon_left=lon_left, dlat=dlat, dlon=dlon)


def warp_window(src_path: str, spec: dict, resampling: str = "average") -> np.ndarray:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject
    tr = from_origin(spec["lon_left"] - spec["dlon"] / 2, spec["lat_top"] + spec["dlat"] / 2,
                     spec["dlon"], spec["dlat"])
    out = np.full((spec["h"], spec["w"]), np.nan, np.float32)
    with rasterio.open(src_path) as src:
        reproject(rasterio.band(src, 1), out, src_nodata=src.nodata, dst_nodata=np.nan,
                  dst_transform=tr, dst_crs=CRS.from_proj4(MARS_GEO_PROJ4),
                  resampling=getattr(Resampling, resampling))
    return out


def build_grid_from_dem(path: str | Path, lat: float = C.JEZERO_CENTER[0], lon: float = C.JEZERO_CENTER[1],
                        half: float = C.CROP_HALF_DEG, res_m: float = C.ANALYSIS_RES_M,
                        data_class: DataClass = DataClass.REAL, save: bool = True) -> tuple[Grid, dict]:
    info = inspect_geotiff(path)
    spec = target_grid_spec(lat, lon, half, res_m)
    z = warp_window(str(path), spec, "average")
    z[(z < -9000) | (z > 25000)] = np.nan
    q = quality_report(z)
    if q["valid_fraction"] < 0.05:
        raise ModuleError("err.dem_no_coverage", f"valid={q['valid_fraction']:.3f}")
    meta = {"dem_info": info, "quality": q, "center": [lat, lon], "half_deg": half,
            "resolution_m": res_m, "crs": MARS_GEO_PROJ4}
    g = Grid(z=z, lat_top=spec["lat_top"], lon_left=spec["lon_left"], dlat=spec["dlat"], dlon=spec["dlon"],
             source=f"{info['file']} (resampled to {res_m:.0f} m)", data_class=data_class, meta=meta)
    if save:
        save_grid(g)
    log.info("DEM processed from %s: %s valid=%.3f", path, z.shape, q["valid_fraction"])
    return g, meta


def quality_report(z: np.ndarray) -> dict:
    v = np.isfinite(z)
    d = {"valid_fraction": float(v.mean()), "nodata_cells": int((~v).sum()), "cells": int(z.size)}
    if v.any():
        zz = z[v]
        d.update(min_m=float(zz.min()), max_m=float(zz.max()), mean_m=float(zz.mean()), std_m=float(zz.std()))
        gy, gx = np.gradient(np.where(v, z, np.nanmean(z)))
        jumps = np.abs(np.hypot(gx, gy))
        d["spike_cells"] = int((jumps > 200).sum())   # >200 m jump between 50 m cells = suspicious
        d["plausible_mars_range"] = bool(-8500 < zz.min() and zz.max() < 22000)
    d["status"] = ("good" if d["valid_fraction"] > 0.9 and d.get("spike_cells", 0) == 0 else
                   "usable" if d["valid_fraction"] > 0.5 else "poor")
    return d


# ---------------------------------------------------------------- cache
def save_grid(g: Grid, path: Path = PROCESSED_NPZ):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():                       # never destroy the previous processed DEM: keep one backup
        import shutil
        shutil.copy2(path, path.with_suffix(".npz.bak"))
    th = g.thermal if g.thermal is not None else np.full_like(g.z, np.nan)
    np.savez_compressed(path, z=g.z.astype(np.float32), thermal=th.astype(np.float32),
                        lat_top=g.lat_top, lon_left=g.lon_left, dlat=g.dlat, dlon=g.dlon,
                        source=g.source, data_class=g.data_class.value, meta=json.dumps(g.meta, default=str))


def load_processed(path: Path = PROCESSED_NPZ) -> Grid | None:
    if not path.exists():
        return None
    d = np.load(path, allow_pickle=False)
    th = d["thermal"].astype(np.float32) if "thermal" in d.files else None
    if th is not None and not np.isfinite(th).any():
        th = None
    return Grid(z=d["z"].astype(np.float32), lat_top=float(d["lat_top"]), lon_left=float(d["lon_left"]),
                dlat=float(d["dlat"]), dlon=float(d["dlon"]), source=str(d["source"]),
                data_class=DataClass(str(d["data_class"])), thermal=th, meta=json.loads(str(d["meta"])))


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- download
def download(url: str, dest: Path, expected_sha256: str | None = None, progress=None, timeout=60) -> dict:
    """Resumable HTTP download with status/size checks. Never reports success on failure."""
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        head = requests.head(url, timeout=timeout, allow_redirects=True)
    except requests.exceptions.ConnectionError as e:
        raise ModuleError("err.network", f"DNS/connection: {e.__class__.__name__}") from e
    except requests.exceptions.Timeout as e:
        raise ModuleError("err.network", "timeout") from e
    if head.status_code >= 400:
        raise ModuleError("err.http", f"HTTP {head.status_code}")
    total = int(head.headers.get("content-length", 0))
    if dest.exists() and total and dest.stat().st_size == total:
        return {"path": str(dest), "bytes": total, "resumed": False, "already": True}
    start = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else {}
    with requests.get(url, stream=True, timeout=timeout, headers=headers) as r:
        if r.status_code not in (200, 206):
            raise ModuleError("err.http", f"HTTP {r.status_code}")
        mode = "ab" if r.status_code == 206 else "wb"
        done = start if r.status_code == 206 else 0
        with open(part, mode) as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    if total and part.stat().st_size != total:
        raise ModuleError("err.incomplete", f"{part.stat().st_size}/{total} bytes")
    if expected_sha256 and sha256(part) != expected_sha256:
        raise ModuleError("err.checksum", dest.name)
    part.replace(dest)
    return {"path": str(dest), "bytes": dest.stat().st_size, "resumed": start > 0, "already": False}
