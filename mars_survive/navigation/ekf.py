"""Autonomous Navigation (module 8): 2-D rover localisation without GPS.

State x = [x_east, y_north, heading]  (m, m, rad; heading 0 = east, CCW+).
Prediction (unicycle model) from wheel odometry speed v and gyroscope yaw rate w:
  x' = x + v dt cos(th), y' = y + v dt sin(th), th' = th + w dt
  F = [[1,0,-v dt sin th],[0,1,v dt cos th],[0,0,1]],  Q from odometry/gyro noise.
Update with range-bearing observations of known landmarks (e.g. surveyed rocks /
features matched by visual odometry):
  z = [sqrt(dx^2+dy^2), atan2(dy,dx) - th] ; H = Jacobian ; standard EKF update.
Wheel slip on sand is modelled as a multiplicative speed bias (ASSUMPTION).
All sensor data here are SYNTHETIC SIMULATION unless the user uploads logs.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


@dataclass
class NavParams:
    dt: float = 1.0
    odo_sigma: float = 0.02          # relative speed noise
    slip_bias: float = 0.05          # 5 % wheel slip (odometry over-reads)
    gyro_sigma_deg_s: float = 0.005     # angle random walk-like white noise per step
    gyro_bias_deg_s: float = 0.0003     # ~1 deg/h (navigation-grade IMU class, ASSUMPTION)
    vo_enabled: bool = True          # visual odometry: corrects slip partly
    vo_sigma: float = 0.01
    range_sigma_m: float = 1.0
    bearing_sigma_deg: float = 1.0
    landmark_range_m: float = 80.0
    seed: int = 1


def path_to_controls(x_m: np.ndarray, y_m: np.ndarray, speed: float, dt: float):
    """Resample a planned route (local metres) into true poses + controls at constant speed."""
    seg = np.hypot(np.diff(x_m), np.diff(y_m))
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(int(s[-1] / (speed * dt)), 2)
    ss = np.linspace(0, s[-1], n)
    xs, ys = np.interp(ss, s, x_m), np.interp(ss, s, y_m)
    th = np.unwrap(np.arctan2(np.gradient(ys), np.gradient(xs)))
    v = np.hypot(np.diff(xs), np.diff(ys)) / dt
    w = np.diff(th) / dt
    return np.stack([xs, ys, th], 1), v, w


def simulate(true_pose, v, w, landmarks, p: NavParams):
    rng = np.random.default_rng(p.seed)
    n = len(v)
    gyro_sig, gyro_b = np.radians(p.gyro_sigma_deg_s), np.radians(p.gyro_bias_deg_s)
    odo = v * (1 + p.slip_bias) * (1 + p.odo_sigma * rng.standard_normal(n))
    if p.vo_enabled:  # VO measures true displacement with small noise -> fuse 50/50 with odometry
        vo = v * (1 + p.vo_sigma * rng.standard_normal(n))
        odo = 0.5 * odo + 0.5 * vo
        speed_sig = 0.5 * np.hypot(p.odo_sigma + p.slip_bias, p.vo_sigma)
    else:
        speed_sig = p.odo_sigma + p.slip_bias
    gyro = w + gyro_b + gyro_sig * rng.standard_normal(n)

    x_dr = np.zeros((n + 1, 3))
    x_dr[0] = true_pose[0]
    x = true_pose[0].astype(float).copy()
    P = np.diag([0.5 ** 2, 0.5 ** 2, np.radians(1) ** 2])
    est = np.zeros((n + 1, 3))
    covs = np.zeros((n + 1, 3, 3))
    est[0], covs[0] = x, P
    R = np.diag([p.range_sigma_m ** 2, np.radians(p.bearing_sigma_deg) ** 2])
    n_updates = 0
    nis = []
    L = np.asarray(landmarks, float).reshape(-1, 2)
    for k in range(n):
        dt = p.dt
        # dead reckoning
        th = x_dr[k, 2]
        x_dr[k + 1] = x_dr[k] + [odo[k] * dt * np.cos(th), odo[k] * dt * np.sin(th), gyro[k] * dt]
        # EKF predict
        th = x[2]
        x = x + np.array([odo[k] * dt * np.cos(th), odo[k] * dt * np.sin(th), gyro[k] * dt])
        F = np.array([[1, 0, -odo[k] * dt * np.sin(th)], [0, 1, odo[k] * dt * np.cos(th)], [0, 0, 1]])
        G = np.array([[dt * np.cos(th), 0], [dt * np.sin(th), 0], [0, dt]])
        Qu = np.diag([(speed_sig * max(abs(odo[k]), 1e-3)) ** 2, (gyro_sig + gyro_b) ** 2])
        P = F @ P @ F.T + G @ Qu @ G.T
        # EKF update with visible landmarks
        tp = true_pose[k + 1]
        vis = np.where(np.hypot(L[:, 0] - tp[0], L[:, 1] - tp[1]) <= p.landmark_range_m)[0] if len(L) else []
        for j in vis:
            lx, ly = L[j]
            dxt, dyt = lx - tp[0], ly - tp[1]
            rt = np.hypot(dxt, dyt)
            zm = np.array([rt + p.range_sigma_m * rng.standard_normal(),
                           wrap(np.arctan2(dyt, dxt) - tp[2] + np.radians(p.bearing_sigma_deg) * rng.standard_normal())])
            dx_, dy_ = lx - x[0], ly - x[1]
            q = dx_ ** 2 + dy_ ** 2
            r = np.sqrt(q)
            zh = np.array([r, wrap(np.arctan2(dy_, dx_) - x[2])])
            H = np.array([[-dx_ / r, -dy_ / r, 0], [dy_ / q, -dx_ / q, -1]])
            S = H @ P @ H.T + R
            K = P @ H.T @ np.linalg.inv(S)
            innov = zm - zh
            innov[1] = wrap(innov[1])
            nis.append(float(innov @ np.linalg.inv(S) @ innov))
            x = x + K @ innov
            x[2] = wrap(x[2])
            P = (np.eye(3) - K @ H) @ P
            n_updates += 1
        est[k + 1], covs[k + 1] = x, P
    return {"true": true_pose, "dr": x_dr, "ekf": est, "cov": covs, "n_updates": n_updates,
            "nis_mean": float(np.mean(nis)) if nis else None}


def landmarks_along(true_pose, spacing_m=150.0, offset_m=25.0, seed=3):
    rng = np.random.default_rng(seed)
    xs, ys = true_pose[:, 0], true_pose[:, 1]
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
    out = []
    for d in np.arange(spacing_m / 2, s[-1], spacing_m):
        i = int(np.searchsorted(s, d))
        side = rng.choice([-1, 1])
        th = true_pose[min(i, len(xs) - 1), 2]
        out.append((xs[i] - side * offset_m * np.sin(th), ys[i] + side * offset_m * np.cos(th)))
    return out
