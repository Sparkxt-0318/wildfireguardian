"""C1-C4 admission study with matched strict unknown-source semantics.

This deliberately does not claim identifiable evacuation error rates when the
truth or forecast has unknown global sources. Every attempted case is retained
with null truth scores and an explicit unresolved admission when unsupported.
Joint-known-support Brier is a separate diagnostic, not complete-domain skill.
No old zero-assignment policy is silently applied to trajectory sentinel -2.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
from types import SimpleNamespace
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experimental/sipp-routing/src"))
from wfg_sipp.frontend import sipp_plan


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(); p.add_argument("--exports", required=True); p.add_argument("--cases", required=True)
    p.add_argument("--data-root", required=True); p.add_argument("--out", required=True)
    a = p.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    cases = [c for c in json.loads(Path(a.cases).read_text()) if c["panel"] == "Korean"]
    exports = {}
    for recfile in Path(a.exports).glob("*/*/FORECAST_RECORD_*.json"):
        rec = json.loads(recfile.read_text()); exports[rec["event"], rec["cutoff_utc"]] = (recfile, rec)
    streams = {name: gzip.open(out / (name + ".jsonl.gz"), "wt") for name in ("C1", "C2", "C3", "C4")}
    summaries = {}; pins = {}; windows = {}; admission_calls = 0
    try:
        for case in cases:
            md = json.loads((Path(case["packet"]) / "NATIVE_METADATA.json").read_text())
            source = md["construction"]["parent_forecast"]; key = (source["event_id"], source["cutoff_utc"])
            recfile, rec = exports[key]; npz = recfile.parent / rec["npz"]
            if sha(npz) != rec["npz_sha256"]:
                raise RuntimeError("V3_HASH")
            pins[str(npz)] = rec["npz_sha256"]
            request = json.loads(Path(case["request"]).read_text())
            if key not in windows:
                with np.load(npz, allow_pickle=False) as z:
                    first = z["trajectory_first_burn_hour"].copy()
                    q = z["new_burn_probability"].copy()
                    known = (first[0] != -2) & z["source_burned_area_valid"] & (z["source_burned_area"] == 0)
                    previous = z["source_burned_area_valid"] & (z["source_burned_area"] == 1)
                # Strict global-source admission, because an unknown source can
                # radiate into a known receiver. A route-local mask is not enough.
                supported = bool(np.all(first != -2))
                rng = np.random.default_rng(20261008)
                uniform = rng.random((32, *q.shape))
                q_known = np.where(known, np.nan_to_num(q, nan=0.0), 0.0)
                def independent(probability, count):
                    f = np.where(uniform[:count] < probability, 1, -1).astype(np.int16)
                    f[:, previous] = 0; f[:, first[0] == -2] = -2
                    return f
                candidates = {
                    "independent_K4_matched_support": independent(q_known, 4),
                    "trajectory_K4": first[:4], "trajectory_K16": first[:16],
                    "persistence": independent(np.zeros_like(q), 16),
                    "current_state_only": independent(np.zeros_like(q), 16),
                    "uniform": independent(np.full_like(q, q_known[known].mean() if known.any() else 0), 16)}
                for factor in (0.5, 1.0, 2.0):
                    with np.errstate(divide="ignore", invalid="ignore"):
                        changed = -np.expm1(np.log1p(-q_known) * factor)
                    candidates["rate_x%g" % factor] = independent(changed, 16)
                for k in (4, 8, 16, 32):
                    candidates["trajectory_K%d" % k] = first[:k]
                windows[key] = first, known, supported, candidates
            first, known, supported, candidates = windows[key]
            configs = [("C1", name, "all", 1.0) for name in ("independent_K4_matched_support", "trajectory_K4", "trajectory_K16")]
            configs += [("C2", name, "all", 1.0) for name in ("rate_x0.5", "rate_x1", "rate_x2", "persistence", "uniform", "current_state_only")]
            configs += [("C3", "trajectory_K%d" % k, "all" if fraction == 1 else "k_of_m", fraction) for k in (4, 8, 16, 32) for fraction in (1.0, .9, .75)]
            if case["region"] in ("uiseong_andong_2025", "yeongdeok_2025"):
                configs += [("C4", "trajectory_K16", "all", 1.0)]
            for campaign, name, rule, fraction in configs:
                model = SimpleNamespace(supported=supported)
                # All supplied actual windows fail this explicit admission. If
                # future complete inputs appear, this script refuses to invent
                # a complete campaign evaluator or call a contact-only oracle.
                if supported:
                    raise RuntimeError("Complete support requires the full-policy campaign runner")
                plan = sipp_plan(None, request, model, wall_s=30)
                admission_calls += 1
                if plan["status"] != "UNRESOLVED":
                    raise RuntimeError("Unknown source support escaped admission")
                f = candidates[name]; predicted = (f[:, known] > 0).mean(axis=0)
                truth_indices = range(512, 612) if campaign != "C4" else [None]
                for truth_index in truth_indices:
                    brier = float(np.mean((predicted - (first[truth_index, known] > 0)) ** 2)) if truth_index is not None and known.any() else None
                    row = dict(cutoff=key[1], event=key[0], region=case["region"], mission=case["mission"],
                               truth_source="reconstructed_arrival" if campaign == "C4" else "holdout_trajectory",
                               forecast_source=name, trajectory_truth_index=truth_index,
                               planning_indices=list(range(len(f))) if name.startswith("trajectory") else None,
                               outcome="unresolved", reason="UNKNOWN_GLOBAL_SOURCE_SUPPORT",
                               true_contact=None, true_peak=None, true_dose=None,
                               arrival_s=None, clairvoyant_arrival_s=None, clairvoyant_outcome="unresolved",
                               false_safe=None, false_refusal=None, regret_s=None,
                               truth_score_supported=False, brier_joint_known_support=brier,
                               brier_denominator_cells=int(known.sum()),
                               acceptance={"rule": rule, "k": int(np.ceil(fraction * len(f))), "m": len(f)},
                               radiation_law="v1", construction_version="wfg.hazard.construction/2",
                               scope="strict admission study, not a completed scored OSSE")
                    streams[campaign].write(json.dumps(row) + "\n")
                    group = summaries.setdefault((campaign, name, rule, fraction), {"cases": 0, "unresolved": 0, "scorable_truth_cases": 0, "brier_sum": 0.0, "brier_cases": 0})
                    group["cases"] += 1; group["unresolved"] += 1
                    if brier is not None:
                        group["brier_sum"] += brier; group["brier_cases"] += 1
            arrival = Path(a.data_root) / "regions" / key[0] / "arrival_time_hours.tif"
            if arrival.exists():
                pins[str(arrival)] = sha(arrival)
    finally:
        for stream in streams.values():
            stream.close()
    table = []
    for (campaign, source, rule, fraction), counts in summaries.items():
        table.append(dict(campaign=campaign, forecast_source=source, rule=rule, fraction=fraction,
                          **counts, mean_brier_joint_known_support=counts["brier_sum"] / counts["brier_cases"] if counts["brier_cases"] else None,
                          false_safe_rate=None, false_refusal_rate=None, wilson_interval=None))
    result = dict(status="EXECUTED_ADMISSION_UNRESOLVED, OSSE_ERROR_RATES_UNIDENTIFIED", windows=len(windows), missions=len(cases),
                  admission_calls=admission_calls, holdout_indices=[512, 611], pool_indices=[0, 511],
                  seed=20261008, host=platform.platform(), python=sys.version,
                  source_sha256=sha(__file__), input_sha256=pins, summaries=table,
                  Caldor="NOT_RUN, learned forecast alignment not established", law_v2="NOT_RUN, track1A physics gate unresolved",
                  dependence="one-hour single-component transition has no multi-step coherence difference",
                  uncertainty="Null scores are unscorable, not zero false-safe or false-refusal. Shared truth draws/mission windows are clustered; no population Wilson CI is computed.")
    (out / "RESULTS.json").write_text(json.dumps(result, indent=2) + "\n")
    with (out / "SUMMARY.csv").open("w") as f:
        w = csv.DictWriter(f, list(table[0])); w.writeheader(); w.writerows(table)
    print(json.dumps({k: result[k] for k in ("status", "windows", "missions", "admission_calls")}))


if __name__ == "__main__":
    main()
