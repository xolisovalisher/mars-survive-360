"""Mars 2D/3D Map (module 2): Folium (EPSG:4326 + NASA Mars Trek) and Plotly 3D terrain.

Leaflet's scale bar/measure tools assume Earth's radius, so they are not used;
all distances come from mars_survive.mapping.coords on the Mars sphere.
"""
from __future__ import annotations

import base64
import io
import json

import matplotlib
import numpy as np
from matplotlib import colors
from PIL import Image

import config as C

matplotlib.use("Agg")


# ---------------------------------------------------------------- raster -> PNG
def to_rgba(a, cmap="terrain", vmin=None, vmax=None, alpha=0.75):
    a = np.asarray(a, float)
    if not np.isfinite(a).any():
        return np.zeros(a.shape + (4,), np.uint8)
    vmin = np.nanpercentile(a, 2) if vmin is None else vmin
    vmax = np.nanpercentile(a, 98) if vmax is None else vmax
    norm = colors.Normalize(vmin, vmax, clip=True)
    rgba = matplotlib.colormaps[cmap](norm(np.nan_to_num(a, nan=vmin)))
    rgba[..., 3] = np.where(np.isfinite(a), alpha, 0)
    return (rgba * 255).astype(np.uint8)


def classes_rgba(cls, palette: dict, alpha=0.65):
    out = np.zeros(cls.shape + (4,), np.uint8)
    for k, hexcol in palette.items():
        rgb = (np.array(colors.to_rgb(hexcol)) * 255).astype(np.uint8)
        m = cls == k
        out[m, :3] = rgb
        out[m, 3] = int(alpha * 255)
    return out


def png_url(rgba: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


HAZARD_PALETTE = {1: "#ffb000", 2: "#ff6a00", 3: "#d7191c", 4: "#7b2cbf"}
ROUTE_COLORS = {"shortest": "#4cc9f0", "lowest_slope": "#b5179e", "lowest_hazard": "#06d6a0", "balanced": "#ffd166"}


def div_marker(text, bg="#ffd166", fg="#111", size=24):
    if C.BROWSER:
        return (text, bg, fg, size)
    import folium
    return folium.DivIcon(icon_size=(size, size), icon_anchor=(size // 2, size // 2),
                          html=f'<div style="background:{bg};color:{fg};border-radius:50%;width:{size}px;height:{size}px;'
                               f'line-height:{size}px;text-align:center;font-weight:700;font-size:12px;'
                               f'border:2px solid #fff;box-shadow:0 0 4px #000">{text}</div>')


def base_map(grid, layers: dict[str, tuple[str, bool]] | None = None, zoom: int = 11, center=None,
             basemap: str | None = None, height_hint: int = 600):
    """layers: name -> (png data url, show). Returns folium.Map (desktop) or DeckMap (browser build)."""
    if C.BROWSER:
        from .deckmap import base_map as deck_base
        return deck_base(grid, layers, center)
    import folium
    lat, lon = center or grid.center
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, crs="EPSG4326", control_scale=False,
                   max_zoom=16, min_zoom=5, prefer_canvas=True)
    order = list(C.TREK_LAYERS)
    if basemap in order:
        order.remove(basemap)
        order.insert(0, basemap)
    for name in order:
        layer, ext, mz, attr = C.TREK_LAYERS[name]
        folium.TileLayer(C.TREK.format(layer=layer, ext=ext), attr=attr, name=name, max_native_zoom=mz, max_zoom=16,
                         overlay=False, no_wrap=True).add_to(m)
    b = grid.bounds
    for name, (url, show) in (layers or {}).items():
        folium.raster_layers.ImageOverlay(url, bounds=b, name=name, show=show).add_to(m)
    # (no MousePosition plugin: it is fetched from a GitHub CDN path, and if that one script fails to load the
    #  whole Leaflet map stays blank. Coordinates are shown in the app panels instead.)
    return m


def add_route(m, lat, lon, color="#ffd166", weight=4, tooltip=""):
    if C.BROWSER:
        return m.route(lat, lon, color, weight, tooltip)
    import folium
    folium.PolyLine(list(zip(np.asarray(lat).tolist(), np.asarray(lon).tolist())), color=color, weight=weight,
                    opacity=0.95, tooltip=tooltip).add_to(m)


def finish(m):
    if C.BROWSER:
        return m
    import folium
    folium.LayerControl(collapsed=True, position="topright").add_to(m)
    return m


# ---------------------------------------------------------------- 3D
def surface_3d(grid, routes: dict | None = None, max_cells: int = 160, exaggeration: float = 3.0, hazard=None,
               title=""):
    import plotly.graph_objects as go
    z = grid.z
    step = max(1, int(np.ceil(max(z.shape) / max_cells)))
    zz = z[::step, ::step]
    rows = np.arange(0, z.shape[0], step)
    cols = np.arange(0, z.shape[1], step)
    # local metric coordinates (km) so the 3D shape is not distorted
    lat0 = grid.center[0]
    x = (grid.lon(cols) - grid.center[1]) * np.radians(1) * C.R_MARS_DTM * np.cos(np.radians(lat0)) / 1000
    y = (grid.lat(rows) - lat0) * np.radians(1) * C.R_MARS_DTM / 1000
    surfacecolor = None if hazard is None else hazard[::step, ::step]
    fig = go.Figure(go.Surface(x=x, y=y, z=zz / 1000 * 1.0, surfacecolor=surfacecolor,
                               colorscale="YlOrRd" if hazard is not None else "Earth",
                               colorbar=dict(title="H" if hazard is not None else "km", len=0.6), showscale=True,
                               hovertemplate="x %{x:.2f} km<br>y %{y:.2f} km<br>z %{z:.3f} km<extra></extra>"))
    for name, r in (routes or {}).items():
        if r is None or not r.found:
            continue
        rx = (np.asarray(r.lon) - grid.center[1]) * np.radians(1) * C.R_MARS_DTM * np.cos(np.radians(lat0)) / 1000
        ry = (np.asarray(r.lat) - lat0) * np.radians(1) * C.R_MARS_DTM / 1000
        fig.add_trace(go.Scatter3d(x=rx, y=ry, z=np.asarray(r.elev) / 1000 + 0.004, mode="lines", name=name,
                                   line=dict(width=6, color=ROUTE_COLORS.get(name, "#fff"))))
    zr = (np.nanmax(zz) - np.nanmin(zz)) / 1000
    xr = float(x.max() - x.min())
    fig.update_layout(title=title, height=560, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      scene=dict(xaxis_title="E (km)", yaxis_title="N (km)", zaxis_title="z (km)",
                                 aspectmode="manual",
                                 aspectratio=dict(x=1, y=float((y.max() - y.min()) / xr), z=max(0.05, exaggeration * zr / xr))),
                      legend=dict(orientation="h"))
    return fig


# ---------------------------------------------------------------- GeoJSON
def route_geojson(routes: dict, props: dict | None = None) -> dict:
    feats = []
    for name, r in routes.items():
        if r is None or not r.found:
            continue
        feats.append({"type": "Feature", "properties": {"strategy": name, **r.summary(), **(props or {})},
                      "geometry": {"type": "LineString",
                                   "coordinates": [[float(lo), float(la), float(z)] for la, lo, z in zip(r.lat, r.lon, r.elev)]}})
    return {"type": "FeatureCollection", "features": feats,
            "crs_note": "Mars planetocentric latitude, east-positive longitude (deg), elevation m (DEM datum)"}


def points_geojson(points: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {k: v for k, v in p.items() if k not in ("lat", "lon")},
         "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]}} for p in points]}


def parse_geojson_points(text: str) -> list[dict]:
    obj = json.loads(text)
    feats = obj.get("features", [obj]) if isinstance(obj, dict) else []
    out = []
    for f in feats:
        geom = f.get("geometry") or {}
        props = f.get("properties") or {}
        if geom.get("type") == "Point":
            lon, lat = geom["coordinates"][:2]
            out.append({"lat": float(lat), "lon": float(lon), "name": str(props.get("name", ""))[:80]})
        elif geom.get("type") == "LineString":
            for lon, lat, *_ in geom["coordinates"]:
                out.append({"lat": float(lat), "lon": float(lon), "name": str(props.get("name", ""))[:80]})
    return out


def deck_3d(grid, routes: dict | None = None, hazard_index=None, exaggeration: float = 3.0, max_points: int = 40000,
            traverse=None):
    """PyDeck (deck.gl) 3-D scene with true Mars distances: positions are local metres on the Mars mean sphere,
    re-expressed as the equivalent degrees on deck.gl's (Earth) globe around the scene centre, so horizontal and
    vertical scales stay consistent (no Earth-size distortion): DEM samples as a point cloud coloured by elevation (or hazard), routes and
    the Perseverance traverse as 3-D paths draped on the terrain. Returns a pydeck.Deck or None if pydeck is
    missing. Streamlit bundles deck.gl, so no CDN is needed; no Earth basemap is drawn."""
    try:
        import pydeck as pdk
    except ImportError:
        return None
    import matplotlib
    R = C.R_MARS_MEAN
    z = grid.z
    step = max(1, int(np.ceil(np.sqrt(z.size / max_points))))
    rows = np.arange(0, z.shape[0], step)
    cols = np.arange(0, z.shape[1], step)
    lat0, lon0 = grid.center if not callable(grid.center) else grid.center()
    la = np.array([grid.lat(r) for r in rows])
    lo = np.array([grid.lon(c) for c in cols])
    LO, LA = np.meshgrid(lo, la)
    Z = z[np.ix_(rows, cols)]
    ok = np.isfinite(Z)
    zmin = float(np.nanmin(Z))
    x = np.radians(LO - lon0) * R * np.cos(np.radians(lat0))
    y = np.radians(LA - lat0) * R
    if hazard_index is not None:
        v = np.nan_to_num(hazard_index[np.ix_(rows, cols)], nan=1.0)
        rgb = matplotlib.colormaps["RdYlGn_r"](np.clip(v, 0, 1))[..., :3]
    else:
        lo_, hi_ = np.nanpercentile(Z, [2, 98])
        rgb = matplotlib.colormaps["gist_earth"](np.clip((Z - lo_) / max(hi_ - lo_, 1e-6), 0, 1))[..., :3]
    RE = 6371008.8                                          # deck.gl's (Earth) sphere radius

    def to_deck(xm, ym):                                   # local Mars metres -> deck lon/lat with same metres
        return (lon0 + np.degrees(np.asarray(xm) / (RE * np.cos(np.radians(lat0)))),
                lat0 + np.degrees(np.asarray(ym) / RE))

    x, y = to_deck(x, y)
    pts = [{"p": [float(a), float(b), float((c - zmin) * exaggeration)], "c": [int(r * 255), int(g_ * 255), int(bb * 255)]}
           for a, b, c, (r, g_, bb) in zip(x[ok], y[ok], Z[ok], rgb[ok])]
    layers = [pdk.Layer("PointCloudLayer", pts, get_position="p", get_color="c", point_size=2)]

    def path(lat, lon):
        lat, lon = np.asarray(lat), np.asarray(lon)
        zz = np.array([grid.sample(grid.z, a, b) for a, b in zip(lat, lon)], float)
        zz = np.where(np.isfinite(zz), zz, zmin)
        px = np.radians(lon - lon0) * R * np.cos(np.radians(lat0))
        py = np.radians(lat - lat0) * R
        px, py = to_deck(px, py)
        return [[float(a), float(b), float((c - zmin) * exaggeration + 15)] for a, b, c in zip(px, py, zz)]

    paths = []
    for name, r in (routes or {}).items():
        if r is not None and r.found:
            col = ROUTE_COLORS.get(name, "#ffffff").lstrip("#")
            paths.append({"name": name, "path": path(r.lat, r.lon),
                          "color": [int(col[i:i + 2], 16) for i in (0, 2, 4)]})
    if traverse is not None and len(traverse) > 1:
        paths.append({"name": "Perseverance", "path": path(traverse["lat"].values, traverse["lon"].values),
                      "color": [0, 229, 255]})
    if paths:
        layers.append(pdk.Layer("PathLayer", paths, get_path="path", get_color="color", width_min_pixels=3,
                                pickable=True))
    view = pdk.ViewState(longitude=lon0, latitude=lat0, zoom=11.3, pitch=55, bearing=-20)
    return pdk.Deck(layers=layers, initial_view_state=view, map_provider=None, map_style=None,
                    tooltip={"text": "{name}"})
