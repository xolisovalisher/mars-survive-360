"""Unsupervised ML: K-Means terrain units trained on the active region (module 7/3)."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def train(features: dict[str, np.ndarray], k: int = 5, seed: int = 0, sample: int = 15000):
    names = list(features)
    X = np.stack([features[n].ravel() for n in names], 1)
    ok = np.all(np.isfinite(X), 1)
    rng = np.random.default_rng(seed)
    idx = rng.choice(np.where(ok)[0], size=min(sample, int(ok.sum())), replace=False)
    sc = StandardScaler().fit(X[idx])
    km = KMeans(n_clusters=k, n_init=4, random_state=seed).fit(sc.transform(X[idx]))
    sil = float(silhouette_score(sc.transform(X[idx][:3000]), km.labels_[:3000]))
    lab = np.full(X.shape[0], 255, np.uint8)
    lab[ok] = km.predict(sc.transform(X[ok]))
    cent = sc.inverse_transform(km.cluster_centers_)
    info = []
    for i in range(k):
        info.append({"unit": i, "share": float((lab == i).sum() / ok.sum()), **{n: float(cent[i, j]) for j, n in enumerate(names)}})
    _name(info)
    return lab.reshape(next(iter(features.values())).shape), info, {"silhouette": sil, "inertia": float(km.inertia_)}


def _name(info):
    left = list(range(len(info)))

    def take(key, rev, label):
        if not left or key not in info[0]:
            return
        i = (max if rev else min)(left, key=lambda j: info[j][key])
        info[i]["name"] = label
        left.remove(i)

    take("slope", True, "steep_slopes")
    take("roughness", True, "rough_blocky")
    take("tpi", True, "ridges_rims")
    take("tpi", False, "hollows")
    for i in sorted(left, key=lambda j: info[j].get("slope", 0)):
        info[i]["name"] = "smooth_plains" if not any(x.get("name") == "smooth_plains" for x in info) else "mixed"
