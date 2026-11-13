"""Mars time and solar illumination: Allison & McEwen (2000, Planet. Space Sci. 48:215)
"Mars24" algorithm. Analytic, no kernels needed; used as a fallback for SPICE.

Inputs are UTC datetimes; longitudes east-positive (converted to west internally).
Accuracy: ~0.01 deg in Ls, a few seconds in local time (per the paper).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np

TT_MINUS_UTC = 69.184  # s, valid since 2017-01-01 (32.184 + 37 leap seconds)


def tt_minus_utc_astropy(dt: datetime) -> float | None:
    """TT − UTC from astropy's bundled IERS leap-second table (no network access); None if astropy is absent."""
    try:
        import warnings
        from astropy.time import Time
        from astropy.utils import iers
        iers.conf.auto_download = False
        iers.conf.auto_max_age = None
        with warnings.catch_warnings():        # ERFA "dubious year" for dates past the table's validity: the
            warnings.simplefilter("ignore")    # last known TT−UTC is still the right value (no new leap seconds)
            t = Time(dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt, scale="utc")
            return float((t.tt.jd1 - t.utc.jd1 + t.tt.jd2 - t.utc.jd2) * 86400.0)
    except Exception:  # noqa: BLE001
        return None


def tt_minus_utc(dt: datetime) -> float:
    """TT − UTC in seconds. Uses astropy's leap-second table when available (covers any date it knows),
    otherwise the built-in table (1999 → 2017-01-01, 37 leap seconds, still current)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    v = tt_minus_utc_astropy(dt)
    if v is not None and 30 < v < 120:
        return round(v, 3)
    return _tt_minus_utc_table(dt)


def _tt_minus_utc_table(dt: datetime) -> float:
    leaps = [(datetime(1999, 1, 1, tzinfo=timezone.utc), 32), (datetime(2006, 1, 1, tzinfo=timezone.utc), 33),
             (datetime(2009, 1, 1, tzinfo=timezone.utc), 34), (datetime(2012, 7, 1, tzinfo=timezone.utc), 35),
             (datetime(2015, 7, 1, tzinfo=timezone.utc), 36), (datetime(2017, 1, 1, tzinfo=timezone.utc), 37)]
    n = 32
    for d, k in leaps:
        if dt >= d:
            n = k
    return 32.184 + n


def julian_date_utc(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return 2440587.5 + dt.timestamp() / 86400.0


_PBS = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528),
        (0.0018, 32.8493, 49.095)]


def mars_time(dt: datetime, lon_east: float = 0.0) -> dict:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jd_ut = julian_date_utc(dt)
    jd_tt = jd_ut + tt_minus_utc(dt) / 86400.0
    d = jd_tt - 2451545.0
    M = (19.3871 + 0.52402073 * d) % 360
    a_fms = (270.3871 + 0.524038496 * d) % 360
    pbs = sum(A * math.cos(math.radians(0.985626 * d / tau + phi)) for A, tau, phi in _PBS)
    Mr = math.radians(M)
    nu_m = ((10.691 + 3.0e-7 * d) * math.sin(Mr) + 0.623 * math.sin(2 * Mr) + 0.050 * math.sin(3 * Mr)
            + 0.005 * math.sin(4 * Mr) + 0.0005 * math.sin(5 * Mr) + pbs)
    ls = (a_fms + nu_m) % 360
    lsr = math.radians(ls)
    eot = 2.861 * math.sin(2 * lsr) - 0.071 * math.sin(4 * lsr) + 0.002 * math.sin(6 * lsr) - nu_m  # deg
    mst = (24 * (((jd_tt - 2451549.5) / 1.0274912517) + 44796.0 - 0.0009626)) % 24
    lmst = (mst + lon_east / 15.0) % 24
    ltst = (lmst + eot / 15.0) % 24
    msd = (jd_tt - 2405522.0028779) / 1.0274912517
    dec = math.degrees(math.asin(0.42565 * math.sin(lsr))) + 0.25 * math.sin(lsr)
    subsolar_lon_w = (mst * 15 + eot + 180) % 360
    return {"jd_tt": jd_tt, "dt_j2000": d, "M": M, "alpha_fms": a_fms, "nu_minus_M": nu_m, "Ls": ls,
            "eot_deg": eot, "eot_min": eot * 4, "MST_h": mst, "LMST_h": lmst, "LTST_h": ltst, "MSD": msd,
            "solar_dec_deg": dec, "subsolar_lon_east": (360 - subsolar_lon_w) % 360}


def solar_elevation(dt: datetime, lat: float, lon_east: float) -> dict:
    m = mars_time(dt, lon_east)
    dec = math.radians(m["solar_dec_deg"])
    phi = math.radians(lat)
    lon_w = (360 - lon_east) % 360
    sub_w = (360 - m["subsolar_lon_east"]) % 360
    H = math.radians(lon_w - sub_w)
    cosz = math.sin(dec) * math.sin(phi) + math.cos(dec) * math.cos(phi) * math.cos(H)
    z = math.degrees(math.acos(max(-1, min(1, cosz))))
    # azimuth clockwise from north
    az = math.degrees(math.atan2(math.sin(-H) * math.cos(dec),
                                 math.cos(phi) * math.sin(dec) - math.sin(phi) * math.cos(dec) * math.cos(H))) % 360
    return {**m, "elevation_deg": 90 - z, "azimuth_deg": az}


def daylight_series(start: datetime, lat: float, lon_east: float, hours: float = 24.66, step_min: float = 10):
    ts = [start + timedelta(minutes=k * step_min) for k in range(int(hours * 60 / step_min) + 1)]
    el = np.array([solar_elevation(t, lat, lon_east)["elevation_deg"] for t in ts])
    lt = np.array([solar_elevation(t, lat, lon_east)["LTST_h"] for t in ts])
    return ts, el, lt


def season_name(ls: float, north: bool = True) -> str:
    names = ["spring", "summer", "autumn", "winter"] if north else ["autumn", "winter", "spring", "summer"]
    return names[int(ls // 90) % 4]
