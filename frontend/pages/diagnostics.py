"""26 System Diagnostics."""
from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd
import streamlit as st

import config as C
from frontend.components import ui
from mars_survive.diagnostics import checks


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("diagnostics", tr)
    py = checks.python_info()
    res = checks.resources()
    mods = checks.modules_health()
    ss._mods_ok = (sum(m["ok"] for m in mods), len(mods))
    c = st.columns(5)
    c[0].metric("Python", py["python"], "OK" if py["ok"] else "≥3.10!", delta_color="off")
    c[1].metric(tr("diag.modules"), f"{ss._mods_ok[0]}/{ss._mods_ok[1]}")
    c[2].metric(tr("diag.disk_free"), f"{res['disk_free_gb']} GB")
    c[3].metric(tr("diag.ram_free"), f"{res.get('ram_available_gb', '?')} GB")
    c[4].metric(tr("diag.rss"), f"{res.get('process_rss_mb', '?')} MB")
    t1, t2, t3, t4, t5 = st.tabs(["📦 " + tr("diag.libs"), "🧩 " + tr("diag.modules"), "🗂 " + tr("diag.data"),
                                  "🧪 " + tr("diag.tests"), "📜 " + tr("diag.logs")])
    with t1:
        lb = pd.DataFrame(checks.libraries())
        lb["ok"] = lb["ok"].map(lambda v: "✓" if v else "✗")
        lb["optional"] = lb["optional"].map(lambda v: tr("ui.yes") if v else "")
        if "error" in lb:
            lb["error"] = lb["error"].fillna("").map(lambda v: "" if v in (None, "None") else str(v))
        ui.df_show(ui.tr_cols(lb, tr))
    with t2:
        md = pd.DataFrame(mods)
        md["ok"] = md["ok"].map(lambda v: "✓" if v else "✗")
        if "error" in md:
            md["error"] = md["error"].fillna("").map(lambda v: "" if v in (None, "None") else str(v))
        ui.df_show(ui.tr_cols(md, tr))
    with t3:
        ui.df_show(ui.tr_cols(pd.DataFrame(checks.directories()), tr))
        st.json(checks.data_assets())
        st.caption(py["platform"])
    with t4:
        last = checks.last_test_report()
        if last:
            c = st.columns(4)
            c[0].metric(tr("diag.passed"), last.get("passed", 0))
            c[1].metric(tr("diag.failed"), last.get("failed", 0))
            c[2].metric(tr("diag.skipped"), last.get("skipped", 0))
            c[3].metric(tr("diag.when"), last.get("when", "")[:16])
        if st.button("▶️ " + tr("btn.run_tests"), type="primary"):
            with st.spinner(tr("ui.computing")):
                try:
                    p = subprocess.run([sys.executable, str(C.ROOT / "scripts" / "run_tests.py"), "--quick"], cwd=C.ROOT,
                                       capture_output=True, text=True, timeout=900)
                    st.session_state["_diag_out"] = p.stdout[-6000:] + p.stderr[-2000:]
                except subprocess.TimeoutExpired:
                    st.session_state["_diag_out"] = tr("diag.timeout")
            st.rerun()
        if st.session_state.get("_diag_out"):
            st.code(st.session_state["_diag_out"])
    with t5:
        st.code(checks.log_tail(60) or "—")
    ui.export_buttons(tr, "diagnostics", obj={"python": py, "resources": res, "modules": mods, "data": checks.data_assets()})
    ui.footer("diagnostics", tr, "importlib checks per module/library; disk via shutil, memory via psutil; tests via pytest",
              ["logs/app.log", "docs/test_results.json"])
