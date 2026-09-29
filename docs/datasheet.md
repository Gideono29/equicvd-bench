# Datasheet — EquiCVD Bench analytic cohort

Structured after Gebru et al., "Datasheets for Datasets".

**Motivation.** To provide a fixed, openly reproducible population for comparing calibration and subgroup
fairness of U.S. cardiovascular risk tools.

**Composition.** One row per NHANES 1999–2018 participant aged 40–79 who was MEC-examined, not pregnant, free of
self-reported CVD, linkage-eligible and had complete predictors (n = 23,564; 810 CVD deaths; 2,396 non-CVD deaths
through 2019). Columns and derivations: `data/processed/data_dictionary.csv`. No direct identifiers. SEQN is the
public NHANES respondent number.

**Collection.** Derived entirely from public-use NCHS files (NHANES component XPT files; 2019 public-use Linked
Mortality Files). No new data were collected.

**Preprocessing.** See `docs/methods.md` §2–4. Deterministic: the same raw files (verified by SHA-256 in
`data/raw/manifest.json`) always produce the same cohort file.

**Uses.** Intended for evaluating risk-prediction tools, including their fairness. The cohort must be analysed
with its survey weights (`wt`, `strata`, `psu`) for population inference.

**Not suitable for:** individual-level clinical decisions; inference about incident (non-fatal) events;
re-identification attempts (prohibited by NCHS data-use terms).

**Distribution.** Derived file to be deposited with the v1.0 Zenodo record. NHANES public-use data and
public-use LMF are released by NCHS for public use; users should cite NCHS and follow NCHS data-use restrictions.

**Maintenance.** Maintained by Gideon Owusu (Michigan Technological University; ORCID 0009-0000-0540-7449). Versioned with the code (see `CHANGELOG.md`). Rebuilt
if NCHS releases a new public-use LMF.
