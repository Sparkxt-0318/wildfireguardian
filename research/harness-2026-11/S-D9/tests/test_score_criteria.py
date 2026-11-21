import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _fixture(d):
    rng = np.random.default_rng(0)
    for f in range(3):
        n = 400
        np.savez(os.path.join(d, f"f{f}.npz"), interval=rng.integers(0, 4, n),
                 y=(rng.random(n) < 0.1).astype(np.int8), hours=np.full(4, 12.0),
                 dist_m=rng.random(n) * 6000, population=np.array("full_rectangle"),
                 p_persistence=np.zeros(n), p_dilation_8h=rng.random(n) * 0.5,
                 p_logistic_rebuilt=rng.random(n) * 0.2, p_d4_wind_recal=rng.random(n) * 0.2,
                 p_cand=rng.random(n) * 0.2)


def _run(d, out):
    files = sorted(str(p) for p in Path(d).glob("f*.npz"))
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    subprocess.run([sys.executable, str(ROOT / "freeze" / "score_criteria.py"), "--out", str(out), *files],
                   check=True, env=env, capture_output=True)


def test_all_criterion_pairs_and_byte_stable(tmp_path):
    _fixture(tmp_path)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    _run(tmp_path, a)
    _run(tmp_path, b)
    assert a.read_bytes() == b.read_bytes()
    paired = json.loads(a.read_text())["paired"]
    for ref in ("persistence", "dilation_8h", "logistic_rebuilt", "d4_wind_recal"):
        assert f"cand__vs__{ref}" in paired
