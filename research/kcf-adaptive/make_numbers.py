"""Collect the headline numbers quoted in RESULTS.md into numbers.json (from derived/*.json only).

    python make_numbers.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE / "derived"


def model_row(m):
    f, c = m["flagging"], m["calibration"]
    return dict(brier=m["brier"], area_per_burned_cell=f["expected_area_per_burned_cell"],
                expected_miss_rate=f["expected_miss_rate"], ece=c["ece"], lowest_bin_gap=c["lowest_bin_gap"])


def arm1():
    out = {}
    o = json.load(open(D / "arm1_output.json"))
    out["output_level_1F"] = {k: model_row(v) for k, v in o["us2024"]["all_windows"]["models"].items()}
    f = D / "arm1.json"
    if not f.exists():
        out["weight_level"] = "NOT RUN"
        return out
    d = json.load(open(f))
    g = d["reproduction_gate"]
    out["reproduction_gate"] = {k: g[k] for k in ("max_abs_diff", "brier_rebuilt", "brier_committed_meanfield",
                                                  "relative_brier_difference", "passes", "label")}
    for key in ("all_windows", "windows_with_history"):
        if key in d:
            r = d[key]
            out[key] = dict(entries=r["entries"], positives=r["positives"],
                            models={k: model_row(v) for k, v in r["models"].items()},
                            paired_brier_difference={k: dict(point=v["point"], ci95=v["ci95"], fires=v["fires_favouring_a"])
                                                     for k, v in r["paired_brier_difference"].items()})
    for key in ("leakage", "verdict_arm1", "LEAKY_NOT_A_RESULT", "parameter_shift", "runs_windows", "settings"):
        if key in d:
            out[key] = d[key]
    return out


def arm2():
    d = json.load(open(D / "arm2.json"))
    pick = lambda a: {k: v for k, v in a.items() if k != "per_fire"}  # noqa: E731
    out = dict(meta=d["meta"], gate=d["gate_kcf_margin"], verdict=d["verdict_arm2"], korea_chosen_k=d["korea_chosen_k"],
               chosen_k_by_fold=sorted({v["chosen_k"] for v in d["k_selection"].values()}))
    out["lofo"] = {h: {k: pick(v) for k, v in d["lofo"][h].items()} for h in ("5", "8")}
    out["korea"] = {h: {k: v["total"] for k, v in d["korea"][h].items()} for h in ("5", "8")}
    out["march25"] = {h: dict(summary=d["march25"][h]["summary"],
                              max_calibration_score_km=d["march25"][h]["max_calibration_score_km"]) for h in ("5", "8")}
    return out


if __name__ == "__main__":
    res = dict(arm1=arm1(), arm2=arm2())
    (HERE / "numbers.json").write_text(json.dumps(res, indent=1) + "\n")
    print("numbers.json", {k: sorted(v)[:12] for k, v in res.items()})
