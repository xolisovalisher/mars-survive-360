"""Communication System (module 10): radio link budget and terrain line-of-sight.

Link budget (all in dB units):
  FSPL [dB]   = 20 log10(d) + 20 log10(f) + 20 log10(4 pi / c)
  EIRP [dBW]  = P_tx[dBW] + G_tx[dBi] - L_tx
  P_rx [dBW]  = EIRP - FSPL - L_atm - L_misc + G_rx
  N0 [dBW/Hz] = 10 log10(k T_sys)
  C/N0 [dBHz] = P_rx - N0 ;  Eb/N0 = C/N0 - 10 log10(R_b)
  Margin [dB] = Eb/N0 - (Eb/N0)_required - implementation loss
Mars atmosphere attenuation at UHF/X band is small (< 0.1 dB, dust storms up to ~1 dB at Ka);
it is a user parameter. Preset values are ILLUSTRATIVE, not mission specifications.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

import config as C


def db(x):
    return 10 * math.log10(x)


def fspl_db(d_m: float, f_hz: float) -> float:
    return 20 * math.log10(d_m) + 20 * math.log10(f_hz) + 20 * math.log10(4 * math.pi / C.C_LIGHT)


@dataclass
class LinkParams:
    name: str = "Rover/astronaut -> orbiter (UHF, illustrative)"
    freq_hz: float = 401.6e6
    p_tx_w: float = 8.0
    g_tx_dbi: float = 0.0
    g_rx_dbi: float = 3.0
    l_tx_db: float = 1.0
    l_atm_db: float = 0.1
    l_misc_db: float = 2.0
    t_sys_k: float = 600.0
    bitrate_bps: float = 256_000.0
    ebn0_req_db: float = 3.5          # e.g. rate-1/2 convolutional + RS at BER 1e-5 (approx.)
    impl_loss_db: float = 1.0
    distance_m: float = 1_000_000.0

    def as_dict(self):
        return asdict(self)


PRESETS = {
    "uhf_orbiter": LinkParams(),
    "base_vhf_local": LinkParams(name="Astronaut -> habitat (local UHF, illustrative)", freq_hz=437e6, p_tx_w=1.0,
                                 g_tx_dbi=0.0, g_rx_dbi=6.0, l_misc_db=3.0, t_sys_k=500, bitrate_bps=64_000,
                                 distance_m=5_000),
    "x_band_dte": LinkParams(name="Direct-to-Earth X band (illustrative)", freq_hz=8.4e9, p_tx_w=15.0, g_tx_dbi=25.0,
                             g_rx_dbi=74.0, l_misc_db=1.0, t_sys_k=30, bitrate_bps=2_000, l_atm_db=0.3,
                             distance_m=2.25e11),
}


def link_budget(p: LinkParams) -> dict:
    fspl = fspl_db(p.distance_m, p.freq_hz)
    eirp = db(p.p_tx_w) + p.g_tx_dbi - p.l_tx_db
    prx = eirp - fspl - p.l_atm_db - p.l_misc_db + p.g_rx_dbi
    n0 = db(C.K_BOLTZMANN * p.t_sys_k)
    cn0 = prx - n0
    ebn0 = cn0 - db(p.bitrate_bps)
    margin = ebn0 - p.ebn0_req_db - p.impl_loss_db
    max_rate = 10 ** ((cn0 - p.ebn0_req_db - p.impl_loss_db - 3.0) / 10)  # keep 3 dB margin
    return {"fspl_db": fspl, "eirp_dbw": eirp, "prx_dbw": prx, "prx_dbm": prx + 30, "n0_dbw_hz": n0,
            "cn0_dbhz": cn0, "ebn0_db": ebn0, "margin_db": margin, "max_rate_bps_3db": max_rate,
            "closes": margin >= 0, "status": "ok" if margin >= 3 else ("marginal" if margin >= 0 else "fail")}


def margin_vs_distance(p: LinkParams, d_min: float, d_max: float, n: int = 100):
    ds = np.geomspace(d_min, d_max, n)
    m = []
    for d in ds:
        q = LinkParams(**{**p.as_dict(), "distance_m": float(d)})
        m.append(link_budget(q)["margin_db"])
    return ds, np.array(m)


def radio_horizon_m(h1_m: float, h2_m: float = 0.0, R: float = C.R_MARS_MEAN) -> float:
    """Geometric horizon over a smooth sphere: sqrt(2 R h1) + sqrt(2 R h2)."""
    return math.sqrt(2 * R * max(h1_m, 0)) + math.sqrt(2 * R * max(h2_m, 0))


def terrain_los(g, lat1, lon1, h1_m, lat2, lon2, h2_m, n: int = 300) -> dict:
    """Line of sight between two antennas over the DEM, including Mars curvature drop d1*d2/(2R)."""
    from mars_survive.mapping.coords import haversine_m
    D = float(haversine_m(lat1, lon1, lat2, lon2))
    t = np.linspace(0, 1, n)
    lats, lons = lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t
    zt = np.array([g.sample(g.z, a, b) for a, b in zip(lats, lons)])
    if np.isnan(zt[0]) or np.isnan(zt[-1]):
        return {"visible": None, "reason": "endpoint_nodata", "distance_m": D}
    z1, z2 = zt[0] + h1_m, zt[-1] + h2_m
    d = t * D
    bulge = d * (D - d) / (2 * C.R_MARS_MEAN)
    ray = z1 + (z2 - z1) * t
    clearance = ray - (np.nan_to_num(zt, nan=-1e9) + bulge)
    inner = clearance[1:-1]
    unknown = bool(np.isnan(zt[1:-1]).any())
    return {"visible": bool(inner.min() > 0) if not unknown else None, "min_clearance_m": float(inner.min()),
            "distance_m": D, "dist": d, "terrain": zt + bulge, "ray": ray, "unknown_samples": unknown}


def visibility_along_route(g, route_lat, route_lon, base_lat, base_lon, ant_route_m=2.0, ant_base_m=10.0, step=3):
    vis = []
    for i in range(0, len(route_lat), step):
        r = terrain_los(g, route_lat[i], route_lon[i], ant_route_m, base_lat, base_lon, ant_base_m, n=120)
        vis.append((i, r["visible"], r["distance_m"]))
    return vis
