"""Arrival-time ensemble metrics on SYNTHETIC fixtures: hand-computed values and known identities."""
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from scipy import stats

from firecast_lab import metrics as m

H = 24


def test_hourly_arrival_lattice_and_censoring():
    hours = np.array([-1.0, 0.0, 0.2, 1.0, 1.0001, 23.5, 24.0, 24.0001, np.inf, -np.inf, np.nan])
    expected = np.array([0, 0, 1, 1, 2, 24, 24, 25, 25, 0, np.nan])
    assert np.array_equal(m.hourly_arrival(hours, H), expected, equal_nan=True)


def _kernel_crps(x, y, fair=False):
    """Gneiting & Raftery (2007) kernel form on the censored lattice values."""
    k = len(x)
    spread = np.abs(x[:, None] - x[None, :]).sum()
    return np.abs(x - y).mean() - spread / (2 * k * (k - 1) if fair else 2 * k * k)


def test_crps_hand_value_standard_and_fair():
    # Members burn in hours 2, 3, 3 and one never (25); the observation burns in hour 3.
    # Lattice: F_2 = 1/4, F_3..24 = 3/4 -> 0.0625 + 22 * 0.0625 = 1.4375; the fair correction removes all of it.
    members = np.array([2, 3, 3, 25], float)[:, None]
    obs, mask = np.array([3.0]), np.ones(1, bool)
    assert m.crps_arrival(members, obs, mask, H) == pytest.approx(1.4375)
    assert m.crps_arrival(members, obs, mask, H, fair=True) == pytest.approx(0.0)
    assert _kernel_crps(members[:, 0], 3.0) == pytest.approx(1.4375)


def test_crps_deterministic_is_censored_absolute_error():
    mask = np.ones(3, bool)
    member = np.array([[3.0, 3.0, 25.0]])
    obs = np.array([7.0, 25.0, 25.0])
    assert np.allclose(m.crps_arrival_terms(member, obs, mask, H), [4.0, 22.0, 0.0])


def test_crps_equals_brier_summed_over_hourly_leads():
    rng = np.random.default_rng(4)                                             # SYNTHETIC
    members = rng.integers(1, H + 2, size=(16, 9, 8)).astype(float)
    obs = rng.integers(1, H + 2, size=(9, 8)).astype(float)
    mask = rng.random((9, 8)) < 0.8
    by_lead = sum(m.brier((obs <= i).astype(float), (members <= i).mean(axis=0), mask) for i in range(1, H + 1))
    assert m.crps_arrival(members, obs, mask, H) == pytest.approx(by_lead)
    assert m.crps_arrival(np.repeat(obs[None], 5, axis=0), obs, mask, H) == 0.0         # perfect ensemble


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(1, H + 1), min_size=2, max_size=8), st.integers(1, H + 1))
def test_crps_lattice_matches_kernel_form(members, obs):
    x = np.array(members, float)
    got = m.crps_arrival(x[:, None], np.array([float(obs)]), np.ones(1, bool), H)
    fair = m.crps_arrival(x[:, None], np.array([float(obs)]), np.ones(1, bool), H, fair=True)
    assert got == pytest.approx(_kernel_crps(x, obs))
    assert fair == pytest.approx(_kernel_crps(x, obs, fair=True))


@pytest.mark.parametrize("bad_obs, bad_member", [(0.0, 3.0), (np.nan, 3.0), (3.0, np.nan), (3.5, 3.0), (26.0, 3.0)])
def test_crps_rejects_unscorable_values_inside_the_mask(bad_obs, bad_member):
    members = np.array([[bad_member, 2.0]])
    obs = np.array([bad_obs, 2.0])
    with pytest.raises(ValueError):
        m.crps_arrival(members, obs, np.ones(2, bool), H)
    assert m.crps_arrival(members, obs, np.array([False, True]), H) == 0.0   # fine once masked out


def test_rank_histogram_hand_ranks():
    members = np.array([[2.0, 2.0, 5.0], [3.0, 4.0, 6.0]])                   # K = 2, three cells
    obs = np.array([1.0, 9.0, 5.5])
    out = m.rank_histogram(members, obs, np.ones(3, bool), seed=0)
    assert out["counts"] == [1, 1, 1] and out["fully_tied"] == 0 and out["cells"] == 3


def test_rank_histogram_breaks_full_ties_uniformly():
    k, n = 4, 50_000                                                           # SYNTHETIC: all censored
    out = m.rank_histogram(np.full((k, n), 25.0), np.full(n, 25.0), np.ones(n, bool), seed=7)
    assert out["fully_tied"] == n
    assert np.allclose(np.array(out["counts"]) / n, 1 / (k + 1), atol=0.01)


def test_rank_histogram_flat_when_exchangeable_and_u_shaped_when_overconfident():
    rng = np.random.default_rng(5)                                             # SYNTHETIC
    k, n = 9, 20_000
    centre = rng.normal(size=n)
    obs = centre + rng.normal(size=n)
    exchangeable = m.rank_histogram(centre + rng.normal(size=(k, n)), obs, np.ones(n, bool), seed=1)["counts"]
    assert stats.chisquare(exchangeable).pvalue > 0.001
    narrow = m.rank_histogram(centre + 0.3 * rng.normal(size=(k, n)), obs, np.ones(n, bool), seed=1)["counts"]
    assert min(narrow[0], narrow[-1]) > 3 * max(narrow[1:-1])


def test_spread_skill_hand_values():
    # Cell A: members 0, 2 (s^2 = 2), mean error 0. Cell B: members 1, 1 (s^2 = 0), error 2.
    # spread = sqrt(1.5 * 1), rmse = sqrt(2), ratio = sqrt(3/4).
    members = np.array([[0.0, 1.0], [2.0, 1.0]])
    out = m.spread_skill(members, np.array([1.0, 3.0]), np.ones(2, bool), bins=2)
    assert out["spread"] == pytest.approx(np.sqrt(1.5)) and out["rmse"] == pytest.approx(np.sqrt(2.0))
    assert out["ratio"] == pytest.approx(np.sqrt(0.75)) and out["members"] == 2
    assert [r["cells"] for r in out["rows"]] == [1, 1] and out["rows"][0]["spread"] == 0.0


def _exchangeable(k, n, seed):
    rng = np.random.default_rng(seed)                                          # SYNTHETIC, spread varies by cell
    centre, scale = rng.normal(size=n), rng.uniform(0.5, 3.0, size=n)
    return centre + scale * rng.normal(size=(k, n)), centre + scale * rng.normal(size=n)


def test_spread_skill_ratio_is_one_for_exchangeable_members():
    members, obs = _exchangeable(10, 40_000, 6)
    out = m.spread_skill(members, obs, np.ones(obs.size, bool))
    assert out["ratio"] == pytest.approx(1.0, abs=0.02)                       # the overall ratio is unbiased
    # Rows binned by the ensemble's own sample variance are biased at small K (selection on s^2) ...
    assert out["rows"][0]["ratio"] < 0.9 and out["rows"][-1]["ratio"] > 1.1
    # ... and not at the ensemble sizes Track A uses.
    members, obs = _exchangeable(256, 10_000, 7)
    assert all(r["ratio"] == pytest.approx(1.0, abs=0.08)
               for r in m.spread_skill(members, obs, np.ones(obs.size, bool))["rows"])
    assert m.spread_skill(np.repeat(obs[None], 4, axis=0) + 1.0, obs, np.ones(obs.size, bool))["ratio"] == 0.0


def test_members_need_a_leading_member_axis():
    obs, mask = np.array([3.0, 4.0]), np.ones(2, bool)
    for call in (lambda: m.rank_histogram(obs, obs, mask, seed=0), lambda: m.spread_skill(obs, obs, mask),
                 lambda: m.crps_arrival(obs, obs, mask, H)):
        with pytest.raises(ValueError, match="members"):
            call()
