"""SYNTHETIC demo terrain placed at Jezero's coordinates.

It is NOT Mars data. It is only used when no real DEM is available and is
always labelled DataClass.SYNTHETIC ("SYNTHETIC DEM") in the interface.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

import config as C
from mars_survive.common import DataClass

from .grid import Grid


def synthetic_grid(seed: int = 7, h: int = 300, w: int = 330) -> Grid:
    rng = np.random.default_rng(seed)
    dlat = math.degrees(C.ANALYSIS_RES_M / C.R_MARS_DTM)
    dlon = dlat / math.cos(math.radians(C.JEZERO_CENTER[0]))
    lat_top = C.JEZERO_CENTER[0] + h / 2 * dlat
    lon_left = C.JEZERO_CENTER[1] - w / 2 * dlon
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    z = np.full((h, w), -2550.0, np.float32)
    for sigma, amp in [(40, 60), (12, 12), (4, 3), (1.2, 0.8)]:
        n = ndimage.gaussian_filter(rng.standard_normal((h, w)), sigma)
        z += amp * n / (n.std() + 1e-9)
    # crater-rim-like arc in the west, delta-like plateau with a scarp, small craters, ridges
    rr = np.hypot(yy - h / 2, xx - w * 0.62)
    z += 380 * np.exp(-((rr - w * 0.62) / 22) ** 2)
    z += 90 / (1 + np.exp((xx - w * 0.28 - 12 * np.sin(yy / 25)) / 4))
    for _ in range(22):
        y0, x0, r0 = rng.uniform(0, h), rng.uniform(0, w), rng.uniform(4, 16)
        d = np.hypot(yy - y0, xx - x0) / r0
        z += r0 * 2.0 * (np.exp(-(d - 1) ** 2 / 0.05) * 0.4 - np.exp(-d ** 2 / 0.6))
    z += 15 * np.clip(np.sin(xx / 6 + yy / 9), 0, 1) * np.exp(-((yy - h * 0.7) / 30) ** 2)
    z[:6, :25] = np.nan  # a small NoData patch so NoData handling is always exercised
    return Grid(z=z, lat_top=lat_top, lon_left=lon_left, dlat=dlat, dlon=dlon,
                source="SYNTHETIC DEM (procedural demo terrain, not Mars data)",
                data_class=DataClass.SYNTHETIC,
                meta={"resolution_m": C.ANALYSIS_RES_M, "seed": seed, "crs": "Mars sphere R=3396190 m, lat/lon"})
