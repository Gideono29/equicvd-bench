# EquiCVD Bench — Methods

This document is the reference description of what `equicvd` computes. Section numbers are cited from the
TRIPOD+AI checklist (`docs/tripod_ai_checklist.md`).

## 1. Data sources

- **NHANES 1999–2018** (10 two-year cycles), continuous, nationally representative cross-sectional survey of the
  U.S. civilian non-institutionalized population. Component files: DEMO, BPX, BPQ, BMX, DIQ, SMQ, MCQ, total
  cholesterol, HDL, glycohemoglobin, standard biochemistry (legacy lab file names for 1999–2004; see
  `equicvd/config.py`).
- **NCHS Public-Use Linked Mortality Files, 2019** — probabilistic linkage to the National Death Index with
  follow-up through 31 December 2019. Fixed-width layout per NCHS read-in programs (`MORT_COLSPECS`).
- `python -m equicvd.cli download` fetches all 117 files from `wwwn.cdc.gov` and `ftp.cdc.gov` and writes
  `data/raw/manifest.json` with byte size and SHA-256 of each file.

## 2. Study population

Inclusion, applied in order (counts in `data/processed/cohort_flow.csv` and `outputs/bench/flow_diagram.png`):

1. Age 40–79 at screening (PCE age range).
2. Examined at the mobile examination center.
3. Not pregnant.
4. No self-reported coronary heart disease, angina, myocardial infarction, heart failure or stroke (MCQ160B–F).
5. Eligible for mortality linkage with non-missing follow-up time.
6. Complete predictors: total and HDL cholesterol, systolic BP, smoking, diabetes, BP treatment, BMI, eGFR; positive
   MEC weight.

For each analysis horizon *h*, cycles are retained only if Kaplan–Meier censoring survival at *h* within the
cycle is ≥ 0.10 (`--min-followup-prob`). For *h* = 10 y this retains 1999–2010.

## 3. Predictors

Definitions are in `data/processed/data_dictionary.csv`. Key choices:

| Predictor | Definition | Note |
|---|---|---|
| Systolic BP | Mean of available auscultatory readings | |
| Diabetes | Self-report, insulin, oral agents, or HbA1c ≥ 6.5% | Fasting glucose not used (subsample only) |
| Current smoking | ≥ 100 lifetime cigarettes and smokes every day/some days | |
| BP treatment | BPQ050A = 1 (skip pattern → 0) | |
| Statin | Any prescribed lipid-lowering medication (BPQ100D) | Proxy; over-counts non-statin therapy |
| eGFR | CKD-EPI 2021, race-free | Creatinine standardized for 1999–2000 and 2005–2006 per NHANES guidance |

**Out-of-range inputs** are clipped to each equation's published valid range (PCE: TC 130–320, HDL 20–100,
SBP 90–200; PREVENT additionally SBP ≤ 180, eGFR 15–140, BMI 18.5–39.9). A sensitivity analysis excludes them.

## 4. Outcome

CVD death = underlying cause UCOD_LEADING 001 (diseases of heart) or 005 (cerebrovascular diseases) within *h*
years of the MEC exam. Non-CVD death is a **competing event**. The estimand is the cause-specific cumulative
incidence at *h*.

This is a **mortality** outcome. The PCE predicts incident hard ASCVD; PREVENT predicts incident total CVD / ASCVD;
Framingham predicts incident general CVD. Absolute calibration of as-published tools against this outcome is
therefore expected to show O/E < 1. The benchmark reports as-published results, recalibrated results and
subgroup-relative calibration so that fairness conclusions do not depend on the outcome mismatch.

## 5. Risk tools

| Tool | Form | Coefficient source | Verification |
|---|---|---|---|
| PCE | Sex × race Cox equations | Goff et al. 2014, means from ACC calculator | Goff Table A examples (`tests/test_scores.py`) |
| PCE-revised | Sex-specific logistic | Yadlowsky et al. 2018 | Cross-checked against `preventr` source |
| PREVENT base (total CVD, ASCVD) | Sex-specific logistic | Khan et al. 2024; `preventr` `sysdata.rda` exported to `equicvd/data/prevent_base_10yr.csv` | `preventr` README example, 5 outcomes |
| Framingham office (non-laboratory) | Sex-specific Cox, BMI in place of lipids | D'Agostino et al. 2008 | — |
| ML-GAM | Additive logistic, cubic B-splines on continuous predictors, L2 (C = 0.5) | Trained here | Cross-fitted |
| ML-GBM | Histogram gradient boosting, monotone in age, SBP, smoking, diabetes (+) and eGFR (−) | Trained here | Cross-fitted |

Race/ethnicity is used only where the published equation requires it (PCE, PCE-revised). The ML comparators are
race-free, like PREVENT. ML comparators are fitted with IPCW sample weights on the benchmark outcome using 5-fold
cross-fitting, so every participant's prediction comes from a model that did not see them.

**Recalibrated tools** (`<tool> (recal)`): logistic recalibration `logit p* = a + b·logit p`, fitted with IPCW
weights, 5-fold cross-fitted. Ranking is unchanged; absolute level and spread are adapted to CVD death.

## 6. Handling censoring and survey design

- **IPCW.** Censoring is administrative (end of 2019), so it depends on exam date. The censoring survival *G*(t) is
  estimated by Kaplan–Meier within cycle. A participant with death (any cause) at *T* ≤ *h* gets weight 1/*G*(*T*−);
  one followed past *h* gets 1/*G*(*h*); one censored before *h* gets 0. `tests/test_metrics.py` shows by simulation
  that the IPCW mean of the binary outcome recovers the true cumulative incidence under competing risks.
- **Survey weights.** 20-year combined MEC weights (WTMEC4YR × 2/10 for 1999–2002, WTMEC2YR/10 otherwise),
  multiplied by the IPCW weight.
- **Variance.** Rao–Wu rescaling bootstrap: within each masked variance stratum, *n*ₕ − 1 PSUs are drawn with
  replacement and weights rescaled by *n*ₕ/(*n*ₕ − 1); default B = 200, seed 20261101.

## 7. Performance and fairness measures

For each tool, overall and within levels of sex, race/ethnicity, age group, income-to-poverty ratio (< 1.3,
1.3–3.5, > 3.5) and education:

- **Calibration:** observed (IPCW, survey-weighted) and expected risk, O/E, calibration intercept (offset logistic)
  and slope, decile calibration plots.
- **Relative O/E:** subgroup O/E ÷ overall O/E. Isolates *differential* miscalibration from overall outcome mismatch.
- **Discrimination:** time-dependent AUC at *h* (cases: CVD death ≤ *h*; controls: everyone else with known status,
  including competing deaths), IPCW- and survey-weighted.
- **Overall accuracy:** IPCW Brier score and scaled Brier (1 − Brier/Brier_null).
- **Decision thresholds:** % flagged, TPR and FPR at 7.5% and 20% predicted risk.
- **Fairness gaps** per attribute: O/E max ÷ min, and max − min of AUC, calibration slope, TPR@7.5%, FPR@7.5%,
  % flagged. Levels with < 10 horizon events are reported but excluded from gaps.

Confidence intervals are bootstrap percentile intervals, except for gap statistics, which use **basic
(reflected) intervals** because max/min statistics are biased upward under resampling.

**What the CIs do not cover:** IPCW weights, recalibration and ML fits are held fixed across replicates. The CIs
therefore reflect sampling variability of participants and PSUs, not model-fitting variability.

## 8. Pre-specified sensitivity analyses (`python -m equicvd.cli sensitivity`)

| Scenario | Change |
|---|---|
| unweighted | Ignore survey weights; iid bootstrap |
| exclude_out_of_range | Drop participants outside PCE input ranges instead of clipping |
| horizon_5y | 5-year CVD death; retains 2011–2014 cycles. Tools output 10-year risks, so only relative measures are interpretable |

## 9. Known limitations

1. Mortality rather than incident events (public-use constraint).
2. NCHS perturbs some public-use LMF fields for confidentiality; confirm key results with restricted-use files.
3. Statin use proxied by any lipid-lowering medication.
4. Self-reported prior CVD for exclusion; residual prevalent disease is possible.
5. Small subgroups (Other Hispanic, Other/Multiracial) have few events; their estimates are imprecise and they drop
   out of gap summaries.
6. Complete-case analysis. 2,729 of 26,293 otherwise-eligible participants (10.4%) lack one or more predictors (`cohort_flow.csv`); multiple imputation is
   candidate v1.1 work.
