#!/usr/bin/env python
"""Measure how many pages the built manuscript actually is.

Until 2026-09-05 no page count had ever been produced for
``paper/WildfireGuardian_Park_2026.docx``. ``check_paper.py`` enforces a *word*
budget and `paper/README.md` converted it to pages at an assumed words-per-page
rate; the author's rule (NH-028) is stated in pages. This script closes that by
rendering the document and counting, so the proxy can be checked against the
thing it proxies instead of being trusted.

    python paper/measure_pages.py                     # count the committed .docx
    python paper/measure_pages.py --docx other.docx
    python paper/measure_pages.py --keep-pdf out.pdf  # also save the render

Exit codes: 0 measured, 2 no usable renderer (a fact about this machine, not
about the document), 1 the render or the count failed.

⚠ WHAT THIS MEASURES, AND WHAT IT DOES NOT. It renders with LibreOffice Writer,
not Word. `build_docx.py` sets Calibri, which is not redistributable; where
Carlito is installed fontconfig substitutes it and Carlito is *metric
compatible* with Calibri, so line breaks and therefore the page count track
Word closely. Where neither is installed the substitute is not metric
compatible and the number is this machine's, not the document's — the script
says which case it is in rather than printing a bare integer. Korean runs
(the author's name, 주소정보누리집, 영덕군) fall to whatever CJK face is
present and Word will pick a different one; there are few enough of them that
they move no page boundary here, but that is an observation, not a guarantee.

⚠ WHY THIS FAILED FOR THREE LAPS. `paper/GAPS.md` recorded that the sandbox's
LibreOffice "refuses to load the built document" and that this said nothing
about our file because it also refused a two-paragraph `.docx`. Both halves
were right and the diagnosis stopped one step short: the image ships
`libreoffice-core` **without** `libreoffice-writer`, so no text-document import
filter exists at all and every word-processor format fails identically. The fix
is to install that package, which is a machine setup step and not something
this repository can carry; ``--why`` prints it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "paper"
DEFAULT_DOCX = PAPER / "WildfireGuardian_Park_2026.docx"

SETUP_HINT = (
    "No LibreOffice Writer on this machine. On Debian/Ubuntu:\n"
    "    apt-get update && apt-get install -y --no-install-recommends \\\n"
    "        libreoffice-writer fonts-crosextra-carlito fonts-nanum\n"
    "Carlito is the metric-compatible stand-in for Calibri and is what makes the\n"
    "count comparable with Word; fonts-nanum renders the Korean runs. Without\n"
    "Writer the converter reports 'source file could not be loaded' for EVERY\n"
    "word-processor file, which is a missing import filter and not a defect in\n"
    "the document."
)


def _has_writer() -> bool:
    """True when a text-document import filter is present, not merely soffice."""
    for root in ("/usr/lib/libreoffice", "/usr/lib64/libreoffice", "/opt/libreoffice"):
        if (Path(root) / "program" / "libswlo.so").exists():
            return True
    return False


#: Seconds allowed for one render. The whole conversion takes about 4 s here.
#: ⚠ Keep this well under the 300 s subprocess timeout in
#: `tests/test_paper.py`, which runs `check_paper.py`: a render timeout longer
#: than the caller's turns "the renderer hung" into a test ERROR instead of the
#: reported-and-skipped path this module promises. It was 600 for one lap.
RENDER_TIMEOUT_S = 90


def render_pdf(docx: Path, outdir: Path, timeout: int = RENDER_TIMEOUT_S) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise FileNotFoundError(SETUP_HINT)
    profile = outdir / "loprofile"
    cmd = [soffice, f"-env:UserInstallation=file://{profile}", "--headless",
           "--convert-to", "pdf", "--outdir", str(outdir), str(docx)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    pdf = outdir / (docx.stem + ".pdf")
    if not pdf.exists():
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
        hint = "" if _has_writer() else "\n" + SETUP_HINT
        raise RuntimeError("soffice produced no PDF: " + " | ".join(tail) + hint)
    return pdf


def count_pages(pdf: Path) -> dict:
    """Count pages two independent ways and refuse to guess when they disagree.

    Standard library only, so this runs in the bootstrap venv and on the
    author's laptop without adding a dependency the gates would then have to
    declare. `pypdf` agreed with the object count on the 2026-09-05 render (21
    both ways), which is what licenses the cheaper method here.
    """
    raw = pdf.read_bytes()
    # Page objects: /Type /Page but not /Type /Pages.
    n_objects = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", raw))
    # Cross-check against the page tree the catalogue points at, when the file
    # is not using compressed object streams (LibreOffice's is not).
    n_tree = None
    cat = re.search(rb"/Type\s*/Catalog(.{0,600}?)>>", raw, flags=re.S)
    if cat:
        ref = re.search(rb"/Pages\s+(\d+)\s+(\d+)\s+R", cat.group(1))
        if ref:
            obj = re.search(rb"(?<![0-9])" + ref.group(1) + rb"\s+" + ref.group(2)
                            + rb"\s+obj(.{0,4000}?)endobj", raw, flags=re.S)
            if obj:
                cnt = re.search(rb"/Count\s+(\d+)", obj.group(1))
                if cnt:
                    n_tree = int(cnt.group(1))
    if not n_objects:
        raise RuntimeError("found no page objects in the PDF; it may use compressed "
                           "object streams, which this counter does not read")
    if n_tree is not None and n_tree != n_objects:
        raise RuntimeError(f"page counts disagree: {n_objects} page objects against "
                           f"a page tree /Count of {n_tree}; not guessing")
    return {"pages": n_objects, "page_tree_count": n_tree}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", default=str(DEFAULT_DOCX))
    ap.add_argument("--keep-pdf", default=None, help="also write the rendered PDF here")
    ap.add_argument("--why", action="store_true", help="print the setup hint and exit")
    a = ap.parse_args()
    if a.why:
        print(SETUP_HINT)
        return 0
    docx = Path(a.docx)
    if not docx.exists():
        print(f"[measure_pages] no such file: {docx}; run paper/build_docx.py first")
        return 1
    if not _has_writer():
        print("[measure_pages] SKIP: " + SETUP_HINT.replace("\n", "\n[measure_pages] "))
        return 2
    with tempfile.TemporaryDirectory() as td:
        try:
            pdf = render_pdf(docx, Path(td))
            counts = count_pages(pdf)
        except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"[measure_pages] FAIL: {exc}")
            return 1
        if a.keep_pdf:
            shutil.copy(pdf, a.keep_pdf)
    fonts = _font_note()
    print("[measure_pages] " + json.dumps({"docx": str(docx), **counts, "calibri_substitute": fonts}))
    return 0


#: Faces whose metrics match Calibri's, so that a count taken with them is a
#: statement about the document rather than about the machine.
METRIC_COMPATIBLE = {"carlito", "calibri"}


def calibri_face() -> str:
    """The face name Calibri actually resolves to here. It decides the count."""
    fcmatch = shutil.which("fc-match")
    if not fcmatch:
        return "unknown"
    try:
        out = subprocess.run([fcmatch, "Calibri"], capture_output=True, text=True, timeout=30).stdout
    except subprocess.TimeoutExpired:
        return "unknown"
    return out.split('"')[1] if '"' in out else out.strip()


def metrics_ok(face: str) -> bool:
    return face.lower() in METRIC_COMPATIBLE


def _font_note() -> str:
    """The face, plus the warning when it is not one the count can be trusted on.

    ⚠ This is not decoration. MEASURED 2026-09-05 on the identical committed
    `.docx` and the identical renderer, varying only which faces fontconfig was
    allowed to see: **Carlito 21 pages, DejaVu Sans 23**. A count taken on a
    face that is not metric compatible with Calibri is a fact about the machine,
    so callers must branch on `metrics_ok()` rather than print this and move on.
    """
    face = calibri_face()
    return face if metrics_ok(face) else (
        face + " — NOT metric-compatible with Calibri; this count is this machine's, "
               "not Word's (measured: Carlito 21 pages, DejaVu Sans 23, same file)")


if __name__ == "__main__":
    raise SystemExit(main())
