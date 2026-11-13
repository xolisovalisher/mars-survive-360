"""12 SPICE & Orbital Geometry."""
from __future__ import annotations

from datetime import datetime, time, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config as C
from frontend.components import ui
from mars_survive.common import ModuleError
from mars_survive.ingestion.importer import safe_name
from mars_survive.spice import kernels as K
from mars_survive.spice.mars_time import daylight_series, season_name, solar_elevation


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("spice", tr)
    st_k = K.status()
    have = all(k["present"] for k in st_k)
    c1, c2 = st.columns([3, 2])
    with c1:
        ui.section("🧩 " + tr("spice.kernels"))
        ui.df_show(ui.tr_cols(pd.DataFrame([{"type": k["kind"], "file": k["file"], "exists": "✓" if k["present"] else "✗",
                                  "description": k["purpose"], "url": k["url"]} for k in st_k]), tr).rename(columns={"description": tr("lbl.description")}))
        st.caption(tr("spice.spiceypy", v=tr("ui.yes") if K.available() else tr("ui.no")))
    with c2:
        ups = st.file_uploader(tr("spice.upload"), type=["tls", "tpc", "bsp", "tf", "ti", "tsc", "bc"], accept_multiple_files=True)
        if ups and st.button("⬆️ " + tr("btn.save_kernels")):
            for u in ups:
                name = safe_name(u.name)
                kind = {".tls": "lsk", ".tpc": "pck", ".bsp": "spk", ".tf": "fk", ".ti": "ik", ".tsc": "sclk", ".bc": "ck"}[
                    "." + name.rsplit(".", 1)[-1].lower()]
                dest = C.SPICE_DIR / kind / name
                dest.write_bytes(u.getvalue())
                v = K.validate_kernel(dest)
                if not v["ok"]:
                    dest.unlink()
                    st.error(f"{name}: {v['reason']}")
                else:
                    st.success(f"{name} ✓")
            st.rerun()
        if not have:
            st.warning(tr("spice.missing"))
    with ui.params(tr):
        c = st.columns(4)
        d = c[0].date_input(tr("spice.date"), datetime(2035, 3, 1).date())
        tm = c[1].time_input(tr("spice.time"), time(12, 0))
        lat = c[2].number_input("lat (°N)", -90.0, 90.0, float(ss.start[0]), format="%.4f")
        lon = c[3].number_input("lon (°E)", -180.0, 360.0, float(ss.start[1]), format="%.4f")
        min_el = st.slider(tr("spice.min_sun"), -10, 40, 10)
    dt = datetime.combine(d, tm, tzinfo=timezone.utc)
    m = solar_elevation(dt, lat, lon)
    c = st.columns(6)
    c[0].metric("Ls", f"{m['Ls']:.2f}°", tr("season." + season_name(m["Ls"], lat >= 0)), delta_color="off")
    c[1].metric("MSD", f"{m['MSD']:.2f}")
    c[2].metric("LMST", _hm(m["LMST_h"]))
    c[3].metric("LTST", _hm(m["LTST_h"]))
    c[4].metric(tr("spice.sun_elev"), f"{m['elevation_deg']:.1f}°")
    c[5].metric(tr("spice.sun_az"), f"{m['azimuth_deg']:.0f}°")
    if have and K.available():
        try:
            sg = K.sun_geometry(dt, lat, lon)
            st.success(tr("spice.compare", e=f"{sg['elevation_deg']:.2f}", a=f"{sg['azimuth_deg']:.1f}", l=f"{sg['Ls']:.2f}",
                          d=f"{sg['elevation_deg'] - m['elevation_deg']:+.2f}"))
        except ModuleError as e:
            st.error(f"{tr(e.key)} {e.detail}")
        except Exception as e:  # noqa: BLE001
            st.error(f"SPICE: {e}")
    else:
        st.info(tr("spice.fallback"))
    start = datetime.combine(d, time(0, 0), tzinfo=timezone.utc)
    ts, el, lt = daylight_series(start, lat, lon, hours=24.66 * 1.0, step_min=10)
    th = np.array([(t - start).total_seconds() / 3600 for t in ts])
    fig = go.Figure(go.Scatter(x=th, y=el, line=dict(color="#ffd166"), name=tr("spice.sun_elev")))
    fig.add_hline(y=0, line_color="#888")
    fig.add_hline(y=min_el, line_dash="dash", line_color="#2ec4b6")
    fig.update_layout(height=300, xaxis_title=tr("spice.hours_utc"), yaxis_title="°", title=tr("spice.daylight"))
    ui.plotly(fig, key="spice_day")
    ok = el >= min_el
    wins = []
    i = 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j + 1 < len(ok) and ok[j + 1]:
                j += 1
            wins.append({"start_utc": ts[i].strftime("%H:%M"), "end_utc": ts[j].strftime("%H:%M"),
                         "ltst_start": _hm(lt[i]), "ltst_end": _hm(lt[j]), "duration_h": round((j - i) * 10 / 60, 2),
                         "max_elev_deg": round(float(el[i:j + 1].max()), 1)})
            i = j + 1
        else:
            i += 1
    ui.section(tr("spice.eva_windows", e=min_el))
    ui.df_show(ui.tr_cols(pd.DataFrame(wins), tr))
    ui.export_buttons(tr, "solar_geometry", pd.DataFrame({"utc": [t.isoformat() for t in ts], "elev_deg": el, "ltst_h": lt}),
                      {k: v for k, v in m.items()})
    ui.footer("spice", tr, "Mars24 (Allison & McEwen 2000): M, α_FMS, PBS, ν−M, Ls, EOT, MST, LMST, LTST, δs, subsolar lon\n"
                           "elevation = 90° − acos(sinδ sinφ + cosδ cosφ cos H); SPICE: spkpos(SUN, IAU_MARS, LT+S) + surfnm",
              ["Allison & McEwen 2000, Planet. Space Sci. 48:215", "NASA GISS Mars24 algorithm", "NAIF SPICE Toolkit (spiceypy)"])


def _hm(h):
    h = h % 24
    return f"{int(h):02d}:{int(round((h % 1) * 60)) % 60:02d}"
