"""Mission Timeline (module 17): phases built from the route, stops and relay windows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

PHASES = ["start", "movement", "observation", "communication", "rest", "return", "emergency"]


def build(profile: dict, cuts: list[int], comm_windows: list[dict] | None = None, prep_min: float = 20,
          rest_every_h: float = 2.0, rest_min: float = 10, start: datetime | None = None) -> pd.DataFrame:
    """cuts = indices of [start, stop1, ..., last] along the route. Last leg = return."""
    start = start or datetime(2035, 1, 1, 8, 0, tzinfo=timezone.utc)
    t = profile["t_s"]
    dwell = profile["dwell_s"]
    rows = [{"phase": "start", "label": "EVA prep / egress", "start_s": 0.0, "end_s": prep_min * 60}]
    off = prep_min * 60
    nleg = len(cuts) - 1
    rest_acc = 0.0
    for k in range(nleg):
        a, b = cuts[k], cuts[k + 1]
        move_start = t[a] + (dwell[a] if k > 0 else 0)
        move_end = t[b] - dwell[b]
        phase = "return" if k == nleg - 1 and nleg > 1 else "movement"
        # insert rests during long legs
        s = move_start
        while move_end - s > rest_every_h * 3600 - rest_acc:
            e = s + rest_every_h * 3600 - rest_acc
            rows.append({"phase": phase, "label": f"Leg {k + 1}", "start_s": off + s, "end_s": off + e})
            rows.append({"phase": "rest", "label": "Rest", "start_s": off + e, "end_s": off + e + rest_min * 60})
            off += rest_min * 60
            s, rest_acc = e, 0.0
        rows.append({"phase": phase, "label": f"Leg {k + 1}", "start_s": off + s, "end_s": off + move_end})
        rest_acc += move_end - s
        if dwell[b] > 0:
            rows.append({"phase": "observation", "label": f"Stop {k + 1} science", "start_s": off + move_end,
                         "end_s": off + t[b]})
    end = rows[-1]["end_s"]
    for w in comm_windows or []:
        if w["start_s"] < end:
            rows.append({"phase": "communication", "label": f"Relay pass {w.get('orbiter', '')}".strip(),
                         "start_s": w["start_s"], "end_s": min(w["end_s"], end)})
    df = pd.DataFrame(rows)
    df["start"] = [start + timedelta(seconds=float(s)) for s in df["start_s"]]
    df["end"] = [start + timedelta(seconds=float(s)) for s in df["end_s"]]
    df["duration_min"] = (df["end_s"] - df["start_s"]) / 60
    return df.sort_values("start_s").reset_index(drop=True)


def resource_over_time(profile: dict, o2_capacity_l: float, battery_wh: float | None = None):
    t_h = profile["t_s"] / 3600
    out = {"t_h": t_h, "o2_remaining_l": o2_capacity_l - profile["o2_l"]}
    if battery_wh:
        out["energy_remaining_wh"] = battery_wh - profile["e_j"] / 3600
    return out


def emergency_return_time(profile: dict, t_ret_s: np.ndarray, nodes: list[int]) -> np.ndarray:
    return t_ret_s[np.asarray(nodes)]
