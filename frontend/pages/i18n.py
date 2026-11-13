"""24 Multilingual System."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from frontend.components import ui
from mars_survive.localization import i18n


def render(ctx):
    tr = ctx.tr
    ui.header("i18n", tr)
    cov = i18n.coverage()
    df = pd.DataFrame([{"code": c["code"], "language": c["language"], "english": c["english"], "rtl": "✓" if c["rtl"] else "",
                        "keys": f"{c['keys']}/{c['total']}", "coverage_pct": round(100 * c["coverage"], 1)} for c in cov])
    c = st.columns(3)
    c[0].metric(tr("i18n.languages"), len(cov))
    c[1].metric(tr("i18n.keys"), cov[0]["total"])
    c[2].metric(tr("i18n.min_cov"), f"{min(x['coverage'] for x in cov) * 100:.1f} %")
    fig = go.Figure(go.Bar(x=df["language"], y=df["coverage_pct"], marker_color="#2ec4b6"))
    fig.update_layout(height=260, yaxis_range=[0, 105], yaxis_title="%", title=tr("i18n.coverage"))
    ui.plotly(fig, key="i18n_cov")
    ui.df_show(ui.tr_cols(df, tr))
    ui.section(tr("i18n.compare"))
    keys = sorted(i18n._load("en"))
    k = st.selectbox(tr("i18n.key"), keys, index=keys.index("app.subtitle") if "app.subtitle" in keys else 0)
    ui.df_show(pd.DataFrame([{"code": c, "language": v[0], "text": i18n.t(k, c)} for c, v in i18n.LANGUAGES.items()]))
    ui.section(tr("i18n.fallback_test"))
    st.code(f"t('__missing__', '{ctx.lang}') -> '{i18n.t('__missing__', ctx.lang)}'\n"
            f"t('mod.route', '{ctx.lang}') -> '{i18n.t('mod.route', ctx.lang)}'")
    with st.expander(tr("i18n.add_lang")):
        st.markdown(tr("i18n.add_text"))
    ui.export_buttons(tr, "translation_coverage", df)
    st.caption(tr("i18n.review_note"))
    ui.footer("i18n", tr, "one translation service (mars_survive/localization/i18n.py), flat JSON per language,\n"
                          "fallback: selected → English → key; placeholders {name} checked by tests; RTL for Arabic",
              ["mars_survive/localization/locales/*.json"])
