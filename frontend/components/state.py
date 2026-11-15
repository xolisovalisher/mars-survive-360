"""Shared mission state across all module pages (Streamlit session_state)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import streamlit as st

import config as C
from mars_survive.dem import get_active_grid
from mars_survive.dem.loader import PROCESSED_NPZ
from mars_survive.integration.engine import Engine
from mars_survive.integration.mission import MissionParams
from mars_survive.localization.i18n import Translator, is_rtl
from mars_survive.provenance import registry
from mars_survive.settings import store as settings_store


def _dem_key() -> str:
    return f"{PROCESSED_NPZ.stat().st_mtime}" if PROCESSED_NPZ.exists() else "synthetic"


@st.cache_resource(show_spinner=False)
def _engine(key: str) -> Engine:
    g = get_active_grid()
    try:
        registry.register_builtin(g)
    except Exception:  # noqa: BLE001 - provenance must never stop the app
        pass
    return Engine(g)


@st.cache_resource(show_spinner=False)
def _real_dem_once() -> dict:
    """First start only: fetch the real USGS Jezero DEM (see mars_survive.dem.bootstrap)."""
    from mars_survive.dem.bootstrap import ensure_real_dem
    return ensure_real_dem()


def real_dem_status() -> dict:
    from mars_survive.dem.bootstrap import status
    return status()


def engine() -> Engine:
    return _engine(_dem_key())


def reset_engine():
    _engine.clear()
    for k in ("routes", "profile", "stop_cuts", "start", "goal", "base", "stops"):
        st.session_state.pop(k, None)


@dataclass
class Ctx:
    tr: Translator
    lang: str
    rtl: bool
    settings: settings_store.Settings
    eng: Engine

    @property
    def g(self):
        return self.eng.g

    @property
    def mp(self) -> MissionParams:
        return st.session_state["mp"]

    @property
    def s(self):
        return st.session_state


def init() -> Ctx:
    ss = st.session_state
    if "settings" not in ss:
        ss.settings = settings_store.load()
    if "lang" not in ss:
        ss.lang = ss.settings.language
    if "page" not in ss:
        ss.page = "map"
    if "ws" not in ss:
        ss.ws = "planner"
    if "mp" not in ss:
        ss.mp = MissionParams(budget_h=ss.settings.default_budget_h, slope_limit_deg=ss.settings.default_slope_limit)
    if not PROCESSED_NPZ.exists() and not C.BROWSER and C.AUTO_REAL_DEM:
        with st.spinner(Translator(ss.lang)("ws.dem_loading")):
            ss._dem_boot = _real_dem_once()
    eng = engine()
    g = eng.g
    if "start" not in ss:
        st0 = C.LANDING_SITE
        r, c = g.rowcol(*st0)
        ss.start = st0 if g.valid(r, c) else g.center
        ss.base = ss.start
        # default destination: western delta front (approximate public location)
        gl = (18.455, 77.405)
        r, c = g.rowcol(*gl)
        ss.goal = gl if g.inside(r, c) else (g.lat(int(g.shape[0] * 0.3)), g.lon(int(g.shape[1] * 0.8)))
        ss.stops = []
    ss.setdefault("strategy", "balanced")
    tr = Translator(ss.lang)
    return Ctx(tr=tr, lang=tr.lang, rtl=is_rtl(tr.lang), settings=ss.settings, eng=eng)


def _ml_key():
    from mars_survive.ai import traversability as TV
    return TV.MODEL_PATH.stat().st_mtime if TV.MODEL_PATH.exists() else 0.0


def ensure_routes(ctx: Ctx, force: bool = False):
    """Four candidate routes start->goal (+ stops) for the current parameters; cached in session."""
    ss = st.session_state
    key = (ss.start, ss.goal, tuple(ss.stops), ctx.mp.slope_limit_deg, ctx.mp.w_slope, ctx.mp.w_hazard,
           ctx.mp.w_energy, ctx.mp.algorithm, ctx.mp.scenario, ctx.mp.dwell_min, ctx.mp.ml_blend, _ml_key())
    if not force and ss.get("routes_key") == key and "routes" in ss:
        return ss.routes
    from mars_survive.routing.planner import STRATEGIES
    pts = [ss.start] + list(ss.stops) + [ss.goal]
    routes, cuts = {}, {}
    for s in STRATEGIES:
        r, c = ctx.eng.plan_stops(pts, ctx.mp, s)
        routes[s], cuts[s] = r, c
    ss.routes, ss.stop_cuts, ss.routes_key = routes, cuts, key
    ss.pop("pipeline", None)
    return routes


def active(ctx: Ctx):
    """(route, profile, cuts) of the selected strategy; plans routes if needed."""
    routes = ensure_routes(ctx)
    ss = st.session_state
    s = ss.strategy if ss.strategy in routes else "balanced"
    r = routes.get(s)
    if r is None or not r.found:
        found = [k for k, v in routes.items() if v.found]
        if not found:
            return None, None, []
        s = found[0]
        r = routes[s]
    cuts = ss.stop_cuts.get(s) or [0, len(r.nodes) - 1]
    key = (ss.routes_key, s, ctx.mp.budget_h, ctx.mp.o2_capacity_l, str(ctx.mp.astronaut), str(ctx.mp.rover))
    if ss.get("profile_key") != key:
        ss.profile = ctx.eng.resources(r, ctx.mp, stop_idx=cuts[1:-1])
        ss.profile_key = key
    return r, ss.profile, cuts


def turnback(ctx: Ctx):
    from mars_survive.routing.eva import turnback as tb
    r, prof, _ = active(ctx)
    if r is None:
        return None
    _, t_ret = ctx.eng.eva_fields(st.session_state.base, ctx.mp)
    return tb(prof["t_s"], r.nodes, t_ret, ctx.mp.budget_h, ctx.mp.reserve_frac)


def grid_xy(ctx: Ctx, lat, lon):
    lat0, lon0 = ctx.g.center
    x = np.radians(np.asarray(lon) - lon0) * C.R_MARS_MEAN * np.cos(np.radians(lat0))
    y = np.radians(np.asarray(lat) - lat0) * C.R_MARS_MEAN
    return x, y
