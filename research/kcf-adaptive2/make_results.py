"""Fill RESULTS.template.md from derived/ -> RESULTS.md (no number is typed by hand)."""
import json
from pathlib import Path

T = Path("RESULTS.template.md").read_text()
d5 = json.load(open("derived/numbers_dev_h5.json"))
d8 = json.load(open("derived/numbers_dev_h8.json")) if Path("derived/numbers_dev_h8.json").exists() else None
o = json.load(open("derived/step1_oracle.json"))
c = json.load(open("derived/step1_curve_summary.json"))
order = ["FIXED", "PERSIST", "QUANTILE", "QUANTILE-own", "QUANTILE-fc", "REGIME", "REGIME+own", "EVT", "EVT-twin", "PRETRAIN-archive",
         "PRETRAIN-sim", "PRETRAIN-both", "M_ref", "META", "META-init", "META-pooled", "KALMAN", "KALMAN-twin"]


def main_table(d):
    L = ["| Method | Family | Area at 10% target (km2) | Achieved miss, 95% interval | Fires | Area / FIXED (95%) | Verdict | Area read at held-out 10% |",
         "|---|---|---|---|---|---|---|---|"]
    for m in order:
        if m not in d:
            continue
        r = d[m]; f = r["ratio_fixed"]
        L.append(f"| {m} | {r['family']} | {r['area']:.1f} | {100*r['miss']:.1f}% ({100*r['miss_lo']:.1f} to {100*r['miss_hi']:.1f}) | {r['n_fires']} | "
                 f"{f[0]:.3f} ({f[1]:.3f} to {f[2]:.3f}) | {r['verdict'] if m != 'FIXED' else '-'} | {r['frontier_area']:.1f} |")
    return "\n".join(L)


orows = []
for base in ("O-fire", "O-day", "O-6h"):
    a, b = o["oracle"][f"{base} [s=1]"], o["oracle"][f"{base}-random [s=1]"]
    orows.append(f"| {base} | {100*a['miss']:.1f}% | {a['area']:.0f} | {100*a['gain_vs_fixed_calibrated']:+.1f}% ({100*a['gain_lo']:+.1f} to {100*a['gain_hi']:+.1f}) | {100*b['gain_vs_fixed_calibrated']:+.1f}% |")
crows = ["| Training fires | Miss FIXED / PERSIST / M_ref | Area FIXED (km2) | Area M_ref (km2) | M_ref / FIXED at the calibrated margin (95%) | M_ref / FIXED read at held-out 10% |", "|---|---|---|---|---|---|"]
for n in (4, 8, 12, 16, 20, 24):
    r = c[str(n)]
    crows.append(f"| {n} | {100*r['miss']['FIXED']:.1f}% / {100*r['miss']['PERSIST']:.1f}% / {100*r['miss']['M_ref']:.1f}% | {r['area']['FIXED']:.0f} | {r['area']['M_ref']:.0f} | "
                 f"{r['mref_over_fixed']:.3f} ({r['lo']:.3f} to {r['hi']:.3f}) | {r['mref_over_fixed_frontier']:.3f} |")
tab5 = Path("derived/tables_h5.md").read_text()
twins = tab5[tab5.index("| Adapted | Twin"):].strip()
fin = Path("derived/tables_final_h5.md").read_text()
kr = fin[:fin.index("### 25 March")].split("\n", 2)[2].strip()
mar = fin[fin.index("| KST |"):].strip()
h8 = (main_table(d8) if d8 else "NOT RUN") + ("\n\nThe h = 8 run uses identical code and the same 28 fires. Oracle and learning curve were run at h = 5 only." if d8 else "")
out = (T.replace("{MAIN}", main_table(d5)).replace("{ORACLE}", "\n".join(orows)).replace("{CURVE}", "\n".join(crows))
       .replace("{TWINS}", twins).replace("{KR}", kr).replace("{MAR}", mar).replace("{H8}", h8)
       .replace("{FIXED_AREA}", f"{o['gate']['fixed_area']:.0f}").replace("{FIXED_MISS}", f"{100*o['gate']['fixed_miss']:.1f}%"))
Path("RESULTS.md").write_text(out)
print(len(out), "chars")
