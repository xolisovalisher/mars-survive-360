"""Risk Assessment (module 20): likelihood x impact matrix from computed metrics.

Each factor gets likelihood L (1..5) from documented thresholds on a metric and a
fixed impact I (1..5) reflecting consequence for crew safety. Score = L x I:
  1-4 low, 5-9 medium, 10-16 high, 20-25 critical.
"""
from __future__ import annotations

import pandas as pd

IMPACT = {"terrain": 4, "energy": 4, "oxygen": 5, "communication": 3, "navigation": 3, "environment": 3,
          "equipment": 3, "radiation": 2}
MITIGATION = {
    "terrain": "choose lowest-hazard route, raise slope margin, scout with rover/drone first",
    "energy": "increase battery reserve, shorten traverse, schedule RTG/solar recharge stops",
    "oxygen": "reduce dwell time, move stops closer, keep >= 25 % reserve, buddy-breathing kit",
    "communication": "plan stops inside relay windows, carry relay beacon, set comm-loss flight rule",
    "navigation": "add landmark/visual-odometry checkpoints, re-localise every 500 m",
    "environment": "avoid afternoon wind peak and dust events, check MEDA forecast",
    "equipment": "pre-EVA suit checks, spares, telemetry alert thresholds",
    "radiation": "check DONKI space weather; abort on solar particle event warning",
}


def _bucket(x, edges):
    """edges ascending: returns 1..5."""
    for k, e in enumerate(edges, start=1):
        if x <= e:
            return k
    return 5


def level(score: int) -> str:
    return "low" if score <= 4 else "medium" if score <= 9 else "high" if score <= 16 else "critical"


def assess(m: dict) -> pd.DataFrame:
    """m keys (any missing -> factor skipped):
    max_slope_frac (max slope / limit), hazard_mean, energy_margin_frac, o2_margin_frac,
    comm_availability, max_comm_gap_h, nav_final_sigma_m, env_level (low/medium/high),
    suit_alerts (count), dose_msv."""
    rows = []

    def add(f, metric, value, L, why):
        mkey = {"battery margin": "energy_battery", "EVA time-budget margin": "energy_time",
                "end-of-mission energy margin": "energy_end"}.get(metric, f) if f == "energy" else f
        rows.append({"factor": f, "mkey": mkey, "metric": metric, "value": value, "likelihood": L, "impact": IMPACT[f],
                     "score": L * IMPACT[f], "level": level(L * IMPACT[f]), "basis": why, "mitigation": MITIGATION[f]})

    if "max_slope_frac" in m:
        L = max(_bucket(m["max_slope_frac"], [0.3, 0.5, 0.7, 0.9]), _bucket(m.get("hazard_mean", 0), [0.1, 0.2, 0.35, 0.5]))
        add("terrain", "max slope / limit; mean hazard", f"{m['max_slope_frac']:.2f}; {m.get('hazard_mean', 0):.2f}", L,
            "L from slope ratio (<=.3,.5,.7,.9) and hazard index (<=.1,.2,.35,.5), max of both")
    if "energy_margin_frac" in m:
        add("energy", m.get("energy_metric", "end-of-mission energy margin"), f"{m['energy_margin_frac']:.0%}",
            6 - _bucket(m["energy_margin_frac"], [0.0, 0.1, 0.25, 0.4]), "margin <=0 ->5, <=10%->4, <=25%->3, <=40%->2, else 1")
    if "o2_margin_frac" in m:
        add("oxygen", "end-of-mission O2 margin", f"{m['o2_margin_frac']:.0%}",
            6 - _bucket(m["o2_margin_frac"], [0.0, 0.1, 0.25, 0.4]), "same bands as energy")
    if "comm_availability" in m:
        L = max(6 - _bucket(m["comm_availability"], [0.05, 0.1, 0.2, 0.4]), _bucket(m.get("max_comm_gap_h", 0), [1, 2, 4, 8]))
        add("communication", "relay availability; longest gap", f"{m['comm_availability']:.0%}; {m.get('max_comm_gap_h', 0):.1f} h",
            L, "availability (<=5%..40%) and gap (<=1,2,4,8 h), max of both")
    if "nav_final_sigma_m" in m:
        add("navigation", "final 1-sigma position error", f"{m['nav_final_sigma_m']:.1f} m",
            _bucket(m["nav_final_sigma_m"], [5, 15, 30, 60]), "<=5 m ->1 ... >60 m ->5")
    if "env_level" in m:
        add("environment", "MEDA environment level", m["env_level"], {"low": 1, "medium": 3, "high": 5}[m["env_level"]],
            "share of samples outside EVA bands")
    if "suit_alerts" in m:
        add("equipment", "suit telemetry alerts", str(m["suit_alerts"]), _bucket(m["suit_alerts"], [0, 1, 2, 3]),
            "0 alerts ->1, each alert +1")
    if "dose_msv" in m:
        L = _bucket(m["dose_msv"], [0.1, 0.3, 1, 3])
        why = "dose bands; SPE not modelled"
        sw = m.get("sw_level")
        if sw in ("medium", "high"):                    # NASA DONKI space-weather flag (module 13)
            L = max(L, {"medium": 3, "high": 5}[sw])
            why += f"; DONKI space-weather flag: {sw}"
        add("radiation", "EVA dose (model)", f"{m['dose_msv'] * 1000:.0f} µSv" + (f" · DONKI {sw}" if sw else ""), L, why)
    return pd.DataFrame(rows)


def overall(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"level": "unknown", "max_score": 0}
    mx = int(df["score"].max())
    return {"level": level(mx), "max_score": mx, "mean_score": float(df["score"].mean()),
            "top_factor": df.sort_values("score", ascending=False).iloc[0]["factor"]}
