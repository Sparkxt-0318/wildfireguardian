#!/usr/bin/env python
"""Read the COMMITTED dispatch PDFs' own bytes and say which 사유 each one can spell.

WFG-267, added after the independent reviewer refused the lap's caveat as a
non-sequitur. `scripts/measure_dispatch_sheet_staleness.py` classes a PDF by the
sibling HTML it was rendered from, and justified it with 「this sandbox has no pypdf, no
pdfminer and no pdftotext」. The absence of a library is not the absence of a method:
these sheets are Chrome-rendered with an embedded Korean font SUBSET, and a subset only
contains the glyphs the page actually set. That is readable with the standard library
alone, and it is independent of the HTML.

The method, and what makes it evidence rather than a coincidence
----------------------------------------------------------------
Each PDF's `/ToUnicode` CMap maps embedded glyph ids back to Unicode. The CMaps are
`FlateDecode` streams, so `zlib` is the whole dependency. Collecting every codepoint
named across a file's CMaps gives the set of characters that file can spell.

The two sentences are then separated by the syllables UNIQUE to each:

    superseded only:  예산 내 차량 진입로가 화재로 차단됨(우회 포함)   minus the shared ones
    current only:     어느 거점에서도 생존 인지 차량 진입 경로가 확인되지 않음   minus the shared ones

A PDF that contains EVERY only-superseded syllable and NONE of the only-current ones
spells the old sentence and cannot spell the new one. This is one-directional evidence
and the script says so: a subset is a property of the whole page, so a syllable could in
principle arrive from other text on the sheet. That is why the result is reported as
CORROBORATION of the render-path classing and never as a replacement for it -- two
independent routes agreeing, which is the point.

Clock-free, network-free, standard library only, reads nothing outside the repository,
and writes nothing: it prints.

    python scripts/probe_dispatch_pdf_fonts.py
    python scripts/probe_dispatch_pdf_fonts.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_BFCHAR = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")


def _codepoints(pdf: Path) -> set[str]:
    """Every Unicode character named by any /ToUnicode CMap in `pdf`."""
    raw = pdf.read_bytes()
    out: set[str] = set()
    for m in _STREAM.finditer(raw):
        try:
            data = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        if b"beginbfchar" not in data and b"beginbfrange" not in data:
            continue
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
            for _src, dst in _BFCHAR.findall(block):
                out |= _utf16_chars(dst)
        for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
            for lo, hi, dst in _BFRANGE.findall(block):
                start = int(dst, 16)
                span = int(hi, 16) - int(lo, 16)
                for i in range(span + 1):
                    try:
                        out.add(chr(start + i))
                    except ValueError:
                        pass
    return out


def _utf16_chars(hexstr: bytes) -> set[str]:
    try:
        return set(bytes.fromhex(hexstr.decode()).decode("utf-16-be", "ignore"))
    except ValueError:
        return set()


def _reasons() -> tuple[str, str]:
    import ast  # noqa: PLC0415
    src = (REPO / "scripts" / "generate_dispatch_outputs.py").read_text(encoding="utf-8")
    found = {}
    for node in ast.parse(src).body:
        targets = ([node.target] if hasattr(node, "target") and node.__class__.__name__
                   == "AnnAssign" else list(getattr(node, "targets", [])))
        for t in targets:
            if getattr(t, "id", None) in ("UNREACHABLE_REASON_KO",
                                          "SUPERSEDED_UNREACHABLE_REASON_KO"):
                found[t.id] = node.value.value
    return found["UNREACHABLE_REASON_KO"], found["SUPERSEDED_UNREACHABLE_REASON_KO"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    current, superseded = _reasons()
    hangul = lambda s: {c for c in s if "가" <= c <= "힣"}  # noqa: E731
    only_sup = sorted(hangul(superseded) - hangul(current))
    only_cur = sorted(hangul(current) - hangul(superseded))

    listing = subprocess.run(["git", "ls-files", "-z", "outputs"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    pdfs = sorted(f for f in listing.split("\0") if f.endswith(".pdf"))

    rows = []
    for rel in pdfs:
        cps = _codepoints(REPO / rel)
        rows.append({
            "pdf": rel,
            "glyphs": len(cps),
            "spells_superseded": all(c in cps for c in only_sup),
            "spells_current": all(c in cps for c in only_cur),
        })

    says_old = [r["pdf"] for r in rows if r["spells_superseded"]]
    says_new = [r["pdf"] for r in rows if r["spells_current"]]
    result = {
        "discriminating_syllables": {"only_superseded": only_sup, "only_current": only_cur},
        "n_pdfs": len(rows),
        "spell_superseded_and_not_current": says_old,
        "spell_current": says_new,
        "rows": rows,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"{len(rows)} committed PDFs probed from their own bytes (zlib + /ToUnicode)")
    print(f"  discriminating syllables: {len(only_sup)} only-superseded, "
          f"{len(only_cur)} only-current")
    print(f"  embed every only-superseded syllable: {len(says_old)}")
    for p in says_old:
        print(f"    {p}")
    print(f"  embed every only-current syllable:    {len(says_new)}")
    for p in says_new:
        print(f"    {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
