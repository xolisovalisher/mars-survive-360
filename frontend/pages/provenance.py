"""22 Data Quality & Provenance."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from mars_survive.provenance.registry import CLASSES, all_datasets, register_builtin


def render(ctx):
    tr = ctx.tr
    ui.header("provenance", tr, ["Real", "Synthetic", "Simulated", "User Supplied"])
    if st.button(tr("btn.refresh_registry")):
        register_builtin(ctx.g)
    ds = all_datasets()
    if not ds:
        register_builtin(ctx.g)
        ds = all_datasets()
    df = pd.DataFrame(ds)
    sel = st.multiselect(tr("prov.filter"), CLASSES, default=CLASSES, format_func=lambda c: tr("dc." + _k(c)))
    show = df[df["data_class"].isin(sel)].copy()
    c = st.columns(4)
    for i, cl in enumerate(CLASSES):
        c[i].metric(tr("dc." + _k(cl)), int((df["data_class"] == cl).sum()))
    cnt = df["data_class"].value_counts()
    fig = go.Figure(go.Pie(labels=[tr("dc." + _k(x)) for x in cnt.index], values=cnt.values, hole=0.5,
                           marker=dict(colors=["#2ec4b6", "#e4572e", "#9b5de5", "#ffd166"])))
    fig.update_traces(textinfo="label+value", textposition="outside")
    fig.update_layout(height=300, title=tr("prov.by_class"), showlegend=False, margin=dict(t=50, b=30, l=30, r=30))
    c1, c2 = st.columns([1, 2])
    with c1:
        ui.plotly(fig, key="prov_pie")
    with c2:
        st.markdown(tr("prov.legend"))
    show["data_class"] = show["data_class"].map(lambda c_: tr("dc." + _k(c_)))
    show["history"] = show["history"].map(lambda h: " → ".join(h))
    cols = ["name", "data_class", "provider", "url", "acquisition_date", "processing_date", "resolution", "crs", "units",
            "quality", "history", "limitations"]
    ui.df_show(ui.tr_cols(show[cols], tr), height=360)
    ui.export_buttons(tr, "provenance", df.assign(history=df["history"].map(lambda h: " -> ".join(h))))
    ui.footer("provenance", tr, "every dataset is registered with class Real / Synthetic / Simulated / User Supplied,\n"
                                "provider, URL, dates, resolution, CRS, units, quality status, processing history, limitations",
              ["SQLite table datasets (data/mars_survive.sqlite3)"])


def _k(c):
    return {"Real": "real", "Synthetic": "synthetic", "Simulated": "simulated", "User Supplied": "user"}[c]
