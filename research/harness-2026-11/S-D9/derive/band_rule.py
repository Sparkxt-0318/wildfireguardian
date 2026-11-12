"""Apply the addendum A1 primary-band rule (committed at 3eb31a38, before this script ran) on cohort R.

Rule: among the cumulative widths 1, 2, 4, 8 and 16 km, take the smallest whose
pooled share of R positives is >= 0.90; if none qualifies, use the full domain.
Only positives' distances and horizons are used. No predictor is read.

  python band_rule.py --dist DIR_FROM_derive_dist --out BAND_RULE.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

WIDTHS_M = (1000.0, 2000.0, 4000.0, 8000.0, 16000.0)
THRESHOLD = 0.90
HORIZON_EDGES = (0.0, 12.0, 24.0, 36.0, 48.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    d_all, f_all, h_all = [], [], []
    for path in sorted(args.dist.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            pos = z["y"] == 1
            d_all.append(z["dist_m"][pos])
            f_all.append(np.full(int(pos.sum()), path.stem))
            h_all.append(z["hours"][z["interval"][pos]])
    d, fire, hours = np.concatenate(d_all), np.concatenate(f_all), np.concatenate(h_all)

    def shares(mask):
        n = int(mask.sum())
        return dict(positives=n, share_within={str(int(w)): (float((d[mask] <= w).mean()) if n else None)
                                               for w in WIDTHS_M},
                    beyond_16km=int((d[mask] > WIDTHS_M[-1]).sum()))

    pooled = shares(np.ones(len(d), bool))
    chosen = next((w for w in WIDTHS_M if pooled["share_within"][str(int(w))] >= THRESHOLD), None)
    out = dict(
        rule="smallest cumulative width in 1/2/4/8/16 km with pooled R positive share >= 0.90; else full domain",
        rule_commit="3eb31a38", threshold=THRESHOLD, widths_m=list(WIDTHS_M),
        chosen_width_m=chosen, primary_population=(f"dist_m <= {int(chosen)} m" if chosen else "full domain"),
        pooled=pooled,
        per_fire={f: shares(fire == f) for f in sorted(set(fire.tolist()))},
        per_horizon={f"({lo},{hi}]": shares((hours > lo) & (hours <= hi)) for lo, hi in
                     zip(HORIZON_EDGES[:-1], HORIZON_EDGES[1:])},
        distance_quantiles_m={str(q): float(np.quantile(d, q)) for q in (0.5, 0.75, 0.9, 0.95, 0.99)},
    )
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("chosen_width_m", "pooled", "distance_quantiles_m")}, indent=1))


if __name__ == "__main__":
    main()
