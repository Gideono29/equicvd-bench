# Changelog

## 1.0.0 — 2026-09-29
First public release; archived on Zenodo.

- **Calibration scope (decided for v1.0):** every published tool is reported both *as published* and after
  cross-fitted logistic recalibration to 10-year CVD death (`<tool> (recal)`). Subgroup-relative O/E and fairness
  gaps are the primary fairness measures, so conclusions do not depend on the mortality-vs-incidence outcome mismatch.
- Cohort: NHANES 1999–2018 + NCHS 2019 public-use LMF; n = 23,564 (13,466 evaluated at 10 years); data dictionary
  and flow diagram.
- Tools: PCE, PCE-revised, PREVENT base (total CVD, ASCVD), Framingham office-based; ML-GAM and ML-GBM comparators.
- Survey-weighted IPCW evaluation with Rao–Wu bootstrap (B = 200); basic bootstrap intervals for fairness gaps;
  Table 1; `sensitivity` command (unweighted, exclude out-of-range, 5-year horizon).
- Documentation: methods, model cards, datasheet, TRIPOD+AI checklist map, manuscript outline, release checklist;
  pinned environment, Dockerfile, CI with citation-metadata validation.

## 1.0.0rc1 — 2026-09-29 (release candidate, not archived)
- Pre-release of the above; fixed package discovery for `pip install`.

## Planned
- **1.1.0 (May 2027), candidates:** PREVENT add-on models (UACR, HbA1c, SDI); NHANES 2017–March 2020 pre-pandemic
  files; multiple imputation; refitting-aware bootstrap; restricted-use LMF confirmation; follow-up of the 5-year
  race-calibration signal.
