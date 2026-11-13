"""User Settings & Configuration (module 25), persisted to data/settings.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import config as C


@dataclass
class Settings:
    language: str = "uz"
    theme: str = "dark"                 # dark | light
    distance_unit: str = "km"           # km | mi
    temperature_unit: str = "C"         # C | K
    map_basemap: str = "Viking MDIM 2.1 colour (Mars Trek)"
    map_zoom: int = 11
    dem_path: str = ""
    ai_model_path: str = str(C.MODELS_DIR / "yolo")
    spice_dir: str = str(C.SPICE_DIR)
    data_dir: str = str(C.DATA)
    default_budget_h: float = 7.0
    default_slope_limit: float = 20.0


def load(path: Path = C.SETTINGS_PATH) -> Settings:
    if path.exists():
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(Settings)}
            return Settings(**{k: v for k, v in d.items() if k in known})
        except (json.JSONDecodeError, TypeError):
            pass
    return Settings()


def save(s: Settings, path: Path = C.SETTINGS_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(s), indent=2, ensure_ascii=False), encoding="utf-8")


def fmt_dist(m: float, unit: str = "km", nd: int = 2) -> str:
    if m is None:
        return "-"
    return f"{m / 1609.344:.{nd}f} mi" if unit == "mi" else f"{m / 1000:.{nd}f} km"


def fmt_temp(c: float, unit: str = "C") -> str:
    return f"{c + 273.15:.1f} K" if unit == "K" else f"{c:.1f} °C"
