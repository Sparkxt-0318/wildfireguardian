"""Equality and unbiasedness tests for the drop-in conditional estimator of wildfire.rollout.simulate."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
HERE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.models import new_burn_probability  # noqa: E402
from wildfire.rollout import simulate  # noqa: E402
from cond_rollout import simulate_with_conditional  # noqa: E402


def stub(K):
    kern = torch.tensor(K)

    class Stub(torch.nn.Module):
        channel_names = ("x",)

        def forward(self, states, environment, *, channel_names, burned_area_valid, feature_valid,
                    dt_hours, boundary):
            return new_burn_probability(states, kern.expand(states.shape[0], -1, -1, -1), dt_hours=dt_hours,
                                        burned_area_valid=burned_area_valid, boundary=boundary)
    return Stub()


def inputs(init, valid=None):
    H, W = init.shape
    b = torch.tensor(init, dtype=torch.float64)[None]
    env = torch.zeros((1, H, W), dtype=torch.float64)
    bv = torch.ones_like(b, dtype=torch.bool) if valid is None else torch.tensor(valid)[None]
    return b, env, dict(channel_names=("x",), burned_area_valid=bv,
                        feature_valid=torch.ones_like(env, dtype=torch.bool))


@pytest.mark.parametrize("n,batch,boundary", [(300, 128, "zero"), (257, 64, "unknown"), (100, 100, "zero")])
def test_plain_output_bit_identical_to_simulate(n, batch, boundary):
    rng = np.random.default_rng(1)
    K = rng.uniform(0, 0.2, size=(25, 12, 13))
    K[12] = 0
    init = np.zeros((12, 13), bool)
    init[5:7, 6] = True
    valid = np.ones((12, 13), bool)
    valid[0, :3] = False  # unknown cells exercise the coverage envelope
    b, env, kw = inputs(init, valid)
    ref = simulate(stub(K), b, env, hours=[1.0, 2.0, 4.0], n_samples=n, seed=7,
                   trajectory_batch_size=batch, boundary=boundary, **kw)
    mine = simulate_with_conditional(stub(K), b, env, hours=[1.0, 2.0, 4.0], n_samples=n, seed=7,
                                     trajectory_batch_size=batch, boundary=boundary, **kw)
    for r, m in zip(ref, mine):
        assert torch.equal(r["details"].valid, m["valid"])
        assert torch.equal(torch.nan_to_num(r["details"].probability, nan=-1.0),
                           torch.nan_to_num(m["probability"], nan=-1.0))


def test_conditional_unbiased_against_plain_with_many_hits():
    rng = np.random.default_rng(2)
    K = rng.uniform(0, 0.15, size=(49, 14, 14))
    K[24] = 0
    init = np.zeros((14, 14), bool)
    init[6:8, 6:8] = True
    b, env, kw = inputs(init)
    n = 4000
    out = simulate_with_conditional(stub(K), b, env, hours=[2.0, 4.0], n_samples=n, seed=3,
                                    trajectory_batch_size=500, boundary="zero", **kw)
    for o in out:
        p = o["probability"][0].numpy()
        c = o["conditional"][0].numpy()
        se_plain = np.sqrt(p * (1 - p) / n)
        se_c = o["conditional_se"][0].numpy()
        m = p > 0.05  # enough hits for plain counting to be a meaningful comparison
        z = (c[m] - p[m]) / np.sqrt(se_plain[m] ** 2 + se_c[m] ** 2)
        assert np.all(np.abs(z) < 5)
        assert abs(z.mean()) < 0.5  # no systematic offset across cells
        # Y is a compensator sum, not capped at 1: it reduces variance for small p (the use case) but
        # can exceed the Bernoulli variance for cells that are likely to burn. Assert only the former.
        low = (p > 0.01) & (p < 0.15)
        if low.sum() >= 5:
            assert np.median(se_c[low] / se_plain[low]) < 1.0


def test_conditional_exact_on_hourly_chain_and_resolves_below_1_over_n():
    a, b2, c3 = 1.0, 0.6, 0.0005
    K = np.zeros((9, 1, 4))
    K[3, 0, 1] = a   # target (0,1) reads source (0,0): offset (0,-1) -> channel 3
    K[3, 0, 2] = b2
    K[3, 0, 3] = c3
    init = np.array([[True, False, False, False]])
    bt, env, kw = inputs(init)
    n = 2000
    out = simulate_with_conditional(stub(K), bt, env, hours=[3.0], n_samples=n, seed=5,
                                    trajectory_batch_size=500, boundary="zero", **kw)[0]
    pa, pb, pc = (1 - math.exp(-a)), (1 - math.exp(-b2)), (1 - math.exp(-c3))
    # hourly recursion, 3 steps: cell 1 by step 1..3; cell 2 needs cell 1 burned at an earlier step
    exact1 = 1 - (1 - pa) ** 3
    exact2 = pa * (1 - (1 - pb) ** 2) + (1 - pa) * pa * pb
    exact3 = pa * pb * pc  # only path: cells 1, 2, 3 ignite at steps 1, 2, 3
    for j, e in ((1, exact1), (2, exact2), (3, exact3)):
        est = float(out["conditional"][0, 0, j])
        se = float(out["conditional_se"][0, 0, j])
        assert abs(est - e) <= 5 * se + 1e-12, (j, est, e, se)
    assert exact3 < 1.0 / n  # far below the 1/n resolution of hit counting
    assert float(out["conditional"][0, 0, 3]) > 0


def test_pilot_weighted_combination_unbiased_and_never_much_worse():
    """Iris option (b): weights from an independent pilot; combination unbiased and, per cell, about as
    good as the better of hit counting and Y (including p > 0.9 where Y alone was ~4x worse)."""
    from cond_rollout import combined_estimate, pilot_weights
    rng = np.random.default_rng(2)
    K = rng.uniform(0, 0.15, size=(49, 14, 14))
    K[24] = 0
    init = np.zeros((14, 14), bool)
    init[6:8, 6:8] = True
    b, env, kw = inputs(init)
    pilot = simulate_with_conditional(stub(K), b, env, hours=[4.0], n_samples=1000, seed=101,
                                      trajectory_batch_size=500, boundary="zero", **kw)[0]
    main = simulate_with_conditional(stub(K), b, env, hours=[4.0], n_samples=4000, seed=202,
                                     trajectory_batch_size=500, boundary="zero", **kw)[0]
    w = pilot_weights(pilot["moments"])
    est, se, clipped = combined_estimate(main["moments"], w)
    n = 4000
    p = main["probability"][0].numpy()
    e = est[0].numpy()
    s = se[0].numpy()
    sp = np.sqrt(p * (1 - p) / n)
    sy = main["conditional_se"][0].numpy()
    m = (p > 0.05) & (p < 0.95)
    z = (e[m] - p[m]) / np.sqrt(sp[m] ** 2 + s[m] ** 2)
    assert np.all(np.abs(z) < 5) and abs(z.mean()) < 0.5
    hi = p > 0.9
    assert np.median(s[hi] / np.minimum(sp[hi], sy[hi])) < 1.3
    lo = (p > 0.0) & (p < 0.5)
    assert lo.sum() >= 5
    assert np.median(s[lo] / sp[lo]) < 1.0
    assert float(clipped.min()) >= 0 and float(clipped.max()) <= 1


def _c651_case(seed=0, H=18, W=17):
    from wildfire.inference import load_trained_model
    ckpt = REPO / ("forecast/runs/20261010_categorical_balanced_benchmark/candidates/"
                   "mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt")
    model = load_trained_model(ckpt)
    names = model.channel_names
    rng = np.random.default_rng(seed)
    env = np.zeros((len(names), H, W), dtype=np.float32)
    env[0] = rng.normal(25, 5, (H, W))           # temperature_2m
    env[1] = rng.normal(4, 2, (H, W))            # wind eastward (strong, so spread is non-trivial)
    env[2] = rng.normal(-2, 2, (H, W))           # wind northward
    env[3] = rng.uniform(0, 30, (H, W))          # slope
    env[4] = rng.uniform(20, 90, (H, W))         # tree cover
    biome = rng.integers(0, 14, (H, W))
    for c in range(14):
        env[5 + c] = (biome == c)
    init = np.zeros((H, W), bool)
    init[8:10, 7:9] = True
    e = torch.tensor(env, dtype=model.mean.dtype)[None]
    b = torch.tensor(init, dtype=e.dtype)[None, None]
    kw = dict(channel_names=names, burned_area_valid=torch.ones_like(b, dtype=torch.bool),
              feature_valid=torch.ones_like(e, dtype=torch.bool))
    return model, b, e, kw


@pytest.mark.parametrize("cache", [False, True])
def test_bit_identical_to_simulate_on_c651_with_fractional_endpoint_and_cache(cache):
    """Owen's scope gap: the scored forecast-v2 path uses step_durations (fractional final interval) and
    cache_environment_kernels=True with the real MixedNonnegativeKernel checkpoint."""
    model, b, e, kw = _c651_case()
    common = dict(hours=[2.0, 3.4], n_samples=203, seed=11, trajectory_batch_size=64, boundary="zero",
                  step_durations=[1.0, 1.0, 1.0, 0.4], cache_environment_kernels=cache, **kw)
    ref = simulate(model, b, e, **common)
    mine = simulate_with_conditional(model, b, e, **common)
    for r, m in zip(ref, mine):
        assert torch.equal(r["details"].valid, m["valid"])
        assert torch.equal(torch.nan_to_num(r["details"].probability, nan=-1.0),
                           torch.nan_to_num(m["probability"], nan=-1.0))
    assert float(torch.nan_to_num(ref[-1]["details"].probability).sum()) > 0  # something spread


def test_cache_path_is_actually_taken_for_c651():
    from wildfire.rollout_cache import prepare_transition
    model, b, e, kw = _c651_case()
    prepared = prepare_transition(model, e[0], kw["feature_valid"][0], channel_names=kw["channel_names"],
                                  batch_size=4, boundary="zero")
    assert prepared is not None
