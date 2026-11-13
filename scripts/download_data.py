"""Download and prepare the real Jezero DEM (USGS Astrogeology, Mars 2020 CTX DEM mosaic, 20 m/px, ~87 MB).

    python scripts/download_data.py              # DEM (+ XML label), then build data/processed/*.npz
    python scripts/download_data.py --local PATH # use an already downloaded GeoTIFF

Resumable, checks HTTP status and file size; on any failure it says so and the app keeps the SYNTHETIC DEM.
No data values are altered — only the analysis window is reprojected/resampled (documented in DATA_SOURCES).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config as C  # noqa: E402
from mars_survive.dem import loader  # noqa: E402
from mars_survive.provenance import registry  # noqa: E402


def main(argv):
    if "--local" in argv:
        tif = Path(argv[argv.index("--local") + 1]).expanduser().resolve()
        if not tif.is_file():
            print(f"[FAIL] file not found: {tif}")
            return 1
    else:
        tif = C.DATA_RAW / C.CTX_DTM_URL.rsplit("/", 1)[-1]
        print(f"Downloading {C.CTX_DTM_URL}\n -> {tif}")

        def prog(done, total):
            if total:
                print(f"\r   {done / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        try:
            info = loader.download(C.CTX_DTM_URL, tif, progress=prog)
            print(f"\n[OK]   {info['bytes'] / 1e6:.1f} MB")
        except Exception as e:  # noqa: BLE001 — report honestly and stop
            print(f"\n[FAIL] download: {e.__class__.__name__}: {e}\n"
                  "       Download the file in a browser from the URL above, then run:\n"
                  f"       python scripts/download_data.py --local <path-to-tif>")
            return 1
        try:
            loader.download(C.CTX_DTM_XML_URL, tif.with_suffix(".xml"))
            print("[OK]   XML label")
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] XML label not downloaded ({e.__class__.__name__}); not required")
    print("Building analysis grid (Jezero window, 50 m)…")
    try:
        g, meta = loader.build_grid_from_dem(tif)
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] processing: {e.__class__.__name__}: {e}")
        return 1
    registry.register_builtin(g)
    q = loader.quality_report(g.z)
    print(f"[OK]   grid {g.shape}, class={g.data_class.value}, valid={q['valid_fraction'] * 100:.1f} %")
    print("Restart the app (or use 'Use this DEM' in module 04) — the SYNTHETIC badge will change to REAL.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
