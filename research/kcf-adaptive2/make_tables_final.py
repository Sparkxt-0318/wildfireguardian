"""Markdown tables for the sealed transfer test: KR and MAR25 (reads derived/final_summary_h5.json and derived/mar25_h5.csv)."""
import json
import pandas as pd

H = 5
S = json.load(open(f"derived/final_summary_h{H}.json"))
order = ["FIXED", "PERSIST", "QUANTILE", "QUANTILE-own", "QUANTILE-fc", "REGIME", "REGIME+own", "EVT", "EVT-twin", "PRETRAIN-archive",
         "PRETRAIN-sim", "PRETRAIN-both", "M_ref", "META", "META-init", "META-pooled", "KALMAN", "KALMAN-twin"]
out = ["### Korea (sealed transfer test), h = 5 h: 12 Korean fires, 756 issue hours, margins calibrated on California only\n",
       "| Method | Area at the California-calibrated margin (km2) | Miss, 95% interval | Missed hours | Area / FIXED (95%) | Area read at held-out 10% |",
       "|---|---|---|---|---|---|"]
for m in order:
    k = S[m]["kr"]; r = k["ratio_vs_FIXED"]
    out.append(f"| {m} | {k['area']:.1f} | {100*k['miss']:.1f}% ({100*k['miss_lo']:.1f} to {100*k['miss_hi']:.1f}) | {k['missed_hours']} of {k['hours']} | "
               f"{r[0]:.2f} ({r[1]:.2f} to {r[2]:.2f}) | {k['frontier_area']:.1f} |")
t = pd.read_csv(f"derived/mar25_h{H}.csv")
out.append("\n### 25 March 2025, h = 5 h, 23 complete issue hours (KST 00-22): margin q in km, M = missed, h = held\n")
ms = ["FIXED", "PERSIST", "QUANTILE", "REGIME", "EVT", "META", "KALMAN", "PRETRAIN-archive"]
out.append("| KST | reach (km) | " + " | ".join(ms) + " |")
out.append("|---|---|" + "---|" * len(ms))
for _, r in t[(t.kst_hour >= 8) & (t.kst_hour <= 22)].iterrows():
    cells = []
    for m in ms:
        q = r[m + "|q"]
        qs = f"{q:.1f}" if q < 1000 else f"{q:,.0f}"
        cells.append(f"{qs} {'h' if r[m + '|held'] else '**M**'}")
    out.append(f"| {int(r.kst_hour):02d} | {r.reach_km:.1f} | " + " | ".join(cells) + " |")
out.append("\n| Method | Hours missed of 23 | Missed during 10-20 KST (the run) of 11 | Mean flagged area (km2, capped at q = 60 km) | Largest margin (km) |")
out.append("|---|---|---|---|---|")
for m in order:
    a = S[m]["mar25"]
    run = sum(1 for h in a["missed_kst"] if 10 <= h <= 20)
    qmax = t[m + "|q"].max()
    out.append(f"| {m} | {a['missed']} | {run} | {a['mean_area_km2']:.0f} | {qmax:,.1f} |")
open(f"derived/tables_final_h{H}.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
