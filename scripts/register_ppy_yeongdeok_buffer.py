#!/usr/bin/env python
"""Register the 영덕 dilation figures in docs/NUMBERS.json (WFG-259, route (i)).

ADDITIVE ON PURPOSE, TWICE OVER. `scripts/build_numbers.py` rebuilds the registry
from its own list and would drop the keys other registrars added (WFG-040), so
this script loads the current file and touches only its own prefix. And its prefix
is NEW: it does not rewrite one `ppy_yeongdeok_` key, because those describe the
committed ZERO-buffer artifact, which this lap did not modify (CHARTER §3 rule 2)
and whose 26 / 16 / 2 this run re-derived unchanged as its identity control.

    python scripts/register_ppy_yeongdeok_buffer.py          # upsert + report
    python scripts/register_ppy_yeongdeok_buffer.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json"
PREFIX = "ppy_yeongdeok_buf_"

#: The caveat every one of these keys carries. It is long because this result is
#: the exact case CHARTER §3.5 is about: it CONFIRMS, to the origin id, a sentence
#: that threatened the project's headline, and it DESTROYS the inference that was
#: being drawn from that sentence. Either half quoted alone is a false statement
#: about the experiment.
BAND = (
    "DILATED PRESENT-PERIMETER ARM, ONE FIRE, ONE REGION, ONE HORIZON, THREE "
    "PRE-REGISTERED WIDTHS. Five facts travel together or none of them may be "
    "quoted. (1) WHAT IT SETTLES. docs/present_perimeter_yeongdeok.md §5 item 5 "
    "asserted from an ended reviewer session that dilating the burning set moves "
    "origin 11935180417 into `saved` at 100 m and that 「at 500 m, 15 of the 16 "
    "flip」. Both REPRODUCE here exactly, origin id included, so the sentence is "
    "TRUE and is now re-derivable. (2) THE INFERENCE FROM IT IS FALSE, AND THAT "
    "IS THE POINT. 「15 of the 16 flip」 was read as 「a router that sees the "
    "present fire plus 500 m reaches all but one of the origins the headline 42 "
    "credits to the forecast」. It does not: at 500 m the arm SAVES 18 of the 44, "
    "DOWN from the zero-buffer 26, because the dilated set swallows 23 of the 44 "
    "origins themselves and the arm then plans for only 21 of them at all. At "
    "100 m it saves 12. On these three widths the best-scoring opponent is the "
    "ZERO-buffer one already committed. (3) THE MECHANISM, READ OFF THE "
    "CROSS-TABULATION AND NOT INFERRED FROM MARGINALS. Of the 26 the zero-buffer "
    "arm saved, the 500 m dilation refuses 20 outright, cuts 3 more off from every "
    "refuge, and still saves 3; the 15 that flip come out of the more distant "
    "still-entering group, and 3 + 15 = 18. ⚠ The 23 refused in total is NOT that "
    "20: it also takes 2 from `not_reached` and 1 from `still_enters_forecast`. "
    "The first draft of this band and of the page said 「all 23 come out of the 26」 "
    "because two marginals both read 23, and WFG-259's independent reviewer blocked "
    "the lap for it; `transition_matrix_from_zero` exists so that no later sentence "
    "has to infer a joint count from two margins. The flip count and the loss count "
    "are two halves of one geometric fact and quoting the first alone inverts the "
    "conclusion. ⚠ The artifact holds NO distance field, so 「the saved origins are "
    "the ones nearest the fire」 is a plausible reading of these cells and is NOT "
    "measured by this run; it is not written on the page. "
    "(4) IT IS NOT AN OPPONENT OF RECORD AND NOT A MARGIN. A buffered arm scored "
    "as THE opponent is WFG-033(b) and NH-027, the author's; NH-032, NH-034 and "
    "NH-052 are open and no margin from this may reach a judge-facing surface. "
    "Three widths, two of them taken verbatim from prose written before the run, "
    "is not a sweep, and a lap that adds a width to find a better one has crossed "
    "into WFG-033(b). (5) IT DOES NOT MEASURE INPUT COARSENESS. Dilation grows "
    "one observation's burning set; coarseness is a 226-component detection "
    "scatter standing in for a fire line (WFG-260). Insofar as this constrains "
    "that direction at all it runs AGAINST the convenient reading, because "
    "growing the refused set LOWERS the net saved count at both widths. "
    "⚠ The arm is still scored against the model's own forecast field, so "
    "§5 item 6's oracle-on-the-scoring-side caveat applies to every number here "
    "unchanged. ⚠ Still a ppy_yeongdeok_ figure about the 영덕 run: no lap puts "
    "one on a judge-facing surface while NH-059 is open."
)

FORBIDDEN = [
    "a buffered present perimeter recovers all but one",
    "500 m recovers 41 of the 42",
    "the buffered opponent is stronger",
    "a wider buffer is always a better opponent",
    "the forecast adds nothing at 500 m",
    "여유폭을 주면 예보가 필요 없습니다",
    "500 m면 42 중 41을 건집니다",
    "완충거리를 넓히면 상대가 항상 강해집니다",
]

#: (key suffix, field in the row, unit, derivation). Keyed by WIDTH rather than by
#: list index, so a reordered artifact cannot silently re-point a key.
WIDTH_FIELDS = [
    ("nodes_refused", "n_nodes_removed", "nodes",
     "walk-graph nodes refused by the dilated present perimeter (the zero-buffer "
     "run refuses 162)"),
    ("saved", "saved", "origins",
     "of the same 44 origins, how many the dilated arm gets to a refuge clear of "
     "the forecast. ⚠ Compare with the committed zero-buffer 26 before quoting it: "
     "this number is LOWER at both widths"),
    ("origins_refused", "origin_removed_by_filter", "origins",
     "of the same 44, how many the dilation refuses OUTRIGHT because the origin's "
     "own node is inside the dilated set — the arm does not plan for them at all, "
     "and they are not 「saved」 and not 「still entering」"),
    ("still_entering", "still_enters_forecast", "origins",
     "of the same 44, how many the dilated arm still walks into the forecast"),
    ("not_reached", "not_reached", "origins",
     "of the same 44, how many are left with a plannable origin and NO route to any "
     "refuge. ⚠ A different harm from `origins_refused`: the arm plans for them and "
     "finds nothing, which is the graph being cut, not the origin being inside the "
     "buffer"),
]

#: The cross-tabulation cells §7.2's mechanism sentence rests on. Registered because
#: the first draft of that sentence inferred them from two equal marginals and was
#: WRONG (WFG-259's independent reviewer): `origin_removed_by_filter` at 500 m and
#: `n_saved_at_zero_that_stopped_being_saved` are both 23 and overlap in 20. A
#: sentence about WHERE origins came from now quotes a registered cell or it is not
#: written.
MATRIX_FIELDS = [
    ("w500m_refused_from_saved", "transition_matrix_from_zero.cells.w500m.saved."
     "origin_removed_by_filter", "origins",
     "of the 26 the ZERO-buffer arm saved, how many the 500 m dilation refuses "
     "outright. ⚠ This is NOT the same as the 23 refused in total, which also "
     "takes 2 from `not_reached` and 1 from `still_enters_forecast`"),
    ("w500m_cut_off_from_saved", "transition_matrix_from_zero.cells.w500m.saved."
     "not_reached", "origins",
     "of the 26 the ZERO-buffer arm saved, how many the 500 m dilation leaves with "
     "a plannable origin and no route to any refuge"),
    ("w500m_still_saved_from_saved", "transition_matrix_from_zero.cells.w500m.saved."
     "saved", "origins",
     "of the 26 the ZERO-buffer arm saved, how many the 500 m dilation still saves"),
]

#: The transition figure, one per non-zero width: out of the 16 that still entered
#: the forecast at zero buffer, how many this width moves into `saved`.
TRANSITION_FIELD = (
    "flipped_to_saved", "n_of_those_now_saved", "origins",
    "of the 16 origins that still entered the forecast under the ZERO-buffer arm, "
    "how many this width moves into `saved`. ⚠ This is the figure "
    "docs/present_perimeter_yeongdeok.md §5 item 5 asserted and it REPRODUCES; it "
    "is not a count of what the arm saves overall, which is `saved` above and is "
    "lower than the zero-buffer 26")

WIDTHS = (100.0, 500.0)


def _dig(doc, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def figures(art: dict) -> list[tuple[str, str, str, str]]:
    out, seen = [], set()
    for i, row in enumerate(art["buffer_sensitivity"]):
        w = float(row["buffer_m"])
        if w not in WIDTHS:
            continue
        seen.add(w)
        tag = "w%dm" % int(w)
        for suffix, field, unit, derivation in WIDTH_FIELDS:
            out.append(("%s_%s" % (tag, suffix), "buffer_sensitivity.%d.%s" % (i, field),
                        unit, "%s (dilation %.0f m)" % (derivation, w)))
    for i, row in enumerate(art["transitions_out_of_still_entering"]):
        w = float(row["buffer_m"])
        if w not in WIDTHS:
            continue
        suffix, field, unit, derivation = TRANSITION_FIELD
        out.append(("w%dm_%s" % (int(w), suffix),
                    "transitions_out_of_still_entering.%d.%s" % (i, field),
                    unit, "%s (dilation %.0f m)" % (derivation, w)))
    out.extend(MATRIX_FIELDS)
    missing = set(WIDTHS) - seen
    if missing:
        raise SystemExit(
            "artifact is missing the widths this registrar owns: %s. Regenerate "
            "with python scripts/measure_present_perimeter_yeongdeok_buffer.py"
            % sorted(missing))
    return out


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in figures(art):
        out[PREFIX + suffix] = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            "derivation": derivation + ". Regenerate: python scripts/"
                          "measure_present_perimeter_yeongdeok_buffer.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": "영덕 2025 · canonical 458-origin scan · the same 44 target "
                      "origins · p_cut 0.5 · node-space dilation",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_present_perimeter_yeongdeok_buffer.py "
                    "reads only committed snapshots and the committed canonical npz "
                    "— no network, no raw bundle, no refit — and REFUSES to write "
                    "unless three gates pass in the same process: the committed "
                    "414 / 42 / 2 partition re-derives, the d = 0 identity control "
                    "reproduces the committed 26 / 16 / 2 exactly, and the 100 m "
                    "node set is a strict superset of the committed 162."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "present_perimeter_yeongdeok_dilated",
            "notes": "docs/present_perimeter_yeongdeok.md §7 states what this "
                     "licenses and what it does not, and §5 item 5 points at it. "
                     "The widths were pre-registered in claim commit 031214b "
                     "before the run.",
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
            print("STALE 영덕 dilation registry entries: " + ", ".join(stale))
            return 1
        print("OK — %d 영덕 dilation entries match the artifact" % len(new))
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print("upserted %d 영덕 dilation entries (%d new or changed); registry now %d"
          % (len(new), len(stale), len(cur)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
