#!/usr/bin/env python
"""The manuscript's gate. Exit 1 on any failure; prints every finding.

  - the built document is <= 25 pages, MEASURED where a renderer exists
  - body text <= 9,000 words, the proxy for that ceiling on machines without one
  - a page count recorded in STATE.json is still anchored to the figure, table
    and reference set it was measured on — the check that needs no renderer
  - every ![caption](figures/X.png) exists and was produced by make_figures.py
  - every [@key] exists in references.bib with a `note` that says verified
  - every [GAP: ...] in the manuscript has a row in GAPS.md, and vice versa
  - the .docx builds (python-docx) and its title is the manuscript's
  - registry-anchored numbers: delegated to scripts/check_number_collisions.py,
    which already scans paper/manuscript.md as tracked prose (make verify)

THE LENGTH RULE. The author decided on 2026-09-05 (NH-028, verbatim: 「Don't
worry about the word count for now. Just make sure it doesn't exceed. 25 pages
for. now」), and a laptop session wrote 25 pages into CHARTER §12 and the
8,500 / 9,000-word proxy into `docs/auto/LOOP_CONFIG.json` and into this file.
That session had to estimate the conversion — its note read 「about 21 pages」.

Paper lap 8 measured the document instead of estimating it: **21 pages**, under
Carlito. `paper/calibrate_pages.py` regenerates the words-to-pages curve, and
what it shows is that the proxy is weaker than it looks. Appending filler ahead
of the availability section, figures and tables held fixed:

    7,461 words -> 21 pages      8,961 -> 23       9,961 -> 24
    7,961       -> 21            9,461 -> 24      10,461 -> 25

⚠ **That curve is the optimistic case and must not be read as a conversion
rate.** Lap 8 first claimed it was 「a property of the template, not of the words
poured into it」, on the evidence that two fillers of different vocabulary gave
identical counts. The lap reviewer pointed out that this controlled the variable
that cannot matter and held fixed the one that does — where the words go — and
the re-run agreed. Splicing the same filler into §4, among the figures, instead
of after them:

    words   7,461  7,961  8,561  8,961  9,461  9,961  10,461
    tail       21     21     22     23     24     24      25
    in §4      21     22     23     23     24     25      25

Real prose is added in the middle of a paper, so **the tail row is a lower bound
on pages, not the conversion.**

What survives, stated at the precision the sampling supports: 「about 21」 was
exactly 21; at the proxy's own 9,000-word limit the document is **23 pages by
either route**, so the proxy keeps two pages of margin and is sound; and the
25-page ceiling arrives between 9,961 words (among the figures) and 10,461 (at
the end), i.e. the proxy stops a lap roughly a thousand words early, which is
the direction it should err in. The sampling step is 500 words and **no count
above 25 was ever measured**, so the ceiling's exact word position is bracketed,
not known.

⚠ And the proxy cannot see the real risk at all. Figures, not prose, are why §4
is eight of the 21 pages, so a new figure costs a page and not one word. That is
what the page check below is for, and why the word budget is only its stand-in
on machines that cannot render.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"
sys.path.insert(0, str(PAPER))
from build_docx import build, parse_bib  # noqa: E402

#: Body-text words: the proxy, kept at the author's number. See the docstring.
LIMIT = 9000
#: The author's actual rule (NH-028, 2026-09-05), checked wherever it can be.
PAGE_LIMIT = 25


def _png_size(path: Path) -> tuple:
    """(width, height) from a PNG's IHDR. Stdlib only, on purpose.

    The fingerprint below must not need Pillow: `check_paper.py` runs on every
    push through `tests/test_paper.py`, and a new import there is a new way for
    the gate to be red about itself rather than about the paper.
    """
    head = path.read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return (None, None)
    return struct.unpack(">II", head[16:24])


def figure_fingerprint(text: str) -> dict:
    """What moves the page count and leaves the word budget unmoved.

    NOT a digest of the PNG bytes. `paper/README.md` records why: `style.py`
    falls back through a font list, so the same script on the same artifacts
    re-renders to different bytes on a machine with a different font set, and a
    byte digest would call that a change. What actually costs a page is a
    figure's presence and its aspect ratio at fixed column width, which survives
    a substituted face — so the fingerprint is over the ordered (path, pixel
    size) list, joined by the table and reference counts and the body-word count
    in `fingerprint_digest`. Those four are what the page count is a function of;
    a recorded count outlives a change to none of them.
    """
    figs = []
    for rel in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        w, h = _png_size(PAPER / rel) if (PAPER / rel).exists() else (None, None)
        figs.append([rel, w, h])
    return figs


def fingerprint_digest(figs: list, tables: int, refs: int, words: int) -> str:
    """The identity of the document a page count was measured on.

    `body_words` is in here deliberately, and it is the difference between a
    gate and a comfort. Leaving it out would let a recorded 「21 pages」 ride
    through any amount of new prose on the argument that the word budget covers
    prose — but the word budget covers the CEILING, not the accuracy of a
    recorded count, and the measured curve moves a page within the budget's own
    range (7,461 -> 21, 7,961 -> 22 when the words go among the figures). So a
    page count survives exactly as long as the document it describes, and on a
    machine that cannot re-measure the honest value is null.
    """
    blob = json.dumps({"figures": figs, "tables": tables, "references": refs, "body_words": words},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def page_check(docx: Path, problems: list) -> dict:
    """Count the built document's pages, where this machine can do so honestly.

    THREE OUTCOMES, and only one of them can fail the gate.

    * **No renderer** — most machines, including whatever CI runs on. Reported;
      the word budget is what covers them. Never a failure.
    * **A renderer, but Calibri resolves to a face whose metrics are not
      Calibri's** — the count is then a fact about the machine. MEASURED on the
      identical file: Carlito 21 pages, DejaVu Sans 23. Reported with the face
      named; never a failure, because failing on it would fail a document that
      is inside the author's rule in Word. This is the branch a lap reviewer
      caught missing on 2026-09-05: the first version computed the face, printed
      it, and then failed hard on the number anyway.
    * **A renderer and metric-compatible metrics** — the count means something,
      and over `PAGE_LIMIT` it fails.

    A render that raises is reported and PASSES; the word budget stays the net.
    That is deliberate (a flaky converter must not turn a push red) and it is
    said plainly here because an earlier version of this docstring claimed the
    opposite — "reported loudly rather than swallowed as a pass" — of code that
    appended nothing to `problems`.

    `measure_pages` is imported lazily and defensively: `check_paper.py` must
    still run if that file is missing, since a module-scope import of a sibling
    that a lap forgot to stage would make every push ImportError-red through
    `tests/test_paper.py`.
    """
    try:
        import measure_pages
    except Exception as exc:                       # noqa: BLE001
        return {"pages": None, "why": f"paper/measure_pages.py unavailable ({exc}); word budget only"}
    if not measure_pages._has_writer():
        return {"pages": None,
                "why": "no LibreOffice Writer here (paper/measure_pages.py --why); word budget only"}
    face = measure_pages.calibri_face()
    try:
        with tempfile.TemporaryDirectory() as td:
            counts = measure_pages.count_pages(measure_pages.render_pdf(docx, Path(td)))
    except Exception as exc:                       # noqa: BLE001 — reported, deliberately not fatal
        return {"pages": None, "why": f"renderer present but failed: {exc}"}
    out = {"pages": counts["pages"], "calibri_face": face,
           "metrics_ok": measure_pages.metrics_ok(face)}
    if not out["metrics_ok"]:
        out["why"] = (f"Calibri resolved to {face!r}, whose metrics are not Calibri's, so this "
                      f"count describes this machine; not gated. Install fonts-crosextra-carlito.")
        return out
    if counts["pages"] > PAGE_LIMIT:
        problems.append(f"built document is {counts['pages']} pages > {PAGE_LIMIT} "
                        f"(the author's rule, NH-028); the word budget did not catch it, "
                        f"which is what happens when figures rather than prose grow")
    return out


def main() -> int:
    md = PAPER / "manuscript.md"
    text = md.read_text(encoding="utf-8")
    problems = []
    with tempfile.TemporaryDirectory() as td:
        docx = Path(td) / "check.docx"
        info = build(md, docx)
        # Measured on the document this manuscript builds NOW, not on the committed
        # .docx, so the gate cannot pass a stale artifact.
        pages = page_check(docx, problems)
    if info["body_words"] > LIMIT:
        problems.append(f"body text {info['body_words']} words > {LIMIT}")
    for rel in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        if not (PAPER / rel).exists():
            problems.append(f"figure missing: {rel}")
    bib = parse_bib(PAPER / "references.bib")
    for key in set(k.strip().lstrip("@") for grp in re.findall(r"\[@([^\]]+)\]", text) for k in grp.split(";")):
        if key not in bib:
            problems.append(f"citation not in references.bib: {key}")
        elif "verified" not in bib[key].get("note", "").lower():
            problems.append(f"citation {key} has no 'verified' note")
    gaps_md = (PAPER / "GAPS.md").read_text(encoding="utf-8") if (PAPER / "GAPS.md").exists() else ""
    n_rows = len(re.findall(r"^\|\s*G\d+\s*\|", gaps_md, flags=re.M))
    n_marks = len(re.findall(r"\[GAP:", text))
    if n_marks != n_rows:
        problems.append(f"{n_marks} [GAP] markers in manuscript vs {n_rows} rows in GAPS.md")
    if not info["title"]:
        problems.append("no title line (# ...) at the top of manuscript.md")
    state = {"body_words": info["body_words"], "figures": info["figures"], "tables": info["tables"],
             "references": info["references"], "gaps": n_marks}
    figs = figure_fingerprint(text)
    digest = fingerprint_digest(figs, info["tables"], info["references"], info["body_words"])
    print("[check_paper] " + json.dumps(state))
    print("[check_paper] pages " + json.dumps(pages))
    # Printed ONLY by a run that measured. This lap's reviewer blocked on the first
    # version, which printed it unconditionally: on a machine that cannot measure, the
    # digest is the one string that silences the staleness check, so printing it there
    # made the bypass (paste it, keep the old page count) and the honest act (null both)
    # the same keystrokes. The value a run may record is the value a run derived.
    if pages.get("pages") is not None and pages.get("metrics_ok"):
        print("[check_paper] built_pages_inputs " + digest + "  (measured this run)")
    # STATE.json is bookkeeping the paper routine writes at the end of its lap, and until
    # 2026-09-05 nothing compared it with the manuscript it describes: this function
    # computed exactly these counts, printed them, and threw them away. A lap reviewer
    # caught STATE.json holding the PREVIOUS lap's body_words and gap count while the
    # manuscript had moved, and no gate anywhere would have said so. Only the counts are
    # checked. `last_incorporated_commit` is deliberately NOT checked: it names the code
    # commit the manuscript was written against and legitimately lags HEAD.
    state_path = PAPER / "STATE.json"
    if state_path.exists():
        try:
            recorded = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"STATE.json is not valid JSON: {exc}")
        else:
            checked = dict(state)
            # `built_pages` is bookkeeping like the rest, so it gets the same drift
            # check — but only when this machine actually produced a trustworthy
            # count, or a machine with no renderer would fail on every run. Without
            # this branch built_pages would be the one number in the file nothing
            # ever compares, which is exactly the staleness class the drift check
            # below was added to kill, on the one number a new figure changes.
            measured_here = pages.get("pages") is not None and bool(pages.get("metrics_ok"))
            if measured_here and "built_pages" in recorded:
                checked["built_pages"] = pages["pages"]
            # WFG-116 / critic #21 F4. Everything above this line is dead on every
            # machine the loop actually owns: no cloud lap and no `auto-gates` run has
            # LibreOffice Writer, so `measured_here` is False there and `built_pages`
            # became the one number in this file that nothing ever re-derived — on the
            # one quantity a new FIGURE changes, which is precisely what the word proxy
            # cannot see. The rule below needs no renderer, and it is worth being exact
            # about what it is and is not, because this lap's reviewer blocked the first
            # version for claiming more.
            #
            # It does NOT re-derive the page count. Nothing here can: a renderer is the
            # only thing that produces that number, and STATE.json is bookkeeping a lap
            # writes by hand, so any field in it is forgeable by the lap the gate audits.
            # What it does is bind a carried count to the document it was measured on,
            # so that (i) a figure or a table or a block of prose arriving unnoticed
            # turns the gate RED instead of silently invalidating a number nobody
            # rechecks, and (ii) keeping the old count anyway stops being an accident
            # and becomes an edit a reviewer can see in the diff. F4's first alternative
            # — one apt line in auto-gates.yml, so a clean clone measures — is the fix
            # that actually re-derives, is outside paper/, and is still open.
            if recorded.get("built_pages") is not None:
                if measured_here:
                    checked["built_pages_inputs"] = digest
                elif recorded.get("built_pages_inputs") is None:
                    problems.append(
                        f"paper/STATE.json records built_pages {recorded['built_pages']!r} with no "
                        f"built_pages_inputs to anchor it, and this machine cannot re-measure — set "
                        f"both to null, or re-measure (paper/measure_pages.py --why prints the "
                        f"install). The anchor is written by the run that measured, not by hand"
                    )
                elif recorded["built_pages_inputs"] != digest:
                    problems.append(
                        f"paper/STATE.json built_pages {recorded['built_pages']!r} was measured on a "
                        f"different document (built_pages_inputs {recorded['built_pages_inputs']!r}) "
                        f"and this machine has no renderer to re-measure. A figure costs a page and "
                        f"no words, so the word budget did not catch this: set built_pages and "
                        f"built_pages_inputs to null, or re-measure (paper/measure_pages.py --why). "
                        f"Do not hand-write the new anchor: it would keep a page count that no run "
                        f"produced, which is the staleness this check exists to make loud"
                    )
            drift = {k: (recorded.get(k), v) for k, v in checked.items() if recorded.get(k) != v}
            if drift:
                problems.append(
                    "STATE.json disagrees with the manuscript it describes "
                    + ", ".join(f"{k}: recorded {was!r}, built {now!r}" for k, (was, now) in sorted(drift.items()))
                    + " — rerun the build and update paper/STATE.json"
                )
    else:
        problems.append("paper/STATE.json is missing")
    for p in problems:
        print("[check_paper] FAIL: " + p)
    print("[check_paper] " + ("OK" if not problems else f"{len(problems)} problem(s)"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
