"""Functional test of the demo scenario (master prompt §18): plan 4 routes, compute resources, risk,
simulation, then export a report (PDF/HTML/CSV/JSON/XLSX) in Uzbek."""
import json
from pathlib import Path

import numpy as np

from mars_survive.integration import pipeline
from mars_survive.integration.mission import MissionParams
from mars_survive.localization.i18n import t
from mars_survive.reporting import export


def test_demo_end_to_end(engine, tmp_path, monkeypatch):
    mp = MissionParams()
    res = pipeline.run(engine, (18.4447, 77.4508), (18.455, 77.405), mp)
    assert set(res["routes"]) == {"shortest", "lowest_slope", "lowest_hazard", "balanced"}
    assert res["recommended"] in res["routes"]
    found = [r for r in res["routes"].values() if r.found]
    assert len(found) == 4
    # shortest is never longer (2D) than the others; low-slope route never steeper than shortest
    d = {k: r.dist2d_m[-1] for k, r in res["routes"].items()}
    assert d["shortest"] <= min(d.values()) + 1e-6
    assert res["routes"]["lowest_slope"].slope_deg.max() <= res["routes"]["shortest"].slope_deg.max() + 1e-6
    prof = res["profiles"][res["recommended"]]
    assert np.all(np.diff(prof["t_s"]) >= 0) and np.all(np.diff(prof["o2_l"]) >= 0)
    assert res["risk_overall"]["level"] in ("low", "medium", "high", "critical")

    monkeypatch.setattr(export.C, "REPORTS_DIR", tmp_path)
    best = res["routes"][res["recommended"]].summary()
    report = {"title": "MARS SURVIVE 360 — " + t("modules.reports", "uz"), "lang": "uz", "rtl": False,
              "generated": "test", "region": t("region.jezero", "uz"), "data_class": "DEM: Synthetic",
              "mission": {t("lbl.mission_name", "uz"): mp.name},
              "sections": [{"key": "route", "title": t("modules.route", "uz"),
                            "kv": {t("lbl.dist2d", "uz"): f"{best['distance_2d_km']:.3f} km",
                                   t("col.max_slope_deg", "uz"): f"{best['max_slope_deg']:.1f}°"},
                            "table": [{"strategy": k, **{kk: vv for kk, vv in r.summary().items() if isinstance(vv, (int, float))}}
                                      for k, r in res["routes"].items()]}]}
    out = export.save_all(report, stem="demo_uz")
    for ext in ("pdf", "html", "csv", "json", "xlsx"):
        p = Path(out[ext])
        assert p.exists() and p.stat().st_size > 50, ext
    assert Path(out["pdf"]).read_bytes()[:5] == b"%PDF-"
    json.loads(Path(out["json"]).read_text(encoding="utf-8"))
