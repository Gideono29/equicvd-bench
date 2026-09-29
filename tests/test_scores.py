"""Reference values: Goff 2013 PCE worked examples; preventr README PREVENT example."""
import numpy as np
import pandas as pd
import pytest

from equicvd.cohort import ckd_epi_2021
from equicvd.scores import pce, prevent


def _p(**kw):
    base = dict(age=55, female=0, black=0, tc=213, hdl=50, sbp=120, bptx=0, smoker=0, diabetes=0,
                statin=0, bmi=27, egfr=90)
    base.update(kw)
    return pd.DataFrame([base])


@pytest.mark.parametrize("female,black,expected", [(1, 0, 0.021), (1, 1, 0.030), (0, 0, 0.053), (0, 1, 0.061)])
def test_pce_goff_examples(female, black, expected):
    # Goff 2013 Table A computed with rounded intermediate logs; exact arithmetic gives 5.38% for White men
    assert float(pce(_p(female=female, black=black))[0]) == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("outcome,expected", [("total_cvd", 0.147), ("ascvd", 0.092), ("heart_failure", 0.081),
                                              ("chd", 0.044), ("stroke", 0.054)])
def test_prevent_preventr_example(outcome, expected):
    d = _p(age=50, female=1, sbp=160, bptx=1, tc=200, hdl=45, statin=0, diabetes=1, smoker=0, egfr=90, bmi=35)
    assert round(float(prevent(d, outcome, clip=False)[0]), 3) == pytest.approx(expected, abs=0.0005)


def test_ckd_epi_2021():
    # 60-year-old woman, SCr 1.0 mg/dL -> ~64 (NKF calculator)
    assert ckd_epi_2021(np.array([1.0]), np.array([60]), np.array([1]))[0] == pytest.approx(64, abs=1)
