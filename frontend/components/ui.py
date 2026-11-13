"""Shared UI building blocks. Every module page uses these so all 27 pages have the
same structure: header -> description -> inputs/parameters -> run -> results ->
chart/map -> export -> source / method / limitations."""
from __future__ import annotations

import html
import io
import json
from contextlib import contextmanager

import pandas as pd
import streamlit as st

from mars_survive.common import DataClass, safe_call

MODULES = [
    # (number, id, icon, group)
    (1, "dashboard", "🛰️", "mission"), (2, "map", "🗺️", "geo"), (3, "terrain", "⛰️", "geo"),
    (4, "dem", "🗂️", "geo"), (5, "route", "🧭", "geo"), (6, "hazards", "⚠️", "geo"),
    (7, "ai", "🤖", "intel"), (8, "autonav", "🚙", "intel"), (9, "navintel", "🎯", "intel"),
    (10, "comm", "📡", "space"), (11, "relay", "🛰", "space"), (12, "spice", "☀️", "space"),
    (13, "meda", "🌡️", "crew"), (14, "suit", "🧑‍🚀", "crew"), (15, "oxygen", "🫁", "crew"),
    (16, "energy", "🔋", "crew"), (17, "timeline", "🕒", "mission"), (18, "science", "🔬", "crew"),
    (19, "simulation", "🎛️", "mission"), (20, "risk", "🧯", "mission"), (21, "ingest", "📥", "data"),
    (22, "provenance", "🧾", "data"), (23, "reports", "📄", "mission"), (24, "i18n", "🌐", "data"),
    (25, "settings", "⚙️", "data"), (26, "diagnostics", "🩺", "data"), (27, "integration", "🧠", "mission"),
]
GROUPS = ["mission", "geo", "intel", "space", "crew", "data"]
NUM = {m[1]: m[0] for m in MODULES}

PLOTLY_LAYOUT = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(18,24,38,.6)",
                     margin=dict(l=10, r=10, t=40, b=10), font=dict(size=12),
                     legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))


def badge(dc: DataClass | str, tr) -> str:
    v = dc.value if isinstance(dc, DataClass) else str(dc)
    cls = {"Real": "real", "Synthetic": "synthetic", "Simulated": "simulated", "User Supplied": "user"}.get(v, "simulated")
    return f"<span class='ms-badge ms-b-{cls}'>{html.escape(tr('dc.' + cls))}</span>"


def header(mid: str, tr, data_classes: list | None = None):
    n = NUM[mid]
    badges = "".join(badge(d, tr) for d in (data_classes or []))
    st.markdown(f"<div class='ms-modhead'><span class='ms-modnum'>{n:02d}</span>"
                f"<span class='ms-modtitle'>{html.escape(tr('mod.' + mid))}</span></div>"
                f"<div class='ms-desc'>{badges}{html.escape(tr('desc.' + mid))}</div>", unsafe_allow_html=True)


def footer(mid: str, tr, method: str, sources: list[str]):
    with st.expander("ℹ️ " + tr("ui.method_sources_limits"), expanded=False):
        c1, c2 = st.columns(2)
        c1.markdown(f"**{tr('ui.method')}**")
        c1.code(method, language=None)
        c2.markdown(f"**{tr('ui.sources')}**")
        for s in sources:
            c2.markdown(f"- {s}")
        st.markdown(f"**{tr('ui.limitations')}**")
        st.warning(tr("lim." + mid))


def card(col, k: str, v: str, s: str = ""):
    col.markdown(f"<div class='ms-card'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div>"
                 f"<div class='s'>{html.escape(s)}</div></div>", unsafe_allow_html=True)


def show_error(err: str, tr):
    if not err:
        return
    if "|" in err and err.split("|")[0].startswith("err."):
        key, det = err.split("|", 1)
        st.error(f"{tr(key)} {('— ' + det) if det else ''}")
    else:
        st.error(f"{tr('err.generic')}: {err}")


def run_safely(tr, fn, *a, **kw):
    """Spinner + safe execution; returns result or None (error displayed)."""
    with st.spinner(tr("ui.computing")):
        res, err = safe_call(fn, *a, **kw)
    show_error(err, tr)
    return res


def export_buttons(tr, name: str, df: pd.DataFrame | None = None, obj: dict | None = None, key: str = ""):
    cols = st.columns(4)
    if df is not None and not df.empty:
        cols[0].download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{name}.csv", "text/csv",
                                key=f"csv_{name}_{key}")
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        cols[1].download_button("⬇️ Excel", buf.getvalue(), f"{name}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"x_{name}_{key}")
    if obj is not None:
        cols[2].download_button("⬇️ JSON", json.dumps(obj, ensure_ascii=False, indent=2, default=_jd).encode(),
                                f"{name}.json", "application/json", key=f"j_{name}_{key}")


def _jd(o):
    if hasattr(o, "tolist"):
        return o.tolist()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


@contextmanager
def params(tr, expanded=True):
    with st.expander("🎛️ " + tr("ui.parameters"), expanded=expanded):
        yield


def section(title: str):
    st.markdown(f"#### {title}")


def plotly(fig, key=None):
    fig.update_layout(**{k: v for k, v in PLOTLY_LAYOUT.items() if k not in fig.layout.to_plotly_json() or k == "template"})
    if st.session_state.get("_theme") == "light":
        fig.update_layout(template="plotly_white", plot_bgcolor="rgba(246,248,251,1)", font_color="#141a24")
    lay = fig.layout
    n_named = sum(1 for tr_ in fig.data if getattr(tr_, "showlegend", None) is not False and getattr(tr_, "name", None)
                  and tr_.type != "pie")
    if lay.title.text and n_named > 1 and lay.showlegend is not False:
        # keep the legend in its own band between the title and the plot area (no overlap with the title)
        mt = (lay.margin.t or 0)
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                          margin=dict(t=max(mt, 84)), title=dict(y=0.98, yanchor="top"))
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def df_show(df: pd.DataFrame, height=None):
    if df is None or len(df) == 0:
        return
    data = df
    na_cols = [c for c in df.columns if df[c].isna().any()]
    if na_cols:
        # columns with gaps are shown as text: missing -> "—" (never "None"/"nan")
        def _fmt(v):
            if v is None or (isinstance(v, float) and v != v):
                return "—"
            if isinstance(v, float):
                return f"{v:.3f}".rstrip("0").rstrip(".")
            return str(v)
        data = df.copy()
        for c in na_cols:
            data[c] = data[c].map(_fmt)
    if height:
        st.dataframe(data, width="stretch", hide_index=True, height=height)
    else:
        st.dataframe(data, width="stretch", hide_index=True)


def tr_cols(df: pd.DataFrame, tr, prefix="col.") -> pd.DataFrame:
    """Translate column headers via keys 'col.<name>' (fallback: original name)."""
    return df.rename(columns={c: (tr(prefix + c) if tr(prefix + c) != prefix + c else c) for c in df.columns})


def tr_vals(series: pd.Series, tr, prefix: str) -> pd.Series:
    return series.map(lambda v: tr(prefix + str(v)) if tr(prefix + str(v)) != prefix + str(v) else v)
