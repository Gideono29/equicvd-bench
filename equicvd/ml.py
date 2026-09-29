"""Explainable ML comparators, cross-fitted on the benchmark outcome with IPCW sample weights.

- ML-GAM: additive logistic model with cubic B-splines (shape functions exported).
- ML-GBM: gradient boosting with monotonic constraints (permutation importances exported).
Race/ethnicity is deliberately not a feature (race-free, like PREVENT).
"""
import os

import numpy as np
import pandas as pd

try:  # joblib shells out to `wmic` (absent on recent Windows) and prints a traceback; seed its cache instead
    from joblib.externals.loky.backend import context as _loky_ctx
    if _loky_ctx.physical_cores_cache is None:
        _loky_ctx.physical_cores_cache = os.cpu_count() or 1
except (ImportError, AttributeError):
    pass

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer

CONT = ["age", "tc", "hdl", "sbp", "bmi", "egfr"]
BIN = ["female", "bptx", "smoker", "diabetes", "statin"]
FEATURES = CONT + BIN
MONOTONE = {"age": 1, "sbp": 1, "smoker": 1, "diabetes": 1, "egfr": -1}


def _gam():
    ct = ColumnTransformer([("spl", SplineTransformer(n_knots=5, degree=3, extrapolation="linear"), CONT)],
                           remainder="passthrough")
    return make_pipeline(ct, LogisticRegression(C=0.5, max_iter=5000))


def _gbm(seed):
    return HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50, l2_regularization=1.0,
        monotonic_cst=[MONOTONE.get(f, 0) for f in FEATURES], early_stopping=False, random_state=seed)


def _fit(model, X, y, w):
    step = model.steps[-1][0] + "__sample_weight" if hasattr(model, "steps") else "sample_weight"
    return model.fit(X, y, **{step: w})


def crossfit(df, y, w, seed=0, folds=5):
    """Out-of-fold predictions for every participant, plus explanation tables."""
    X = df[FEATURES].astype(float)
    preds = {"ML-GAM": np.zeros(len(df)), "ML-GBM": np.zeros(len(df))}
    imps = []
    skf = StratifiedKFold(folds, shuffle=True, random_state=seed)
    for k, (tr, te) in enumerate(skf.split(X, y)):
        fit = tr[w[tr] > 0]
        for name, mk in (("ML-GAM", _gam), ("ML-GBM", lambda: _gbm(seed + k))):
            m = _fit(mk(), X.iloc[fit], y[fit], w[fit])
            preds[name][te] = m.predict_proba(X.iloc[te])[:, 1]
            if name == "ML-GBM":
                ev = te[w[te] > 0]
                pi = permutation_importance(m, X.iloc[ev], y[ev], sample_weight=w[ev], scoring="roc_auc",
                                            n_repeats=5, random_state=seed)
                imps.append(pd.Series(pi.importances_mean, index=FEATURES, name=k))
    importance = (pd.concat(imps, axis=1).agg(["mean", "std"], axis=1)
                  .rename(columns={"mean": "auc_drop_mean", "std": "auc_drop_sd_across_folds"})
                  .sort_values("auc_drop_mean", ascending=False).rename_axis("feature").reset_index())

    # GAM shape functions from a full-data fit: partial log-odds centered at the median
    known = w > 0
    gam = _fit(_gam(), X[known], y[known], w[known])
    ref = X.median()
    shapes = []
    for f in CONT:
        grid = np.linspace(*np.percentile(X[f], [1, 99]), 50)
        Xg = pd.DataFrame([ref] * len(grid))
        Xg[f] = grid
        lo = gam.decision_function(Xg) - gam.decision_function(pd.DataFrame([ref]))[0]
        shapes += [{"feature": f, "value": v, "partial_log_odds": l} for v, l in zip(grid, lo)]
    coef = gam.steps[-1][1].coef_[0][-len(BIN):]
    shapes += [{"feature": f, "value": 1.0, "partial_log_odds": c} for f, c in zip(BIN, coef)]
    return pd.DataFrame(preds, index=df.index), importance, pd.DataFrame(shapes)
