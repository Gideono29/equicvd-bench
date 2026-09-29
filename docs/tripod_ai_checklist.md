# TRIPOD+AI reporting map

TRIPOD+AI (Collins GS et al., *BMJ* 2024;385:e078378) covers development and evaluation of prediction models,
including fairness. This file maps each checklist **topic** to where the manuscript can take its content. Transcribe
the official item numbers from the published checklist when you fill in the journal's form. They are left out here
so this file cannot disagree with the official list.

Status: ✅ available from the repository · ✍️ must be written for the manuscript · ⚠️ decision or data needed.

| Section / topic | Source in repository | Status |
|---|---|---|
| Title: identify as evaluation (external validation) of prediction models + ML comparators | — | ✍️ |
| Abstract (structured) | `outputs/bench/report.md` §2–4 | ✍️ |
| Background: healthcare context, rationale, known fairness concerns | `docs/model_cards.md` | ✍️ |
| Objectives | README | ✍️ |
| Data sources, dates of collection | `docs/methods.md` §1 | ✅ |
| Participants: setting, eligibility, treatments | `docs/methods.md` §2, `cohort_flow.csv` | ✅ |
| Data preparation / preprocessing | `docs/methods.md` §3, `data_dictionary.csv` | ✅ |
| Outcome definition, timing, blinding | `docs/methods.md` §4 | ✅ (blinding: not applicable, registry linkage) |
| Predictors: definition, measurement, timing | `docs/methods.md` §3, `data_dictionary.csv` | ✅ |
| Sample size justification | Events per subgroup: `report.md` §3 | ⚠️ add precision-based justification (e.g. Riley et al. criteria for validation) |
| Missing data | `docs/methods.md` §9.6, `cohort_flow.csv` | ✅ complete case; ⚠️ consider MI sensitivity |
| Analytical methods: model specification, performance measures, uncertainty | `docs/methods.md` §5–7 | ✅ |
| Class imbalance | Not addressed; IPCW only | ✍️ state no resampling |
| **Fairness: methods to identify and handle unfairness; subgroups** | `docs/methods.md` §7, `report.md` §3–4 | ✅ |
| Model output: form of predictions, thresholds | 10-y risk; 7.5% and 20% thresholds | ✅ |
| Training vs evaluation data differences | ML cross-fitting, `docs/methods.md` §5 | ✅ |
| Ethical approval | NCHS Research Ethics Review Board approved NHANES; secondary public data | ✍️ confirm with your IRB whether exempt determination is needed |
| Funding, conflicts of interest | — | ✍️ |
| Protocol / registration | — | ⚠️ post a protocol (e.g. OSF) before the v1.0 freeze |
| Data availability | Public NCHS files; derived cohort on Zenodo | ✅ after DOI |
| Code availability | GitHub + Zenodo DOI | ⚠️ after repository creation |
| Patient and public involvement | — | ✍️ |
| Results: participant flow | `flow_diagram.png` | ✅ |
| Results: participant characteristics, overall and by subgroup | `table1.csv` | ✅ |
| Results: model performance with CIs, overall and by subgroup | `metrics.csv`, `report.md` | ✅ |
| Results: model updating (recalibration) | `<tool> (recal)` rows | ✅ |
| Results: sensitivity analyses | `outputs/sensitivity/sensitivity_report.md` | ✅ |
| Discussion: interpretation, limitations, usability, fairness implications | `docs/methods.md` §9 | ✍️ |
