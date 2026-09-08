#!/usr/bin/env python3
"""What the word proxy does not count, re-derived from the built document.

`check_paper.py` gates on `body_words`, which `build_docx.py` increments in
exactly two places: the list-item branch and the paragraph branch.  Figure
captions, table captions, table cells, headings, the generated References
section and the title page all render on the page and are all outside it.
This script measures that difference on the shipped `.docx` and prints the
decomposition, so no lap has to hand-count it.

Why it exists.  Paper lap 19 published this decomposition by counting the
Markdown *source* instead of the rendered *document*.  Its parts overshot its
own total, because heading lines were counted with their `#` markers attached
and because the builder prepends a rendered "Figure N. " / "Table N. " label
that the source does not contain.  Its independent reviewer found it before the
push and asked for the obvious remedy: a committed script whose output is the
table, rather than a hand-run in a session that ends.  That is this file.

What it does NOT do.  Nothing runs it on a push and it gates nothing, so a
number copied out of it into prose can still go stale in the ordinary way --
the same standing weakness `measure_pages.py` has, and a dev-lap item for the
same reason (CHARTER section 12 keeps this routine out of `tests/`).  What it
does guarantee is that the parts reconcile with the total: `main` exits 1 when
they do not, so a decomposition that does not add up cannot be printed as
though it did.

Reads only the committed `paper/manuscript.md` and the committed built
document.  Deterministic; no clock, no network, no file outside `paper/`.

    python paper/measure_render_gap.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent
DOCX = PAPER / "WildfireGuardian_Park_2026.docx"

#: A rendered figure caption paragraph, as `build_docx.py` labels it.
FIG_CAPTION = re.compile(r"^Figure \d+\.")
#: A rendered table caption paragraph.  Anchored the same way, so a body
#: sentence that merely opens with "Table 3 tallies ..." is not mistaken for
#: one -- that sentence has no full stop after the numeral.
TAB_CAPTION = re.compile(r"^Table \d+\.")


def words(text: str) -> int:
    return len(text.split())


def measure(docx_path: Path = DOCX) -> dict:
    """Decompose the rendered document into proxied and unproxied words."""
    import docx  # local: the gate must not import this at module scope

    doc = docx.Document(str(docx_path))
    paras = list(doc.paragraphs)

    heads = [i for i, p in enumerate(paras) if p.style.name.startswith("Heading")]
    abstract = next(i for i, p in enumerate(paras) if p.text.strip() == "Abstract")
    references = max(i for i in heads if paras[i].text.strip() == "References")

    out = {"front_matter": 0, "headings": 0, "figure_captions": 0,
           "table_captions": 0, "body_paragraphs": 0, "references": 0}
    for i, p in enumerate(paras):
        n, text = words(p.text), p.text.strip()
        if i < abstract:
            out["front_matter"] += n            # title, author, affiliation, draft note
        elif i > references:
            out["references"] += n
        elif p.style.name.startswith("Heading"):
            out["headings"] += n
        elif FIG_CAPTION.match(text):
            out["figure_captions"] += n
        elif TAB_CAPTION.match(text):
            out["table_captions"] += n
        else:
            out["body_paragraphs"] += n
    out["table_cells"] = sum(words(c.text)
                             for t in doc.tables for r in t.rows for c in r.cells)
    out["reference_entries"] = sum(1 for p in paras[references + 1:] if p.text.strip())
    out["rendered_total"] = sum(out[k] for k in
                                ("front_matter", "headings", "figure_captions",
                                 "table_captions", "body_paragraphs",
                                 "references", "table_cells"))
    return out


def main(argv: list[str]) -> int:
    if not DOCX.exists():
        print(f"[render-gap] no built document at {DOCX}; run paper/build_docx.py first")
        return 2
    try:
        info = measure()
    except ImportError as exc:                                  # pragma: no cover
        print(f"[render-gap] python-docx unavailable ({exc})")
        return 2

    sys.path.insert(0, str(PAPER))
    from build_docx import build  # noqa: E402  the counter under audit

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        built = build(PAPER / "manuscript.md", Path(tmp) / "audit.docx")
    body_words = built["body_words"]

    # The residual: `build_docx.py` strips `[@key]` from the source before
    # counting, while `add_runs` renders "[n]" in its place.  Rendered body
    # paragraphs therefore exceed `body_words` by the citation markers.
    residual = info["body_paragraphs"] - body_words
    parts = {
        "figure captions": info["figure_captions"],
        "table captions": info["table_captions"],
        "table cells": info["table_cells"],
        "headings": info["headings"],
        f"references ({info['reference_entries']} entries)": info["references"],
        "title-page front matter": info["front_matter"],
        "citation markers rendered but not counted": residual,
    }
    gap = info["rendered_total"] - body_words

    print(f"[render-gap] rendered in the built document : {info['rendered_total']:>6}")
    print(f"[render-gap] counted by build_docx.py       : {body_words:>6}  (body_words)")
    print(f"[render-gap] rendered and NOT counted       : {gap:>6}"
          f"  ({gap / info['rendered_total']:.1%} of the document)")
    print(f"[render-gap] the proxy sees                 : "
          f"{body_words / info['rendered_total']:.0%} of the words that render")
    for name, n in parts.items():
        print(f"[render-gap]   {name:<44} {n:>6}")
    movable = info["figure_captions"] + info["table_captions"] + info["table_cells"]
    print(f"[render-gap] of that, prose a lap could move a sentence INTO: {movable}"
          f"  ({movable / body_words:.1%} of body_words)")

    if sum(parts.values()) != gap:
        print(f"[render-gap] FAIL: the parts sum to {sum(parts.values())}, not {gap}")
        return 1
    print("[render-gap] OK: the parts reconcile with the total")
    if "--json" in argv:
        print(json.dumps({"rendered_total": info["rendered_total"],
                          "body_words": body_words, "gap": gap,
                          "parts": parts, "movable": movable}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
