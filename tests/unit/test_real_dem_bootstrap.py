"""The first-start bootstrap must load REAL USGS pixels or clearly fail — never label demo terrain as real."""
import math

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")


def _fake_usgs_tif(path):
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    crs = CRS.from_proj4("+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=77.5 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs")
    R = 3396190
    x0, y0 = math.radians(77.1 - 77.5) * R, math.radians(18.8) * R
    yy, xx = np.mgrid[0:1200, 0:1200]
    z = (-2500 + 300 * np.sin(xx / 100) + 200 * np.cos(yy / 75)).astype("float32")
    with rasterio.open(path, "w", driver="GTiff", width=1200, height=1200, count=1, dtype="float32", crs=crs,
                       transform=from_origin(x0, y0, 40, 40), nodata=-3.4e38) as d:
        d.write(z, 1)


@pytest.fixture()
def boot(tmp_path, monkeypatch):
    import config as C
    from mars_survive.dem import bootstrap as B
    from mars_survive.dem import loader as L
    npz = tmp_path / "jezero_dem.npz"
    monkeypatch.setattr(L, "PROCESSED_NPZ", npz)
    monkeypatch.setattr(B, "PROCESSED_NPZ", npz)
    monkeypatch.setattr(B, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(C, "AUTO_REAL_DEM", True)
    monkeypatch.setattr(C, "DATA_RAW", tmp_path / "raw")
    return B, L, npz


def test_unreachable_sources_fail_honestly(boot):
    B, L, npz = boot
    d = B.ensure_real_dem(force=True, sources=("http://127.0.0.1:9/none/M20_JezeroCrater_CTXDEM_20m.tif",))
    assert d["state"] == "failed" and d["errors"] and not npz.exists()
    # a recent failure is not retried on every page load
    assert B.ensure_real_dem(sources=("http://127.0.0.1:9/x.tif",))["state"] == "skipped"


def test_real_pixels_are_processed_and_labelled(boot, tmp_path, monkeypatch):
    B, L, npz = boot
    tif = tmp_path / "M20_JezeroCrater_CTXDEM_20m.tif"
    _fake_usgs_tif(tif)
    monkeypatch.setattr(B, "_from_remote", lambda url: L.build_grid_from_dem(tif, save=False))
    d = B.ensure_real_dem(force=True, sources=("https://example.invalid/M20_JezeroCrater_CTXDEM_20m.tif",))
    assert d["state"] == "fetched" and npz.exists()
    g = L.load_processed(npz)
    assert g.is_real and "USGS" in g.source and np.isfinite(g.z).mean() > 0.9
