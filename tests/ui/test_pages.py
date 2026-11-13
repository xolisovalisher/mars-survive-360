"""UI tests: every one of the 27 modules renders without exceptions/error boxes, in several languages,
and core user actions (language switch, navigation, compute buttons) work. Uses Streamlit AppTest (headless)."""
import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

import config as C  # noqa: E402
from frontend.components.ui import MODULES  # noqa: E402

APP = str(C.ROOT / "app.py")
PAGE_IDS = [m[1] for m in MODULES]


def _run(page, lang="en"):
    at = AppTest.from_file(APP, default_timeout=300)
    at.query_params["page"] = page
    at.query_params["lang"] = lang
    at.run()
    return at


def _assert_clean(at, page):
    assert not at.exception, f"{page}: {[e.value for e in at.exception][:2]}"
    assert not at.error, f"{page}: {[e.value[:200] for e in at.error][:2]}"


def test_27_modules_listed():
    assert len(PAGE_IDS) == 27 and len(set(PAGE_IDS)) == 27


@pytest.mark.parametrize("page", PAGE_IDS)
def test_page_renders_en(page):
    at = _run(page, "en")
    _assert_clean(at, page)
    # every module shows a computed result: at least one metric, chart, table, map or report element
    n = (len(at.metric) + len(at.dataframe) + len(at.get("plotly_chart")) + len(at.get("iframe"))
         + len(at.get("deck_gl_json_chart")) + len(at.success) + len(at.info) + len(at.json))
    assert n > 0, f"{page}: no computed output"


@pytest.mark.parametrize("lang", ["uz", "ar", "zh", "hi", "ru"])
@pytest.mark.parametrize("page", ["dashboard", "route", "oxygen", "risk", "integration", "reports"])
def test_pages_other_languages(page, lang):
    _assert_clean(_run(page, lang), f"{page}/{lang}")


def test_language_switch_changes_ui():
    at = _run("dashboard", "en")
    title_en = at.markdown[0].value if at.markdown else ""
    sel = at.selectbox(key="lang_select")
    sel.set_value("uz").run()
    _assert_clean(at, "dashboard/uz")
    assert at.query_params.get("lang") in ("uz", ["uz"])
    texts = " ".join(m.value for m in at.markdown)
    assert "Missiya" in texts and texts != title_en


def test_sidebar_navigation():
    at = _run("dashboard", "en")
    btn = [b for b in at.sidebar.button if "05" in b.label]
    assert btn, "route button missing in sidebar"
    btn[0].click().run()
    _assert_clean(at, "nav->route")
    assert "05" in " ".join(m.value for m in at.markdown)


def test_integration_button_produces_recommendation():
    at = _run("integration", "en")
    b = [x for x in at.button if x.label and "integrated" in x.label.lower()]
    if b:
        b[0].click().run()
    _assert_clean(at, "integration")
    labels = [m.label for m in at.metric]
    assert any("Recommended" in lbl for lbl in labels)


def _radio_with(at, option, label="Example (synthetic)"):
    """Radios show translated labels (format_func); find the one that offers the example source."""
    for r in at.radio:
        if label in [str(o) for o in r.options]:
            return r
    raise AssertionError(f"no radio with option {option}")


def test_ml_tab_trains_model_and_shows_metrics(tmp_path, monkeypatch):
    from mars_survive.ai import traversability as TV
    at = _run("ai", "en")
    btn = [b for b in at.button if b.label and "Train and evaluate" in b.label]
    assert btn, "train button missing"
    btn[0].click().run(timeout=600)
    _assert_clean(at, "ai/train")
    labels = [m.label for m in at.metric]
    assert "F1 (test)" in labels and "ROC-AUC" in labels
    assert any("Model trained" in s.value for s in at.success)
    assert TV.MODEL_PATH.exists() and TV.card()["test"]["f1"] > 0.5


def test_route_uses_ml_weight_slider():
    at = _run("route", "en")
    sl = [s for s in at.slider if "ML weight" in (s.label or "")]
    assert sl, "ML weight slider missing (model should exist after training test)"
    sl[0].set_value(0.8).run()
    _assert_clean(at, "route/ml")


def test_space_weather_example_flags_radiation():
    at = _run("meda", "en")
    r = _radio_with(at, "example")
    r.set_value("example").run()
    _assert_clean(at, "meda/donki")
    m = {x.label: x.value for x in at.metric}
    assert m.get("EVA radiation flag") == "High"
    # the flag reaches the risk module
    at.query_params["page"] = "risk"
    at.run()
    _assert_clean(at, "risk after donki")


def test_perseverance_example_and_nearest_points():
    at = _run("science", "en")
    r = _radio_with(at, "example")
    r.set_value("example").run()
    _assert_clean(at, "science/pv")
    labels = [m.label for m in at.metric]
    assert "Traverse points" in labels and "Driven distance" in labels
    assert any("Perseverance passed" in s.value or "from the traverse" in w.value
               for s in at.success for w in (at.warning or [s]))


def test_globe_planet_to_crater():
    at = _run("map", "en")
    _assert_clean(at, "map/globe")
    r = [x for x in at.radio if x.key == "globe_radio"]
    assert r, "globe site list missing"
    r[0].set_value("jezero").run()
    _assert_clean(at, "globe/jezero")
    md = " ".join(m.value for m in at.markdown)
    assert "From the planet to the crater" in md
    assert any("Zoomed to" in s.value for s in at.success)
    r = [x for x in at.radio if x.key == "globe_radio"][0]
    r.set_value("curiosity").run()
    _assert_clean(at, "globe/curiosity")
    assert any("outside the loaded DEM" in i.value for i in at.info)
