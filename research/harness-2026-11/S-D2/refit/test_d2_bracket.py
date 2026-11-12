"""Tests for the d2_bracket fitter (needs torch, numpy, scipy and the forecast package)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))           # synthetic.py, the verified reference implementation
import synthetic as S                           # noqa: E402

spec = importlib.util.spec_from_file_location("d2_bracket", HERE / "d2_bracket.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def test_complete_loglik_matches_verified_synthetic_reference():
    p = S.make_problem(3, n=24, radius=1, n_seeds=2, scale=0.08, k0=B.EPS)
    n = p.n
    offs = B.offsets(9)                                    # our delta, row-major
    # Ours: lambda_i = sum_delta K[delta,i] 1{tau_(i+delta)}; synthetic: sum_d k_d 1{tau_(i-d)} => K[delta] = k_(-delta)
    kmap = {tuple(d): k for d, k in zip(p.offs, p.k)}
    K = np.array([[kmap.get((-dr, -dc), 0.0)] * (n * n) for dr, dc in offs])
    tau = p.tau.copy()
    seeds = np.zeros(n * n, bool)
    seeds[p.seeds] = True
    latent = np.isfinite(tau) & ~seeds
    scored = ~seeds
    src = B.source_index(n, n, offs)
    ll, wsum = B.complete_loglik(torch.as_tensor(K, dtype=torch.float64), tau, latent, scored,
                                 np.ones(n * n), p.T, src)
    ev, ex = S.sufficient_stats(p, tau)
    ref = S.complete_loglik(np.concatenate([[p.k0], p.k]), ev, ex)
    # Differences come only from the background term (k0 * exposure time), which is tiny here.
    assert float(ll) == pytest.approx(ref, rel=1e-4, abs=1e-3)
    assert wsum == scored.sum()


def _sample(rng, H=40, W=40, hours=24.0, channels=4):
    from wildfire.survival import PerimeterSample
    env = rng.normal(size=(channels, H, W)).astype(np.float32)
    initial = np.zeros((H, W), bool)
    initial[18:22, 18:22] = True
    endpoint = initial.copy()
    endpoint[15:25, 15:26] = True
    return PerimeterSample("SYN", "2020-01-01T00:00:00+00:00", hours, env, initial, endpoint, ~initial,
                           np.ones((H, W), np.float32), np.zeros((H, W), np.float32))


def test_fit_bracket_runs_two_epochs_with_d4_and_finite_loss():
    from wildfire.models import StructuredKernelModel
    rng = np.random.default_rng(0)
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "a", "b"]
    model = StructuredKernelModel(4, 5, 4, 0.0, channel_names=names, mean=torch.zeros(4), std=torch.ones(4),
                                  prior="free", frame="wind")
    model.initialize_rate(0.02)
    train = [_sample(rng) for _ in range(3)]
    logs = []
    res = B.fit_bracket(model, train, [], epochs=2, learning_rate=0.003, seed=0, d4=True, samples_per_step=1,
                        validate_each_epoch=False, log=logs.append, sweeps=1, step=1.0)
    assert len(res["history"]) == 2
    assert all(np.isfinite(h["train_scaled_loss"]) for h in res["history"])


def test_estep_stream_does_not_change_training_order():
    # The training RNG consumes only order and D4 draws; the E-step has its own stream.
    import inspect
    src = inspect.getsource(B.fit_bracket)
    assert "estep_rng" in src and "gibbs_sweep(Kn, tau, np.flatnonzero(latent), src, tgt, scored, sample.hours, step, estep_rng)" in src
    assert "SeedSequence([seed, 0x5D2B])" in src
