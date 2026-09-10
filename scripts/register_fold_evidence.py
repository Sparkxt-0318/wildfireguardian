#!/usr/bin/env python
"""Register the two counts that describe the weak LOFO fold (WFG-233).

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads
the current file, replaces only the `foldev_` keys, and writes it back.

    python scripts/register_fold_evidence.py          # upsert + report
    python scripts/register_fold_evidence.py --check  # exit 1 if stale

Why these two keys exist at all. `docs/MODEL_CARD.md`'s 작품설명서 section ends with
the one sentence in this repository written to be pasted into a document the judges
receive, and it explained the 0.68 `gangneung_2023` fold with a detection count while
the same file's headline blockquote, its per-fire table and `docs/fold_sizes.md`
explained the same fold with a positive-cell count. Both numbers are true and they
count different things. Neither was registered, so `make verify` re-derived neither
and nothing stopped a later lap from swapping one for the other. These keys make the
distinction mechanical: each carries the other's value and scope in its caveat, and
`tests/test_fold_evidence_registry.py` fails if they ever become equal or if the
pasted sentence stops carrying both.

⚠ Neither count has a second, independent derivation in this repository, and the caveat
says so. The `cross_check` on the detection key is a TRANSCRIPTION check: the artifact
it compares against is written by copying the record this key reads.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
FOLD_SIZES = "docs/fold_sizes.json"
FIRMS_FIRST = "data/processed/detection/firms_first_detection.json"
GK2A_FLOOR = "data/processed/detection/gk2a_detection_floor.json"
PREFIX = "foldev_"
FIRE = "gangneung_2023"

#: The caveat both keys carry. The whole point of the pair is that neither may be
#: read as the other, so each states what the other one is.
BAND = (
    "TWO COUNTS OF DIFFERENT THINGS, ON THE SAME FIRE. The 0.68 LOFO fold "
    "`gangneung_2023` is described in this repository by two quantities that are "
    "both true and are NOT interchangeable. (1) The FOLD'S POSITIVE CELLS = 8: the "
    "number of 500 m grid cells labelled positive inside the fold, out of 396 rows "
    "(docs/fold_sizes.json, produced by scripts/fold_sizes.py from the committed "
    "LOFO dataset). This is the quantity that makes the 0.682 fold AUC unstable, "
    "because it is the evidence the AUC is computed over, and it is therefore the "
    "operative number whenever the weakness of the fold is being explained. (2) The "
    "WHOLE-FIRE FIRMS DETECTIONS = 17: the number of FIRMS active-fire detections "
    "associated with the entire gangneung_2023 event over its whole burn, not "
    "restricted to the fold's grid, its cells or its overpass window "
    "(data/processed/detection/firms_first_detection.json). It describes how little "
    "the satellite saw of the fire; it does NOT describe how much evidence the fold "
    "contains. "
    "⚠ THE CROSS-CHECK ON THIS KEY IS A TRANSCRIPTION CHECK AND NOT CORROBORATION. "
    "data/processed/detection/gk2a_detection_floor.json carries the same 17, but it "
    "does not derive it: scripts/gk2a_detection.py reads "
    "firms_first_detection.json and assigns the record verbatim "
    "(`rec[\"firms\"] = firms.get(label)`), so the two files are byte-identical for "
    "this fire, down to report_utc and delay_h. gk2a_detection.py counts GK2A "
    "infrared anomalies and performs no FIRMS counting of any kind. The cross_check "
    "therefore catches a hand-edit of one file and nothing else; it CANNOT catch a "
    "rebuild against a different event definition, because the copy would follow. "
    "If the source file is absent the copy becomes null rather than disagreeing. "
    "No second, independent derivation of this count exists in the repository. "
    "Quoting 17 where 8 belongs overstates the fold's evidence by a factor of two "
    "and answers a different question than the one asked. Write both, with their "
    "units, or write the positive-cell count alone; README.md:489 is the model "
    "wording. "
    "⚠ A THIRD 17 EXISTS AND MUST NOT BE CITED: the legacy Build A spread_v2 audit "
    "file gives detections_csv = 17 and detections_in_grid = 17 for this fire over "
    "2023-04-11 to 04-13. That directory carries LEGACY_DO_NOT_CITE.md, and its 17 is "
    "scoped to a bbox and a date window, so it agrees with the whole-fire count by "
    "coincidence and not by derivation. Its path is deliberately not written here, "
    "because writing it would register this file as a citation of it; a lap that "
    "sources this number by grepping for 17 lands there first."
)

FORBIDDEN = [
    "the fold has 17 positives",
    "17 positive cells",
    "탐지 17건의 양성",
    "양성 17건",
    "the fold was trained on 17 detections",
    "8 FIRMS detections",
    "the fire had only 8 detections",
]

# key suffix -> (source artifact, json_path, value, unit, derivation, sample)
FIGURES = [
    (
        "gangneung2023_fold_positive_cells",
        FOLD_SIZES,
        None,  # resolved by fire_id, not by a hard-coded list index
        "cells",
        "Positive 500 m cells in the gangneung_2023 LOFO fold, out of 396 rows. "
        "This is the fold's evidence and the reason its 0.682 AUC is unstable. "
        "Regenerate: python scripts/fold_sizes.py --write",
        "gangneung_2023 LOFO fold · 396행 · 2 overpasses · 1 transition",
    ),
    (
        "gangneung2023_firms_whole_fire_detections",
        FIRMS_FIRST,
        f"{FIRE}.n",
        "detections",
        "FIRMS active-fire detections for the WHOLE gangneung_2023 event, not "
        "restricted to the LOFO fold's grid or overpass window. "
        "Regenerate: python scripts/gk2a_detection.py",
        "gangneung_2023 전체 화재 · FIRMS active-fire detections",
    ),
]


def _dig(doc, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _fold_index(fold_sizes: dict) -> int:
    """Locate the fire by name, so a reordered artifact cannot silently retarget."""
    for i, row in enumerate(fold_sizes["folds"]):
        if row["fire_id"] == FIRE:
            return i
    raise SystemExit(f"{FOLD_SIZES}: no fold named {FIRE!r}")


def build_entries(head: str, doc_hash: str) -> dict:
    fold_sizes = json.loads((REPO / FOLD_SIZES).read_text(encoding="utf-8"))
    idx = _fold_index(fold_sizes)
    out = {}
    for suffix, artifact, path, unit, derivation, sample in FIGURES:
        if path is None:
            path = f"folds.{idx}.positive_cells"
        art = json.loads((REPO / artifact).read_text(encoding="utf-8"))
        entry = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": artifact,
            "json_path": path,
            "derivation": derivation,
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": sample,
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "Both values are counts read out of committed JSON artifacts. "
                    "No model is fitted, no DEM is read and no network access is "
                    "needed to re-derive either one."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "fold_evidence",
            "notes": "docs/MODEL_CARD.md's 작품설명서 correction mapping states both "
                     "counts with their scopes; README.md:489 is the model wording. "
                     "The two are not interchangeable — see the caveat.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": artifact, "json_path": path}}},
        }
        if suffix.endswith("firms_whole_fire_detections"):
            # A TRANSCRIPTION check, not corroboration. gk2a_detection.py copies this
            # record verbatim out of firms_first_detection.json, so the two agree by
            # construction; the check catches a hand-edit of one file and nothing
            # more. Kept for that narrow value, described honestly in BAND.
            entry["cross_check"] = {
                "file": GK2A_FLOOR,
                "json_path": f"per_fire.{FIRE}.firms.n",
                "must_equal": f"{PREFIX}{suffix}.value",
            }
        out[PREFIX + suffix] = entry
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE fold-evidence registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} fold-evidence entries match the artifacts")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} fold-evidence entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
