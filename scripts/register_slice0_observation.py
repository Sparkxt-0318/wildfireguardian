#!/usr/bin/env python
"""Register the slice-0-is-the-observation figures in docs/NUMBERS.json (WFG-260).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads the
current file, replaces only the `ppy_yeongdeok_slice0_` key, and writes it back.

    python scripts/register_slice0_observation.py          # upsert + report
    python scripts/register_slice0_observation.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_yeongdeok_slice0_2025.json"
PREFIX = "ppy_yeongdeok_slice0_"

#: The caveat the key carries. It leads with what a reader is most likely to get
#: wrong: this is a property of the INPUT FIELD, not an outcome of the run, and it
#: cuts AGAINST the project's own choice of word.
BAND = (
    "PROPERTIES OF THE INPUT FIELD, NOT OUTCOMES OF A RUN, AND NOT A RESULT. "
    "It is not a routing count and does not belong beside the 42 or beside "
    "any ppy_yeongdeok_ outcome. Four facts travel with it or it may not be "
    "quoted: (1) WHAT IT IS FOR. It qualifies ONE sentence — "
    "that the present-perimeter opponent's PLANNING side is fed the observed FIRMS "
    "footprint and no model output, which is what paper/manuscript.md's 「needs no "
    "model at all」 rests on; the identity BEHIND that sentence is registered "
    "elsewhere, as dn_yeongdeok_t0min_n_cells, and is not re-registered here. "
    "(2) THE PLANNING SIDE ONLY. The arm is still SCORED "
    "against the full forecast; docs/present_perimeter_yeongdeok.md §5 item 6 names "
    "that oracle and this measurement leaves its conclusion standing word for word. "
    "(3) THE COMPONENT COUNT CUTS AGAINST US. 249 cells in 226 8-connected "
    "components, the largest 3 cells, on a 500 m grid rasterised from VIIRS "
    "detections whose own footprint is 375 m, is a DETECTION SCATTER not a mapped "
    "perimeter, so 「present perimeter」 is a generous word for the object the arm "
    "refuses; it is registered because the qualification belongs beside the claim, "
    "and it is convention-dependent — the same set is 236 components at "
    "4-connectivity, which the artifact also records. (4) NOT TRANSFERABLE. Nothing "
    "here is measured about 의성·안동 (docs/present_perimeter_arm.md), whose arm has "
    "a different input, and nothing here says the observation is CORRECT — the "
    "canonical field's envelope-coverage caveat applies unchanged, and obs_stack "
    "is CUMULATIVE so the t = 0 seed sits inside the footprint later scored "
    "(docs/disc_null.md §3c). ⚠ Not an outcome count, but still a ppy_yeongdeok_ "
    "figure about the 영덕 run, and no lap puts one on a judge-facing surface "
    "while NH-059 is open."
)

FORBIDDEN = [
    "the present perimeter is a mapped perimeter",
    "the fair opponent is fed the forecast",
    "slice 0 is a model output",
    "the opponent plans on the model",
    "현재 화선은 실측 경계선입니다",
    "공정한 상대도 모델을 씁니다",
]

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    # ⚠ `observed_cells` (249) is DELIBERATELY NOT REGISTERED HERE, and this comment is
    # the record of why (WFG-260's independent reviewer, 2026-09-11). The identity it
    # would have registered -- obs_stack[0] > 0 and haz_stack[0] >= p_cut are the same 249
    # cells -- was established and registered one lap earlier by
    # scripts/measure_disc_null.py, as `dn_yeongdeok_t0min_n_cells` and
    # `dn_yeongdeok_seed_cells_in_model`, and docs/disc_null.md §2 states it in prose
    # including the abort-if-untrue behaviour. A third home for the same fact is what
    # `ssotize` exists to prevent, and CHARTER §3.3 wants one artifact per number, not a
    # second one that agrees. The artifact this script writes still RECORDS the 249, and
    # tests/test_slice0_is_observation.py still checks it cell for cell against the array;
    # prose cites the dn_ keys for it. Only the component count is new, and only it is
    # registered.
    ("components_8conn", "measurements.slice0_components_8conn", "components",
     "how many 8-connected components that burning set falls into, largest 3 cells. "
     "⚠ This qualifies the claim rather than supporting it: the object the arm "
     "treats as a 「present perimeter」 is a detection scatter on the 500 m hazard "
     "grid, not a mapped fire line. Convention-dependent; the artifact records 236 at "
     "4-connectivity beside it"),
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
            + ". Regenerate: python scripts/measure_slice0_is_observation.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · routing_demo_canonical.npz slice 0 · p_cut 0.5",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_slice0_is_observation.py reads only the "
                    "committed canonical npz — no network, no raw bundle, no refit, "
                    "no route re-run — and REFUSES to write unless slice 0 is at "
                    "t = 0, is strictly binary, and equals obs_stack[0] cell for "
                    "cell in the same process."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "present_perimeter_yeongdeok",
            "notes": "docs/present_perimeter_yeongdeok.md §2 and §5 item 6 state what "
                     "this licenses and what it does not. It is a property of the "
                     "input field and produces no margin and no routing outcome.",
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
            print("STALE slice-0 registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} slice-0 entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} slice-0 entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
