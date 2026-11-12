"""Unit tests on invented data for the S-D9 additions: file contract, strata and CRPS."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from sd9bench import load, score
from sd9bench.score import crps_ensemble, stratified


def write(path, **arrays):
    np.savez(path, **arrays)
    return path


def fire_file(tmp_path, name="F1", n=40, k=4, seed=0, **extra):
    rng = np.random.default_rng(seed)
    interval = np.repeat(np.arange(k), n // k)
    y = (rng.random(n) < 0.2).astype(np.int8)
    arrays = dict(interval=interval, y=y, hours=np.array([6.0, 18.0, 30.0, 42.0][:k]),
                  p_model=rng.random(n), p_persistence=np.zeros(n), p_dilation_best=rng.random(n) * 0.5)
    arrays.update(extra)
    return write(tmp_path / f"{name}.npz", **arrays)


# --- file contract ---------------------------------------------------------

def test_load_concatenates_and_maps_hours(tmp_path):
    a = fire_file(tmp_path, "A", seed=1)
    b = fire_file(tmp_path, "B", seed=2)
    e = load([b, a])
    assert e.fire.tolist()[:10] == ["A"] * 10            # sorted by fire
    assert e.hours.tolist()[:10] == [6.0] * 10           # hours indexed by interval
    assert set(e.predictions) == {"model", "persistence", "dilation_best"}


@pytest.mark.parametrize("bad", [
    dict(p_model=np.full(40, 1.5)),                       # out of range
    dict(p_model=np.full(40, np.nan)),                    # non-finite
    dict(y=np.full(40, 2, dtype=np.int8)),                # non-binary
    dict(interval=np.full(40, 9)),                        # index outside hours
    dict(hours=np.array([6.0, -1.0, 30.0, 42.0])),        # nonpositive horizon
    dict(dist_m=np.full(40, -1.0)),                       # negative distance
    dict(area_samples_model=np.ones((3, 5))),             # wrong K
])
def test_contract_violations_raise(tmp_path, bad):
    with pytest.raises(ValueError):
        load([fire_file(tmp_path, **bad)])


def test_mismatched_predictors_raise(tmp_path):
    a = fire_file(tmp_path, "A")
    b = write(tmp_path / "B.npz", interval=np.zeros(4, int), y=np.zeros(4, np.int8), hours=np.array([1.0]),
              p_model=np.zeros(4))
    with pytest.raises(ValueError, match="differ"):
        load([a, b])


def test_partial_optional_arrays_raise(tmp_path):
    a = fire_file(tmp_path, "A", dist_m=np.zeros(40))
    b = fire_file(tmp_path, "B")
    with pytest.raises(ValueError, match="dist_m"):
        load([a, b])


# --- strata ----------------------------------------------------------------

def test_horizon_strata_partition_entries(tmp_path):
    e = load([fire_file(tmp_path, "A", seed=3), fire_file(tmp_path, "B", seed=4)])
    rows = stratified(e, e.hours, (0, 12, 24, 36, 48), "h")
    assert sum(r["entries"] for r in rows) == len(e.y)
    assert [r["intervals"] for r in rows] == [2, 2, 2, 2]  # one interval per fire per bin
    assert all(r["fires"] == 2 for r in rows)
    # Within-stratum Brier equals the direct computation.
    use = e.hours <= 12
    assert rows[0]["models"]["model"]["brier"] == pytest.approx(np.mean((e.predictions["model"][use] - e.y[use]) ** 2))


def test_band_strata_need_dist(tmp_path):
    e = load([fire_file(tmp_path)])
    assert score(e, draws=50)["by_band"] == {"status": "UNAVAILABLE_NO_DIST_M"}
    e = load([fire_file(tmp_path, "G", dist_m=np.linspace(0, 8000, 40))])
    rows = score(e, draws=50)["by_band"]
    assert sum(r["entries"] for r in rows) == 40


def test_base_rate_bss(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50)
    pbar = e.y.mean()
    b = np.mean((e.predictions["model"] - e.y) ** 2)
    assert r["models"]["model"]["pooled"]["base_rate_bss"] == pytest.approx(1 - b / (pbar * (1 - pbar)))


# --- CRPS ------------------------------------------------------------------

def brute_crps(x, y):
    x = np.asarray(x, float)
    return np.abs(x - y).mean() - 0.5 * np.mean([abs(a - b) for a, b in itertools.product(x, x)])


@pytest.mark.parametrize("x,y", [([3.0], 5.0), ([1, 2, 3, 4], 2.5), ([0, 0, 10], 0.0), ([7, 1, 4, 4, 9], 20.0)])
def test_crps_matches_brute_force(x, y):
    assert crps_ensemble(np.array(x, float), y) == pytest.approx(brute_crps(x, y), abs=1e-12)


def test_crps_point_ensemble_is_absolute_error():
    assert crps_ensemble(np.array([4.0, 4.0, 4.0]), 1.0) == pytest.approx(3.0)


def test_area_crps_scored_only_with_samples(tmp_path):
    samples = np.tile(np.arange(5, dtype=float), (4, 1))
    e = load([fire_file(tmp_path, area_samples_model=samples)])
    out = score(e, draws=50)["area_crps"]
    assert out["model"]["status"] == "SCORED" and out["model"]["intervals"] == 4
    assert out["persistence"]["status"] == "UNAVAILABLE_NO_AREA_SAMPLES"
    observed = np.bincount(e.interval, weights=e.y, minlength=4)
    expected = np.mean([brute_crps(np.arange(5), o) for o in observed])
    assert out["model"]["mean_crps"] == pytest.approx(expected)


def test_mc_correction_declared_only(tmp_path):
    e = load([fire_file(tmp_path)])
    r = score(e, draws=50, mc_trajectories={"model": 1024})
    p = e.predictions["model"]
    pooled = r["models"]["model"]["pooled"]
    assert pooled["brier_mc_variance_corrected"] == pytest.approx(pooled["brier"] - np.mean(p * (1 - p)) / 1023)
    with pytest.raises(ValueError):
        score(e, draws=50, mc_trajectories={"nope": 10})
