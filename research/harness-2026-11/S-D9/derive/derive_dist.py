"""Derive dist_m for cohort R (US2024) from the committed forecast-v2 entry files.

The cutoff mapped union is not stored, but it is recoverable. Within each fire's
fixed rectangle, the scored cells of an interval are exactly the known cells
outside the cutoff union. The script verifies the following before using the
complement as the cutoff union; any failure aborts:
  (1) every case receipt has excluded_cells == 0 and scored_cells == reference_cells
  (2) every interval of a fire uses the same rectangle
  (3) for every chained pair (endpoint_k == cutoff_k+1),
      complement_k+1 == complement_k  OR  positives_k
  (4) no complement cell lies on the rectangle edge at the first interval
These checks are consistent with "complement == cutoff union" but cannot rule
out a static unknown set. If one existed, (3) would still hold, so check (4)
plus excluded_cells == 0 is the evidence against it.

dist_m is the Euclidean distance between cell centres, times 375 m, to the
nearest complement cell (scipy.ndimage.distance_transform_edt). The output
files copy every input array unchanged and add dist_m. They go to --out,
outside git, because they are regenerable.

  python derive_dist.py --out DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[4]
HELDOUT = ROOT / "forecast/runs/20261030_perimeter_trained/execution_v3/heldout"
CELL_M = 375.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    receipts = {}
    for f in (HELDOUT / "cases").glob("*.json"):
        c = json.loads(f.read_text())
        receipts[(c["case"]["event"], c["case"]["cutoff"])] = c
    report = {}
    for path in sorted(HELDOUT.glob("*.npz")):
        ev = path.stem
        z = dict(np.load(path, allow_pickle=False))
        t1 = [str(t) for t in z["t1"]]
        recs = [receipts[(ev, t)] for t in t1]
        assert all(r["excluded_cells"] == 0 and r["scored_cells"] == r["reference_cells"] for r in recs), ev
        rects = {tuple(r["rectangle"]) for r in recs}
        assert len(rects) == 1, (ev, rects)
        h, w = rects.pop()
        dist = np.empty(len(z["y"]), dtype=np.float64)
        comps, pos = [], []
        for k in range(len(t1)):
            m = z["interval"] == k
            assert m.sum() == recs[k]["scored_cells"], (ev, k)
            comp = np.ones((h, w), bool)
            comp[z["row"][m], z["col"][m]] = False
            assert comp.any(), (ev, k, "empty cutoff union")
            p = np.zeros((h, w), bool)
            sel = z["y"][m] == 1
            p[z["row"][m][sel], z["col"][m][sel]] = True
            comps.append(comp)
            pos.append(p)
            d = ndimage.distance_transform_edt(~comp) * CELL_M
            dist[m] = d[z["row"][m], z["col"][m]]
        chained = [k for k in range(len(t1) - 1) if recs[k]["case"]["endpoint"] == t1[k + 1]]
        for k in chained:
            assert np.array_equal(comps[k + 1], comps[k] | pos[k]), (ev, k, "complement not monotone")
        edge = np.zeros((h, w), bool)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        assert not (comps[0] & edge).any(), (ev, "complement on rectangle edge")
        assert np.isfinite(dist).all() and (dist > 0).all(), ev
        z["dist_m"] = dist
        out = args.out / path.name
        np.savez(out, **z)
        report[ev] = dict(intervals=len(t1), chained_pairs_checked=len(chained), rectangle=[h, w],
                          source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                          dist_m_sha256=hashlib.sha256(dist.tobytes()).hexdigest())
    (args.out / "DERIVE_REPORT.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: {kk: v[kk] for kk in ("intervals", "chained_pairs_checked", "dist_m_sha256")}
                      for k, v in report.items()}, indent=1))


if __name__ == "__main__":
    main()
