"""Data Ingestion (module 21): safe validation and parsing of uploaded files.

Security: extension whitelist, size limit, magic-byte sniffing, sanitized file
names (no path traversal), defusedxml for XML, json with size limit.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

import config as C
from mars_survive.common import DataClass, ModuleError, get_logger
from mars_survive.provenance import registry

log = get_logger("ingestion")
MAGIC = {".tif": [b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"], ".tiff": [b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"],
         ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"]}


def safe_name(name: str) -> str:
    base = Path(str(name).replace("\\", "/")).name          # drops any directory part / ".."
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:120].lstrip(".")
    if not base:
        raise ModuleError("err.bad_name", name)
    return base


def validate(name: str, data: bytes) -> dict:
    fn = safe_name(name)
    ext = Path(fn).suffix.lower()
    if ext not in C.ALLOWED_UPLOAD_EXT:
        raise ModuleError("err.ext", ext)
    size = len(data)
    if size == 0:
        raise ModuleError("err.empty", fn)
    if size > C.MAX_UPLOAD_MB * 1e6:
        raise ModuleError("err.too_big", f"{size / 1e6:.1f} MB > {C.MAX_UPLOAD_MB} MB")
    if ext in MAGIC and not any(data.startswith(m) for m in MAGIC[ext]):
        raise ModuleError("err.magic", fn)
    return {"name": fn, "ext": ext, "size_bytes": size, "sha256": hashlib.sha256(data).hexdigest()}


def parse(name: str, data: bytes) -> dict:
    v = validate(name, data)
    ext = v["ext"]
    info: dict = {**v, "format": None, "crs": None, "units": None, "metadata": {}, "errors": []}
    try:
        if ext in (".tif", ".tiff"):
            import rasterio
            from rasterio.io import MemoryFile
            with MemoryFile(data) as mf, mf.open() as src:
                info.update(format="GeoTIFF" if src.crs else "TIFF", crs=src.crs.to_string() if src.crs else None,
                            units=src.units[0] if src.units and src.units[0] else None,
                            metadata={"width": src.width, "height": src.height, "bands": src.count,
                                      "dtype": src.dtypes[0], "nodata": src.nodata, "res": list(src.res),
                                      "bounds": list(src.bounds)})
                if not src.crs:
                    info["errors"].append("no CRS: not georeferenced")
        elif ext in (".xml", ".lbl"):
            from mars_survive.dem.loader import parse_label_xml
            if ext == ".lbl":
                text = data[:200_000].decode("latin-1", "replace")
                kv = dict(re.findall(r"^\s*([A-Z_^]+)\s*=\s*(.+?)\s*$", text, re.M)[:200])
                info.update(format="PDS3 label", metadata=kv)
            else:
                lab = parse_label_xml(data)
                info.update(format="PDS4 XML" if lab["is_pds4"] else "XML", metadata=lab)
        elif ext in (".json", ".geojson"):
            obj = json.loads(data.decode("utf-8"))
            if isinstance(obj, dict) and obj.get("type") in ("FeatureCollection", "Feature", "LineString", "Point",
                                                              "Polygon", "MultiLineString"):
                feats = obj.get("features", [obj])
                info.update(format="GeoJSON", metadata={"type": obj.get("type"), "features": len(feats)},
                            crs="EPSG:4326-style lon/lat (planetocentric assumed)")
            else:
                info.update(format="JSON", metadata={"keys": list(obj)[:30] if isinstance(obj, dict) else len(obj)})
        elif ext == ".csv":
            import pandas as pd
            df = pd.read_csv(io.BytesIO(data), sep=None, engine="python", nrows=200_000, comment="#")
            info.update(format="CSV", metadata={"rows": len(df), "columns": list(df.columns)[:40],
                                                "numeric_columns": int(df.select_dtypes("number").shape[1])})
        elif ext in (".png", ".jpg", ".jpeg"):
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im.verify()
            im = Image.open(io.BytesIO(data))
            info.update(format=f"image/{im.format}", metadata={"size": list(im.size), "mode": im.mode})
    except ModuleError:
        raise
    except Exception as e:  # noqa: BLE001
        info["errors"].append(f"{e.__class__.__name__}: {e}")
    info["valid"] = not info["errors"]
    log.info("ingested %s format=%s valid=%s", info["name"], info["format"], info["valid"])
    return info


def store(info: dict, data: bytes) -> Path:
    dest = C.DATA_UPLOADS / info["name"]
    dest.write_bytes(data)
    registry.register(info["name"], DataClass.USER, "user upload", "", "", "", info.get("crs") or "",
                      info.get("units") or "", "valid" if info.get("valid") else "errors: " + "; ".join(info["errors"]),
                      ["upload", "validated"], "user supplied - verify origin", info["size_bytes"], info["sha256"])
    return dest
