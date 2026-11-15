"""2-D mission map drawn with deck.gl (pydeck) — used by the browser build.

The desktop app draws its 2-D maps with Folium/Leaflet. In the one-file browser
build Leaflet's stylesheet and the Mars Trek tiles come from other web sites,
which a shared page may not load, so the same picture is drawn with deck.gl,
which ships inside Streamlit and needs no network:

* raster layers (hillshade, slope, hazard …) are the same PNG data URLs,
* routes, the Perseverance traverse and markers are vector layers,
* a click on the map returns the clicked point through a fine, almost
  invisible grid of pickable points (deck.gl reports picked objects only).

The class mimics the small part of the folium.Map API that the pages use
(add_child / route / path / finish), so pages keep one code path.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .globe import _q

CLICK_LAYER = "click_grid"


def _rgb(hex_color: str, a: int = 255) -> list[int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a]
    except ValueError:
        return [255, 255, 255, a]


@dataclass
class Marker:
    lat: float
    lon: float
    text: str
    bg: str
    tip: str
    fg: str = "#111"
    size: int = 24


@dataclass
class DeckMap:
    bounds: list            # [[south, west], [north, east]]
    center: tuple
    zoom: float | None = None
    overlays: list = field(default_factory=list)   # (name, url, show)
    paths: list = field(default_factory=list)      # dict(path, color, width, tip, dash)
    markers: list = field(default_factory=list)

    # --- folium-like API -------------------------------------------------
    def add_child(self, obj):
        if isinstance(obj, Marker):
            self.markers.append(obj)
        return self

    def add_to(self, _):
        return self

    def route(self, lat, lon, color="#ffd166", weight=4, tooltip="", dash=False):
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        ok = np.isfinite(lat) & np.isfinite(lon)
        pts = [[round(float(b), 7), round(float(a), 7)] for a, b in zip(lat[ok], lon[ok])]
        if len(pts) >= 2:
            self.paths.append({"path": pts, "color": _rgb(color), "width": float(weight), "tip": tooltip, "dash": dash})

    # --- rendering --------------------------------------------------------
    def fit_zoom(self, width_px: int = 820, height_px: int = 540) -> float:
        (s, w), (n, e) = self.bounds
        lon_span = max(e - w, 1e-6)
        y = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))  # noqa: E731
        lat_span_merc = max(abs(y(n) - y(s)), 1e-9)
        zx = math.log2(width_px * 360.0 / (lon_span * 512.0))
        zy = math.log2(height_px * 2 * math.pi / (lat_span_merc * 512.0))
        return round(min(zx, zy) - 0.05, 2)

    def click_points(self, n: int = 110) -> list[dict]:
        (s, w), (nn, e) = self.bounds
        lats = np.linspace(s, nn, n)
        lons = np.linspace(w, e, n)
        return [{"lat": round(float(a), 6), "lon": round(float(b), 6), "tip": f"{a:.4f}° N, {b:.4f}° E"}
                for a in lats for b in lons]

    def deck(self, height: int = 540, clickable: bool = False, show: set | None = None):
        import pydeck as pdk
        (s, w), (n, e) = self.bounds
        layers = []
        for i, (name, url, on) in enumerate(self.overlays):
            if (name in show) if show is not None else on:
                layers.append(pdk.Layer("BitmapLayer", id=f"ov{i}", image=_q(url), bounds=[w, s, e, n],
                                        opacity=1.0, pickable=False))
        if clickable:
            (cs, cw), (cn, ce) = self.bounds
            spacing = max((cn - cs), (ce - cw)) / 110
            layers.append(pdk.Layer("ScatterplotLayer", id=CLICK_LAYER, data=self.click_points(),
                                    get_position=["lon", "lat"], get_radius=spacing * 111_000 * 0.55,
                                    radius_units="'meters'", get_fill_color=[255, 255, 255, 2], pickable=True,
                                    auto_highlight=True, highlight_color=[255, 255, 255, 90]))
        for j, p in enumerate(self.paths):
            layers.append(pdk.Layer("PathLayer", id=f"path{j}", data=[p], get_path="path", get_color="color",
                                    get_width="width", width_units="'pixels'", width_min_pixels=1,
                                    joint_rounded=True, cap_rounded=True, pickable=True))
        if self.markers:
            md = [{"lat": m.lat, "lon": m.lon, "text": m.text, "tip": m.tip, "bg": _rgb(m.bg), "fg": _rgb(m.fg),
                   "r": m.size / 2} for m in self.markers]
            layers.append(pdk.Layer("ScatterplotLayer", id="markers", data=md, get_position=["lon", "lat"],
                                    get_fill_color="bg", get_line_color=[255, 255, 255, 255], stroked=True,
                                    line_width_min_pixels=2, get_radius="r", radius_units="'pixels'", pickable=True))
            # marker labels are plain ASCII (deck.gl's default character set); no character_set needed
            layers.append(pdk.Layer("TextLayer", id="marker_text", data=md, get_position=["lon", "lat"],
                                    get_text="text", get_color="fg", get_size=12, size_units="'pixels'",
                                    font_weight=700, pickable=False))
        view = pdk.ViewState(latitude=self.center[0], longitude=self.center[1],
                             zoom=self.zoom if self.zoom is not None else self.fit_zoom(height_px=height),
                             min_zoom=8, max_zoom=17, pitch=0, bearing=0)
        return pdk.Deck(layers=layers, initial_view_state=view, map_style=None,
                        map_provider=None, tooltip={"text": "{tip}"},
                        views=[pdk.View(type="MapView", controller=True)])


def base_map(grid, layers: dict | None = None, center=None) -> DeckMap:
    (s, w), (n, e) = grid.bounds
    m = DeckMap(bounds=[[s, w], [n, e]], center=center or grid.center)
    for name, (url, show) in (layers or {}).items():
        m.overlays.append((name, url, show))
    return m


def picked_point(event) -> dict | None:
    """Turn a pydeck selection event into the {'last_clicked': {'lat','lng'}} dict that st_folium returns."""
    try:
        sel = event.selection if hasattr(event, "selection") else event.get("selection", {})
        objs = (sel.get("objects") if isinstance(sel, dict) else getattr(sel, "objects", {})) or {}
    except Exception:  # noqa: BLE001
        return None
    for layer in (CLICK_LAYER, "markers"):
        for o in objs.get(layer, []) or []:
            if "lat" in o and "lon" in o:
                return {"last_clicked": {"lat": float(o["lat"]), "lng": float(o["lon"])}}
    return None
