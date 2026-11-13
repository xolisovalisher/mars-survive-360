"""Data Quality & Provenance (module 22): registry of every dataset in use."""
from __future__ import annotations

import json

import config as C
from mars_survive import storage
from mars_survive.common import DataClass

CLASSES = [c.value for c in DataClass]


def register(name, data_class: DataClass | str, provider="", url="", acquisition_date="", resolution="", crs="",
             units="", quality="", history: list | None = None, limitations="", size_bytes=0, sha256="",
             path=C.DB_PATH) -> int:
    dc = data_class.value if isinstance(data_class, DataClass) else str(data_class)
    if dc not in CLASSES:
        raise ValueError(f"unknown data class {dc}")
    existing = storage.rows("SELECT id FROM datasets WHERE name=? AND data_class=?", (name, dc), path)
    hist = json.dumps(history or [])
    if existing:
        storage.execute("UPDATE datasets SET processing_date=?, quality=?, history=?, size_bytes=?, sha256=? WHERE id=?",
                        (storage.now(), quality, hist, int(size_bytes or 0), sha256, existing[0]["id"]), path)
        return existing[0]["id"]
    return storage.execute(
        "INSERT INTO datasets(name,data_class,provider,url,acquisition_date,processing_date,resolution,crs,units,"
        "quality,history,limitations,size_bytes,sha256,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (name, dc, provider, url, acquisition_date, storage.now(), resolution, crs, units, quality, hist,
         limitations, int(size_bytes or 0), sha256, storage.now()), path)


def all_datasets(path=C.DB_PATH) -> list[dict]:
    out = storage.rows("SELECT * FROM datasets ORDER BY id", (), path)
    for d in out:
        d["history"] = json.loads(d["history"] or "[]")
    return out


def register_builtin(grid, path=C.DB_PATH):
    """Register the datasets the platform itself uses, with honest classes."""
    if grid.is_real:
        register(grid.source, grid.data_class, "USGS Astrogeology / NASA JPL", C.CTX_DTM_URL, "2021-10-14",
                 f"{grid.meta.get('resolution_m', 50)} m (from 20 m)", "Mars sphere R=3396190 m lat/lon", "m",
                 grid.meta.get("quality", {}).get("status", ""), ["download", "warp average to grid"],
                 "50 m grid hides boulders", path=path)
    else:
        register("SYNTHETIC DEM (demo terrain)", DataClass.SYNTHETIC, "MARS SURVIVE 360", "", "", "50 m",
                 "Mars sphere lat/lon", "m", "n/a", ["procedural generation"],
                 "NOT Mars data - for demonstration only", path=path)
    register("NASA Mars Trek WMTS (Viking, MOLA)", DataClass.REAL, "NASA JPL Mars Trek", "https://trek.nasa.gov/mars/",
             "", "232 m / 463 m", "EQ (lat/lon)", "-", "online tiles", ["displayed in browser"], "basemap only", path=path)
    register("Curiosity RAD surface dose (Hassler et al. 2014)", DataClass.REAL, "NASA MSL RAD", "doi:10.1126/science.1244797",
             "2012-2013", "-", "-", "mSv/day", "published", ["constant 0.64 mSv/day, altitude scaled"],
             "solar particle events not modelled", path=path)
    register("Relay orbits (two-body circular)", DataClass.SIMULATED, "MARS SURVIVE 360", "", "", "-", "Mars-fixed",
             "km", "model", ["Keplerian propagation"], "not NASA ephemerides", path=path)
    register("Navigation sensors (odometry, gyro, landmarks)", DataClass.SIMULATED, "MARS SURVIVE 360", "", "", "-",
             "local ENU", "m", "model", ["EKF simulation"], "synthetic sensor noise", path=path)
    register("Suit telemetry", DataClass.SIMULATED, "MARS SURVIVE 360", "", "", "-", "-", "SI", "model",
             ["physics-based simulation"], "not a real suit interface", path=path)
