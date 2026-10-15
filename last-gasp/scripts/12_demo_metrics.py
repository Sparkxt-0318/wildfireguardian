"""Booth demo simulator metrics (SIMULATED, no hardware). Writes results/demo_booth_metrics.json.

Usage: .venv/bin/python scripts/12_demo_metrics.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from lastgasp.provenance import git_info  # noqa: E402
from lastgasp_demo.sources import SimulatorSource  # noqa: E402
from lastgasp_demo.state import DemoState  # noqa: E402

village = json.loads((ROOT / "demo/village.json").read_text())
lat, n_spots, correct_spot = [], [], []
for seed in range(1, 21):
    src = SimulatorSource(village, 1.0, seed=seed)
    st = DemoState(village, 1.0, 3)
    declared = {}
    t = 0.0
    while t <= 200:
        st.ingest(src.poll(t))
        before = st.dead.copy()
        st.update(t)
        for k in np.where(st.dead & ~before)[0]:
            declared[st.ids[k]] = t
        t += 0.25
    for i, td in declared.items():
        if src.death[i] <= 200:
            lat.append(td - src.death[i])
    n_spots.append(len(st.spots))
    sx, sy, _ = src.spot_point
    correct_spot.append(any(np.hypot(s["x"] - sx, s["y"] - sy) < 100 for s in st.spots))
out = {"n_runs": 20, "detection_latency_median_s": float(np.median(lat)),
       "detection_latency_p90_s": float(np.percentile(lat, 90)),
       "runs_with_correct_spot_flag": int(sum(correct_spot)),
       "runs_with_any_extra_spot_flag": int(sum(1 for n, c in zip(n_spots, correct_spot) if n > int(c))),
       "heartbeat_s": 1.0, "timeout_beats": 3, "packet_loss": 0.05,
       "provenance": {**git_info(), "script": "scripts/12_demo_metrics.py", "config": "demo/village.json"}}
(ROOT / "results/demo_booth_metrics.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "provenance"}))
