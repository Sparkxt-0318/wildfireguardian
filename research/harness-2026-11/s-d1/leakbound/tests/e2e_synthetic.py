"""Synthetic end-to-end of run_leakbound_L.py fit/score/report/resume/stop (no part-a data). Writes 30 fake per-fire
caches with a planted F1 effect, then runs the script; extract is skipped because every cache exists.

    python tests/e2e_synthetic.py OUTDIR && python run_leakbound_L.py --data-root OUTDIR --pins OUTDIR/pins.json \
        --perimeters OUTDIR/perim --folds OUTDIR/folds.csv --times OUTDIR/times.csv --work OUTDIR/w --run OUTDIR/run \
        --stop-at 2099-01-01T00:00:00Z
"""
import csv
import sys
from pathlib import Path

import numpy as np

S = Path(sys.argv[1])
(S / "run/cache").mkdir(parents=True, exist_ok=True)
(S / "perim").mkdir(exist_ok=True)
(S / "pins.json").write_text("{}")
(S / "perim/PERIMETER_MANIFEST.json").write_text('{"events":{}}')
rng = np.random.default_rng(5)
fires = [f"F{i:02d}" for i in range(30)]
with open(S / "folds.csv", "w") as f:
    w = csv.writer(f); w.writerow(["Incident_C", "fold"]); [w.writerow([e, i % 5]) for i, e in enumerate(fires)]
with open(S / "times.csv", "w") as f:
    w = csv.writer(f); w.writerow(["Incident_C", "first_utc", "last_utc", "surveys"])
    [w.writerow([e, "2020-07-01T00:00:00+00:00", "2020-07-08T00:00:00+00:00", 7]) for e in fires]
for e in fires:
    n = int(rng.integers(200, 600)); x = rng.normal(size=(n, 21)); f1 = rng.uniform(0, 2, n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(-3 + x[:, 0] + 1.5 * f1)))).astype(np.int8)
    np.savez_compressed(S / f"run/cache/{e}.npz", x=x, y=y, dist_m=rng.uniform(0, 8000, n).astype(np.float32), f1=f1,
                        interval=np.zeros(n, np.int32), f2=np.float64(0.5), intervals=np.int32(3), newburn=np.int64(10),
                        newburn_outside_crop=np.int64(1), band_uncropped=np.int64(100),
                        band_uncropped_inside_crop=np.int64(90))
