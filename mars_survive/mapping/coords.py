"""Mars coordinate systems and distances.

* Planetocentric latitude: angle from the equatorial plane at the planet's centre.
* Planetographic latitude: angle of the surface normal of the reference ellipsoid.
  tan(phi_g) = tan(phi_c) * (a/b)^2   (a = equatorial, b = polar radius)
* East-positive longitude (0..360 E, used by IAU/USGS for Mars) vs west-positive
  (0..360 W, used by older Viking-era products): lon_E = (360 - lon_W) mod 360.
"""
from __future__ import annotations

import math

import numpy as np

import config as C

A, B = C.R_MARS_EQ, C.R_MARS_POLAR


def centric_to_graphic(lat_c: float) -> float:
    if abs(lat_c) >= 90:
        return lat_c
    return math.degrees(math.atan(math.tan(math.radians(lat_c)) * (A / B) ** 2))


def graphic_to_centric(lat_g: float) -> float:
    if abs(lat_g) >= 90:
        return lat_g
    return math.degrees(math.atan(math.tan(math.radians(lat_g)) * (B / A) ** 2))


def east_to_west(lon_e: float) -> float:
    return (360.0 - lon_e) % 360.0


def west_to_east(lon_w: float) -> float:
    return (360.0 - lon_w) % 360.0


def to_pm180(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0


def haversine_m(lat1, lon1, lat2, lon2, R: float = C.R_MARS_MEAN):
    """Great-circle distance on a sphere (m). Works on scalars or numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def initial_bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def destination(lat, lon, bearing_deg, dist_m, R: float = C.R_MARS_MEAN):
    d = dist_m / R
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def parse_coordinate(text: str) -> tuple[float, float]:
    """Parse '18.44, 77.45' / '18.44N 77.45E' / '18.44 282.55W' -> (lat_c, lon_east)."""
    s = text.strip().upper().replace(",", " ").replace(";", " ")
    parts = [p for p in s.split() if p]
    if len(parts) != 2:
        raise ValueError("expected two numbers: latitude longitude")

    def num(p):
        sign = -1 if p.endswith(("S", "W")) else 1
        return sign * float(p.rstrip("NSEW°")), p.endswith("W")

    lat, _ = num(parts[0])
    lon, is_w = num(parts[1])
    if is_w:  # e.g. "282.55W" means west-positive 282.55 -> east 77.45
        lon = west_to_east(-lon)
    if not -90 <= lat <= 90:
        raise ValueError("latitude out of range")
    return lat, lon % 360 if lon > 180 else lon
