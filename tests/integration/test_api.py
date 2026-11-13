"""REST API tests (FastAPI TestClient)."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and j["dem"]["data_class"] in ("Real", "Synthetic", "User Supplied")


def test_terrain_stats():
    j = client.get("/api/terrain/stats").json()
    assert "slope" in j["layers"] and j["layers"]["slope"]["mean"] >= 0


def test_route_all_strategies():
    r = client.post("/api/route", json={"start": {"lat": 18.4447, "lon": 77.4508}, "goal": {"lat": 18.455, "lon": 77.405},
                                        "include_path": True})
    assert r.status_code == 200
    routes = r.json()["routes"]
    assert [x["strategy"] for x in routes] == ["shortest", "lowest_slope", "lowest_hazard", "balanced"]
    found = [x for x in routes if x["found"]]
    assert found and all(x["distance_3d_km"] >= x["distance_2d_km"] > 0 for x in found)
    assert len(found[0]["path"]) == found[0]["points"]


def test_route_outside_dem_is_422():
    r = client.post("/api/route", json={"start": {"lat": 0, "lon": 0}, "goal": {"lat": 18.45, "lon": 77.4}})
    assert r.status_code == 422 and r.json()["error"] == "invalid_input"


def test_route_validation():
    r = client.post("/api/route", json={"start": {"lat": 120, "lon": 0}, "goal": {"lat": 18.45, "lon": 77.4}})
    assert r.status_code == 422


def test_link_budget_physics():
    near = client.post("/api/link-budget", json={"preset": "uhf_orbiter", "distance_m": 500_000}).json()["result"]
    far = client.post("/api/link-budget", json={"preset": "uhf_orbiter", "distance_m": 1_000_000}).json()["result"]
    k = "fspl_db"
    assert abs((far[k] - near[k]) - 6.0206) < 0.01      # doubling distance = +6.02 dB free-space loss


def test_oxygen_monotonic():
    a = client.post("/api/oxygen", json={"distance_m": 1000}).json()
    b = client.post("/api/oxygen", json={"distance_m": 3000}).json()
    assert 0 < a["o2_used_l"] < b["o2_used_l"] and a["data_class"] == "Simulated"


def test_mars_time_reference():
    # Allison & McEwen (2000) worked example: 2000-01-06 00:00 UTC -> Ls 277.18758
    j = client.post("/api/mars-time", json={"utc": "2000-01-06T00:00:00Z", "lon_east": 0}).json()
    assert abs(j["Ls"] - 277.18758) < 0.01
