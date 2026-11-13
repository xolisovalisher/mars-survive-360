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

import config as C  # noqa: E402
from frontend.components import state, ui  # noqa: E402
from mars_survive.common import get_logger  # noqa: E402
from mars_survive.localization.i18n import LANGUAGES  # noqa: E402
from mars_survive.settings import store as settings_store  # noqa: E402

log = get_logger("app")
st.set_page_config(page_title=C.APP_NAME, page_icon="🔴", layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------- query params (deep links / tests)
qp = st.query_params
if "lang" in qp and qp["lang"] in LANGUAGES and st.session_state.get("_qp_lang") != qp["lang"]:
    st.session_state.lang = qp["lang"]
    st.session_state._qp_lang = qp["lang"]
if "page" in qp and qp["page"] in ui.NUM and st.session_state.get("_qp_page") != qp["page"]:
    st.session_state.page = qp["page"]
    st.session_state._qp_page = qp["page"]

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
    extra += (".block-container{direction:rtl;text-align:right} .ms-top{flex-direction:row-reverse} [data-testid='stMetricValue'] div,[data-testid='stMetricDelta'] div,.ms-chip b,[data-testid='stDataFrame'] {direction:ltr;unicode-bidi:isolate;text-align:right}"
              " iframe,.js-plotly-plot,[data-testid='stDataFrame']{direction:ltr}"
              " [data-testid='stSidebar']{direction:rtl;text-align:right}")
if ctx.settings.theme == "light":
    extra += (":root{--ms-bg:#eef1f6;--ms-panel:#ffffff;--ms-panel2:#f6f8fb;--ms-line:#d5dbe6;--ms-text:#141a24;"
              "--ms-mute:#5b6b82} [data-testid='stAppViewContainer']{background:#eef1f6}"
              " [data-testid='stSidebar']{background:#f7f8fb} .ms-title{color:#141a24} .ms-modtitle{color:#141a24}"
              " .ms-card .v{color:#141a24}"
              " .ms-foot{background:rgba(255,255,255,.97)} .ms-foot b{color:#141a24}"
              " div[data-testid='stExpander']{background:#ffffff} div[data-testid='stExpander'] details{background:#ffffff}"
              " .ms-top{background:linear-gradient(90deg,rgba(228,87,46,.14),#ffffff 35%)} .ms-top .ms-sub{color:#5b6b82}"
              " .ms-chip{background:#f6f8fb}")
st.markdown(f"<style>{css}{extra}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------- top bar (language selector top-right)
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


g = ctx.g
dc_html = ui.badge(g.data_class, tr)
mod_ok = st.session_state.get("_mods_ok")
if mod_ok is None:
    from mars_survive.diagnostics.checks import modules_health
    mh = modules_health()
    mod_ok = (sum(m["ok"] for m in mh), len(mh))
    st.session_state._mods_ok = mod_ok
sys_cls = "ms-ok" if mod_ok[0] == mod_ok[1] else "ms-warn"
top_l, top_r = st.columns([5.2, 1.15], vertical_alignment="center")
with top_l:
    st.markdown(
        f"<div class='ms-top'><div class='ms-logo'></div><div style='min-width:0;flex:0 1 auto'><div class='ms-title'>MARS SURVIVE 360</div>"
        f"<div class='ms-sub' title='{html.escape(tr('app.subtitle'), quote=True)}'>{html.escape(tr('app.subtitle'))}</div></div><div style='flex:1'></div>"
        f"<span class='ms-chip'>🎯 {html.escape(tr('top.mission'))}: <b>{html.escape(ctx.mp.name)}</b></span>"
        f"<span class='ms-chip'>📍 {html.escape(tr('top.region'))}: <b>{html.escape(tr('region.jezero'))}</b></span>"
        f"<span class='ms-chip'>🗂 {html.escape(tr('top.data'))}: {dc_html}</span>"
        f"<span class='ms-chip'><span class='ms-dot {sys_cls}'></span>{html.escape(tr('top.system'))}: "
        f"<b>{mod_ok[0]}/{mod_ok[1]}</b></span></div>", unsafe_allow_html=True)
with top_r:
    codes = list(LANGUAGES)
    st.selectbox("🌐 " + tr("top.language"), codes, index=codes.index(ctx.lang), key="lang_select",
                 format_func=lambda c: f"{LANGUAGES[c][0]}", on_change=on_lang)

# ---------------------------------------------------------------- sidebar navigation
with st.sidebar:
    st.markdown(f"<div class='ms-title' style='font-size:15px'>🔴 MARS SURVIVE 360</div>"
                f"<div class='ms-sub'>v{C.VERSION} · {html.escape(tr('nav.title'))}</div>", unsafe_allow_html=True)
    for grp in ui.GROUPS:
        st.markdown(f"<div class='ms-navgroup'>{html.escape(tr('grp.' + grp))}</div>", unsafe_allow_html=True)
        for num, mid, icon, gg in sorted([m for m in ui.MODULES if m[3] == grp], key=lambda m: m[0]):
            active = st.session_state.page == mid
            if st.button(f"{icon} {num:02d} · {tr('mod.' + mid)}", key=f"nav_{mid}", width="stretch",
                         type="primary" if active else "tertiary"):
                st.session_state.page = mid
                st.query_params["page"] = mid
                st.session_state._qp_page = mid
                st.rerun()

# ---------------------------------------------------------------- page
page = st.session_state.page
page_err = None
try:
    mod = importlib.import_module(f"frontend.pages.{page}")
    mod.render(ctx)
except Exception as e:  # noqa: BLE001 - one module must never take down the platform
    page_err = f"{e.__class__.__name__}: {e}"
    log.error("page %s failed: %s\n%s", page, e, traceback.format_exc())
    st.error(f"{tr('err.page')} — {page_err}")
    with st.expander(tr("ui.details")):
        st.code(traceback.format_exc())

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
