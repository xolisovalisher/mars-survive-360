"""Shared helpers: logging, data-class labels, safe execution."""
from __future__ import annotations

import logging
import traceback
from enum import Enum
from logging.handlers import RotatingFileHandler

import config as C


class DataClass(str, Enum):
    """Provenance class shown next to every dataset and result."""
    REAL = "Real"
    SYNTHETIC = "Synthetic"
    SIMULATED = "Simulated"
    USER = "User Supplied"


_LOGGER = None


def get_logger(name: str = "mars_survive") -> logging.Logger:
    global _LOGGER
    if _LOGGER is None:
        lg = logging.getLogger("mars_survive")
        lg.setLevel(logging.INFO)
        if not lg.handlers:
            fh = RotatingFileHandler(C.LOGS_DIR / "app.log", maxBytes=2_000_000, backupCount=3,
                                     encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            lg.addHandler(fh)
        _LOGGER = lg
    return logging.getLogger(name if name.startswith("mars_survive") else f"mars_survive.{name}")


class ModuleError(Exception):
    """Error with a user-readable message (translation key + details)."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}")
        self.key = key
        self.detail = detail


def safe_call(fn, *args, **kwargs):
    """Run fn; return (result, None) or (None, error-string). Errors are logged."""
    try:
        return fn(*args, **kwargs), None
    except ModuleError as e:
        get_logger().warning("module error %s %s", e.key, e.detail)
        return None, f"{e.key}|{e.detail}"
    except Exception as e:  # noqa: BLE001 - one module must never crash the app
        get_logger().error("error in %s: %s\n%s", getattr(fn, "__name__", fn), e, traceback.format_exc())
        return None, f"{e.__class__.__name__}: {e}"
