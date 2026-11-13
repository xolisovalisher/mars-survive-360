from datetime import datetime, timezone

import numpy as np
import pytest

import config as C


def test_ekf_beats_dead_reckoning():
    from mars_survive.navigation import ekf
    from mars_survive.navigation.metrics import error_ellipse, summarize
    x = np.linspace(0, 3000, 200)
    y = 200 * np.sin(x / 600)
    pose, v, w = ekf.path_to_controls(x, y, 1.0, 5.0)
    sim = ekf.simulate(pose, v, w, ekf.landmarks_along(pose), ekf.NavParams(dt=5.0))
    s = summarize(sim)
    assert s["ekf"]["rmse_m"] < s["dr"]["rmse_m"]
    assert s["landmark_updates"] > 0
    assert 0 <= s["ekf"]["consistency_2sigma"] <= 1
    el = error_ellipse(sim["cov"][-1][:2, :2])
    assert el.shape == (60, 2)


def test_trajectory_deviation():
    from mars_survive.navigation.metrics import trajectory_deviation
    plan = np.array([[0, 0], [100, 0]], float)
    est = np.array([[50, 3], [50, -4]], float)
    assert trajectory_deviation(plan, est).tolist() == pytest.approx([3, 4])


def test_fspl_known_value():
    from mars_survive.communication.link import fspl_db
    # 1 km at 1 GHz: 92.45 + 20log10(1) + 20log10(1) = 92.45 dB (classic formula)
    assert fspl_db(1000, 1e9) == pytest.approx(92.45, abs=0.01)


def test_link_budget_consistency():
    from mars_survive.communication.link import LinkParams, link_budget
    p = LinkParams(distance_m=1e6)
    a = link_budget(p)
    b = link_budget(LinkParams(**{**p.as_dict(), "distance_m": 2e6}))
    assert a["margin_db"] - b["margin_db"] == pytest.approx(6.0206, abs=1e-3)   # inverse-square law
    assert a["cn0_dbhz"] == pytest.approx(a["prx_dbw"] - a["n0_dbw_hz"])


def test_radio_horizon():
    from mars_survive.communication.link import radio_horizon_m
    assert radio_horizon_m(2.0) == pytest.approx((2 * C.R_MARS_MEAN * 2) ** 0.5)


def test_terrain_los(grid):
    from mars_survive.communication.link import terrain_los
    a = terrain_los(grid, grid.lat(150), grid.lon(150), 2, grid.lat(150), grid.lon(160), 2)
    assert a["visible"] in (True, False, None)
    assert a["distance_m"] > 0


def test_orbit_period_and_windows():
    from mars_survive.relay.orbits import Orbiter, contact_windows, period_s, store_and_forward
    assert period_s(300) / 60 == pytest.approx(112.5, abs=1.5)    # MRO ~112 min
    cw = contact_windows(Orbiter(), 18.44, 77.45, hours=24.66)
    assert len(cw["windows"]) >= 1 and 0 < cw["availability"] < 0.2
    for w in cw["windows"]:
        assert w["max_elev_deg"] >= 10
    sf = store_and_forward(10_000, cw["windows"], 256_000, 24.66)
    assert sf["sent_mb"][-1] <= sf["generated_mb"] + 1e-9
    out = store_and_forward(10_000, cw["windows"], 256_000, 24.66, outage=(0, 24.66 * 3600))
    assert out["sent_mb"][-1] == 0


def test_mars24_reference_example():
    """Allison & McEwen (2000) worked example, 2000-01-06 00:00 UTC."""
    from mars_survive.spice.mars_time import mars_time
    m = mars_time(datetime(2000, 1, 6, tzinfo=timezone.utc))
    assert m["M"] == pytest.approx(21.74558, abs=1e-4)
    assert m["nu_minus_M"] == pytest.approx(4.44193, abs=1e-4)
    assert m["Ls"] == pytest.approx(277.18758, abs=1e-3)
    assert m["MST_h"] == pytest.approx(23.99425, abs=1e-4)
    assert m["eot_deg"] == pytest.approx(-5.18774, abs=1e-3)


def test_solar_elevation_bounds():
    from mars_survive.spice.mars_time import daylight_series
    ts, el, lt = daylight_series(datetime(2031, 3, 1, tzinfo=timezone.utc), 18.44, 77.45)
    assert el.max() > 30 and el.min() < -30       # there is a day and a night within one sol


def test_spice_kernel_validation(tmp_path):
    from mars_survive.spice.kernels import validate_kernel
    good = tmp_path / "x.tls"
    good.write_text("KPL/LSK\n\\begindata\n")
    bad = tmp_path / "y.bsp"
    bad.write_text("not a kernel")
    assert validate_kernel(good)["ok"] and not validate_kernel(bad)["ok"]


def test_spice_missing_kernels_does_not_crash(tmp_path, monkeypatch):
    from mars_survive.common import ModuleError
    from mars_survive.spice import kernels
    monkeypatch.setattr(kernels.C, "SPICE_DIR", tmp_path)
    st = kernels.status(tmp_path)
    assert all(not s["present"] for s in st)
    with pytest.raises(ModuleError):
        kernels.sun_geometry(datetime(2030, 1, 1, tzinfo=timezone.utc), 18.4, 77.4)
