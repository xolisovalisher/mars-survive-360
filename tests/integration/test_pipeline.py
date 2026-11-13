import numpy as np

from mars_survive.integration import pipeline
from mars_survive.integration.mission import MissionParams


def test_full_chain(engine):
    g = engine.g
    out = pipeline.run(engine, (g.lat(150), g.lon(165)), (g.lat(60), g.lon(260)), MissionParams())
    failed = [s for s in out["steps"] if s["status"] != "ok"]
    assert not failed, failed
    assert out["recommended"] in out["routes"]
    scores = [r["score"] for r in out["table"]]
    assert scores == sorted(scores)
    assert out["risk"] is not None and len(out["risk"]) >= 5
    assert out["simulation"]["outcome"] in ("completed", "aborted_safe", "failed")
    assert out["navigation"]["ekf"]["rmse_m"] < out["navigation"]["dr"]["rmse_m"]
    keys = [k for k, _ in out["explanation"]]
    assert keys[0] == "expl.best"


def test_rover_scenario(engine):
    g = engine.g
    mp = MissionParams(scenario="rover", budget_h=60)
    out = pipeline.run(engine, (g.lat(150), g.lon(165)), (g.lat(120), g.lon(200)), mp)
    pr = out["profiles"][out["recommended"]]
    assert pr["o2_total_l"] == 0 and pr["energy_kwh"] > 0


def test_weights_change_recommendation(engine):
    g = engine.g
    a = pipeline.run(engine, (g.lat(150), g.lon(165)), (g.lat(60), g.lon(260)), MissionParams(),
                     weights={"time": 0, "energy": 0, "hazard": 0, "slope": 0, "comm": 0, "nav": 5})
    assert a["recommended"] == min(a["table"], key=lambda r: r["distance_3d_km"])["strategy"]


def test_eva_envelope(engine):
    from mars_survive.routing.eva import envelope_margin_h
    mp = MissionParams()
    base = engine.g.center
    t_out, t_ret = engine.eva_fields(base, mp)
    env = envelope_margin_h(t_out, t_ret, mp.budget_h, mp.reserve_frac, mp.dwell_min, engine.g.shape)
    reach = np.isfinite(env) & (env >= 0)
    assert 0 < reach.mean() < 1
    i = engine.node(*base)
    assert t_out[i] == 0 and t_ret[i] == 0


def test_dashboard_kpis(engine):
    from mars_survive.dashboard.kpis import kpis
    g = engine.g
    mp = MissionParams()
    r = engine.plan_four((g.lat(150), g.lon(165)), (g.lat(60), g.lon(260)), mp)["balanced"]
    k = kpis({"route": r, "profile": engine.resources(r, mp), "mp": mp, "hazard_objects": engine.H.objects})
    assert k["distance_km"] > 0 and k["o2_remaining_pct"] is not None and k["hazards"] > 0
