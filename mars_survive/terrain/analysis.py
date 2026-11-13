"""Terrain Intelligence (module 3): DEM derivatives.

All derivatives use the true ground cell size: dy = R*dlat, dx = R*dlon*cos(lat).
Units: slope/aspect in degrees, curvature in 1/m (x100 for 1/100 m), others in metres.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from mars_survive.dem.grid import Grid


def filled(z: np.ndarray) -> np.ndarray:
    """Nearest-neighbour fill of NoData (only for computing derivatives; mask is re-applied)."""
    m = np.isfinite(z)
    if m.all():
        return z.astype(float)
    if not m.any():
        return np.zeros_like(z, float)
    idx = ndimage.distance_transform_edt(~m, return_distances=False, return_indices=True)
    return z[tuple(idx)].astype(float)


def gradients(g: Grid):
    z = filled(g.z)
    dzdy = -np.gradient(z, axis=0) / g.dy                 # +north (row index grows southward)
    dzdx = np.gradient(z, axis=1) / g.dx_rows[:, None]    # +east
    return dzdx, dzdy


def _mask(a, g):
    a = a.astype(np.float32)
    a[~np.isfinite(g.z)] = np.nan
    return a


def slope_deg(g: Grid):
    dzdx, dzdy = gradients(g)
    return _mask(np.degrees(np.arctan(np.hypot(dzdx, dzdy))), g)


def aspect_deg(g: Grid):
    """Downslope direction, degrees clockwise from north (0 = faces north). Flat -> NaN."""
    dzdx, dzdy = gradients(g)
    asp = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360) % 360
    asp[np.hypot(dzdx, dzdy) < 1e-4] = np.nan
    return _mask(asp, g)


def curvature(g: Grid):
    """Laplacian-based total curvature (1/m): + convex (ridges, rims), - concave (hollows)."""
    z = filled(g.z)
    dx = g.dx_rows[:, None]
    d2x = (np.roll(z, -1, 1) - 2 * z + np.roll(z, 1, 1)) / dx ** 2
    d2y = (np.roll(z, -1, 0) - 2 * z + np.roll(z, 1, 0)) / g.dy ** 2
    c = -(d2x + d2y)
    c[:, [0, -1]] = np.nan
    c[[0, -1], :] = np.nan
    return _mask(c, g)


def roughness(g: Grid, sigma_px: float = 2.0, win: int = 5):
    """Std-dev of the elevation residual after a Gaussian low-pass (m)."""
    z = filled(g.z)
    res = z - ndimage.gaussian_filter(z, sigma_px)
    m = ndimage.uniform_filter(res, win)
    m2 = ndimage.uniform_filter(res ** 2, win)
    return _mask(np.sqrt(np.clip(m2 - m ** 2, 0, None)), g)


def tri(g: Grid):
    """Terrain Ruggedness Index (Riley 1999): mean |dz| to the 8 neighbours (m)."""
    z = filled(g.z)
    acc = np.zeros_like(z)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr or dc:
                acc += np.abs(z - np.roll(np.roll(z, dr, 0), dc, 1))
    return _mask(acc / 8, g)


def local_relief(g: Grid, win: int = 9):
    """Max - min elevation in a win x win window (m)."""
    z = filled(g.z)
    return _mask(ndimage.maximum_filter(z, win) - ndimage.minimum_filter(z, win), g)


def tpi(g: Grid, radius_px: int = 10):
    """Topographic Position Index: + ridges/rims, - depressions (m)."""
    z = filled(g.z)
    return _mask(z - ndimage.uniform_filter(z, 2 * radius_px + 1), g)


def hillshade(g: Grid, az: float = 315.0, alt: float = 40.0):
    dzdx, dzdy = gradients(g)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(-dzdx, -dzdy)   # downslope direction = horizontal part of the surface normal
    a, h = np.radians(az), np.radians(alt)
    hs = np.sin(h) * np.cos(slope) + np.cos(h) * np.sin(slope) * np.cos(a - aspect)
    return _mask(np.clip(hs, 0, 1), g)


@dataclass
class TerrainLayers:
    slope: np.ndarray
    aspect: np.ndarray
    curvature: np.ndarray
    roughness: np.ndarray
    tri: np.ndarray
    relief: np.ndarray
    tpi: np.ndarray
    hillshade: np.ndarray
    variability: np.ndarray
    complexity: np.ndarray


def compute_all(g: Grid) -> TerrainLayers:
    s = slope_deg(g)
    r = roughness(g)
    rel = local_relief(g)
    t = tri(g)
    # terrain variability: local std of slope (deg); complexity: normalised blend 0..1
    sf = np.nan_to_num(s, nan=0.0)
    var = np.sqrt(np.clip(ndimage.uniform_filter(sf ** 2, 7) - ndimage.uniform_filter(sf, 7) ** 2, 0, None))
    var = _mask(var, g)

    def norm(a):
        lo, hi = np.nanpercentile(a, 2), np.nanpercentile(a, 98)
        return np.clip((a - lo) / (hi - lo + 1e-9), 0, 1)

    comp = _mask((norm(s) + norm(r) + norm(rel) + norm(var)) / 4, g)
    return TerrainLayers(slope=s, aspect=aspect_deg(g), curvature=curvature(g), roughness=r, tri=t,
                         relief=rel, tpi=tpi(g), hillshade=hillshade(g), variability=var, complexity=comp)


def stats(a: np.ndarray) -> dict:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return {"mean": None}
    return {"mean": float(v.mean()), "std": float(v.std()), "min": float(v.min()),
            "p50": float(np.percentile(v, 50)), "p90": float(np.percentile(v, 90)), "max": float(v.max())}


def profile(g: Grid, lat1, lon1, lat2, lon2, n: int = 200) -> dict:
    """Elevation profile along the great circle between two points (bilinear sampling)."""
    from mars_survive.mapping.coords import haversine_m
    t = np.linspace(0, 1, n)
    lats, lons = lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t  # fine for < 50 km
    z = np.array([g.sample(g.z, a, b) for a, b in zip(lats, lons)])
    total = float(haversine_m(lat1, lon1, lat2, lon2))
    d = t * total
    dz = np.diff(z)
    seg = np.diff(d)
    sl = np.degrees(np.arctan(np.abs(dz) / np.maximum(seg, 1e-9)))
    d3 = float(np.nansum(np.sqrt(seg ** 2 + dz ** 2)))
    return {"dist_m": d, "elev": z, "lat": lats, "lon": lons, "slope_deg": np.concatenate([[0], sl]),
            "dist2d_m": total, "dist3d_m": d3, "gain_m": float(np.nansum(np.clip(dz, 0, None))),
            "loss_m": float(-np.nansum(np.clip(dz, None, 0))), "nodata_samples": int(np.isnan(z).sum())}
