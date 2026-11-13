"""GIS export: mission layers as a GeoPackage in a Mars coordinate reference system (GeoPandas + Shapely).

CRS: IAU_2015:49900 — Mars (2015) sphere, planetocentric latitude, east longitude (the convention used by
the app and by the USGS Jezero products). Opens in QGIS / ArcGIS as Mars data, not as Earth WGS84.
Optional: needs geopandas + shapely; without them the caller gets a clear ModuleError.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd

from mars_survive.common import ModuleError

MARS_CRS = "IAU_2015:49900"


def available() -> bool:
    try:
        import geopandas  # noqa: F401
        import shapely  # noqa: F401
        return True
    except ImportError:
        return False


def _crs():
    from pyproj import CRS
    try:
        return CRS(MARS_CRS)
    except Exception:  # noqa: BLE001 — very old PROJ without IAU codes
        return CRS.from_proj4("+proj=longlat +R=3389500 +no_defs +type=crs")


def mission_layers(routes: dict, targets: list | None = None, hazards: list | None = None,
                   traverse: pd.DataFrame | None = None, data_class: str = "Synthetic") -> dict:
    """{layer name: GeoDataFrame}. routes: {strategy: RouteResult}; targets/hazards: list of dicts with lat/lon."""
    if not available():
        raise ModuleError("err.missing_pkg", "geopandas, shapely")
    import geopandas as gpd
    import shapely
    crs = _crs()
    out = {}
    rows = []
    for k, r in (routes or {}).items():
        if r is None or not r.found:
            continue
        s = r.summary()
        rows.append({"strategy": k, "dist2d_km": s["distance_2d_km"], "dist3d_km": s["distance_3d_km"],
                     "max_slope": s["max_slope_deg"], "hazard_mean": s["hazard_mean"], "data_class": data_class,
                     "geometry": shapely.LineString(list(zip(r.lon, r.lat)))})
    if rows:
        out["routes"] = gpd.GeoDataFrame(rows, crs=crs)
    if targets:
        out["science_targets"] = gpd.GeoDataFrame(
            [{**{k: v for k, v in t.items() if k not in ("lat", "lon") and not isinstance(v, (list, dict))},
              "geometry": shapely.Point(t["lon"], t["lat"])} for t in targets], crs=crs)
    if hazards:
        out["hazards"] = gpd.GeoDataFrame(
            [{"type": h.get("type"), "level": h.get("level"), "area_km2": h.get("area_km2"),
              "geometry": shapely.Point(h["lon"], h["lat"])} for h in hazards if "lat" in h], crs=crs)
    if traverse is not None and len(traverse) > 1:
        segs = [{"segment": int(s), "sol": None if pd.isna(p["sol"].iloc[0]) else int(p["sol"].iloc[0]),
                 "geometry": shapely.LineString(list(zip(p["lon"], p["lat"])))}
                for s, p in traverse.groupby("segment", sort=False) if len(p) >= 2]
        if segs:
            out["perseverance_traverse"] = gpd.GeoDataFrame(segs, crs=crs)
    return out


def to_geopackage(layers: dict) -> bytes:
    if not layers:
        raise ModuleError("err.invalid", "nothing to export")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "mission.gpkg"
        for name, gdf in layers.items():
            gdf.to_file(p, layer=name, driver="GPKG")
        return p.read_bytes()


def to_geojson(layers: dict) -> bytes:
    """All layers merged into one GeoJSON FeatureCollection (property 'layer')."""
    import geopandas as gpd
    frames = [g.assign(layer=n) for n, g in layers.items()]
    allg = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    buf = io.StringIO()
    import warnings
    with warnings.catch_warnings():          # GeoJSON (RFC 7946) cannot carry a non-WGS84 CRS — documented
        warnings.simplefilter("ignore", UserWarning)
        buf.write(allg.to_json(drop_id=True))
    return buf.getvalue().encode("utf-8")
