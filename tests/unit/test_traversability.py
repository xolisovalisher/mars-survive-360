"""Supervised traversability model: data protocol, learning skill, integration into routing."""
import numpy as np
import pytest

from mars_survive.ai import traversability as TV


@pytest.fixture(scope="module")
def trained(engine, tmp_path_factory):
    cfg = TV.TrainConfig(models=("logistic", "gboost", "mlp"), mlp_epochs=8, max_train_rows=30_000)
    return TV.train(engine.g, engine.T, TV.LabelRule(), cfg, save=False)


def test_features_never_contain_the_cell_itself(engine):
    """Changing a cell's own slope/roughness must not change its features (no label leakage)."""
    import copy
    T2 = copy.copy(engine.T)
    T2.slope = engine.T.slope.copy()
    T2.roughness = engine.T.roughness.copy()
    r, c = 150, 160
    T2.slope[r, c] += 30.0
    T2.roughness[r, c] += 5.0
    a = TV.feature_stack(engine.g, engine.T)[r, c]
    b = TV.feature_stack(engine.g, T2)[r, c]
    ring = [TV.FEATURES.index(f) for f in ("slope_ring_mean", "slope_ring_max", "rough_ring_mean", "rough_ring_max")]
    assert np.allclose(a[ring], b[ring])
    # ...while the label of that cell does change
    assert TV.labels(engine.g, T2)[r, c] == 1


def test_spatial_split_is_disjoint_and_covers(engine):
    y = TV.labels(engine.g, engine.T)
    split, bid = TV.block_split(engine.g.shape, TV.TrainConfig(), y)
    for b in np.unique(bid):
        assert len(np.unique(split[bid == b])) == 1          # a block belongs to exactly one set
    assert set(np.unique(split)) == {0, 1, 2}
    for s in (0, 1, 2):
        assert len(np.unique(y[split == s])) == 2             # both classes in every set


def test_nodata_is_labelled_not_traversable(engine):
    y = TV.labels(engine.g, engine.T)
    nod = ~np.isfinite(engine.g.z)
    assert nod.any() and y[nod].all()


def test_model_learns_beyond_baselines(trained):
    model, rep = trained
    te = rep["test"]
    prev = rep["baseline"]["prevalence_test"]
    assert te["pr_auc"] > prev + 0.3                         # far above a random classifier
    assert te["f1"] > 0.6 and te["roc_auc"] > 0.9
    logi = next(r for r in rep["results"] if r["model"] == "logistic")["test"]["pr_auc"]
    assert te["pr_auc"] >= logi - 0.02                       # selected model not worse than the linear baseline
    assert {r["model"] for r in rep["results"]} == {"logistic", "gboost", "mlp"}
    assert rep["importance"][0]["importance"] > 0


def test_metrics_are_consistent(trained):
    _, rep = trained
    cm = rep["test"]["confusion"]
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    assert abs(rep["test"]["precision"] - tp / (tp + fp)) < 1e-9
    assert abs(rep["test"]["recall"] - tp / (tp + fn)) < 1e-9
    assert sum(cm.values()) == rep["rows"]["test"]


def test_probability_grid_and_routing(engine, trained):
    from mars_survive.integration.mission import MissionParams
    model, _ = trained
    p = model.probability_grid(engine.g, engine.T)
    assert p.shape == engine.g.shape
    assert np.all(p[~np.isfinite(engine.g.z)] == 1.0)          # missing data never safe
    assert np.nanmin(p) >= 0 and np.nanmax(p) <= 1
    engine.ml_prob(model)                                     # inject the trained model
    a = engine.plan_four((18.4447, 77.4508), (18.455, 77.405), MissionParams(ml_blend=0.0))["balanced"]
    b = engine.plan_four((18.4447, 77.4508), (18.455, 77.405), MissionParams(ml_blend=1.0))["balanced"]
    assert a.found and b.found
    # with blend = 1 the hazard used along the path is the model probability
    assert b.summary()["hazard_mean"] <= 1.0


def test_torch_mlp_if_available(engine):
    if not TV.torch_available():
        pytest.skip("PyTorch not installed")
    X = np.random.default_rng(0).normal(size=(2000, 3)).astype(np.float32)
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    m = TV.TorchMLP(3, epochs=15, seed=0).fit(X, y, X, y)
    acc = ((m.predict_proba(X)[:, 1] > 0.5) == y).mean()
    assert acc > 0.95 and m.history[-1]["train_loss"] < m.history[0]["train_loss"]


def test_save_load_roundtrip(engine, trained, tmp_path, monkeypatch):
    model, _ = trained
    monkeypatch.setattr(TV, "MODEL_DIR", tmp_path)
    path = tmp_path / "model.joblib"
    model.save(path)
    m2 = TV.load(path)
    X = TV.feature_stack(engine.g, engine.T).reshape(-1, len(TV.FEATURES))[:500]
    X = X[np.all(np.isfinite(X), axis=1)]
    assert np.allclose(model.proba(X), m2.proba(X))
    assert TV.load(tmp_path.parent / "elsewhere.joblib") is None   # only the app's own model folder
