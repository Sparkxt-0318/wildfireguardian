"""DEVELOPMENT-ONLY (Iris): does d4's probability decay geometrically with distance, and are tail positives
concentrated in a few fast intervals? Cohort R, 4 km band, dist_m from derive_dist.py.

Per interval: least-squares slope of log10(p_d4) on distance in cells, over band cells with p > 0
(r^2 is reported). Tail positives (p < 1e-5) are counted per interval, together with the interval's
positive count and its new-burn reach (the largest distance of a positive, in cells).
  python decay.py --dist DIR --out DECAY.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--dist", required=True, type=Path)
ap.add_argument("--out", required=True, type=Path)
a = ap.parse_args()
rows = []
for path in sorted(a.dist.glob("*.npz")):
    z = np.load(path, allow_pickle=False)
    for k in range(len(z["hours"])):
        m = (z["interval"] == k) & (z["dist_m"] <= 4000)
        p, y, d = z["p_d4_wind_seed0"][m].astype(float), z["y"][m], z["dist_m"][m] / 375.0
        ok = p > 0
        slope = r2 = None
        if ok.sum() > 10 and np.ptp(d[ok]) > 0:
            x, t = d[ok], np.log10(p[ok])
            A = np.vstack([x, np.ones_like(x)]).T
            coef, res, *_ = np.linalg.lstsq(A, t, rcond=None)
            slope = float(coef[0])
            r2 = float(1 - (res[0] / ((t - t.mean()) ** 2).sum())) if res.size else None
        tail = int(((p < 1e-5) & (y == 1)).sum())
        rows.append(dict(fire=path.stem, interval=k, hours=float(z["hours"][k]), positives=int(y.sum()),
                         tail_positives=tail, max_positive_dist_cells=float(d[y == 1].max()) if y.sum() else 0.0,
                         log10p_per_cell=slope, r2=r2))
tails = np.array([r["tail_positives"] for r in rows])
order = np.argsort(-tails)
slopes = np.array([r["log10p_per_cell"] for r in rows if r["log10p_per_cell"] is not None])
r2s = np.array([r["r2"] for r in rows if r["r2"] is not None])
top = [rows[i] for i in order[:10]]
summary = dict(
    label="DEVELOPMENT-ONLY on exposed cohort R, 4 km band", intervals=len(rows),
    tail_positives_total=int(tails.sum()),
    top10_interval_share_of_tail=float(tails[order[:10]].sum() / tails.sum()),
    intervals_with_any_tail_positive=int((tails > 0).sum()),
    slope_log10p_per_cell_quantiles={q: float(np.quantile(slopes, float(q))) for q in ("0.1", "0.5", "0.9")},
    r2_quantiles={q: float(np.quantile(r2s, float(q))) for q in ("0.1", "0.5", "0.9")},
    top10_intervals=top)
a.out.write_text(json.dumps(dict(summary=summary, intervals=rows), indent=1) + "\n")
print(json.dumps({k: v for k, v in summary.items() if k != "top10_intervals"}, indent=1))
for r in top:
    print(r)
