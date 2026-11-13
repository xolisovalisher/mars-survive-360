"""Regular latitude/longitude elevation grid on the Mars sphere.

Conventions (documented in docs/scientific_methods):
* latitude  = planetocentric, degrees north;
* longitude = east-positive, degrees (0..360 or -180..180 both accepted);
* row 0 is the northernmost row; cell values are cell centres.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

import config as C
from mars_survive.common import DataClass


@dataclass
class Grid:
    z: np.ndarray                  # elevation, metres, NaN = NoData
    lat_top: float                 # latitude of the centre of row 0
    lon_left: float                # longitude of the centre of column 0
    dlat: float                    # degrees per row (>0)
    dlon: float                    # degrees per column (>0)
    source: str
    data_class: DataClass
    thermal: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    # ---- geometry ----------------------------------------------------
    @property
    def shape(self):
        return self.z.shape

    @property
    def is_real(self) -> bool:
        return self.data_class in (DataClass.REAL, DataClass.USER)

    def lat(self, r):
        return self.lat_top - np.asarray(r) * self.dlat

    def lon(self, c):
        return self.lon_left + np.asarray(c) * self.dlon

    def rowcol(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(round((self.lat_top - lat) / self.dlat)),
                int(round((lon - self.lon_left) / self.dlon)))

    def inside(self, r: int, c: int) -> bool:
        h, w = self.shape
        return 0 <= r < h and 0 <= c < w

    def valid(self, r: int, c: int) -> bool:
        return self.inside(r, c) and bool(np.isfinite(self.z[r, c]))

    @property
    def bounds(self):
        """[[south, west], [north, east]] of the pixel edges (Leaflet order)."""
        h, w = self.shape
        return [[self.lat_top - (h - 0.5) * self.dlat, self.lon_left - 0.5 * self.dlon],
                [self.lat_top + 0.5 * self.dlat, self.lon_left + (w - 0.5) * self.dlon]]

    @property
    def center(self):
        (s, w), (n, e) = self.bounds
        return (s + n) / 2, (w + e) / 2

    @property
    def dy(self) -> float:
        """North-south cell size, m."""
        return C.R_MARS_DTM * math.radians(self.dlat)

    @property
    def dx_rows(self) -> np.ndarray:
        """East-west cell size per row, m (shrinks with cos(latitude))."""
        lats = np.radians(self.lat(np.arange(self.shape[0])))
        return C.R_MARS_DTM * math.radians(self.dlon) * np.cos(lats)

    def sample(self, arr: np.ndarray, lat: float, lon: float) -> float:
        """Bilinear sample of a raster on this grid (NaN outside)."""
        fr = (self.lat_top - lat) / self.dlat
        fc = (lon - self.lon_left) / self.dlon
        r0, c0 = int(math.floor(fr)), int(math.floor(fc))
        h, w = arr.shape
        if r0 < 0 or c0 < 0 or r0 + 1 >= h or c0 + 1 >= w:
            return float("nan")
        tr, tc = fr - r0, fc - c0
        q = arr[r0:r0 + 2, c0:c0 + 2].astype(float)
        return float((q[0, 0] * (1 - tc) + q[0, 1] * tc) * (1 - tr) + (q[1, 0] * (1 - tc) + q[1, 1] * tc) * tr)

    def cell_area_km2(self) -> float:
        return self.dy * float(np.mean(self.dx_rows)) / 1e6
