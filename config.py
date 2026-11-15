"""Central configuration: paths, physical constants (with sources), data URLs.

Every number that is a modelling ASSUMPTION (not a measurement) is marked
`# ASSUMPTION` so reviewers can see what is simplified.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "MARS SURVIVE 360"
APP_FULL_NAME = "Interplanetary Survival Guide — Martian Mission Planning & Intelligence Platform"
VERSION = "1.3.0"

# Browser build (Pyodide/stlite, one .html file): no subprocesses, no outside network from a shared
# page, no Leaflet tiles. Set MS360_BROWSER=1 to try the browser behaviour in a normal Python.
import sys as _sys
BROWSER = _sys.platform == "emscripten" or os.environ.get("MS360_BROWSER") == "1"


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE pairs from .env (never overrides real environment variables, never logs values)."""
    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------- paths
DATA = ROOT / "data"
DATA_RAW = DATA / "raw"
DATA_PROCESSED = DATA / "processed"
DATA_SYNTHETIC = DATA / "synthetic"
DATA_SAMPLES = DATA / "samples"
DATA_METADATA = DATA / "metadata"
DATA_UPLOADS = DATA / "uploads"
MODELS_DIR = ROOT / "models"
SPICE_DIR = ROOT / "spice_kernels"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"
DB_PATH = DATA / "mars_survive.sqlite3"
SETTINGS_PATH = DATA / "settings.json"
for _p in (DATA_RAW, DATA_PROCESSED, DATA_SYNTHETIC, DATA_SAMPLES, DATA_METADATA, DATA_UPLOADS,
           MODELS_DIR / "yolo", REPORTS_DIR, LOGS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- Mars constants
# IAU WGCCRE 2015 (Archinal et al., Celest. Mech. Dyn. Astr. 130:22, 2018)
R_MARS_EQ = 3_396_190.0          # m, equatorial radius
R_MARS_POLAR = 3_376_200.0       # m, polar radius
R_MARS_MEAN = 3_389_500.0        # m, volumetric mean radius (NASA Mars Fact Sheet)
R_MARS_DTM = 3_396_190.0         # m, sphere used by the USGS Mars 2020 DEM products
FLATTENING = (R_MARS_EQ - R_MARS_POLAR) / R_MARS_EQ   # ~0.00589
G_MARS = 3.721                   # m/s^2, equatorial surface gravity (NASA Mars Fact Sheet)
G_EARTH = 9.80665                # m/s^2, standard gravity (only for unit conversion)
GM_MARS = 4.282837e13            # m^3/s^2 (NASA Mars Fact Sheet)
SOL_S = 88_775.244               # s, mean solar day (Allison & McEwen 2000)
SIDEREAL_DAY_S = 88_642.663      # s, Mars rotation period (IAU 2015)
SCALE_HEIGHT_M = 11_100.0        # m, atmospheric scale height (NASA Mars Fact Sheet)
C_LIGHT = 299_792_458.0          # m/s
K_BOLTZMANN = 1.380649e-23       # J/K
O2_KJ_PER_L = 20.1               # kJ per litre O2 (respiratory energy equivalent, RQ ~0.82)
O2_DENSITY_STP = 1.429           # g/L at 0 degC, 1 atm
R_GAS = 8.314462618              # J/(mol K)
M_O2 = 0.0319988                 # kg/mol

# Radiation: Curiosity RAD, Gale crater surface, Aug 2012 - Jun 2013
# (Hassler et al., Science 343, 2014): 0.64 +/- 0.12 mSv/day dose equivalent.
RAD_GALE_MSV_PER_DAY = 0.64
RAD_GALE_ELEV_M = -4_500.0
RAD_ELEV_EXPONENT = 0.2          # ASSUMPTION: dose ~ (P_gale/P)^0.2
CAREER_LIMIT_MSV = 600.0         # NASA-STD-3001 Vol.1 career effective-dose limit

# ---------------------------------------------------------------- region
REGION_NAME = "Jezero Crater"
LANDING_SITE = (18.4447, 77.4508)   # Octavia E. Butler Landing (NASA/JPL), planetocentric, east-positive
JEZERO_CENTER = (18.44, 77.45)
ANALYSIS_RES_M = 50.0
CROP_HALF_DEG = 0.18

# ---------------------------------------------------------------- data sources
CTX_DTM_URL = ("https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/"
               "ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif")
CTX_DTM_XML_URL = CTX_DTM_URL[:-4] + ".xml"
# same USGS file on the USGS Astrogeology AWS bucket (used if planetarymaps.usgs.gov is slow or down)
CTX_DTM_MIRROR_URL = ("https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/"
                      "ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif")
# first start: fetch the real USGS DEM automatically (set MS360_AUTO_REAL_DEM=0 to stay offline)
AUTO_REAL_DEM = os.environ.get("MS360_AUTO_REAL_DEM", "1") != "0"
CTX_DTM_CATALOG = "https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic"
THEMIS_DAY_URL = "https://planetarymaps.usgs.gov/mosaic/Mars_MO_THEMIS-IR-Day_mosaic_global_100m_v12.tif"
M20_TRAVERSE = "https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json"
DONKI_BASE = "https://api.nasa.gov/DONKI"
TREK = "https://trek.nasa.gov/tiles/Mars/EQ/{layer}/1.0.0/default/default028mm/{{z}}/{{y}}/{{x}}.{ext}"
TREK_LAYERS = {
    "Viking MDIM 2.1 colour (Mars Trek)": ("Viking_MDIM21_ClrMosaic_global_232m", "jpg", 7,
                                          "NASA/JPL/USGS Viking MDIM 2.1 via NASA Mars Trek"),
    "MOLA shaded relief (Mars Trek)": ("Mars_MGS_MOLA_ClrShade_merge_global_463m", "jpg", 6,
                                      "NASA/GSFC MGS MOLA via NASA Mars Trek"),
}

# ---------------------------------------------------------------- security / limits
MAX_UPLOAD_MB = 200
ALLOWED_UPLOAD_EXT = {".tif", ".tiff", ".xml", ".lbl", ".csv", ".json", ".geojson",
                      ".png", ".jpg", ".jpeg"}
NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")
