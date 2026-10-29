"""Track 1C, Contract A: the optional ``trajectory_callback`` of ``rollout.simulate``.

The callback must be an observer only: with it absent the outputs, random draws
and global RNG state are byte-identical to the released behaviour, and with it
present the outputs are still identical while the callback sees every trajectory
state after every synchronous update.
"""
import math

import pytest
import torch

from tests.test_rollout import CHANNELS, _bayesian, _component, _inputs
from wildfire import rollout


@pytest.fixture(autouse=True)
def _few_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _run(predictor, *, callback=None, n_samples=100, batch=32, hours=(1, 2, 3), seed=41):
    burned, features = _inputs(rate=math.log(2))
    options = dict(channel_names=CHANNELS,
                   burned_area_valid=torch.ones_like(burned, dtype=torch.bool),
                   feature_valid=torch.ones_like(features, dtype=torch.bool),
                   hours=list(hours), n_samples=n_samples, seed=seed,
                   trajectory_batch_size=batch, boundary="zero")
    if callback is not None:
        options["trajectory_callback"] = callback
    return rollout.simulate(predictor, burned, features, **options)


def _assert_identical(left, right):
    assert len(left) == len(right)
    for a, b in zip(left, right):
        assert a["metadata"] == b["metadata"]
        for name in ("burned_probability", "mc_standard_error", "confidence_lower", "confidence_upper"):
            torch.testing.assert_close(a[name], b[name], rtol=0, atol=0, equal_nan=True)
        for name in ("probability", "valid", "rate", "rate_valid"):
            torch.testing.assert_close(getattr(a["details"], name), getattr(b["details"], name),
                                       rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("bayesian", [False, True])
def test_default_path_is_byte_identical_and_callback_is_an_observer(bayesian):
    predictor = (_bayesian([_component(3, -math.log(0.8)), _component(5, -math.log(0.2))],
                           [math.log(0.5), math.log(0.5)]).predictor
                 if bayesian else _component())
    torch.manual_seed(1234)
    state_before = torch.get_rng_state().clone()
    reference = _run(predictor)
    assert torch.equal(torch.get_rng_state(), state_before)
    again = _run(predictor)
    _assert_identical(reference, again)
    calls = []

    def callback(block, states, step):
        calls.append((block, states.clone(), step))
        states.fill_(True)       # mutating the copy must not change the simulation
    observed = _run(predictor, callback=callback)
    assert torch.equal(torch.get_rng_state(), state_before)
    _assert_identical(reference, observed)
    assert calls, "callback was never called"


def test_callback_sees_every_block_and_step_and_reproduces_the_counts():
    predictor = _component()
    n_samples, batch, hours = 100, 32, (1, 2, 3)
    seen = {}

    def callback(block, states, step):
        assert states.dtype == torch.bool and states.ndim == 4 and states.shape[1] == 1
        seen[(block, step)] = states.clone()
    results = _run(predictor, callback=callback, n_samples=n_samples, batch=batch, hours=hours)
    blocks = (n_samples + batch - 1) // batch
    assert sorted(seen) == [(b, s) for b in range(blocks) for s in (1, 2, 3)]
    assert [seen[(b, 1)].shape[0] for b in range(blocks)] == [32, 32, 32, 4]
    burned, _ = _inputs()
    observed = (burned == 1).reshape(1, *burned.shape[-2:])
    for b in range(blocks):                      # burning is absorbing
        assert torch.all(seen[(b, 1)] <= seen[(b, 2)]) and torch.all(seen[(b, 2)] <= seen[(b, 3)])
    # First-burn hour per trajectory (Contract A coding) and exact agreement with the empirical probability (K = N).
    states = {s: torch.cat([seen[(b, s)] for b in range(blocks)])[:, 0] for s in (1, 2, 3)}
    first = torch.full(states[1].shape, -1, dtype=torch.int16)
    first[:, observed[0]] = 0
    for s in (3, 2, 1):
        first[states[s] & ~observed] = s
    for index, hour in enumerate(hours):
        probability = results[index]["details"].probability[0]
        empirical = ((first >= 1) & (first <= hour)).double().mean(dim=0)
        torch.testing.assert_close(empirical, torch.nan_to_num(probability, nan=0.0), rtol=0, atol=1e-12)


RELEASED_ROLLOUT_SHA256 = "116774602de1334908cb0c9236f327fcb6b32f0fd6334ccdd24db8eb4cf60efe"   # forecast/PUBLICATION_MANIFEST.json


def _released_module():
    """Rebuild the released rollout.py by deleting exactly the four added lines; load it as a separate module."""
    import hashlib
    import importlib.util
    import sys
    from pathlib import Path
    source = Path(rollout.__file__).read_text()
    added = ["    trajectory_callback=None,\n",
             next(line for line in source.splitlines(keepends=True) if line.lstrip().startswith("``trajectory_callback(")),
             "                if trajectory_callback is not None:\n",
             "                    trajectory_callback(block, states[:size] == 1, k + 1)\n"]
    released = source
    for line in added:
        assert released.count(line) == 1, line
        released = released.replace(line, "", 1)
    assert hashlib.sha256(released.encode()).hexdigest() == RELEASED_ROLLOUT_SHA256
    name = "wildfire._released_rollout_for_test"
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "wildfire"
    sys.modules[name] = module
    exec(compile(released, "released_rollout.py", "exec"), module.__dict__)
    return module


def test_only_the_callback_lines_differ_from_the_released_source_and_outputs_match_it():
    released = _released_module()
    predictor = _component()
    burned, features = _inputs(rate=math.log(2))
    options = dict(channel_names=CHANNELS, burned_area_valid=torch.ones_like(burned, dtype=torch.bool),
                   feature_valid=torch.ones_like(features, dtype=torch.bool), hours=[1, 2, 3], n_samples=100,
                   seed=41, trajectory_batch_size=32, boundary="zero")
    _assert_identical(released.simulate(predictor, burned, features, **options),
                      rollout.simulate(predictor, burned, features, **options))
