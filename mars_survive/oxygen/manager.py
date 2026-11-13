"""Oxygen Management (module 15) + suited-walking physiology.

Metabolic cost of walking: Minetti et al. (2002, J. Appl. Physiol. 93:1039)
  C(i) = 280.5 i^5 - 58.7 i^4 - 76.8 i^3 + 51.9 i^2 + 19.6 i + 2.5   [J kg^-1 m^-1], |i| <= 0.45
Mars transfer (ASSUMPTION): C_Mars = C(i) * (g_Mars/g_Earth) * suit_factor, applied to
body + suit + payload mass. Walking speed: Tobler's hiking function rescaled to v_flat.
O2 consumption: V_O2 [L/min] = P_met [W] * 60 / (20.1 kJ/L * 1000).
Tank: ideal gas, p V = n R T  ->  m_O2 = p V M / (R T).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import config as C


def minetti_cost(grade):
    i = np.clip(grade, -0.45, 0.45)
    return 280.5 * i ** 5 - 58.7 * i ** 4 - 76.8 * i ** 3 + 51.9 * i ** 2 + 19.6 * i + 2.5


def tobler_speed(grade, v_flat):
    return v_flat * np.exp(-3.5 * (np.abs(grade + 0.05) - 0.05))


@dataclass
class AstronautParams:
    body_mass_kg: float = 75.0
    suit_mass_kg: float = 50.0       # ASSUMPTION
    payload_kg: float = 10.0
    suit_factor: float = 1.6         # ASSUMPTION
    v_flat_ms: float = 1.0           # ASSUMPTION (3.6 km/h)
    basal_w: float = 100.0
    work_w: float = 250.0            # metabolic rate while doing science at a stop (ASSUMPTION)

    @property
    def total_mass(self):
        return self.body_mass_kg + self.suit_mass_kg + self.payload_kg


def walk_segments(dh, dz, rough_m, p: AstronautParams):
    """Per-segment time (s), energy (J), mean metabolic power (W)."""
    dh = np.asarray(dh, float)
    dz = np.asarray(dz, float)
    grade = dz / np.maximum(dh, 1e-6)
    d3 = np.sqrt(dh ** 2 + dz ** 2)
    v = tobler_speed(grade, p.v_flat_ms) / (1 + 0.10 * np.asarray(rough_m, float))  # ASSUMPTION roughness
    t = d3 / v
    e = p.total_mass * minetti_cost(grade) * (C.G_MARS / C.G_EARTH) * p.suit_factor * d3 + p.basal_w * t
    return {"t_s": t, "e_j": e, "power_w": e / np.maximum(t, 1e-9), "grade": grade}


def o2_litres_from_energy(e_j):
    return np.asarray(e_j) / 1000.0 / C.O2_KJ_PER_L


def o2_lpm_from_power(power_w):
    return np.asarray(power_w) * 60.0 / (C.O2_KJ_PER_L * 1000.0)


def tank_o2_kg(pressure_kpa: float, volume_l: float, temp_k: float = 293.15) -> float:
    n = pressure_kpa * 1e3 * volume_l * 1e-3 / (C.R_GAS * temp_k)
    return n * C.M_O2


def o2_kg_to_litres_stp(kg: float) -> float:
    return kg * 1000.0 / C.O2_DENSITY_STP


@dataclass
class OxygenPlan:
    capacity_l: float           # usable O2 at STP, L
    emergency_reserve_frac: float
    mission_o2_l: float
    return_o2_l: float          # O2 needed to return from the farthest point
    duration_h: float

    def report(self) -> dict:
        usable = self.capacity_l * (1 - self.emergency_reserve_frac)
        remaining = usable - self.mission_o2_l
        rate = self.mission_o2_l / max(self.duration_h, 1e-9)        # L/h average
        return {
            "capacity_l": self.capacity_l, "usable_l": usable,
            "emergency_reserve_l": self.capacity_l * self.emergency_reserve_frac,
            "mission_o2_l": self.mission_o2_l, "remaining_l": remaining,
            "avg_rate_l_per_h": rate,
            "endurance_h": usable / rate if rate > 0 else float("inf"),
            "min_return_reserve_l": self.return_o2_l,
            "margin_frac": remaining / usable if usable > 0 else 0.0,
            "status": ("critical" if remaining < 0 else
                       "warning" if remaining < self.return_o2_l or remaining < 0.15 * usable else "ok"),
        }


def depletion_curve(t_s, cum_o2_l, capacity_l, reserve_frac):
    usable = capacity_l * (1 - reserve_frac)
    return {"t_h": np.asarray(t_s) / 3600, "remaining_l": usable - np.asarray(cum_o2_l), "usable_l": usable}
