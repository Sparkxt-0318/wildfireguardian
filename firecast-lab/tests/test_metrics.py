"""Probability metrics and the Fractions Skill Score on SYNTHETIC fixtures: hand-computed values and identities."""
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.extra.numpy import arrays
from sklearn.metrics import average_precision_score
from wildfire import baselines

from firecast_lab import metrics as m

Y = np.array([1.0, 0.0, 1.0, 0.0])          # SYNTHETIC
P = np.array([0.9, 0.2, 0.6, 0.0])
ALL = np.ones(4, bool)


def test_brier_hand_values_and_mask():
    assert m.brier(Y, P, ALL) == pytest.approx((0.01 + 0.04 + 0.16 + 0.0) / 4)
    keep = np.array([True, True, False, True])
    y, p = Y.copy(), P.copy()
    y[2], p[2] = np.nan, np.nan                  # unscored cells are never read
    assert m.brier(y, p, keep) == pytest.approx((0.01 + 0.04 + 0.0) / 3)


def test_brier_skill_against_persistence_and_a_reference():
    bs = 0.0525
    assert m.brier_skill(Y, P, 0.0, ALL) == pytest.approx(1 - bs / 0.5)        # persistence: BS = base rate
    assert m.brier_skill(Y, P, np.full(4, 0.5), ALL) == pytest.approx(1 - bs / 0.25)
    assert m.brier_skill(Y, P, P, ALL) == 0.0
    assert np.isnan(m.brier_skill(Y, P, Y, ALL))                               # perfect reference: undefined


def test_reliability_rows_and_ece_hand_values():
    p = np.array([0, 0, 0.0005, 0.002, 0.05, 0.05, 0.6, 1.0])                 # SYNTHETIC
    y = np.array([1, 0, 0, 0, 0, 1, 1, 1], float)
    rows = m.reliability(y, p, np.ones(8, bool))
    assert len(rows) == 11 and sum(r["count"] for r in rows) == 8
    zero, below_01pct, below_03pct = rows[0], rows[1], rows[2]
    assert (zero["lower"], zero["upper"], zero["count"], zero["observed_sum"]) == (0.0, 0.0, 2, 1.0)
    assert (below_01pct["lower"], below_01pct["upper"], below_01pct["count"]) == (0.0, 0.001, 1)
    assert (below_03pct["lower"], below_03pct["count"], below_03pct["forecast_sum"]) == (0.001, 1, 0.002)
    bin_5pct = next(r for r in rows if r["lower"] == 0.03)
    assert (bin_5pct["count"], bin_5pct["mean_forecast"], bin_5pct["observed_frequency"]) == (2, 0.05, 0.5)
    assert rows[-1]["count"] == 1                                              # p = 1 lands in the closed last bin
    # |0-1| + |0.0005-0| + |0.002-0| + |0.1-1| + |0.6-1| + |1-1|, over 8 cells
    assert m.ece(y, p, np.ones(8, bool)) == pytest.approx(2.3025 / 8)
    # One bin above zero: calibration in the large on p > 0, plus the exact-zero row
    assert m.ece(y, p, np.ones(8, bool), edges=(0.0, 1.0)) == pytest.approx((1 + abs(1.7025 - 3)) / 8)
    assert m.ece(np.array([1, 0, 0, 0.0]), np.full(4, 0.25), np.ones(4, bool)) == 0.0


def test_average_precision_hand_value_ties_and_sklearn():
    # Ranks: TP (P=1, R=.5), FP, TP (P=2/3, R=1) -> 0.5 * 1 + 0.5 * 2/3
    assert m.average_precision(Y, np.array([0.9, 0.8, 0.7, 0.1]), ALL) == pytest.approx(5 / 6)
    assert np.isnan(m.average_precision(np.zeros(4), P, ALL))
    rng = np.random.default_rng(0)                                             # SYNTHETIC, many ties
    y = (rng.random(500) < 0.2).astype(float)
    p = np.round(rng.random(500), 1)
    assert m.average_precision(y, p, np.ones(500, bool)) == pytest.approx(average_precision_score(y, p), abs=1e-12)


def test_summary_reuses_baselines_score_consistently():
    rng = np.random.default_rng(1)                                             # SYNTHETIC
    y = (rng.random((20, 30)) < 0.1).astype(float)
    p = np.clip(0.6 * y + 0.3 * rng.random((20, 30)), 0, 1)
    mask = rng.random((20, 30)) < 0.8
    s = m.summary(y, p, mask, reference=0.0)
    assert s["brier"] == pytest.approx(m.brier(y, p, mask))
    assert s["bss_vs_persistence"] == pytest.approx(m.brier_skill(y, p, 0.0, mask))
    assert s["brier_skill_vs_reference"] == pytest.approx(s["bss_vs_persistence"])
    assert s["average_precision"] == pytest.approx(m.average_precision(y, p, mask))
    assert s["entries"] == mask.sum() and s["base_rate"] == pytest.approx(y[mask].mean())
    base = baselines.score(y[mask], p[mask])
    assert {k: s[k] for k in base} == base                                     # every score() field, unchanged


@pytest.mark.parametrize("bad", ["nan_inside", "p_above_one", "y_not_binary", "int_mask", "empty_mask"])
def test_inputs_are_validated_inside_the_mask(bad):
    y, p, mask = Y.copy(), P.copy(), ALL.copy()
    if bad == "nan_inside":
        p[0] = np.nan
    elif bad == "p_above_one":
        p[0] = 1.2
    elif bad == "y_not_binary":
        y[0] = 0.5
    elif bad == "int_mask":
        mask = mask.astype(int)
    else:
        mask[:] = False
    with pytest.raises((ValueError, TypeError)):
        m.brier(y, p, mask)


# ----------------------------------------------------------------------------------- Fractions Skill Score
def test_fss_three_by_three_hand_value():
    # Outcome at the centre, forecast one cell east. Masked 3x3 fractions use only in-grid cells
    # (corner windows hold 4 cells, edge windows 6, the centre 9): num = 11/72, den = 385/648, FSS = 26/35.
    y = np.zeros((3, 3)); y[1, 1] = 1                                          # SYNTHETIC
    p = np.zeros((3, 3)); p[1, 2] = 1
    mask = np.ones((3, 3), bool)
    num, den = m.fss_terms(y, p, mask, 3)
    assert num.sum() == pytest.approx(11 / 72) and den.sum() == pytest.approx(385 / 648)
    assert m.fss(y, p, mask, 3) == pytest.approx(26 / 35)
    assert m.fss(y, p, mask, 1) == 0.0                                         # no overlap at grid scale


def test_fss_identities():
    rng = np.random.default_rng(2)                                             # SYNTHETIC
    y = (rng.random((15, 12)) < 0.2).astype(float)
    p = rng.random((15, 12))
    mask = rng.random((15, 12)) < 0.7
    yv, pv = y[mask], p[mask]
    assert m.fss(y, p, mask, 1) == pytest.approx(1 - np.sum((pv - yv) ** 2) / np.sum(pv ** 2 + yv ** 2))
    assert all(v == pytest.approx(1.0) for v in m.fss_scales(y, y, mask).values())
    f, o = pv.mean(), yv.mean()                       # window covering the grid from every cell: AFSS
    assert m.fss(y, p, mask, 31) == pytest.approx(2 * f * o / (f ** 2 + o ** 2))
    b = (p > 0.5).astype(float)
    assert m.fss(y, b, mask, 3) == pytest.approx(m.fss(b, y, mask, 3))       # symmetric in its two fields
    assert m.fss_useful(0.1) == pytest.approx(0.55)


def test_fss_ignores_unscored_cells_and_marks_empty_windows():
    rng = np.random.default_rng(3)                                             # SYNTHETIC
    y = (rng.random((10, 10)) < 0.3).astype(float)
    p = rng.random((10, 10))
    mask = np.zeros((10, 10), bool); mask[2:8, 1:6] = True
    y2, p2 = y.copy(), p.copy()
    y2[~mask], p2[~mask] = np.nan, np.nan
    for n in (1, 3, 9):
        assert m.fss(y2, p2, mask, n) == pytest.approx(m.fss(y, p, mask, n))
    frac = m.neighbourhood_fraction(p2, mask, 3)
    assert np.isnan(frac[0, 9]) and np.isfinite(frac[2, 1])
    assert np.allclose(m.neighbourhood_fraction(p, mask, 1)[mask], p[mask])
    with pytest.raises(ValueError):
        m.neighbourhood_fraction(p, mask, 4)


@settings(max_examples=40, deadline=None)
@given(arrays(np.float64, (6, 7), elements=st.floats(0, 1)), arrays(np.bool_, (6, 7)),
       arrays(np.bool_, (6, 7)), st.sampled_from([1, 3, 5]))
def test_fss_is_between_zero_and_one(p, y, mask, n):
    if not mask.any():
        return
    value = m.fss(y.astype(float), p, mask, n)
    assert np.isnan(value) or -1e-12 <= value <= 1 + 1e-12


@settings(max_examples=40, deadline=None)
@given(arrays(np.float64, 12, elements=st.floats(0, 1)), arrays(np.float64, 12, elements=st.floats(0, 1)),
       arrays(np.bool_, 12))
def test_brier_skill_never_exceeds_one(p, r, y):
    mask = np.ones(12, bool)
    value = m.brier_skill(y.astype(float), p, r, mask)
    assert np.isnan(value) or value <= 1 + 1e-12
    same = m.brier_skill(y.astype(float), p, p, mask)
    assert same == 0.0 or np.isnan(same)
