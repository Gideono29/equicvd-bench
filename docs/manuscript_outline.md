# Manuscript outline (v1.0 companion paper)

Working title: *Calibration and subgroup fairness of U.S. cardiovascular risk equations: an open, reproducible
benchmark on NHANES 1999–2018 with linked mortality*

Numbers come from `outputs/bench/` and `outputs/sensitivity/`. Cite the files rather than copying values by hand,
so the text stays in sync if results are regenerated.

## Abstract (≈ 300 words)
Background · Methods (data, n, outcome, tools, metrics, survey design) · Results (overall O/E and AUC per tool;
largest relative-O/E gaps with CIs) · Conclusions · Code/data availability with DOI.

## 1. Introduction
- The PCE and PREVENT are used for primary-prevention decisions; PREVENT removed race as a predictor.
- Open question: are the tools calibrated *equally* across sex, race/ethnicity, and socioeconomic position in a
  nationally representative sample?
- Gap: evaluations use closed cohorts, differ in outcome definitions, and are rarely reproducible.
- Contribution: an open, versioned benchmark with survey-design-correct, competing-risk-aware metrics.

## 2. Methods
Adapt from `docs/methods.md` §1–8 and follow `docs/tripod_ai_checklist.md`.
- **Figure 1** — participant flow (`flow_diagram.png`).

## 3. Results
- **Table 1** — baseline characteristics overall and by race/ethnicity (`table1.csv`).
- **Table 2** — overall performance, as published and recalibrated (`report.md` §2a–2b).
- **Figure 2** — decile calibration plots (`calibration_deciles.png`).
- **Figure 3** — relative O/E forest plot by sex, race/ethnicity and income (`subgroup_relOE_forest.png`).
- **Table 3** — fairness gaps with basic bootstrap CIs (`report.md` §4).
- Text: headline finding is the income gradient (low-income under-prediction), which also persists in the ML
  comparators, so it comes from the predictor set rather than the equations alone.
- **Supplement** — full `metrics.csv`; sensitivity analyses; ML explanations; per-cycle follow-up.

## 4. Discussion
- Principal findings; comparison with prior PREVENT/PCE validation studies (add citations).
- Why income/education gradients persist in race-free and ML models: omitted social determinants → motivates the
  PREVENT-SDI add-on (v1.1).
- Limitations (`docs/methods.md` §9): mortality outcome, public-use perturbation, statin proxy, complete-case
  analysis, small subgroups.
- Implications for guideline thresholds and for fairness auditing practice.

## 5. Declarations
Data availability · code availability (GitHub + Zenodo DOI) · ethics · funding · competing interests · author
contributions (CRediT).

## Target venues (to decide)
Methods-oriented clinical epidemiology journals, or a data/benchmark track if the emphasis is the resource.
