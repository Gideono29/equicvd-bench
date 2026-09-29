"""Run the benchmark: score, evaluate, bootstrap, and write tables/figures/report."""
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .metrics import calibration_deciles, crossfit_recalibrate, evaluate, ipcw, rao_wu_multipliers
from .scores import TOOLS, score_all
from .tables import flow_diagram, table1

ATTRIBUTES = ["sex", "race", "age_group", "income", "education"]
MIN_GAP_EVENTS = 10  # subgroups with fewer horizon events are reported but excluded from gap summaries
RECAL = " (recal)"


def run_bench(data_dir, out, B=200, horizon=10.0, min_g=0.10, weighted=True, ml=True, seed=20261101,
              recalibrate=True, exclude_oor=False, label="main"):
    """Evaluate all tools. `out` is the output directory for this run (scenario)."""
    t0 = time.time()
    data_dir, out = Path(data_dir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cohort_path = data_dir / "processed" / "cohort.csv.gz"
    df = pd.read_csv(cohort_path)
    rng = np.random.default_rng(seed)
    flow_extra = []
    if exclude_oor:
        df = df[df["oor_pce"] == 0]
        flow_extra.append(("Predictors within PCE valid ranges", len(df)))

    # Horizon eligibility: keep cycles whose censoring survival at the horizon is adequate
    _, _, g_h = ipcw(df, horizon)
    keep = sorted(c for c, g in g_h.items() if g >= min_g)
    dropped = sorted(set(g_h) - set(keep))
    df = df[df["cycle"].isin(keep)].reset_index(drop=True)
    y, w, _ = ipcw(df, horizon)
    flow_extra.append((f"Cycles with adequate {horizon:g}-y follow-up ({keep[0]} to {keep[-1]})", len(df)))
    print(f"[{label}] Horizon {horizon:g}y: cycles kept {keep[0]}..{keep[-1]} ({len(keep)}), dropped {dropped}; "
          f"n={len(df):,}, CVD deaths by horizon={int(y.sum())}", flush=True)

    sw = df["wt"].to_numpy(float) if weighted else np.ones(len(df))
    sw = sw / sw.mean()
    t1 = table1(df, y, sw)
    t1.to_csv(out / "table1.csv", index=False)
    flow_diagram(data_dir / "processed" / "cohort_flow.csv", flow_extra, int(y.sum()), out / "flow_diagram.png")

    preds = score_all(df)
    if recalibrate:
        for t in list(preds.columns):
            preds[t + RECAL] = crossfit_recalibrate(preds[t].to_numpy(), y, w, seed)
    importance = shapes = None
    if ml:
        print(f"[{label}] Cross-fitting explainable ML comparators ...", flush=True)
        mlp, importance, shapes = crossfit_ml(df, y, w, seed)
        preds = pd.concat([preds, mlp], axis=1)

    point = evaluate(preds, df, y, w, sw, ATTRIBUTES, MIN_GAP_EVENTS)

    print(f"[{label}] Bootstrap B={B} ({'Rao-Wu survey design' if weighted else 'iid'}) ...", flush=True)
    strata, psu = df["strata"].to_numpy(), df["psu"].to_numpy()
    reps = []
    for b in range(B):
        mult = rao_wu_multipliers(strata, psu, rng) if weighted else rng.multinomial(len(df), np.full(len(df), 1 / len(df)))
        r = evaluate(preds, df, y, w, sw * mult, ATTRIBUTES, MIN_GAP_EVENTS)
        r["rep"] = b
        reps.append(r)
        if (b + 1) % 50 == 0:
            print(f"  {b + 1}/{B}  ({time.time() - t0:.0f}s)", flush=True)
    key = ["tool", "attribute", "level", "metric"]
    boot = pd.concat(reps, ignore_index=True) if reps else pd.DataFrame(columns=key + ["value", "rep"])
    ci = boot.groupby(key)["value"].agg(
        lo=lambda v: np.nanpercentile(v, 2.5), hi=lambda v: np.nanpercentile(v, 97.5), se="std",
        n_rep=lambda v: int(np.isfinite(v).sum())).reset_index()
    res = point.merge(ci, on=key, how="left")
    # Gap statistics (max-min, max/min) are biased upward under resampling, so percentile intervals can
    # exclude the point estimate. Use basic (reflected) bootstrap intervals for them instead.
    gap = res["level"].str.startswith("GAP")
    lo_b, hi_b = 2 * res["value"] - res["hi"], 2 * res["value"] - res["lo"]
    floor = np.where(res["level"] == "GAP(max/min)", 1.0, 0.0)
    res["ci_method"] = np.where(gap, "basic", "percentile")
    res.loc[gap, "lo"] = np.maximum(lo_b[gap], floor[gap])
    res.loc[gap, "hi"] = hi_b[gap]
    res.to_csv(out / "metrics.csv", index=False)

    cal = pd.concat([calibration_deciles(preds[t].to_numpy(), y, w, sw).assign(tool=t) for t in preds.columns])
    cal.to_csv(out / "calibration_deciles.csv", index=False)
    preds.assign(SEQN=df["SEQN"], cycle=df["cycle"], y=y, ipcw=w).to_csv(out / "predictions.csv.gz", index=False)
    if importance is not None:
        importance.to_csv(out / "ml_gbm_permutation_importance.csv", index=False)
        shapes.to_csv(out / "ml_gam_shape_functions.csv", index=False)

    figs = ["flow_diagram.png"] + _figures(res, cal, out, horizon)
    manifest = {
        "equicvd_version": __version__, "scenario": label,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "args": dict(B=B, horizon=horizon, min_followup_prob=min_g, weighted=weighted, ml=ml, seed=seed,
                     recalibrate=recalibrate, exclude_out_of_range=exclude_oor),
        "cohort_sha256": hashlib.sha256(cohort_path.read_bytes()).hexdigest(),
        "cycles_kept": keep, "cycles_dropped": dropped, "G_horizon_by_cycle": {k: float(v) for k, v in g_h.items()},
        "n": int(len(df)), "horizon_events": int(y.sum()), "runtime_s": round(time.time() - t0, 1),
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=1))
    _report(res, manifest, importance, figs, out, t1)
    print(f"[{label}] Done in {time.time() - t0:.0f}s. Outputs in {out}", flush=True)
    return res


def crossfit_ml(df, y, w, seed):
    from .ml import crossfit
    return crossfit(df, y, w, seed)


def _built_for(tool):
    base = tool.replace(RECAL, "")
    if base in TOOLS:
        return TOOLS[base][1] + (" → recalibrated to CVD death" if tool.endswith(RECAL) else "")
    return "CVD death (trained here)"


def _get(res, tool, metric, attribute="Overall", level="All"):
    r = res[(res.tool == tool) & (res.metric == metric) & (res.attribute == attribute) & (res.level == level)]
    return r.iloc[0] if len(r) else None


def _fmt(r, pct=False, d=2):
    if r is None or not np.isfinite(r["value"]):
        return "–"
    f = (lambda v: f"{100 * v:.1f}") if pct else (lambda v: f"{v:.{d}f}")
    if pd.notna(r.get("lo")):
        return f"{f(r['value'])} ({f(r['lo'])}–{f(r['hi'])})"
    return f(r["value"])


def _figures(res, cal, out, horizon):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    tools = list(dict.fromkeys(res.tool))
    ncol = 4
    nrow = -(-len(tools) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 3.1 * nrow), squeeze=False)
    for ax, t in zip(axes.flat, tools):
        c = cal[cal.tool == t]
        m = max(c.expected.max(), c.observed.max()) * 1.1
        ax.plot([0, m], [0, m], color="#999", lw=0.8, ls="--")
        ax.plot(c.expected, c.observed, "o-", color="#2b6cb0", ms=3)
        ax.set_title(t, fontsize=9)
        ax.set_xlabel(f"Predicted {horizon:g}-y risk", fontsize=8)
        ax.set_ylabel(f"Observed {horizon:g}-y CVD death", fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in list(axes.flat)[len(tools):]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "calibration_deciles.png", dpi=150)
    plt.close(fig)

    # Relative O/E by race, sex and income for as-published tools and ML (recalibrated versions are in metrics.csv)
    ftools = [t for t in tools if not t.endswith(RECAL)]
    sub = res[(res.metric == "rel_OE") & res.attribute.isin(["sex", "race", "income"]) & ~res.level.str.startswith("GAP")]
    fig, ax = plt.subplots(figsize=(7, 0.19 * len(sub[sub.tool.isin(ftools)]) + 1.2))
    labels, ypos, yv = [], [], 0.0
    for t in ftools:
        for _, r in sub[sub.tool == t].iterrows():
            xerr = [[max(r.value - r.lo, 0)], [max(r.hi - r.value, 0)]] if pd.notna(r.lo) else None
            ax.errorbar(r.value, yv, xerr=xerr, fmt="o", ms=3, color="#2b6cb0", ecolor="#90b4dc")
            labels.append(f"{t} · {r.level}")
            ypos.append(yv)
            yv += 1
        yv += 0.6
    ax.set_yticks(ypos, labels, fontsize=6)
    ax.axvline(1, color="#999", lw=0.8, ls="--")
    ax.set_xscale("log")
    ticks = [0.25, 0.5, 1, 2, 4]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_xlabel("Relative O/E: subgroup O/E ÷ overall O/E (log scale, 95% CI)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out / "subgroup_relOE_forest.png", dpi=150)
    plt.close(fig)
    return ["calibration_deciles.png", "subgroup_relOE_forest.png"]


def _perf_table(res, tools, h):
    L = [f"| Tool | Target | Expected % | Observed % | O/E | Cal. slope | AUC | Scaled Brier | % ≥7.5% | TPR@7.5% |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for t in tools:
        L.append(f"| {t} | {_built_for(t)} | {_fmt(_get(res, t, 'expected'), pct=True)} "
                 f"| {_fmt(_get(res, t, 'observed'), pct=True)} | {_fmt(_get(res, t, 'OE'))} "
                 f"| {_fmt(_get(res, t, 'cal_slope'))} | {_fmt(_get(res, t, 'AUC'), d=3)} "
                 f"| {_fmt(_get(res, t, 'scaled_brier'), d=3)} | {_fmt(_get(res, t, 'pct_flagged_7.5'), pct=True)} "
                 f"| {_fmt(_get(res, t, 'TPR_7.5'), pct=True)} |")
    return L


def _report(res, man, importance, figs, out, t1):
    tools = list(dict.fromkeys(res.tool))
    pub = [t for t in tools if t.replace(RECAL, "") in TOOLS and not t.endswith(RECAL)]
    rec = [t for t in tools if t.endswith(RECAL)]
    mlt = [t for t in tools if t.startswith("ML-")]
    a = man["args"]
    h = a["horizon"]
    L = [f"# EquiCVD Bench — run report (v{man['equicvd_version']}, scenario: {man['scenario']})", "",
         f"Run {man['run_utc']} · horizon {h:g} y · B={a['B']} "
         f"{'Rao–Wu survey bootstrap' if a['weighted'] else 'iid bootstrap (unweighted)'} · seed {a['seed']}"
         + (" · out-of-range participants excluded" if a.get("exclude_out_of_range") else ""), "",
         "## 1. Evaluation cohort", "",
         f"- Cycles evaluated: {', '.join(man['cycles_kept'])}",
         f"- Cycles dropped (censoring survival G({h:g}y) < {a['min_followup_prob']}): "
         f"{', '.join(man['cycles_dropped']) or 'none'}",
         f"- Participants: {man['n']:,}; CVD deaths within horizon: {man['horizon_events']:,}", "",
         f"**Table 1.** Baseline characteristics ({'survey-weighted' if a['weighted'] else 'unweighted'} mean (SD) "
         "or %; n unweighted)", ""]
    cols = list(t1.columns)
    L += ["| " + " | ".join(cols) + " |", "|---" * len(cols) + "|"]
    L += ["| " + " | ".join(str(v) for v in row) + " |" for row in t1.itertuples(index=False)]
    L += ["", f"## 2a. Overall performance, as published (outcome: {h:g}-year CVD death, NHANES public-use LMF)", ""]
    L += _perf_table(res, pub + mlt, h)
    if rec:
        L += ["", "## 2b. Overall performance after logistic recalibration to CVD death (5-fold cross-fitted)", "",
              "Recalibration refits only an intercept and slope on each tool's logit, so ranking (AUC) is unchanged; "
              "it answers \"how fair is the tool once its absolute level is corrected for this outcome?\"", ""]
        L += _perf_table(res, rec, h)
    L += ["", "## 3. Subgroup calibration: relative O/E (subgroup O/E ÷ overall O/E; 1 = same as overall)", ""]
    for attr in ATTRIBUTES:
        levels = [l for l in dict.fromkeys(res[(res.attribute == attr) & ~res.level.str.startswith("GAP")].level)]
        L += [f"**{attr}**", "", "| Tool | " + " | ".join(levels) + " |", "|---" * (len(levels) + 1) + "|"]
        for t in pub + rec + mlt:
            L.append(f"| {t} | " + " | ".join(_fmt(_get(res, t, "rel_OE", attr, l)) for l in levels) + " |")
        ev = [_get(res, tools[0], "events", attr, l) for l in levels]
        L += ["| *events* | " + " | ".join(f"{int(e['value'])}" if e is not None else "–" for e in ev) + " |", ""]
    L += ["## 4. Fairness gaps across subgroups (95% basic bootstrap CI)", "",
          f"Subgroups with < {MIN_GAP_EVENTS} horizon events are excluded from gap summaries.", "",
          "| Tool | Attribute | O/E max÷min | AUC max−min | TPR@7.5% max−min | FPR@7.5% max−min |", "|---|---|---|---|---|---|"]
    for t in pub + rec + mlt:
        for attr in ATTRIBUTES:
            L.append(f"| {t} | {attr} | {_fmt(_get(res, t, 'OE', attr, 'GAP(max/min)'))} "
                     f"| {_fmt(_get(res, t, 'AUC', attr, 'GAP(max-min)'), d=3)} "
                     f"| {_fmt(_get(res, t, 'TPR_7.5', attr, 'GAP(max-min)'), pct=True)} "
                     f"| {_fmt(_get(res, t, 'FPR_7.5', attr, 'GAP(max-min)'), pct=True)} |")
    if importance is not None:
        L += ["", "## 5. Explainability (ML-GBM, out-of-fold permutation importance, drop in AUC)", "",
              "| Feature | ΔAUC (mean ± SD across folds) |", "|---|---|"]
        L += [f"| {r.feature} | {r.auc_drop_mean:.4f} ± {r.auc_drop_sd_across_folds:.4f} |" for r in importance.itertuples()]
        L += ["", "ML-GAM partial log-odds shape functions: `ml_gam_shape_functions.csv`."]
    L += ["", "## 6. Interpretation notes and known limitations", "",
          "- **Outcome mismatch.** Public-use LMF supports CVD *mortality* (UCOD 001 heart disease, 005 cerebrovascular), "
          "not incident ASCVD. O/E < 1 for as-published PCE/PREVENT is expected by construction; subgroup *relative* "
          "O/E, the recalibrated results, and the gap metrics are the fairness-relevant quantities. ML comparators are "
          "trained on this outcome and so bound what is achievable here.",
          "- **Competing risks.** Non-CVD deaths before the horizon are known non-events (cumulative-incidence estimand).",
          "- **Censoring.** IPCW with Kaplan–Meier censoring estimated within cycle.",
          "- **What the CIs cover.** IPCW weights, recalibration fits and ML fits are held fixed across bootstrap "
          "replicates, so CIs reflect sampling of participants/PSUs but not model-fitting variability. Cross-fitting "
          "(5 folds) removes in-sample optimism from the point estimates.",
          "- **Gap CIs** use basic (reflected) bootstrap intervals because max/min statistics are biased upward under "
          "resampling; all other CIs are percentile intervals.",
          "- **Age-group threshold gaps** (TPR/FPR) mostly reflect that age is a dominant predictor, not unfairness.",
          "- **Predictors.** Lipid-lowering medication (BPQ100D) proxies statin use; eGFR is CKD-EPI 2021 on "
          "standardized creatinine; out-of-range inputs are clipped to each equation's valid range unless excluded.",
          "- **Public-use perturbation.** NCHS perturbs some follow-up/cause fields in public-use LMF; results should be "
          "confirmed against restricted-use files before clinical interpretation."]
    if figs:
        L += ["", "## Figures", ""] + [f"![{f}]({f})" for f in figs]
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
