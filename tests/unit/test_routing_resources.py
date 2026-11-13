import math

import numpy as np
import pytest

from mars_survive.routing.planner import STRATEGIES, GridPlanner, RouteParams, plan_all


def _planner(g, engine=None, **kw):
    if engine is None:
        lv = np.zeros(g.shape, np.uint8)
        hi = np.zeros(g.shape, np.float32)
    else:
        lv, hi = engine.H.level, engine.H.index
    return GridPlanner(g, hi, lv, RouteParams(**kw))


def test_flat_route_distance_close_to_straight(flat_grid):
    P = _planner(flat_grid)
    r = P.plan((10, 10), (100, 70), "shortest", "astar")
    assert r.found
    straight = math.hypot(90 * flat_grid.dy, 60 * flat_grid.dx_rows[0])
    assert straight <= r.dist2d_m[-1] <= straight * 1.03         # 16-neighbour: <= 2.75 % error


def test_astar_equals_dijkstra(grid, engine):
    P = _planner(grid, engine)
    a = P.plan((150, 165), (60, 260), "balanced", "astar")
    d = P.plan((150, 165), (60, 260), "balanced", "dijkstra")
    assert a.found and d.found
    assert a.cost == pytest.approx(d.cost, rel=1e-9)
    assert a.expanded < d.expanded


def test_weighted_astar_bounded(grid, engine):
    P = _planner(grid, engine, epsilon=1.5)
    a = P.plan((150, 165), (60, 260), "lowest_slope", "astar")
    w = P.plan((150, 165), (60, 260), "lowest_slope", "weighted_astar")
    assert w.cost <= 1.5 * a.cost + 1e-6 and w.cost >= a.cost - 1e-6


def test_strategies_tradeoffs(grid, engine):
    R = plan_all(_planner(grid, engine), (150, 165), (60, 260))
    assert set(R) == set(STRATEGIES)
    s = {k: v.summary() for k, v in R.items()}
    assert s["shortest"]["distance_3d_km"] <= min(v["distance_3d_km"] for v in s.values()) + 1e-9
    assert s["lowest_hazard"]["hazard_mean"] <= s["shortest"]["hazard_mean"] + 1e-9
    for v in s.values():
        assert v["max_slope_deg"] <= 20.0 + 1e-6                   # slope limit respected


def test_blocked_goal_not_safe(flat_grid):
    lv = np.zeros(flat_grid.shape, np.uint8)
    lv[:, 60] = 3                                                 # wall of no-go cells
    P = GridPlanner(flat_grid, np.zeros(flat_grid.shape, np.float32), lv, RouteParams())
    r = P.plan((60, 10), (60, 110), "shortest")
    assert not r.found and r.reason == "no_path"


def test_minetti_and_tobler():
    from mars_survive.oxygen.manager import minetti_cost, tobler_speed
    assert minetti_cost(0.0) == pytest.approx(2.5)
    assert minetti_cost(0.1) > minetti_cost(0.0) > 0
    assert tobler_speed(0.0, 1.0) == pytest.approx(1.0)
    assert tobler_speed(-0.05, 1.0) > tobler_speed(0.0, 1.0) > tobler_speed(0.2, 1.0)


def test_o2_conversions():
    from mars_survive.oxygen.manager import o2_kg_to_litres_stp, o2_lpm_from_power, tank_o2_kg
    assert o2_lpm_from_power(335) == pytest.approx(1.0, rel=1e-3)   # 335 W ~ 1 L/min
    m = tank_o2_kg(101.325, 22.414, 273.15)                         # 1 mol at STP
    assert m == pytest.approx(0.032, rel=1e-3)
    assert o2_kg_to_litres_stp(1.429e-3) == pytest.approx(1.0)


def test_oxygen_plan_status():
    from mars_survive.oxygen.manager import OxygenPlan
    r = OxygenPlan(1000, 0.25, 500, 100, 5).report()
    assert r["usable_l"] == 750 and r["remaining_l"] == 250 and r["status"] == "ok"
    assert OxygenPlan(1000, 0.25, 800, 100, 5).report()["status"] == "critical"


def test_rover_traction_physics():
    from mars_survive.energy.model import RoverParams, traction
    import config as C
    p = RoverParams()
    flat = traction([100.0], [0.0], [0.0], p)
    assert flat["force_n"][0] == pytest.approx(p.mass_kg * C.G_MARS * p.c_rr, rel=1e-6)
    up = traction([100.0], [10.0], [0.0], p)
    assert up["e_j"][0] > flat["e_j"][0]
    down = traction([100.0], [-30.0], [0.0], p)
    assert down["force_n"][0] >= 0                                   # no regeneration


def test_resource_profile(engine):
    from mars_survive.integration.mission import MissionParams
    mp = MissionParams()
    r = engine.plan_four((engine.g.lat(150), engine.g.lon(165)), (engine.g.lat(60), engine.g.lon(260)), mp)["balanced"]
    pr = engine.resources(r, mp, stop_idx=[len(r.nodes) // 2])
    assert np.all(np.diff(pr["t_s"]) >= 0) and np.all(np.diff(pr["o2_l"]) >= 0)
    assert pr["dwell_s"].sum() == pytest.approx(mp.dwell_min * 60)
    assert pr["o2_total_l"] == pytest.approx(pr["e_j"][-1] / 1000 / 20.1)
