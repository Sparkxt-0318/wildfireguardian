#!/usr/bin/env python
"""Register the refuge-siting arm's own POPULATION in docs/NUMBERS.json (WFG-247).

The `l0i_` family already registers what the refuge search FOUND — 20, 24, 0 saved
and 2,218 candidate sites. It never registered what those savings are counted OVER,
and that is the whole defect WFG-247 names: the 마무리 of the five-minute demo says
「2,218곳」 and 「20가구」 in one breath, and the two are different populations —
candidate SITES on the walk graph, and OSM buildings. A student asked
「아까 단위가 지점이라고 하셨는데 왜 여기는 가구입니까」 had no number to answer with,
because the denominator lived only in each key's free-text `sample` field, where no
gate re-derives it and no sentence can cite it.

So the denominator becomes a first-class key with its own `check` block, read from
the same artifact the numerators come from. ⚠ NOT from
`data/processed/building_origin_routing.json`, whose `bld_yeongdeok_n_mapped` is also
124: that would be the WFG-244 mistake of presenting a coincidence as a derivation.
The refuge search's population is the one the refuge search wrote down.

ADDITIVE, AND IT NEVER DELETES BY PREFIX. `scripts/build_numbers.py` rebuilds the
registry from its own list and would drop keys other registrars added (WFG-040); the
other `register_*.py` scripts then clear their whole prefix before upserting. This one
must not: the rest of the `l0i_` family was written into docs/NUMBERS.json by hand in
Session 22 and has no registrar, so a prefix sweep here would delete four committed
keys the screen and the demo script both cite. It upserts exactly the keys it defines.

    python scripts/register_refuge_population.py          # upsert + report
    python scripts/register_refuge_population.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/vulnerability/refuge_placement.json"

#: The caveat both keys carry. It says the two things that make the denominator
#: worth citing at all: what the population IS, and that it is not the unit the
#: rest of the demo uses for its output object.
BAND = (
    "THE DENOMINATOR OF THE REFUGE-SITING ARM, NOT A CENSUS AND NOT THIS "
    "PROJECT'S OUTPUT UNIT. Two facts travel with it or it may not be quoted. "
    "(1) 124 is a count of OSM BUILDINGS in the 영덕 walk-graph snapshot, which is "
    "a different population from the 2,218 candidate SITES the search enumerates "
    "and a different population again from the 지점 (one node of the OSM walking "
    "graph) that docs/auto/JUDGE_QA.md Q20a defines as this project's own output "
    "unit. All three appear in the demo's closing 56 seconds and WFG-247 is the "
    "row for saying which is which where each is said. (2) ⚠ PROVISIONAL — it "
    "rests on the 124-building OSM snapshot, not on real 도로명주소 footprints "
    "(Session 21 blocked on a logged-in download, NH-005 still open). The same "
    "Overpass query returns 1,763 buildings for Mati and 988 for Paradise against "
    "74-124 for 영덕, so rural Korean OSM coverage is sparse and every household "
    "count resting on it will move."
)

FORBIDDEN = [
    "영덕에 124가구가 산다",
    "124 households live in Yeongdeok",
    "전수 조사",
    "a census of Yeongdeok households",
]

# key -> (json_path into the artifact, unit, derivation)
FIGURES = {
    "l0i_household_population": (
        "optimum_h240.baseline.n_households", "households",
        "The population every l0i_ saved-household count is measured over: the "
        "OSM buildings in the 영덕 walk-graph snapshot, of which 24 fail to reach "
        "safety inside the 240-minute horizon before any refuge is added. So "
        "「20가구」 reads 20 of 124, and 「24가구」 is all 24 of the failing set"),
    "l0i_walk_nodes_total": (
        "optimum_h240.constraints.n_walk_nodes_total", "nodes",
        "Walk-network nodes the candidate filter starts from, of which 2,218 "
        "survive it as candidate sites. Registered because the screen and the "
        "demo script both called 2,218 itself 「보행망 노드」, which named the "
        "filter's input with the filter's output"),
}


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for key, (path, unit, derivation) in FIGURES.items():
        out[key] = {
            "value": float(_dig(art, path)),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation + ". Regenerate: python scripts/refuge_placement.py --optimize --horizons --sweep --verify",
            "config_hash": doc_hash,
            "config_hash_at_production": None,
            "git_commit": head,
            "sample": "영덕 2025, OSM 건물 124동(잠정), 기존 대피소 43곳, 지평 240분",
            "caveat": BAND,
            "forbidden_phrasings": list(FORBIDDEN),
            "reproducible": True,
            "reproducibility": {"status": "reproducible",
                                "evidence": "both values are constants of the committed artifact and "
                                            "are re-read from it by scripts/verify_numbers.py",
                                "blocked_by": None},
            "provenance": "derived",
            "arm": "L0_intervention",
            "notes": "Session 22 artifact, registered 2026-09-11 by WFG-247. GEOMETRIC "
                     "RECOMMENDATION under stated assumptions, not a siting decision.",
            "check": {"kind": "json_path", "tolerance": 1e-06,
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
            print("STALE refuge-population registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} refuge-population entries match the artifact")
        return 0
    for key, entry in new.items():
        if key in cur:  # the first registration's commit is the provenance
            entry["git_commit"] = cur[key].get("git_commit", head)
        cur[key] = entry
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} refuge-population entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
