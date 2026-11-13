"""Mission parameters and the resource profile of a route (shared by modules 1, 14-17, 19, 20, 27)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

import config as C
from mars_survive.energy.model import RoverParams, traction
from mars_survive.oxygen.manager import AstronautParams, o2_lpm_from_power, walk_segments
from mars_survive.routing.planner import RouteResult


@dataclass
class MissionParams:
    name: str = "Jezero Delta EVA-1"
    scenario: str = "astronaut"          # "astronaut" | "rover"
    budget_h: float = 7.0                # life-support / operations window
    reserve_frac: float = 0.25
    slope_limit_deg: float = 20.0
    dwell_min: float = 30.0
    w_slope: float = 1.0
    w_hazard: float = 1.0
    w_energy: float = 1.0
    o2_capacity_l: float = 1400.0        # usable O2 at STP for one EVA (ASSUMPTION)
    algorithm: str = "astar"
    ml_blend: float = 0.0                # weight of the supervised traversability model in the hazard cost
    astronaut: AstronautParams = field(default_factory=AstronautParams)
    rover: RoverParams = field(default_factory=RoverParams)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "MissionParams":
        d = dict(d)
        a = AstronautParams(**d.pop("astronaut", {}))
        r = RoverParams(**d.pop("rover", {}))
        known = {k: v for k, v in d.items() if k in MissionParams.__dataclass_fields__}
        return MissionParams(**known, astronaut=a, rover=r)


def dose_rate_msv_h(elev_m):
    p_ratio = np.exp((np.asarray(elev_m, float) - C.RAD_GALE_ELEV_M) / C.SCALE_HEIGHT_M)
    return C.RAD_GALE_MSV_PER_DAY / 24.0 * p_ratio ** C.RAD_ELEV_EXPONENT


def resource_profile(route: RouteResult, rough_along: np.ndarray, mp: MissionParams, stop_idx: list[int] | None = None):
    """Per-point cumulative time, energy, O2 and dose along a route (+ dwell at stops)."""
    stop_idx = stop_idx or []
    d2 = np.diff(route.dist2d_m)
    dz = np.diff(route.elev)
    rough_seg = 0.5 * (rough_along[:-1] + rough_along[1:])
    if mp.scenario == "rover":
        seg = traction(d2, dz, rough_seg, mp.rover)
        work_w = mp.rover.p_idle_w + mp.rover.p_instr_w * 2
    else:
        seg = walk_segments(d2, dz, rough_seg, mp.astronaut)
        work_w = mp.astronaut.work_w
    dwell = np.zeros(len(route.nodes))
    for i in stop_idx:
        if 0 < i < len(dwell) - 1:
            dwell[i] = mp.dwell_min * 60
    t = np.concatenate([[0], np.cumsum(seg["t_s"])]) + np.cumsum(dwell)
    e = np.concatenate([[0], np.cumsum(seg["e_j"])]) + np.cumsum(dwell * work_w)
    power = np.concatenate([[seg["power_w"][0] if len(seg["power_w"]) else 0], seg["power_w"]])
    if mp.scenario == "astronaut":
        o2 = e / 1000 / C.O2_KJ_PER_L
    else:
        o2 = np.zeros_like(e)
    dt = np.diff(t, prepend=0)
    dose = np.cumsum(dt / 3600 * dose_rate_msv_h(route.elev))
    return {"t_s": t, "e_j": e, "o2_l": o2, "power_w": power, "dose_msv": dose, "dwell_s": dwell,
            "duration_h": float(t[-1] / 3600), "energy_kwh": float(e[-1] / 3.6e6), "o2_total_l": float(o2[-1]),
            "dose_total_msv": float(dose[-1])}


def power_series(route_profile: dict, step_s: float = 60.0):
    """Resample metabolic/electric power on a regular time grid (for telemetry)."""
    t = route_profile["t_s"]
    e = route_profile["e_j"]
    tt = np.arange(0, t[-1] + step_s, step_s)
    ee = np.interp(tt, t, e)
    pw = np.gradient(ee, tt)
    return tt, np.clip(pw, 50, None)


def o2_lpm(power_w):
    return o2_lpm_from_power(power_w)
