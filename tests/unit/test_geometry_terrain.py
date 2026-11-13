import math

import numpy as np
import pytest

import config as C
from mars_survive.mapping import coords


def test_haversine_quarter_meridian():
    d = coords.haversine_m(0, 0, 90, 0)
    assert d == pytest.approx(math.pi / 2 * C.R_MARS_MEAN, rel=1e-9)


def test_haversine_one_degree():
    assert coords.haversine_m(18.4, 77.0, 18.4, 78.0) == pytest.approx(
        math.radians(1) * C.R_MARS_MEAN * math.cos(math.radians(18.4)), rel=2e-4)


def test_centric_graphic_roundtrip():
    for lat in (-80, -18.4, 0, 18.4447, 60):
        assert coords.graphic_to_centric(coords.centric_to_graphic(lat)) == pytest.approx(lat, abs=1e-9)
    assert coords.centric_to_graphic(18.4447) > 18.4447          # graphic latitude is larger in magnitude
    # analytic: dphi ~ sin(2 phi)/2 * ((a/b)^2 - 1) = 0.204 deg at 18.44 N
    assert coords.centric_to_graphic(18.4447) - 18.4447 == pytest.approx(0.204, abs=0.001)


def test_east_west_longitude():
    assert coords.east_to_west(77.4508) == pytest.approx(282.5492)
    assert coords.west_to_east(282.5492) == pytest.approx(77.4508)


def test_parse_coordinate():
    assert coords.parse_coordinate("18.44, 77.45") == (18.44, 77.45)
    lat, lon = coords.parse_coordinate("18.44N 282.55W")
    assert lat == 18.44 and lon == pytest.approx(77.45)
    with pytest.raises(ValueError):
        coords.parse_coordinate("95 10")


def test_destination_inverse():
    lat, lon = coords.destination(18.4, 77.4, 45.0, 5000)
    assert coords.haversine_m(18.4, 77.4, lat, lon) == pytest.approx(5000, rel=1e-6)
    assert coords.initial_bearing_deg(18.4, 77.4, lat, lon) == pytest.approx(45.0, abs=0.01)


def test_grid_cell_sizes(grid):
    assert grid.dy == pytest.approx(C.ANALYSIS_RES_M, rel=1e-3)
    assert np.all(np.abs(grid.dx_rows - C.ANALYSIS_RES_M) < 1.0)


def test_slope_of_known_plane(flat_grid):
    from mars_survive.terrain.analysis import aspect_deg, slope_deg
    g = flat_grid
    x = np.arange(g.shape[1]) * g.dx_rows[0]
    g2 = type(g)(**{**g.__dict__, "z": (np.tile(x, (g.shape[0], 1)) * 0.1).astype(np.float32)})  # 10 % east-up
    s = slope_deg(g2)
    assert np.nanmedian(s) == pytest.approx(math.degrees(math.atan(0.1)), abs=0.05)
    asp = aspect_deg(g2)
    assert np.nanmedian(asp) == pytest.approx(270, abs=0.5)   # downslope faces west


def test_terrain_layers_and_profile(grid):
    from mars_survive.terrain.analysis import compute_all, profile, stats
    T = compute_all(grid)
    for a in (T.slope, T.roughness, T.tri, T.relief, T.curvature, T.complexity):
        assert a.shape == grid.shape
        assert np.isnan(a[~np.isfinite(grid.z)]).all()     # NoData stays NoData
    assert 0 <= np.nanmin(T.complexity) and np.nanmax(T.complexity) <= 1
    st = stats(T.slope)
    assert st["max"] >= st["p90"] >= st["p50"] >= st["min"]
    p = profile(grid, grid.lat(150), grid.lon(40), grid.lat(150), grid.lon(300))
    assert p["dist3d_m"] >= p["dist2d_m"] * 0.999
    assert p["gain_m"] >= 0 and p["loss_m"] >= 0


def test_hazards(grid, engine):
    from mars_survive.hazards.detect import LEVELS, summary
    H = engine.H
    assert set(np.unique(H.level)).issubset(set(LEVELS))
    assert (H.level[~np.isfinite(grid.z)] == 4).all()          # NoData -> unknown, never safe
    assert abs(sum(summary(H).values()) - 1) < 1e-9
    o = H.objects[0]
    for k in ("lat", "lon", "type", "level", "method", "source", "confidence"):
        assert k in o
    assert o["confidence"] <= 0.6                               # synthetic DEM lowers confidence
