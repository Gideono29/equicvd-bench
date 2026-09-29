"""Checks of the evaluation primitives against simple closed-form or scikit-learn references."""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from equicvd.metrics import censoring_km, crossfit_recalibrate, ipcw, rao_wu_multipliers, weighted_auc


def test_weighted_auc_matches_sklearn_with_ties():
    rng = np.random.default_rng(1)
    p = np.round(rng.random(500), 2)
    y = (rng.random(500) < p).astype(int)
    w = rng.random(500) + 0.5
    assert weighted_auc(p, y, w) == pytest.approx(roc_auc_score(y, p, sample_weight=w), abs=1e-12)


def test_no_censoring_gives_unit_weights():
    t = np.array([1.0, 2.0, 12.0, 15.0])
    e = np.array([1, 2, 1, 0])  # the only censoring is after the horizon
    g_minus, g_h = censoring_km(t, e, 10.0)
    assert g_h == 1.0 and np.all(g_minus == 1.0)


def test_ipcw_recovers_cumulative_incidence_under_random_censoring():
    rng = np.random.default_rng(7)
    n = 40000
    t_cvd, t_oth = rng.exponential(40, n), rng.exponential(30, n)
    c = rng.uniform(5, 25, n)
    t_ev = np.minimum(t_cvd, t_oth)
    time = np.minimum(t_ev, c)
    event = np.where(t_ev <= c, np.where(t_cvd <= t_oth, 1, 2), 0)
    df = pd.DataFrame({"time": time, "event": event, "cycle": "x"})
    y, w, _ = ipcw(df, 10.0)
    truth = np.mean((t_cvd <= 10) & (t_cvd <= t_oth))
    assert np.sum(w * y) / np.sum(w) == pytest.approx(truth, abs=0.006)


def test_rao_wu_multipliers_average_one():
    rng = np.random.default_rng(3)
    strata = np.repeat(np.arange(30), 40)
    psu = np.tile(np.repeat([1, 2], 20), 30)
    m = np.mean([rao_wu_multipliers(strata, psu, rng).mean() for _ in range(300)])
    assert m == pytest.approx(1.0, abs=0.02)


def test_recalibration_fixes_scaled_risk():
    rng = np.random.default_rng(11)
    true = rng.uniform(0.005, 0.2, 20000)
    y = (rng.random(20000) < true).astype(int)
    recal = crossfit_recalibrate(np.clip(true * 4, 0, 0.95), y, np.ones_like(true))
    assert recal.mean() == pytest.approx(y.mean(), rel=0.05)
