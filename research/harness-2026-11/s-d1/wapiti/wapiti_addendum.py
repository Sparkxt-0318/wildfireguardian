"""POST-PLAN, DESCRIPTIVE addendum to the Wapiti reconciliation (written after A0-A6 were computed; not part of the
committed step list). (1) Are the (S) and (M) predictions and labels bit-identical on the 24 matched intervals?
(2) Per-interval Brier difference for the 28 (S)-only intervals that carry the sign change.

    python wapiti_addendum.py --heldout HELDOUT --cases ARCH_CASES --out RESULTS_wapiti_addendum.json
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

EVENT = "ID-BOF-000683_Wapiti_Wapiti"
iso = lambda t: datetime.fromisoformat(t).astimezone(timezone.utc).replace(microsecond=0)  # noqa: E731
ap = argparse.ArgumentParser()
ap.add_argument("--heldout", type=Path, required=True)
ap.add_argument("--cases", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
M = {}
for c in sorted(p for p in a.cases.iterdir() if p.is_dir()):
    ref = np.load(c / "reference.npz"); m = np.load(c / "m548_prediction.npz"); pr = json.loads((c / "protocol.json").read_text())
    M[(iso(pr["cutoff"]), iso(pr["endpoint"]))] = (ref["burned_area"][1, 0] == 1, m["probability"][0, 0])
z = np.load(a.heldout / f"{EVENT}.npz")
t1 = [iso(t) for t in z["t1"]]
ends = {iso(r["case"]["cutoff"]): (iso(r["case"]["endpoint"]), r["case"]["hours"]) for r in
        (json.loads(p.read_text()) for p in (a.heldout / "cases").glob("*.json")) if r["case"]["event"] == EVENT}
ident = dict(cells=0, p_bit_identical=0, y_identical=0, max_abs_dp=0.0)
rows = []
for k, t in enumerate(t1):
    sel = z["interval"] == k
    y, p = z["y"][sel].astype(float), z["p_c651_mc"][sel].astype(float)
    e, h = ends[t]
    d = float(np.mean((p - y) ** 2) - np.mean(y))
    key = (t, e)
    if key in M:
        yM, pM = M[key]
        r, c = z["row"][sel], z["col"][sel]
        ident["cells"] += int(sel.sum())
        ident["p_bit_identical"] += int((pM[r, c].astype(np.float32) == z["p_c651_mc"][sel]).sum())
        ident["y_identical"] += int((yM[r, c].astype(np.int8) == z["y"][sel]).sum())
        ident["max_abs_dp"] = max(ident["max_abs_dp"], float(np.abs(pM[r, c] - p).max()))
    rows.append(dict(cutoff=str(t), endpoint=str(e), hours=h, in_preprint=key in M, n=int(sel.sum()),
                     positives=int(y.sum()), brier_c651=float(np.mean((p - y) ** 2)), brier_zero=float(np.mean(y)),
                     diff=d, sum_sq_excess=float(np.sum((p - y) ** 2) - np.sum(y))))
extra = [r for r in rows if not r["in_preprint"]]
tot_excess = sum(r["sum_sq_excess"] for r in extra)
for r in extra:
    r["share_of_extra_excess"] = r["sum_sq_excess"] / tot_excess if tot_excess else None
extra.sort(key=lambda r: -r["sum_sq_excess"])
out = dict(label="POST-PLAN DESCRIPTIVE", identity_on_matched=ident, n_extra_intervals=len(extra),
           extra_pooled=dict(n=sum(r["n"] for r in extra), positives=sum(r["positives"] for r in extra),
                             sum_sq_excess=tot_excess), extra_intervals_by_excess=extra,
           extra_hours=sorted(r["hours"] for r in extra), matched_hours=sorted(r["hours"] for r in rows if r["in_preprint"]))
a.out.write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(dict(identity=ident, n_extra=len(extra), extra_pooled=out["extra_pooled"],
                      top5=[(r["cutoff"][:16], round(r["hours"], 1), r["n"], r["positives"], round(r["share_of_extra_excess"], 3)) for r in extra[:5]],
                      extra_hours_range=(min(out["extra_hours"]), max(out["extra_hours"])),
                      matched_hours_range=(min(out["matched_hours"]), max(out["matched_hours"])))))
