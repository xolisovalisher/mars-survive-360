"""NASA DONKI (Space Weather Database Of Notifications, Knowledge, Information) client and Mars-EVA relevance.

API: https://api.nasa.gov/DONKI/<TYPE>?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&api_key=KEY
Types used: FLR (solar flares), SEP (solar energetic particles), CME (coronal mass ejections, incl. WSA-ENLIL
model impact lists that may name Mars or Mars spacecraft), GST (geomagnetic storms — Earth only, shown for context).

Honest limits: DONKI is Earth/heliosphere-centric. A flare or SEP observed from Earth is not necessarily
Mars-directed; only CME ENLIL impact entries that mention Mars/MAVEN/Perseverance/Curiosity are treated as
Mars-relevant. The derived EVA radiation flag is a planning heuristic, not a dose forecast.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from mars_survive.common import ModuleError
from mars_survive.nasa_live import http

BASE = "https://api.nasa.gov/DONKI"
TYPES = ["FLR", "SEP", "CME", "GST"]
MARS_WORDS = ("mars", "maven", "perseverance", "curiosity", "msl", "m2020", "insight", "tianwen")


def api_key() -> str:
    return os.environ.get("NASA_API_KEY") or "DEMO_KEY"


def fetch(kind: str, start: date, end: date, use_cache=True) -> dict:
    """Return {"data_class", "fetched_utc", "source", "payload": list}. Raises ModuleError on failure."""
    if kind not in TYPES:
        raise ModuleError("err.invalid", kind)
    if end < start or (end - start).days > 366:
        raise ModuleError("err.invalid", "date range must be 0..366 days")
    key = f"{kind}:{start}:{end}"
    if use_cache:
        c = http.cache_load("donki", key, max_age_h=6)
        if c:
            return c
    params = {"startDate": start.isoformat(), "endDate": end.isoformat(), "api_key": api_key()}
    payload = http.get_json(f"{BASE}/{kind}", params=params)
    if payload in (None, ""):
        payload = []
    if not isinstance(payload, list):
        raise ModuleError("err.bad_json", "DONKI response is not a list")
    http.cache_save("donki", key, payload, "Real", f"{BASE}/{kind}")
    return http.cache_load("donki", key)


def _t(s):
    if not s:
        return pd.NaT
    try:
        return pd.Timestamp(str(s).replace("Z", "")).tz_localize(None)
    except Exception:  # noqa: BLE001
        return pd.NaT


def _mars_impacts(cme: dict) -> list[dict]:
    out = []
    for an in cme.get("cmeAnalyses") or []:
        for en in an.get("enlilList") or []:
            for imp in en.get("impactList") or []:
                loc = str(imp.get("location", ""))
                if any(w in loc.lower() for w in MARS_WORDS):
                    out.append({"location": loc, "arrival": _t(imp.get("arrivalTime")),
                                "glancing": bool(imp.get("isGlancingBlow"))})
    return out


def normalize(kind: str, payload: list) -> pd.DataFrame:
    """Flatten DONKI records into one table: kind, id, time, magnitude, detail, mars_relevant, mars_arrival."""
    rows = []
    for e in payload or []:
        if not isinstance(e, dict):
            continue
        if kind == "FLR":
            rows.append({"kind": "FLR", "id": e.get("flrID"), "time": _t(e.get("peakTime") or e.get("beginTime")),
                         "magnitude": e.get("classType"), "detail": e.get("sourceLocation") or "",
                         "mars_relevant": False, "mars_arrival": pd.NaT})
        elif kind == "SEP":
            inst = ", ".join(i.get("displayName", "") for i in e.get("instruments") or [])
            rows.append({"kind": "SEP", "id": e.get("sepID"), "time": _t(e.get("eventTime")), "magnitude": "SEP",
                         "detail": inst, "mars_relevant": any(w in inst.lower() for w in MARS_WORDS),
                         "mars_arrival": pd.NaT})
        elif kind == "CME":
            speeds = [a.get("speed") for a in e.get("cmeAnalyses") or [] if a.get("speed")]
            imps = _mars_impacts(e)
            rows.append({"kind": "CME", "id": e.get("activityID"), "time": _t(e.get("startTime")),
                         "magnitude": f"{max(speeds):.0f} km/s" if speeds else "",
                         "detail": e.get("sourceLocation") or "", "mars_relevant": bool(imps),
                         "mars_arrival": min((i["arrival"] for i in imps if pd.notna(i["arrival"])), default=pd.NaT)})
        elif kind == "GST":
            kps = [k.get("kpIndex") for k in e.get("allKpIndex") or [] if k.get("kpIndex") is not None]
            rows.append({"kind": "GST", "id": e.get("gstID"), "time": _t(e.get("startTime")),
                         "magnitude": f"Kp {max(kps):g}" if kps else "", "detail": "Earth geomagnetic storm",
                         "mars_relevant": False, "mars_arrival": pd.NaT})
    df = pd.DataFrame(rows, columns=["kind", "id", "time", "magnitude", "detail", "mars_relevant", "mars_arrival"])
    return df.sort_values("time", ascending=False, na_position="last").reset_index(drop=True)


def flare_class_rank(c: str) -> float:
    """'X1.2' → 1.2e-4 W/m² style rank (A..X log scale); unknown → 0."""
    try:
        base = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}[str(c)[0].upper()]
        return base * float(str(c)[1:] or 1)
    except Exception:  # noqa: BLE001
        return 0.0


@dataclass
class SpaceWeatherAssessment:
    level: str                 # low | medium | high
    reasons: list
    counts: dict
    window: tuple


def assess(df: pd.DataFrame, eva_time: datetime | None = None, lookback_days: int = 3) -> SpaceWeatherAssessment:
    """EVA radiation flag from recent events (heuristic, documented):
    high   — a Mars-relevant CME arrival within ±1 day of the EVA, or any SEP event in the look-back window;
    medium — an X-class flare or a CME ≥ 1000 km/s in the window (direction to Mars unknown);
    low    — otherwise."""
    if eva_time is None:
        eva_time = datetime.now(timezone.utc).replace(tzinfo=None)
    t1 = pd.Timestamp(eva_time)
    t0 = t1 - pd.Timedelta(days=lookback_days)
    w = df[(df["time"] >= t0) & (df["time"] <= t1 + pd.Timedelta(days=1))] if len(df) else df
    reasons, level = [], "low"
    arr = df[df["mars_relevant"] & df["mars_arrival"].notna()] if len(df) else df
    near = arr[(arr["mars_arrival"] - t1).abs() <= pd.Timedelta(days=1)] if len(arr) else arr
    if len(near):
        level = "high"
        reasons.append(("sw.r_cme_mars", {"n": len(near)}))
    sep = w[w["kind"] == "SEP"] if len(w) else w
    if len(sep):
        level = "high"
        reasons.append(("sw.r_sep", {"n": len(sep)}))
    if level != "high" and len(w):
        xf = w[(w["kind"] == "FLR") & (w["magnitude"].map(flare_class_rank) >= 1e-4)]
        fast = w[(w["kind"] == "CME") & (w["magnitude"].str.replace(" km/s", "", regex=False)
                                          .apply(pd.to_numeric, errors="coerce") >= 1000)]
        if len(xf) or len(fast):
            level = "medium"
            if len(xf):
                reasons.append(("sw.r_xflare", {"n": len(xf)}))
            if len(fast):
                reasons.append(("sw.r_fastcme", {"n": len(fast)}))
    if not reasons:
        reasons.append(("sw.r_quiet", {}))
    counts = {k: int((w["kind"] == k).sum()) if len(w) else 0 for k in TYPES}
    return SpaceWeatherAssessment(level, reasons, counts, (t0.to_pydatetime(), t1.to_pydatetime()))


def example_payloads() -> dict:
    """Bundled SYNTHETIC examples in DONKI's JSON format (for offline demos/tests; not NASA data)."""
    import json
    from pathlib import Path
    p = Path(__file__).with_name("examples") / "donki_example_synthetic.json"
    return json.loads(p.read_text(encoding="utf-8"))
