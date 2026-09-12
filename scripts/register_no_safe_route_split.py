#!/usr/bin/env python
"""Register the WFG-262 `no_safe_route` origin-split counts in docs/NUMBERS.json.

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `nsr_` keys, and writes it back.

    python scripts/register_no_safe_route_split.py          # upsert + report
    python scripts/register_no_safe_route_split.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = ("data/processed/no_safe_route_origin_split/"
            "split_20260912T0026Z.json")
PREFIX = "nsr_"

#: The caveat every one of these keys carries. It leads with the thing a reader
#: who quotes a zero here is most likely to get wrong: a clean bucket is not a
#: licensed sentence.
BAND = (
    "A ZERO THAT LICENSES NOTHING ON THE SHEET. These keys count how many "
    "origins in a committed canonical scan would be refused by "
    "routing/evacuation.py's pre-search branch — the one that returns "
    "reached=False before any search runs when the origin's own node is already "
    "at or above p_cut at departure. Four facts travel together or none may be "
    "quoted: (1) NO COMMITTED NUMBER MOVES and no scan was re-run. The committed "
    "no_safe_route counts are 2 / 12 / 10 and this measurement sits beside them; "
    "it reproduced n_nodes and n_origins_scanned for all three regions before it "
    "wrote anything. (2) THE ZERO IS STRUCTURAL, NOT LUCKY. All three copies of "
    "candidate_origins skip a node with hazard.prob_at(x, y, 0.0) >= p_cut, "
    "which is the same predicate the branch tests, so at departure_min = 0 every "
    "origin that could trigger it was removed before the scan began. (3) IT DOES "
    "NOT LICENSE THE A4 SHEET SENTENCE. The bucket's code condition is only "
    "「the naive route enters the hazard AND the future-aware search reached no "
    "refuge」; reached=False is also produced by the hazard gate blocking every "
    "alternative with the budget nowhere near binding, which is the mechanism "
    "docs/routing_limitations.md §1 established for fa_exceeds_budget and which "
    "survives this zero untouched. (4) THE MARGIN IS THIN ON THE HEADLINE "
    "REGION. 영덕's largest departure-time probability over scanned origins is "
    "0.495617 against a p_cut of 0.5, so the invariant holds by 0.0044 and not "
    "by design intent. ⚠ A scan called with departure_min > 0, or an origin rule "
    "that drops the p_cut filter, reintroduces the defect silently; "
    "tests/test_no_safe_route_origin_split.py is what ties the two predicates "
    "together."
)

FORBIDDEN = [
    "the no_safe_route bucket is correct",
    "the dispatch sheet sentence is verified",
    "no household is already in the fire",
    "예산 내 안전한 보행 경로가 없음은 검증되었습니다",
    "출동 지시서 문장은 확인되었습니다",
]

_SAMPLE = ("3개 지역 · 영덕 458곳 / 의성·안동 368곳 / 울진·삼척 393곳 주사 · "
           "slope_digraph_canonical · p_cut 0.5 · departure_min 0")

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("refused_before_search_yeongdeok",
     "regions.0.n_origins_removed_before_search", "origins",
     "how many of 영덕's 458 scanned origins routing/evacuation.py would refuse "
     "before any search runs, because the origin's own node is already at or "
     "above p_cut at departure. These are the origins whose presence in "
     "no_safe_route would make the A4 sheet's 「예산 내 … 우회 포함」 sentence "
     "false for them, and there are none"),
    ("refused_before_search_uiseong_andong",
     "regions.1.n_origins_removed_before_search", "origins",
     "the same count for 의성·안동's 368 scanned origins, whose committed "
     "no_safe_route bucket is the largest of the three at 12. Every one of those "
     "12 members was checked individually against the predicate, not inferred "
     "from the aggregate"),
    ("refused_before_search_uljin_samcheok",
     "regions.2.n_origins_removed_before_search", "origins",
     "the same count for 울진·삼척's 393 scanned origins. Its 10 committed "
     "no_safe_route members were also checked individually"),
    ("max_departure_prob_yeongdeok",
     "regions.0.max_prob_at_departure_over_scanned_origins", "probability",
     "the largest ignition probability at departure over 영덕's scanned origins, "
     "read off build_time_expanded_field's own table at column 0. This is how "
     "close the origin rule comes to admitting an origin the router would refuse "
     "before searching: 0.0044 below the 0.5 cutoff. It is the reason the "
     "invariant needs a test rather than a sentence"),
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
            + ". Regenerate: python scripts/measure_no_safe_route_origin_split.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": _SAMPLE,
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_no_safe_route_origin_split.py rebuilds "
                    "each region's node set from the committed osm-walk snapshot, "
                    "imports the committed origin rule from "
                    "run_real_roads_real_hazard_slope.candidate_origins rather than "
                    "restating it, and REFUSES to exit 0 unless n_nodes and "
                    "n_origins_scanned re-derive against the committed artifact for "
                    "all three regions first — the WFG-114 reproduction-gate "
                    "pattern. No network access, no raw bundle, no DEM and no "
                    "refit: the predicate reads node coordinates and the hazard "
                    "surface only."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "no_safe_route_origin_split",
            "notes": "docs/routing_limitations.md §6 states the method, the "
                     "pre-registration, the result and what it does NOT show. It "
                     "moves no committed count and repairs no arm.",
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
            print("STALE no_safe_route-split registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} no_safe_route-split entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} no_safe_route-split entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
