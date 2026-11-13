"""DONKI space weather and Perseverance traverse/raw-image parsing (offline, on format examples)."""
from datetime import datetime

import pandas as pd
import pytest

from mars_survive.common import ModuleError
from mars_survive.nasa_live import donki as D
from mars_survive.nasa_live import http
from mars_survive.nasa_live import perseverance as P


def _events():
    ex = D.example_payloads()
    return pd.concat([D.normalize(k, ex[k]) for k in D.TYPES], ignore_index=True)


def test_donki_normalize_and_mars_relevance():
    df = _events()
    assert set(df["kind"]) == {"FLR", "SEP", "CME", "GST"}
    cme = df[df["kind"] == "CME"]
    assert cme["mars_relevant"].sum() == 1                       # only the CME whose ENLIL list names Mars
    assert pd.Timestamp("2026-11-10 06:00") in set(cme["mars_arrival"].dropna())


def test_donki_assessment_levels():
    df = _events()
    assert D.assess(df, datetime(2026, 11, 10, 8)).level == "high"     # Mars CME arrival ±1 day + SEP
    assert D.assess(df, datetime(2026, 11, 5, 8)).level == "low"
    only_x = df[df["kind"] == "FLR"]
    assert D.assess(only_x, datetime(2026, 11, 8, 0)).level == "medium"  # X1.3 flare, direction unknown


def test_flare_class_rank():
    assert D.flare_class_rank("X1.3") > D.flare_class_rank("M9.9") > D.flare_class_rank("C1") > 0
    assert D.flare_class_rank("?") == 0


def test_donki_fetch_validates_inputs():
    with pytest.raises(ModuleError):
        D.fetch("XYZ", datetime(2026, 1, 1).date(), datetime(2026, 1, 2).date())
    with pytest.raises(ModuleError):
        D.fetch("FLR", datetime(2026, 2, 1).date(), datetime(2026, 1, 1).date())


def test_api_key_is_redacted():
    assert "SECRET" not in http._redact("https://api.nasa.gov/DONKI/FLR?startDate=x&api_key=SECRET123&b=1")


def test_json_parsing_limits():
    with pytest.raises(ModuleError):
        http.parse_json_bytes(b"{not json")
    assert http.parse_json_bytes(b'\xef\xbb\xbf{"a": 1}') == {"a": 1}


def test_traverse_parse_and_nearest():
    df = P.parse_traverse(P.example_traverse())
    s = P.summary(df)
    assert s["vertices"] > 10 and s["sol_min"] < s["sol_max"] and s["driven_km"] > 0
    assert df["dist_m"].is_monotonic_increasing
    n = P.nearest(df, df["lat"].iloc[5], df["lon"].iloc[5])
    assert n["distance_m"] < 1e-6 and n["sol"] == int(df["sol"].iloc[5])


def test_traverse_lon_360_and_bad_input():
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"sol": 1}, "geometry": {"type": "LineString",
                                                                    "coordinates": [[437.45, 18.44], [437.46, 18.45]]}}]}
    df = P.parse_traverse(gj)
    assert df["lon"].between(-180, 180).all() and abs(df["lon"].iloc[0] - 77.45) < 1e-9
    with pytest.raises(ModuleError):
        P.parse_traverse({"type": "Nope"})
    with pytest.raises(ModuleError):
        P.parse_traverse({"type": "FeatureCollection", "features": []})


def test_raw_images_parse_and_url_safety():
    payload = {"images": [
        {"imageid": "A", "sol": 5, "camera": {"instrument": "NAVCAM_LEFT"},
         "image_files": {"small": "https://mars.nasa.gov/a.png", "full_res": "javascript:alert(1)"}},
        {"imageid": "B", "sol": 5, "camera": {"instrument": "MCZ_RIGHT"}, "image_files": {}}]}
    df = P.parse_raw_images(payload)
    assert df.loc[0, "thumb"] == "https://mars.nasa.gov/a.png"
    assert df.loc[0, "full"] is None                       # non-https URL dropped
    assert list(P.filter_cameras(df, ["mastcam"])["imageid"]) == ["B"]
    ex = P.parse_raw_images(P.example_raw())
    assert len(ex) and ex["thumb"].isna().all()            # synthetic example carries no images


def test_risk_uses_space_weather_flag():
    from mars_survive.risk.assessment import assess
    base = {"dose_msv": 0.05}
    low = assess(base)
    high = assess({**base, "sw_level": "high"})
    get = lambda df: int(df[df["factor"] == "radiation"]["likelihood"].iloc[0])  # noqa: E731
    assert get(high) == 5 and get(low) < 5
