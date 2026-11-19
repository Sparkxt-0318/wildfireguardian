"""Step 1(b) report: held-out area ratio to FIXED vs number of training fires (PROTOCOL 4.2)."""
import json
import numpy as np
from lib import boot_idx

c = json.load(open("derived/step1_curve.json"))
ns = sorted(int(k) for k in c)
rows, out = [], {}
for n in ns:
    r = c[str(n)]
    fx, pe, mr = (np.array(r[m]["area_per_fire"]) for m in ("FIXED", "PERSIST", "M_ref"))
    bi = boot_idx(len(fx), 2000, 20261122)
    rat = mr[bi].mean(1) / fx[bi].mean(1)
    fr = r["M_ref"]["frontier"] / r["FIXED"]["frontier"]
    out[n] = dict(miss={m: r[m]["miss"] for m in r}, area={m: r[m]["area"] for m in r}, frontier={m: r[m]["frontier"] for m in r},
                  mref_over_fixed=mr.mean() / fx.mean(), lo=float(np.percentile(rat, 2.5)), hi=float(np.percentile(rat, 97.5)),
                  mref_over_fixed_frontier=fr, persist_over_fixed=pe.mean() / fx.mean())
    rows.append(n)
    print(f"n={n:2d}  miss FIXED {100*r['FIXED']['miss']:.1f} PERSIST {100*r['PERSIST']['miss']:.1f} M_ref {100*r['M_ref']['miss']:.1f} | "
          f"area FIXED {r['FIXED']['area']:.0f} M_ref {r['M_ref']['area']:.0f} | M_ref/FIXED {mr.mean()/fx.mean():.3f} [{np.percentile(rat,2.5):.3f},{np.percentile(rat,97.5):.3f}]"
          f"  frontier ratio {fr:.3f}  (frontier areas FIXED {r['FIXED']['frontier']:.0f}, M_ref {r['M_ref']['frontier']:.0f})")
sel = [n for n in ns if n >= 8]
y = np.log([out[n]["mref_over_fixed_frontier"] for n in sel]); x = np.log(sel)
sl = np.polyfit(x, y, 1)[0]
# fire-bootstrap of the slope using the calibrated per-fire area ratio
bi = boot_idx(28, 2000, 20261123)
sls = []
for b in bi:
    yy = [np.log(np.array(c[str(n)]["M_ref"]["area_per_fire"])[b].mean() / np.array(c[str(n)]["FIXED"]["area_per_fire"])[b].mean()) for n in sel]
    sls.append(np.polyfit(x, yy, 1)[0])
print(f"slope of log(M_ref/FIXED) vs log n over n={sel}: frontier-based {sl:+.4f}; calibrated-area bootstrap 95% [{np.percentile(sls,2.5):+.4f}, {np.percentile(sls,97.5):+.4f}]")
out["slope_frontier"] = float(sl); out["slope_calibrated_ci"] = [float(np.percentile(sls, 2.5)), float(np.percentile(sls, 97.5))]
json.dump(out, open("derived/step1_curve_summary.json", "w"), indent=1)
