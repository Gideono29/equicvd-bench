"""Published 10-year cardiovascular risk equations, vectorised.

Inputs are a DataFrame with columns: age, female, black, tc, hdl (mg/dL), sbp (mmHg), bptx, smoker,
diabetes, statin (0/1), bmi (kg/m2), egfr (mL/min/1.73m2).
"""
from importlib import resources

import numpy as np
import pandas as pd

from .cohort import RANGES

MG_TO_MMOL = 0.02586


def _clip(df, eq):
    x = df.copy()
    for var, (lo, hi) in RANGES[eq].items():
        x[var] = x[var].clip(lo, hi)
    return x


# Goff et al. 2013 ACC/AHA Pooled Cohort Equations (hard ASCVD); means as in preventr / ACC calculator
_PCE = {
    (1, 0): dict(ln_age=-29.799, ln_age2=4.884, ln_tc=13.540, ln_age_tc=-3.114, ln_hdl=-13.578, ln_age_hdl=3.149,
                 t_sbp=2.019, t_age_sbp=0.0, u_sbp=1.957, u_age_sbp=0.0, smoker=7.574, ln_age_smoker=-1.665,
                 diabetes=0.661, s0=0.9665, mean=-29.1817),
    (1, 1): dict(ln_age=17.114, ln_age2=0.0, ln_tc=0.940, ln_age_tc=0.0, ln_hdl=-18.920, ln_age_hdl=4.475,
                 t_sbp=29.291, t_age_sbp=-6.432, u_sbp=27.820, u_age_sbp=-6.087, smoker=0.691, ln_age_smoker=0.0,
                 diabetes=0.874, s0=0.9533, mean=86.6081),
    (0, 0): dict(ln_age=12.344, ln_age2=0.0, ln_tc=11.853, ln_age_tc=-2.664, ln_hdl=-7.990, ln_age_hdl=1.769,
                 t_sbp=1.797, t_age_sbp=0.0, u_sbp=1.764, u_age_sbp=0.0, smoker=7.837, ln_age_smoker=-1.795,
                 diabetes=0.658, s0=0.9144, mean=61.1816),
    (0, 1): dict(ln_age=2.469, ln_age2=0.0, ln_tc=0.302, ln_age_tc=0.0, ln_hdl=-0.307, ln_age_hdl=0.0,
                 t_sbp=1.916, t_age_sbp=0.0, u_sbp=1.809, u_age_sbp=0.0, smoker=0.549, ln_age_smoker=0.0,
                 diabetes=0.645, s0=0.8954, mean=19.5425),
}


def pce(df, clip=True):
    x = _clip(df, "pce") if clip else df
    la, lt, lh, ls = (np.log(x[c].to_numpy(float)) for c in ("age", "tc", "hdl", "sbp"))
    tx = x["bptx"].to_numpy() == 1
    out = np.full(len(x), np.nan)
    for (fem, blk), c in _PCE.items():
        m = (x["female"].to_numpy() == fem) & (x["black"].to_numpy() == blk)  # non-Black use White equations
        s = (c["ln_age"] * la + c["ln_age2"] * la ** 2 + c["ln_tc"] * lt + c["ln_age_tc"] * la * lt
             + c["ln_hdl"] * lh + c["ln_age_hdl"] * la * lh
             + np.where(tx, c["t_sbp"] * ls + c["t_age_sbp"] * la * ls, c["u_sbp"] * ls + c["u_age_sbp"] * la * ls)
             + c["smoker"] * x["smoker"].to_numpy() + c["ln_age_smoker"] * la * x["smoker"].to_numpy()
             + c["diabetes"] * x["diabetes"].to_numpy())
        out[m] = 1 - c["s0"] ** np.exp(s[m] - c["mean"])
    return out


def pce_revised(df, clip=True):
    """Yadlowsky et al. 2018 revised PCE (logistic; coefficients as implemented in preventr)."""
    x = _clip(df, "pce") if clip else df
    age, sbp, tx, dm, smk, blk = (x[c].to_numpy(float) for c in ("age", "sbp", "bptx", "diabetes", "smoker", "black"))
    ratio = x["tc"].to_numpy(float) / x["hdl"].to_numpy(float)
    f = (-12.823110 + 0.106501 * age + 0.432440 * blk + 0.000056 * sbp ** 2 + 0.017666 * sbp + 0.731678 * tx
         + 0.943970 * dm + 1.009790 * smk + 0.151318 * ratio - 0.008580 * age * blk - 0.003647 * sbp * tx
         + 0.006208 * sbp * blk + 0.152968 * blk * tx - 0.000153 * age * sbp + 0.115232 * blk * dm
         - 0.092231 * blk * smk + 0.070498 * ratio * blk - 0.000173 * sbp * blk * tx - 0.000094 * age * sbp * blk)
    m = (-11.679980 + 0.064200 * age + 0.482835 * blk - 0.000061 * sbp ** 2 + 0.038950 * sbp + 2.055533 * tx
         + 0.842209 * dm + 0.895589 * smk + 0.193307 * ratio - 0.014207 * sbp * tx + 0.011609 * sbp * blk
         - 0.119460 * blk * tx + 0.000025 * age * sbp - 0.077214 * blk * dm - 0.226771 * blk * smk
         - 0.117749 * ratio * blk + 0.004190 * sbp * blk * tx - 0.000199 * age * sbp * blk)
    lp = np.where(x["female"].to_numpy() == 1, f, m)
    return 1 / (1 + np.exp(-lp))


def _prevent_coefs():
    with resources.files("equicvd").joinpath("data/prevent_base_10yr.csv").open() as f:
        return pd.read_csv(f).set_index("term")


def prevent(df, outcome="total_cvd", clip=True):
    """Khan et al. 2024 AHA PREVENT base model, 10-year risk (coefficients from preventr sysdata)."""
    x = _clip(df, "prevent") if clip else df
    co = _prevent_coefs()
    age = (x["age"].to_numpy(float) - 55) / 10
    nonhdl = (x["tc"].to_numpy(float) - x["hdl"].to_numpy(float)) * MG_TO_MMOL - 3.5
    hdl = (x["hdl"].to_numpy(float) * MG_TO_MMOL - 1.3) / 0.3
    sbp = x["sbp"].to_numpy(float)
    sbp_lo, sbp_hi = (np.minimum(sbp, 110) - 110) / 20, (np.maximum(sbp, 110) - 130) / 20
    egfr = x["egfr"].to_numpy(float)
    egfr_lo, egfr_hi = (np.minimum(egfr, 60) - 60) / -15, (np.maximum(egfr, 60) - 90) / -15
    bmi = x["bmi"].to_numpy(float)
    bmi_lo, bmi_hi = (np.minimum(bmi, 30) - 25) / 5, (np.maximum(bmi, 30) - 30) / 5
    dm, smk, bptx, st = (x[c].to_numpy(float) for c in ("diabetes", "smoker", "bptx", "statin"))
    terms = dict(age=age, nonhdl=nonhdl, hdl=hdl, sbp_lt110=sbp_lo, sbp_ge110=sbp_hi, diabetes=dm, smoking=smk,
                 bmi_lt30=bmi_lo, bmi_ge30=bmi_hi, egfr_lt60=egfr_lo, egfr_ge60=egfr_hi, bptx=bptx, statin=st,
                 bptx_sbp=bptx * sbp_hi, statin_nonhdl=st * nonhdl, age_nonhdl=age * nonhdl, age_hdl=age * hdl,
                 age_sbp=age * sbp_hi, age_diabetes=age * dm, age_smoking=age * smk, age_bmi=age * bmi_hi,
                 age_egfr=age * egfr_lo, constant=np.ones(len(x)))
    fem = x["female"].to_numpy() == 1
    lp = np.zeros(len(x))
    for t, v in terms.items():
        lp += v * np.where(fem, co.loc[t, f"female_{outcome}"], co.loc[t, f"male_{outcome}"])
    return 1 / (1 + np.exp(-lp))


def framingham_office(df):
    """D'Agostino et al. 2008 Framingham general CVD, office-based (non-laboratory, BMI) model."""
    c = {1: dict(age=2.72107, bmi=0.51125, u=2.81291, t=2.88267, smk=0.61868, dm=0.77763, s0=0.94833, mean=26.0145),
         0: dict(age=3.11296, bmi=0.79277, u=1.85508, t=1.92672, smk=0.70953, dm=0.53160, s0=0.88431, mean=23.9388)}
    out = np.full(len(df), np.nan)
    la, lb, ls = (np.log(df[v].to_numpy(float)) for v in ("age", "bmi", "sbp"))
    tx = df["bptx"].to_numpy() == 1
    for fem, k in c.items():
        m = df["female"].to_numpy() == fem
        s = (k["age"] * la + k["bmi"] * lb + np.where(tx, k["t"], k["u"]) * ls
             + k["smk"] * df["smoker"].to_numpy() + k["dm"] * df["diabetes"].to_numpy())
        out[m] = 1 - k["s0"] ** np.exp(s[m] - k["mean"])
    return out


# name -> (function, outcome the tool was built to predict, uses laboratory values)
TOOLS = {
    "PCE": (pce, "hard ASCVD", True),
    "PCE-revised": (pce_revised, "hard ASCVD", True),
    "PREVENT-CVD": (lambda d: prevent(d, "total_cvd"), "total CVD (ASCVD+HF)", True),
    "PREVENT-ASCVD": (lambda d: prevent(d, "ascvd"), "ASCVD", True),
    "Framingham-office": (framingham_office, "general CVD", False),
}


def score_all(df):
    return pd.DataFrame({name: fn(df) for name, (fn, _, _) in TOOLS.items()}, index=df.index)
