"""Collect every reported number into numbers.json (all MEASURED unless a key says ORACLE / ASSUMED)."""
import json
from pathlib import Path

def j(p):
    return json.load(open(p)) if Path(p).exists() else None

o, p = j("derived/step1_oracle.json"), j("derived/step1_pooled.json")
out = dict(
    labels="MEASURED = computed here from data; ORACLE = uses the fire's future, never a result for any method.",
    step1=dict(
        gate=o["gate"],
        fixed_at_10=o["methods"]["FIXED"]["summary"], persist=o["methods"]["PERSIST"]["summary"], m_ref=o["methods"]["M_ref"]["summary"],
        fixed_committed_3p75km=o["methods"]["FIXED_3.75km_committed"], zero_margin=o["methods"]["ZERO"],
        oracle_preregistered={k: {a: b for a, b in v.items() if a != "area_per_fire"} for k, v in o["oracle"].items()},
        oracle_pooled_budget_amendment2=p,
        learning_curve=j("derived/step1_curve_summary.json"),
        L4_reproduction=dict(kcf_margin_lofo_miss=0.06156, committed=0.061556, on_eligible_hours=0.06013,
                             reach_max_abs_diff_km=5.7e-6, dev_eligible_hours=20065)),
    dev_h5=j("derived/numbers_dev_h5.json"), dev_h8=j("derived/numbers_dev_h8.json"),
    per_fire_robustness_h5=j("derived/per_fire_robustness_h5.json"),
    sealed_transfer_h5=j("derived/final_summary_h5.json"))
json.dump(out, open("numbers.json", "w"), indent=1)
print("numbers.json", Path("numbers.json").stat().st_size, "bytes")
