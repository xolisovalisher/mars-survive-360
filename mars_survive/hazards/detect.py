"""Hazard Detection (module 6).

Per-cell hazard index H in [0, 1] and hazard objects (connected regions) with
type, level, coordinates, method and a confidence value.

Rules (thresholds are user-editable; defaults are ASSUMPTIONS for suited walking /
slow rover driving on a 50 m grid):
  steep_slope      slope >= slope_limit                       -> no-go
  steep_slope      slope >= 0.6 * slope_limit                 -> caution
  rough_surface    roughness >= p95 of region                 -> caution / high
  rocky_terrain    TRI >= p95 and roughness >= p90            -> high
  crater_edge      curvature >= p97 and relief >= relief_min  -> high
  discontinuity    relief >= 3 * relief p90                   -> high
  uncertain        NoData or adjacent to NoData               -> unknown (never "safe")
Confidence: 0.9 for direct DEM thresholds, 0.6 for derived/statistical classes,
0.3 for uncertain terrain - reduced to x0.6 when the DEM is SYNTHETIC.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from mars_survive.dem.grid import Grid
from mars_survive.terrain.analysis import TerrainLayers

LEVELS = {0: "safe", 1: "caution", 2: "high", 3: "no-go", 4: "unknown"}


@dataclass
class HazardResult:
    index: np.ndarray        # 0..1 continuous hazard index
    level: np.ndarray        # 0..4 (see LEVELS)
    type_map: np.ndarray     # int code of dominant hazard type
    objects: list            # list of dicts
    params: dict


TYPES = ["none", "steep_slope", "rough_surface", "rocky_terrain", "crater_edge", "discontinuity", "uncertain"]


def detect(g: Grid, T: TerrainLayers, slope_limit: float = 20.0, relief_min: float = 15.0,
           min_cells: int = 4) -> HazardResult:
    s, r, t, c, rel = T.slope, T.roughness, T.tri, T.curvature, T.relief
    valid = np.isfinite(g.z)
    p = lambda a, q: float(np.nanpercentile(a, q))  # noqa: E731
    r90, r95, t95, c97, rel90 = p(r, 90), p(r, 95), p(t, 95), p(c, 97), p(rel, 90)

    level = np.zeros(g.shape, np.uint8)
    tmap = np.zeros(g.shape, np.uint8)

    def mark(mask, lv, tp):
        m = mask & valid & (level < lv)
        level[m] = lv
        tmap[m] = tp

    mark(np.nan_to_num(s) >= 0.6 * slope_limit, 1, 1)
    mark(np.nan_to_num(r) >= r95, 1, 2)
    mark((np.nan_to_num(t) >= t95) & (np.nan_to_num(r) >= r90), 2, 3)
    mark((np.nan_to_num(c) >= c97) & (np.nan_to_num(rel) >= relief_min), 2, 4)
    mark(np.nan_to_num(rel) >= 3 * rel90, 2, 5)
    mark(np.nan_to_num(s) >= slope_limit, 3, 1)
    near_nodata = ndimage.binary_dilation(~valid, iterations=1)
    level[near_nodata] = 4
    tmap[near_nodata] = 6

    idx = np.clip(0.55 * np.nan_to_num(s) / slope_limit + 0.25 * np.nan_to_num(r) / (r95 + 1e-6)
                  + 0.20 * np.nan_to_num(rel) / (3 * rel90 + 1e-6), 0, 1).astype(np.float32)
    idx[level == 3] = 1.0
    idx[level == 4] = 1.0

    synthetic_factor = 1.0 if g.is_real else 0.6
    conf_by_type = {1: 0.9, 2: 0.6, 3: 0.6, 4: 0.6, 5: 0.6, 6: 0.3}
    objects = []
    lab, n = ndimage.label(level >= 1)
    if n:
        sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
        coms = ndimage.center_of_mass(np.ones_like(lab), lab, index=np.arange(1, n + 1))
        for i, (sz, (cr, cc)) in enumerate(zip(sizes, coms), start=1):
            if sz < min_cells:
                continue
            m = lab == i
            lv = int(level[m].max())
            tp = int(np.bincount(tmap[m], minlength=len(TYPES))[1:].argmax() + 1)
            objects.append({
                "id": len(objects) + 1, "type": TYPES[tp], "level": LEVELS[lv],
                "lat": float(g.lat(cr)), "lon": float(g.lon(cc)),
                "area_km2": float(sz * g.cell_area_km2()),
                "max_slope_deg": float(np.nanmax(s[m])) if np.isfinite(s[m]).any() else None,
                "method": "DEM threshold rules (slope/roughness/TRI/curvature/relief)",
                "source": g.source, "confidence": round(conf_by_type.get(tp, 0.5) * synthetic_factor, 2)})
    objects.sort(key=lambda o: (-["safe", "caution", "high", "no-go", "unknown"].index(o["level"]), -o["area_km2"]))
    return HazardResult(index=idx, level=level, type_map=tmap, objects=objects,
                        params=dict(slope_limit=slope_limit, relief_min=relief_min, r95=r95, t95=t95, c97=c97))


def summary(h: HazardResult) -> dict:
    tot = h.level.size
    return {LEVELS[k]: float((h.level == k).sum() / tot) for k in LEVELS}
