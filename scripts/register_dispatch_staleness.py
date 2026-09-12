#!/usr/bin/env python
"""Register the WFG-267 dispatch-sheet staleness counts in docs/NUMBERS.json.

ADDITIVE ON PURPOSE. `scripts/build_numbers.py` rebuilds the registry from its own
list and would drop the keys other registrars added (WFG-040); this script loads the
current file, replaces only the `dss_` keys, and writes it back.

    python scripts/register_dispatch_staleness.py          # upsert + report
    python scripts/register_dispatch_staleness.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = ("data/processed/dispatch_sheet_staleness/"
            "staleness_20260912T154037Z.json")
PREFIX = "dss_"

#: The caveat every one of these keys carries. It leads with the inference, because a
#: reader who quotes one of these is most likely to think a PDF was opened and read.
BAND = (
    "THESE COUNTS ARE AN INFERENCE THROUGH THE RENDER PATH, AND NOTHING HERE IS A "
    "STATEMENT ABOUT A REAL FIRE. Four facts travel together or none of these keys may "
    "be quoted. (1) THE DERIVATION DOES NOT READ A SINGLE PDF. A committed "
    "`dispatch_a4*.pdf` is classed by the 사유 sentence in the sibling "
    "`dispatch_a4*.html` it was rendered from by "
    "`scripts/generate_dispatch_outputs.py`, and the artifact records the method as "
    "`sibling_html_via_render_path`. So `dss_stale_committed_pdfs` means 「rendered from "
    "an HTML that carries the superseded sentence」 and NOT 「was opened and found to "
    "contain it」. ⚠ An earlier draft of this band justified that with 「this sandbox has "
    "no pypdf, no pdfminer and no pdftotext, SO the bytes were not read」. The premise is "
    "true and the 「so」 is false, and the lap's independent reviewer refused it: these "
    "sheets embed a Korean font SUBSET, and `scripts/probe_dispatch_pdf_fonts.py` reads "
    "each file's `/ToUnicode` CMaps with `zlib` alone. Run against all "
    "`dss_committed_dispatch_pdfs` PDFs it finds exactly the `dss_stale_committed_pdfs` "
    "sheets able to spell the superseded 사유 and none able to spell the current one — "
    "an independent route to the same answer, and `tests/test_dispatch_sheet_staleness.py` "
    "holds the two together. It CORROBORATES the classing rather than replacing it: a "
    "font subset is a property of the whole page, so it establishes what a sheet CAN "
    "spell, not the order of the words. (2) NOTHING WAS REGENERATED AND NO SHEET WAS "
    "REWRITTEN. Every file counted here is the committed record of a 2026-08-01 run, "
    "kept byte-unchanged under CHARTER §3 rule 2 and rule 7; this measurement reads and "
    "counts, and the repair it justifies is a NOTE beside the sheets. (3) THE SCOPE IS "
    "EVERY TRACKED FILE UNDER `outputs/`, which is the correction this measurement "
    "exists to make. WFG-267 was filed against `outputs/dispatch/20260801T163042Z/` "
    "alone and asked 「which of the three committed PDFs carries it」; the tree holds "
    "dss_committed_dispatch_pdfs PDFs across dss_run_dirs_with_a_committed_pdf run "
    "directories, and the stale ones are NOT all in that directory. (4) "
    "`dss_html_carrying_current` WAS ZERO UNTIL 2026-09-12 AND IS NOW THE COUNT OF SHEETS "
    "IN THE ONE RUN COMMITTED AFTER THE WFG-264 REPAIR: every 2026-08-01 sheet predates the "
    "repair and none of them can carry the sentence the emitter prints today; the sheets "
    "that do are the two 차량 도달 불가 homes of the real-hazard run "
    "outputs/dispatch_real_hazard/20260912T153043Z/ (NH-057), and the gate re-derives the "
    "count from the tree rather than pinning it. "
    "docs/dispatch_sheet_staleness.md states the method, the result and what it does "
    "NOT show."
)

FORBIDDEN = [
    "the committed sheets were corrected",
    "every dispatch PDF is current",
    "only one committed PDF is stale",
    "커밋된 시트를 고쳤습니다",
    "출동 지시서 PDF 는 모두 최신입니다",
    "옛 문장이 있는 PDF 는 한 장뿐입니다",
]

_SAMPLE = ("영덕 2025 · the committed outputs/ tree at the head that registered these "
           "keys · 439-series responder sheets generated 2026-08-01 · counted from "
           "`git ls-files -z outputs`, no run re-executed")

# key suffix -> (json_path into the artifact, unit, derivation)
FIGURES = [
    ("committed_dispatch_pdfs", "counts.tracked_pdf", "files",
     "every tracked `.pdf` under `outputs/`, which is what a judge could be handed "
     "without anything being regenerated. It is the denominator WFG-267's own framing "
     "did not have: the row says 「the three committed PDFs」, scoping to one run "
     "directory"),
    ("run_dirs_with_a_committed_pdf", "counts.run_dirs_with_a_committed_pdf",
     "directories",
     "how many run directories under `outputs/` ship at least one committed PDF. The "
     "reason the count above is not the row's three: the sheets are spread over "
     "`outputs/dispatch/`, `outputs/dispatch_full/` and `outputs/live/`"),
    ("stale_committed_pdfs", "counts.stale_pdf", "files",
     "how many of those PDFs were rendered from an HTML carrying "
     "`SUPERSEDED_UNREACHABLE_REASON_KO`. ⚠ This is the render-path inference of "
     "caveat (1), corroborated independently by scripts/probe_dispatch_pdf_fonts.py "
     "reading the PDFs' own embedded font subsets, and still not a reading of the "
     "words on the page. The paths are enumerated in the "
     "artifact's `stale_pdfs` and in `outputs/dispatch/README.md`, and "
     "`tests/test_dispatch_sheet_staleness.py` re-derives the set from the tree and "
     "refuses to let the note and the tree disagree"),
    ("html_carrying_superseded", "counts.html_carrying_superseded", "files",
     "how many tracked `.html` sheets under `outputs/` print the superseded 사유. This "
     "is the number `docs/live_pipeline.md` already carries as 「44 files」, re-derived "
     "here from the tree rather than copied from that page"),
    ("html_carrying_current", "counts.html_carrying_current", "files",
     "how many print the sentence the emitter prints TODAY. It is ZERO, and an empty "
     "sub-case is published as an empty sub-case: every committed sheet predates the "
     "WFG-264 repair. ⚠ NOT a control, though an earlier draft called it one: it comes "
     "from the SAME scan, with the same code, as the count above, so no outside truth "
     "enters. It rules out the tree holding two live sentences and rules out nothing "
     "about the scan itself"),
    ("tracked_dispatch_html", "counts.tracked_html", "files",
     "every tracked `.html` under `outputs/`, the population the two counts above are "
     "taken from"),
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
            + ". Regenerate: python scripts/measure_dispatch_sheet_staleness.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": _SAMPLE,
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/measure_dispatch_sheet_staleness.py reads "
                    "`git ls-files -z outputs`, the two 사유 constants parsed out of "
                    "scripts/generate_dispatch_outputs.py with `ast`, and the tracked "
                    "sheets themselves — no network, no raw bundle, no clock in the "
                    "measurement, nothing outside the repository. It REFUSES to write "
                    "an artifact if either constant stops being a module-level string "
                    "literal, rather than reporting zero hits."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "dispatch_sheet_staleness",
            "notes": "docs/dispatch_sheet_staleness.md states the method, the result, "
                     "the caveats and what it does NOT show. It moves no committed "
                     "count, rewrites no committed sheet and re-runs nothing; the "
                     "repair it justifies is a note beside the sheets and a gate that "
                     "keeps the note and the tree from drifting apart.",
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
            print("STALE dispatch-staleness registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} dispatch-staleness entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} dispatch-staleness entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
