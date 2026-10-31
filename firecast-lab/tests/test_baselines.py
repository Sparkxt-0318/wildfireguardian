"""Phase 0 baselines on SYNTHETIC fires: reuse of wildfire.baselines, fitting, support, members, no outcome reads."""
import dataclasses

import numpy as np
import pytest
from scipy import stats
from wildfire import baselines as wb

import synthetic as syn
from firecast_lab import baselines as bl
from firecast_lab import metrics as m


@pytest.fixture(scope="module")
def train():
    """SYNTHETIC training windows: three fires spreading downwind (east), lead 24 h."""
    out = []
    for seed in range(3):
        out += syn.windows(f"SYNTHETIC_{seed}", *syn.fire(seed=seed))
    return out


def test_dilation_is_wildfire_dilation_by_lead():
    rng = np.random.default_rng(0)
    for _ in range(20):
        burned = rng.random((15, 17)) < 0.03
        burned[rng.integers(15), 0] = True                          # touch the grid edge too
        k = float(rng.choice([1, 2, 3, 8]))
        inputs = syn.window(burned, np.full(burned.shape, np.inf)).inputs
        cum, supported = bl.Dilation(hours_per_cell=k).probabilities(inputs, 24)
        assert supported.all() and np.array_equal(cum[0], burned)
        for lead in range(1, 25):
            assert np.array_equal(cum[lead].astype(bool) & ~burned, wb.dilation(burned, lead, k).astype(bool))
            assert (cum[lead][burned] == 1).all()


def test_dilation_tuning_minimizes_the_direct_pooled_brier(train):
    model = bl.Dilation().fit(train)
    for k, score in model.training_brier.items():
        y, p, masks = [], [], []
        for w in train:
            cum, _ = bl.Dilation(hours_per_cell=k).probabilities(w.inputs, w.lead_h)
            y.append(((w.outcome_h > 0) & (w.outcome_h <= w.lead_h)).astype(float))
            p.append(cum[-1])
            masks.append(w.fitting_rows)
        direct = m.brier(np.concatenate([a.ravel() for a in y]), np.concatenate([a.ravel() for a in p]),
                         np.concatenate([a.ravel() for a in masks]))
        assert score == pytest.approx(direct)
    best = min(model.training_brier.values())
    assert model.hours_per_cell == max(k for k, s in model.training_brier.items() if s == best)
    assert model.hours_per_cell in bl.DILATION_CANDIDATES


def test_calibrated_dilation_recovers_a_known_distance_law():
    # SYNTHETIC: a 3x3 burned block; a cell at Chebyshev distance d arrives d * G hours after the cutoff,
    # G ~ Gamma(2, 3 h per cell), so P(burned by lead l | d) = GammaCDF(l / d).
    rng = np.random.default_rng(1)
    burned = np.zeros((41, 41), bool)
    burned[19:22, 19:22] = True
    d = bl.front_distance(burned)
    train = [syn.window(burned, np.where(burned, -1.0, d * rng.gamma(2.0, 3.0, d.shape))) for _ in range(40)]
    model = bl.CalibratedDilation().fit(train)
    cum, supported = model.probabilities(train[0].inputs, 24)
    law = stats.gamma(2.0, scale=3.0)
    for lead in (3, 12, 24):
        for dist in (1, 2, 4, 8):
            cell = (19, 21 + dist)
            assert cum[lead][cell] == pytest.approx(law.cdf(lead / dist), abs=0.06)
    assert supported.all() and np.array_equal(cum[0], burned) and (cum[:, burned] == 1).all()
    assert (np.diff(cum, axis=0) >= 0).all()                                  # non-decreasing in lead
    row = cum[24][20, 22:]
    assert (np.diff(row) <= 0).all()                                          # non-increasing in distance


def test_lead_features_match_hand_features():
    rng = np.random.default_rng(2)
    burned = rng.random((12, 13)) < 0.05
    u, v, slope = rng.normal(size=(3, 12, 13))
    base = wb.hand_features(burned, 1.0, u, v, slope, None, ())
    for lead in (1, 2, 7, 24):
        assert np.allclose(bl.lead_features(base, lead), wb.hand_features(burned, lead, u, v, slope, None, ()),
                           rtol=0, atol=1e-12)


def test_logistic_learns_downwind_spread_and_declares_support(train):
    model = bl.Logistic(rows_per_class=150).fit(train)
    burned = np.zeros((21, 21), bool)
    burned[10, 10] = True
    u, v, slope = np.full((21, 21), 6.0), np.zeros((21, 21)), np.full((21, 21), 12.0)
    slope[0, 0] = np.nan                                                       # a missing input
    w = syn.window(burned, np.full(burned.shape, np.inf), u=u, v=v, slope=slope)
    cum, supported = model.probabilities(w.inputs, 24)
    assert cum[24][10, 16] > 2 * cum[24][10, 4] > 0                            # downwind (east) beats upwind
    assert not supported[0, 0] and np.isnan(cum[:, 0, 0]).all() and supported[burned].all()
    known = cum[:, supported]
    assert (np.diff(known, axis=0) >= 0).all() and ((known >= 0) & (known <= 1)).all()
    assert set(model.describe()) >= {"coef", "intercept"}


def test_baselines_give_coherent_members_at_matched_k(train):
    w = train[1]
    for name in ("persistence", "dilation", "calibrated_dilation", "logistic"):
        model = bl.make(name).fit(train)
        hours = bl.members(model, w, K=12, seed=5)
        assert hours.shape == (12, *w.inputs.shape)
        burned = w.inputs.burned
        assert (hours[:, burned] == w.inputs.initial_h[burned]).all()          # present fire keeps its age
        new = hours[:, ~burned]
        assert (np.isinf(new) | ((new > 0) & (new <= w.lead_h))).all()
        reached = (hours > 0) & (hours <= w.lead_h)                           # shared coupling: nested members
        sizes = reached.sum(axis=(1, 2))
        order = np.argsort(sizes)
        assert all((reached[a] <= reached[b]).all() for a, b in zip(order[:-1], order[1:]))
        assert np.array_equal(hours, bl.members(model, w, K=12, seed=5))
    assert (np.isinf(bl.members(bl.Persistence(), w, K=3, seed=0)[:, ~w.inputs.burned])).all()


def test_forecasts_never_read_the_outcome(train):
    w = train[2]
    blind = dataclasses.replace(w, outcome_h=np.full(w.outcome_h.shape, np.nan))
    for name in ("persistence", "dilation", "calibrated_dilation", "logistic"):
        model = bl.make(name).fit(train)
        for coupling, length in (("shared", None), ("copula", 2.0)):
            a = bl.members(model, w, K=6, seed=1, coupling=coupling, length_cells=length)
            b = bl.members(model, blind, K=6, seed=1, coupling=coupling, length_cells=length)
            assert np.array_equal(a, b, equal_nan=True)


def test_fitting_needs_one_lead_and_some_rows(train):
    with pytest.raises(ValueError, match="no fitting rows"):
        bl.CalibratedDilation().fit([])
    other = syn.windows("SYNTHETIC_12", *syn.fire(seed=7), lead_h=12)
    with pytest.raises(ValueError, match="one lead"):
        bl.Dilation().fit(train + other)
    with pytest.raises(ValueError, match="unknown baseline"):
        bl.make("farsite")
