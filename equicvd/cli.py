"""Command-line entry point: python -m equicvd.cli {download,cohort,bench}."""
import argparse
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 1))
warnings.filterwarnings("ignore", message="Could not find the number of physical cores")

from .config import DEFAULT_DATA_DIR, DEFAULT_OUT_DIR


def main(argv=None):
    p = argparse.ArgumentParser(prog="equicvd", description="EquiCVD Bench")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="fetch NHANES 1999-2018 XPT files + 2019 public-use LMF")
    d.add_argument("--jobs", type=int, default=4)

    c = sub.add_parser("cohort", help="build the analytic cohort")
    c.add_argument("--range-policy", choices=["clip", "exclude"], default="clip",
                   help="out-of-range predictors: clip to each equation's valid range (default) or exclude")

    b = sub.add_parser("bench", help="score, evaluate calibration/discrimination/fairness with bootstrap CIs")
    b.add_argument("-B", "--bootstrap", type=int, default=200)
    b.add_argument("--horizon", type=float, default=10.0, help="prediction horizon, years")
    b.add_argument("--min-followup-prob", type=float, default=0.10,
                   help="drop cycles whose censoring survival G(horizon) is below this")
    b.add_argument("--unweighted", action="store_true", help="ignore NHANES survey design")
    b.add_argument("--no-ml", action="store_true", help="skip the explainable-ML comparators")
    b.add_argument("--no-recal", action="store_true", help="skip cross-fitted recalibrated versions of each tool")
    b.add_argument("--exclude-out-of-range", action="store_true",
                   help="drop participants outside PCE input ranges instead of clipping")
    b.add_argument("--seed", type=int, default=20261101)
    b.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)

    s = sub.add_parser("sensitivity", help="run pre-specified sensitivity scenarios and summarise")
    s.add_argument("-B", "--bootstrap", type=int, default=200)
    s.add_argument("--scenarios", nargs="+", default=None,
                   help="subset of: main unweighted exclude_out_of_range horizon_5y")
    s.add_argument("--no-ml", action="store_true")
    s.add_argument("--seed", type=int, default=20261101)
    s.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)

    a = p.parse_args(argv)
    if a.cmd == "download":
        from .download import download_all
        res = download_all(a.data_dir, jobs=a.jobs)
        return 1 if any(r["status"] == "failed" for r in res) else 0
    if a.cmd == "cohort":
        from .cohort import build_cohort
        build_cohort(a.data_dir, range_policy=a.range_policy)
        return 0
    if a.cmd == "bench":
        from .bench import run_bench
        run_bench(a.data_dir, a.out_dir / "bench", B=a.bootstrap, horizon=a.horizon, min_g=a.min_followup_prob,
                  weighted=not a.unweighted, ml=not a.no_ml, seed=a.seed, recalibrate=not a.no_recal,
                  exclude_oor=a.exclude_out_of_range)
        return 0
    if a.cmd == "sensitivity":
        from .sensitivity import run_sensitivity
        run_sensitivity(a.data_dir, a.out_dir, B=a.bootstrap, seed=a.seed, ml=not a.no_ml, scenarios=a.scenarios)
        return 0


if __name__ == "__main__":
    sys.exit(main())
