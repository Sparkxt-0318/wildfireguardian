"""Build every table of RESULTS.md from derived/ (PROTOCOL 8). Usage: python make_tables.py [h]. Writes derived/tables_h<h>.md and numbers entries."""
import json, sys
from pathlib import Path
import numpy as np
from lib import *

H = int(sys.argv[1]) if len(sys.argv) > 1 else 5
D = Data(H, "/tmp/w/work")
dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
idx = D.rows_of(dev)
R = {}
for p in sorted(Path("derived/step2").glob(f"*_h{H}.npz")):
    name = p.stem.rsplit("_h", 1)[0]
    z = np.load(p)
    fl, miss, area = evaluate(D, idx, z["s"], z["kappa"])
    R[name] = dict(fires=fl, miss=miss, area=area, sm=boot_summary(miss, area))
FX, PE = R["FIXED"], R["PERSIST"]
order = ["FIXED", "PERSIST", "QUANTILE", "QUANTILE-own", "QUANTILE-fc", "REGIME", "REGIME+own", "EVT", "EVT-twin", "PRETRAIN-archive",
         "PRETRAIN-sim", "PRETRAIN-both", "M_ref", "META", "META-init", "META-pooled", "KALMAN", "KALMAN-twin"]
order = [m for m in order if m in R]
fam = {"FIXED": "baseline", "PERSIST": "baseline", "QUANTILE": "3 quantile loss", "QUANTILE-own": "3 (own-past features only)",
       "QUANTILE-fc": "3/4 (issued-forecast features only)", "REGIME": "4 forecast regime", "REGIME+own": "4 regime + own-past quantile",
       "EVT": "6 peaks over threshold", "EVT-twin": "6 (constant-scale twin)", "PRETRAIN-archive": "5 pretrain: 19 archive fires",
       "PRETRAIN-sim": "5 pretrain: simulated fires", "PRETRAIN-both": "5 pretrain: both", "M_ref": "reference GBM, no tuning",
       "META": "1 meta-learning, adapted", "META-init": "1 (meta-init, no adaptation)", "META-pooled": "1 (pooled net, no adaptation)",
       "KALMAN": "2 per-fire Kalman, adapted", "KALMAN-twin": "2 (twin, no adaptation)"}
out, num = [], {}
out.append(f"### DEV, h = {H} h, {len(dev)} GOFER fires, {len(idx):,} issue hours, 7 outer folds by fire\n")
out.append("| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Area / PERSIST (95%) | Verdict vs FIXED | Area read at held-out 10% |")
out.append("|---|---|---|---|---|---|---|---|---|")
for m in order:
    r = R[m]; sm = r["sm"]
    rf = ratio_ci(r["area"][:, L1], FX["area"][:, L1]) if m != "FIXED" else (1, 1, 1)
    rp = ratio_ci(r["area"][:, L1], PE["area"][:, L1]) if m != "PERSIST" else (1, 1, 1)
    v = verdict(sm, *rf) if m != "FIXED" else "-"
    num[m] = dict(area=sm["area"], miss=sm["miss"], miss_lo=sm["miss_lo"], miss_hi=sm["miss_hi"], n_fires=sm["n_fires"],
                  ratio_fixed=list(rf), ratio_persist=list(rp), verdict=v, frontier_area=sm["frontier_area"], family=fam[m])
    out.append(f"| {m} | {fam[m]} | {sm['area']:.1f} | {100*sm['miss']:.1f}% ({100*sm['miss_lo']:.1f} to {100*sm['miss_hi']:.1f}) | {sm['n_fires']} | "
               f"{rf[0]:.3f} ({rf[1]:.3f} to {rf[2]:.3f}) | {rp[0]:.3f} ({rp[1]:.3f} to {rp[2]:.3f}) | {v} | {sm['frontier_area']:.1f} |")
out.append("\n### Does adapting to the fire help, against the same model without adaptation (paired by fire)\n")
out.append("| Adapted | Twin | Area adapted / twin (95%) | Reading |")
out.append("|---|---|---|---|")
pairs = [("META", "META-init"), ("META", "META-pooled"), ("KALMAN", "KALMAN-twin"), ("EVT", "EVT-twin"), ("QUANTILE", "QUANTILE-own"),
         ("QUANTILE-own", "FIXED"), ("QUANTILE", "QUANTILE-fc"), ("PRETRAIN-archive", "M_ref"), ("PRETRAIN-sim", "M_ref"),
         ("PRETRAIN-both", "M_ref"), ("REGIME+own", "QUANTILE-own")]
num["pairs"] = {}
for a, b in pairs:
    if a in R and b in R:
        rt = ratio_ci(R[a]["area"][:, L1], R[b]["area"][:, L1])
        rd = "lower" if rt[2] < 1 else ("higher" if rt[1] > 1 else "no difference")
        num["pairs"][f"{a}|{b}"] = dict(ratio=list(rt), reading=rd)
        out.append(f"| {a} | {b} | {rt[0]:.3f} ({rt[1]:.3f} to {rt[2]:.3f}) | {rd} |")
Path(f"derived/tables_h{H}.md").write_text("\n".join(out) + "\n")
json.dump(num, open(f"derived/numbers_dev_h{H}.json", "w"), indent=1)
print("\n".join(out))
