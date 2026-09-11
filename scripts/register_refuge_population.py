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

#: The caveat the two POPULATION keys carry. It says the two things that make the
#: denominator worth citing at all: what the population IS, and that it is not the
#: unit the rest of the demo uses for its output object.
BAND = (
    "THE DENOMINATOR OF THE REFUGE-SITING ARM, NOT A CENSUS AND NOT THIS "
    "PROJECT'S OUTPUT UNIT. Two facts travel with it or it may not be quoted. "
    "(1) 124 is a count of OSM BUILDINGS in the 영덕 walk-graph snapshot, which is "
    "a different population from the 2,218 candidate SITES the search enumerates "
    "and a different population again from the 지점 (one node of the OSM walking "
    "graph) that docs/auto/JUDGE_QA.md Q20a defines as this project's own output "
    "unit. All three appear in the demo's closing segment — the 마무리, whose "
    "length is re-allocated by scripts/measure_demo_script_pace.py whenever the "
    "spoken text moves, so this caveat names the segment and not a number of "
    "seconds that its own registration lap would falsify (the sentence that "
    "carries this population took it from 56 s to 61 s). WFG-247 is the row for "
    "saying which population is which where each is said. (2) ⚠ PROVISIONAL — it "
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

#: The caveat the DENOMINATOR carries, and it is a different warning from BAND.
#: ⚠ WFG-250: the lap that registered `l0i_household_population` then wrote 124 into
#: the spoken 마무리 as though it were the denominator of 20 and 24. It is not. 124 is
#: what the ARM is measured over; the CLAIM's denominator is the 24 that fail the
#: horizon before any refuge is added, which is what `scripts/finals.template.html`
#: and `docs/finals_screen_v2.md` §2.4 had said correctly the whole time. Quoting the
#: wrong one of these two understates this project's own result by a factor of five,
#: which is why nothing caught it: the error cut AGAINST the work.
DENOMINATOR_BAND = (
    "THE DENOMINATOR OF THE REFUGE-SITING CLAIM, AND NOT THE POPULATION OF THE "
    "ARM. Three facts travel with it or it may not be quoted. (1) 24 is the count "
    "of OSM buildings in the 영덕 walk-graph snapshot that FAIL to reach safety "
    "inside the 240-minute horizon BEFORE any refuge is added, out of the 124 "
    "registered as l0i_household_population. 「20가구」 is therefore 20 of 24 and "
    "not 20 of 124, and 「24가구」 is the whole failing set rather than a fifth of "
    "the village. (2) ⚠ It is NOT interchangeable with l0i_best_pair_saved, which "
    "is also 24: the two agree because the best pair happens to recover every "
    "failing building, and a lap that treats one as the other is presenting a "
    "coincidence as a derivation (WFG-244's defect). If a refit ever moved either, "
    "they would part. (3) ⚠ PROVISIONAL for the same reason the population is: it "
    "rests on the 124-building OSM snapshot, not on 도로명주소 footprints (NH-005 "
    "open), and every count resting on that snapshot will move."
)

DENOMINATOR_FORBIDDEN = [
    "124동 중 20가구",
    "20 of the 124 households",
    "OSM 건물 124동 중 20가구가 도달",
]

# key -> (json_path into the artifact, unit, derivation, caveat, forbidden phrasings,
#         the backlog row that added the key)
FIGURES = {
    "l0i_household_population": (
        "optimum_h240.baseline.n_households", "households",
        "The population every l0i_ saved-household count is measured over: the "
        "OSM buildings in the 영덕 walk-graph snapshot, of which 24 fail to reach "
        "safety inside the 240-minute horizon before any refuge is added. So "
        "「20가구」 reads 20 of 124, and 「24가구」 is all 24 of the failing set",
        BAND, FORBIDDEN, "WFG-247"),
    "l0i_walk_nodes_total": (
        "optimum_h240.constraints.n_walk_nodes_total", "nodes",
        "Walk-network nodes the candidate filter starts from, of which 2,218 "
        "survive it as candidate sites. Registered because the screen and the "
        "demo script both called 2,218 itself 「보행망 노드」, which named the "
        "filter's input with the filter's output",
        BAND, FORBIDDEN, "WFG-247"),
    "l0i_failing_denominator_h240": (
        "optimum_h240.baseline.n_failing", "households",
        "The denominator of 20 and 24: buildings that do NOT reach safety inside "
        "the 240-minute horizon before a refuge is added, read from the same "
        "baseline block as the population. Registered because the demo's spoken "
        "closing named the arm's population (124) where the claim's denominator "
        "is this (24), which understates the result five-fold (WFG-250)",
        DENOMINATOR_BAND, DENOMINATOR_FORBIDDEN, "WFG-250"),
}


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for key, (path, unit, derivation, caveat, forbidden, row) in FIGURES.items():
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
            "caveat": caveat,
            "forbidden_phrasings": list(forbidden),
            "reproducible": True,
            "reproducibility": {"status": "reproducible",
                                "evidence": "both values are constants of the committed artifact and "
                                            "are re-read from it by scripts/verify_numbers.py",
                                "blocked_by": None},
            "provenance": "derived",
            "arm": "L0_intervention",
            # ⚠ PER KEY, and the first draft of this registrar got that wrong in a way
            # its own independent reviewer had to point out. The draft froze WFG-247 into
            # all three keys' notes and defended it as forced -- "any field that varies
            # with the row would change the stored hash of a key already committed". The
            # same function disproves it: `caveat` and `forbidden_phrasings` vary per key
            # here and the two pre-existing entries' bytes did not move, because their
            # values did not change. What §3d's freeze forbids is CHANGING a committed
            # entry, not varying a field across keys. A knowingly-wrong provenance line
            # frozen into the registry is worse than the edit it was avoiding.
            "notes": f"Session 22 artifact, registered 2026-09-11 by {row}. GEOMETRIC "
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
