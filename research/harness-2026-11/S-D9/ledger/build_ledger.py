"""Build the S-D9 fire-exposure ledger from evidence already committed in the repository.

The script only reads. It writes EXPOSURE_LEDGER.csv (one row per fire),
INTERVAL_LEDGER.csv (one row per enumerable scored interval) and
LEDGER_SUMMARY.json, which holds the counts and the SHA-256 of both CSVs.
Every exposure claim cites a repository evidence path and the commit that
first added that path.

Exposure classes, most exposed first:
  FIT          outcomes used to fit parameters of some model in the lineage
  SELECTED_ON  outcomes used for model, variant or hyperparameter selection,
               or inspected before a selection
  SCORED       forecast outcomes scored and reported after freezing
  INSPECTED    forecast outputs or perimeters viewed or used, but not scored
  UNTOUCHED    no evidence of any of the above in this repository

A fire's overall class is the most exposed class across all lineages. Fires
named only in prose (HUNT, LEVELOCK, GOFER) keep their own rows; the
evidence for them is a prose note and their artifacts are not in git.

Run from the repository root:
  python3 research/harness-2026-11/S-D9/ledger/build_ledger.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RANK = ["FIT", "SELECTED_ON", "SCORED", "INSPECTED", "UNTOUCHED"]

EV = {
    "catalog": "forecast/data/environment/events.json",
    "split_v2": "research/forecast-v2/SPLIT.json",
    "us2024": "research/forecast-v2/PREASSESSMENT_US2024_TIMESTAMPS.json",
    "kr2025": "research/forecast-v2/PREASSESSMENT_KOREA2025_WINDOWS.json",
    "v2_readme": "research/forecast-v2/README.md",
    "us_preds": "forecast/runs/20261030_perimeter_trained/execution_v3/heldout",
    "kr_preds": "forecast/runs/20261030_perimeter_trained/execution_v3/korean2025",
    "cellhour": "forecast/runs/20261010_categorical_balanced_benchmark/protocol.json",
    "cellhour_part": "forecast/runs/20261010_categorical_balanced_benchmark/partition_verification.json",
    "m548_audit": "forecast/documents/observed_runtime_audit_20261013.json",
    "m548_doc": "forecast/documents/observed_combined_evaluation.md",
    "farsite": "research/forecast-v2/FARSITE_SCORES.json",
    "routing": "research/routing/INDEPENDENT_REPORT.v1.md",
    "sipp": "research/sipp-routing",
    "caldor_rim": "research/next-combined/caldor-rim-alignment-1e646b164/CALDOR_RIM_ALIGNMENT_AUDIT.md",
    "november": "research/november-20261111/README.md",
    "prereg": "forecast/documents/preregistration_blind_test.md",
}


def first_commit(path: str) -> str:
    """Return the commit that first added the path (the oldest in --diff-filter=A history)."""
    out = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%H", "--", path],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    if not out:
        raise SystemExit(f"evidence path has no adding commit: {path}")
    return out[-1]


def load(key: str):
    return json.loads((ROOT / EV[key]).read_text())


def main() -> None:
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    if shallow != "false":
        raise SystemExit("shallow clone: first-adding commits would be wrong; run `git fetch --unshallow` first")
    commits = {k: first_commit(v) for k, v in EV.items()}
    catalog = load("catalog")
    split = load("split_v2")
    cellhour = load("cellhour")["original_splits"]
    us = load("us2024")
    kr = load("kr2025")
    m548 = load("m548_audit")
    farsite = load("farsite")

    fires: dict[str, dict] = {}

    def fire(fid, name, country, year, source):
        fires.setdefault(fid, {
            "fire_id": fid, "name": name, "country": country, "year": year,
            "label_source": source, "exposures": [],
        })
        return fires[fid]

    def expose(fid, lineage, cls, what, ev_key):
        assert cls in RANK, cls
        fires[fid]["exposures"].append({
            "lineage": lineage, "class": cls, "what": what,
            "evidence": EV[ev_key], "evidence_first_commit": commits[ev_key],
        })

    for e in catalog:
        src = "kriged arrival reconstruction (Zenodo 21788344)" if e["country"] == "KR" \
            else "NIROPS perimeters + kriged arrival (Zenodo 21788344)"
        fire(e["id"], e["name"], e["country"], e["year"], src)

    # Cell-hour benchmark (Oct 10; mixed_3_5_7_9 checkpoint lineage).
    role = {"train": "FIT", "validation": "SELECTED_ON", "test": "SCORED"}
    for fid, part in cellhour.items():
        expose(fid, "cellhour_benchmark_20261010", role[part],
               f"original event split '{part}'; split unit cell_hour; "
               "test fires disjoint from train/validation", "cellhour")

    # c651 (= M548) lineage, as SPLIT.json c651_training_overlap describes it.
    for fid in split["fit"]["us_perimeter_and_kriged"] + ["KFS_02", "KFS_03"]:
        expose(fid, "c651", "FIT", "c651 fit on cell-hours of this fire", "split_v2")
    expose("ID-BOF-000683_Wapiti_Wapiti", "c651", "SELECTED_ON",
           "c651 selection followed inspection of Wapiti and other test events", "split_v2")
    m548_events = sorted({c["event"] for c in m548["cases"]})
    for fid in m548_events:
        n = sum(1 for c in m548["cases"] if c["event"] == fid and c["status"] == "complete")
        expose(fid, "c651", "SCORED",
               f"M548 observed evaluation, {n} complete of {len(m548['cases'])} attempted cases (aggregate in git)",
               "m548_audit")
    for fid in us["per_fire"]:
        expose(fid, "c651", "SCORED", "c651_mc/meanfield scored on forecast-v2 US2024 common cells", "us2024")

    # forecast-v2 lineage (seven final variants, logistic, dilation).
    for fid in split["fit"]["us_perimeter_and_kriged"]:
        expose(fid, "forecast_v2", "FIT", "US fit fire; also a leave-one-year-out development fold", "split_v2")
        expose(fid, "forecast_v2", "SELECTED_ON", "development fold used for equal-fire Brier variant selection", "split_v2")
    for fid in split["fit"]["korean_kriged_only"]:
        expose(fid, "forecast_v2", "FIT", "Korean kriged input to the mixed regime", "split_v2")
    for fid, pf in us["per_fire"].items():
        expose(fid, "forecast_v2", "SCORED",
               f"{pf['eligible_duration_intervals']} intervals (<=48 h) scored, 16 predictors, predictions in git", "us2024")
    for fid in sorted(set(c["case"]["event"] for c in kr["cases"])):
        n = sum(1 for c in kr["cases"] if c["case"]["event"] == fid)
        expose(fid, "forecast_v2", "SCORED", f"{n} Korea2025 12 h windows attempted; predictions in git", "kr2025")

    # Stored FARSITE deterministic scenarios.
    for fid in sorted({c["event"] for c in farsite["cases"]}):
        n = sum(1 for c in farsite["cases"] if c["event"] == fid)
        expose(fid, "farsite_scenarios", "SCORED", f"{n} stored deterministic scenarios scored", "farsite")

    # Routing and planner: forecast outputs used as routing inputs (viewed, not scored).
    for fid, what in [
        ("KFS_01", "Uiseong-Andong and Yeongdeok routing panels share this fire"),
        ("KFS_05", "Hongseong routing panel"),
    ]:
        expose(fid, "routing_panels", "INSPECTED", what, "routing")
    for fid, what in [("KFS_02", "uljin_2022 routing/SIPP inputs"), ("KFS_11", "miryang_2022 routing/SIPP inputs"),
                      ("KFS_01", "uiseong_andong_2025 routing/SIPP inputs"), ("KFS_05", "hongseong routing/SIPP inputs")]:
        expose(fid, "routing_panels", "INSPECTED", what, "sipp")

    # Fires outside the catalog.
    fire("Caldor2021", "Caldor", "US", 2021, "retrospective perimeter timing construction")
    fire("Rim2013", "Rim", "US", 2013, "retrospective perimeter timing construction")
    for fid in ("Caldor2021", "Rim2013"):
        expose(fid, "routing_panels", "INSPECTED",
               "perimeters used for routing/thermal construction; native c651 forecast NOT run (alignment unestablished)",
               "caldor_rim")
    fire("HUNT2019", "HUNT", "unknown (not in git)", 2019, "unknown (artifacts held locally)")
    fire("LEVELOCK2019", "LEVELOCK", "unknown (not in git)", 2019, "unknown (artifacts held locally)")
    for fid in ("HUNT2019", "LEVELOCK2019"):
        expose(fid, "d4_experimental", "SCORED",
               "retrospective sensitivity: d4 vs persistence vs logistic Brier/AP reported (prose only)", "november")
    fire("GOFER_archive", "GOFER (28 CA fires; members not listed in git)", "US", None,
         "GOFER hourly perimeters")
    expose("GOFER_archive", "november_readiness", "INSPECTED",
           "archive recovered and checksum-checked; no forecast scored; event overlap with fit fires unresolved",
           "november")

    # Write the fire-level ledger.
    rows = []
    for f in sorted(fires.values(), key=lambda r: (r["country"], r["fire_id"])):
        classes = {x["class"] for x in f["exposures"]} or {"UNTOUCHED"}
        overall = min(classes, key=RANK.index)
        rows.append({
            "fire_id": f["fire_id"], "name": f["name"], "country": f["country"], "year": f["year"],
            "label_source": f["label_source"], "overall_class": overall,
            "lineages": ";".join(sorted({x["lineage"] for x in f["exposures"]})),
            "exposures": " | ".join(f"{x['lineage']}:{x['class']}: {x['what']} "
                                    f"[{x['evidence']} @ {x['evidence_first_commit'][:12]}]"
                                    for x in f["exposures"]),
        })
    fire_csv = to_csv(rows)
    (OUT / "EXPOSURE_LEDGER.csv").write_text(fire_csv)

    # Interval-level ledger for every interval enumerable from committed evidence.
    irows = []
    for c in us["cases"]:
        irows.append({"cohort": "US2024_forecast_v2", "event": c["event"], "cutoff": c["cutoff"],
                      "endpoint": c["endpoint"], "hours": round(c["hours"], 6), "status": "SCORED",
                      "evidence": EV["us2024"]})
    for c in kr["cases"]:
        k = c["case"]
        irows.append({"cohort": "KR2025_forecast_v2", "event": k["event"], "cutoff": k["cutoff"],
                      "endpoint": k["endpoint"], "hours": k["hours"], "status": "ATTEMPTED",
                      "evidence": EV["kr2025"]})
    for c in m548["cases"]:
        irows.append({"cohort": "M548_observed_20261012", "event": c["event"], "cutoff": c["cutoff"],
                      "endpoint": c["endpoint"], "hours": round(c["duration_minutes"] / 60, 6),
                      "status": c["status"].upper(), "evidence": EV["m548_audit"]})
    for c in farsite["cases"]:
        irows.append({"cohort": "FARSITE_stored", "event": c["event"], "cutoff": c["cutoff"],
                      "endpoint": c["endpoint"], "hours": "", "status": c["status"],
                      "evidence": EV["farsite"]})
    int_csv = to_csv(irows)
    (OUT / "INTERVAL_LEDGER.csv").write_text(int_csv)

    counts = {}
    for r in rows:
        counts[r["overall_class"]] = counts.get(r["overall_class"], 0) + 1
    m548_plan = 324
    summary = {
        "schema": "wfg.s-d9.exposure-ledger/1",
        "fire_rows": len(rows),
        "overall_class_counts": counts,
        "untouched_fires_in_repository": [r["fire_id"] for r in rows if r["overall_class"] == "UNTOUCHED"],
        "us2024_interval_accounting": {
            "consecutive_survey_intervals_planned_by_m548": m548_plan,
            "scored_forecast_v2_le_48h": len(us["cases"]),
            "not_scored_by_forecast_v2_gt_48h_or_outside_catalog_window": m548_plan - len(us["cases"]),
            "note": "The 51 intervals over 48 h are counted, not enumerated: their survey timestamps "
                    "are not in git (they come from the NIROPS archive). Only 32 can be derived as gaps between "
                    "consecutive eligible intervals.",
        },
        "interval_rows": {k: sum(1 for r in irows if r["cohort"] == k)
                          for k in sorted({r["cohort"] for r in irows})},
        "sha256": {"EXPOSURE_LEDGER.csv": sha(fire_csv), "INTERVAL_LEDGER.csv": sha(int_csv)},
        "evidence_first_commits": {EV[k]: v for k, v in commits.items()},
    }
    (OUT / "LEDGER_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in ("fire_rows", "overall_class_counts", "interval_rows", "sha256")},
                     indent=2))


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == "__main__":
    main()
