"""Censoring-aware, survey-weighted calibration, discrimination and fairness metrics.

Outcome: CVD death within `horizon` years, with non-CVD death as a competing event. Status at the horizon is
known for anyone who died before it or was followed past it; administratively censored participants are
handled by inverse probability of censoring weights (IPCW), with the censoring distribution estimated by
Kaplan-Meier within NHANES cycle (censoring is administrative at 2019-12-31, so it depends on exam date).
The IPCW-weighted mean of the binary outcome is a consistent estimate of the cause-specific cumulative incidence.
"""
import numpy as np
import pandas as pd

THRESHOLDS = (0.075, 0.20)


def censoring_km(time, event, horizon):
    """Return G(t-) at each subject's min(time, horizon) evaluation point and G(horizon)."""
    cens = event == 0
    u = np.unique(time[cens])
    if len(u) == 0:
        return np.ones(len(time)), 1.0
    st = np.sort(time)
    n_risk = len(time) - np.searchsorted(st, u, side="left")
    d = np.bincount(np.searchsorted(u, time[cens]), minlength=len(u))
    surv = np.cumprod(1 - d / n_risk)
    k_minus = np.searchsorted(u, np.minimum(time, horizon), side="left")  # censorings strictly before t
    g_minus = np.where(k_minus > 0, surv[np.maximum(k_minus - 1, 0)], 1.0)
    kh = np.searchsorted(u, horizon, side="right")
    return g_minus, (surv[kh - 1] if kh > 0 else 1.0)


def ipcw(df, horizon, strata_col="cycle"):
    """Binary horizon outcome y, IPCW weight w, and per-stratum G(horizon)."""
    y = ((df["event"] == 1) & (df["time"] <= horizon)).to_numpy(int)
    w = np.zeros(len(df))
    g_h = {}
    for s, idx in df.groupby(strata_col).indices.items():
        t, e = df["time"].to_numpy()[idx], df["event"].to_numpy()[idx]
        g_minus, gh = censoring_km(t, e, horizon)
        g_h[s] = gh
        died = (e != 0) & (t <= horizon)
        past = t > horizon
        wi = np.zeros(len(idx))
        wi[died] = 1 / g_minus[died]
        if gh > 0:
            wi[past] = 1 / gh
        w[idx] = wi
    return y, w, g_h


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def weighted_logistic(x, y, w, offset=None, iters=25):
    """Weighted logistic regression y ~ a + b*x (or y ~ a + offset). Returns (a, b)."""
    X = np.column_stack([np.ones_like(x), x]) if offset is None else np.ones((len(x), 1))
    off = np.zeros_like(x) if offset is None else offset
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ beta + off, -35, 35)
        mu = 1 / (1 + np.exp(-eta))
        g = X.T @ (w * (y - mu))
        H = (X * (w * mu * (1 - mu))[:, None]).T @ X
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            return (np.nan, np.nan)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return (beta[0], beta[1]) if offset is None else (beta[0], np.nan)


def crossfit_recalibrate(p, y, w, seed=0, folds=5):
    """Logistic recalibration (intercept + slope on logit p) fitted with IPCW weights, out-of-fold."""
    from sklearn.model_selection import StratifiedKFold
    lp = _logit(p)
    out = np.empty(len(p))
    for tr, te in StratifiedKFold(folds, shuffle=True, random_state=seed).split(lp, y):
        k = tr[w[tr] > 0]
        a, b = weighted_logistic(lp[k], y[k], w[k] / w[k].mean())
        out[te] = 1 / (1 + np.exp(-(a + b * lp[te])))
    return out


def weighted_auc(p, y, w):
    case, ctrl = w * y, w * (1 - y)
    if case.sum() <= 0 or ctrl.sum() <= 0:
        return np.nan
    order = np.argsort(p, kind="mergesort")
    ps, cs, ks = p[order], case[order], ctrl[order]
    uniq, start = np.unique(ps, return_index=True)
    c_case = np.add.reduceat(cs, start)
    c_ctrl = np.add.reduceat(ks, start)
    below = np.cumsum(c_ctrl) - c_ctrl
    return float(np.sum(c_case * (below + 0.5 * c_ctrl)) / (cs.sum() * ks.sum()))


def group_metrics(p, y, w, sw):
    """Metrics for one tool in one group. sw = survey (or bootstrap) weight; w = IPCW."""
    W = sw * w
    known = W > 0
    pk, yk, Wk = p[known], y[known], W[known]
    if Wk.sum() == 0 or sw.sum() == 0:
        return {}
    obs = float(np.sum(Wk * yk) / Wk.sum())
    exp_ = float(np.sum(sw * p) / sw.sum())
    lp = _logit(pk)
    citl, _ = weighted_logistic(lp, yk, Wk / Wk.mean(), offset=lp)
    a, b = weighted_logistic(lp, yk, Wk / Wk.mean())
    brier = float(np.sum(Wk * (yk - pk) ** 2) / Wk.sum())
    out = {
        "n": float((sw > 0).sum()), "events": float(yk[Wk > 0].sum()),
        "observed": obs, "expected": exp_, "OE": obs / exp_ if exp_ > 0 else np.nan,
        "cal_intercept": citl, "cal_slope": b, "AUC": weighted_auc(pk, yk, Wk),
        "brier": brier, "scaled_brier": 1 - brier / (obs * (1 - obs)) if 0 < obs < 1 else np.nan,
    }
    for t in THRESHOLDS:
        flag_all = p >= t
        flag = pk >= t
        pos, neg = np.sum(Wk * yk), np.sum(Wk * (1 - yk))
        tag = f"{t * 100:g}"
        out[f"pct_flagged_{tag}"] = float(np.sum(sw * flag_all) / sw.sum())
        out[f"TPR_{tag}"] = float(np.sum(Wk * yk * flag) / pos) if pos > 0 else np.nan
        out[f"FPR_{tag}"] = float(np.sum(Wk * (1 - yk) * flag) / neg) if neg > 0 else np.nan
    return out


GAP_METRICS = ["OE", "AUC", "cal_slope", "TPR_7.5", "FPR_7.5", "pct_flagged_7.5"]


def evaluate(preds: pd.DataFrame, df: pd.DataFrame, y, w, sw, attributes, min_events=0):
    """Long table: tool x attribute x level x metric, plus fairness-gap rows (attribute-level)."""
    rows = []
    groups = [("Overall", "All", np.ones(len(df), bool))]
    for a in attributes:
        vals = df[a].to_numpy()
        for lev in sorted(pd.unique(vals[pd.notna(vals)]).tolist()):
            groups.append((a, str(lev), vals == lev))
    for tool in preds.columns:
        p = preds[tool].to_numpy(float)
        overall_oe = None
        per_attr = {}
        for attr, lev, m in groups:
            g = group_metrics(p[m], y[m], w[m], sw[m])
            if not g:
                continue
            if attr == "Overall":
                overall_oe = g["OE"]
            g["rel_OE"] = g["OE"] / overall_oe if overall_oe else np.nan
            for k, v in g.items():
                rows.append((tool, attr, lev, k, v))
            if attr != "Overall" and g["events"] >= min_events:
                per_attr.setdefault(attr, []).append(g)
        for attr, gs in per_attr.items():
            if len(gs) < 2:
                continue
            for mname in GAP_METRICS:
                vals = np.array([g[mname] for g in gs], float)
                vals = vals[np.isfinite(vals)]
                if len(vals) >= 2:
                    rows.append((tool, attr, "GAP(max-min)", mname, float(vals.max() - vals.min())))
            oes = np.array([g["OE"] for g in gs], float)
            oes = oes[np.isfinite(oes) & (oes > 0)]
            if len(oes) >= 2:
                rows.append((tool, attr, "GAP(max/min)", "OE", float(oes.max() / oes.min())))
    return pd.DataFrame(rows, columns=["tool", "attribute", "level", "metric", "value"])


def calibration_deciles(p, y, w, sw, bins=10):
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    k = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    W = sw * w
    out = []
    for b in range(len(edges) - 1):
        m = k == b
        if W[m].sum() > 0:
            out.append({"bin": b + 1, "n": int(m.sum()), "expected": float(np.sum(sw[m] * p[m]) / sw[m].sum()),
                        "observed": float(np.sum(W[m] * y[m]) / W[m].sum())})
    return pd.DataFrame(out)


def rao_wu_multipliers(strata, psu, rng):
    """Rao-Wu rescaling bootstrap: resample n_h-1 PSUs within each stratum; returns per-person multipliers."""
    mult = np.zeros(len(strata))
    for s in np.unique(strata):
        in_s = strata == s
        psus = np.unique(psu[in_s])
        n_h = len(psus)
        if n_h < 2:
            mult[in_s] = 1.0
            continue
        draws = rng.choice(psus, size=n_h - 1, replace=True)
        counts = {q: (draws == q).sum() for q in psus}
        for q in psus:
            mult[in_s & (psu == q)] = counts[q] * n_h / (n_h - 1)
    return mult
