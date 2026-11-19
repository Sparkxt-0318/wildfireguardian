#!/usr/bin/env python3
"""Collect every reported number into numbers.json and print the tables of RESULTS.md into derived/tables.md."""
import json
from pathlib import Path

import pandas as pd

H = Path(__file__).resolve().parent
D = H / "derived"
ca = json.load(open(D / "final_ca.json"))
kr = json.load(open(D / "korea.json"))
kept = json.load(open(D / "kept.json"))
arch = json.load(open(D / "archive_propensity.json"))
props = [json.loads(l) for l in open(D / "proposals.jsonl")]
dev = {json.loads(l)["name"]: json.loads(l) for l in open(D / "dev_log.jsonl")}
M = ["FIXED", "QUANTILE", "TRACKER", "TRACKER-noupdate", "TRACKER-nofc", "TRACKER-noarchive"]
LABEL = {"FIXED": "FIXED margin", "QUANTILE": "QUANTILE (kcf-adaptive2)", "TRACKER": "TRACKER (kept version)",
         "TRACKER-noupdate": "TRACKER, hourly update off", "TRACKER-nofc": "TRACKER, forecast input off",
         "TRACKER-noarchive": "TRACKER, archive input off"}


def valid(r):
    return abs(r["miss"] - 0.10) <= 0.03 and r["miss_lo"] <= 0.10 <= r["miss_hi"]


def pct(x):
    return f"{100 * x:.1f}%"


def row(set_name, n, r, warned):
    return (f"| {set_name} | {LABEL[n]} | {r['area']:.1f} | {pct(r['miss'])} ({100 * r['miss_lo']:.1f} to {100 * r['miss_hi']:.1f})"
            f"{'' if valid(r) else ' not at target'} | {r['n_fires']} | {r['frontier_area']:.1f} | {warned} |")


o = ["## Results table", "",
     "| Set | Method | Area at the calibrated margin (km2) | Achieved miss, 95% interval | Fires | Area read at exactly 10% miss (km2) | Run-days warned |",
     "|---|---|---|---|---|---|---|"]
for n in M:
    r = ca[n]
    o.append(row("California held-out", n, r, f"{r['warned']} of {r['run_days']} (b)" if "warned" in r else "-"))
gA = kr["A TRACKER"]
for n in M:
    a = kr.get(f"A {n}")
    o.append(row("Korea, leave-one-fire-out", n, kr[n], f"{a['warned']} of {a['run_days']} (a)" if a else "-"))
o.append("| Korea | Gust rule G (kcf-aloft) | - | - | 12 | - | 4 of 9 (a) |")
o += ["", "## Ratios (paired fire bootstrap)", "", "| Set | Comparison | Area ratio at calibrated margins (95%) | Ratio read at exactly 10% miss |", "|---|---|---|---|"]
for s, d in (("California held-out", ca), ("Korea", kr)):
    for k, v in d.items():
        if k.startswith("ratio "):
            o.append(f"| {s} | {k[6:]} | {v['ratio']:.3f} ({v['lo']:.3f} to {v['hi']:.3f}) | {v['frontier_ratio']:.3f} |")
o += ["", "## Target A detail", "",
      "| Method | Warned of 9 | Onset days warned | Warned without 25 March | Alarms on the no-run fire-days | Model alarm point-days in the burden set (range over left-out fires) | G alarm point-days |",
      "|---|---|---|---|---|---|---|"]
for n in M:
    a = kr.get(f"A {n}")
    if a:
        pd_ = [x["tracker_model_alarm_point_days"] for x in a["days"]]
        o.append(f"| {LABEL[n]} | {a['warned']} | {a['warned_onset']} of {a['onset_days']} | {a['warned_without_25_march']} of 8 | "
                 f"{a['alarms_on_no_run_fire_days']} of {a['no_run_fire_days']} | {min(pd_)} to {max(pd_)} | {a['burden']['G_alarm_point_days']} |")
o += ["", "### Every run fire-day (TRACKER; noupdate; nofc)", "",
      "| Fire | KST day | First run hour | Onset | p at that hour | threshold c | Warned | p (update off) | Warned (update off) | Warned (forecast off) | G (kcf-aloft) |",
      "|---|---|---|---|---|---|---|---|---|---|---|"]
GW = {("KFS_01", "2025-03-25"), ("KFS_02", "2022-03-04"), ("KFS_02", "2022-03-05"), ("KFS_03", "2022-03-05")}
for x, y, z in zip(kr["A TRACKER"]["days"], kr["A TRACKER-noupdate"]["days"], kr["A TRACKER-nofc"]["days"]):
    o.append(f"| {x['fire']} | {x['kst_day']} | {x['first_run_kst']:02d} | {'yes' if x['onset'] else 'no'} | {x['p']:.3f} | {x['c']:.3f} | "
             f"{'yes' if x['warned'] else 'no'} | {y['p']:.3f} | {'yes' if y['warned'] else 'no'} | {'yes' if z['warned'] else 'no'} | "
             f"{'yes' if (x['fire'], x['kst_day']) in GW else 'no'} |")
o += ["", "## Korea, secondary rows", "", "| Method | Row | Area (km2) | Miss, 95% interval | Area read at 10% |", "|---|---|---|---|---|"]
for n in M:
    for tag, lab in (("CA-fit LOFO-kappa", "California-fitted, kappa leave-one-fire-out"), ("CA-transfer", "California-fitted and calibrated")):
        r = kr[f"{tag} {n}"]
        fa = r["frontier_area"]
        o.append(f"| {LABEL[n]} | {lab} | {r['area']:.1f} | {pct(r['miss'])} ({100 * r['miss_lo']:.1f} to {100 * r['miss_hi']:.1f}) | "
                 f"{'-' if fa != fa else f'{fa:.1f}'} |")
m = pd.read_csv(D / "mar25.csv")
o += ["", "## 25 March 2025, KFS_01 (model fitted without KFS_01)", "",
      "| KST | reach 5 h (km) | fc gust | fc 850 hPa wind | fc RH min | growth last hour (km) | enter | p before update | p after | c | alarm | m quiet | m run | TRACKER margin | FIXED | QUANTILE | update off | forecast off |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]


def mk(q, miss):
    return f"{q:.1f} **M**" if miss else f"{q:.1f} h"


for _, r in m.iterrows():
    o.append(f"| {int(r.kst_hour):02d} | {r.reach_km:.1f} | {r.gust_ms:.1f} | {r.w850_ms:.1f} | {r.rhmin_pct:.0f} | {r.o_g1_km:.2f} | "
             f"{r['enter_TRACKER']:.3f} | {r['prior_TRACKER']:.3f} | {r['p_TRACKER']:.3f} | {r['c_TRACKER']:.3f} | "
             f"{'yes' if r['p_TRACKER'] >= r['c_TRACKER'] else 'no'} | {r['m0_TRACKER']:.1f} | {r['m1_TRACKER']:.1f} | "
             f"{mk(r['q_TRACKER'], r['miss_TRACKER'])} | {mk(r['q_FIXED'], r['miss_FIXED'])} | {mk(r['q_QUANTILE'], r['miss_QUANTILE'])} | "
             f"{mk(r['q_TRACKER-noupdate'], r['miss_TRACKER-noupdate'])} | {mk(r['q_TRACKER-nofc'], r['miss_TRACKER-nofc'])} |")
o += ["", "| Method | Hours missed of 12 (09 to 20 KST) | Largest margin (km) | Mean flagged area (km2) |", "|---|---|---|---|"]
mar = {}
for n in M:
    mar[n] = dict(missed=int(m[f"miss_{n}"].sum()), max_margin=float(m[f"q_{n}"].max()), mean_area=float(m[f"area_{n}"].mean()))
    o.append(f"| {LABEL[n]} | {mar[n]['missed']} | {mar[n]['max_margin']:.1f} | {mar[n]['mean_area']:.0f} |")
open(D / "tables.md", "w").write("\n".join(o) + "\n")

tq, tf = ca["ratio TRACKER / QUANTILE"], kr["ratio TRACKER / FIXED"]
A = kr["A TRACKER"]
targets = {
    "A": dict(warned=A["warned"], of=A["run_days"], gust_rule=4, passed=A["warned"] >= 5,
              strict_passed=A["warned"] >= 5 and A["alarms_on_no_run_fire_days"] <= 0,
              alarms_on_no_run_fire_days=A["alarms_on_no_run_fire_days"], onset_warned=A["warned_onset"], onset_days=A["onset_days"]),
    "B": dict(ratio=tf["ratio"], lo=tf["lo"], hi=tf["hi"], frontier_ratio=tf["frontier_ratio"], miss_valid=valid(kr["TRACKER"]),
              passed=valid(kr["TRACKER"]) and tf["ratio"] < 1 and tf["frontier_ratio"] < 1),
    "C": dict(ratio=tq["ratio"], lo=tq["lo"], hi=tq["hi"], frontier_ratio=tq["frontier_ratio"], miss_valid=valid(ca["TRACKER"]),
              passed=valid(ca["TRACKER"]) and tq["ratio"] <= 1 and tq["frontier_ratio"] <= 1)}
json.dump(dict(targets=targets, california_held_out=ca, korea=kr, march25=mar, kept=kept, archive=arch, proposals=props, dev=dev),
          open(H / "numbers.json", "w"), indent=1)
print(json.dumps(targets, indent=1))
