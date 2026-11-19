"""Report the sealed transfer test: KR (12 Korean fires, Choi rasters) and MAR25 (25 March 2025 detections). PROTOCOL 7."""
import os
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from lib import *

H = int(sys.argv[1]) if len(sys.argv) > 1 else 5
D = Data(H, os.environ.get("KCF2_WORK", "/tmp/w/work"))
kr = np.flatnonzero([(p == "CHOI") and str(f).startswith("KFS") for p, f in zip(D.product, D.fire)])
det = np.flatnonzero(D.product == "DET")
res, mar = {}, {}
for p in sorted(Path("derived/final").glob(f"*_h{H}.npz")):
    name = p.stem.rsplit("_h", 1)[0]
    z = np.load(p)
    s = z["s"]; kap = float(z["kappa"])
    kr_ok = kr[np.isfinite(s[kr])]
    fl, miss, area = evaluate(D, kr_ok, s, np.full(len(D.S), kap))
    nh = np.array([(D.fid[kr_ok] == D.fires.index(f)).sum() for f in fl])
    res[name] = dict(fires=fl, miss=miss, area=area, kappa=kap, sm=boot_summary(miss, area), hours=nh,
                     missed_hours=(miss[:, L1] * nh).round().astype(int))
    q = kap * np.maximum(s[det], S_FLOOR)
    mar[name] = dict(q=q, held=(D.S[det] <= q), area=D.area(det, np.minimum(q, NB * CELL_KM)))
out = {}
fx = res.get("FIXED")
print(f"KR transfer, h={H}: {len(fx['fires'])} fires, {int(fx['hours'].sum())} hours")
print(f"{'method':18s} {'area':>7s} {'miss%':>6s} {'[95% CI]':>14s} {'missed h':>9s} {'ratio/FIXED [CI]':>22s} {'frontier10':>10s}")
for name, r in res.items():
    rt = ratio_ci(r["area"][:, L1], fx["area"][:, L1]) if name != "FIXED" else (1, 1, 1)
    sm = r["sm"]
    out[name] = dict(kr=dict(sm, ratio_vs_FIXED=list(rt), missed_hours=int(r["missed_hours"].sum()), hours=int(r["hours"].sum()),
                              fires=r["fires"], per_fire_missed=r["missed_hours"].tolist(), per_fire_hours=r["hours"].tolist(),
                              per_fire_area=r["area"][:, L1].tolist()))
    print(f"{name:18s} {sm['area']:7.1f} {100*sm['miss']:6.2f} [{100*sm['miss_lo']:4.1f},{100*sm['miss_hi']:5.1f}] {int(r['missed_hours'].sum()):9d} {rt[0]:6.3f} [{rt[1]:5.3f},{rt[2]:5.3f}] {sm['frontier_area']:10.1f}")
# MAR25 table
t = pd.to_datetime(D.df.t_utc.values[det]) + pd.Timedelta(hours=9)
tab = pd.DataFrame({"kst_hour": t.hour, "reach_km": D.S[det]})
for name, m in mar.items():
    tab[f"{name}|q"] = m["q"].round(2); tab[f"{name}|held"] = m["held"]; tab[f"{name}|area"] = m["area"].round(0)
tab.to_csv(f"derived/mar25_h{H}.csv", index=False)
print(f"\nMAR25 h={H}: {len(det)} complete issue hours (KST {t.hour.min()}-{t.hour.max()})")
for name, m in mar.items():
    out[name]["mar25"] = dict(missed=int((~m["held"]).sum()), hours=int(len(det)), mean_area_km2=float(m["area"].mean()),
                              missed_kst=[int(h) for h in t.hour[~m["held"]]])
    print(f"{name:18s} missed {int((~m['held']).sum()):2d}/{len(det)}  mean area {m['area'].mean():9.0f} km2  max q {m['q'].max():6.2f} km  first held-after-miss KST: {[int(h) for h in t.hour[m['held']]][:0]}")
json.dump(out, open(f"derived/final_summary_h{H}.json", "w"), indent=1)
