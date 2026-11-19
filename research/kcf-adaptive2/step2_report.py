"""Aggregate held-out DEV results: one row per method (PROTOCOL 3, 8). Writes derived/step2_summary.json and prints the table."""
import json, sys
from pathlib import Path
import numpy as np
from lib import *

H = int(sys.argv[1]) if len(sys.argv) > 1 else 5
D = Data(H, "/tmp/w/work")
dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
idx = D.rows_of(dev)
res = {}
for p in sorted(Path("derived/step2").glob(f"*_h{H}.npz")):
    name = p.stem.rsplit("_h", 1)[0]
    z = np.load(p)
    fl, miss, area = evaluate(D, idx, z["s"], z["kappa"])
    res[name] = dict(fires=fl, miss=miss, area=area, sm=boot_summary(miss, area))
out = {}
ref = {k: res[k] for k in ("FIXED", "PERSIST") if k in res}
rows = []
for name, r in res.items():
    d = dict(r["sm"])
    for cn, c in ref.items():
        rt, lo, hi = ratio_ci(r["area"][:, L1], c["area"][:, L1])
        d[f"ratio_vs_{cn}"] = [rt, lo, hi]
        d[f"verdict_vs_{cn}"] = verdict(r["sm"], rt, lo, hi) if name != cn else ""
    fr = frontier_read(r["miss"], r["area"]); d["frontier_area"] = fr
    if "FIXED" in res and name != "FIXED":
        d["frontier_ratio_vs_FIXED"] = fr / res["FIXED"]["sm"]["frontier_area"]
    out[name] = d
    rows.append((name, d))
json.dump(out, open(f"derived/step2_summary_h{H}.json", "w"), indent=1)
print(f"{'method':18s} {'area':>7s} {'miss%':>6s} {'[95% CI]':>14s} {'ratio/FIXED [CI]':>22s} {'verdict':>18s} {'ratio/PERSIST':>8s} {'front10':>8s}")
for name, d in rows:
    rf = d.get("ratio_vs_FIXED", [np.nan] * 3); rp = d.get("ratio_vs_PERSIST", [np.nan] * 3)
    print(f"{name:18s} {d['area']:7.1f} {100*d['miss']:6.2f} [{100*d['miss_lo']:4.1f},{100*d['miss_hi']:5.1f}] {rf[0]:6.3f} [{rf[1]:5.3f},{rf[2]:5.3f}] {d.get('verdict_vs_FIXED',''):>18s} {rp[0]:8.3f} {d['frontier_area']:8.1f}")
