"""07 AI / Computer Vision."""
from __future__ import annotations

import io
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import config as C
from frontend.components import maps, state, ui
from mars_survive.ai import terrain_units, vision
from mars_survive.ingestion.importer import validate
from mars_survive.mapping import views as V


def render(ctx):
    tr, ss = ctx.tr, st.session_state
    ui.header("ai", tr)
    ys = vision.yolo_status()
    t0, t1, t2, t3, t4 = st.tabs([tr("ml.tab"), tr("ai.detect"), tr("ai.units"),
                                  tr("ai.yolo_train"), tr("ai.assistant")])
    with t0:
        from frontend.components import ml_tab
        ml_tab.render(ctx)
    with t1:
        with ui.params(tr):
            c1, c2, c3 = st.columns(3)
            src = c1.radio(tr("ai.image_source"), ["synthetic", "upload"], format_func=lambda s: tr("ai.src." + s))
            engines = ["heuristic_cv"] + (["yolo"] if ys["ready"] else [])
            eng = c2.selectbox(tr("ai.engine"), engines, format_func=lambda e: tr("ai.eng." + e))
            if not ys["ready"]:
                c2.caption(tr("ai.yolo_unavailable", pkg=tr("ui.yes") if ys["package"] else tr("ui.no"),
                                      w=len(ys["weights"])))
            conf = c3.slider(tr("ai.conf"), 0.05, 0.95, 0.25, 0.05)
            up = st.file_uploader(tr("ai.upload_img"), type=["png", "jpg", "jpeg"]) if src == "upload" else None
            gt_up = st.file_uploader(tr("ai.upload_gt"), type=["txt"])
        img, gts, dc = None, None, "Synthetic"
        if src == "synthetic":
            img, gts = vision.synthetic_test_image(seed=int(ss.get("ai_seed", 0)))
            if st.button(tr("ai.new_scene")):
                ss.ai_seed = int(ss.get("ai_seed", 0)) + 1
                st.rerun()
        elif up is not None:
            try:
                validate(up.name, up.getvalue())
                img = np.asarray(Image.open(io.BytesIO(up.getvalue())).convert("RGB"))
                dc = "User Supplied"
            except Exception as e:  # noqa: BLE001
                st.error(f"{tr('err.image')}: {e}")
        if gt_up is not None and img is not None:
            gts = vision.read_yolo_labels(gt_up.getvalue().decode("utf-8", "replace"), img.shape[1], img.shape[0])
        if img is None:
            st.info(tr("ai.need_image"))
        else:
            if eng == "yolo":
                dets = ui.run_safely(tr, vision.yolo_detect, img, ys["weights"][0], conf) or []
            else:
                dets = ui.run_safely(tr, vision.heuristic_detect, img) or []
            dets = [d for d in dets if d.get("score", 1) >= conf]
            st.markdown(ui.badge(dc, tr) + ("" if eng == "yolo" else f"<span class='ms-badge ms-b-simulated'>"
                        f"{tr('ai.not_trained_badge')}</span>"), unsafe_allow_html=True)
            c1, c2 = st.columns([3, 2])
            c1.image(vision.draw(img, dets), caption=tr("ai.detections", n=len(dets)), width="stretch")
            with c2:
                cnt = pd.Series([d["cls"] for d in dets]).value_counts() if dets else pd.Series(dtype=int)
                c = st.columns(3)
                for i, k in enumerate(vision.CLASSES):
                    c[i].metric(tr("cls." + k), int(cnt.get(k, 0)))
                st.metric(tr("ai.hazard_cover"), f"{vision.hazard_score(dets, img.shape) * 100:.1f} %")
                if gts:
                    ev = vision.evaluate(dets, gts)
                    ui.section(tr("ai.metrics"))
                    m = st.columns(5)
                    for i, (k, lbl) in enumerate([("precision", "P"), ("recall", "R"), ("f1", "F1"), ("map50", "mAP50"),
                                                  ("map50_95", "mAP50-95")]):
                        m[i].metric(lbl, f"{ev[k]:.3f}")
                    ui.df_show(pd.DataFrame(ev["per_class"]).T.reset_index().rename(columns={"index": "class"}).round(3))
                    st.caption(tr("ai.metrics_note"))
                else:
                    st.info(tr("ai.no_gt"))
            df = pd.DataFrame(dets)
            if not df.empty:
                ui.df_show(df.round(1), height=200)
                ui.export_buttons(tr, "detections", df)
    with t2:
        c1, c2 = st.columns(2)
        k = c1.slider(tr("ai.k"), 3, 8, 5)
        feats = c2.multiselect(tr("ai.features"), ["slope", "roughness", "tpi", "relief", "curvature"],
                               default=["slope", "roughness", "tpi"], format_func=lambda n: tr("layer." + n))
        if st.button(tr("btn.train_kmeans"), type="primary") or "units" not in ss or ss.get("units_k") != (k, tuple(feats)):
            T = ctx.eng.T
            fe = {f: getattr(T, f) for f in feats if f != "tpi"} | ({"tpi": T.tpi} if "tpi" in feats else {})
            if ctx.g.thermal is not None:
                fe["thermal"] = ctx.g.thermal
            if len(fe) >= 2:
                res = ui.run_safely(tr, terrain_units.train, fe, k)
                if res:
                    ss.units, ss.units_k = res, (k, tuple(feats))
        if "units" in ss:
            lab, info, q = ss.units
            pal = {i: c for i, c in enumerate(["#4daf4a", "#ffff33", "#ff7f00", "#e41a1c", "#377eb8", "#984ea3", "#a65628", "#f781bf"])}
            url = V.png_url(V.classes_rgba(lab, pal, 0.6))
            m = V.base_map(ctx.g, {tr("layer.hillshade"): (maps.overlay_png(state._dem_key(), "hillshade", ctx.mp.slope_limit_deg), True),
                                   tr("ai.units"): (url, True)})
            c1, c2 = st.columns([3, 2])
            with c1:
                maps.render_map(V.finish(m), height=430, key="units_map", tr=tr)
            with c2:
                df = pd.DataFrame(info)
                df["name"] = df["name"].map(lambda n: tr("unit." + n))
                df["color"] = [pal[i] for i in df["unit"]]
                ui.df_show(df.round(3))
                st.metric(tr("ai.silhouette"), f"{q['silhouette']:.3f}")
                st.caption(tr("ai.units_note"))
                ui.export_buttons(tr, "terrain_units", df)
    with t3:
        st.markdown(tr("ai.yolo_text"))
        st.write({"ultralytics": ys["package"], "weights": ys["weights"] or "—", "models_dir": str(C.MODELS_DIR / "yolo")})
        c1, c2 = st.columns(2)
        img_dir = c1.text_input(tr("ai.images_dir"), str(C.DATA / "samples" / "images"))
        lab_dir = c2.text_input(tr("ai.labels_dir"), str(C.DATA / "samples" / "labels"))
        c3, c4, c5 = st.columns(3)
        r_tr = c3.slider("train", 0.5, 0.9, 0.7, 0.05)
        r_va = c4.slider("val", 0.05, 0.4, 0.2, 0.05)
        c5.metric("test", f"{max(0.0, 1 - r_tr - r_va):.2f}")
        if st.button(tr("btn.split_dataset")):
            from pathlib import Path
            if not Path(img_dir).is_dir():
                st.error(tr("ai.dir_missing", d=img_dir))
            else:
                out = ui.run_safely(tr, vision.split_dataset, Path(img_dir), Path(lab_dir), C.DATA / "processed" / "yolo_dataset",
                                    (r_tr, r_va, 1 - r_tr - r_va))
                if out:
                    st.success(str(out))
        ep = st.number_input(tr("ai.epochs"), 1, 500, 50)
        if st.button(tr("btn.train_yolo"), disabled=not ys["package"]):
            yaml = C.DATA / "processed" / "yolo_dataset" / "data.yaml"
            if not yaml.exists():
                st.error(tr("ai.need_split"))
            else:
                out = ui.run_safely(tr, vision.yolo_train, str(yaml), int(ep))
                if out:
                    st.success(str(out))
        if not ys["package"]:
            st.info(tr("ai.install_hint"))
            st.code("pip install ultralytics")
    with t4:
        r, prof, cuts = state.active(ctx)
        if r is None:
            st.info(tr("alert.no_route"))
        else:
            s = r.summary()
            tb = state.turnback(ctx)
            lines = [tr("asst.intro", s=tr("strat." + ss.strategy), km=f"{s['distance_3d_km']:.2f}", h=f"{prof['duration_h']:.2f}"),
                     tr("asst.terrain", ms=f"{s['mean_slope_deg']:.1f}", xs=f"{s['max_slope_deg']:.1f}",
                        g=f"{s['elev_gain_m']:.0f}", l=f"{s['elev_loss_m']:.0f}"),
                     tr("asst.hazard", m=f"{s['hazard_mean']:.2f}", x=f"{s['hazard_max']:.2f}")]
            if ctx.mp.scenario == "astronaut":
                lines.append(tr("asst.o2", o=f"{prof['o2_total_l']:.0f}", c=f"{ctx.mp.o2_capacity_l:.0f}"))
            else:
                lines.append(tr("asst.energy", e=f"{prof['e_j'][-1] / 3600:.0f}", c=f"{ctx.mp.rover.battery_wh:.0f}"))
            if tb:
                lines.append(tr("expl.turnback_ok" if tb["feasible"] else "expl.turnback_bad", m=f"{tb['min_margin_h']:.2f}"))
            steep = np.where(r.slope_deg > 0.7 * ctx.mp.slope_limit_deg)[0]
            if len(steep):
                lines.append(tr("asst.steep", n=len(steep), km=f"{r.dist3d_m[steep[0]] / 1000:.2f}"))
            for ln in lines:
                st.markdown("• " + ln)
            st.caption(tr("asst.note"))
            q = st.text_input(tr("asst.ask"), max_chars=300)
            if q:
                if os.environ.get("ANTHROPIC_API_KEY"):
                    ans = ui.run_safely(tr, _llm, q, lines, ctx.lang)
                    if ans:
                        st.markdown(ans)
                else:
                    st.info(tr("asst.no_llm"))
    ui.footer("ai", tr, "heuristic CV: Hough circles (craters), adaptive threshold + solidity/aspect filters (rocks),\n"
                        "low Laplacian texture & bright (sand); YOLO only with installed weights; metrics: IoU≥0.5,\n"
                        "AP = 101-point interpolated (COCO), mAP50-95 = mean over IoU 0.50:0.05:0.95; K-Means k units",
              ["OpenCV", "Ultralytics YOLO (optional)", "scikit-learn KMeans", ctx.g.source])


def _llm(question, facts, lang):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=os.environ.get("MARS_LLM_MODEL", "claude-sonnet-5-5"), max_tokens=600,
                                 system="You explain a DEMONSTRATION Mars traverse plan. Use ONLY the facts given. "
                                        "Say clearly that numbers come from simplified models and are not safety guidance. "
                                        f"Answer in language code '{lang}'.",
                                 messages=[{"role": "user", "content": "Facts:\n" + "\n".join(facts) + "\n\nQuestion: " + question}])
    return msg.content[0].text
