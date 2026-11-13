"""13 MEDA Environmental Intelligence."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from mars_survive.common import ModuleError
from mars_survive.meda import environment as M

UNITS = {"air_temp_c": "°C", "ground_temp_c": "°C", "pressure_pa": "Pa", "wind_speed_ms": "m/s", "wind_dir_deg": "°",
         "dust_tau": "τ", "uv_index": "-"}


def render(ctx):
    tr = ctx.tr
    ui.header("meda", tr, ["Real", "Synthetic", "User Supplied"])
    t1, t2 = st.tabs(["🌡️ " + tr("meda.tab"), "☀️ " + tr("sw.tab")])
    with t1:
        _render_meda(ctx)
    with t2:
        from frontend.components import spaceweather_tab
        spaceweather_tab.render(ctx)


def _render_meda(ctx):
    tr, ss = ctx.tr, st.session_state
    head = st.container()
    with ui.params(tr):
        c1, c2, c3 = st.columns(3)
        src = c1.radio(tr("meda.source"), ["sample", "upload"], format_func=lambda s: tr("meda.src." + s))
        win = c2.slider(tr("meda.window"), 8, 96, 24)
        zt = c3.slider(tr("meda.z"), 2.0, 8.0, 4.0, 0.5)
        up = st.file_uploader(tr("meda.upload"), type=["csv"]) if src == "upload" else None
    dc = "Synthetic"
    df, mapping = None, {}
    if src == "sample":
        df = M.synthetic_sample(seed=int(ss.get("meda_seed", 0)))
        mapping = {c: c for c in df.columns}
    elif up is not None:
        try:
            df, mapping = M.read_csv(up.getvalue()[:100_000_000])
            dc = "User Supplied"
        except ModuleError as e:
            st.error(f"{tr(e.key)} — {e.detail}")
            return
    with head:
        st.markdown(ui.badge(dc, tr), unsafe_allow_html=True)
    if df is None:
        st.info(tr("meda.need_file"))
        st.code("TIME,ATS,GTS,PS,HORIZONTAL_WIND_SPEED,WIND_DIRECTION\n0,210.5,215.2,705.1,3.4,182\n...", language="text")
        return
    if dc == "Synthetic":
        st.warning(tr("meda.synthetic_notice"))
    st.caption(tr("meda.mapping") + ": " + ", ".join(f"{k}←{v}" for k, v in mapping.items()))
    vars_ = [c for c in UNITS if c in df]
    sel = st.multiselect(tr("meda.variables"), vars_, default=vars_[:3], format_func=lambda v: tr("meda.v." + v))
    an = M.anomalies(df, win, zt)
    risk = M.environment_risk(df)
    ss.meda_risk = risk
    c = st.columns(4)
    c[0].metric(tr("meda.samples"), len(df))
    c[1].metric(tr("meda.anomalies"), len(an))
    c[2].metric(tr("meda.env_level"), tr("lv." + risk["level"]))
    if "air_temp_c" in df:
        c[3].metric(tr("meda.v.air_temp_c"), f"{df['air_temp_c'].min():.0f} … {df['air_temp_c'].max():.0f} °C")
    for v in sel:
        fig = go.Figure(go.Scatter(x=df["time"], y=df[v], mode="lines", name=tr("meda.v." + v), line=dict(color="#2ec4b6")))
        if not an.empty:
            a = an[an["variable"] == v]
            fig.add_trace(go.Scatter(x=a["time"], y=a["value"], mode="markers", name=tr("meda.anomalies"),
                                     marker=dict(color="#ef476f", size=9, symbol="x")))
        if v in M.LIMITS:
            lo, hi = M.LIMITS[v]
            fig.add_hrect(y0=lo, y1=hi, fillcolor="#2ec4b6", opacity=0.06, line_width=0)
        fig.update_layout(height=230, title=f"{tr('meda.v.' + v)} ({UNITS[v]})", xaxis_title=tr("meda.time"))
        ui.plotly(fig, key=f"meda_{v}")
    c1, c2 = st.columns(2)
    with c1:
        ui.section(tr("meda.stats"))
        stt = M.statistics(df).round(2)
        stt.index = [tr("meda.v." + i) for i in stt.index]
        st.dataframe(stt, width="stretch")
    with c2:
        ui.section(tr("meda.risk_table"))
        ui.df_show(pd.DataFrame([{"variable": tr("meda.v." + k), "min": round(v["min"], 1), "max": round(v["max"], 1),
                                  "band": f"{v['band'][0]} … {v['band'][1]}", "outside_pct": round(100 * v["outside_frac"], 1),
                                  "level": tr("lv." + ["low", "medium", "high"][v["level"]])}
                                 for k, v in risk["variables"].items()]))
        if not an.empty:
            ui.df_show(an.round(2), height=180)
    ui.export_buttons(tr, "meda_analysis", df, {"risk": risk, "anomalies": an.to_dict("records")})
    ui.footer("meda", tr, "robust z = (x − rolling median) / (1.4826·MAD); anomaly if |z| > threshold\n"
                          "environment level from share of samples outside EVA planning bands (ASSUMPTION bands)",
              ["NASA PDS Atmospheres Node — Mars 2020 MEDA derived data (user-imported CSV)", "Rodriguez-Manfredi et al. 2021 (MEDA)"])
