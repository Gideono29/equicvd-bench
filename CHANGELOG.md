# Changelog

## 1.0.0rc1 — 2026-09-29 (release candidate)
- Cohort build complete: NHANES 1999–2018 + 2019 public-use LMF; n = 23,564; data dictionary and flow diagram.
- Tools: PCE, PCE-revised, PREVENT base (total CVD, ASCVD), Framingham office-based; ML-GAM and ML-GBM comparators.
- Cross-fitted logistic recalibration of every published tool (`<tool> (recal)`), reported alongside as-published results.
- Fairness gaps with basic bootstrap intervals; Table 1; `sensitivity` command (unweighted, exclude out-of-range, 5-year horizon).
- Documentation: methods, model cards, datasheet, TRIPOD+AI checklist mapping; pinned environment, Dockerfile, CI.

## Planned
- **1.0.0 (November 2026):** freeze after the 30 October calibration-scope decision; mint Zenodo DOI.
- **1.1.0 (May 2027), candidates:** PREVENT add-on models (UACR, HbA1c, SDI); NHANES 2017–March 2020 pre-pandemic
  files; multiple imputation; refitting-aware bootstrap; restricted-use LMF confirmation.
