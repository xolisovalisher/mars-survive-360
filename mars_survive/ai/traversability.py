"""Supervised terrain-traversability model (module 07 → used by route planning, module 05).

Task
    Per DEM cell: P(cell is NOT traversable for a suited astronaut on foot).

Labels (weak supervision — stated honestly everywhere)
    A cell is labelled non-traversable (1) if its slope > ``slope_max_deg`` (default 15°, ASSUMPTION for walking
    in a pressurised suit with load) OR its roughness > ``rough_max_m`` (default 2 m RMS residual relief,
    ASSUMPTION), or it is NoData. These labels are computed from the DEM by explicit rules; they are NOT field
    observations or human annotations.

Features (context, not the label itself)
    The model never sees the cell's own slope or roughness. It sees the neighbourhood: ring statistics of
    slope/roughness (3×3 without the centre), 7×7 means/std, TRI, local relief, |curvature|, TPI, slope
    variability and elevation spread. So it has to *infer* the cell from its surroundings — a real learning
    problem whose skill is measured on spatially held-out blocks.

Protocol
    * Spatial block split (5×5 blocks): train / validation / test blocks are disjoint, so neighbouring
      (auto-correlated) cells never leak between sets.
    * Three model families: logistic regression (baseline), histogram gradient boosting, neural network
      (PyTorch MLP if torch is installed, otherwise scikit-learn MLP). Class imbalance via class weights.
    * Model selection and decision threshold on validation (max F1); the test set is used once.
    * Metrics: precision, recall, F1, ROC-AUC, PR-AUC (average precision), Brier score, confusion matrix,
      permutation feature importance.

Use in routing
    ``probability_grid`` gives P(non-traversable) for every cell; the planner blends it into the hazard
    index with weight ``ml_blend`` (0 = rules only, 1 = model only).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

import config as C
from mars_survive.common import get_logger

log = get_logger("ai.traversability")

MODEL_DIR = C.MODELS_DIR / "traversability"
MODEL_PATH = MODEL_DIR / "model.joblib"
CARD_PATH = MODEL_DIR / "model_card.json"

FEATURES = ["slope_ring_mean", "slope_ring_max", "slope_mean7", "slope_std7",
            "rough_ring_mean", "rough_ring_max", "rough_mean7",
            "tri", "relief", "abs_curvature", "tpi", "variability", "elev_std5"]

RING3 = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], bool)


@dataclass
class LabelRule:
    slope_max_deg: float = 15.0
    rough_max_m: float = 2.0

    def text(self) -> str:
        return f"slope > {self.slope_max_deg:g}° OR roughness > {self.rough_max_m:g} m OR NoData"


@dataclass
class TrainConfig:
    blocks: int = 5
    n_val_blocks: int = 5
    n_test_blocks: int = 5
    seed: int = 42
    max_train_rows: int = 60_000
    models: tuple = ("logistic", "gboost", "mlp")
    mlp_epochs: int = 25


# ---------------------------------------------------------------------------------------------- features
def _ring_mean(a):
    w = RING3.astype(float)
    num = ndi.convolve(np.nan_to_num(a), w, mode="nearest")
    den = ndi.convolve(np.isfinite(a).astype(float), w, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def _ring_max(a):
    return ndi.maximum_filter(np.nan_to_num(a, nan=np.nanmax(a)), footprint=RING3, mode="nearest")


def _mean(a, k):
    num = ndi.uniform_filter(np.nan_to_num(a), k, mode="nearest")
    den = ndi.uniform_filter(np.isfinite(a).astype(float), k, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def _std(a, k):
    m = _mean(a, k)
    m2 = _mean(a * a, k)
    return np.sqrt(np.clip(m2 - m * m, 0, None))


def feature_stack(g, T) -> np.ndarray:
    """(H, W, F) feature cube; NaN where the DEM has no data."""
    s, r = T.slope.astype(float), T.roughness.astype(float)
    z = g.z.astype(float)
    cube = np.stack([
        _ring_mean(s), _ring_max(s), _mean(s, 7), _std(s, 7),
        _ring_mean(r), _ring_max(r), _mean(r, 7),
        T.tri, T.relief, np.abs(T.curvature), T.tpi, T.variability, _std(z, 5),
    ], axis=-1).astype(np.float32)
    cube[~np.isfinite(z)] = np.nan
    return cube


def labels(g, T, rule: LabelRule = LabelRule()) -> np.ndarray:
    nod = ~np.isfinite(g.z)
    y = (np.nan_to_num(T.slope, nan=90) > rule.slope_max_deg) | (np.nan_to_num(T.roughness, nan=99) > rule.rough_max_m)
    return (y | nod).astype(np.int8)


def block_split(shape, cfg: TrainConfig, y: np.ndarray | None = None):
    """Assign every cell to train(0)/val(1)/test(2) by spatial block. Retries seeds until every split has
    both classes (so metrics are defined)."""
    h, w = shape
    b = cfg.blocks
    rb = np.minimum(np.arange(h) * b // h, b - 1)
    cb = np.minimum(np.arange(w) * b // w, b - 1)
    bid = rb[:, None] * b + cb[None, :]
    for k in range(50):
        rng = np.random.default_rng(cfg.seed + k)
        perm = rng.permutation(b * b)
        role = np.zeros(b * b, np.int8)
        role[perm[:cfg.n_test_blocks]] = 2
        role[perm[cfg.n_test_blocks:cfg.n_test_blocks + cfg.n_val_blocks]] = 1
        split = role[bid]
        if y is None:
            return split, bid
        ok = all(len(np.unique(y[split == s])) == 2 for s in (0, 1, 2))
        if ok:
            return split, bid
    return split, bid


# ---------------------------------------------------------------------------------------------- models
class TorchMLP:
    """Small fully connected network (PyTorch), sklearn-like interface. Trained with weighted BCE + Adam."""

    def __init__(self, n_in, hidden=(64, 32), epochs=25, lr=2e-3, batch=1024, seed=0, pos_weight=1.0):
        import torch
        from torch import nn
        torch.manual_seed(seed)
        layers, d = [], n_in
        for hdim in hidden:
            layers += [nn.Linear(d, hdim), nn.ReLU(), nn.Dropout(0.1)]
            d = hdim
        layers += [nn.Linear(d, 1)]
        self.net = nn.Sequential(*layers)
        self.epochs, self.lr, self.batch, self.seed, self.pos_weight = epochs, lr, batch, seed, pos_weight
        self.history = []

    def fit(self, X, y, Xv=None, yv=None):
        import torch
        from torch import nn
        Xt = torch.tensor(X, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([self.pos_weight]))
        g = torch.Generator().manual_seed(self.seed)
        for ep in range(self.epochs):
            self.net.train()
            idx = torch.randperm(len(Xt), generator=g)
            tot = 0.0
            for i in range(0, len(idx), self.batch):
                j = idx[i:i + self.batch]
                opt.zero_grad()
                loss = lossf(self.net(Xt[j]), yt[j])
                loss.backward()
                opt.step()
                tot += loss.item() * len(j)
            rec = {"epoch": ep + 1, "train_loss": tot / len(Xt)}
            if Xv is not None:
                with torch.no_grad():
                    self.net.eval()
                    lv = lossf(self.net(torch.tensor(Xv, dtype=torch.float32)),
                               torch.tensor(yv, dtype=torch.float32).unsqueeze(1))
                rec["val_loss"] = float(lv)
            self.history.append(rec)
        return self

    def predict_proba(self, X):
        import torch
        with torch.no_grad():
            self.net.eval()
            p = torch.sigmoid(self.net(torch.tensor(X, dtype=torch.float32))).numpy()[:, 0]
        return np.column_stack([1 - p, p])

    # joblib-friendly state
    def __getstate__(self):
        d = dict(self.__dict__)
        d["net"] = (self.net, {k: v.cpu() for k, v in self.net.state_dict().items()})
        return d

    def __setstate__(self, d):
        net, sd = d["net"]
        net.load_state_dict(sd)
        d["net"] = net
        self.__dict__.update(d)


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _make(name, n_in, pos_weight, cfg: TrainConfig):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if name == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")), "LogisticRegression"
    if name == "gboost":
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                              class_weight="balanced", random_state=cfg.seed,
                                              early_stopping=True, validation_fraction=0.15), "HistGradientBoosting"
    if name == "mlp":
        if torch_available():
            return ("torch", TorchMLP(n_in, epochs=cfg.mlp_epochs, seed=cfg.seed, pos_weight=pos_weight)), "PyTorch MLP 64-32"
        return make_pipeline(StandardScaler(), MLPClassifier((64, 32), max_iter=60, early_stopping=True,
                                                             random_state=cfg.seed)), "sklearn MLP 64-32"
    raise ValueError(name)


# ---------------------------------------------------------------------------------------------- metrics
def metrics(y, p, thr) -> dict:
    from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, f1_score,
                                 precision_score, recall_score, roc_auc_score)
    yh = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh, labels=[0, 1]).ravel()
    return {"n": int(len(y)), "positives": int(y.sum()), "threshold": float(thr),
            "precision": float(precision_score(y, yh, zero_division=0)),
            "recall": float(recall_score(y, yh, zero_division=0)),
            "f1": float(f1_score(y, yh, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan"),
            "pr_auc": float(average_precision_score(y, p)) if y.sum() else float("nan"),
            "brier": float(brier_score_loss(y, p)),
            "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def best_threshold(y, p) -> float:
    from sklearn.metrics import precision_recall_curve
    pr, rc, th = precision_recall_curve(y, p)
    f1 = 2 * pr * rc / np.clip(pr + rc, 1e-9, None)
    i = int(np.nanargmax(f1[:-1])) if len(th) else 0
    return float(th[i]) if len(th) else 0.5


# ---------------------------------------------------------------------------------------------- model object
@dataclass
class TraversabilityModel:
    estimator: object
    kind: str                      # "sklearn" | "torch"
    name: str
    scaler: object | None
    threshold: float
    rule: LabelRule
    card: dict = field(default_factory=dict)

    def proba(self, X: np.ndarray) -> np.ndarray:
        if self.kind == "torch":
            return self.estimator.predict_proba(self.scaler.transform(X))[:, 1]
        return self.estimator.predict_proba(X)[:, 1]

    def probability_grid(self, g, T) -> np.ndarray:
        cube = feature_stack(g, T)
        h, w, f = cube.shape
        X = cube.reshape(-1, f)
        ok = np.all(np.isfinite(X), axis=1)
        out = np.full(h * w, np.nan, np.float32)
        if ok.any():
            out[ok] = self.proba(X[ok])
        out = out.reshape(h, w)
        out[~np.isfinite(g.z)] = 1.0          # missing data is never assumed safe
        return out

    def save(self, path: Path = MODEL_PATH):
        import joblib
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        (path.parent / "model_card.json").write_text(json.dumps(self.card, indent=2, default=str), encoding="utf-8")


def load(path: Path = MODEL_PATH) -> TraversabilityModel | None:
    """Load the model saved by this app. joblib uses pickle: only files written by `train` under
    models/traversability are loaded — never user uploads."""
    path = Path(path)
    if path.resolve().parent != MODEL_DIR.resolve() or not path.is_file():
        return None
    try:
        import joblib
        m = joblib.load(path)
        return m if isinstance(m, TraversabilityModel) else None
    except Exception as e:  # noqa: BLE001
        log.error("model load failed: %s", e.__class__.__name__)
        return None


def card() -> dict | None:
    if CARD_PATH.is_file():
        try:
            return json.loads(CARD_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
    return None


# ---------------------------------------------------------------------------------------------- training
def build_dataset(g, T, rule: LabelRule, cfg: TrainConfig):
    cube = feature_stack(g, T)
    y = labels(g, T, rule)
    split, bid = block_split(g.shape, cfg, y)
    valid = np.isfinite(g.z) & np.all(np.isfinite(cube), axis=-1)
    X = cube[valid]
    return X, y[valid].astype(int), split[valid], bid[valid], split, y


def train(g, T, rule: LabelRule = LabelRule(), cfg: TrainConfig = TrainConfig(), progress=None,
          save: bool = True) -> tuple[TraversabilityModel, dict]:
    """Train all model families, select on validation, evaluate once on test. Returns (model, report)."""
    from sklearn.preprocessing import StandardScaler
    t0 = time.perf_counter()
    X, y, sp, _, split_grid, y_grid = build_dataset(g, T, rule, cfg)
    Xtr, ytr = X[sp == 0], y[sp == 0]
    Xva, yva = X[sp == 1], y[sp == 1]
    Xte, yte = X[sp == 2], y[sp == 2]
    rng = np.random.default_rng(cfg.seed)
    if len(ytr) > cfg.max_train_rows:                         # stratified subsample for speed
        pos, neg = np.flatnonzero(ytr == 1), np.flatnonzero(ytr == 0)
        k_pos = min(len(pos), cfg.max_train_rows // 2)
        sel = np.concatenate([rng.choice(pos, k_pos, replace=False),
                              rng.choice(neg, min(len(neg), cfg.max_train_rows - k_pos), replace=False)])
        Xtr, ytr = Xtr[sel], ytr[sel]
    pos_weight = float((ytr == 0).sum() / max(1, (ytr == 1).sum()))
    scaler = StandardScaler().fit(Xtr)
    results, fitted = [], {}
    for i, name in enumerate(cfg.models):
        if progress:
            progress(i / (len(cfg.models) + 1), name)
        est, label = _make(name, X.shape[1], pos_weight, cfg)
        t1 = time.perf_counter()
        if isinstance(est, tuple):                               # torch
            net = est[1].fit(scaler.transform(Xtr), ytr, scaler.transform(Xva), yva)
            m = TraversabilityModel(net, "torch", label, scaler, 0.5, rule)
        else:
            est.fit(Xtr, ytr)
            m = TraversabilityModel(est, "sklearn", label, None, 0.5, rule)
        pv = m.proba(Xva)
        m.threshold = best_threshold(yva, pv)
        val = metrics(yva, pv, m.threshold)
        results.append({"model": name, "name": label, "fit_s": round(time.perf_counter() - t1, 2), "val": val})
        fitted[name] = m
    best = max(results, key=lambda r: (r["val"]["f1"], r["val"]["pr_auc"]))
    model = fitted[best["model"]]
    # evaluate every family on test for transparency (selection was done on validation only)
    for r in results:
        r["test"] = metrics(yte, fitted[r["model"]].proba(Xte), fitted[r["model"]].threshold)
    # trivial baseline: always "traversable" and prevalence
    base = {"prevalence_test": float(yte.mean()), "always_traversable_f1": 0.0}
    # permutation importance of the selected model on a validation sample
    nimp = min(6000, len(yva))
    idx = rng.choice(len(yva), nimp, replace=False)

    from sklearn.metrics import average_precision_score
    Xs, ys = Xva[idx], yva[idx]
    base_ap = average_precision_score(ys, model.proba(Xs))
    imp_mean, imp_std = [], []
    for j in range(Xs.shape[1]):                               # permutation importance (drop in PR-AUC)
        drops = []
        for _ in range(3):
            Xp = Xs.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            drops.append(base_ap - average_precision_score(ys, model.proba(Xp)))
        imp_mean.append(np.mean(drops))
        imp_std.append(np.std(drops))
    importance = sorted(({"feature": f, "importance": float(v), "std": float(s)}
                         for f, v, s in zip(FEATURES, imp_mean, imp_std)),
                        key=lambda d: -d["importance"])
    history = getattr(model.estimator, "history", None)
    report = {
        "trained_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "dem_source": g.source, "dem_data_class": getattr(g.data_class, "value", str(g.data_class)),
        "label_rule": rule.text(), "label_origin": "rule-based weak supervision (not human annotation)",
        "features": FEATURES, "split": "spatial blocks %dx%d: %d test, %d val, rest train (seed %d)" % (
            cfg.blocks, cfg.blocks, cfg.n_test_blocks, cfg.n_val_blocks, cfg.seed),
        "rows": {"train": int(len(ytr)), "val": int(len(yva)), "test": int(len(yte))},
        "class_balance": {"train_pos": float(ytr.mean()), "val_pos": float(yva.mean()), "test_pos": float(yte.mean())},
        "results": results, "selected": best["name"], "selected_key": best["model"],
        "test": next(r["test"] for r in results if r["model"] == best["model"]),
        "baseline": base, "importance": importance, "history": history,
        "torch": torch_available(), "train_s": round(time.perf_counter() - t0, 1),
    }
    model.card = report
    if save:
        model.save()
    if progress:
        progress(1.0, "done")
    log.info("traversability model trained: %s test F1 %.3f", best["name"], report["test"]["f1"])
    return model, report
