"""DEVELOPMENT-ONLY (Iris): are d4's tail positives label-filled interior cells?

The endpoint mapped union of an interval is (cutoff union) OR (that interval's
positives). The cutoff union is recovered as in derive_dist.py. A positive is
"enclosed" if at least 6 of its 8 neighbours are in the endpoint union, and an
"island" if all 8 are. Cells outside the rectangle count as not in the union.
Tail = d4 p < 1e-5; non-tail = d4 p >= 1e-5. Scope: the 4 km band of cohort R.
Fuel and land-cover gating (Iris's part a) needs covariates that are not in git,
so it is not computed here.

  python enclosure.py --out ENCLOSURE.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[4]
HELDOUT = ROOT / "forecast/runs/20261030_perimeter_trained/execution_v3/heldout"
TAIL, BAND_M, CELL_M = 1e-5, 4000.0, 375.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    receipts = {}
    for f in (HELDOUT / "cases").glob("*.json"):
        c = json.loads(f.read_text())
        receipts[(c["case"]["event"], c["case"]["cutoff"])] = c
    kernel = np.ones((3, 3), int)
    kernel[1, 1] = 0
    rows = {k: dict(positives=0, enclosed=0, island=0) for k in ("tail", "nontail")}
    per_fire = {}
    for path in sorted(HELDOUT.glob("*.npz")):
        ev = path.stem
        z = np.load(path, allow_pickle=False)
        t1 = [str(t) for t in z["t1"]]
        h, w = receipts[(ev, t1[0])]["rectangle"]
        pf = {k: dict(positives=0, enclosed=0) for k in ("tail", "nontail")}
        for k in range(len(t1)):
            m = z["interval"] == k
            comp = np.ones((h, w), bool)
            comp[z["row"][m], z["col"][m]] = False
            pos = np.zeros((h, w), bool)
            sel = z["y"][m] == 1
            pos[z["row"][m][sel], z["col"][m][sel]] = True
            endpoint = comp | pos
            nb = ndimage.convolve(endpoint.astype(int), kernel, mode="constant", cval=0)
            dist = ndimage.distance_transform_edt(~comp) * CELL_M
            rr, cc, p = z["row"][m][sel], z["col"][m][sel], z["p_d4_wind_seed0"][m][sel]
            inband = dist[rr, cc] <= BAND_M
            for name, use in (("tail", (p < TAIL) & inband), ("nontail", (p >= TAIL) & inband)):
                n8 = nb[rr[use], cc[use]]
                rows[name]["positives"] += int(use.sum())
                rows[name]["enclosed"] += int((n8 >= 6).sum())
                rows[name]["island"] += int((n8 == 8).sum())
                pf[name]["positives"] += int(use.sum())
                pf[name]["enclosed"] += int((n8 >= 6).sum())
        per_fire[ev] = pf
    for r in rows.values():
        r["enclosed_share"] = r["enclosed"] / r["positives"] if r["positives"] else None
        r["island_share"] = r["island"] / r["positives"] if r["positives"] else None
    out = dict(label="DEVELOPMENT-ONLY on exposed cohort R, 4 km band", tail_threshold=TAIL,
               enclosed_rule=">= 6 of 8 neighbours in endpoint union", **rows, per_fire=per_fire)
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
