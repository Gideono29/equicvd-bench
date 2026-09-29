# EquiCVD Bench

Open benchmark of **calibration and subgroup fairness** of U.S. cardiovascular risk tools on
NHANES 1999–2018 with the NCHS 2019 public-use linked mortality files.

Maintainer: Gideon Owusu, Michigan Technological University
([ORCID 0009-0000-0540-7449](https://orcid.org/0009-0000-0540-7449))

| Tool | Reference | Predicts |
|---|---|---|
| PCE | Goff et al., *Circulation* 2014 | 10-y hard ASCVD |
| PCE-revised | Yadlowsky et al., *Ann Intern Med* 2018 | 10-y hard ASCVD |
| PREVENT-CVD / -ASCVD (base) | Khan et al., *Circulation* 2024 | 10-y total CVD / ASCVD |
| Framingham-office (non-laboratory, BMI) | D'Agostino et al., *Circulation* 2008 | 10-y general CVD |
| ML-GAM, ML-GBM (explainable ML) | this benchmark, cross-fitted | 10-y CVD death |

## Quick start

```bash
pip install -e .[test]
python -m equicvd.cli download      # ~117 files, ~250 MB, from wwwn.cdc.gov and ftp.cdc.gov (SHA-256 manifest)
python -m equicvd.cli cohort        # data/processed/cohort.csv.gz + cohort_flow.csv
python -m equicvd.cli bench -B 200  # outputs/bench/{report.md, metrics.csv, table1.csv, figures}
python -m equicvd.cli sensitivity -B 200  # outputs/sensitivity/{sensitivity_report.md, <scenario>/}
pytest -q                           # equation reference tests + metric checks
```

Or run everything with `scripts/reproduce.sh` / `scripts/reproduce.ps1`, or in Docker (`Dockerfile`, pinned by
`requirements-lock.txt`).

## Documentation

| File | Contents |
|---|---|
| `docs/methods.md` | Full analysis specification |
| `docs/model_cards.md` | One card per evaluated tool |
| `docs/datasheet.md` | Datasheet for the analytic cohort |
| `docs/tripod_ai_checklist.md` | TRIPOD+AI reporting map |
| `docs/manuscript_outline.md` | Companion-paper outline tied to output files |
| `docs/release_checklist.md` | Zenodo setup and v1.0.0 release steps |
| `data/processed/data_dictionary.csv` | Every cohort column: units, definition, NHANES source |

## Citation

See `CITATION.cff`. A Zenodo DOI will be minted with v1.0.0.

## Design

- **Cohort**: age 40–79, MEC-examined, not pregnant, no self-reported CHD/angina/MI/HF/stroke, linkage-eligible,
  complete predictors. Diabetes = self-report, insulin/oral agent, or HbA1c ≥ 6.5%. eGFR = CKD-EPI 2021 on
  NHANES-standardized creatinine. Out-of-range inputs clipped (`cohort --range-policy exclude` to drop instead).
- **Outcome**: CVD death (UCOD_LEADING 001 heart disease, 005 cerebrovascular) within the horizon; non-CVD death is a
  competing event; administrative censoring handled by IPCW (Kaplan–Meier within cycle). Cycles whose censoring
  survival at the horizon is below `--min-followup-prob` (default 0.10) are excluded — for 10 years that keeps
  1999–2010.
- **Metrics** (overall and by sex, race/ethnicity, age group, income-to-poverty ratio, education): O/E, relative O/E,
  calibration intercept/slope, time-dependent AUC, (scaled) Brier, % flagged / TPR / FPR at 7.5% and 20%, and
  fairness gaps (max/min O/E, max−min AUC/TPR/FPR).
- **Uncertainty**: Rao–Wu rescaling bootstrap over PSUs within strata using 20-year combined MEC weights
  (`--unweighted` for iid). Gap statistics use basic bootstrap intervals.
- **Recalibration**: every published tool is also reported after cross-fitted logistic recalibration to CVD death
  (`<tool> (recal)`; disable with `--no-recal`).

## Known limitations

Public-use linkage gives CVD **mortality**, not incident ASCVD, so absolute O/E for PCE/PREVENT is < 1 by
construction; the fairness quantities are relative (subgroup vs overall). Statin use is proxied by any
lipid-lowering medication (BPQ100D). NCHS perturbs some public-use LMF fields.
