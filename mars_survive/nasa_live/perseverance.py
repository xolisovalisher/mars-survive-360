"""Perseverance (Mars 2020) traverse and raw images — what the crew will see along the route.

Traverse: NASA/JPL MMGIS GeoJSON (config.M20_TRAVERSE, plus the companion waypoints file) — LineString /
Point features with a sol number; coordinates are east longitude / planetocentric latitude.
Raw images: public feed https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json&sol=N
(raw, uncalibrated engineering/science images; JPL-Caltech/NASA).

Nothing here is downloaded automatically. When the services are unreachable the module says so; a GeoJSON/JSON
file saved from these services can be loaded instead (User Supplied). A small bundled example file is
SYNTHETIC (format example only).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
from mars_survive.common import ModuleError
from mars_survive.mapping.coords import haversine_m
from mars_survive.nasa_live import http

TRAVERSE_URL = C.M20_TRAVERSE
WAYPOINTS_URL = C.M20_TRAVERSE.replace("M20_traverse.json", "M20_waypoints.json")
RAW_URL = "https://mars.nasa.gov/rss/api/"
CAMERA_GROUPS = {
    "navcam": ("NAVCAM",), "mastcam": ("MCZ_",), "hazcam": ("FRONT_HAZCAM", "REAR_HAZCAM"),
    "supercam": ("SUPERCAM",), "watson_sherloc": ("SHERLOC",), "skycam": ("SKYCAM",),
}
SOL_KEYS = ("sol", "Sol", "SOL", "toSol", "endSol", "sol_end")


def _sol(props: dict):
    for k in SOL_KEYS:
        if k in props and props[k] not in (None, ""):
            try:
                return int(float(props[k]))
            except (TypeError, ValueError):
                pass
    return None


def parse_traverse(gj: dict) -> pd.DataFrame:
    """GeoJSON → ordered vertex table: lat, lon (east, 0..360 kept as given if > 180 → converted to −180..180),
    sol, segment, cumulative distance (m, haversine on the Mars mean sphere)."""
    if not isinstance(gj, dict) or gj.get("type") not in ("FeatureCollection", "Feature"):
        raise ModuleError("err.geojson", "not a GeoJSON FeatureCollection")
    feats = gj["features"] if gj["type"] == "FeatureCollection" else [gj]
    rows = []
    for i, f in enumerate(feats):
        geom = (f or {}).get("geometry") or {}
        props = (f or {}).get("properties") or {}
        sol = _sol(props)
        t = geom.get("type")
        if t == "LineString":
            lines = [geom.get("coordinates") or []]
        elif t == "MultiLineString":
            lines = geom.get("coordinates") or []
        elif t == "Point":
            lines = [[geom.get("coordinates")]]
        else:
            continue
        for line in lines:
            for pt in line:
                if not pt or len(pt) < 2:
                    continue
                lon, lat = float(pt[0]), float(pt[1])
                if lon > 180:
                    lon -= 360
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
                rows.append({"segment": i, "sol": sol, "lat": lat, "lon": lon})
    if not rows:
        raise ModuleError("err.geojson", "no coordinates")
    df = pd.DataFrame(rows)
    if df["sol"].notna().any():
        df["sol"] = df["sol"].ffill().bfill()
        df = df.sort_values(["sol", "segment"], kind="stable").reset_index(drop=True)
    d = haversine_m(df["lat"].values[:-1], df["lon"].values[:-1], df["lat"].values[1:], df["lon"].values[1:])
    jump = d > 2000                     # separate features far apart are not driven distance
    d = np.where(jump, 0.0, d)
    df["dist_m"] = np.concatenate([[0.0], np.cumsum(d)])
    return df


def fetch_traverse(use_cache=True) -> dict:
    if use_cache:
        c = http.cache_load("m20traverse", TRAVERSE_URL, max_age_h=24)
        if c:
            return c
    payload = http.get_json(TRAVERSE_URL)
    parse_traverse(payload)                          # validate before caching
    http.cache_save("m20traverse", TRAVERSE_URL, payload, "Real", TRAVERSE_URL)
    return http.cache_load("m20traverse", TRAVERSE_URL)


def summary(df: pd.DataFrame) -> dict:
    sols = df["sol"].dropna()
    return {"vertices": int(len(df)), "sol_min": int(sols.min()) if len(sols) else None,
            "sol_max": int(sols.max()) if len(sols) else None, "driven_km": float(df["dist_m"].iloc[-1] / 1000),
            "lat_range": (float(df["lat"].min()), float(df["lat"].max())),
            "lon_range": (float(df["lon"].min()), float(df["lon"].max()))}


def nearest(df: pd.DataFrame, lat: float, lon: float) -> dict:
    d = haversine_m(lat, lon, df["lat"].values, df["lon"].values)
    i = int(np.argmin(d))
    row = df.iloc[i]
    return {"index": i, "distance_m": float(d[i]), "sol": None if pd.isna(row["sol"]) else int(row["sol"]),
            "lat": float(row["lat"]), "lon": float(row["lon"])}


def _local_xy(lat, lon, lat0, lon0):
    """Local equirectangular metres on the Mars mean sphere (error < 0.1 % over a few km)."""
    R = C.R_MARS_MEAN
    return (np.radians(np.asarray(lon) - lon0) * R * np.cos(np.radians(lat0)),
            np.radians(np.asarray(lat) - lat0) * R)


def route_vs_traverse(df: pd.DataFrame, lats, lons) -> pd.DataFrame:
    """For every route vertex: distance to the traverse POLYLINE (Shapely, point-to-segment) and the sol of the
    nearest traverse vertex. Without Shapely: distance to the nearest traverse vertex (slight overestimate)."""
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    sols = [nearest(df, la, lo)["sol"] for la, lo in zip(lats, lons)]
    try:
        import shapely
        lat0, lon0 = float(df["lat"].mean()), float(df["lon"].mean())
        tx, ty = _local_xy(df["lat"].values, df["lon"].values, lat0, lon0)
        lines = []
        for _, part in df.assign(x=tx, y=ty).groupby("segment", sort=False):
            if len(part) >= 2:
                lines.append(shapely.LineString(np.column_stack([part["x"], part["y"]])))
        geom = shapely.MultiLineString(lines) if lines else shapely.MultiPoint(np.column_stack([tx, ty]))
        px, py = _local_xy(lats, lons, lat0, lon0)
        d = shapely.distance(shapely.points(px, py), geom)
        method = "shapely"
    except ImportError:
        d = np.array([nearest(df, la, lo)["distance_m"] for la, lo in zip(lats, lons)])
        method = "vertex"
    return pd.DataFrame({"lat": lats, "lon": lons, "dist_to_traverse_m": d, "sol": sols, "method": method})


# ------------------------------------------------------------------------------------------- raw images
def fetch_raw_images(sol: int, per_page: int = 50, page: int = 0, use_cache=True) -> dict:
    if not (0 <= int(sol) <= 20000):
        raise ModuleError("err.invalid", "sol")
    key = f"raw:{int(sol)}:{per_page}:{page}"
    if use_cache:
        c = http.cache_load("m20raw", key, max_age_h=24 * 7)
        if c:
            return c
    params = {"feed": "raw_images", "category": "mars2020", "feedtype": "json", "sol": int(sol),
              "num": int(per_page), "page": int(page), "order": "sol desc"}
    payload = http.get_json(RAW_URL, params=params)
    if not isinstance(payload, dict) or "images" not in payload:
        raise ModuleError("err.bad_json", "raw image feed: no 'images'")
    http.cache_save("m20raw", key, payload, "Real", RAW_URL)
    return http.cache_load("m20raw", key)


def _safe_url(u) -> str | None:
    u = str(u or "")
    return u if u.startswith("https://") and " " not in u and len(u) < 600 else None


def parse_raw_images(payload: dict) -> pd.DataFrame:
    rows = []
    for im in (payload or {}).get("images") or []:
        if not isinstance(im, dict):
            continue
        cam = im.get("camera") or {}
        files = im.get("image_files") or {}
        ext = im.get("extended") or {}
        rows.append({"imageid": str(im.get("imageid", ""))[:80], "sol": im.get("sol"),
                     "instrument": str(cam.get("instrument", ""))[:40], "filter": str(cam.get("filter_name", ""))[:20],
                     "date_utc": str(im.get("date_taken_utc", ""))[:25], "lmst": str(ext.get("localtime", ""))[:20],
                     "mast_az": ext.get("mastAz"), "mast_el": ext.get("mastEl"),
                     "thumb": _safe_url(files.get("small") or files.get("medium")),
                     "full": _safe_url(files.get("full_res") or files.get("large") or files.get("medium")),
                     "page": _safe_url(im.get("link")) or "https://mars.nasa.gov/mars2020/multimedia/raw-images/",
                     "credit": str(im.get("credit", "NASA/JPL-Caltech"))[:80]})
    return pd.DataFrame(rows, columns=["imageid", "sol", "instrument", "filter", "date_utc", "lmst", "mast_az",
                                       "mast_el", "thumb", "full", "page", "credit"])


def filter_cameras(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    if not groups or not len(df):
        return df
    pref = tuple(p for g in groups for p in CAMERA_GROUPS.get(g, ()))
    return df[df["instrument"].str.upper().str.startswith(pref)]


def example_traverse() -> dict:
    p = Path(__file__).with_name("examples") / "m20_traverse_example_synthetic.geojson"
    return json.loads(p.read_text(encoding="utf-8"))


def example_raw() -> dict:
    p = Path(__file__).with_name("examples") / "m20_raw_images_example_synthetic.json"
    return json.loads(p.read_text(encoding="utf-8"))
