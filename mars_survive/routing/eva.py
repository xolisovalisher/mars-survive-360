"""EVA survival analysis: survival envelope and last safe turn-back point.

Directed time graph (uphill and downhill differ). Dijkstra from the base gives
T_out(cell); Dijkstra on the transposed graph gives T_ret(cell) = fastest time
back to the base. Envelope margin = usable budget - (T_out + work + T_ret).
Turn-back: margin_i = usable - (elapsed_i + T_ret(point_i)); last i with
margin >= 0 is the last safe turn-back point.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from mars_survive.dem.grid import Grid
from mars_survive.oxygen.manager import AstronautParams, walk_segments
from mars_survive.terrain.analysis import filled

from .planner import DIRS, crossed_cells


def time_graph(g: Grid, rough: np.ndarray, blocked: np.ndarray, p: AstronautParams, slope_limit: float):
    h, w = g.shape
    idx = np.arange(h * w).reshape(h, w)
    z = filled(g.z)
    rough = np.nan_to_num(rough, nan=0.0)
    src, dst, wt = [], [], []
    tan_lim = np.tan(np.radians(slope_limit))
    for dr, dc in DIRS:
        rs = slice(max(0, -dr), h - max(0, dr))
        cs = slice(max(0, -dc), w - max(0, dc))
        rd = slice(rs.start + dr, rs.stop + dr)
        cd = slice(cs.start + dc, cs.stop + dc)
        dx = g.dx_rows[rs][:, None] * abs(dc)
        dh = np.sqrt(dx ** 2 + (g.dy * abs(dr)) ** 2) * np.ones_like(z[rs, cs])
        dz = z[rd, cd] - z[rs, cs]
        m = walk_segments(dh, dz, 0.5 * (rough[rs, cs] + rough[rd, cd]), p)
        ok = ~blocked[rs, cs] & ~blocked[rd, cd] & (np.abs(dz / dh) <= tan_lim)
        cr = crossed_cells(dr, dc)
        if cr:
            (a1, b1), (a2, b2) = cr
            bp = np.pad(blocked, 2, constant_values=True)
            r0, c0 = rs.start + 2, cs.start + 2
            hh, ww = ok.shape
            x1 = bp[r0 + a1:r0 + a1 + hh, c0 + b1:c0 + b1 + ww]
            x2 = bp[r0 + a2:r0 + a2 + hh, c0 + b2:c0 + b2 + ww]
            ok &= ~(x1 | x2) if abs(dr) + abs(dc) == 3 else ~(x1 & x2)
        src.append(idx[rs, cs][ok])
        dst.append(idx[rd, cd][ok])
        wt.append(m["t_s"][ok])
    return csr_matrix((np.concatenate(wt) + 1e-6, (np.concatenate(src), np.concatenate(dst))), shape=(h * w, h * w))


def survival_fields(G, base: int):
    t_out = dijkstra(G, directed=True, indices=base)
    t_ret = dijkstra(G.T.tocsr(), directed=True, indices=base)
    return t_out, t_ret


def envelope_margin_h(t_out, t_ret, budget_h, reserve_frac, dwell_min, shape):
    usable = budget_h * 3600 * (1 - reserve_frac)
    return ((usable - (t_out + dwell_min * 60 + t_ret)) / 3600).reshape(shape)


def turnback(elapsed_s: np.ndarray, nodes: list[int], t_ret: np.ndarray, budget_h, reserve_frac) -> dict:
    usable = budget_h * 3600 * (1 - reserve_frac)
    ret = t_ret[np.asarray(nodes)]
    margin = usable - (np.asarray(elapsed_s) + ret)
    bad = np.where(margin < 0)[0]
    tbp = int(bad[0] - 1) if len(bad) and bad[0] > 0 else (0 if len(bad) else None)
    return {"return_s": ret, "margin_s": margin, "usable_s": usable, "tbp_idx": tbp,
            "feasible": len(bad) == 0, "min_margin_h": float(np.min(margin) / 3600)}
