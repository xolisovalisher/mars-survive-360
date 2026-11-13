"""MEDA Environmental Intelligence (module 13).

Imports Perseverance MEDA-like tables (PDS derived CSV or user CSV), maps columns
flexibly, computes statistics, detects anomalies (robust rolling z-score) and
derives an environmental hazard level for EVA. A SYNTHETIC diurnal sample is
provided only for demonstration and is always labelled as such.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd

from mars_survive.common import DataClass, ModuleError

ALIASES = {
    "time": ["time", "timestamp", "utc", "sclk", "lmst", "ltst", "local_time", "hour"],
    "air_temp_c": ["air_temp_c", "air_temperature", "ats", "atmos_temp", "air_temp", "temperature"],
    "ground_temp_c": ["ground_temp_c", "ground_temperature", "gts", "surface_temp"],
    "pressure_pa": ["pressure_pa", "pressure", "ps", "press"],
    "wind_speed_ms": ["wind_speed_ms", "wind_speed", "ws", "horizontal_wind_speed"],
    "wind_dir_deg": ["wind_dir_deg", "wind_direction", "wd"],
    "dust_tau": ["dust_tau", "opacity", "tau", "optical_depth"],
    "uv_index": ["uv_index", "uv", "rds_uv"],
}
LIMITS = {  # EVA comfort/safety bands - ASSUMPTIONS for planning, not suit specifications
    "air_temp_c": (-100.0, 10.0), "ground_temp_c": (-110.0, 30.0), "wind_speed_ms": (0.0, 15.0),
    "dust_tau": (0.0, 1.5), "pressure_pa": (500.0, 1100.0),
}


def synthetic_sample(sols: int = 3, step_min: int = 15, seed: int = 0) -> pd.DataFrame:
    """SYNTHETIC diurnal cycle with magnitudes typical of Jezero (not measured data)."""
    rng = np.random.default_rng(seed)
    n = int(sols * 24.66 * 60 / step_min)
    t = np.arange(n) * step_min / 60.0       # hours since start
    lt = t % 24.66
    ph = 2 * np.pi * (lt - 14.0) / 24.66
    air = -50 + 32 * np.cos(ph) + rng.normal(0, 1.5, n)
    ground = -45 + 45 * np.cos(ph) + rng.normal(0, 2, n)
    press = 720 + 15 * np.cos(2 * np.pi * (lt - 6) / 24.66) + rng.normal(0, 2, n)
    wind = np.clip(3 + 4 * np.clip(np.cos(ph), 0, None) + rng.gamma(2, 0.8, n), 0, None)
    wd = (180 + 60 * np.sin(ph) + rng.normal(0, 20, n)) % 360
    tau = 0.5 + 0.05 * np.sin(2 * np.pi * t / 60) + rng.normal(0, 0.01, n)
    air[int(n * 0.6)] += 25          # injected anomalies so detection can be demonstrated
    wind[int(n * 0.3)] += 18
    return pd.DataFrame({"time": t, "air_temp_c": air, "ground_temp_c": ground, "pressure_pa": press,
                         "wind_speed_ms": wind, "wind_dir_deg": wd, "dust_tau": tau})


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    low = {c.lower().strip(): c for c in df.columns}
    mapping = {}
    for std, al in ALIASES.items():
        for a in al:
            if a in low:
                mapping[std] = low[a]
                break
    if not any(k in mapping for k in ALIASES if k != "time"):
        raise ModuleError("err.meda_columns", ", ".join(df.columns[:12]))
    out = pd.DataFrame({k: pd.to_numeric(df[v], errors="coerce") if k != "time" else df[v] for k, v in mapping.items()})
    if "air_temp_c" in out and out["air_temp_c"].dropna().mean() > 100:   # Kelvin -> Celsius
        out["air_temp_c"] -= 273.15
    if "ground_temp_c" in out and out["ground_temp_c"].dropna().mean() > 100:
        out["ground_temp_c"] -= 273.15
    if "time" not in out:
        out["time"] = np.arange(len(out))
    return out, mapping


def read_csv(data: bytes) -> tuple[pd.DataFrame, dict]:
    try:
        df = pd.read_csv(io.BytesIO(data), comment="#", sep=None, engine="python", nrows=500_000)
    except Exception as e:  # noqa: BLE001
        raise ModuleError("err.csv_parse", str(e)) from e
    return normalize_columns(df)


def statistics(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ALIASES if c != "time" and c in df]
    return df[cols].describe(percentiles=[0.05, 0.5, 0.95]).T


def anomalies(df: pd.DataFrame, window: int = 24, z: float = 4.0) -> pd.DataFrame:
    """Robust rolling z-score (median / MAD). Returns rows flagged per variable."""
    rows = []
    for c in [c for c in ALIASES if c not in ("time", "wind_dir_deg") and c in df]:
        x = df[c].astype(float)
        med = x.rolling(window, center=True, min_periods=5).median()
        mad = (x - med).abs().rolling(window, center=True, min_periods=5).median() * 1.4826 + 1e-9
        zz = (x - med) / mad
        for i in np.where(np.abs(zz) > z)[0]:
            rows.append({"index": int(i), "time": df["time"].iloc[i], "variable": c, "value": float(x.iloc[i]),
                         "expected": float(med.iloc[i]), "z": float(zz.iloc[i])})
    return pd.DataFrame(rows)


def environment_risk(df: pd.DataFrame) -> dict:
    out = {}
    worst = 0
    for c, (lo, hi) in LIMITS.items():
        if c not in df or df[c].dropna().empty:
            continue
        x = df[c].dropna()
        frac = float(((x < lo) | (x > hi)).mean())
        lv = 0 if frac == 0 else (1 if frac < 0.1 else 2)
        worst = max(worst, lv)
        out[c] = {"min": float(x.min()), "max": float(x.max()), "outside_frac": frac, "level": lv, "band": [lo, hi]}
    return {"variables": out, "level": ["low", "medium", "high"][worst]}


DATA_CLASS_SAMPLE = DataClass.SYNTHETIC
