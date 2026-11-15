"""Module 07 tab: supervised traversability model — train, evaluate, inspect, use in routing."""
from __future__ import annotations

import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import maps, state, ui
from mars_survive.ai import traversability as TV
from mars_survive.mapping import views as V


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    st.info(tr("ml.intro"))
    with ui.params(tr):
        c1, c2, c3, c4 = st.columns(4)
        smax = c1.slider(tr("ml.slope_max"), 5.0, 30.0, 15.0, 0.5)
        rmax = c2.slider(tr("ml.rough_max"), 0.5, 6.0, 2.0, 0.1)
        blocks = c3.slider(tr("ml.blocks"), 4, 8, 5)
        epochs = c4.slider(tr("ml.epochs"), 5, 60, 25, 5, disabled=not TV.torch_available())
        st.caption(tr("ml.engine", nn=("PyTorch " + _torch_ver()) if TV.torch_available() else "scikit-learn MLP"))
    if st.button(tr("ml.train"), type="primary"):
        bar = st.progress(0.0, text=tr("ml.training"))
        nb = max(1, blocks * blocks // 5)
        cfg = TV.TrainConfig(blocks=blocks, n_val_blocks=nb, n_test_blocks=nb, mlp_epochs=epochs)
        res = ui.run_safely(tr, TV.train, ctx.g, ctx.eng.T, TV.LabelRule(smax, rmax), cfg,
                            lambda f, n: bar.progress(min(1.0, f), text=f"{tr('ml.training')} {n}"))
        bar.empty()
        if res:
            st.success(tr("ml.trained", m=res[1]["selected"], f=f"{res[1]['test']['f1']:.3f}"))
            st.cache_data.clear()
    card = TV.card()
    if not card:
        st.warning(tr("ml.none"))
        return
    st.markdown(ui.badge(card.get("dem_data_class", "Synthetic"), tr) + " " + ui.badge("Simulated", tr)
                + f" &nbsp; <small>{html.escape(tr('ml.labels_from'))}: <code>{html.escape(card['label_rule'])}</code></small>",
                unsafe_allow_html=True)
    if str(card.get("dem_data_class", "")).lower().startswith("synth"):
        st.warning(tr("ml.disclaimer"))
    te = card["test"]
    k = st.columns(6)
    short = {"logistic": "LogReg", "gboost": "GBoost", "mlp": "MLP"}.get(card.get("selected_key"), card["selected"][:10])
    k[0].metric(tr("ml.selected"), short, help=card["selected"])
    k[1].metric("F1 (test)", f"{te['f1']:.3f}")
    k[2].metric(tr("col.precision"), f"{te['precision']:.3f}")
    k[3].metric(tr("col.recall"), f"{te['recall']:.3f}")
    k[4].metric("ROC-AUC", f"{te['roc_auc']:.3f}")
    k[5].metric("PR-AUC", f"{te['pr_auc']:.3f}", help=tr("ml.prevalence", p=f"{card['baseline']['prevalence_test']:.3f}"))
    rows = [{"model": r["name"], "fit_s": r["fit_s"], "val_f1": r["val"]["f1"], "test_f1": r["test"]["f1"],
             "precision": r["test"]["precision"], "recall": r["test"]["recall"], "roc_auc": r["test"]["roc_auc"],
             "pr_auc": r["test"]["pr_auc"], "brier": r["test"]["brier"], "threshold": r["val"]["threshold"]}
            for r in card["results"]]
    cmp_df = pd.DataFrame(rows)
    ui.section(tr("ml.compare"))
    ui.df_show(ui.tr_cols(cmp_df.round(3), tr))
    st.caption(tr("ml.split", s=card["split"], tr_=card["rows"]["train"], va=card["rows"]["val"], te=card["rows"]["test"]))
    c1, c2 = st.columns(2)
    with c1:
        cm = te["confusion"]
        z = [[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]]
        lab = [tr("ml.trav"), tr("ml.nontrav")]
        fig = go.Figure(go.Heatmap(z=z, x=[tr("ml.pred") + ": " + l for l in lab], y=[tr("ml.actual") + ": " + l for l in lab],
                                   colorscale="Blues", text=z, texttemplate="%{text}", showscale=False))
        fig.update_layout(height=320, title=tr("ml.confusion"), yaxis=dict(autorange="reversed"))
        ui.plotly(fig, key="ml_cm")
    with c2:
        imp = pd.DataFrame(card["importance"])
        fig = go.Figure(go.Bar(x=imp["importance"], y=[tr("feat." + f) for f in imp["feature"]], orientation="h",
                               error_x=dict(array=imp["std"]), marker_color="#e4572e"))
        fig.update_layout(height=320, title=tr("ml.importance"), yaxis=dict(autorange="reversed"))
        ui.plotly(fig, key="ml_imp")
    hist = card.get("history")
    if hist:
        h = pd.DataFrame(hist)
        fig = go.Figure()
        fig.add_scatter(x=h["epoch"], y=h["train_loss"], name=tr("ml.loss_train"))
        if "val_loss" in h:
            fig.add_scatter(x=h["epoch"], y=h["val_loss"], name=tr("ml.loss_val"))
        fig.update_layout(height=280, title=tr("ml.history"), xaxis_title="epoch")
        ui.plotly(fig, key="ml_hist")
    ui.section(tr("ml.prob_map"))
    pm = ctx.eng.ml_prob()
    if pm is not None:
        m = V.base_map(ctx.g, {tr("layer.hillshade"): (maps.overlay_png(state._dem_key(), "hillshade", ctx.mp.slope_limit_deg), True),
                               tr("layer.ml"): (V.png_url(V.to_rgba(pm, "RdYlGn_r", 0, 1, alpha=0.6)), True)})
        c1, c2 = st.columns([3, 2])
        with c1:
            maps.render_map(V.finish(m), height=420, key="ml_map", tr=tr)
        with c2:
            rule_lab = TV.labels(ctx.g, ctx.eng.T, TV.LabelRule(**_rule(card)))
            v = np.isfinite(ctx.g.z)
            agree = float(((pm[v] >= card["test"]["threshold"]) == (rule_lab[v] == 1)).mean())
            st.metric(tr("ml.mean_p"), f"{np.nanmean(pm[v]):.3f}")
            st.metric(tr("ml.share_nontrav"), f"{(pm[v] >= card['test']['threshold']).mean() * 100:.1f} %")
            st.metric(tr("ml.agree"), f"{agree * 100:.1f} %")
            st.caption(tr("ml.map_note"))
    ui.export_buttons(tr, "traversability_model_card", cmp_df, obj=card, key="mlc")


def _rule(card):
    import re
    m = re.findall(r"[-+]?\d*\.?\d+", card["label_rule"])
    return {"slope_max_deg": float(m[0]), "rough_max_m": float(m[1])} if len(m) >= 2 else {}


def _torch_ver():
    import torch
    return torch.__version__.split("+")[0]
