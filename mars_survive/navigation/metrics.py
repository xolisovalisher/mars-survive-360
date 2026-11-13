"""Navigation Intelligence (module 9): accuracy and uncertainty metrics."""
from __future__ import annotations

import numpy as np

from .ekf import wrap


def errors(true, est):
    e = np.hypot(est[:, 0] - true[:, 0], est[:, 1] - true[:, 1])
    he = np.degrees(np.abs(wrap(est[:, 2] - true[:, 2])))
    return e, he


def summarize(sim: dict) -> dict:
    t = sim["true"]
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(t[:, 0]), np.diff(t[:, 1])))])
    out = {}
    for k in ("dr", "ekf"):
        e, he = errors(t, sim[k])
        out[k] = {"rmse_m": float(np.sqrt(np.mean(e ** 2))), "final_error_m": float(e[-1]),
                  "max_error_m": float(e.max()), "drift_pct": float(100 * e[-1] / max(s[-1], 1e-9)),
                  "heading_rmse_deg": float(np.sqrt(np.mean(he ** 2)))}
    P = sim["cov"]
    sig_pos = np.sqrt(np.maximum(P[:, 0, 0] + P[:, 1, 1], 0))
    out["ekf"]["position_sigma_final_m"] = float(sig_pos[-1])
    out["ekf"]["heading_sigma_final_deg"] = float(np.degrees(np.sqrt(max(P[-1, 2, 2], 0))))
    # sensor confidence: share of steps where the true error is inside the 2-sigma circle
    e, _ = errors(t, sim["ekf"])
    out["ekf"]["consistency_2sigma"] = float(np.mean(e <= 2 * sig_pos + 1e-9))
    out["path_length_m"] = float(s[-1])
    out["landmark_updates"] = sim["n_updates"]
    out["nis_mean"] = sim["nis_mean"]
    return out


def error_ellipse(P2: np.ndarray, n_sigma: float = 2.0, n: int = 60):
    vals, vecs = np.linalg.eigh(P2)
    vals = np.maximum(vals, 0)
    a = np.linspace(0, 2 * np.pi, n)
    circ = np.stack([np.cos(a), np.sin(a)])
    return (vecs @ np.diag(n_sigma * np.sqrt(vals)) @ circ).T


def trajectory_deviation(planned_xy: np.ndarray, est_xy: np.ndarray) -> np.ndarray:
    """Cross-track distance of each estimated point to the planned polyline (m)."""
    a, b = planned_xy[:-1], planned_xy[1:]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.empty(len(est_xy))
    for i, p in enumerate(est_xy):
        t = np.clip(((p - a) * ab).sum(1) / L2, 0, 1)
        proj = a + t[:, None] * ab
        out[i] = np.min(np.hypot(*(proj - p).T))
    return out
