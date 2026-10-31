"""Coherent member generators on SYNTHETIC probability fields: marginals, lattice consistency, coherence, seeds."""
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from firecast_lab import members as mb
from firecast_lab import metrics as m


def _cum(rng, L=6, shape=(6, 7)):
    """SYNTHETIC cumulative probabilities: flat stretches, exact 0 and 1, cells burned at the cutoff, unknowns."""
    steps = rng.random((L, *shape)) * (rng.random((L, *shape)) < 0.6)
    cdf = np.cumsum(steps, axis=0)
    final = rng.random(shape) ** 2
    final[0, 0], final[0, 1] = 0.0, 1.0
    cdf = cdf / np.maximum(cdf[-1], 1e-12) * final
    cum = np.concatenate([np.zeros((1, *shape)), cdf])
    burned, unknown = np.zeros(shape, bool), np.zeros(shape, bool)
    burned[1, :2], unknown[2, :2] = True, True
    cum[:, burned], cum[:, unknown] = 1.0, np.nan
    return cum, burned, unknown


@pytest.mark.parametrize("coupling, length", [("shared", None), ("copula", 3.0)])
def test_marginals_reproduce_the_inputs(coupling, length):
    cum, burned, unknown = _cum(np.random.default_rng(1))
    K = 4000
    hours = mb.coherent_members(cum, K, seed=11, coupling=coupling, length_cells=length)
    assert np.isnan(hours[:, unknown]).all() and not np.isnan(hours[:, ~unknown]).any()
    for lead in range(cum.shape[0]):
        freq = (hours[:, ~unknown] <= lead).mean(axis=0)
        p = cum[lead, ~unknown]
        assert (np.abs(freq - p) <= 5 * np.sqrt(p * (1 - p) / K) + 1e-12).all()   # exact where p is 0 or 1
    assert (hours[:, burned] == 0.0).all()                 # burned at the cutoff: initial_h defaults to 0


def test_lattice_and_timing_follow_the_shared_uniform_rule():
    rng = np.random.default_rng(2)
    cum, _, unknown = _cum(rng)
    u = 1.0 - rng.random((50, *cum.shape[1:]))
    hours = mb.threshold(cum, u)
    for lead in range(cum.shape[0]):                       # burned by l  <=>  U <= cum[l], at every lead
        assert np.array_equal((hours <= lead)[:, ~unknown], (u <= cum[lead])[:, ~unknown])
    new = (hours > 0) & np.isfinite(hours)
    assert np.array_equal(m.hourly_arrival(hours, 6)[new], np.ceil(hours[new]))
    # hand values: one cell, cum = [0, .2, .6, .6, 1]; within the hour the piecewise-linear CDF is inverted
    one = np.array([0.0, 0.2, 0.6, 0.6, 1.0])[:, None, None]
    got = mb.threshold(one, np.array([0.4, 0.7, 0.2, 1.0, 0.1])[:, None, None])[:, 0, 0]
    assert np.allclose(got, [1.5, 3.25, 1.0, 4.0, 0.5])
    never = np.array([0.0, 0.1, 0.5])[:, None, None]
    assert mb.threshold(never, np.full((1, 1, 1), 0.7))[0, 0, 0] == np.inf


def test_initial_hours_mark_cells_burned_at_the_cutoff():
    cum = np.array([[1.0, 0.0], [1.0, 0.5]])[:, None, :]  # cell 0 burned at the cutoff, cell 1 not
    hours = mb.coherent_members(cum, 20, seed=0, initial_h=np.array([[-3.5, np.nan]]))
    assert (hours[:, 0, 0] == -3.5).all() and ((hours[:, 0, 1] == np.inf) | (hours[:, 0, 1] <= 1)).all()
    with pytest.raises(ValueError, match="<= 0"):
        mb.coherent_members(cum, 2, seed=0, initial_h=np.array([[2.0, np.nan]]))


def test_shared_members_are_nested_super_level_sets():
    L, shape = 8, (12, 15)
    cum = np.broadcast_to(np.linspace(0, 1, L + 1)[:, None, None], (L + 1, *shape)).copy()
    hours = mb.coherent_members(cum, 40, seed=3)
    assert (hours == hours[:, :1, :1]).all()               # constant field: every member is all or nothing
    ramp = np.clip(np.linspace(0, 1, L + 1)[:, None, None] * np.linspace(1.5, 0.1, 15)[None, None, :], 0, 1)
    hours = mb.coherent_members(np.broadcast_to(ramp, (L + 1, 3, 15)), 40, seed=4)
    burned = hours <= L
    assert (np.diff(burned.astype(int), axis=2) <= 0).all()   # higher probability is always burned first


def test_gaussian_field_has_the_declared_correlation_and_unit_variance():
    rng = np.random.default_rng(5)
    length = 4.0
    z = np.stack([mb.gaussian_field((40, 40), length, rng) for _ in range(400)])
    assert abs(z.var() - 1) < 0.03 and abs(z[:, 0, 0].var() - 1) < 0.2     # stationary up to the corner
    for lag in (1, 2, 4, 8):
        rho = np.mean(z[:, :, :-lag] * z[:, :, lag:]) / z.var()
        assert rho == pytest.approx(np.exp(-lag**2 / (2 * length**2)), abs=0.03)
    with pytest.raises(ValueError):
        mb.gaussian_field((4, 4), 0.0, rng)


def test_copula_members_are_spatially_coherent():
    # One lead, p = 1/2 everywhere. Neighbours disagree with probability arccos(rho) / pi under the copula
    # (rho = exp(-1 / (2 L^2))), 0 when shared, 1/2 for independent cells.
    cum = np.stack([np.zeros((30, 30)), np.full((30, 30), 0.5)])
    burned = mb.coherent_members(cum, 400, seed=6, coupling="copula", length_cells=4.0) <= 1
    disagree = (burned[:, :, 1:] != burned[:, :, :-1]).mean()
    assert disagree == pytest.approx(np.arccos(np.exp(-1 / 32)) / np.pi, abs=0.01)
    independent = 1.0 - np.random.default_rng(6).random((400, 30, 30)) <= 0.5
    assert (independent[:, :, 1:] != independent[:, :, :-1]).mean() == pytest.approx(0.5, abs=0.01)
    shared = mb.coherent_members(cum, 400, seed=6) <= 1
    assert (shared[:, :, 1:] == shared[:, :, :-1]).all()


@pytest.mark.parametrize("coupling, length", [("shared", None), ("copula", 2.5)])
def test_members_are_deterministic_under_the_seed(coupling, length):
    cum, _, _ = _cum(np.random.default_rng(7))
    a = mb.coherent_members(cum, 16, seed=[9, 1], coupling=coupling, length_cells=length)
    b = mb.coherent_members(cum, 16, seed=[9, 1], coupling=coupling, length_cells=length)
    c = mb.coherent_members(cum, 16, seed=[9, 2], coupling=coupling, length_cells=length)
    assert np.array_equal(a, b, equal_nan=True) and not np.array_equal(a, c, equal_nan=True)


def test_inputs_are_validated():
    good = np.array([[0.0], [0.5]])[:, :, None]
    with pytest.raises(ValueError, match="decrease"):
        mb.coherent_members(np.array([[0.0], [0.5], [0.4]])[:, :, None], 2, seed=0)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        mb.coherent_members(good * 3, 2, seed=0)
    with pytest.raises(ValueError, match="every lead"):
        mb.coherent_members(np.array([[0.0], [np.nan]])[:, :, None], 2, seed=0)
    with pytest.raises(ValueError, match="correlation length"):
        mb.coherent_members(good, 2, seed=0, coupling="copula")
    with pytest.raises(ValueError, match="coupling"):
        mb.coherent_members(good, 2, seed=0, coupling="independent")
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        mb.threshold(good, np.zeros((1, 1, 1)))


def test_burned_by_is_the_member_share_and_unknown_stays_nan():
    hours = np.array([[[0.0, 3.0, np.inf, np.nan]], [[0.0, 30.0, 1.0, np.nan]]])
    assert np.array_equal(mb.burned_by(hours, 24), np.array([[0.0, 0.5, 0.5, np.nan]]), equal_nan=True)


@settings(max_examples=80, deadline=None)
@given(st.lists(st.lists(st.floats(0, 1), min_size=4, max_size=4), min_size=1, max_size=5),
       st.lists(st.floats(1e-9, 1), min_size=1, max_size=5))
def test_property_burned_by_lead_matches_the_threshold_rule(cells, us):
    cum = np.sort(np.array(cells), axis=1).T[:, None, :]             # [L + 1 = 4, 1, n] non-decreasing
    u = np.broadcast_to(np.array(us)[:, None, None], (len(us), 1, cum.shape[2]))
    hours = mb.threshold(cum, u)
    for lead in range(4):
        assert np.array_equal(hours <= lead, u <= cum[lead])
    new = (hours > 0) & np.isfinite(hours)
    assert np.array_equal(np.ceil(hours[new]), m.hourly_arrival(hours, 3)[new])
