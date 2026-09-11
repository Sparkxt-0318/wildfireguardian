#!/usr/bin/env python
"""Register the Yeongdeok present-perimeter counts in docs/NUMBERS.json (WFG-129).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `ppy_yeongdeok_` keys, and writes it back.

    python scripts/register_present_perimeter_yeongdeok.py          # upsert + report
    python scripts/register_present_perimeter_yeongdeok.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_yeongdeok_2025.json"
PREFIX = "ppy_yeongdeok_"

#: The caveat every one of these keys carries. It leads with the thing a reader
#: who quotes one of these counts is most likely to get wrong: the committed 42
#: has not moved and this is not a margin.
BAND = (
    "ONE CONTRAST ON ONE FIRE AGAINST ONE OPPONENT, AND NOT A MARGIN. The "
    "present-perimeter arm is slice 0 of the committed canonical hazard field used "
    "as a NODE FILTER on the walk graph — a node is removed when "
    "hazard.prob_at(x, y, 0.0) >= p_cut, which is the same predicate "
    "scripts/run_real_roads_real_hazard_slope.candidate_origins already uses to "
    "refuse an origin standing in the fire — and then the repository's own "
    "naive_route over the filtered graph, SCORED against the full forecast at the "
    "same departure time and the same p_cut as the other two arms. Five facts "
    "travel together or none may be quoted: (1) NO COMMITTED NUMBER MOVES. The "
    "canonical partition is still 414 / 42 / 2 and this run REPRODUCED it before it "
    "wrote anything; these keys sit beside the 42 and do not replace it. (2) ZERO "
    "BUFFER, so no width was swept and no width could be chosen after the answer — "
    "this is NOT WFG-033(b) and does not pre-empt NH-027. (3) IT IS NOT A MARGIN "
    "and must not be spoken as one while NH-032, NH-034 and NH-052 are open; it is "
    "a partition of 44 origins into three named outcomes. (4) NOT TRANSFERABLE. The "
    "91 on 의성·안동 is a different region measured with a different arm "
    "(docs/present_perimeter_arm.md), and nothing here says anything about it. "
    "(5) ONE FIRE, ONE REGION, ONE HORIZON, and the canonical field's 32.6 % "
    "envelope-coverage caveat applies to it unchanged. ⚠ An origin counted as "
    "not_reached is the FILTER's doing and not the fire's — every one of the 44 was "
    "reached by the fire-blind router on the unfiltered graph — so that count is "
    "reported separately and is never folded into either of the other two."
)

FORBIDDEN = [
    "the forecast only saves 16 households",
    "the present perimeter is enough",
    "the forecast adds nothing",
    "42 becomes 16",
    "예보는 16곳만 살립니다",
    "현재 화선만 보면 충분합니다",
    "the margin over the present perimeter is 16",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("target_origins", "target_set.n", "origins",
     "origins whose FIRE-BLIND route reaches a refuge and enters the forecast "
     "hazard on the canonical Yeongdeok field: the committed naive_into_FA_safe "
     "bucket plus the committed no_safe_route bucket. This is the set the "
     "present-perimeter arm is run over, and it is the set the booth's headline "
     "is about"),
    ("saved_by_present_perimeter", "outcomes.saved", "origins",
     "of those origins, how many a router that avoids ONLY the present perimeter "
     "already gets to a refuge without entering the forecast — the share of the "
     "headline contrast that does NOT require knowing where the fire will be"),
    ("still_enter_forecast", "outcomes.still_enters_forecast", "origins",
     "of those origins, how many a present-perimeter-only router still walks into "
     "the forecast — the share that the forecast, and not the present perimeter, "
     "is doing the work for"),
    ("not_reached_under_filter", "outcomes.not_reached", "origins",
     "of those origins, how many reach NO refuge once the present perimeter is "
     "removed from the graph. ⚠ This is the FILTER's doing and not the fire's, "
     "because all of them were reached fire-blind on the unfiltered graph; it is "
     "reported separately and never folded into the other two counts"),
    ("filter_nodes_removed", "present_perimeter_filter.n_nodes_removed", "nodes",
     "walk-graph nodes the present-perimeter filter removes — how much of the "
     "graph the arm actually deletes, which is what decides whether a not_reached "
     "outcome means the fire or the filter"),
    ("filter_shelters_removed", "present_perimeter_filter.n_shelters_removed",
     "refuges",
     "refuges standing inside the present perimeter and therefore removed with "
     "the rest of the filtered nodes"),
]


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES:
        cur = art
        for part in path.split("."):
            cur = cur[part]
        out[PREFIX + suffix] = {
            "value": cur,
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation
            + ". Regenerate: python scripts/measure_present_perimeter_yeongdeok.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · 458곳 주사 · routing_demo_canonical.npz · p_cut 0.5",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_present_perimeter_yeongdeok.py rebuilds "
                    "the artifact from the committed canonical npz and the committed "
                    "snapshots (osm-walk, osm-shelters, srtm-dem) with no network "
                    "access, no raw bundle and no refit, and REFUSES to write unless "
                    "the committed 414 / 42 / 2 partition re-derives first in the same "
                    "process — the WFG-114 reproduction-gate pattern."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "present_perimeter_yeongdeok",
            "notes": "docs/present_perimeter_yeongdeok.md states the method, the "
                     "pre-registration, the result and what it does NOT show. It is a "
                     "routing contrast on one region and produces no margin.",
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
            print("STALE present-perimeter registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} present-perimeter entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} present-perimeter entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
