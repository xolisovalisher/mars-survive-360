"""Regression: key outputs must stay equal to the reviewed v1.0.0 snapshot (tests/fixtures/golden_v1.json).
A change that moves these numbers must be intentional: review it, then regenerate the snapshot with
`python -m tests.regression.golden`."""
import json
import math

import pytest

from tests.regression.golden import GOLDEN, snapshot

REL = 1e-6


@pytest.fixture(scope="module")
def pair(engine):
    return json.loads(GOLDEN.read_text(encoding="utf-8")), snapshot(engine)


def _close(a, b, rel=REL, abs_=1e-9):
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


def test_mars_time_unchanged(pair):
    g, n = pair
    for k in g["mars24"]:
        assert _close(g["mars24"][k], n["mars24"][k]), k


def test_geometry_unchanged(pair):
    g, n = pair
    assert _close(g["haversine_1deg_m"], n["haversine_1deg_m"])
    assert _close(g["graphic_lat_jezero"], n["graphic_lat_jezero"])


def test_link_budget_unchanged(pair):
    g, n = pair
    for k in g["link_uhf"]:
        assert _close(g["link_uhf"][k], n["link_uhf"][k]), k


def test_terrain_and_hazards_unchanged(pair):
    g, n = pair
    for k in g["terrain"]:
        assert _close(g["terrain"][k], n["terrain"][k], rel=1e-5), k
    assert g["hazard_levels"] == n["hazard_levels"]


@pytest.mark.parametrize("strategy", ["shortest", "lowest_slope", "lowest_hazard", "balanced"])
def test_routes_unchanged(pair, strategy):
    g, n = pair
    a, b = g["routes"][strategy], n["routes"][strategy]
    assert a["found"] == b["found"]
    for k in ("d2_km", "d3_km", "max_slope", "hazard_mean", "duration_h", "o2_l"):
        assert _close(a[k], b[k], rel=1e-5), (strategy, k, a[k], b[k])
