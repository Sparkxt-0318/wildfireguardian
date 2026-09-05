#!/usr/bin/env python
"""Regenerate the words-to-pages curve for this manuscript, at two insertion points.

The word budget in `check_paper.py` is a proxy for the author's 25-page rule
(NH-028). This script is how that proxy is checked against the thing it proxies,
so the curve in the docstrings is re-derivable rather than a number a lap once
printed. It writes nothing into the repository: scratch copies of the manuscript
and their builds go to a temporary directory.

    python paper/calibrate_pages.py                 # both insertion points
    python paper/calibrate_pages.py --steps 0 500 1000
    python paper/calibrate_pages.py --where tail

⚠ WHY TWO INSERTION POINTS, AND WHY THE FIRST VERSION OF THIS WAS WRONG.
Paper lap 8 measured the curve once, appending filler after the last figure, and
concluded from two fillers of different vocabulary giving identical counts that
the conversion was 「a property of the template, not of the words poured into
it」. The lap's reviewer pointed out that this varied the thing that cannot
matter and held fixed the thing that does. Re-run: the same filler spliced into
§4 instead gives 7,961 words -> 22 pages where tail insertion gives 21, and
8,561 -> 23 where tail gives 22. Prose gets added in the middle of a paper, so
**tail insertion is the optimistic bound**, and the curve is reported as a range
across the two rather than as a rate.

⚠ AND THE COUNT IS FONT-CONDITIONAL. Measured on the identical built file, same
renderer, varying only which faces fontconfig may see: Carlito 21 pages, DejaVu
Sans 23. `build_docx.py` asks for Calibri, which is not redistributable; only a
metric-compatible stand-in makes the number a statement about the document.
This script refuses to report a curve on a face that is not one, for the same
reason `check_paper.py` refuses to gate on it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"
sys.path.insert(0, str(PAPER))
from build_docx import build  # noqa: E402
import measure_pages  # noqa: E402

#: Where filler goes. "tail" is after every figure; "mid" is among them, in §4,
#: which is where a lap actually adds a caveat.
ANCHORS = {
    "tail": "## Data and code availability",
    "mid": "### 4.2 The operating point, and why no threshold guarantee is available",
}
DEFAULT_STEPS = (0, 500, 1000, 1500, 2000, 2500, 3000)


def body_paragraphs(src: str) -> list[str]:
    """The manuscript's own prose, so the filler sets like the real thing.

    Stock filler would do here — lap 8 measured both and they agreed — but real
    paragraphs cost nothing and remove the objection.
    """
    paras, buf = [], []
    for ln in src.split("\n"):
        if ln.strip() and not re.match(r"^(#|!\[|\||Table\s|\s*[-*]\s|\s*\d+\.\s)", ln):
            buf.append(ln.rstrip())
        else:
            if len(buf) >= 4:
                paras.append(" ".join(buf))
            buf = []
    if len(buf) >= 4:
        paras.append(" ".join(buf))
    out = []
    for p in paras:
        p = re.sub(r"\[@[^\]]+\]", "", p)
        p = re.sub(r"\[GAP:[^\]]+\]", "", p)
        out.append(re.sub(r"\s+", " ", p.replace("**", "").replace("*", "").replace("`", "")).strip())
    return out


def wrap(text: str, width: int = 86) -> str:
    """88-column hard wrap, as `paper/README.md` requires of the manuscript."""
    out, line = [], []
    for w in text.split():
        if sum(len(x) + 1 for x in line) + len(w) > width:
            out.append(" ".join(line))
            line = []
        line.append(w)
    if line:
        out.append(" ".join(line))
    return "\n".join(out)


def filler(paras: list[str], n_words: int) -> str:
    got, words, i = [], 0, 0
    while words < n_words:
        ws = paras[i % len(paras)].split()
        i += 1
        if words + len(ws) > n_words:
            ws = ws[: n_words - words]
        got.append(wrap(" ".join(ws)))
        words += len(ws)
    return "\n\n".join(got) + "\n\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, nargs="+", default=list(DEFAULT_STEPS),
                    help="extra body words to splice in")
    ap.add_argument("--where", choices=sorted(ANCHORS) + ["both"], default="both")
    a = ap.parse_args()

    if not measure_pages._has_writer():
        print("[calibrate] SKIP: " + measure_pages.SETUP_HINT.replace("\n", "\n[calibrate] "))
        return 2
    face = measure_pages.calibri_face()
    if not measure_pages.metrics_ok(face):
        print(f"[calibrate] SKIP: Calibri resolves to {face!r}, whose metrics are not Calibri's, "
              f"so a curve measured here would describe this machine. "
              f"Install fonts-crosextra-carlito.")
        return 2

    src = (PAPER / "manuscript.md").read_text(encoding="utf-8")
    paras = body_paragraphs(src)
    wheres = sorted(ANCHORS) if a.where == "both" else [a.where]
    rows = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for where in wheres:
            anchor = ANCHORS[where]
            if anchor not in src:
                print(f"[calibrate] FAIL: anchor for {where!r} is not in manuscript.md: {anchor!r}")
                return 1
            for extra in a.steps:
                text = src if not extra else src.replace(anchor, filler(paras, extra) + anchor)
                md = tmp / f"{where}_{extra}.md"
                md.write_text(text, encoding="utf-8")
                info = build(md, tmp / f"{where}_{extra}.docx")
                pages = measure_pages.count_pages(
                    measure_pages.render_pdf(tmp / f"{where}_{extra}.docx", tmp))["pages"]
                rows.append({"where": where, "extra_words": extra,
                             "body_words": info["body_words"], "pages": pages})
                print(f"[calibrate] {where:4s} +{extra:<5d} {info['body_words']:6d} words "
                      f"-> {pages:3d} pages")
    print("[calibrate] " + json.dumps({"calibri_face": face, "rows": rows}))
    by = {}
    for r in rows:
        by.setdefault(r["body_words"], {})[r["where"]] = r["pages"]
    spread = [(w, v) for w, v in sorted(by.items()) if len(set(v.values())) > 1]
    if spread:
        print("[calibrate] insertion point changes the count at: "
              + ", ".join(f"{w} words {v}" for w, v in spread)
              + " — so the tail curve is a LOWER BOUND on pages, not a conversion rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
