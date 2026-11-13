"""Performance budgets (generous, for an ordinary laptop): the UI must stay interactive.
Each test measures wall time; numbers are also printed with `pytest -s` for the TEST_REPORT."""
import time

import numpy as np
import pytest

START, GOAL = (18.4447, 77.4508), (18.455, 77.405)


def _t(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, time.perf_counter() - t0


def test_engine_build_time(grid):
    from mars_survive.integration.engine import Engine
    _, dt = _t(Engine, grid)
    print(f"\n[perf] engine build (terrain + hazards, {grid.shape}): {dt:.2f} s")
    assert dt < 10


def test_route_planning_time(engine):
    from mars_survive.integration.mission import MissionParams
    mp = MissionParams()
    _, dt = _t(engine.plan_four, START, GOAL, mp)
    print(f"\n[perf] 4 routes A*: {dt:.3f} s")
    assert dt < 5
    mp.algorithm = "dijkstra"
    _, dt2 = _t(engine.plan_four, START, GOAL, mp)
    print(f"[perf] 4 routes Dijkstra: {dt2:.3f} s")
    assert dt2 < 20


def test_long_route_across_grid(engine):
    from mars_survive.integration.mission import MissionParams
    g = engine.g
    (s, w), (n, e) = g.bounds if not callable(g.bounds) else g.bounds()
    a = (s + 0.15 * (n - s), w + 0.15 * (e - w))
    b = (n - 0.15 * (n - s), e - 0.15 * (e - w))
    r, dt = _t(engine.plan_four, a, b, MissionParams())
    print(f"\n[perf] 4 routes corner-to-corner: {dt:.2f} s")
    assert dt < 30


def test_large_raster_terrain(grid):
    """4× the cells of the demo window (≈ 600×660)."""
    from mars_survive.dem.grid import Grid
    from mars_survive.terrain.analysis import compute_all
    z = np.kron(grid.z, np.ones((2, 2), np.float32))
    big = Grid(z=z, lat_top=grid.lat_top, lon_left=grid.lon_left, dlat=grid.dlat / 2, dlon=grid.dlon / 2,
               source="perf", data_class=grid.data_class)
    _, dt = _t(compute_all, big)
    mb = z.nbytes / 2**20
    print(f"\n[perf] terrain layers on {z.shape} ({mb:.1f} MB): {dt:.2f} s")
    assert dt < 30


def test_ml_inference_time(engine):
    from mars_survive.ai import traversability as TV
    m, _ = TV.train(engine.g, engine.T, cfg=TV.TrainConfig(models=("gboost",), max_train_rows=20_000), save=False)
    _, dt = _t(m.probability_grid, engine.g, engine.T)
    print(f"\n[perf] ML probability map {engine.g.shape}: {dt:.2f} s")
    assert dt < 10


def test_ekf_time(engine):
    from mars_survive.integration.mission import MissionParams
    from mars_survive.navigation import ekf
    r = engine.plan_four(START, GOAL, MissionParams())["balanced"]
    x = (np.asarray(r.lon) - r.lon[0]) * 55000.0
    y = (np.asarray(r.lat) - r.lat[0]) * 59000.0
    pose, v, w = ekf.path_to_controls(x, y, 1.0, 1.0)
    lm = ekf.landmarks_along(pose, 250.0, 25.0, 3)
    _, dt = _t(ekf.simulate, pose, v, w, lm, ekf.NavParams())
    print(f"\n[perf] EKF over {len(pose)} steps: {dt:.2f} s")
    assert dt < 10


def test_integrated_pipeline_time(engine):
    from mars_survive.integration import pipeline
    from mars_survive.integration.mission import MissionParams
    _, dt = _t(pipeline.run, engine, START, GOAL, MissionParams())
    print(f"\n[perf] integrated pipeline (module 27): {dt:.2f} s")
    assert dt < 60


def test_memory_of_engine_is_bounded(engine):
    total = sum(a.nbytes for a in vars(engine.T).values() if isinstance(a, np.ndarray))
    print(f"\n[perf] terrain layer memory: {total / 2**20:.1f} MB")
    assert total < 200 * 2**20
