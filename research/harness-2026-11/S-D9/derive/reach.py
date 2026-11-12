"""DEVELOPMENT-ONLY (orchestrator request): are d4_wind's near-zero-tail misses beyond its structural reach?

d4 uses a 9x9 kernel (forecast-v2 RUN_PROTOCOL kernel_size 9), so one hourly step
reaches at most 4 cells: 1,500 m along an axis and 2,121 m diagonally. For an
entry with horizon h hours, the reach ratio is r = dist_m / (1,500 m/h * h), using
the axis (most conservative) reach. r > 1 means beyond reach on every path;
r > 1.414 means beyond reach even diagonally.
Data: cohort R (exposed), with dist_m from derive_dist.py.
Tail: d4 p < 1e-5. Shown for the 4 km band and for the full domain.
The recalibrated d4 (LOFO, logistic_dev.py) is evaluated on the same entries.

  python reach.py --dist DIR --out REACH.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logistic_dev as L  # noqa: E402

AXIS_M_PER_H = 4 * 375.0
EDGES = (0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 1.414, 2.0, np.inf)
TAIL = 1e-5


def table(r, y, p_d4, p_rec):
    rows = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (r >= lo) & (r < hi)
        n = int(m.sum())
        rows.append(dict(ratio_lower=lo, ratio_upper=(None if np.isinf(hi) else hi), entries=n,
                         positives=int(y[m].sum()), burn_rate=float(y[m].mean()) if n else None,
                         d4_mean_p=float(p_d4[m].mean()) if n else None,
                         recal_mean_p=float(p_rec[m].mean()) if n else None))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    data = {}
    for path in sorted(args.dist.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            data[path.stem] = dict(y=z["y"].astype(int), dist=z["dist_m"], hours=z["hours"][z["interval"]],
                                   d4=z["p_d4_wind_seed0"].astype(float))
    fires = sorted(data)
    rec = {}
    for held in fires:
        train = [f for f in fires if f != held]
        x = np.concatenate([L.features(data[f]["dist"], data[f]["hours"], data[f]["d4"], "d4recal") for f in train])
        y = np.concatenate([data[f]["y"] for f in train])
        sc, m = L.fit(x, y, np.random.default_rng(L.SEED))
        rec[held] = m.predict_proba(sc.transform(L.features(data[held]["dist"], data[held]["hours"],
                                                            data[held]["d4"], "d4recal")))[:, 1]
    cat = lambda k: np.concatenate([data[f][k] for f in fires])  # noqa: E731
    y, dist, hours, d4 = cat("y"), cat("dist"), cat("hours"), cat("d4")
    p_rec = np.concatenate([rec[f] for f in fires])
    r = dist / (AXIS_M_PER_H * hours)
    out = dict(label="DEVELOPMENT-ONLY on exposed cohort R", axis_reach_m_per_hour=AXIS_M_PER_H,
               diagonal_reach_m_per_hour=AXIS_M_PER_H * 2 ** 0.5, tail_threshold=TAIL,
               max_reach_ratio_in_4km_band=float(r[dist <= 4000].max()))
    for scope, mask in (("band_4km", dist <= 4000), ("full_domain", np.ones_like(y, bool))):
        tail = mask & (d4 < TAIL)
        out[scope] = dict(
            tail_entries=int(tail.sum()), tail_positives=int(y[tail].sum()),
            tail_positives_beyond_axis_reach=int(y[tail & (r >= 1)].sum()),
            tail_positives_beyond_diagonal_reach=int(y[tail & (r >= 2 ** 0.5)].sum()),
            tail_table=table(r[tail], y[tail], d4[tail], p_rec[tail]),
            all_entries_table=table(r[mask], y[mask], d4[mask], p_rec[mask]),
        )
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    for scope in ("band_4km", "full_domain"):
        s = out[scope]
        print(scope, {k: s[k] for k in s if not k.endswith("table")})
        for row in s["tail_table"]:
            print("  ", row)
    print("max ratio in band", out["max_reach_ratio_in_4km_band"])


if __name__ == "__main__":
    main()
