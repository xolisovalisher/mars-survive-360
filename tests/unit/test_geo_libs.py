"""GeoPandas/Shapely GIS export in the Mars CRS, Astropy leap seconds, PyDeck scene, Shapely route distance."""
from datetime import datetime, timezone

import pytest

START, GOAL = (18.4447, 77.4508), (18.455, 77.405)


def test_geopackage_in_mars_crs(engine, tmp_path):
    gpd = pytest.importorskip("geopandas")
    from mars_survive.integration.mission import MissionParams
    from mars_survive.nasa_live import perseverance as P
    from mars_survive.reporting import gis
    from mars_survive.science import catalog as cat
    routes = engine.plan_four(START, GOAL, MissionParams())
    layers = gis.mission_layers(routes, cat.all_targets(path=tmp_path / "t.sqlite3"), engine.H.objects[:20],
                                P.parse_traverse(P.example_traverse()))
    assert {"routes", "hazards", "perseverance_traverse"} <= set(layers)
    p = tmp_path / "m.gpkg"
    p.write_bytes(gis.to_geopackage(layers))
    back = gpd.read_file(p, layer="routes")
    assert len(back) == 4
    assert "Mars" in back.crs.name and '"IAU","49900"' in back.crs.to_wkt(version="WKT1_GDAL")
    assert abs(back.crs.ellipsoid.semi_major_metre - 3396190) < 1           # Mars, not Earth
    # route length from the exported geometry agrees with the planner's 2-D distance (Mars sphere)
    from mars_survive.mapping.coords import haversine_m
    import numpy as np
    g = back[back["strategy"] == "shortest"].geometry.iloc[0]
    xy = np.asarray(g.coords)
    d = haversine_m(xy[:-1, 1], xy[:-1, 0], xy[1:, 1], xy[1:, 0]).sum() / 1000
    assert abs(d - back[back["strategy"] == "shortest"]["dist2d_km"].iloc[0]) < 0.01


def test_astropy_leap_seconds_match_and_extend_table():
    pytest.importorskip("astropy")
    from mars_survive.spice import mars_time as M
    for y, m in [(2000, 1), (2012, 8), (2017, 2), (2026, 11)]:
        d = datetime(y, m, 6, tzinfo=timezone.utc)
        assert abs(M.tt_minus_utc_astropy(d) - M._tt_minus_utc_table(d)) < 1e-3
    assert abs(M.tt_minus_utc(datetime(1990, 1, 1, tzinfo=timezone.utc)) - 57.184) < 1e-3   # before the table


def test_shapely_distance_to_polyline_beats_vertex_distance():
    pytest.importorskip("shapely")
    from mars_survive.nasa_live import perseverance as P
    df = P.parse_traverse(P.example_traverse())
    la, lo = (df.lat[0] + df.lat[1]) / 2, (df.lon[0] + df.lon[1]) / 2
    r = P.route_vs_traverse(df, [la], [lo])
    assert r["method"].iloc[0] == "shapely" and r["dist_to_traverse_m"].iloc[0] < 1.0
    assert P.nearest(df, la, lo)["distance_m"] > 10


def test_pydeck_scene(engine):
    pytest.importorskip("pydeck")
    from mars_survive.integration.mission import MissionParams
    from mars_survive.mapping import views as V
    deck = V.deck_3d(engine.g, engine.plan_four(START, GOAL, MissionParams()), None, 3.0)
    assert deck is not None and len(deck.layers) == 2
    pts = deck.layers[0].data
    assert len(pts) > 1000 and all(len(p["p"]) == 3 for p in pts[:10])
