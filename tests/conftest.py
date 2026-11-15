import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MS360_AUTO_REAL_DEM", "0")   # tests never touch the network for the DEM


@pytest.fixture(scope="session")
def grid():
    from mars_survive.dem import synthetic_grid
    return synthetic_grid()


@pytest.fixture(scope="session")
def engine(grid):
    from mars_survive.integration.engine import Engine
    return Engine(grid)


@pytest.fixture()
def tmp_db(tmp_path):
    return tmp_path / "test.sqlite3"


@pytest.fixture(scope="session")
def flat_grid():
    import math

    import numpy as np

    import config as C
    from mars_survive.common import DataClass
    from mars_survive.dem.grid import Grid
    n = 121
    d = math.degrees(50 / C.R_MARS_DTM)
    return Grid(z=np.zeros((n, n), np.float32), lat_top=0.1, lon_left=10.0, dlat=d, dlon=d, source="flat",
                data_class=DataClass.SYNTHETIC)
