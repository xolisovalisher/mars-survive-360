"""Compute the regression snapshot (key numbers of v1.0.0 on the bundled SYNTHETIC DEM).
python -m tests.regression.golden  → rewrites tests/fixtures/golden_v1.json (only on purpose, after review)."""
import json
from pathlib import Path

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "golden_v1.json"
START, GOAL = (18.4447, 77.4508), (18.455, 77.405)


def snapshot(engine) -> dict:
    from datetime import datetime, timezone

    from mars_survive.communication.link import PRESETS, link_budget
    from mars_survive.integration.mission import MissionParams
    from mars_survive.mapping.coords import centric_to_graphic, haversine_m
    from mars_survive.spice.mars_time import mars_time
    import numpy as np
    out = {}
    mt = mars_time(datetime(2000, 1, 6, tzinfo=timezone.utc), 0.0)
    out["mars24"] = {"Ls": mt["Ls"], "MSD": mt["MSD"], "eot_min": mt["eot_min"]}
    out["haversine_1deg_m"] = float(haversine_m(0, 0, 1, 0))
    out["graphic_lat_jezero"] = float(centric_to_graphic(18.4447))
    lb = link_budget(PRESETS["uhf_orbiter"])
    out["link_uhf"] = {"fspl_db": lb["fspl_db"], "margin_db": lb["margin_db"]}
    T = engine.T
    out["terrain"] = {k: float(np.nanmean(getattr(T, k))) for k in ("slope", "roughness", "tri", "relief")}
    out["hazard_levels"] = {str(i): int((engine.H.level == i).sum()) for i in range(5)}
    mp = MissionParams()
    routes = engine.plan_four(START, GOAL, mp)
    out["routes"] = {}
    for k, r in routes.items():
        s = r.summary()
        prof = engine.resources(r, mp)
        out["routes"][k] = {"found": s["found"], "d2_km": s["distance_2d_km"], "d3_km": s["distance_3d_km"],
                            "max_slope": s["max_slope_deg"], "hazard_mean": s["hazard_mean"],
                            "duration_h": float(prof["duration_h"]), "o2_l": float(prof["o2_total_l"])}
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mars_survive.dem import synthetic_grid
    from mars_survive.integration.engine import Engine
    GOLDEN.write_text(json.dumps(snapshot(Engine(synthetic_grid())), indent=2), encoding="utf-8")
    print("written", GOLDEN)
