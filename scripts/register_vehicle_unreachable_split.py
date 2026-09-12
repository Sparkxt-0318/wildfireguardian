#!/usr/bin/env python
"""Register the WFG-264 vehicle-unreachable split counts in docs/NUMBERS.json.

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `vus_` keys, and writes it back.

    python scripts/register_vehicle_unreachable_split.py          # upsert + report
    python scripts/register_vehicle_unreachable_split.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = ("data/processed/vehicle_unreachable_split/"
            "split_20260912T033329Z.json")
PREFIX = "vus_"

#: The caveat every one of these keys carries. It leads with what a reader who
#: quotes one of them is most likely to get wrong: none of these is a
#: misclassification count.
BAND = (
    "NOT A MISCLASSIFICATION COUNT, AND NOT A COUNT OF WHY. These keys describe "
    "the committed 439-series `no_surviving_vehicle_ingress` class — the homes "
    "the A4 dispatch sheet lists under 「차량 도달 불가」. Four facts travel "
    "together or none may be quoted: (1) NO COMMITTED NUMBER MOVES and nothing "
    "was re-run or refit. The committed class sizes are 24 (dispatch slice) and "
    "32 (full-coverage re-run) and both re-derive here against "
    "four_way_counts and responder_exposure before anything else is read. "
    "(2) THE CLASS IS DECIDED BY rescuer_reachable, the survival-aware, "
    "detouring, time-expanded router. best_closing_window_min — the field these "
    "counts read — is assess_ingress's DIRECT-corridor screening, stored by "
    "build_dispatch_list for context only. The two tests are different by "
    "design and this measurement does not second-guess the classification. "
    "(3) WHAT IT DOES ESTABLISH is about the SENTENCE, not the class: the sheet "
    "asserted 「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」, and for the "
    "homes counted by vus_corridor_reachable_* the run's own corridor "
    "assessment recorded a corridor whose earliest fire-cutoff crossing is at "
    "least a full responder safety margin after the responder's ETA. (4) THE "
    "SPLIT BY RETURN SITE IS NOT MEASURED. Three return sites collapse into this "
    "class (pre-search refusal at the DEPOT's own node, exhausted Dijkstra, "
    "route reached but enters_hazard) and the committed artifacts do not record "
    "which one fired; recovering that would mean re-running the scan. ⚠ A NULL "
    "best window is an infinity of EITHER sign — no drive path from any depot, "
    "or a corridor the fire never crosses — so vus_no_finite_window_* rules out "
    "both worlds together and neither separately. An earlier draft of this "
    "measurement read null as the first alone; a constructed reproduction "
    "falsified it before it shipped. ⚠ The "
    "threshold is READ from each artifact's provenance.assumed "
    "responder_safety_margin_min (12.0 min) and never typed into the script. "
    "docs/routing_limitations.md §7 states the method and what it does NOT show."
)

FORBIDDEN = [
    "the unreachable class is wrong",
    "these homes are reachable",
    "the vehicle can get in",
    "차량 도달 불가 판정이 틀렸습니다",
    "구조대가 갈 수 있습니다",
    "출동 지시서 문장은 확인되었습니다",
]

_SAMPLE = ("영덕 2025 · 439-series responder arm · vehicle_cutoff 0.7 · "
           "dispatch_delay 30 min · safety_margin 12 min · budget 75 min · "
           "synthetic hazard, real OSM drive network")

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("class_size_dispatch_slice", "arms.0.n_unreachable", "homes",
     "the committed dispatch slice's `no_surviving_vehicle_ingress` class size, "
     "re-derived here from unreachable_homes and cross-checked against both "
     "four_way_counts and responder_exposure. It is the identity control the "
     "other dispatch-slice keys stand on, not a new figure"),
    ("no_finite_window_dispatch_slice",
     "arms.0.n_no_finite_best_closing_window", "homes",
     "how many of those homes have NO finite best closing window. A null window "
     "is an infinity of either sign and both are real worlds: -inf is "
     "ingress_corridor's NetworkXNoPath branch (no depot has any drive path at "
     "all) and +inf is a corridor the fire never crosses. So a zero here rules "
     "out BOTH worlds together and neither separately, and every home in the "
     "class had at least one depot with a road and a corridor the fire does "
     "cross. It is ZERO, and an empty sub-case is published as an empty "
     "sub-case"),
    ("corridor_survives_past_eta_dispatch_slice",
     "arms.0.n_corridor_survives_past_responder_eta", "homes",
     "how many have a direct corridor whose earliest fire-cutoff crossing is at "
     "or after the responder's ETA. For these, fire had not closed the best "
     "corridor by the time the responder would have arrived; only the safety "
     "margin puts them out of reach"),
    ("corridor_reachable_dispatch_slice",
     "arms.0.n_corridor_reachable_by_the_screening_test", "homes",
     "the strong version of the same: how many have a stored window at or above "
     "the run's own 12-minute safety margin, which can only have come from "
     "assess_ingress's FEASIBLE branch. For these the direct-corridor screening "
     "itself returned reachable=True while the survival-aware router returned "
     "no route, and the sheet told a dispatcher the road was blocked by fire"),
    ("class_size_full_coverage", "arms.1.n_unreachable", "homes",
     "the same class size on the full-coverage re-run (all 441 origins rather "
     "than the committed 20-point dispatch slice), with the same two identity "
     "controls passed before anything downstream was read"),
    ("no_finite_window_full_coverage",
     "arms.1.n_no_finite_best_closing_window", "homes",
     "the same count on the full-coverage re-run. Also zero, so the sub-cases "
     "are empty on both committed fields and not only on the slice"),
    ("corridor_survives_past_eta_full_coverage",
     "arms.1.n_corridor_survives_past_responder_eta", "homes",
     "the corridor-survives-past-ETA count on the full-coverage re-run"),
    ("corridor_reachable_full_coverage",
     "arms.1.n_corridor_reachable_by_the_screening_test", "homes",
     "the screening-reachable count on the full-coverage re-run. It is larger "
     "than the dispatch slice's because the slice commits 24 of these homes and "
     "the full re-run 32, not because any home changed class"),
]


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES:
        cur = art
        for part in path.split("."):
            cur = cur[int(part)] if part.isdigit() else cur[part]
        out[PREFIX + suffix] = {
            "value": cur,
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation
            + ". Regenerate: python scripts/measure_vehicle_unreachable_split.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": _SAMPLE,
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_vehicle_unreachable_split.py opens two "
                    "committed artifacts and nothing else — no network, no raw "
                    "bundle, no DEM, no snapshot graphml, no clock in the "
                    "measurement. It REFUSES to write anything unless "
                    "len(unreachable_homes) re-derives against both "
                    "four_way_counts and responder_exposure on each arm and "
                    "four_way_sums_to_n is true, and it reads the safety-margin "
                    "threshold out of each artifact's own provenance rather than "
                    "carrying one."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "vehicle_unreachable_split",
            "notes": "docs/routing_limitations.md §7 states the code condition, "
                     "the three return sites, the method, the result and what it "
                     "does NOT show. It moves no committed count and refits "
                     "nothing; the repair it justifies is a sentence.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": path}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE vehicle-unreachable-split registry entries: "
                  + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} vehicle-unreachable-split entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} vehicle-unreachable-split entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
