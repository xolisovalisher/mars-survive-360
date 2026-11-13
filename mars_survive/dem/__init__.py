"""DEM data management (module 4)."""
from __future__ import annotations

from .grid import Grid
from .loader import build_grid_from_dem, load_processed
from .synthetic import synthetic_grid


def get_active_grid() -> Grid:
    """Processed real/user DEM if present, otherwise the labelled SYNTHETIC DEM."""
    g = load_processed()
    return g if g is not None else synthetic_grid()


__all__ = ["Grid", "synthetic_grid", "load_processed", "build_grid_from_dem", "get_active_grid"]
