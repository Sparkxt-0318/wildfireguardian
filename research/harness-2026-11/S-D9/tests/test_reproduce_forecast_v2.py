"""Correctness check: the harness reproduces the committed forecast-v2 canonical held-out scores.

Every pooled and per-fire metric of all 16 predictors, every paired whole-fire
Brier interval and every paired BSS interval in research/forecast-v2/RESULTS.json
('heldout') is recomputed from the committed per-fire entry files and compared.
The tolerance is 1e-12 relative, which is floating-point summation order only.
Integer counts must match exactly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sd9bench import load, score

ROOT = Path(__file__).resolve().parents[4]
HELDOUT = ROOT / "forecast/runs/20261030_perimeter_trained/execution_v3/heldout"
RESULTS = ROOT / "research/forecast-v2/RESULTS.json"


@pytest.fixture(scope="module")
def pair():
    published = json.loads(RESULTS.read_text())["heldout"]
    # c651_mc used 1,024 trajectories (RESULTS.json heldout_inputs.n_samples).
    n = json.loads(RESULTS.read_text())["heldout_inputs"]["n_samples"]
    ours = score(load(sorted(HELDOUT.glob("*.npz"))), mc_trajectories={"c651_mc": n})
    return published, ours


def compare(a, b, path=""):
    """Every key of published value a must exist in b and match."""
    if isinstance(a, dict):
        assert isinstance(b, dict), path
        for k, v in a.items():
            assert k in b, f"{path}/{k} missing from harness output"
            compare(v, b[k], f"{path}/{k}")
    elif isinstance(a, list):
        assert isinstance(b, (list, tuple)) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, f"{path}[{i}]")
    elif isinstance(a, bool) or a is None or isinstance(a, str):
        assert a == b, f"{path}: {a!r} != {b!r}"
    elif isinstance(a, int):
        assert a == b, f"{path}: {a} != {b}"
    else:
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15), f"{path}: {a!r} != {b!r}"


def test_cohort_counts(pair):
    published, ours = pair
    assert ours["entries"] == published["entries"] == 1705079
    assert ours["positives"] == published["positives"] == 8520
    assert ours["fires"] == published["fires"]


def test_all_models_pooled_and_per_fire(pair):
    published, ours = pair
    assert set(ours["models"]) == set(published["models"])
    assert len(published["models"]) == 16
    for name, record in published["models"].items():
        compare(record, ours["models"][name], f"models/{name}")


def test_all_paired_whole_fire_intervals(pair):
    published, ours = pair
    assert set(published["paired"]) <= set(ours["paired"])
    assert len(published["paired"]) == 30
    for key, record in published["paired"].items():
        compare(record, ours["paired"][key], f"paired/{key}")


def test_headline_primary_values(pair):
    """The README headline numbers, as written in research/forecast-v2/README.md."""
    _, ours = pair
    d = ours["paired"]["d4_wind_seed0__vs__persistence"]
    assert round(d["point_difference"], 13) == round(-0.0000699497011684351, 13)
    assert [round(x, 10) for x in d["percentile_95_interval"]] == [-0.0001376572, 0.0000228664]
    assert round(ours["models"]["d4_wind_seed0"]["pooled"]["brier"], 9) == 0.004926886
