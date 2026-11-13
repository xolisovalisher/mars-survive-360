"""Energy Management (module 16): rover traction + power budget.

Traction force on a slope (Mars gravity):
  F = m g_M (C_rr cos(theta) + sin(theta))       [N]   (no regeneration downhill: F >= 0)
  P_mech = F v ;  P_elec = P_mech / eta + P_idle + P_instr      [W]
  E = sum(P_elec * dt)   [J]  -> Wh = J / 3600
Terrain resistance: C_rr scaled by (1 + k_rough * roughness) (ASSUMPTION).
Default rover values are ILLUSTRATIVE (Perseverance-class mass), user-editable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

import config as C


@dataclass
class RoverParams:
    mass_kg: float = 1025.0            # Perseverance launch mass of the rover (NASA)
    speed_ms: float = 0.042            # ~152 m/h top speed on flat ground (NASA, autonav)
    c_rr: float = 0.15                 # ASSUMPTION rolling resistance on regolith
    k_rough: float = 0.15              # ASSUMPTION extra resistance per metre roughness
    eta: float = 0.35                  # ASSUMPTION drive-train efficiency
    p_idle_w: float = 60.0             # ASSUMPTION avionics/heaters
    p_instr_w: float = 40.0            # ASSUMPTION instruments while driving
    motor_power_max_w: float = 250.0   # ASSUMPTION
    battery_wh: float = 2 * 43 * 28.0  # 2 x 43 Ah Li-ion at ~28 V (illustrative)
    reserve_frac: float = 0.3
    recharge_w: float = 110.0          # MMRTG electrical output at launch (~110 W, NASA)

    def as_dict(self):
        return asdict(self)


def traction(dh, dz, rough_m, p: RoverParams) -> dict:
    dh = np.asarray(dh, float)
    dz = np.asarray(dz, float)
    theta = np.arctan2(dz, np.maximum(dh, 1e-9))
    d3 = np.sqrt(dh ** 2 + dz ** 2)
    crr = p.c_rr * (1 + p.k_rough * np.asarray(rough_m, float))
    F = np.clip(p.mass_kg * C.G_MARS * (crr * np.cos(theta) + np.sin(theta)), 0, None)
    # speed derates when the motors saturate
    v = np.minimum(p.speed_ms, p.motor_power_max_w * p.eta / np.maximum(F, 1e-6))
    t = d3 / v
    p_elec = F * v / p.eta + p.p_idle_w + p.p_instr_w
    e = p_elec * t
    return {"t_s": t, "e_j": e, "power_w": p_elec, "force_n": F, "speed_ms": v, "theta_deg": np.degrees(theta)}


def battery_curve(t_s, e_j, p: RoverParams, recharge=True):
    """State of charge along the route (Wh), including RTG recharge while driving."""
    t = np.concatenate([[0], np.cumsum(t_s)])
    use = np.concatenate([[0], np.cumsum(e_j)]) / 3600
    gain = t / 3600 * p.recharge_w if recharge else 0 * t
    soc = np.clip(p.battery_wh - use + gain, None, p.battery_wh)
    return {"t_h": t / 3600, "soc_wh": soc, "min_soc_wh": float(soc.min()),
            "reserve_wh": p.battery_wh * p.reserve_frac}


def power_budget(e_j_total: float, duration_s: float, p: RoverParams) -> dict:
    wh = e_j_total / 3600
    gain = duration_s / 3600 * p.recharge_w
    net = wh - gain
    return {"energy_wh": wh, "rtg_gain_wh": gain, "net_wh": net, "battery_wh": p.battery_wh,
            "end_soc_wh": p.battery_wh - max(net, 0), "reserve_ok": p.battery_wh - max(net, 0) >= p.battery_wh * p.reserve_frac,
            "avg_power_w": e_j_total / max(duration_s, 1e-9)}
