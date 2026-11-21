import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _fixture(d, cand_scale=0.2):
    rng = np.random.default_rng(0)
    for f in range(4):
        n = 500
        np.savez(os.path.join(d, f"f{f}.npz"), interval=rng.integers(0, 4, n),
                 y=(rng.random(n) < 0.1).astype(np.int8), hours=np.full(4, 12.0),
                 dist_m=rng.random(n) * 6000, population=np.array("full_rectangle"),
                 p_persistence=np.zeros(n), p_dilation_8h=rng.random(n) * 0.5,
                 p_logistic_rebuilt=rng.random(n) * 0.2, p_d4_wind_recal=rng.random(n) * 0.2,
                 p_cand=0.15 + rng.random(n) * cand_scale)


def _run(d, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    files = sorted(str(p) for p in Path(d).glob("f*.npz"))
    subprocess.run([sys.executable, str(ROOT / "freeze" / "score_criteria.py"), "--out", str(Path(d) / "s.json"), *files],
                   check=True, env=env, capture_output=True)
    subprocess.run([sys.executable, str(ROOT / "freeze" / "criterion5.py"), "--scores", str(Path(d) / "s.json"),
                    "--candidate", "cand", "--out", str(Path(d) / "c5.json"), *files],
                   check=True, env=env, capture_output=True)
    return json.loads((Path(d) / "c5.json").read_text())


def test_empty_candidate_bin_is_not_evaluable(tmp_path):
    _fixture(tmp_path)  # candidate predictions all >= 0.15: empty [0, 0.1) bin
    r = _run(tmp_path)
    assert r["verdict"].startswith("NOT EVALUABLE") and r["met"] is False
    assert r["per_model"]["cand"]["count"] == 0


def test_gaps_match_scorer_and_have_intervals(tmp_path):
    rng = np.random.default_rng(1)
    for f in range(4):
        n = 500
        np.savez(os.path.join(tmp_path, f"f{f}.npz"), interval=rng.integers(0, 4, n),
                 y=(rng.random(n) < 0.1).astype(np.int8), hours=np.full(4, 12.0),
                 dist_m=rng.random(n) * 6000, population=np.array("full_rectangle"),
                 p_persistence=np.zeros(n), p_dilation_8h=rng.random(n) * 0.5,
                 p_logistic_rebuilt=rng.random(n) * 0.2, p_d4_wind_recal=rng.random(n) * 0.2,
                 p_cand=rng.random(n) * 0.12)
    r = _run(tmp_path)  # the run itself asserts agreement with the scorer's calibration bins
    assert r["verdict"] in ("met", "not met")
    for ref in ("persistence", "dilation_8h", "logistic_rebuilt"):
        assert r["comparisons"][ref]["descriptive_bootstrap_95_interval_of_gap_difference"] is not None


def test_perfectly_calibrated_candidate_is_met(tmp_path):
    # Owen's fixture E: a constant equal to the band base rate (gap ~0, float noise ~1e-14).
    rng = np.random.default_rng(2)
    files = []
    ys, ds = [], []
    for f in range(4):
        n = 500
        y = (rng.random(n) < 0.05).astype(np.int8)
        d = rng.random(n) * 6000
        ys.append(y); ds.append(d)
    band_rate = float(np.concatenate(ys)[np.concatenate(ds) <= 4000].mean())
    for f in range(4):
        n = 500
        np.savez(os.path.join(tmp_path, f"f{f}.npz"), interval=rng.integers(0, 4, n), y=ys[f],
                 hours=np.full(4, 12.0), dist_m=ds[f], population=np.array("full_rectangle"),
                 p_persistence=np.zeros(n), p_dilation_8h=0.2 + rng.random(n) * 0.5,
                 p_logistic_rebuilt=rng.random(n) * 0.09, p_d4_wind_recal=rng.random(n) * 0.09,
                 p_cand=np.full(n, band_rate))
    r = _run(tmp_path)
    assert r["per_model"]["cand"]["gap"] < 1e-12
    assert r["verdict"] == "met" and r["met"] is True
