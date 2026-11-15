"""System Diagnostics (module 26). Each check is independent and never raises."""
from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import shutil
import sys
import time

import config as C

LIBS = ["streamlit", "folium", "streamlit_folium", "plotly", "numpy", "scipy", "pandas", "sklearn", "rasterio",
        "networkx", "cv2", "PIL", "fpdf", "openpyxl", "spiceypy", "defusedxml", "fastapi", "pydantic", "requests",
        "psutil", "uharfbuzz", "joblib", "pydeck", "shapely", "astropy", "torch", "geopandas", "ultralytics"]
OPTIONAL = {"spiceypy", "uharfbuzz", "ultralytics", "torch", "geopandas", "astropy", "fastapi", "shapely"}
if C.BROWSER:  # the browser build draws maps with deck.gl and has no OS process information
    OPTIONAL |= {"folium", "streamlit_folium", "psutil"}
MODULES = ["dem", "terrain.analysis", "hazards.detect", "routing.planner", "routing.eva", "ai.vision", "ai.terrain_units",
           "navigation.ekf", "navigation.metrics", "communication.link", "relay.orbits", "spice.kernels",
           "spice.mars_time", "meda.environment", "telemetry.suit", "oxygen.manager", "energy.model",
           "timeline.planner", "science.catalog", "simulation.engine", "risk.assessment", "ingestion.importer",
           "provenance.registry", "reporting.export", "localization.i18n", "settings.store", "integration.pipeline",
           "mapping.coords", "mapping.views", "dashboard.kpis", "ai.traversability", "nasa_live.donki",
           "nasa_live.perseverance", "reporting.gis"]


def python_info() -> dict:
    return {"python": sys.version.split()[0], "platform": platform.platform(), "ok": sys.version_info >= (3, 10)}


def libraries() -> list[dict]:
    out = []
    for name in dict.fromkeys(LIBS):
        try:
            m = importlib.import_module(name)
            out.append({"library": name, "version": getattr(m, "__version__", "ok"), "ok": True,
                        "optional": name in OPTIONAL})
        except Exception as e:  # noqa: BLE001
            out.append({"library": name, "version": None, "ok": False, "optional": name in OPTIONAL,
                        "error": e.__class__.__name__})
    return out


def modules_health(quick: bool = False) -> list[dict]:
    """Import every platform module and time it. quick=True only checks that each module file is
    present (no import) — used for the header badge in the browser build, where importing all 34
    modules at start-up would add seconds before the first page shows."""
    out = []
    for m in MODULES:
        t0 = time.perf_counter()
        try:
            if quick:
                if importlib.util.find_spec(f"mars_survive.{m}") is None:
                    raise ModuleNotFoundError(m)
                out.append({"module": m, "ok": True, "ms": None, "error": ""})
                continue
            importlib.import_module(f"mars_survive.{m}")
            out.append({"module": m, "ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1), "error": ""})
        except Exception as e:  # noqa: BLE001
            out.append({"module": m, "ok": False, "ms": None, "error": f"{e.__class__.__name__}: {e}"})
    return out


def directories() -> list[dict]:
    out = []
    for p in [C.DATA, C.DATA_RAW, C.DATA_PROCESSED, C.DATA_UPLOADS, C.MODELS_DIR, C.SPICE_DIR, C.REPORTS_DIR, C.LOGS_DIR]:
        writable = False
        try:
            f = p / ".write_test"
            f.write_text("x")
            f.unlink()
            writable = True
        except OSError:
            pass
        out.append({"path": str(p.relative_to(C.ROOT)), "exists": p.exists(), "writable": writable})
    return out


def data_assets() -> dict:
    from mars_survive.ai.vision import yolo_status
    from mars_survive.dem.loader import PROCESSED_NPZ
    from mars_survive.spice.kernels import status as kstatus
    raw = list(C.DATA_RAW.glob("*.tif"))
    return {"dem_processed": PROCESSED_NPZ.exists(), "dem_raw_files": [p.name for p in raw],
            "yolo": yolo_status(), "spice": [{"kind": k["kind"], "present": k["present"]} for k in kstatus()]}


def resources() -> dict:
    du = shutil.disk_usage(C.ROOT)
    d = {"disk_free_gb": round(du.free / 1e9, 1), "disk_total_gb": round(du.total / 1e9, 1)}
    try:
        import psutil
        vm = psutil.virtual_memory()
        d.update(ram_total_gb=round(vm.total / 1e9, 1), ram_available_gb=round(vm.available / 1e9, 1),
                 cpu_count=psutil.cpu_count(), process_rss_mb=round(psutil.Process().memory_info().rss / 1e6, 1))
    except Exception:  # noqa: BLE001
        pass
    return d


def last_test_report() -> dict | None:
    p = C.ROOT / "docs" / "test_results.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def log_tail(n: int = 40) -> str:
    p = C.LOGS_DIR / "app.log"
    if not p.exists():
        return ""
    return "".join(p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-n:])
