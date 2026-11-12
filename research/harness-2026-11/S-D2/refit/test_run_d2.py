"""Tests for the D2 refit wrapper's loss swap (needs torch and the forecast package)."""
import importlib.util
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("run_d2", HERE / "run_d2.py")
run_d2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_d2)


def test_endpoint_nll_matches_bernoulli_and_masks():
    p = torch.tensor([0.2, 0.9, 0.5, float("nan")], dtype=torch.float64)
    y = torch.tensor([1.0, 0.0, 1.0, 1.0], dtype=torch.float64)
    w = torch.tensor([1.0, 2.0, 0.5, 3.0], dtype=torch.float64)
    m = torch.tensor([True, True, False, True])
    val, wsum = run_d2.endpoint_nll(p, y, w, m)
    eps = run_d2.NLL_EPS
    expect = -(1.0 * torch.log(torch.tensor(0.2 + eps, dtype=torch.float64)) + 2.0 * torch.log1p(torch.tensor(-0.9 + eps, dtype=torch.float64)))
    assert float(val) == pytest.approx(float(expect), rel=1e-9)
    assert float(wsum) == pytest.approx(3.0)       # masked and NaN cells excluded


def test_gradient_is_nonzero_in_the_near_zero_tail():
    p = torch.tensor([1e-9, 1e-12], dtype=torch.float64, requires_grad=True)
    y = torch.tensor([1.0, 1.0], dtype=torch.float64)
    val, _ = run_d2.endpoint_nll(p, y, torch.ones(2, dtype=torch.float64), torch.tensor([True, True]))
    val.backward()
    assert (p.grad < -1e5).all()                    # strong push upward, unlike a clamp


def test_swap_is_scoped_to_fit_mean_field():
    from wildfire import survival
    original = survival.endpoint_brier
    seen = {}

    class FakePipeline:
        @staticmethod
        def fit_mean_field(*a, **kw):
            seen["inside"] = survival.endpoint_brier
            return "ok"

    fp = FakePipeline()
    run_d2.install_nll(fp)
    assert fp.fit_mean_field() == "ok"
    assert seen["inside"] is run_d2.endpoint_nll
    assert survival.endpoint_brier is original


def test_pins_match_current_sources():
    for path, expected in run_d2.PINNED.items():
        assert run_d2.sha256(path) == expected
