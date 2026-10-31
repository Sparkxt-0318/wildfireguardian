"""Property tests: monotonicity in burning, consistency with cell-level data, unknown handling."""
import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from helpers import brute_cells, make_set

INF, NAN = np.inf, np.nan
TIMES = st.sampled_from([-40.0, 0.0, 10.0, 20.0, 30.0, 50.0, 80.0, INF, NAN])
SET = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@st.composite
def scenario_and_query(draw):
    H = draw(st.integers(3, 5))
    W = draw(st.integers(3, 5))
    K = draw(st.integers(1, 2))
    ig = np.array(draw(st.lists(TIMES, min_size=K * H * W, max_size=K * H * W))).reshape(K, H, W)
    dur = np.array(draw(st.lists(st.sampled_from([0.0, 10.0, 25.0, 60.0]), min_size=K * H * W,
                                 max_size=K * H * W))).reshape(K, H, W)
    ex = np.where(np.isfinite(ig), ig + dur, ig)
    ex = np.where(ig == -INF, 30.0, ex)
    coords = st.sampled_from([-20.0, 0.0, 50.0, 100.0, 130.0, 150.0, 200.0, 250.0, 300.0, 520.0])
    n = draw(st.integers(1, 3))
    g = np.array([[draw(coords), draw(coords)] for _ in range(n)])
    a = draw(st.sampled_from([-30.0, 0.0, 10.0, 20.0, 45.0]))
    b = a + draw(st.sampled_from([0.0, 5.0, 10.0, 30.0, 70.0]))
    return ig, ex, g, a, b


def more_burning(ig, ex, rng):
    """Add burning: earlier ignitions, later extinctions, new burning cells. Unknown stays unknown."""
    ig2, ex2 = ig.copy(), ex.copy()
    known = ~np.isnan(ig)
    pick = known & (rng.random(ig.shape) < 0.5)
    never = pick & (ig == INF)
    ig2[never] = rng.choice([-10.0, 0.0, 15.0, 40.0], size=never.sum())
    ex2[never] = ig2[never] + 20.0
    burn = pick & np.isfinite(ig)
    ig2[burn] -= rng.choice([0.0, 5.0, 10.0], size=burn.sum())
    ex2[burn] += rng.choice([0.0, 5.0, 10.0], size=burn.sum())
    return ig2, ex2


@SET
@given(scenario_and_query(), st.integers(0, 2 ** 31 - 1))
def test_adding_burning_never_weakens_hazard(case, seed):
    ig, ex, g, a, b = case
    s1 = make_set(ig, ex, horizon=90.0)
    ig2, ex2 = more_burning(ig, ex, np.random.default_rng(seed))
    s2 = make_set(ig2, ex2, horizon=90.0)
    for h1, h2 in zip(s1.query(g, a, b), s2.query(g, a, b)):
        if h1.contact is True:
            assert h2.contact is True
        assert h2.supported == h1.supported            # support depends on knowledge, not burning
        tol = 1e-9
        assert h2.flux_upper >= h1.flux_upper * (1 - tol)
        assert h2.dose_upper >= h1.dose_upper * (1 - tol)
        assert h2.flux_lower >= h1.flux_lower * (1 - tol)
        assert h2.dose_lower >= h1.dose_lower * (1 - tol)


@SET
@given(scenario_and_query())
def test_segment_result_is_consistent_with_cell_data(case):
    ig, ex, g, a, b = case
    s = make_set(ig, ex, horizon=90.0)
    cells, outside = brute_cells(s, g)
    for k, hz in enumerate(s.query(g, a, b)):
        burning = [(r, c) for r, c in cells if s.supported[k, r, c] and s.extinguish_s[k, r, c] > s.ignite_s[k, r, c]
                   and s.ignite_s[k, r, c] <= b and s.extinguish_s[k, r, c] > a]
        unknown = any(not s.supported[k, r, c] for r, c in cells)
        supported = not (unknown or outside or b > 90.0)
        assert hz.supported == supported
        assert hz.contact == (True if burning else (False if supported else None))
        assert 0.0 <= hz.flux_lower <= hz.flux_upper and 0.0 <= hz.dose_lower <= hz.dose_upper


@SET
@given(scenario_and_query())
def test_marking_cells_unknown_never_adds_support(case):
    ig, ex, g, a, b = case
    s1 = make_set(ig, ex, horizon=90.0)
    ig2, ex2 = ig.copy(), ex.copy()
    ig2[..., 1, :] = NAN
    ex2[..., 1, :] = NAN
    s2 = make_set(ig2, ex2, horizon=90.0)
    for h1, h2 in zip(s1.query(g, a, b), s2.query(g, a, b)):
        assert not (h2.supported and not h1.supported)
        if h2.contact is False:
            assert h1.contact is False
        assert h2.flux_upper >= h1.flux_upper * (1 - 1e-9)
        assert h2.dose_upper >= h1.dose_upper * (1 - 1e-9)
