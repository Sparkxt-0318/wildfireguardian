"""Contract A (export v3) tests. Need the forecast environment (PyTorch); skipped in the routing-only environment."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "forecast"))
import export_v3 as X  # noqa: E402

FROZEN = Path("/home/user/wfg-shared/routing-inputs/latest_inputs_try02/exports")


def synthetic_v2(seed=3, shape=(6, 7)):
    rng = np.random.default_rng(seed)
    H, W = shape
    known = np.ones(shape, bool)
    known[0, :3] = False                                    # unknown cumulative state
    burned = np.where(known, 0.0, np.nan)
    burned[3, 3] = 1.0
    observed = known & (np.nan_to_num(burned) == 1)
    valid = known.copy()
    q = np.where(valid, rng.uniform(0.05, 0.6, shape), np.nan)
    q[observed] = 0.0
    q[5, 6] = 0.0                                           # structural zero
    rate_valid = valid & ~observed
    rate = np.where(rate_valid, -np.log1p(-np.nan_to_num(q)), np.nan)
    return {"new_burn_probability": q, "probability_valid": valid, "rate_per_h": rate, "rate_valid": rate_valid,
            "source_burned_area": burned, "source_burned_area_valid": known,
            "affine_transform": np.array([375.0, 0, 0, 0, -375.0, H * 375.0]),
            "heat__initial_active_burning_probability": np.where(known, 0.0, np.nan),
            "heat__initial_remaining_burning_duration_s": np.where(known, 0.0, np.nan),
            "heat__initial_burning_valid": known.copy()}


def _required(v2):
    burned = v2["source_burned_area"]
    known = v2["source_burned_area_valid"] & np.isfinite(burned)
    observed = known & (np.nan_to_num(burned) == 1)
    return known & (observed | v2["rate_valid"]), observed


def test_replay_codes_and_monte_carlo_agreement_with_saved_probability():
    v2 = synthetic_v2()
    n = 4096
    traj = X.replay_trajectories(v2, n=n, seed=11, batch=64)
    fbh = traj["trajectory_first_burn_hour"]
    required, observed = _required(v2)
    assert fbh.dtype == np.int16 and fbh.shape == (n, *v2["new_burn_probability"].shape)
    assert np.all(fbh[:, observed] == 0)
    assert np.all(fbh[:, ~required] == -2)
    assert set(np.unique(fbh[:, required & ~observed])) <= {-1, 1}
    q = np.nan_to_num(v2["new_burn_probability"])
    assert not np.any(fbh[:, q == 0] == 1)
    empirical = ((fbh >= 1) & (fbh <= 1)).mean(axis=0)
    # equal to the rollout's own empirical probability (K = N) exactly ...
    assert np.array_equal(empirical, np.nan_to_num(traj["probability_by_hour"][0]))
    # ... and to the saved v2 probability within Monte Carlo tolerance (six standard deviations plus one count)
    tol = 6 * np.sqrt(q * (1 - q) / n) + 1.0 / n
    assert np.all(np.abs(empirical - q)[required] <= tol[required])


def test_trajectory_seed_regenerates_every_trajectory():
    v2 = synthetic_v2()
    n, batch, seed = 100, 32, 5
    traj = X.replay_trajectories(v2, n=n, seed=seed, batch=batch)
    H, W = v2["new_burn_probability"].shape
    required, observed = _required(v2)
    q = torch.as_tensor(np.where(required, v2["new_burn_probability"], 0.0))
    for k in (0, 31, 32, 99):
        derived = int(np.array([traj["trajectory_seed"][k]], dtype=np.int64).view(np.uint64)[0])
        assert derived == X.derived_seed(seed, 0, k // batch, 0)
        g = torch.Generator(device="cpu").manual_seed(derived)
        u = torch.rand((batch, 1, H, W), generator=g, dtype=torch.float64)[k % batch, 0]
        ignite = (torch.as_tensor(required) & (u < q)).numpy()
        assert np.array_equal(traj["trajectory_first_burn_hour"][k] == 1, ignite & ~observed)
    assert np.all(traj["trajectory_component"] == 0)


def test_replay_refuses_any_horizon_beyond_one_hour():
    v2 = synthetic_v2()
    with pytest.raises(SystemExit):
        X.replay_trajectories(v2, n=8, seed=0, batch=8, hours=2)
    predictor, scope_error = X._replay_predictor(v2)
    H, W = v2["new_burn_probability"].shape
    with pytest.raises(scope_error):
        X.simulate_trajectories(predictor, v2["source_burned_area"][None], v2["source_burned_area_valid"][None],
                                np.zeros((1, 1, H, W)), np.ones((1, 1, H, W), bool), predictor.channel_names,
                                hours=2, n=8, seed=0, batch=8)


def test_model_mode_trajectories_match_multi_hour_probabilities_on_a_fixture_model():
    from tests.test_rollout import CHANNELS, _component, _inputs
    burned, features = _inputs(rate=math.log(2))
    n = 256
    traj = X.simulate_trajectories(_component(), burned.numpy(), np.ones(burned.shape, bool), features.numpy(),
                                   np.ones(features.shape, bool), CHANNELS, hours=3, n=n, seed=41, batch=32, boundary="zero")
    fbh = traj["trajectory_first_burn_hour"]
    for h in (1, 2, 3):
        empirical = ((fbh >= 1) & (fbh <= h)).mean(axis=0)
        assert np.array_equal(empirical, np.nan_to_num(traj["probability_by_hour"][h - 1]))
    assert fbh[:, 2, 1].tolist() == [0] * n                 # the seeded cell is burned at the cutoff
    assert set(np.unique(fbh)) <= {-1, 0, 1, 2, 3}


def test_written_v3_keeps_every_v2_array_byte_identical(tmp_path):
    v2 = synthetic_v2()
    traj = X.replay_trajectories(v2, n=64, seed=0, batch=32)
    record = {"event": "FIXTURE", "checkpoint_sha256": X.CHECKPOINT_SHA256, "npz_sha256": "fixture"}
    npz, rec_path, rec = X.write_v3(tmp_path, "20000101T000000Z", v2, record, "fixture", "fixture", traj, export_count=16, n=64,
                                    seed=0, batch=32, hours=1, mode="replay")
    with np.load(npz) as a:
        for k, v in v2.items():
            assert a[k].dtype == v.dtype and a[k].tobytes() == v.tobytes(), k
        assert a["trajectory_first_burn_hour"].shape == (16, *v2["new_burn_probability"].shape)
        assert a["trajectory_first_burn_hour"].dtype == np.int16 and a["trajectory_seed"].dtype == np.int64
        assert a["trajectory_component"].dtype == np.int16
    rec = json.loads(Path(rec_path).read_text())
    assert rec["export_version"] == "wfg.latest-forecast-export/3" and rec["trajectory_count"] == 16
    for k in ("trajectory_horizon_hours", "trajectory_boundary", "trajectory_missing_policy"):
        assert k in rec
    assert rec["checkpoint_sha256"] == X.CHECKPOINT_SHA256
    with pytest.raises(SystemExit):
        X.write_v3(tmp_path, "20000101T000000Z", v2, record, "fixture", "fixture", traj, export_count=16, n=64, seed=0, batch=32,
                   hours=1, mode="replay")


@pytest.mark.skipif(not (FROZEN / "KFS_02").is_dir(), reason="frozen routing inputs not present")
def test_frozen_uljin_export_replay_agrees_with_saved_probability():
    v2 = X.load_v2(FROZEN / "KFS_02" / "FORECAST_20220304T060000Z.npz")
    n = 1024
    traj = X.replay_trajectories(v2, n=n, seed=0, batch=32)
    q = np.nan_to_num(v2["new_burn_probability"])
    empirical = (traj["trajectory_first_burn_hour"] == 1).mean(axis=0)
    tol = 6 * np.sqrt(q * (1 - q) / n) + 1.0 / n
    assert np.all(np.abs(empirical - q) <= tol)


CHECKPOINT = HERE.parents[2] / "forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"


@pytest.mark.skipif(not CHECKPOINT.is_file(), reason="c651 checkpoint not present")
def test_fixture_model_mode_end_to_end_and_replay_equals_model_mode_at_one_hour(tmp_path):
    """FIXTURE: synthetic data root, real c651 checkpoint, frozen v2 exporter, rollout with the callback (model mode);
    the one-hour replay from the produced v2 export must reproduce every model-mode trajectory exactly."""
    pytest.importorskip("rasterio")
    import subprocess
    repo = HERE.parents[2]
    root = tmp_path / "fixture_root"
    subprocess.run([sys.executable, str(repo / "research/scenario-members/fixture_data_root.py"), "--out", str(root)], check=True,
                   capture_output=True)
    out = tmp_path / "export"
    X.main(["model", "--source-root", str(repo / "forecast"), "--data-root", str(root), "--checkpoint", str(CHECKPOINT),
            "--event", "FIX_01", "--cutoff", "2000-01-01T03:00:00Z", "--out", str(out), "--n", "256", "--export-count", "256"])
    v2 = X.load_v2(out / "v2_staging" / "FORECAST_20000101T030000Z.npz")
    with np.load(out / "FORECAST_20000101T030000Z.npz") as z:
        model_fbh = z["trajectory_first_burn_hour"].copy()
        for k, v in v2.items():
            assert z[k].tobytes() == v.tobytes()
    replay = X.replay_trajectories(v2, n=256, seed=0, batch=32)
    assert np.array_equal(replay["trajectory_first_burn_hour"], model_fbh)
    assert (model_fbh == 1).any()
