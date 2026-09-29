# Model cards

One card per tool evaluated in EquiCVD Bench. "Here" means NHANES 1999–2010, ages 40–79, free of CVD, outcome
10-year CVD death. Performance numbers are in `outputs/bench/report.md`, not repeated here, so this file does not
drift from the results.

---

## PCE — Pooled Cohort Equations
- **Reference:** Goff DC Jr et al. 2013 ACC/AHA Guideline on the Assessment of Cardiovascular Risk. *Circulation* 2014;129(25 Suppl 2):S49–73.
- **Intended use:** 10-year risk of first hard ASCVD event (CHD death, nonfatal MI, fatal/nonfatal stroke), adults 40–79 without ASCVD, to guide statin decisions (threshold 7.5%).
- **Development data:** ARIC, CHS, CARDIA, Framingham Original and Offspring (1968–2000s).
- **Inputs:** age, sex, race (White / African American; others use White equations), TC, HDL, SBP, BP treatment, smoking, diabetes.
- **Fairness-relevant design:** race-specific equations; no equations for Hispanic or Asian adults.
- **Implementation:** `equicvd.scores.pce`; ACC calculator means; tested against Goff Table A.

## PCE-revised
- **Reference:** Yadlowsky S et al. Clinical implications of revised pooled cohort equations for estimating atherosclerotic cardiovascular disease risk. *Ann Intern Med* 2018;169:20–29.
- **Intended use:** as PCE, re-derived with more contemporary cohorts (adds MESA, JHS) and elastic-net logistic regression.
- **Inputs:** as PCE, with TC/HDL ratio; Black indicator and interactions.
- **Implementation:** `equicvd.scores.pce_revised`; coefficients cross-checked against `preventr`.

## PREVENT (base), total CVD and ASCVD
- **Reference:** Khan SS et al. Development and validation of the American Heart Association's PREVENT equations. *Circulation* 2024;149:430–449.
- **Intended use:** 10-year risk of total CVD (ASCVD + heart failure) and ASCVD, adults 30–79 without CVD.
- **Development data:** 25 datasets, > 3 million adults.
- **Inputs:** age, sex, non-HDL-C, HDL-C, SBP, BP treatment, statin, diabetes, smoking, eGFR (BMI for the HF component). **Race-free.**
- **Not evaluated here:** optional UACR, HbA1c and SDI add-on models (v1.1 candidates).
- **Implementation:** `equicvd.scores.prevent`; coefficients exported from `preventr` `sysdata.rda`; tested against the `preventr` worked example for all 5 outcomes.

## Framingham office-based (non-laboratory)
- **Reference:** D'Agostino RB Sr et al. General cardiovascular risk profile for use in primary care. *Circulation* 2008;117:743–753.
- **Intended use:** 10-year general CVD risk where lipids are unavailable.
- **Inputs:** age, sex, BMI, SBP, BP treatment, smoking, diabetes.
- **Implementation:** `equicvd.scores.framingham_office`.

## ML-GAM (explainable ML comparator)
- **Purpose:** benchmark reference — how well a transparent additive model trained on *this* outcome can do, overall and across subgroups. Not a clinical tool.
- **Model:** logistic regression on cubic B-spline bases (5 knots) of age, TC, HDL, SBP, BMI, eGFR, plus sex, BP treatment, smoking, diabetes, statin; L2 penalty C = 0.5; IPCW sample weights.
- **Race-free** by design.
- **Validation:** 5-fold cross-fitting; all reported predictions are out-of-fold.
- **Explanations:** partial log-odds shape functions (`ml_gam_shape_functions.csv`).

## ML-GBM (explainable ML comparator)
- **Model:** histogram gradient boosting (200 iterations, learning rate 0.05, 15 leaves, min 50 per leaf, L2 = 1); monotone increasing in age, SBP, smoking, diabetes and decreasing in eGFR; IPCW sample weights; race-free.
- **Validation:** 5-fold cross-fitting.
- **Explanations:** out-of-fold permutation importance (ΔAUC) with across-fold SD.

## Recalibrated variants `<tool> (recal)`
- **Purpose:** separate "is the tool's *level* right for this outcome?" from "is it equally right across groups?".
- **Method:** logistic recalibration (intercept + slope on the tool's logit), IPCW-weighted, 5-fold cross-fitted. Ranking and AUC are unchanged.
