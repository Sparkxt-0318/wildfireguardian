import importlib.util
from pathlib import Path
import subprocess
import numpy as np
import pytest
torch = pytest.importorskip("torch", reason="trajectory export tests require the pinned forecast environment")
from wildfire.models import BurnProbability
from wildfire.rollout import simulate, _generator

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("_v3_export", ROOT / "experimental/scenario-members/export_v3.py")
export = importlib.util.module_from_spec(spec); spec.loader.exec_module(export)


class Toy(torch.nn.Module):
    channel_names = ("fixture",)
    def __init__(self):
        super().__init__(); self.anchor = torch.nn.Parameter(torch.tensor(0.0, dtype=torch.float64))
    def forward(self, b, environment, *, burned_area_valid, feature_valid, **kwargs):
        q = 0.5 * torch.roll(b, 1, -1) * (1 - b)
        valid = burned_area_valid & feature_valid.all(dim=-3, keepdim=True)
        return BurnProbability(q, valid, torch.ones_like(q), valid)


def controls():
    b = torch.zeros((1, 3, 5), dtype=torch.float64); b[0, 1, 1] = 1
    return dict(burned_area=b, environmental_data=torch.zeros_like(b),
                channel_names=("fixture",), burned_area_valid=torch.ones_like(b, dtype=torch.bool),
                feature_valid=torch.ones_like(b, dtype=torch.bool))


def test_callback_none_matches_original_bit_for_bit_and_observer_cannot_mutate():
    source = subprocess.check_output(["git", "-C", str(ROOT), "show", "59f3187d7:forecast/wildfire/rollout.py"], text=True)
    original = {"__name__": "wildfire._original_rollout", "__package__": "wildfire"}
    exec(compile(source, "<original_rollout>", "exec"), original)
    c = dict(hours=[1, 2, 3], n_samples=37, seed=89, trajectory_batch_size=16, boundary="zero", **controls())
    before = torch.random.get_rng_state().clone()
    a = original["simulate"](Toy(), **c)
    b = simulate(Toy(), **c, trajectory_callback=None)
    seen = []
    def observer(block, states, hour):
        assert states.dtype == torch.bool
        seen.append((block, states.shape[0], hour))
        states.fill_(False)
    d = simulate(Toy(), **c, trajectory_callback=observer)
    assert len(seen) == 9
    assert seen[-1] == (2, 5, 3)
    for aa, bb, dd in zip(a, b, d):
        for key in ("burned_probability", "mc_standard_error", "confidence_lower", "confidence_upper"):
            assert torch.equal(aa[key], bb[key]) and torch.equal(bb[key], dd[key])
        assert torch.equal(aa["details"].valid, bb["details"].valid)
    assert torch.equal(before, torch.random.get_rng_state())


class Wrapper:
    predictor = Toy()
    def _prepare_prediction_inputs(self, sample):
        return sample, {}
    def _initialize_burned_area(self, inputs, geometry, missing):
        return inputs, {"assumed_unburned_cells": 0}


def test_first_burn_reproduces_full_mc_mean_and_stream_identity():
    arrays, meta = export.collect_trajectories(Wrapper(), controls(), horizon_hours=3,
                                               n_samples=37, trajectory_count=37, seed=89,
                                               trajectory_batch_size=16, boundary="zero")
    first = arrays["trajectory_first_burn_hour"]
    assert first.dtype == np.int16 and first.shape == (37, 3, 5)
    for h in range(1, 4):
        observed = ((first >= 0) & (first <= h)).mean(axis=0)
        np.testing.assert_allclose(observed, arrays["trajectory_cumulative_probability"][h - 1], rtol=0, atol=1e-15)
    expected = _generator(89, 0, 2, 0).initial_seed()
    assert int(arrays["trajectory_seed"].view(np.uint64)[-1]) == expected
    assert arrays["trajectory_offset_in_block"][-1] == 4
    assert meta["trajectory_batch_size"] == 16


def test_unknown_is_never_exported_as_never_burned():
    sample = controls(); sample["burned_area_valid"][0, 0, 0] = False
    arrays, _ = export.collect_trajectories(Wrapper(), sample, n_samples=8, trajectory_count=8,
                                            trajectory_batch_size=4, boundary="zero")
    assert np.all(arrays["trajectory_first_burn_hour"][:, 0, 0] == -2)
