"""DEVELOPMENT-ONLY: conformal risk control for warning zones on cohort R (A1 §5.4, revision 27).

The procedure, alpha values and predictors were committed in A1 (2c9f6349) before this script
ran. Leave-one-fire-out over the 6 exposed US2024 fires; full rectangle (primary) and 4 km band.

  python crc_dev.py --dist DIR --out CRC_DEV.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sd9bench.crc import leave_one_fire_out  # noqa: E402

PREDICTORS = ("d4_wind_seed0", "logistic", "c651_mc", "dilation_8h")
ALPHAS = (0.1, 0.2, 0.3)
BAND_M = 4000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    cols = {k: [] for k in ("fire", "y", "interval", "dist", *PREDICTORS)}
    for path in sorted(args.dist.glob("*.npz")):
        with np.load(path, allow_pickle=False) as z:
            cols["fire"].append(np.full(len(z["y"]), path.stem))
            cols["y"].append(z["y"].astype(int))
            cols["interval"].append(z["interval"])
            cols["dist"].append(z["dist_m"])
            for p in PREDICTORS:
                cols[p].append(z[f"p_{p}"].astype(float))
    c = {k: np.concatenate(v) for k, v in cols.items()}
    out = dict(label="DEVELOPMENT-ONLY on exposed cohort R (US2024, 6 fires); A1 §5.4; not confirmatory",
               declared_in="A1 revision 27, commit 2c9f6349", population="full_rectangle", alphas=list(ALPHAS),
               primary_alpha=0.2, results={})
    for scope, mask in (("full_domain", np.ones(len(c["y"]), bool)), ("band_4km", c["dist"] <= BAND_M)):
        out["results"][scope] = {}
        for p in PREDICTORS:
            out["results"][scope][p] = {
                str(a): leave_one_fire_out(c["fire"][mask], c[p][mask], c["y"][mask], c["interval"][mask], a)
                for a in ALPHAS}
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    for scope, res in out["results"].items():
        print(scope)
        for p, by_a in res.items():
            for a, r in by_a.items():
                ts = [round(v["calibration"]["threshold"], 6) for v in r["per_fire"].values()]
                print(f"  {p:14s} a={a} feasible {r['folds_feasible']}/6 heldFNR {r['mean_held_out_fnr']:.3f} "
                      f"zone {r['mean_zone_share']:.3f} t {ts}")


if __name__ == "__main__":
    main()
