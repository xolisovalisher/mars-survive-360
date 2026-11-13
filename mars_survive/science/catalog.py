"""Science Target Catalog (module 18).

origin = "published"   : coordinate published by NASA/JPL (verifiable source given);
origin = "approximate" : location read approximately from public maps - verify in Mars Trek;
origin = "user"        : entered by the user.
"""
from __future__ import annotations

import numpy as np

import config as C
from mars_survive import storage
from mars_survive.mapping.coords import haversine_m

SEED = [
    {"name": "Octavia E. Butler Landing (Perseverance)", "lat": 18.4447, "lon": 77.4508, "kind": "landing_site",
     "description": "Perseverance landing point, 18 Feb 2021.", "priority": 3, "origin": "published",
     "source": "NASA/JPL Mars 2020 mission"},
    {"name": "Western delta front", "lat": 18.455, "lon": 77.405, "kind": "delta",
     "description": "Fluvial-deltaic sediments; high biosignature preservation potential.", "priority": 5,
     "origin": "approximate", "source": "approx. from Mars 2020 maps - verify"},
    {"name": "Seitah (olivine-rich unit)", "lat": 18.425, "lon": 77.430, "kind": "igneous",
     "description": "Olivine-rich crater-floor unit sampled by Perseverance.", "priority": 4,
     "origin": "approximate", "source": "approx. from Mars 2020 maps - verify"},
    {"name": "Crater floor plains", "lat": 18.470, "lon": 77.465, "kind": "plains",
     "description": "Smooth terrain for instrument checks and traverse tests.", "priority": 2,
     "origin": "approximate", "source": "approx. - verify"},
]
KINDS = ["landing_site", "delta", "igneous", "plains", "crater", "rock", "outcrop", "sample_site", "other"]
STATUSES = ["planned", "observed", "sampled", "skipped"]


def ensure_seed(path=C.DB_PATH):
    if not storage.rows("SELECT id FROM targets LIMIT 1", (), path):
        for s in SEED:
            add(**s, path=path)


def add(name, lat, lon, kind="other", description="", priority=3, origin="user", source="user", status="planned",
        path=C.DB_PATH) -> int:
    name = str(name).strip()[:120]
    if not name:
        raise ValueError("empty name")
    lat, lon = float(lat), float(lon)
    if not -90 <= lat <= 90:
        raise ValueError("latitude out of range")
    return storage.execute("INSERT INTO targets(name,lat,lon,kind,description,status,priority,origin,source,created)"
                           " VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (name, lat, lon, kind if kind in KINDS else "other", str(description)[:1000],
                            status if status in STATUSES else "planned", int(priority), origin, source,
                            storage.now()), path)


def all_targets(path=C.DB_PATH) -> list[dict]:
    ensure_seed(path)
    return storage.rows("SELECT * FROM targets ORDER BY priority DESC, id", (), path)


def set_status(tid: int, status: str, path=C.DB_PATH):
    if status in STATUSES:
        storage.execute("UPDATE targets SET status=? WHERE id=?", (status, int(tid)), path)


def delete(tid: int, path=C.DB_PATH):
    storage.execute("DELETE FROM targets WHERE id=?", (int(tid),), path)


def distance_to_route(targets: list[dict], route_lat, route_lon) -> list[dict]:
    out = []
    for t in targets:
        d = haversine_m(t["lat"], t["lon"], np.asarray(route_lat), np.asarray(route_lon))
        i = int(np.argmin(d))
        out.append({**t, "route_distance_m": float(d[i]), "route_index": i})
    return out


def observation_tasks(t: dict) -> list[str]:
    base = {"delta": ["context imaging", "close-up imaging", "abrasion + proximity science", "sample core"],
            "igneous": ["context imaging", "mineralogy spectra", "sample core"],
            "landing_site": ["hardware inspection", "context imaging"],
            "plains": ["instrument calibration", "soil scoop"]}
    return base.get(t.get("kind"), ["context imaging", "measurements"])
