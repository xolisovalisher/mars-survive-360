"""Route Planning (module 5): grid search with A*, Weighted A* and Dijkstra.

Graph: every valid cell is a node with 16 neighbours (8 king + 8 knight moves);
the knight moves reduce the octagonal grid-metric error from 8.2 % to 2.75 %.
Edge length is 3-D: sqrt(d_h^2 + dz^2) with d_h from the true cell sizes.

Strategies (edge cost = d3 * factor, factor >= 1, so the straight-line distance
is an admissible A* heuristic):
  shortest       factor = 1
  lowest_slope   factor = 1 + w_s * 4 * (slope/limit)^2
  lowest_hazard  factor = 1 + w_h * 6 * H                (H = hazard index 0..1)
  balanced       factor = 1 + w_s*1.5*(slope/limit)^2 + w_h*2.5*H + w_e*E,
  (with an ML model, H = (1-a)*H_rules + a*P_ml(non-traversable), a = ml_blend)
                 E = max(grade, 0) * 5  (penalises climbing = energy)
Impassable: NoData, edge slope > limit, cells with level no-go or unknown.
Unknown / NoData terrain is NEVER treated as safe.
"""
from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field

import numpy as np

from mars_survive.dem.grid import Grid
from mars_survive.terrain.analysis import filled

DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1),
        (-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]


def crossed_cells(dr: int, dc: int) -> list[tuple[int, int]]:
    """Cells a move passes through (besides start/end). Knight moves cross two cells,
    diagonal moves touch two orthogonal neighbours (corner)."""
    sr, sc = (dr > 0) - (dr < 0), (dc > 0) - (dc < 0)
    if abs(dr) == 2:
        return [(sr, 0), (sr, dc)]
    if abs(dc) == 2:
        return [(0, sc), (dr, sc)]
    if dr and dc:
        return [(dr, 0), (0, dc)]
    return []


STRATEGIES = ["shortest", "lowest_slope", "lowest_hazard", "balanced"]
ALGORITHMS = ["astar", "weighted_astar", "dijkstra"]


@dataclass
class RouteParams:
    slope_limit_deg: float = 20.0
    w_slope: float = 1.0
    w_hazard: float = 1.0
    w_energy: float = 1.0
    ml_blend: float = 0.0         # 0 = rule hazard only, 1 = ML P(non-traversable) only
    epsilon: float = 1.5          # inflation for Weighted A*
    max_expansions: int = 2_000_000


@dataclass
class RouteResult:
    strategy: str
    algorithm: str
    found: bool
    nodes: list = field(default_factory=list)
    lat: np.ndarray | None = None
    lon: np.ndarray | None = None
    elev: np.ndarray | None = None
    dist2d_m: np.ndarray | None = None   # cumulative
    dist3d_m: np.ndarray | None = None   # cumulative
    slope_deg: np.ndarray | None = None  # per point (segment ending at point)
    hazard: np.ndarray | None = None
    cost: float = math.inf
    expanded: int = 0
    compute_s: float = 0.0
    reason: str = ""

    def summary(self) -> dict:
        if not self.found:
            return {"strategy": self.strategy, "found": False, "reason": self.reason}
        return {"strategy": self.strategy, "algorithm": self.algorithm, "found": True,
                "distance_2d_km": float(self.dist2d_m[-1] / 1000), "distance_3d_km": float(self.dist3d_m[-1] / 1000),
                "mean_slope_deg": float(np.mean(self.slope_deg[1:])) if len(self.slope_deg) > 1 else 0.0,
                "max_slope_deg": float(np.max(self.slope_deg)), "hazard_mean": float(np.mean(self.hazard)),
                "hazard_max": float(np.max(self.hazard)), "elev_gain_m": float(np.sum(np.clip(np.diff(self.elev), 0, None))),
                "elev_loss_m": float(-np.sum(np.clip(np.diff(self.elev), None, 0))),
                "points": len(self.nodes), "expanded_nodes": self.expanded, "compute_s": round(self.compute_s, 3)}


class GridPlanner:
    def __init__(self, g: Grid, hazard_index: np.ndarray, hazard_level: np.ndarray, params: RouteParams,
                 ml_prob: np.ndarray | None = None):
        self.g = g
        self.p = params
        self.h, self.w = g.shape
        self.z = filled(g.z)
        self.dx = g.dx_rows
        self.dy = g.dy
        blocked = ~np.isfinite(g.z) | (hazard_level >= 3)
        self.blocked = blocked
        self.H = np.nan_to_num(hazard_index, nan=1.0)
        if ml_prob is not None and params.ml_blend > 0:
            # hazard used in the cost = (1 - a) * rule index + a * model probability (supervised model, module 07)
            a = float(np.clip(params.ml_blend, 0.0, 1.0))
            self.H = (1 - a) * self.H + a * np.nan_to_num(ml_prob, nan=1.0)
        self.tan_lim = math.tan(math.radians(params.slope_limit_deg))

    def _factor(self, strategy, grade, haz):
        p = self.p
        s_rel = (math.atan(abs(grade)) / math.radians(p.slope_limit_deg))
        if strategy == "shortest":
            return 1.0
        if strategy == "lowest_slope":
            return 1.0 + p.w_slope * 4.0 * s_rel * s_rel
        if strategy == "lowest_hazard":
            return 1.0 + p.w_hazard * 6.0 * haz
        return 1.0 + p.w_slope * 1.5 * s_rel * s_rel + p.w_hazard * 2.5 * haz + p.w_energy * 5.0 * max(grade, 0.0)

    def nearest_valid(self, r, c, radius=15):
        if 0 <= r < self.h and 0 <= c < self.w and not self.blocked[r, c]:
            return r, c
        best = None
        for rr in range(max(0, r - radius), min(self.h, r + radius + 1)):
            for cc in range(max(0, c - radius), min(self.w, c + radius + 1)):
                if not self.blocked[rr, cc]:
                    d = (rr - r) ** 2 + (cc - c) ** 2
                    if best is None or d < best[0]:
                        best = (d, rr, cc)
        return (best[1], best[2]) if best else None

    def plan(self, start: tuple[int, int], goal: tuple[int, int], strategy: str = "balanced",
             algorithm: str = "astar") -> RouteResult:
        t0 = time.perf_counter()
        res = RouteResult(strategy=strategy, algorithm=algorithm, found=False)
        s = self.nearest_valid(*start)
        gl = self.nearest_valid(*goal)
        if s is None or gl is None:
            res.reason = "start_or_goal_blocked"
            return res
        h, w = self.h, self.w
        z, dx, dy, H, blocked = self.z, self.dx, self.dy, self.H, self.blocked
        eps = 0.0 if algorithm == "dijkstra" else (self.p.epsilon if algorithm == "weighted_astar" else 1.0)
        gr, gc = gl
        lat_g = None  # heuristic uses local metric (mean dx) - admissible lower bound
        dxm = float(dx.min())

        def heur(r, c):
            return eps * math.hypot((r - gr) * dy, (c - gc) * dxm) if eps else 0.0

        start_i = s[0] * w + s[1]
        goal_i = gr * w + gc
        gbest = {start_i: 0.0}
        parent = {start_i: -1}
        openh = [(heur(*s), 0.0, start_i)]
        closed = set()
        expanded = 0
        tan_lim = self.tan_lim
        while openh:
            f, gcost, u = heapq.heappop(openh)
            if u in closed:
                continue
            closed.add(u)
            expanded += 1
            if u == goal_i or expanded > self.p.max_expansions:
                break
            r, c = divmod(u, w)
            zu = z[r, c]
            for dr, dc in DIRS:
                rr, cc = r + dr, c + dc
                if rr < 0 or cc < 0 or rr >= h or cc >= w or blocked[rr, cc]:
                    continue
                v = rr * w + cc
                if v in closed:
                    continue
                cr = crossed_cells(dr, dc)
                if cr:
                    (a1, b1), (a2, b2) = cr
                    x1, x2 = blocked[r + a1, c + b1], blocked[r + a2, c + b2]
                    # knight: no crossing of any blocked cell; diagonal: no squeezing between two blocked cells
                    if (x1 or x2) if abs(dr) + abs(dc) == 3 else (x1 and x2):
                        continue
                dh = math.hypot(dr * dy, dc * 0.5 * (dx[r] + dx[rr]))
                dzv = z[rr, cc] - zu
                grade = dzv / dh
                if abs(grade) > tan_lim:
                    continue
                d3 = math.sqrt(dh * dh + dzv * dzv)
                hz = 0.5 * (H[r, c] + H[rr, cc])
                ng = gcost + d3 * self._factor(strategy, grade, hz)
                if ng < gbest.get(v, math.inf):
                    gbest[v] = ng
                    parent[v] = u
                    heapq.heappush(openh, (ng + heur(rr, cc), ng, v))
        res.expanded = expanded
        res.compute_s = time.perf_counter() - t0
        if goal_i not in parent:
            res.reason = "no_path"
            return res
        path = []
        cur = goal_i
        while cur != -1:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        res.found = True
        res.cost = gbest[goal_i]
        self._fill(res, path)
        return res

    def _fill(self, res: RouteResult, path):
        g = self.g
        r, c = np.divmod(np.asarray(path), self.w)
        res.nodes = [int(p) for p in path]
        res.lat, res.lon = g.lat(r), g.lon(c)
        res.elev = self.z[r, c]
        dxs = 0.5 * (g.dx_rows[r[:-1]] + g.dx_rows[r[1:]]) * (c[1:] - c[:-1])
        dys = g.dy * (r[1:] - r[:-1])
        dh = np.hypot(dxs, dys)
        dz = np.diff(res.elev)
        res.dist2d_m = np.concatenate([[0], np.cumsum(dh)])
        res.dist3d_m = np.concatenate([[0], np.cumsum(np.sqrt(dh ** 2 + dz ** 2))])
        res.slope_deg = np.concatenate([[0], np.degrees(np.arctan(np.abs(dz) / np.maximum(dh, 1e-9)))])
        res.hazard = self.H[r, c]


def plan_all(planner: GridPlanner, start, goal, algorithm="astar", strategies=STRATEGIES) -> dict:
    return {s: planner.plan(start, goal, s, algorithm) for s in strategies}


def multi_stop(planner: GridPlanner, stops: list[tuple[int, int]], strategy="balanced", algorithm="astar"):
    """Chain legs stop0->stop1->...; returns merged RouteResult and leg boundaries (indices)."""
    legs = [planner.plan(a, b, strategy, algorithm) for a, b in zip(stops[:-1], stops[1:])]
    if not all(l.found for l in legs):
        bad = next(l for l in legs if not l.found)
        return bad, []
    nodes, cuts = [], [0]
    for l in legs:
        nodes += l.nodes if not nodes else l.nodes[1:]
        cuts.append(len(nodes) - 1)
    merged = RouteResult(strategy=strategy, algorithm=algorithm, found=True,
                         expanded=sum(l.expanded for l in legs), compute_s=sum(l.compute_s for l in legs),
                         cost=sum(l.cost for l in legs))
    planner._fill(merged, nodes)
    return merged, cuts
