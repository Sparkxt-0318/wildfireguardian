"""Summaries 1-5 of REBUILT_INPUT_PLAN.md, all of them, whatever they show. No bootstrap, no decision.
p_rebuilt (this run) vs p_original (stored p_d4_wind_seed0) on the stored cells; full domain and 4 km band
(dist_m <= 4000); pooled and per fire. Unsupported cells (valid False) are counted and kept out of nothing silently:
every summary is over all stored cells, and the unsupported count is reported beside it.

    python summarize_rebuilt_input.py --results RESULTS_rebuilt_input.jsonl --cells-dir CELLS --out RESULTS_rebuilt_input_summary.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

FLOOR = 4.2e-7   # re-execution floor of the unmodified-rollout control (d4_wind)
TAIL = 1.0 / 1024


def block(y, p1, p0):
    y, p1, p0 = y.astype(np.float64), p1.astype(np.float64), p0.astype(np.float64)
    d = np.abs(p1 - p0)
    pos = y == 1
    out = dict(n=int(len(y)), positives=int(pos.sum()))
    if not len(y):
        return out
    out["abs_dp"] = dict(max=float(d.max()), median=float(np.median(d)), mean=float(d.mean()),
                         p99=float(np.quantile(d, 0.99)), above_floor=int((d > FLOOR).sum()))
    b1, b0 = float(np.mean((p1 - y) ** 2)), float(np.mean((p0 - y) ** 2))
    out["brier"] = dict(rebuilt=b1, original=b0, delta=b1 - b0)
    if 0 < pos.sum() < len(y):
        a1, a0 = float(average_precision_score(y, p1)), float(average_precision_score(y, p0))
        out["average_precision"] = dict(rebuilt=a1, original=a0, delta=a1 - a0)
    out["tail_p_lt_1_1024"] = {k: dict(share_cells=float(np.mean(p < TAIL)),
                                       share_positives=float(np.mean(p[pos] < TAIL)) if pos.any() else None)
                               for k, p in (("rebuilt", p1), ("original", p0))}
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ("--results", "--cells-dir", "--out"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    lines = [json.loads(l) for l in a.results.read_text().splitlines()]
    head, foot = lines[0], lines[-1]
    rows = [r for r in lines[1:-1]]
    data = {}
    for r in rows:
        z = np.load(a.cells_dir / f"{r['case_id']}.npz")
        data.setdefault(r["case"]["event"], []).append({k: z[k] for k in ("y", "p_rebuilt", "p_original", "dist_m", "valid")})

    def cat(items, k):
        return np.concatenate([d[k] for d in items]) if items else np.array([])

    def summarise(items):
        y, p1, p0, dm, v = (cat(items, k) for k in ("y", "p_rebuilt", "p_original", "dist_m", "valid"))
        band = dm <= 4000.0
        return dict(full=block(y, p1, p0), band_4km=block(y[band], p1[band], p0[band]),
                    unsupported_cells=int((~v.astype(bool)).sum()))

    allitems = [d for v in data.values() for d in v]
    out = dict(plan="REBUILT_INPUT_PLAN.md", label="descriptive row only; no pass/fail", header=head, footer=foot,
               counts=dict(n_cases=len(rows), n_cells=int(sum(r["cells"] for r in rows)),
                           n_positives=int(sum(r["positives"] for r in rows)),
                           n_flagged=sum(r["flagged"] for r in rows),
                           identity_mismatch_cases=[r["case_id"] for r in rows if r["identity_mismatch"]],
                           entries_mismatch_cases=[r["case_id"] for r in rows if not r["entries_match"]],
                           environmental_snapshot_differs=sum(r["environmental_snapshot_differs"] for r in rows),
                           residence_equal=sum(r["residence_equal"] for r in rows)),
               pooled=summarise(allitems), per_fire={e: summarise(v) for e, v in sorted(data.items())})
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(counts=out["counts"], pooled=out["pooled"]), indent=1))


if __name__ == "__main__":
    main()
