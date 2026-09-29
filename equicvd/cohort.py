"""Build the analytic cohort: NHANES 1999-2018 adults 40-79 free of CVD, linked to 2019 public-use mortality."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (CVD_UCOD, CYCLES, MORT_COLSPECS, MORT_NAMES, RACE_LABELS, cycle_files)

# Valid input ranges of the published equations (used to clip or exclude)
RANGES = {
    "pce": {"age": (40, 79), "tc": (130, 320), "hdl": (20, 100), "sbp": (90, 200)},
    "prevent": {"age": (30, 79), "tc": (130, 320), "hdl": (20, 100), "sbp": (90, 180),
                "egfr": (15, 140), "bmi": (18.5, 39.9)},
}


def _read_xpt(path: Path, cols: list) -> pd.DataFrame:
    df = pd.read_sas(path, format="xport", encoding="latin-1")
    keep = ["SEQN"] + [c for c in dict.fromkeys(cols) if c in df.columns]
    return df[keep]


def load_cycle(raw: Path, label: str, year: int, suffix: str) -> pd.DataFrame:
    files = cycle_files(year, suffix)
    demo_stem = "DEMO" + suffix
    df = _read_xpt(raw / "nhanes" / label / f"{demo_stem}.xpt", files.pop(demo_stem))
    for stem, cols in files.items():
        path = raw / "nhanes" / label / f"{stem}.xpt"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `python -m equicvd.cli download` first")
        df = df.merge(_read_xpt(path, cols), on="SEQN", how="left")
    df["cycle"] = label
    df["cycle_start"] = year
    return df


def load_mortality(raw: Path) -> pd.DataFrame:
    frames = []
    for _, year, _ in CYCLES:
        path = raw / "mortality" / f"NHANES_{year}_{year + 1}_MORT_2019_PUBLIC.dat"
        m = pd.read_fwf(path, colspecs=MORT_COLSPECS, names=MORT_NAMES, na_values=["."], dtype=str)
        frames.append(m.apply(pd.to_numeric, errors="coerce"))
    return pd.concat(frames, ignore_index=True)


def _coalesce(df, cols):
    out = pd.Series(np.nan, index=df.index)
    for c in cols:
        if c in df.columns:
            out = out.fillna(df[c])
    return out


def _yes_no(s):
    """NHANES 1=yes/2=no coding -> 1/0, refused/don't know/missing -> NaN."""
    return s.map({1: 1.0, 2: 0.0})


def derive(raw: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame({"SEQN": raw["SEQN"].astype(int), "cycle": raw["cycle"],
                      "cycle_start": raw["cycle_start"]})
    d["age"] = raw["RIDAGEYR"]
    d["female"] = (raw["RIAGENDR"] == 2).astype(int)
    d["sex"] = np.where(d["female"] == 1, "Female", "Male")
    d["race"] = raw["RIDRETH1"].map(RACE_LABELS)
    d["black"] = (raw["RIDRETH1"] == 4).astype(int)

    # Systolic BP: mean of available auscultatory readings
    d["sbp"] = raw[[c for c in ["BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"] if c in raw]].mean(axis=1)
    d["tc"] = raw["LBXTC"]
    d["hdl"] = _coalesce(raw, ["LBDHDL", "LBXHDD", "LBDHDD"])
    d["bmi"] = raw["BMXBMI"]
    d["hba1c"] = raw["LBXGH"]

    # Current smoking: smoked >=100 cigarettes and now smokes every day / some days
    ever = _yes_no(raw["SMQ020"])
    now = raw["SMQ040"].map({1: 1.0, 2: 1.0, 3: 0.0})
    d["smoker"] = np.where(ever == 0, 0.0, np.where(ever == 1, now, np.nan))

    # Diabetes: self-report, insulin, oral agents, or HbA1c >= 6.5%
    dm_q = raw["DIQ010"].map({1: 1.0, 2: 0.0, 3: 0.0})
    dm_rx = (raw["DIQ050"] == 1) | (raw["DIQ070"] == 1)
    a1c = d["hba1c"] >= 6.5
    d["diabetes"] = np.where((dm_q == 1) | dm_rx | a1c, 1.0,
                             np.where(dm_q.notna() | d["hba1c"].notna(), 0.0, np.nan))

    # BP-lowering medication (BPQ050A asked only of those told to take medication; skip -> no)
    told_htn = _yes_no(raw["BPQ020"])
    d["bptx"] = np.where(told_htn.isna(), np.nan, (raw["BPQ050A"] == 1).astype(float))
    # Lipid-lowering medication (NHANES does not separate statins in BPQ; proxy)
    d["statin"] = (raw["BPQ100D"] == 1).astype(float)

    # Serum creatinine, standardized to IDMS-traceable method per NHANES guidance
    cr = _coalesce(raw, ["LBDSCR", "LBXSCR"])
    cr = np.where(d["cycle_start"] == 1999, 1.013 * cr + 0.147, cr)
    cr = np.where(d["cycle_start"] == 2005, -0.016 + 0.978 * cr, cr)
    d["creatinine"] = cr
    d["egfr"] = ckd_epi_2021(d["creatinine"], d["age"], d["female"])

    mcq = raw[["MCQ160B", "MCQ160C", "MCQ160D", "MCQ160E", "MCQ160F"]]
    d["prior_cvd"] = (mcq == 1).any(axis=1).astype(int)
    d["pregnant"] = (raw["RIDEXPRG"] == 1).astype(int)
    d["mec_examined"] = (raw["RIDSTATR"] == 2).astype(int)

    # Social subgroups
    pir = raw["INDFMPIR"]
    d["income"] = pd.cut(pir, [-np.inf, 1.3, 3.5, np.inf], labels=["PIR<1.3", "PIR 1.3-3.5", "PIR>3.5"],
                         right=False).astype(object)
    d["education"] = raw["DMDEDUC2"].map({1: "<HS", 2: "<HS", 3: "HS/GED", 4: "Some college",
                                          5: "College+"})
    d["age_group"] = pd.cut(d["age"], [40, 50, 60, 70, 80], right=False,
                            labels=["40-49", "50-59", "60-69", "70-79"]).astype(object)

    # Survey design: 20-year combined MEC weight (4-yr weight for 1999-2002 per NCHS guidance)
    early = d["cycle_start"].isin([1999, 2001])
    d["wt"] = np.where(early, raw["WTMEC4YR"] * 2 / 10, raw["WTMEC2YR"] / 10)
    d["strata"] = raw["SDMVSTRA"]
    d["psu"] = raw["SDMVPSU"]

    # Outcomes from the public-use linked mortality file (follow-up through 2019-12-31)
    d["linkage_eligible"] = (raw["ELIGSTAT"] == 1).astype(int)
    d["time"] = raw["PERMTH_EXM"] / 12.0
    died = raw["MORTSTAT"] == 1
    cvd = died & raw["UCOD_LEADING"].isin(CVD_UCOD)
    d["event"] = np.select([cvd, died], [1, 2], 0)  # 0 alive/censored, 1 CVD death, 2 other death
    return d


def ckd_epi_2021(scr, age, female):
    """Race-free CKD-EPI 2021 creatinine equation (mL/min/1.73m2)."""
    scr = np.asarray(scr, float)
    female = np.asarray(female) == 1
    k = np.where(female, 0.7, 0.9)
    a = np.where(female, -0.241, -0.302)
    r = scr / k
    return (142 * np.minimum(r, 1) ** a * np.maximum(r, 1) ** -1.200 * 0.9938 ** np.asarray(age, float)
            * np.where(female, 1.012, 1.0))


CORE = ["tc", "hdl", "sbp", "smoker", "diabetes", "bptx", "bmi", "egfr"]

# column -> (type/units, definition, NHANES/LMF source variables)
DICTIONARY = {
    "SEQN": ("int", "Respondent sequence number (unique across cycles)", "DEMO.SEQN"),
    "cycle": ("str", "NHANES survey cycle, e.g. 1999-2000", "file"),
    "cycle_start": ("int", "First calendar year of the cycle", "file"),
    "age": ("years", "Age at screening", "RIDAGEYR"),
    "female": ("0/1", "Female sex", "RIAGENDR==2"),
    "sex": ("str", "Female / Male", "RIAGENDR"),
    "race": ("str", "Race/ethnicity (Mexican American, Other Hispanic, NH White, NH Black, Other/Multiracial)", "RIDRETH1"),
    "black": ("0/1", "Non-Hispanic Black (selects PCE African-American equations)", "RIDRETH1==4"),
    "sbp": ("mmHg", "Mean of available auscultatory systolic readings", "BPXSY1-BPXSY4"),
    "tc": ("mg/dL", "Serum total cholesterol", "LBXTC (LAB13, L13_B, L13_C, TCHOL_D-J)"),
    "hdl": ("mg/dL", "HDL cholesterol", "LBDHDL (1999-2002), LBXHDD (2003-04), LBDHDD (2005-18)"),
    "bmi": ("kg/m2", "Body mass index", "BMXBMI"),
    "hba1c": ("%", "Glycohemoglobin", "LBXGH"),
    "smoker": ("0/1", "Current smoker: >=100 lifetime cigarettes and now smokes every day or some days", "SMQ020, SMQ040"),
    "diabetes": ("0/1", "Self-reported diagnosis, insulin, oral agents, or HbA1c >= 6.5%", "DIQ010, DIQ050, DIQ070, LBXGH"),
    "bptx": ("0/1", "Currently taking prescribed BP-lowering medication", "BPQ020, BPQ050A"),
    "statin": ("0/1", "Currently taking prescribed lipid-lowering medication (statin proxy)", "BPQ100D"),
    "creatinine": ("mg/dL", "Serum creatinine standardized to IDMS (1999-2000: 1.013x+0.147; 2005-06: -0.016+0.978x)",
                   "LBXSCR / LBDSCR"),
    "egfr": ("mL/min/1.73m2", "CKD-EPI 2021 race-free eGFR", "derived from creatinine, age, sex"),
    "prior_cvd": ("0/1", "Self-reported CHF, CHD, angina, MI or stroke (exclusion)", "MCQ160B-F"),
    "pregnant": ("0/1", "Pregnant at exam (exclusion)", "RIDEXPRG==1"),
    "mec_examined": ("0/1", "Examined at mobile examination center", "RIDSTATR==2"),
    "income": ("str", "Family income-to-poverty ratio group: <1.3, 1.3-3.5, >3.5", "INDFMPIR"),
    "education": ("str", "Highest education (adults 20+): <HS, HS/GED, Some college, College+", "DMDEDUC2"),
    "age_group": ("str", "Age band 40-49 / 50-59 / 60-69 / 70-79", "RIDAGEYR"),
    "wt": ("weight", "20-year combined MEC weight: WTMEC4YR*2/10 for 1999-2002, WTMEC2YR/10 otherwise",
           "WTMEC2YR, WTMEC4YR"),
    "strata": ("int", "Masked variance pseudo-stratum", "SDMVSTRA"),
    "psu": ("int", "Masked variance pseudo-PSU", "SDMVPSU"),
    "linkage_eligible": ("0/1", "Eligible for mortality linkage", "LMF ELIGSTAT==1"),
    "time": ("years", "Follow-up from MEC exam to death or 2019-12-31", "LMF PERMTH_EXM/12"),
    "event": ("0/1/2", "0 alive at end of follow-up, 1 CVD death (UCOD 001 heart disease or 005 cerebrovascular), "
              "2 non-CVD death", "LMF MORTSTAT, UCOD_LEADING"),
    "oor_pce": ("0/1", "Any PCE input outside valid range (age 40-79, TC 130-320, HDL 20-100, SBP 90-200)", "derived"),
    "oor_prevent": ("0/1", "Any PREVENT input outside valid range (age 30-79, TC 130-320, HDL 20-100, SBP 90-180, "
                    "eGFR 15-140, BMI 18.5-39.9)", "derived"),
}


def write_dictionary(columns, path):
    missing = [c for c in columns if c not in DICTIONARY]
    if missing:
        print(f"WARNING: undocumented cohort columns: {missing}")
    rows = [{"column": c, "type_units": DICTIONARY[c][0], "definition": DICTIONARY[c][1], "source": DICTIONARY[c][2]}
            for c in columns if c in DICTIONARY]
    pd.DataFrame(rows).to_csv(path, index=False)


def build_cohort(data_dir: Path, range_policy: str = "clip") -> pd.DataFrame:
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    print("Reading NHANES component files ...", flush=True)
    raw = pd.concat([load_cycle(raw_dir, *c) for c in CYCLES], ignore_index=True)
    mort = load_mortality(raw_dir)
    raw = raw.merge(mort, on="SEQN", how="left")
    d = derive(raw)

    flow = [("All NHANES 1999-2018 participants", len(d))]

    def step(mask, label):
        nonlocal d
        d = d[mask.loc[d.index]]
        flow.append((label, len(d)))

    step(d["age"].between(40, 79), "Age 40-79 at screening")
    step(d["mec_examined"] == 1, "Examined at mobile examination center")
    step(d["pregnant"] == 0, "Not pregnant")
    step(d["prior_cvd"] == 0, "No self-reported CHD, angina, MI, heart failure or stroke")
    step((d["linkage_eligible"] == 1) & d["time"].notna(), "Eligible for mortality linkage with follow-up")
    step(d[CORE].notna().all(axis=1) & (d["wt"] > 0), "Complete predictors (" + ", ".join(CORE) + ")")

    for eq, rng in RANGES.items():
        oor = np.zeros(len(d), bool)
        for var, (lo, hi) in rng.items():
            oor |= ~d[var].between(lo, hi).to_numpy()
        d[f"oor_{eq}"] = oor.astype(int)
    if range_policy == "exclude":
        step(d["oor_pce"] == 0, "Predictors within PCE valid ranges")

    d = d.reset_index(drop=True)
    out = data_dir / "processed"
    out.mkdir(parents=True, exist_ok=True)
    d.to_csv(out / "cohort.csv.gz", index=False)
    write_dictionary(d.columns, out / "data_dictionary.csv")
    flow_df = pd.DataFrame(flow, columns=["step", "n"])
    flow_df["excluded"] = (-flow_df["n"].diff()).fillna(0).astype(int)
    flow_df.to_csv(out / "cohort_flow.csv", index=False)
    meta = {
        "range_policy": range_policy,
        "n": int(len(d)),
        "cvd_deaths": int((d["event"] == 1).sum()),
        "other_deaths": int((d["event"] == 2).sum()),
        "median_followup_years": float(d["time"].median()),
        "by_cycle": d.groupby("cycle").agg(n=("SEQN", "size"), cvd_deaths=("event", lambda e: int((e == 1).sum())),
                                           max_fu=("time", "max")).reset_index().to_dict("records"),
        "out_of_range_pce": int(d["oor_pce"].sum()),
        "out_of_range_prevent": int(d["oor_prevent"].sum()),
    }
    (out / "cohort_meta.json").write_text(json.dumps(meta, indent=1, default=float))

    print("\nCohort flow:")
    print(flow_df.to_string(index=False))
    print(f"\nFinal cohort n={meta['n']:,}; CVD deaths={meta['cvd_deaths']:,}; other deaths={meta['other_deaths']:,}; "
          f"median follow-up {meta['median_followup_years']:.1f} y")
    print(f"Written: {out / 'cohort.csv.gz'}")
    return d
