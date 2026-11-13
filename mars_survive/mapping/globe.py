"""3-D Mars globe (module 02): NASA global mosaic on a rotatable sphere, landing sites, analysis window.

Texture sources, in order of preference:
1. NASA Mars Trek Viking MDIM 2.1 colour mosaic — stitched from Trek WMTS tiles (level 3 → 4096 × 2048) when the
   computer is online, then cached in data/cache/ (Real, sharper).
2. Bundled USGS/NASA Viking colour mosaic 925 m, 2048 × 1024 (Real, public domain) — always available, offline.
Both are real NASA/USGS imagery; nothing synthetic is drawn on the globe.

Coordinates: planetocentric latitude, east longitude. The texture is shifted from 0…360°E to −180…180° for
deck.gl's BitmapLayer. deck.gl's globe has Earth's radius; only angles are used, so the picture is exact in
latitude/longitude (marker sizes are visual only).
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

import config as C
from mars_survive.common import ModuleError, get_logger

log = get_logger("mapping.globe")

BUNDLED = C.ROOT / "assets" / "mars" / "mars_viking_clrmosaic_925m_2048x1024_lon0-360.jpg"
TREK_CACHE = C.DATA / "cache" / "trek_viking_mdim21_level3_4096x2048_lon-180-180.jpg"
TREK_LAYER = "Viking_MDIM21_ClrMosaic_global_232m"
TREK_LEVEL = 3                                     # 2^(z+1) × 2^z tiles of 256 px → 16 × 8 → 4096 × 2048


@dataclass(frozen=True)
class Site:
    key: str
    lat: float
    lon: float
    kind: str          # crater | landing
    source: str
    has_dem: bool


SITES = [
    Site("jezero", 18.38, 77.58, "crater", "IAU/USGS Gazetteer of Planetary Nomenclature (crater centre, D ≈ 49 km)", True),
    Site("perseverance", 18.4447, 77.4508, "landing", "NASA/JPL Mars 2020 — Octavia E. Butler landing site", True),
    Site("curiosity", -4.5895, 137.4417, "landing", "NASA/JPL MSL — Bradbury Landing, Gale crater", False),
]


@dataclass
class Texture:
    image: Image.Image          # equirectangular, longitude −180…180 (left edge −180°)
    data_class: str
    source: str
    resolution_km: float


def _roll_0_360_to_pm180(a: np.ndarray) -> np.ndarray:
    return np.roll(a, a.shape[1] // 2, axis=1)


def bundled_texture() -> Texture:
    if not BUNDLED.is_file():
        raise ModuleError("err.missing_file", str(BUNDLED.name))
    im = Image.open(BUNDLED).convert("RGB")
    a = _roll_0_360_to_pm180(np.asarray(im))
    return Texture(Image.fromarray(a), "Real",
                   "USGS/NASA Mars Viking colour mosaic 925 m (public domain), 2048×1024 copy", 2 * np.pi * 3389.5 / 2048)


def trek_texture() -> Texture | None:
    if not TREK_CACHE.is_file():
        return None
    try:
        im = Image.open(TREK_CACHE).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    return Texture(im, "Real", f"NASA Mars Trek — Viking MDIM 2.1 colour mosaic, {im.width}×{im.height} (cached)",
                   2 * np.pi * 3389.5 / im.width)


def best_texture(prefer_trek: bool = True) -> Texture:
    """Sharper Trek mosaic if it was cached earlier, otherwise the bundled NASA/USGS mosaic (always present)."""
    if prefer_trek:
        t = trek_texture()
        if t is not None:
            return t
    return bundled_texture()


def tile_url(z: int, x: int, y: int) -> str:
    return C.TREK.format(layer=TREK_LAYER, ext="jpg").format(z=z, x=x, y=y)


def fetch_trek_texture(level: int = TREK_LEVEL, fetch=None, progress=None) -> Texture:
    """Download all Trek WMTS tiles of one level (EPSG:4326 tiling: 2^(level+1) × 2^level tiles) and stitch them.
    `fetch(url) -> bytes` can be injected for tests. Any missing tile aborts (no partial globe is cached)."""
    import requests
    nx, ny = 2 ** (level + 1), 2 ** level
    if fetch is None:
        def fetch(url):
            r = requests.get(url, timeout=20, headers={"User-Agent": f"MARS-SURVIVE-360/{C.VERSION}"})
            if r.status_code != 200:
                raise ModuleError("err.http", f"HTTP {r.status_code}")
            return r.content
    canvas = Image.new("RGB", (nx * 256, ny * 256))
    n = 0
    try:
        for y in range(ny):
            for x in range(nx):
                data = fetch(tile_url(level, x, y))
                tile = Image.open(io.BytesIO(data)).convert("RGB")
                if tile.size != (256, 256):
                    tile = tile.resize((256, 256))
                canvas.paste(tile, (x * 256, y * 256))
                n += 1
                if progress:
                    progress(n / (nx * ny))
    except ModuleError:
        raise
    except Exception as e:  # noqa: BLE001 — network / DNS / decoding
        raise ModuleError("err.network", e.__class__.__name__) from e
    a = np.asarray(canvas)
    if a.mean() < 5:                                # all-black result = service answered with empty tiles
        raise ModuleError("err.http", "empty tiles")
    TREK_CACHE.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(TREK_CACHE, "JPEG", quality=90)
    log.info("Trek globe texture cached: %s tiles", n)
    return trek_texture()


def data_url(tex: Texture, max_width: int = 4096, quality: int = 88) -> str:
    im = tex.image
    if im.width > max_width:
        im = im.resize((max_width, max_width // 2), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def sample_rgb(tex: Texture, lat: float, lon: float, r: int = 2) -> tuple:
    """Mean colour of the texture around (lat, lon) — used by tests to check georeferencing."""
    a = np.asarray(tex.image).astype(float)
    h, w = a.shape[:2]
    x = int(((lon + 180) % 360) / 360 * w)
    y = int((90 - lat) / 180 * h)
    return tuple(a[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].reshape(-1, 3).mean(axis=0))


def labels_overlay(width: int = 4096) -> str:
    """Transparent PNG (equirectangular, −180…180) with the site NUMBERS 1, 2, 3 next to the markers.
    deck.gl's TextLayer does not render in GlobeView, so the numbers are drawn into a separate overlay layer —
    the NASA texture itself is never modified. Names are listed with the same numbers beside the globe."""
    from PIL import ImageDraw, ImageFont
    h = width // 2
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    font_path = C.ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
    size = max(12, width // 120)
    try:
        font = ImageFont.truetype(str(font_path), size)
    except OSError:
        font = ImageFont.load_default()
    offsets = {"jezero": (-3.0, 3.0), "perseverance": (3.0, -2.6), "curiosity": (2.6, 2.6)}   # degrees: dx, dy
    for i, s in enumerate(SITES, 1):
        dx, dy = offsets.get(s.key, (1.0, 1.0))
        x = (s.lon + dx + 180) / 360 * width
        y = (90 - (s.lat + dy)) / 180 * h
        txt = str(i)
        bb = d.textbbox((0, 0), txt, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad = size // 4
        d.rounded_rectangle([x - tw / 2 - pad, y - th / 2 - pad, x + tw / 2 + pad, y + th / 2 + pad + 2], radius=pad,
                            fill=(10, 14, 22, 220), outline=(255, 255, 255, 230), width=2)
        d.text((x - tw / 2, y - th / 2 - bb[1]), txt, font=font, fill=(255, 255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def graticule(step: int = 30) -> list:
    lines = []
    for lon in range(-180, 180, step):
        lines.append({"path": [[lon, la] for la in range(-90, 91, 5)]})
    for la in range(-60, 61, step):
        lines.append({"path": [[lo, la] for lo in range(-180, 181, 5)]})
    return lines


def _q(s: str) -> str:
    """Quote a literal string for pydeck (unquoted strings become @deck.gl/json accessor expressions)."""
    return "'" + s + "'"


def deck(tex_url: str, labels: dict, grid=None, focus: Site | None = None, show_grid: bool = True,
         selected_key: str | None = None, dem_overlay_url: str | None = None):
    """pydeck Deck with the globe view. `labels`: {site key: translated name}. `dem_overlay_url`: PNG drawn over the
    DEM analysis window (hillshade of the active DEM) — the crater-scale detail when zoomed in."""
    import pydeck as pdk
    layers = [pdk.Layer("BitmapLayer", id="mars", image=_q(tex_url), bounds=[-180, -90, 180, 90])]
    if grid is not None and dem_overlay_url:
        (s0, w0), (n0, e0) = grid.bounds if not callable(grid.bounds) else grid.bounds()
        layers.append(pdk.Layer("BitmapLayer", id="dem_hillshade", image=_q(dem_overlay_url), bounds=[w0, s0, e0, n0],
                                opacity=0.9))
    if show_grid:
        layers.append(pdk.Layer("PathLayer", graticule(), id="grid", get_path="path", get_color=[255, 255, 255, 60],
                                width_min_pixels=1))
    if grid is not None:
        (s, w), (n, e) = grid.bounds if not callable(grid.bounds) else grid.bounds()
        layers.append(pdk.Layer("PathLayer", [{"path": [[w, s], [e, s], [e, n], [w, n], [w, s]]}], id="dem",
                                get_path="path", get_color=[255, 196, 0], width_min_pixels=2))
    pts = [{"key": s.key, "name": f"{i}. " + labels.get(s.key, s.key), "lat": s.lat, "lon": s.lon,
            "color": [255, 196, 0] if s.key == selected_key else ([0, 229, 255] if s.kind == "landing" else [255, 87, 51])}
           for i, s in enumerate(SITES, 1)]
    layers.append(pdk.Layer("ScatterplotLayer", pts, id="sites", get_position=["lon", "lat"], get_fill_color="color",
                            get_radius=90000, radius_min_pixels=7, radius_max_pixels=14, stroked=True,
                            get_line_color=[0, 0, 0], line_width_min_pixels=1, pickable=True))
    if focus is None:                                   # numbered labels (see labels_overlay)
        layers.insert(1, pdk.Layer("BitmapLayer", id="labels", image=_q(labels_overlay()), bounds=[-180, -90, 180, 90]))
    if focus is not None:
        view = pdk.ViewState(longitude=focus.lon, latitude=focus.lat, zoom=9.2 if focus.has_dem else 3.5)
    else:
        view = pdk.ViewState(longitude=77.45, latitude=18.44, zoom=1.45)
    return pdk.Deck(layers=layers, views=[pdk.View(type="_GlobeView", controller=True)], initial_view_state=view,
                    map_provider=None, map_style=None, tooltip={"text": "{name}"})
