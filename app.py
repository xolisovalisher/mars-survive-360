"""MARS SURVIVE 360 - Streamlit entry point.

Run:  streamlit run app.py      (Windows: scripts\\start_windows.bat)
"""
from __future__ import annotations

import html
import importlib
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if (ROOT / "_vendor").is_dir() and str(ROOT / "_vendor") not in sys.path:   # browser build: pure-Python packages
    sys.path.insert(1, str(ROOT / "_vendor"))

import config as C  # noqa: E402
from frontend.components import state, ui  # noqa: E402
from mars_survive.common import get_logger  # noqa: E402
from mars_survive.localization.i18n import LANGUAGES  # noqa: E402
from mars_survive.settings import store as settings_store  # noqa: E402

log = get_logger("app")
st.set_page_config(page_title="Mars Survive 360", page_icon=str(ROOT / "assets" / "mars" / "favicon.png"),
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- query params (deep links / tests)
qp = st.query_params
if "lang" in qp and qp["lang"] in LANGUAGES and st.session_state.get("_qp_lang") != qp["lang"]:
    st.session_state.lang = qp["lang"]
    st.session_state._qp_lang = qp["lang"]
if "page" in qp and qp["page"] in ui.NUM and st.session_state.get("_qp_page") != qp["page"]:
    st.session_state.page = qp["page"]                 # old links (?page=route) open the right workspace
    st.session_state.ws = ui.WS_OF.get(qp["page"], "planner")
    st.session_state._qp_page = qp["page"]
if "ws" in qp and qp["ws"] in {w[0] for w in ui.WORKSPACES} | {"system"} and st.session_state.get("_qp_ws") != qp["ws"]:
    st.session_state.ws = qp["ws"]
    st.session_state._qp_ws = qp["ws"]

t0 = time.perf_counter()
ctx = state.init()
tr = ctx.tr

# ---------------------------------------------------------------- theme (real Streamlit theme, not only CSS)
from streamlit import config as _stcfg
_THEMES = {
    "dark": dict(base="dark", backgroundColor="#0b0f17", secondaryBackgroundColor="#121826", textColor="#e6ebf5"),
    "light": dict(base="light", backgroundColor="#eef1f6", secondaryBackgroundColor="#ffffff", textColor="#141a24"),
}
_want = _THEMES.get(ctx.settings.theme, _THEMES["dark"])
st.session_state["_theme"] = ctx.settings.theme
if _stcfg.get_option("theme.base") != _want["base"]:
    for _k, _v in _want.items():
        _stcfg.set_option("theme." + _k, _v)
    st.rerun()

# ---------------------------------------------------------------- styles
css = (ROOT / "frontend" / "styles" / "theme.css").read_text(encoding="utf-8")
extra = ""
if ctx.rtl:
    extra += (".block-container{direction:rtl;text-align:right} [data-testid='stMetricValue'] div,"
              "[data-testid='stMetricDelta'] div,.ms-kpi .v,[data-testid='stDataFrame']{direction:ltr;unicode-bidi:isolate;text-align:right}"
              " iframe,.js-plotly-plot,[data-testid='stDataFrame']{direction:ltr} .ms-ph .r{margin-left:0;margin-right:auto}"
              " .st-key-ms_toolrail .stButton button,.st-key-ms_toolrail .stButton button p{text-align:right;justify-content:flex-start}")
if ctx.settings.theme == "light":
    extra += (":root{--ms-bg:#eef1f6;--ms-panel:#ffffff;--ms-panel2:#f5f7fa;--ms-line:#d8dee8;--ms-text:#141a24;--ms-mute:#5b6b82}"
              " .ms-title,.ms-ph,.ms-kpi .v,.ms-kv td:last-child,.ms-strat .t,.ms-rail-h,.ms-modtitle,.ms-card .v,"
              ".ms-datachip b,.ms-pop-h b,.ms-foot b{color:#141a24}"
              " .st-key-ms_header .stButton button:hover{color:#141a24} .ms-foot{background:rgba(255,255,255,.97)}")
st.markdown(f"<style>{css}{extra}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------- header: brand · workspaces · data · language · system
def on_lang():
    st.session_state.lang = st.session_state.lang_select
    s = st.session_state.settings
    s.language = st.session_state.lang
    try:
        settings_store.save(s)
    except OSError:
        pass
    st.query_params["lang"] = st.session_state.lang
    st.session_state._qp_lang = st.session_state.lang


def go(ws: str, page: str | None = None):
    st.session_state.ws = ws
    if page:
        st.session_state.page = page
        st.query_params["page"] = page
        st.session_state._qp_page = page
    st.query_params["ws"] = ws
    st.session_state._qp_ws = ws


g = ctx.g
ss = st.session_state
mod_ok = ss.get("_mods_ok")
if mod_ok is None:
    from mars_survive.diagnostics.checks import modules_health
    mh = modules_health(quick=C.BROWSER)
    mod_ok = (sum(m["ok"] for m in mh), len(mh))
    ss._mods_ok = mod_ok
sys_cls = "ms-ok" if mod_ok[0] == mod_ok[1] else "ms-warn"
ws_ids = [w[0] for w in ui.WORKSPACES]

with st.container(key="ms_header"):
    h_brand, h_nav, h_data, h_lang, h_sys = st.columns([2.35, 5.6, 1.45, 1.05, 0.42], vertical_alignment="center",
                                                        gap="small")
    with h_brand:
        st.markdown(
            f"<div class='ms-brand'><img src='data:image/png;base64,{ui.logo_b64()}' alt=''/>"
            f"<div><div class='ms-title'>MARS SURVIVE 360</div>"
            f"<div class='ms-sub'>{html.escape(tr('ws.tagline'))}</div></div></div>", unsafe_allow_html=True)
    with h_nav:
        cols = st.columns(len(ui.WORKSPACES), gap="small")
        for col, (wid, icon, _) in zip(cols, ui.WORKSPACES):
            if col.button(tr("ws." + wid), key=f"wsnav_{wid}", icon=icon, width="stretch",
                          type="primary" if ss.ws == wid else "tertiary"):
                go(wid)
                st.rerun()
    with h_data:
        real = g.is_real
        st.markdown(
            f"<div class='ms-datachip {'real' if real else 'syn'}' title='{html.escape(g.source, quote=True)}'>"
            f"<span class='ms-dot {'ms-ok' if real else 'ms-warn'}'></span>"
            f"<div><b>{html.escape(tr('ws.dem_real') if real else tr('ws.dem_synthetic'))}</b>"
            f"<span>{html.escape(tr('ws.dem_real_sub') if real else tr('ws.dem_synthetic_sub'))}</span></div></div>",
            unsafe_allow_html=True)
    with h_lang:
        codes = list(LANGUAGES)
        st.selectbox(tr("top.language"), codes, index=codes.index(ctx.lang), key="lang_select",
                     format_func=lambda c: f"{LANGUAGES[c][0]}", on_change=on_lang, label_visibility="collapsed")
    with h_sys:
        with st.popover("", icon=":material/settings:", help=tr("ws.system")):
            st.markdown(f"<div class='ms-pop-h'><span class='ms-dot {sys_cls}'></span> {html.escape(tr('top.system'))}: "
                        f"<b>{mod_ok[0]}/{mod_ok[1]}</b> · v{C.VERSION}</div>", unsafe_allow_html=True)
            for mid in ui.SYSTEM_TOOLS:
                if st.button(f"{ui.NUM[mid]:02d} · {tr('mod.' + mid)}", key=f"sys_{mid}", icon=ui.ICON[mid],
                             width="stretch", type="tertiary"):
                    go("system", mid)
                    st.rerun()
            if C.BROWSER:
                st.caption(tr("browser.badge") + " " + tr("browser.storage"))

# ---------------------------------------------------------------- workspace
page_err = None
ws = ss.ws if ss.ws in ws_ids + ["system"] else "planner"


def _run_page(name: str):
    global page_err
    try:
        mod = importlib.import_module(f"frontend.pages.{name}")
        mod.render(ctx)
    except Exception as e:  # noqa: BLE001 - one module must never take down the platform
        page_err = f"{e.__class__.__name__}: {e}"
        log.error("page %s failed: %s\n%s", name, e, traceback.format_exc())
        st.error(f"{tr('err.page')} — {page_err}")
        with st.expander(tr("ui.details")):
            st.code(traceback.format_exc())


if ws == "planner":
    _run_page("planner")
else:
    tools = ui.SYSTEM_TOOLS if ws == "system" else next(w[2] for w in ui.WORKSPACES if w[0] == ws)
    if ss.page not in tools:
        ss.page = tools[0]
    rail, main = st.columns([1.12, 4.9], gap="medium")
    with rail:
        with st.container(key="ms_toolrail"):
            st.markdown(f"<div class='ms-rail-h'>{html.escape(tr('ws.' + ws))}</div>"
                        f"<div class='ms-rail-d'>{html.escape(tr('ws.' + ws + '_desc'))}</div>", unsafe_allow_html=True)
            for mid in tools:
                if st.button(tr("mod." + mid), key=f"tool_{mid}", icon=ui.ICON[mid], width="stretch",
                             type="primary" if ss.page == mid else "tertiary"):
                    go(ws, mid)
                    st.rerun()
            if ws != "planner":
                st.markdown("<div class='ms-rail-sep'></div>", unsafe_allow_html=True)
                if st.button(tr("ws.back_to_map"), key="tool_back", icon=":material/arrow_back:", width="stretch",
                             type="secondary"):
                    go("planner")
                    st.rerun()
    with main:
        _run_page(ss.page)

# ---------------------------------------------------------------- footer status bar
warn_n = len(st.session_state.get("_warnings", []))
elapsed = (time.perf_counter() - t0) * 1000
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
st.markdown(
    f"<div class='ms-foot'><span><span class='ms-dot {sys_cls}'></span> <b>{html.escape(tr('foot.system'))}</b>: "
    f"{html.escape(tr('foot.online'))}</span>"
    f"<span><b>{html.escape(tr('foot.source'))}</b>: {html.escape(tr('src.synthetic') if getattr(g.data_class, 'value', g.data_class) == 'Synthetic' else g.source[:70])}</span>"
    f"<span><b>{html.escape(tr('foot.updated'))}</b>: {now}</span>"
    f"<span><b>{html.escape(tr('foot.compute'))}</b>: {'⚠ ' + html.escape(tr('foot.error')) if page_err else '✓'} "
    f"{elapsed:.0f} ms</span>"
    f"<span><b>{html.escape(tr('foot.warnings'))}</b>: {warn_n + (0 if g.is_real else 1)}"
    f"{(' · ' + html.escape(tr('foot.synthetic_warning'))) if not g.is_real else ''}</span></div>",
    unsafe_allow_html=True)
