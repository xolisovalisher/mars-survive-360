"""AI / Computer Vision (module 7).

Three clearly separated engines:
  1. "heuristic_cv"  - classical OpenCV detector (NOT a trained model): crater
     candidates by Hough circles on a smoothed image; rock candidates as compact
     dark blobs with a bright side (shadow/sunlit pair) via adaptive threshold
     + contour shape filters; sand/dune areas as low-texture, high-brightness regions.
  2. "yolo"          - Ultralytics YOLO, only if the package AND a weights file
     exist (models/yolo/*.pt). Otherwise reported as unavailable - never faked.
  3. evaluation      - precision / recall / F1 / AP50 / AP50-95 for any engine
     given ground-truth boxes (YOLO txt format), plus dataset split tooling.
"""
from __future__ import annotations

import random
import shutil
from pathlib import Path

import numpy as np

import config as C

CLASSES = ["rock", "crater", "sand"]


# ---------------------------------------------------------------- heuristic engine
def heuristic_detect(img_rgb: np.ndarray, min_rock_px: int = 12, max_rock_px: int = 4000) -> list[dict]:
    import cv2
    g = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY) if img_rgb.ndim == 3 else img_rgb
    h0, w0 = g.shape
    scale = min(1.0, 768 / max(h0, w0))            # work on <= 768 px for speed, report in original pixels
    if scale < 1:
        g = cv2.resize(g, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_AREA)
    h, w = g.shape
    den = cv2.GaussianBlur(cv2.medianBlur(g, 5), (0, 0), 1.5)
    dets = []
    # craters: strong circular edges on a smoothed image
    blur = cv2.GaussianBlur(den, (0, 0), 2.5)
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.5, minDist=max(h, w) / 12, param1=60, param2=35,
                               minRadius=max(8, min(h, w) // 40), maxRadius=min(h, w) // 4)
    if circles is not None:
        for x, y, r in circles[0][:30]:
            dets.append({"cls": "crater", "x1": float(x - r) / scale, "y1": float(y - r) / scale,
                         "x2": float(x + r) / scale, "y2": float(y + r) / scale, "score": 0.5})
    # rocks: compact blobs clearly darker than the local background (shadowed side)
    bg = cv2.GaussianBlur(den, (0, 0), 12)
    diff = cv2.subtract(bg, den)
    thr = max(12.0, float(np.percentile(diff, 99.0)) * 0.6)
    mask = (diff > thr).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    smin, smax = min_rock_px * scale ** 2, max_rock_px * scale ** 2
    for c in cnts:
        a = cv2.contourArea(c)
        if not (smin <= a <= smax):
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        solidity = a / max(cv2.contourArea(cv2.convexHull(c)), 1)
        if solidity < 0.75 or max(bw, bh) / max(min(bw, bh), 1) > 3:
            continue
        contrast = float(diff[y:y + bh, x:x + bw].mean())
        dets.append({"cls": "rock", "x1": x / scale, "y1": y / scale, "x2": (x + bw) / scale, "y2": (y + bh) / scale,
                     "score": float(min(0.95, 0.3 + 0.4 * solidity + contrast / 200))})
    # sand: low texture, above-median brightness, large regions
    lap = cv2.Laplacian(den, cv2.CV_32F)
    tex = cv2.blur(np.abs(lap), (31, 31))
    sand = ((tex < np.percentile(tex, 15)) & (den > np.median(den))).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(sand, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        if cv2.contourArea(c) > 0.02 * h * w:
            x, y, bw, bh = cv2.boundingRect(c)
            dets.append({"cls": "sand", "x1": x / scale, "y1": y / scale, "x2": (x + bw) / scale, "y2": (y + bh) / scale,
                         "score": 0.4})
    return dets


def draw(img_rgb: np.ndarray, dets: list[dict]) -> np.ndarray:
    import cv2
    out = img_rgb.copy()
    col = {"rock": (255, 80, 60), "crater": (60, 200, 255), "sand": (255, 220, 60)}
    for d in dets:
        cv2.rectangle(out, (int(d["x1"]), int(d["y1"])), (int(d["x2"]), int(d["y2"])), col.get(d["cls"], (255, 255, 255)), 2)
    return out


def hazard_score(dets: list[dict], shape) -> float:
    """Fraction of image area covered by rock/crater detections (0..1) - a terrain hazard proxy."""
    h, w = shape[:2]
    m = np.zeros((h, w), bool)
    for d in dets:
        if d["cls"] in ("rock", "crater"):
            m[max(0, int(d["y1"])):int(d["y2"]), max(0, int(d["x1"])):int(d["x2"])] = True
    return float(m.mean())


# ---------------------------------------------------------------- YOLO engine
def yolo_status() -> dict:
    try:
        import ultralytics  # noqa: F401
        pkg = True
    except Exception:  # noqa: BLE001
        pkg = False
    weights = sorted(str(p) for p in (C.MODELS_DIR / "yolo").glob("*.pt"))
    return {"package": pkg, "weights": weights, "ready": pkg and bool(weights)}


def yolo_detect(img_rgb: np.ndarray, weights: str, conf: float = 0.25) -> list[dict]:
    from ultralytics import YOLO
    model = YOLO(weights)
    res = model.predict(img_rgb, conf=conf, verbose=False)[0]
    names = res.names
    out = []
    for b, c, s in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.cls.cpu().numpy(), res.boxes.conf.cpu().numpy()):
        out.append({"cls": names[int(c)], "x1": float(b[0]), "y1": float(b[1]), "x2": float(b[2]), "y2": float(b[3]),
                    "score": float(s)})
    return out


def yolo_train(data_yaml: str, epochs: int = 50, imgsz: int = 640, base: str = "yolov8n.pt") -> dict:
    from ultralytics import YOLO
    m = YOLO(base)
    r = m.train(data=data_yaml, epochs=epochs, imgsz=imgsz, project=str(C.MODELS_DIR / "checkpoints"))
    return {"save_dir": str(getattr(r, "save_dir", ""))}


# ---------------------------------------------------------------- dataset tools
def split_dataset(images_dir: Path, labels_dir: Path, out_dir: Path, ratios=(0.7, 0.2, 0.1), seed: int = 0) -> dict:
    """Create YOLO folder structure images/{train,val,test}, labels/{...} and data.yaml."""
    imgs = sorted([p for p in images_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    random.Random(seed).shuffle(imgs)
    n = len(imgs)
    n_tr, n_va = int(ratios[0] * n), int(ratios[1] * n)
    parts = {"train": imgs[:n_tr], "val": imgs[n_tr:n_tr + n_va], "test": imgs[n_tr + n_va:]}
    for split, items in parts.items():
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
        for p in items:
            shutil.copy2(p, out_dir / "images" / split / p.name)
            lab = labels_dir / (p.stem + ".txt")
            if lab.exists():
                shutil.copy2(lab, out_dir / "labels" / split / lab.name)
    yaml = out_dir / "data.yaml"
    yaml.write_text(f"path: {out_dir}\ntrain: images/train\nval: images/val\ntest: images/test\n"
                    f"names: {dict(enumerate(CLASSES))}\n", encoding="utf-8")
    return {k: len(v) for k, v in parts.items()} | {"yaml": str(yaml)}


def read_yolo_labels(text: str, w: int, h: int) -> list[dict]:
    """YOLO txt: class cx cy bw bh (normalised)."""
    out = []
    for line in text.strip().splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:5])
        out.append({"cls": CLASSES[c] if c < len(CLASSES) else str(c), "x1": (cx - bw / 2) * w, "y1": (cy - bh / 2) * h,
                    "x2": (cx + bw / 2) * w, "y2": (cy + bh / 2) * h})
    return out


# ---------------------------------------------------------------- evaluation
def iou(a, b) -> float:
    ix = max(0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    iy = max(0, min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]))
    inter = ix * iy
    ua = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"]) + (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) - inter
    return inter / ua if ua > 0 else 0.0


def _ap(preds, gts, thr):
    preds = sorted(preds, key=lambda d: -d.get("score", 1))
    used = set()
    tp = []
    for p in preds:
        best, bj = 0, -1
        for j, g in enumerate(gts):
            if j in used or g["cls"] != p["cls"]:
                continue
            v = iou(p, g)
            if v > best:
                best, bj = v, j
        if best >= thr:
            used.add(bj)
            tp.append(1)
        else:
            tp.append(0)
    if not gts:
        return 0.0, 0, len(preds), 0
    tp = np.array(tp, float)
    ctp = np.cumsum(tp)
    rec = ctp / len(gts)
    prec = ctp / np.arange(1, len(tp) + 1) if len(tp) else np.array([])
    # 101-point interpolated AP (COCO style)
    ap = 0.0
    for r in np.linspace(0, 1, 101):
        p = prec[rec >= r].max() if len(prec) and (rec >= r).any() else 0.0
        ap += p / 101
    n_tp = int(tp.sum())
    return ap, n_tp, len(preds) - n_tp, len(gts) - n_tp


def evaluate(preds: list[dict], gts: list[dict]) -> dict:
    classes = sorted({g["cls"] for g in gts} | {p["cls"] for p in preds})
    out = {"per_class": {}}
    aps50, aps5095 = [], []
    TP = FP = FN = 0
    for c in classes:
        pc, gc = [p for p in preds if p["cls"] == c], [g for g in gts if g["cls"] == c]
        ap50, tp, fp, fn = _ap(pc, gc, 0.5)
        ap_range = [(_ap(pc, gc, t)[0]) for t in np.arange(0.5, 0.96, 0.05)]
        TP, FP, FN = TP + tp, FP + fp, FN + fn
        if gc:
            aps50.append(ap50)
            aps5095.append(float(np.mean(ap_range)))
        out["per_class"][c] = {"ap50": ap50, "ap50_95": float(np.mean(ap_range)), "tp": tp, "fp": fp, "fn": fn}
    P = TP / (TP + FP) if TP + FP else 0.0
    R = TP / (TP + FN) if TP + FN else 0.0
    out.update(precision=P, recall=R, f1=2 * P * R / (P + R) if P + R else 0.0,
               map50=float(np.mean(aps50)) if aps50 else 0.0, map50_95=float(np.mean(aps5095)) if aps5095 else 0.0,
               tp=TP, fp=FP, fn=FN)
    return out


def synthetic_test_image(seed: int = 0, size: int = 512):
    """SYNTHETIC test scene with known boxes (for verifying the pipeline, not Mars imagery)."""
    import cv2
    rng = np.random.default_rng(seed)
    img = np.clip(rng.normal(150, 12, (size, size)), 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (5, 5), 0)
    gts = []
    for _ in range(3):
        x, y, r = rng.integers(60, size - 60, 2).tolist() + [int(rng.integers(20, 45))]
        cv2.circle(img, (x, y), r, 95, 4)
        cv2.circle(img, (x, y), r - 4, 120, -1)
        gts.append({"cls": "crater", "x1": x - r, "y1": y - r, "x2": x + r, "y2": y + r})
    for _ in range(12):
        x, y = rng.integers(20, size - 20, 2).tolist()
        rx, ry = int(rng.integers(4, 10)), int(rng.integers(4, 10))
        cv2.ellipse(img, (x, y), (rx, ry), 0, 0, 360, 40, -1)
        gts.append({"cls": "rock", "x1": x - rx, "y1": y - ry, "x2": x + rx, "y2": y + ry})
    rgb = np.stack([img * 1.0, img * 0.75, img * 0.55], -1).clip(0, 255).astype(np.uint8)
    return rgb, gts
