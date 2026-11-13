#!/usr/bin/env python3
"""S4 of the independent part-a rerun (Owen): score the primary statistic with numpy only.

It is a second implementation, sharing no code with sd9bench or wildfire.baselines. It reads the per-fire entry
files (the sd9bench / forecast-v2 held-out npz contract: interval, y, hours, dist_m, p_<name>). For each pair
CAND:REF it computes, in the 4 km band (dist_m <= 4000 m, A1 §4 revision 1):
  * the pooled paired Brier difference, Brier(CAND) - Brier(REF), over all band entries;
  * the 95% percentile interval over whole-fire bootstrap draws. Each draw resamples fires with replacement and
    pools squared errors (sum of differences / sum of entries). Fires are in sorted Incident_C order and drawn
    with numpy.random.default_rng(seed).integers(0, n_fires, (draws, n_fires)).
  * per-fire differences, the fire count, entries and positives.
A canonical JSON table is written (sorted keys, floats as repr). Its sha256 is printed.

    python s4_score.py --pairs d2_bracket_rebuilt:logistic_rebuilt,... --out TABLE.json FILES.npz...
    python s4_score.py ... --compare-sd9bench RESULTS.json   # numeric check against sd9bench cumulative_bands['4000']
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

BAND_M = 4000.0
SEED = 20261030
DRAWS = 10000


def load(paths, names):
    fires, ys, dists, preds = [], [], [], {n: [] for n in names}
    for path in sorted(Path(p) for p in paths):
        with np.load(path, allow_pickle=False) as z:
            if "dist_m" not in z.files:
                raise SystemExit(f"{path.name}: no dist_m, the 4 km band cannot be formed")
            y = z["y"].astype(np.float64)
            if not set(np.unique(y)) <= {0.0, 1.0}:
                raise SystemExit(f"{path.name}: y not 0/1")
            d = z["dist_m"].astype(np.float64)
            keep = d <= BAND_M
            fires.append(np.full(int(keep.sum()), path.stem, dtype=object))
            ys.append(y[keep]); dists.append(d[keep])
            for n in names:
                p = z[f"p_{n}"].astype(np.float64)
                if not (np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()):
                    raise SystemExit(f"{path.name}: p_{n} not finite in [0, 1]")
                preds[n].append(p[keep])
    return (np.concatenate(fires), np.concatenate(ys), {n: np.concatenate(v) for n, v in preds.items()})


def paired(fire, y, pc, pr, draws, seed):
    order = sorted(set(fire.tolist()))
    sums = np.zeros(len(order)); counts = np.zeros(len(order)); pos = np.zeros(len(order))
    idx = {f: i for i, f in enumerate(order)}
    k = np.fromiter((idx[f] for f in fire), dtype=np.int64, count=len(fire))
    d = (pc - y) ** 2 - (pr - y) ** 2
    np.add.at(sums, k, d); np.add.at(counts, k, 1.0); np.add.at(pos, k, y)
    draw = np.random.default_rng(seed).integers(0, len(order), size=(draws, len(order)))
    values = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
    lo, hi = np.quantile(values, [0.025, 0.975])
    return dict(point_difference=float(sums.sum() / counts.sum()), interval_95=[float(lo), float(hi)],
                interval_below_zero=bool(hi < 0), fires=len(order), entries=int(counts.sum()),
                positives=int(pos.sum()), draws=draws, seed=seed,
                per_fire_difference={f: float(sums[i] / counts[i]) for i, f in enumerate(order)},
                fires_favouring_candidate=int((sums < 0).sum()))


def canonical(o) -> bytes:
    return (json.dumps(o, indent=1, sort_keys=True, allow_nan=False) + "\n").encode()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--pairs", required=True, help="comma-separated CAND:REF")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--compare-sd9bench", type=Path)
    ap.add_argument("--rtol", type=float, default=1e-12)
    a = ap.parse_args(argv)
    pairs = [tuple(p.split(":")) for p in a.pairs.split(",")]
    names = sorted({n for p in pairs for n in p})
    fire, y, preds = load(a.files, names)
    table = dict(statistic="pooled paired Brier difference, 4 km band (dist_m <= 4000 m), whole-fire bootstrap",
                 band_m=BAND_M, files=len(a.files),
                 models={n: dict(brier=float(np.mean((preds[n] - y) ** 2))) for n in names},
                 paired={f"{c}__vs__{r}": paired(fire, y, preds[c], preds[r], a.draws, a.seed) for c, r in pairs})
    blob = canonical(table)
    a.out.write_bytes(blob)
    print("table sha256", hashlib.sha256(blob).hexdigest())
    if a.compare_sd9bench:
        ref = json.loads(a.compare_sd9bench.read_text())["cumulative_bands"]["4000"]
        bad = []
        def close(u, v):
            return u == v or (u is not None and v is not None and math.isclose(u, v, rel_tol=a.rtol, abs_tol=1e-15))
        for key, mine in table["paired"].items():
            theirs = ref["paired"].get(key)
            if theirs is None:
                bad.append(f"{key}: absent in sd9bench (its CLI pairs only persistence/dilation_best references)"); continue
            for m, t in ((mine["point_difference"], theirs["point_difference"]),
                         (mine["interval_95"][0], theirs["percentile_95_interval"][0]),
                         (mine["interval_95"][1], theirs["percentile_95_interval"][1])):
                if not close(m, t):
                    bad.append(f"{key}: {m!r} vs {t!r}")
            for f, v in mine["per_fire_difference"].items():
                if not close(v, theirs["per_fire_difference"][f]):
                    bad.append(f"{key} {f}: {v!r} vs {theirs['per_fire_difference'][f]!r}")
        for n, m in table["models"].items():
            t = ref["models"][n]["pooled"]["brier"]
            if not close(m["brier"], t):
                bad.append(f"brier {n}: {m['brier']!r} vs {t!r}")
        print("sd9bench comparison:", "AGREE" if not bad else f"{len(bad)} DIFFERENCES")
        for b in bad[:20]:
            print("  ", b)
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
