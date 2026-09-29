"""Pre-specified sensitivity analyses, each a full benchmark run, plus a side-by-side summary."""
from pathlib import Path

import numpy as np
import pandas as pd

from .bench import run_bench

SCENARIOS = {
    "main": dict(),
    "unweighted": dict(weighted=False),
    "exclude_out_of_range": dict(exclude_oor=True),
    "horizon_5y": dict(horizon=5.0),
}
SUMMARY = [("Overall", "All", "OE", "O/E"), ("Overall", "All", "AUC", "AUC"),
           ("Overall", "All", "cal_slope", "Cal. slope"),
           ("race", "NH Black", "rel_OE", "Rel. O/E NH Black"), ("income", "PIR<1.3", "rel_OE", "Rel. O/E PIR<1.3"),
           ("race", "GAP(max/min)", "OE", "Race O/E max÷min"), ("income", "GAP(max/min)", "OE", "Income O/E max÷min")]


def run_sensitivity(data_dir, out_dir, B=200, seed=20261101, ml=True, scenarios=None):
    out_dir = Path(out_dir) / "sensitivity"
    results = {}
    for name in scenarios or SCENARIOS:
        results[name] = run_bench(data_dir, out_dir / name, B=B, seed=seed, ml=ml, label=name, **SCENARIOS[name])

    rows = []
    for name, res in results.items():
        for tool in dict.fromkeys(res.tool):
            row = {"scenario": name, "tool": tool}
            for attr, lev, met, label in SUMMARY:
                r = res[(res.tool == tool) & (res.attribute == attr) & (res.level == lev) & (res.metric == met)]
                if len(r):
                    r = r.iloc[0]
                    row[label] = r.value
                    row[label + " lo"], row[label + " hi"] = r.lo, r.hi
            rows.append(row)
    summ = pd.DataFrame(rows)
    summ.to_csv(out_dir / "sensitivity_summary.csv", index=False)

    L = ["# EquiCVD Bench — sensitivity analyses", "",
         "| Scenario | What changes |", "|---|---|",
         "| main | 10-y horizon, survey-weighted, out-of-range inputs clipped |",
         "| unweighted | ignores NHANES weights/design (iid bootstrap) |",
         "| exclude_out_of_range | drops participants outside PCE input ranges instead of clipping |",
         "| horizon_5y | 5-y CVD death; admits 2011–2014 cycles. Tools still output 10-y risk, so read relative "
         "O/E and gaps, not absolute O/E |", ""]
    for label in [s[3] for s in SUMMARY]:
        L += [f"**{label}**", "", "| Tool | " + " | ".join(results) + " |", "|---" * (len(results) + 1) + "|"]
        for tool in dict.fromkeys(summ.tool):
            cells = []
            for name in results:
                r = summ[(summ.scenario == name) & (summ.tool == tool)]
                if len(r) and label in r and np.isfinite(r.iloc[0][label]):
                    r = r.iloc[0]
                    cells.append(f"{r[label]:.2f} ({r[label + ' lo']:.2f}–{r[label + ' hi']:.2f})")
                else:
                    cells.append("–")
            L.append(f"| {tool} | " + " | ".join(cells) + " |")
        L.append("")
    (out_dir / "sensitivity_report.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Sensitivity summary -> {out_dir / 'sensitivity_report.md'}")
    return summ
