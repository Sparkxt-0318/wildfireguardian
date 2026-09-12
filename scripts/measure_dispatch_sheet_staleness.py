#!/usr/bin/env python
"""Measure which COMMITTED dispatch sheets carry the superseded 「차량 도달 불가」 사유.

WFG-267 (i). `WFG-264` repaired the sentence in the emitter
(`scripts/generate_dispatch_outputs.py`), and `docs/live_pipeline.md` §「Responder-side」
records the supersession. Neither says **which printed page** a student is holding when a
judge points at two different sentences in one stack, and that is the only form of the
question that can be answered at a booth.

What it measures, and the one inference it makes
------------------------------------------------
A committed `dispatch_a4*.pdf` is rendered from its sibling `dispatch_a4*.html` by
`scripts/generate_dispatch_outputs.py` (the `printable.html_to_pdf(hp, ...)` call at the
A4 step, and the split re-emit below it). This script does NOT open the PDFs: staleness is
decided on the **sibling HTML**, and the artifact records that under
`method: "sibling_html_via_render_path"` so no reader mistakes it for a reading of the
words on the page.

⚠ An earlier version of this docstring justified the choice with 「there is no pypdf, no
pdfminer and no pdftotext here, **so** the bytes are not read」. The premise is true; the
「so」 is not, and the lap's independent reviewer refused it. These sheets embed a Korean
font SUBSET, and `scripts/probe_dispatch_pdf_fonts.py` reads each PDF's `/ToUnicode` CMaps
with `zlib` alone — an independent route that finds the same set. It corroborates this
one rather than replacing it, because a subset says what a page CAN spell and not in what
order. `docs/dispatch_sheet_staleness.md` §4 states both and what is still owed.

Scope is EVERY tracked file under `outputs/`, not one run directory. That is the
correction this measurement exists to make: WFG-267 was filed against
`outputs/dispatch/20260801T163042Z/` alone and asks 「which of the three committed PDFs」,
which pre-commits the answer to a three-item universe. `git ls-files 'outputs/**/*.pdf'`
returns considerably more, in several run directories, and more than one of them is stale.

Clock-free, network-free, and it reads nothing outside the repository: `git ls-files`
for the file set, the two constants out of the emitter, and the tracked sheets themselves.

    python scripts/measure_dispatch_sheet_staleness.py            # write a new artifact
    python scripts/measure_dispatch_sheet_staleness.py --stdout   # print, write nothing
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMITTER = REPO / "scripts" / "generate_dispatch_outputs.py"
OUT_DIR = REPO / "data" / "processed" / "dispatch_sheet_staleness"

#: The sheet families this measurement knows how to pair. A PDF is paired with the HTML of
#: the same stem; the split sheets (`dispatch_a4_dispatch`, `dispatch_a4_unreachable`) fall
#: out of the same rule and need no special case.
PDF_SUFFIX = ".pdf"
HTML_SUFFIX = ".html"


def reason_constants() -> tuple[str, str]:
    """`(current, superseded)` read out of the emitter's own source.

    Read with `ast` rather than imported: the constants are the subject of this
    measurement, and parsing the assignment binds to the literal the file actually
    carries without executing the emitter's imports. A renamed or deleted constant
    raises here rather than silently measuring nothing.
    """
    tree = ast.parse(EMITTER.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        targets = (
            [node.target] if isinstance(node, ast.AnnAssign) else
            list(node.targets) if isinstance(node, ast.Assign) else []
        )
        for t in targets:
            if isinstance(t, ast.Name) and t.id in (
                    "UNREACHABLE_REASON_KO", "SUPERSEDED_UNREACHABLE_REASON_KO"):
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found[t.id] = value.value
    missing = {"UNREACHABLE_REASON_KO", "SUPERSEDED_UNREACHABLE_REASON_KO"} - set(found)
    if missing:
        raise SystemExit(
            f"{EMITTER.relative_to(REPO)} no longer defines {sorted(missing)} as a "
            "module-level string literal. This measurement is ABOUT those two "
            "constants, so it refuses to write an artifact rather than report zero.")
    return found["UNREACHABLE_REASON_KO"], found["SUPERSEDED_UNREACHABLE_REASON_KO"]


def tracked_outputs() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "outputs"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    return sorted(f for f in out.split("\0") if f)


def measure() -> dict:
    current, superseded = reason_constants()
    files = tracked_outputs()
    htmls = [f for f in files if f.endswith(HTML_SUFFIX)]
    pdfs = [f for f in files if f.endswith(PDF_SUFFIX)]
    html_set = set(htmls)

    def carries(rel: str, needle: str) -> bool:
        return needle in (REPO / rel).read_text(encoding="utf-8")

    superseded_html = [h for h in htmls if carries(h, superseded)]
    current_html = [h for h in htmls if carries(h, current)]

    stale_pdfs, fresh_pdfs, unpaired_pdfs = [], [], []
    for p in pdfs:
        sibling = p[: -len(PDF_SUFFIX)] + HTML_SUFFIX
        if sibling not in html_set:
            unpaired_pdfs.append(p)
        elif carries(sibling, superseded):
            stale_pdfs.append(p)
        else:
            fresh_pdfs.append(p)

    run_dirs = sorted({str(Path(p).parent.parent) for p in pdfs})
    return {
        "schema": "dispatch_sheet_staleness/1",
        "row": "WFG-267",
        "method": "sibling_html_via_render_path",
        "method_note": (
            "A committed dispatch PDF is classed by the sentence in the sibling HTML it "
            "was rendered from; this measurement does not open the PDFs. That is a "
            "choice of route, NOT a limit of the sandbox: scripts/probe_dispatch_pdf_fonts.py "
            "reads each PDF's own embedded font subset with zlib alone and finds the same "
            "set, which corroborates this classing without replacing it. See "
            "docs/dispatch_sheet_staleness.md §4."),
        "scope": "every tracked file under outputs/ (git ls-files -z outputs)",
        "reasons": {
            "current": current,
            "superseded": superseded,
            "source": "scripts/generate_dispatch_outputs.py",
        },
        "counts": {
            "tracked_html": len(htmls),
            "tracked_pdf": len(pdfs),
            "run_dirs_with_a_committed_pdf": len(run_dirs),
            "html_carrying_superseded": len(superseded_html),
            "html_carrying_current": len(current_html),
            "stale_pdf": len(stale_pdfs),
            "fresh_pdf": len(fresh_pdfs),
            "unpaired_pdf": len(unpaired_pdfs),
        },
        "stale_pdfs": stale_pdfs,
        "unpaired_pdfs": unpaired_pdfs,
        "run_dirs_with_a_committed_pdf": run_dirs,
        "provenance": {
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=REPO,
                capture_output=True, text=True).stdout.strip(),
            "emitter_sha256": hashlib.sha256(EMITTER.read_bytes()).hexdigest(),
            "regenerate": "python scripts/measure_dispatch_sheet_staleness.py",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true",
                    help="print the measurement and write no artifact")
    args = ap.parse_args()
    result = measure()
    if args.stdout:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"staleness_{stamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    c = result["counts"]
    print(f"wrote {path.relative_to(REPO)}")
    print(f"  {c['tracked_pdf']} committed dispatch PDFs in "
          f"{c['run_dirs_with_a_committed_pdf']} run directories; "
          f"{c['stale_pdf']} carry the superseded 사유")
    for p in result["stale_pdfs"]:
        print(f"    STALE {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
