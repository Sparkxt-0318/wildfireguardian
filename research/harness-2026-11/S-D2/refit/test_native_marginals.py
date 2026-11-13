"""Tests for native multi-observation cumulative marginals (A1 §5.2)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("native_marginals", HERE / "native_marginals.py")
NM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NM)
sys.path.insert(0, str(HERE.parents[1] / "S-D9"))


def _model_and_sample(hours=12.0, seed=0):
    from wildfire.models import StructuredKernelModel
    from wildfire.survival import PerimeterSample
    rng = np.random.default_rng(seed)
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "a", "b"]
    torch.manual_seed(seed)
    model = StructuredKernelModel(4, 5, 4, 0.0, channel_names=names, mean=torch.zeros(4), std=torch.ones(4),
                                  prior="free", frame="wind")
    model.initialize_rate(0.05)
    H = W = 32
    env = rng.normal(size=(4, H, W)).astype(np.float32)
    initial = np.zeros((H, W), bool)
    initial[14:18, 14:18] = True
    s = PerimeterSample("SYN", "2020-01-01T00:00:00+00:00", hours, env, initial, initial.copy(), ~initial,
                        np.ones((H, W), np.float32), np.zeros((H, W), np.float32))
    return model, s


def test_single_lead_equals_sample_forecast_endpoint():
    from wildfire.survival import sample_forecast
    model, s = _model_and_sample(hours=12.0)
    with torch.no_grad():
        p, v = sample_forecast(model, s)
    cdf, val = NM.cumulative_marginals(model, s, [12.0])
    assert np.array_equal(cdf[0], p.numpy().astype(np.float64)) and np.array_equal(val[0], v.numpy())


def test_whole_hour_leads_match_separate_runs_and_are_monotone():
    from dataclasses import replace
    from wildfire.survival import sample_forecast
    model, s = _model_and_sample()
    leads = [6.0, 12.0, 30.0]
    cdf, val = NM.cumulative_marginals(model, s, leads)
    for j, t in enumerate(leads):
        with torch.no_grad():
            p, _ = sample_forecast(model, replace(s, hours=t))
        assert np.allclose(cdf[j], p.numpy(), atol=0, rtol=0)
    assert (np.diff(cdf, axis=0) >= 0).all() and cdf[-1].max() > cdf[0].max()


def test_fractional_leads_break_exactly():
    assert NM.lead_step_durations([1.5, 3.0]) == [1.0, 0.5, 1.0, 0.5]
    with pytest.raises(ValueError):
        NM.lead_step_durations([3.0, 3.0])


def test_arrival_entries_roundtrip_through_sd9bench(tmp_path):
    from sd9bench.arrival import load_arrival
    model, s = _model_and_sample()
    H, W = s.initial.shape
    hours = np.array([0.0, 12.0, 24.0, 60.0])
    states = np.zeros((4, H, W), bool)
    states[0] = s.initial
    states[1] = states[0]; states[1][13:19, 13:19] = True
    states[2] = states[1]; states[2][12:20, 12:20] = True
    states[3] = states[2]; states[3][10:22, 10:22] = True
    fc = {}
    for c in (0, 1, 2):
        later = [k for k in range(c + 1, 4) if 0 < hours[k] - hours[c] <= 48]
        fc[c] = NM.cumulative_marginals(model, s, list(hours[later] - hours[c]))
    e = NM.arrival_entries([0, 1, 2], hours, states, fc)
    # cutoff 0 has leads 12, 24 (60 is beyond 48 h); cutoff 1: 12, 48; cutoff 2: 36
    assert e["lead_hours"].shape == (3, 2)
    assert np.allclose(e["lead_hours"][0], [12, 24]) and np.allclose(e["lead_hours"][2, :1], [36])
    np.savez(tmp_path / "SYN.npz", cutoff=e["cutoff"], n_leads=e["n_leads"], arrival_bin=e["arrival_bin"],
             lead_hours=e["lead_hours"], cdf_d2=e["cdf"])
    A = load_arrival([tmp_path / "SYN.npz"])
    assert len(A.n_leads) == len(e["cutoff"])
    valid = np.arange(A.cdf["d2"].shape[1])[None, :] < A.n_leads[:, None]
    assert np.isfinite(A.cdf["d2"][valid]).all()
    # a cell mapped at survey 1 from cutoff 0 has bin 0; an untouched far cell has bin n_leads
    i0 = np.flatnonzero(e["cutoff"] == 0)
    assert set(np.unique(e["arrival_bin"][i0])) <= {0, 1, 2} and (e["arrival_bin"][i0] == 2).any()
