"""Engine: one object that owns the grid and derived layers so all modules share them."""
from __future__ import annotations

import numpy as np

from mars_survive.dem.grid import Grid
from mars_survive.hazards.detect import HazardResult, detect
from mars_survive.routing import eva
from mars_survive.routing.planner import STRATEGIES, GridPlanner, RouteParams, RouteResult, multi_stop, plan_all
from mars_survive.terrain.analysis import TerrainLayers, compute_all

from .mission import MissionParams, resource_profile


class Engine:
    def __init__(self, grid: Grid, slope_limit: float = 20.0):
        self.g = grid
        self.T: TerrainLayers = compute_all(grid)
        self.slope_limit = None
        self.H: HazardResult | None = None
        self.set_slope_limit(slope_limit)
        self._eva_cache = {}
        self._ml, self._ml_key = None, None

    def set_slope_limit(self, lim: float):
        if lim != self.slope_limit:
            self.slope_limit = lim
            self.H = detect(self.g, self.T, slope_limit=lim)
            self._eva_cache = {}

    def planner(self, mp: MissionParams) -> GridPlanner:
        self.set_slope_limit(mp.slope_limit_deg)
        ml = self.ml_prob() if getattr(mp, "ml_blend", 0) > 0 else None
        return GridPlanner(self.g, self.H.index, self.H.level,
                           RouteParams(slope_limit_deg=mp.slope_limit_deg, w_slope=mp.w_slope,
                                       w_hazard=mp.w_hazard, w_energy=mp.w_energy,
                                       ml_blend=getattr(mp, "ml_blend", 0.0) if ml is not None else 0.0), ml)

    def ml_prob(self, model=None):
        """P(non-traversable) per cell from the trained supervised model (None if no model is trained)."""
        from mars_survive.ai import traversability as TV
        key = TV.MODEL_PATH.stat().st_mtime if TV.MODEL_PATH.exists() else None
        if model is None and key is None:
            return None
        if model is not None or self._ml_key != key:
            m = model or TV.load()
            if m is None:
                return None
            self._ml = m.probability_grid(self.g, self.T)
            self._ml_key = key
        return self._ml

    def cell(self, lat, lon):
        r, c = self.g.rowcol(lat, lon)
        return (r, c) if self.g.inside(r, c) else None

    def node(self, lat, lon):
        rc = self.cell(lat, lon)
        return None if rc is None else rc[0] * self.g.shape[1] + rc[1]

    def plan_four(self, start, goal, mp: MissionParams) -> dict[str, RouteResult]:
        P = self.planner(mp)
        return plan_all(P, self.cell(*start), self.cell(*goal), mp.algorithm, STRATEGIES)

    def plan_stops(self, points: list[tuple[float, float]], mp: MissionParams, strategy: str):
        P = self.planner(mp)
        return multi_stop(P, [self.cell(*p) for p in points], strategy, mp.algorithm)

    def rough_along(self, route: RouteResult):
        r, c = np.divmod(np.asarray(route.nodes), self.g.shape[1])
        return np.nan_to_num(self.T.roughness[r, c], nan=0.0)

    def resources(self, route: RouteResult, mp: MissionParams, stop_idx=None):
        return resource_profile(route, self.rough_along(route), mp, stop_idx)

    def eva_fields(self, base_latlon, mp: MissionParams):
        """Fastest out/return time fields from the base (cached per base + params)."""
        key = (self.node(*base_latlon), mp.slope_limit_deg, mp.scenario, tuple(sorted(vars(mp.astronaut).items())),
               mp.rover.speed_ms)
        if key not in self._eva_cache:
            self.set_slope_limit(mp.slope_limit_deg)
            blocked = ~np.isfinite(self.g.z) | (self.H.level >= 3)
            G = eva.time_graph(self.g, self.T.roughness, blocked, mp.astronaut, mp.slope_limit_deg)
            if mp.scenario == "rover":   # rover: scale walking-time graph to rover speed (simple, documented)
                G = G * (mp.astronaut.v_flat_ms / max(mp.rover.speed_ms, 1e-3))
            base = self.planner(mp).nearest_valid(*self.cell(*base_latlon))
            bnode = base[0] * self.g.shape[1] + base[1]
            self._eva_cache[key] = eva.survival_fields(G, bnode)
        return self._eva_cache[key]
