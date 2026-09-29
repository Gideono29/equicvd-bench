"""Manuscript tables and figures: Table 1 (baseline characteristics) and the cohort flow diagram."""
import numpy as np
import pandas as pd

CONTINUOUS = [("Age, y", "age"), ("Total cholesterol, mg/dL", "tc"), ("HDL cholesterol, mg/dL", "hdl"),
              ("Systolic BP, mmHg", "sbp"), ("BMI, kg/m²", "bmi"), ("eGFR, mL/min/1.73m²", "egfr")]
BINARY = [("Female", lambda d: d["female"] == 1), ("Current smoking", lambda d: d["smoker"] == 1),
          ("Diabetes", lambda d: d["diabetes"] == 1), ("BP-lowering medication", lambda d: d["bptx"] == 1),
          ("Lipid-lowering medication", lambda d: d["statin"] == 1),
          ("Income-to-poverty ratio < 1.3", lambda d: d["income"] == "PIR<1.3"),
          ("Less than high school", lambda d: d["education"] == "<HS")]
RACE_ORDER = ["NH White", "NH Black", "Mexican American", "Other Hispanic", "Other/Multiracial"]


def _col(d, y, sw):
    out = {"Participants, n": f"{len(d):,}", "CVD deaths within horizon, n": f"{int(y.sum()):,}"}
    for label, v in CONTINUOUS:
        x = d[v].to_numpy(float)
        m = np.average(x, weights=sw)
        sd = np.sqrt(np.average((x - m) ** 2, weights=sw))
        out[label] = f"{m:.1f} ({sd:.1f})"
    for label, f in BINARY:
        x = f(d).to_numpy(float)
        known = d["income"].notna().to_numpy() if "poverty" in label else np.ones(len(d), bool)
        out[label + ", %"] = f"{100 * np.average(x[known], weights=sw[known]):.1f}"
    return out


def table1(df, y, sw):
    cols = {"Characteristic": None, "Overall": _col(df, y, sw)}
    for r in RACE_ORDER:
        m = (df["race"] == r).to_numpy()
        if m.any():
            cols[r] = _col(df[m], y[m], sw[m])
    rows = list(cols["Overall"].keys())
    return pd.DataFrame({"Characteristic": rows, **{k: [v[r] for r in rows] for k, v in cols.items() if v}})


def flow_diagram(flow_csv, extra_steps, events, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    flow = pd.read_csv(flow_csv)
    steps = list(zip(flow["step"], flow["n"])) + list(extra_steps)
    fig, ax = plt.subplots(figsize=(7.5, 1.05 * len(steps) + 0.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(-len(steps) - 0.2, 0.8)
    ax.axis("off")
    prev = None
    for i, (label, n) in enumerate(steps):
        yv = -i
        ax.text(3.2, yv, f"{label}\nn = {n:,}", ha="center", va="center", fontsize=8,
                bbox=dict(boxstyle="round,pad=0.4", fc="#eef4fb", ec="#2b6cb0", lw=0.8))
        if prev is not None:
            ax.annotate("", xy=(3.2, yv + 0.33), xytext=(3.2, yv + 0.67),
                        arrowprops=dict(arrowstyle="->", color="#555", lw=0.8))
            ax.text(7.2, yv + 0.5, f"Excluded n = {prev - n:,}", ha="center", va="center", fontsize=7,
                    bbox=dict(boxstyle="round,pad=0.3", fc="#f7f7f7", ec="#999", lw=0.6))
        prev = n
    ax.text(3.2, -len(steps) + 0.1, f"Analytic sample · CVD deaths within horizon = {events:,}", ha="center",
            fontsize=8, style="italic")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
