"""Module 13 tab: NASA DONKI space weather → EVA radiation flag (feeds module 20 risk)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from mars_survive.common import ModuleError
from mars_survive.nasa_live import donki as D
from mars_survive.nasa_live import http

COLORS = {"FLR": "#ffb703", "SEP": "#e63946", "CME": "#8ecae6", "GST": "#a8dadc"}


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    st.info(tr("sw.intro"))
    with ui.params(tr):
        c1, c2, c3, c4 = st.columns(4)
        src = c1.radio(tr("sw.source"), ["live", "upload", "example"], format_func=lambda s: tr("sw.src." + s))
        today = date.today()
        ex = src == "example"
        d_end = date(2026, 11, 10) if ex else today
        start = c2.date_input(tr("sw.start"), d_end - timedelta(days=30), max_value=today, key=f"sw_s_{src}")
        end = c3.date_input(tr("sw.end"), d_end, max_value=today, key=f"sw_e_{src}")
        lookback = c4.slider(tr("sw.lookback"), 1, 14, 3)
        c5, c6 = st.columns(2)
        eva_d = c5.date_input(tr("sw.eva_date"), d_end, key=f"sw_d_{src}")
        eva_t = c6.time_input(tr("sw.eva_time"), time(8, 0) if ex else time(12, 0), key=f"sw_t_{src}")
        kinds = st.multiselect(tr("sw.kinds"), D.TYPES, default=D.TYPES, format_func=lambda k: tr("sw.k." + k))
        if src == "live":
            st.caption(tr("sw.key_hint", k="DEMO_KEY" if D.api_key() == "DEMO_KEY" else "NASA_API_KEY ✓"))
    payloads, dc, meta = {}, None, ""
    if src == "live":
        if st.button("🛰️ " + tr("sw.fetch"), type="primary"):
            got, errs = {}, []
            with st.spinner(tr("ui.computing")):
                for k in kinds:
                    try:
                        got[k] = D.fetch(k, start, end)
                    except ModuleError as e:
                        errs.append(f"{k}: {tr(e.key)} — {e.detail}")
            if errs:
                st.error(tr("sw.fetch_failed") + "\n\n" + "\n".join(f"- {e}" for e in errs))
            if got:
                ss.sw_live = got
        if ss.get("sw_live"):
            payloads = {k: v["payload"] for k, v in ss.sw_live.items() if k in kinds}
            dc = "Real"
            meta = ", ".join(f"{k}: {v['fetched_utc']}" for k, v in ss.sw_live.items())
    elif src == "upload":
        up = st.file_uploader(tr("sw.upload"), type=["json"])
        st.caption(tr("sw.upload_hint"))
        if up is not None:
            try:
                obj = http.parse_json_bytes(up.getvalue())
                if isinstance(obj, list):                      # a single DONKI endpoint response
                    k = st.selectbox(tr("sw.kind_of_file"), D.TYPES, format_func=lambda k: tr("sw.k." + k))
                    payloads = {k: obj}
                elif isinstance(obj, dict):
                    payloads = {k: obj.get(k) or [] for k in D.TYPES if k in kinds}
                dc = "User Supplied"
            except ModuleError as e:
                st.error(f"{tr(e.key)} — {e.detail}")
    else:
        ex = D.example_payloads()
        payloads = {k: ex.get(k, []) for k in kinds}
        dc = "Synthetic"
        st.warning(tr("sw.example_note"))
    if dc is None:
        st.info(tr("sw.need_data"))
        ss.pop("sw_assessment", None)
        return
    df = pd.concat([D.normalize(k, p) for k, p in payloads.items()], ignore_index=True) if payloads else \
        D.normalize("FLR", [])
    eva = datetime.combine(eva_d, eva_t)
    a = D.assess(df, eva, lookback)
    ss.sw_assessment = a
    st.markdown(ui.badge(dc, tr) + (f" <small>{tr('sw.fetched_at')}: {meta}</small>" if meta else ""),
                unsafe_allow_html=True)
    k = st.columns(5)
    lv = tr("lv." + a.level)
    k[0].metric(tr("sw.level"), lv[:1].upper() + lv[1:])
    for i, t in enumerate(D.TYPES, 1):
        k[i].metric(tr("sw.k." + t), a.counts.get(t, 0), help=tr("sw.in_window", d=lookback))
    icon = {"high": "🔴", "medium": "🟠", "low": "🟢"}[a.level]
    for key, kw in a.reasons:
        (st.success if a.level == "low" else st.warning)(f"{icon} " + tr(key, **kw))
    st.caption(tr("sw.limit"))
    if len(df):
        fig = go.Figure()
        for t in D.TYPES:
            d = df[df["kind"] == t]
            if len(d):
                fig.add_scatter(x=d["time"], y=[tr("sw.k." + t)] * len(d), mode="markers", name=tr("sw.k." + t),
                                marker=dict(size=[16 if r else 10 for r in d["mars_relevant"]], color=COLORS[t],
                                            symbol=["star" if r else "circle" for r in d["mars_relevant"]]),
                                text=[f"{m} {x}" for m, x in zip(d["magnitude"], d["detail"])], hoverinfo="text+x")
        arr = df[df["mars_arrival"].notna()]
        if len(arr):
            fig.add_scatter(x=arr["mars_arrival"], y=[tr("sw.mars_arrival")] * len(arr), mode="markers",
                            name=tr("sw.mars_arrival"), marker=dict(size=16, color="#e4572e", symbol="diamond"))
        fig.add_vline(x=eva, line_dash="dash", line_color="#2ec4b6")
        fig.add_vrect(x0=a.window[0], x1=eva, fillcolor="#2ec4b6", opacity=0.08, line_width=0)
        fig.update_layout(height=320, title=tr("sw.timeline"))
        ui.plotly(fig, key="sw_tl")
        show = df.copy()
        show["kind"] = show["kind"].map(lambda t: tr("sw.k." + t))
        show["mars_relevant"] = show["mars_relevant"].map(lambda v: "✓" if v else "")
        show["time"] = show["time"].astype(str)
        show["mars_arrival"] = show["mars_arrival"].astype(str).replace("NaT", "")
        ui.df_show(ui.tr_cols(show, tr))
        ui.export_buttons(tr, "donki_events", df.astype(str), key="sw")
    else:
        st.success(tr("sw.no_events"))
