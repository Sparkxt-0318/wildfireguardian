"""Convergence order of the dt-step CA to the first-passage sampler (small fast case).

20x20 grid, 5x5 uniform kernel, coefficient sum 1.0/h, single centre ignition, 4 h,
expected number of new cells, n = 8,000 per method.

    python research/harness-2026-11/s-d1/convergence_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fpp import cellular_automaton, first_passage  # noqa: E402

n, T = 8000, 4.0
K = np.full((25, 20, 20), 1.0 / 24)
K[12] = 0
init = np.zeros((20, 20), bool)
init[10, 10] = True
_, arr = first_passage(K, init, [T], n_samples=n, seed=1, keep_arrivals=n)
x = ((arr <= T) & ~init).sum(axis=(1, 2))
ref, ref_se = x.mean(), x.std(ddof=1) / np.sqrt(n)
out = {"first_passage": [float(ref), float(ref_se)]}
print(f"FPP {ref:.3f} ± {ref_se:.3f}")
for m in (1, 2, 4, 8, 16, 32, 64):
    _, tot = cellular_automaton(K, init, [T], dt=1 / m, n_samples=n, seed=50 + m, return_totals=True)
    y = tot[0]
    mu, se = y.mean(), y.std(ddof=1) / np.sqrt(n)
    out[f"1/{m}"] = [float(mu), float(se)]
    print(f"dt=1/{m:<3d} {mu:8.3f} ± {se:.3f}   gap to FPP {ref - mu:8.3f}  gap*m {m * (ref - mu):8.2f}")
Path(__file__).with_name("RESULTS_convergence.json").write_text(json.dumps(out, indent=1))
