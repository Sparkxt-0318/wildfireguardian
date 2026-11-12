"""Synthetic tests for the joint-forecast metrics (ensemble.py) and conformal risk control (crc.py)."""

from __future__ import annotations

import numpy as np
import pytest

from sd9bench import load
from sd9bench.crc import calibrate, evaluate, fire_fnr, leave_one_fire_out
from sd9bench.ensemble import area_ensemble_scores, rank_histogram, ranks, spread_skill


def _ranks(obs_scale, ens_scale, n=4000, m=50, seed=1, bias=0.0):
    rng = np.random.default_rng(seed)
    obs = rng.normal(bias, obs_scale, n)
    ens = rng.normal(0, ens_scale, (n, m))
    return ranks(ens, obs, np.random.default_rng(2)), ens, obs


# --- rank histogram ---------------------------------------------------------

def test_calibrated_ensemble_gives_flat_histogram():
    r, ens, obs = _ranks(1.0, 1.0)
    h = rank_histogram(r)
    assert h["chi2_p"] > 0.001
    assert abs(h["outer_share"] - 0.2) < 0.03
    assert 0.8 < spread_skill(ens, obs)["ratio"] < 1.2


def test_overconfident_ensemble_gives_u_shape():
    r, ens, obs = _ranks(2.0, 1.0)
    h = rank_histogram(r)
    f = h["frequency"]
    assert h["chi2_p"] < 1e-6
    assert f[0] > 2 * f[5] and f[-1] > 2 * f[5]
    assert h["outer_share"] > 0.35
    assert spread_skill(ens, obs)["ratio"] > 2


def test_overdispersed_ensemble_gives_hump():
    r, _, _ = _ranks(0.5, 1.0)
    f = rank_histogram(r)["frequency"]
    assert f[4] + f[5] > 2 * (f[0] + f[-1])


def test_biased_ensemble_gives_slope():
    r, _, _ = _ranks(1.0, 1.0, bias=1.0)
    f = rank_histogram(r)["frequency"]
    assert f[-1] > 3 * f[0]


def test_ties_are_broken_uniformly():
    ens = np.zeros((20000, 9))          # every sample ties with the observation
    r = ranks(ens, np.zeros(20000), np.random.default_rng(0))
    h = rank_histogram(r, bins=10)
    assert h["chi2_p"] > 0.001


def test_ranks_validate_shapes():
    with pytest.raises(ValueError):
        ranks(np.zeros((3, 4)), np.zeros(2), np.random.default_rng(0))


def test_area_ensemble_scores_from_entry_files(tmp_path):
    rng = np.random.default_rng(3)
    files = []
    for name in ("A", "B"):
        k, n = 6, 60
        interval = np.repeat(np.arange(k), n // k)
        y = (rng.random(n) < 0.3).astype(np.int8)
        obs = np.bincount(interval, weights=y, minlength=k)
        samples = obs[:, None] + rng.integers(-2, 3, size=(k, 40))
        np.savez(tmp_path / f"{name}.npz", interval=interval, y=y, hours=np.array([6., 6., 18., 18., 30., 42.]),
                 p_model=rng.random(n), area_samples_model=np.clip(samples, 0, None).astype(float))
        files.append(tmp_path / f"{name}.npz")
    out = area_ensemble_scores(load(files))
    assert out["model"]["status"] == "SCORED" and out["model"]["intervals"] == 12
    assert sum(r["intervals"] for r in out["model"]["by_horizon"]) == 12
    assert sum(out["model"]["rank_histogram"]["counts"]) == 12


def test_area_ensemble_unavailable_without_samples(tmp_path):
    np.savez(tmp_path / "A.npz", interval=np.zeros(4, int), y=np.array([0, 1, 0, 0], np.int8),
             hours=np.array([6.0]), p_model=np.full(4, 0.2))
    assert area_ensemble_scores(load([tmp_path / "A.npz"]))["model"]["status"] == "UNAVAILABLE_NO_AREA_SAMPLES"


# --- conformal risk control -------------------------------------------------

def test_fire_fnr_is_monotone_and_exact():
    pos = np.sort(np.array([0.1, 0.2, 0.2, 0.9]))
    t = np.array([0.0, 0.1, 0.15, 0.2, 0.5, 1.0])
    assert fire_fnr(pos, t).tolist() == [0.0, 0.0, 0.25, 0.25, 0.75, 1.0]


def test_infeasible_alpha_gives_whole_domain():
    cal = [np.array([0.5, 0.6])] * 5          # n = 5: needs alpha >= 1/6
    c = calibrate(cal, alpha=0.1)
    assert not c["feasible"] and c["threshold"] == 0.0 and c["required_mean_fnr"] < 0


def test_calibrate_picks_largest_threshold_meeting_bound():
    # n = 4, alpha = 0.5: need mean FNR <= (0.5*5 - 1)/4 = 0.375
    cal = [np.array([0.1, 0.4, 0.8, 0.9])] * 4
    c = calibrate(cal, alpha=0.5)
    assert c["feasible"] and c["threshold"] == pytest.approx(0.4)   # FNR(0.4)=0.25, FNR(0.8)=0.5
    assert c["calibration_mean_fnr"] == pytest.approx(0.25)


def test_evaluate_zone_and_fnr():
    p = np.array([0.9, 0.1, 0.5, 0.0])
    y = np.array([1, 1, 0, 0])
    e = evaluate(p, y, np.array([0, 0, 1, 1]), t=0.5)
    assert e["fnr"] == 0.5 and e["zone_share_of_scored"] == 0.5 and e["zone_cells_mean_per_interval"] == 1.0
    assert e["precision"] == 0.5


def test_lofo_controls_risk_on_exchangeable_fires():
    rng = np.random.default_rng(7)
    fires, ps, ys, iv = [], [], [], []
    for f in range(60):
        n = 400
        y = (rng.random(n) < 0.1).astype(int)
        p = np.clip(0.3 * y + rng.normal(0.1, 0.12, n) + rng.normal(0, 0.05), 0, 1)
        fires += [f"F{f:02d}"] * n
        ps.append(p); ys.append(y); iv.append(np.repeat(np.arange(4), n // 4))
    out = leave_one_fire_out(np.array(fires), np.concatenate(ps), np.concatenate(ys), np.concatenate(iv), alpha=0.2)
    assert out["folds_feasible"] == 60
    assert out["mean_held_out_fnr"] <= 0.2 + 0.03
    assert out["mean_zone_share"] < 1.0
