"""Suit Telemetry (module 14): SIMULATION of a generic EVA suit (not a NASA suit).

Driven by the metabolic power profile of the planned route:
  O2 use      V_O2 = P_met * 60 / 20100  [L/min] ; tank pressure from p V = n R T
  CO2 output  ~ RQ * V_O2 (RQ = 0.85), scrubber capacity limits CO2 partial pressure
  Battery     P_suit = P_base + k * P_met (fans, pumps, comms)
  Cooling     heat load = metabolic power - work; water evaporation rate ~ load / 2.45 MJ/kg
Faults can be injected (O2 leak, fan failure, comm loss, battery degradation) to test alerts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

import config as C


@dataclass
class SuitParams:
    o2_tank_l: float = 2 * 3.9          # two bottles, water volume, L (ASSUMPTION)
    o2_tank_kpa: float = 6_200.0        # initial pressure (ASSUMPTION ~900 psi)
    o2_min_kpa: float = 600.0           # pressure for regulator + reserve
    suit_pressure_kpa: float = 29.6     # 4.3 psi pure O2 (typical US EVA suit)
    battery_wh: float = 1_100.0         # ASSUMPTION
    p_base_w: float = 70.0
    k_fan: float = 0.05
    water_kg: float = 3.6               # sublimator / evaporator feed water (ASSUMPTION)
    co2_capacity_l: float = 900.0       # scrubber capacity in L CO2 (ASSUMPTION)
    temp_setpoint_c: float = 21.0

    def as_dict(self):
        return asdict(self)


THRESHOLDS = {"o2_tank_kpa": ("min", 1200.0, 800.0), "battery_pct": ("min", 25.0, 10.0),
              "co2_kpa": ("max", 0.7, 1.0), "suit_temp_c": ("max", 27.0, 30.0),
              "water_kg": ("min", 0.8, 0.3), "suit_pressure_kpa": ("min", 28.5, 27.5)}


def simulate(t_s: np.ndarray, power_w: np.ndarray, p: SuitParams, faults: dict | None = None,
             comm_ok: np.ndarray | None = None, seed: int = 0) -> pd.DataFrame:
    """t_s, power_w: time stamps and metabolic power profile (from the route model)."""
    faults = faults or {}
    rng = np.random.default_rng(seed)
    t = np.asarray(t_s, float)
    pw = np.asarray(power_w, float)
    dt = np.diff(t, prepend=t[0])
    o2_lpm = pw * 60 / (C.O2_KJ_PER_L * 1000)
    leak_lpm = np.where(t >= faults.get("o2_leak_start_s", np.inf), faults.get("o2_leak_lpm", 0.0), 0.0)
    o2_used_l = np.cumsum((o2_lpm + leak_lpm) * dt / 60)
    n0 = p.o2_tank_kpa * 1e3 * p.o2_tank_l * 1e-3 / (C.R_GAS * 293.15)
    n_used = o2_used_l / 22.414
    tank = np.clip((n0 - n_used) * C.R_GAS * 293.15 / (p.o2_tank_l * 1e-3) / 1e3, 0, None)
    fan_fail = t >= faults.get("fan_fail_s", np.inf)
    p_suit = p.p_base_w + p.k_fan * pw * np.where(fan_fail, 0.2, 1.0)
    batt_wh = p.battery_wh * (1 - faults.get("battery_degradation", 0.0)) - np.cumsum(p_suit * dt / 3600)
    batt_pct = np.clip(100 * batt_wh / p.battery_wh, 0, 100)
    co2_l = np.cumsum(0.85 * o2_lpm * dt / 60)
    scrub_left = np.clip(1 - co2_l / p.co2_capacity_l, 0, 1)
    co2_kpa = 0.1 + 0.9 * (1 - scrub_left) ** 3 + np.where(fan_fail, 0.5, 0.0) + rng.normal(0, 0.01, len(t))
    heat = np.clip(pw - 60, 0, None)
    water = np.clip(p.water_kg - np.cumsum(heat * dt / 2.45e6), 0, None)
    temp = p.temp_setpoint_c + 0.004 * np.clip(pw - 300, 0, None) + np.where(fan_fail | (water <= 0), 6.0, 0.0) \
        + rng.normal(0, 0.15, len(t))
    hum = np.clip(35 + 0.02 * pw + np.where(fan_fail, 25, 0) + rng.normal(0, 1, len(t)), 0, 100)
    suit_p = p.suit_pressure_kpa - np.where(t >= faults.get("o2_leak_start_s", np.inf), 0.3, 0.0) \
        + rng.normal(0, 0.03, len(t))
    comm = np.ones(len(t), bool) if comm_ok is None else np.asarray(comm_ok, bool)
    if "comm_loss" in faults:
        a, b = faults["comm_loss"]
        comm = comm & ~((t >= a) & (t <= b))
    return pd.DataFrame({"t_h": t / 3600, "metabolic_w": pw, "o2_lpm": o2_lpm + leak_lpm, "o2_used_l": o2_used_l,
                         "o2_tank_kpa": tank, "suit_pressure_kpa": suit_p, "battery_pct": batt_pct,
                         "co2_kpa": co2_kpa, "suit_temp_c": temp, "humidity_pct": hum, "water_kg": water,
                         "comm_ok": comm})


def alerts(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, (kind, warn, crit) in THRESHOLDS.items():
        x = df[col].values
        for level, thr in (("CRITICAL", crit), ("WARNING", warn)):
            bad = x < thr if kind == "min" else x > thr
            if bad.any():
                i = int(np.argmax(bad))
                rows.append({"parameter": col, "level": level, "first_t_h": float(df["t_h"].iloc[i]),
                             "value": float(x[i]), "threshold": thr})
                break
    if (~df["comm_ok"]).any():
        i = int(np.argmax(~df["comm_ok"].values))
        rows.append({"parameter": "comm_ok", "level": "WARNING", "first_t_h": float(df["t_h"].iloc[i]),
                     "value": 0.0, "threshold": 1.0})
    return pd.DataFrame(rows)


def anomaly_scores(df: pd.DataFrame, cols=("o2_lpm", "suit_temp_c", "co2_kpa", "humidity_pct", "suit_pressure_kpa")):
    """Isolation Forest on telemetry channels (unsupervised ML, trained on this run)."""
    from sklearn.ensemble import IsolationForest
    X = df[list(cols)].values
    m = IsolationForest(n_estimators=150, contamination=0.02, random_state=0).fit(X)
    return -m.score_samples(X), m.predict(X) == -1


def safety_status(al: pd.DataFrame) -> str:
    if al.empty:
        return "nominal"
    return "abort" if (al["level"] == "CRITICAL").any() else "caution"
