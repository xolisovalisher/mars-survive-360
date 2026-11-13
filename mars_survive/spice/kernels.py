"""SPICE & Orbital Geometry (module 12) with spiceypy.

If kernels are missing the module does not fail: it reports which kernels are
needed, where to get them, and the app falls back to the analytic Mars24 algorithm.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import config as C
from mars_survive.common import ModuleError, get_logger

log = get_logger("spice")

REQUIRED = [
    {"kind": "LSK", "file": "naif0012.tls", "dir": "lsk", "header": "KPL/LSK",
     "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls", "purpose": "UTC <-> TDB time"},
    {"kind": "PCK", "file": "pck00011.tpc", "dir": "pck", "header": "KPL/PCK",
     "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc", "purpose": "Mars shape & rotation (IAU_MARS)"},
    {"kind": "SPK", "file": "de440s.bsp", "dir": "spk", "header": "DAF/SPK",
     "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp", "purpose": "Sun/planet ephemeris"},
]
HEADERS = {".tls": "KPL/LSK", ".tpc": "KPL/PCK", ".bsp": "DAF/SPK", ".tf": "KPL/FK", ".ti": "KPL/IK",
           ".tsc": "KPL/SCLK", ".bc": "DAF/CK"}


def available() -> bool:
    try:
        import spiceypy  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def validate_kernel(path: Path) -> dict:
    """Check extension and the NAIF identification word in the first bytes."""
    ext = path.suffix.lower()
    exp = HEADERS.get(ext)
    try:
        head = path.read_bytes()[:8].decode("latin-1")
    except OSError as e:
        return {"file": path.name, "ok": False, "reason": str(e)}
    ok = exp is not None and head.startswith(exp)
    return {"file": path.name, "kind": exp, "ok": ok, "size_kb": round(path.stat().st_size / 1024, 1),
            "reason": "" if ok else f"expected header {exp}, found {head!r}"}


def scan(root: Path = C.SPICE_DIR) -> list[dict]:
    out = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in HEADERS:
            out.append(validate_kernel(p))
    return out


def status(root: Path = C.SPICE_DIR) -> list[dict]:
    found = {k["file"]: k for k in scan(root)}
    res = []
    for r in REQUIRED:
        f = found.get(r["file"]) or next((v for v in found.values() if v["kind"] == r["header"] and v["ok"]), None)
        res.append({**r, "present": bool(f and f["ok"]), "found_file": f["file"] if f else None})
    return res


_loaded: set[str] = set()


def load_all(root: Path = C.SPICE_DIR) -> list[str]:
    if not available():
        raise ModuleError("err.spiceypy_missing", "pip install spiceypy")
    import spiceypy as sp
    loaded = []
    for k in scan(root):
        if k["ok"]:
            p = next(root.rglob(k["file"]))
            if str(p) not in _loaded:
                sp.furnsh(str(p))
                _loaded.add(str(p))
            loaded.append(k["file"])
    return loaded


def clear():
    if available():
        import spiceypy as sp
        sp.kclear()
    _loaded.clear()


def utc_to_et(dt: datetime) -> float:
    import spiceypy as sp
    return sp.str2et(dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))


def sun_geometry(dt: datetime, lat: float, lon_east: float) -> dict:
    """Solar elevation/azimuth at a Mars surface site from SPICE (needs LSK+PCK+SPK)."""
    import numpy as np
    import spiceypy as sp
    st = {s["kind"]: s["present"] for s in status()}
    missing = [k for k, v in st.items() if not v]
    if missing:
        raise ModuleError("err.kernels_missing", ",".join(missing))
    load_all()
    et = utc_to_et(dt)
    radii = sp.bodvrd("MARS", "RADII", 3)[1]
    re, rp = radii[0], radii[2]
    f = (re - rp) / re
    # planetocentric -> surface point on the ellipsoid
    site = sp.srfrec(499, math.radians(lon_east), math.radians(lat))
    sun, lt = sp.spkpos("SUN", et, "IAU_MARS", "LT+S", "MARS")
    normal = sp.surfnm(re, re, rp, site)
    to_sun = np.array(sun) - np.array(site)
    to_sun /= np.linalg.norm(to_sun)
    elev = 90 - math.degrees(math.acos(np.clip(np.dot(normal, to_sun), -1, 1)))
    east = np.cross([0, 0, 1], normal)
    east /= np.linalg.norm(east)
    north = np.cross(normal, east)
    az = math.degrees(math.atan2(np.dot(to_sun, east), np.dot(to_sun, north))) % 360
    ls = math.degrees(sp.lspcn("MARS", et, "LT+S"))
    dist_au = np.linalg.norm(sun) / 1.495978707e8
    return {"et": et, "elevation_deg": elev, "azimuth_deg": az, "Ls": ls, "sun_distance_au": dist_au,
            "flattening": f, "light_time_s": lt}
