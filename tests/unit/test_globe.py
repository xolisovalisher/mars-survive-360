"""3-D Mars globe: bundled NASA texture is present and georeferenced, sites are correct, Trek stitching works and
never caches a partial globe, deck layers are built."""
import base64
import io

import numpy as np
import pytest
from PIL import Image

from mars_survive.common import ModuleError
from mars_survive.mapping import globe as G


def _lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def test_bundled_texture_always_available():
    t = G.bundled_texture()
    assert t.image.size == (2048, 1024) and t.data_class == "Real"
    assert "USGS/NASA" in t.source


def test_texture_is_georeferenced():
    """Known albedo features of Mars must fall on the right longitudes/latitudes (−180…180 after the shift)."""
    t = G.bundled_texture()
    syrtis = _lum(G.sample_rgb(t, 8.4, 69.5, 6))          # Syrtis Major — classic dark albedo feature
    hellas = _lum(G.sample_rgb(t, -42.4, 70.5, 6))        # Hellas basin floor — bright
    tharsis = _lum(G.sample_rgb(t, 18.65, 226.2 - 360, 6))  # Olympus Mons / Tharsis — bright, dusty
    acidalia = _lum(G.sample_rgb(t, 46.7, -22.0, 6))      # Acidalia Planitia — dark
    assert hellas > 1.8 * syrtis and tharsis > 1.8 * syrtis and hellas > 1.4 * acidalia
    # the 180° roll is real: sampling Syrtis 180° away (= Tharsis side) must look different
    assert abs(_lum(G.sample_rgb(t, 8.4, 69.5 - 180, 6)) - syrtis) > 30


def test_sites_and_dem():
    keys = {s.key: s for s in G.SITES}
    assert set(keys) == {"jezero", "perseverance", "curiosity"}
    p = keys["perseverance"]
    assert (p.lat, p.lon) == (18.4447, 77.4508)
    assert abs(keys["curiosity"].lat + 4.5895) < 1e-9 and abs(keys["curiosity"].lon - 137.4417) < 1e-9
    assert keys["jezero"].has_dem and p.has_dem and not keys["curiosity"].has_dem


def test_sites_inside_active_dem(grid):
    for s in G.SITES:
        if s.has_dem:
            assert grid.inside(*grid.rowcol(s.lat, s.lon)), s.key


def test_data_url_roundtrip():
    u = G.data_url(G.bundled_texture())
    assert u.startswith("data:image/jpeg;base64,")
    im = Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1])))
    assert im.size == (2048, 1024)


def test_labels_overlay_is_transparent_png():
    u = G.labels_overlay(1024)
    im = Image.open(io.BytesIO(base64.b64decode(u.split(",", 1)[1])))
    a = np.asarray(im)
    assert im.mode == "RGBA" and (a[..., 3] == 0).mean() > 0.95 and a[..., 3].max() > 200


def test_trek_stitching_with_injected_tiles(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "TREK_CACHE", tmp_path / "trek.jpg")
    seen = []

    def fake(url):
        seen.append(url)
        z, y, x = url.rsplit("/", 3)[-3:]
        x = int(x.split(".")[0])
        im = Image.new("RGB", (256, 256), (40 + 10 * x, 60, 80 + 20 * int(y)))
        b = io.BytesIO()
        im.save(b, "JPEG")
        return b.getvalue()
    t = G.fetch_trek_texture(level=1, fetch=fake)
    assert len(seen) == 4 * 2 and t.image.size == (1024, 512)
    assert all("/Viking_MDIM21_ClrMosaic_global_232m/" in u and "/1/" in u for u in seen)
    assert G.best_texture().source.startswith("NASA Mars Trek")          # cached Trek texture preferred
    assert G.best_texture(prefer_trek=False).source.startswith("USGS/NASA")


def test_trek_failure_keeps_bundled(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "TREK_CACHE", tmp_path / "trek.jpg")

    def broken(url):
        raise ConnectionError("no route")
    with pytest.raises(ModuleError) as e:
        G.fetch_trek_texture(level=1, fetch=broken)
    assert e.value.key == "err.network"
    assert not (tmp_path / "trek.jpg").exists()                           # nothing partial cached
    assert G.best_texture().source.startswith("USGS/NASA")                 # globe still has NASA imagery


def test_deck_layers(grid):
    pytest.importorskip("pydeck")
    d = G.deck("data:image/jpeg;base64,AAAA", {"jezero": "Jezero"}, grid)
    types = [l.type for l in d.layers]
    assert types[0] == "BitmapLayer" and "ScatterplotLayer" in types and "PathLayer" in types
    assert d.views[0].type == "_GlobeView"
    z = G.deck("data:image/jpeg;base64,AAAA", {}, grid, G.SITES[0], dem_overlay_url="data:image/png;base64,AA")
    assert any(getattr(l, "id", "") == "dem_hillshade" for l in z.layers)
    assert z.initial_view_state.zoom > 8
