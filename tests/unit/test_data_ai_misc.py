import json

import numpy as np
import pandas as pd
import pytest

from mars_survive.common import DataClass, ModuleError


def test_meda_pipeline():
    from mars_survive.meda import environment as M
    df = M.synthetic_sample()
    st = M.statistics(df)
    assert "air_temp_c" in st.index
    an = M.anomalies(df)
    assert {"air_temp_c", "wind_speed_ms"} & set(an["variable"])   # injected anomalies are found
    assert M.environment_risk(df)["level"] in ("low", "medium", "high")
    csv = "TIME,ATS,PS,HORIZONTAL_WIND_SPEED\n1,210,700,3\n2,215,701,4\n"
    d, mp = M.read_csv(csv.encode())
    assert mp["air_temp_c"] == "ATS" and d["air_temp_c"].iloc[0] == pytest.approx(210 - 273.15)
    with pytest.raises(ModuleError):
        M.read_csv(b"a,b\n1,2\n")


def test_suit_simulation_alerts():
    from mars_survive.telemetry import suit
    t = np.arange(0, 6 * 3600, 60.0)
    pw = np.full_like(t, 300.0)
    df = suit.simulate(t, pw, suit.SuitParams())
    assert df["o2_tank_kpa"].is_monotonic_decreasing
    nominal = suit.alerts(df)
    leak = suit.alerts(suit.simulate(t, pw, suit.SuitParams(), faults={"o2_leak_start_s": 3600, "o2_leak_lpm": 3.0}))
    assert len(leak) >= len(nominal)
    assert suit.safety_status(leak) in ("caution", "abort")
    sc, flag = suit.anomaly_scores(df)
    assert len(sc) == len(df)


def test_risk_matrix():
    from mars_survive.risk.assessment import assess, level, overall
    assert level(4) == "low" and level(9) == "medium" and level(16) == "high" and level(25) == "critical"
    df = assess({"max_slope_frac": 0.95, "hazard_mean": 0.6, "o2_margin_frac": -0.1, "energy_margin_frac": 0.5})
    o = df.set_index("factor")
    assert o.loc["oxygen", "likelihood"] == 5 and o.loc["oxygen", "level"] == "critical"
    assert overall(df)["level"] == "critical"


def test_simulation_scenarios(engine):
    from mars_survive.integration.mission import MissionParams
    from mars_survive.simulation.engine import SCENARIOS, SimConfig, run
    mp = MissionParams()
    g = engine.g
    r = engine.plan_four((g.lat(150), g.lon(165)), (g.lat(60), g.lon(260)), mp)["balanced"]
    pr = engine.resources(r, mp)
    t_ret = np.linspace(pr["t_s"][-1], 0, len(r.nodes))[::-1] * 0 + pr["t_s"]   # simple proxy for tests
    outcomes = {}
    for sc in SCENARIOS:
        res = run(pr, t_ret, mp.o2_capacity_l, float("inf"), SimConfig(sc), time_budget_s=mp.budget_h * 3600)
        outcomes[sc] = res["outcome"]
        assert res["outcome"] in ("completed", "aborted_safe", "failed")
    assert outcomes["normal"] == "completed"
    assert outcomes["emergency_return"] == "aborted_safe"
    small = run(pr, t_ret, pr["o2_total_l"] * 0.6, float("inf"), SimConfig("normal"), time_budget_s=1e9)
    assert small["outcome"] in ("aborted_safe", "failed")


def test_ingestion_security(tmp_path):
    from mars_survive.ingestion.importer import parse, safe_name, validate
    assert safe_name("../../etc/passwd.csv") == "passwd.csv"
    assert safe_name("..\\..\\x.json") == "x.json"
    with pytest.raises(ModuleError):
        validate("evil.exe", b"MZ")
    with pytest.raises(ModuleError):
        validate("fake.png", b"not a png")
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><l>&b;</l>'
    info = parse("bomb.xml", bomb) if False else None
    with pytest.raises(ModuleError):
        parse("bomb.xml", bomb)                               # defusedxml refuses entity definitions
    gj = json.dumps({"type": "FeatureCollection", "features": []}).encode()
    assert parse("r.geojson", gj)["format"] == "GeoJSON"
    assert parse("t.csv", b"a,b\n1,2\n")["metadata"]["rows"] == 1


def test_geotiff_roundtrip(tmp_path):
    import math

    import rasterio
    from rasterio.transform import from_origin

    from mars_survive.dem.loader import build_grid_from_dem, inspect_geotiff, quality_report
    R = 3396190.0
    x0, y0 = R * math.radians(77.20), R * math.radians(18.66)
    z = (np.add.outer(np.arange(1100), np.arange(1300)) * 0.1 - 2600).astype(np.float32)
    p = tmp_path / "dem.tif"
    with rasterio.open(p, "w", driver="GTiff", height=1100, width=1300, count=1, dtype="float32",
                       crs="+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs",
                       transform=from_origin(x0, y0, 20, 20), nodata=-3.4028227e38) as d:
        d.write(z, 1)
    info = inspect_geotiff(p)
    assert info["crs_is_mars"] and info["pixel_size"] == [20.0, 20.0]
    g, meta = build_grid_from_dem(p, half=0.12, save=False)
    assert g.data_class == DataClass.REAL and meta["quality"]["valid_fraction"] > 0.5
    assert quality_report(g.z)["plausible_mars_range"]


def test_pds4_label_parse():
    from mars_survive.dem.loader import parse_label_xml
    xml = b"""<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"><Identification_Area>
    <title>Jezero DEM</title><logical_identifier>urn:x</logical_identifier></Identification_Area>
    <a_axis_radius unit="km">3396.19</a_axis_radius></Product_Observational>"""
    lab = parse_label_xml(xml)
    assert lab["is_pds4"] and lab["fields"]["title"] == "Jezero DEM" and lab["fields"]["a_axis_radius"] == "3396.19"


def test_vision_metrics():
    from mars_survive.ai.vision import evaluate, heuristic_detect, iou, synthetic_test_image
    a = {"cls": "rock", "x1": 0, "y1": 0, "x2": 10, "y2": 10, "score": 1}
    assert iou(a, a) == 1.0
    perfect = evaluate([a], [a])
    assert perfect["precision"] == 1 and perfect["recall"] == 1 and perfect["map50"] == pytest.approx(1.0)
    empty = evaluate([], [a])
    assert empty["recall"] == 0
    img, gts = synthetic_test_image()
    dets = heuristic_detect(img)
    ev = evaluate(dets, gts)
    assert 0 <= ev["precision"] <= 1 and ev["recall"] > 0          # heuristic finds at least something


def test_yolo_status_honest():
    from mars_survive.ai.vision import yolo_status
    st = yolo_status()
    assert st["ready"] == (st["package"] and bool(st["weights"]))


def test_storage_catalog_provenance(tmp_db):
    from mars_survive import storage
    from mars_survive.provenance import registry
    from mars_survive.science import catalog
    mid = storage.create_mission("M1", "d", "Jezero", "astronaut", 6, {"a": 1}, path=tmp_db)
    storage.update_mission(mid, path=tmp_db, status="active")
    assert storage.list_missions(tmp_db)[0]["status"] == "active"
    storage.create_mission("x'); DROP TABLE missions;--", "", "", "rover", 1, {}, path=tmp_db)
    assert len(storage.list_missions(tmp_db)) == 2                  # injection stored as plain text
    ts = catalog.all_targets(tmp_db)
    assert any(t["origin"] == "published" for t in ts) and any(t["origin"] == "approximate" for t in ts)
    catalog.add("My rock", 18.45, 77.44, path=tmp_db)
    assert any(t["origin"] == "user" for t in catalog.all_targets(tmp_db))
    registry.register("x", DataClass.USER, path=tmp_db)
    with pytest.raises(ValueError):
        registry.register("y", "Fake", path=tmp_db)


def test_i18n_fallback_and_coverage():
    from mars_survive.localization import i18n
    assert i18n.t("__missing_key__", "uz") == "__missing_key__"
    assert len(i18n.LANGUAGES) == 18 and i18n.is_rtl("ar") and not i18n.is_rtl("uz")
    cov = {c["code"]: c["coverage"] for c in i18n.coverage()}
    assert cov["en"] == 1.0
    for code, v in cov.items():
        assert v >= 0.99, f"{code} translation coverage {v:.2%}"


def test_i18n_placeholders_consistent():
    import re

    from mars_survive.localization import i18n
    en = i18n._load("en")
    for code in i18n.LANGUAGES:
        d = i18n._load(code)
        for k, v in en.items():
            if k in d:
                assert set(re.findall(r"\{(\w+)\}", v)) == set(re.findall(r"\{(\w+)\}", d[k])), (code, k)


def test_settings_roundtrip(tmp_path):
    from mars_survive.settings import store
    s = store.Settings(language="ar", theme="light")
    p = tmp_path / "s.json"
    store.save(s, p)
    assert store.load(p).language == "ar"
    assert store.fmt_dist(1609.344, "mi") == "1.00 mi" and store.fmt_temp(0, "K") == "273.1 K"


def test_reports_all_formats(tmp_path):
    from mars_survive.reporting import export
    rep = {"title": "Test", "lang": "en", "generated": "now", "region": "Jezero", "data_class": "Synthetic",
           "mission": {"name": "<script>x</script>"},
           "sections": [{"key": "route", "title": "Route", "kv": {"km": 1.2}, "table": [{"a": 1, "b": 2.5}],
                         "image": export.chart_png([0, 1], {"z": [0, 1]}), "notes": ["n"]}]}
    assert export.to_pdf(rep)[:4] == b"%PDF"
    h = export.to_html(rep).decode()
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert b"Route" in export.to_csv(rep)
    assert json.loads(export.to_json(rep))["title"] == "Test"
    assert export.to_excel(rep)[:2] == b"PK"


@pytest.mark.parametrize("lang", ["uz", "ru", "ar", "hi", "zh", "ja", "ko", "vi", "kk", "tk"])
def test_pdf_unicode_languages(lang):
    from mars_survive.localization import i18n
    from mars_survive.reporting import export
    rep = {"title": i18n.t("app.subtitle", lang), "lang": lang, "rtl": i18n.is_rtl(lang), "generated": "now",
           "sections": [{"key": "a", "title": i18n.t("nav.route", lang), "kv": {i18n.t("lbl.distance", lang): "1 km"}}]}
    assert export.to_pdf(rep)[:4] == b"%PDF"


def test_upload_size_limit(monkeypatch):
    from mars_survive.ingestion import importer
    monkeypatch.setattr(importer.C, "MAX_UPLOAD_MB", 0.001)          # 1 kB limit for the test
    with pytest.raises(ModuleError) as e:
        importer.validate("big.csv", b"a,b\n" + b"1,2\n" * 1000)
    assert e.value.key == "err.too_big"
    with pytest.raises(ModuleError):
        importer.validate("empty.csv", b"")


def test_sql_injection_is_stored_as_text(tmp_db):
    from mars_survive.science import catalog as cat
    evil = "x'); DROP TABLE targets; --"
    tid = cat.add(evil, 18.44, 77.45, path=tmp_db)
    names = [t["name"] for t in cat.all_targets(path=tmp_db)]
    assert evil in names and tid > 0                                    # table still exists, text kept literally
