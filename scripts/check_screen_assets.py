#!/usr/bin/env python
"""Three gates a demonstration screen must pass, checkable before one is built.

Round-3 PHASE 21 STEP 1.

WHY THE CHECKERS COME FIRST
---------------------------
A screen that fetches a font from a CDN works perfectly on the machine it was
built on and fails in the room where it matters — a competition hall with no
network, or a network that resolves nothing. A contrast failure is invisible to
the person who chose the colour and decisive for the judge reading it from four
metres away. Both are cheap to check and expensive to discover late, so the
checks exist before the thing they check.

THREE GATES
-----------
1. ``offline``  — no external resource of any kind. Not a CDN font, not a map
   tile, not an analytics beacon. The only URL permitted anywhere is the SVG
   XML namespace, which is an identifier and is never fetched.
2. ``dashes``   — no EM dash (U+2014) and no EN dash (U+2013) in visible text.
   Both are wider than a digit in most proportional faces, so a dash inside a
   numeric column defeats ``font-variant-numeric: tabular-nums`` and the
   figures stop lining up. Ranges and changes get a tilde or an arrow instead.
3. ``contrast`` — every declared foreground/background pair meets WCAG 2.1.
   Computed exactly, from the relative-luminance definition, not eyeballed.

⚠ WHAT THIS TOOL DOES NOT DO
It cannot measure a GLYPH'S ADVANCE WIDTH without the font file, and no font is
vendored in this repository yet. So "is the arrow the same width as a digit in
the face we ship?" is NOT answered here and must not be assumed — see
``--report`` output, which says so rather than staying silent.

Run:
    python scripts/check_screen_assets.py demo/operator_screen.html
    python scripts/check_screen_assets.py --report      # palette audit only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# 1. Offline
# ---------------------------------------------------------------------------

#: The permitted URLs. Both are XML namespace IDENTIFIERS — the strings name a
#: dialect and are never dereferenced. `tests/test_operator_screen.py` already
#: relies on the SVG one.
#:
#: ⚠ Exempting the XLink namespace exempts the NAMESPACE, not the attribute set
#: through it: `setAttributeNS(XLINK_NS, 'href', x)` is fine only while `x` is
#: a data: URI or a fragment. What `x` is remains the author's problem.
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
NAMESPACE_IDENTIFIERS: frozenset[str] = frozenset({SVG_NS, XLINK_NS})

#: Ways a page can reach the network. Checked as text, because the point is
#: that none of them should be present at all.
NETWORK_TOKENS: tuple[str, ...] = (
    "fetch(", "XMLHttpRequest", "WebSocket(", "EventSource(",
    "navigator.sendBeacon", "importScripts(", "serviceWorker",
    "@import", "url(http", "srcset=", "integrity=",
)

_URL_RE = re.compile(r"""https?://[^\s"'<>)]+""")


@dataclass
class Finding:
    gate: str
    line: int
    detail: str
    excerpt: str = ""

    def as_dict(self) -> dict:
        return {"gate": self.gate, "line": self.line, "detail": self.detail,
                "excerpt": self.excerpt}


def check_offline(text: str) -> list[Finding]:
    out: list[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for url in _URL_RE.findall(line):
            if url.rstrip("\"',") in NAMESPACE_IDENTIFIERS:
                continue
            out.append(Finding("offline", i, f"external URL: {url}",
                               line.strip()[:120]))
        for tok in NETWORK_TOKENS:
            if tok in line:
                out.append(Finding("offline", i,
                                   f"network-capable construct: {tok}",
                                   line.strip()[:120]))
    return out


# ---------------------------------------------------------------------------
# 2. Dashes
# ---------------------------------------------------------------------------

#: EM dash and EN dash. Both banned in visible text.
BANNED_DASHES: dict[str, str] = {
    "—": "EM dash (U+2014)",
    "–": "EN dash (U+2013)",
}

#: What to use instead. Recorded here so the error message can say it.
DASH_REPLACEMENTS = (
    "range  ->  tilde:  125~530 m",
    "change ->  arrow:  6.12 → 1.71",
    "list   ->  middle dot or slash",
    "inside a numeric TABLE -> split the column (Before / After), never a "
    "glyph: any inline glyph risks breaking tabular-nums alignment",
)

#: Regions of an HTML file that are NOT visible text. A dash inside a comment
#: or a script string is not on screen and is not a typographic problem.
_SCRIPT_OR_STYLE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>|<!--.*?-->", re.S | re.I)


def visible_text(html: str) -> str:
    """Strip script, style and comments; keep what a reader can see."""
    return _SCRIPT_OR_STYLE.sub(lambda m: "\n" * m.group(0).count("\n"), html)


def check_dashes(text: str, *, html: bool = True) -> list[Finding]:
    body = visible_text(text) if html else text
    out: list[Finding] = []
    for i, line in enumerate(body.splitlines(), start=1):
        for ch, name in BANNED_DASHES.items():
            if ch in line:
                col = line.index(ch)
                out.append(Finding(
                    "dashes", i,
                    f"{name} in visible text — it is wider than a digit and "
                    "defeats tabular-nums",
                    line.strip()[max(0, col - 40):col + 40]))
    return out


# ---------------------------------------------------------------------------
# 3. Contrast — WCAG 2.1, computed exactly
# ---------------------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour: str) -> float:
    """WCAG 2.1 relative luminance of an sRGB colour."""
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) == 8:            # #rrggbbaa — alpha ignored, see contrast()
        h = h[:6]
    if len(h) != 6:
        raise ValueError(f"not a colour: {hex_colour!r}")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g)
            + 0.0722 * _srgb_to_linear(b))


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio, 1.0 to 21.0.

    ⚠ Alpha is IGNORED. A translucent foreground's real contrast depends on
    what is behind it, which a static check cannot know — so a colour with
    alpha is reported at its opaque ratio and that is an UPPER bound. Do not
    read a pass on a translucent colour as a pass.
    """
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


#: WCAG 2.1 thresholds.
AA_NORMAL, AA_LARGE, AAA_NORMAL = 4.5, 3.0, 7.0
#: Non-text (icons, chart marks, focus rings) — WCAG 2.1 SC 1.4.11.
NON_TEXT = 3.0


def grade(ratio: float, *, large: bool = False, non_text: bool = False) -> str:
    need = NON_TEXT if non_text else (AA_LARGE if large else AA_NORMAL)
    if ratio >= AAA_NORMAL and not non_text:
        return "AAA"
    return "AA" if ratio >= need else "FAIL"


@dataclass
class ContrastPair:
    name: str
    fg: str
    bg: str
    large: bool = False
    non_text: bool = False

    def check(self) -> dict:
        r = contrast(self.fg, self.bg)
        return {"name": self.name, "fg": self.fg, "bg": self.bg,
                "ratio": round(r, 2),
                "required": (NON_TEXT if self.non_text
                             else AA_LARGE if self.large else AA_NORMAL),
                "grade": grade(r, large=self.large, non_text=self.non_text),
                "kind": ("non-text" if self.non_text
                         else "large text" if self.large else "body text")}


def check_contrast(pairs: list[ContrastPair]) -> list[Finding]:
    out: list[Finding] = []
    for p in pairs:
        res = p.check()
        if res["grade"] == "FAIL":
            out.append(Finding(
                "contrast", 0,
                f"{p.name}: {res['ratio']}:1 on {p.bg} — needs "
                f"{res['required']}:1 for {res['kind']}", f"{p.fg} on {p.bg}"))
    return out


# ---------------------------------------------------------------------------
# The palette actually in use today, so a new one has a baseline to beat
# ---------------------------------------------------------------------------

#: Extracted from `scripts/build_operator_screen.py`. These are the colours the
#: PHASE-8 screen ships with; measuring them is what makes "the new palette is
#: better" a comparison rather than an assertion.
CURRENT_BG_DEEP = "#0b0f14"
CURRENT_BG_PANEL = "#16202b"

CURRENT_PALETTE: list[ContrastPair] = [
    ContrastPair("본문 (밝은 회색)", "#e8edf2", CURRENT_BG_PANEL),
    ContrastPair("보조 텍스트", "#94a3b8", CURRENT_BG_PANEL),
    ContrastPair("흐린 텍스트", "#64748b", CURRENT_BG_PANEL),
    ContrastPair("자력 대피 (청록 점)", "#22d3ee", CURRENT_BG_DEEP, non_text=True),
    ContrastPair("구조 필요 (황색 점)", "#f59e0b", CURRENT_BG_DEEP, non_text=True),
    ContrastPair("도달 불가 (적색 점)", "#dc2626", CURRENT_BG_DEEP, non_text=True),
    ContrastPair("경로: 미래 인지 (청록 선)", "#22d3ee", CURRENT_BG_DEEP, non_text=True),
    ContrastPair("경로: 화재 무지 (적색 선)", "#f87171", CURRENT_BG_DEEP, non_text=True),
    ContrastPair("강조 (청색)", "#2563eb", CURRENT_BG_PANEL, non_text=True),
    ContrastPair("경고 텍스트 (황)", "#fde047", CURRENT_BG_PANEL),
    ContrastPair("적색 텍스트", "#f87171", CURRENT_BG_PANEL),
]


def palette_report(pairs: list[ContrastPair] = CURRENT_PALETTE) -> dict:
    rows = [p.check() for p in pairs]
    return {
        "pairs": rows,
        "n_fail": sum(1 for r in rows if r["grade"] == "FAIL"),
        "thresholds": {"AA_normal": AA_NORMAL, "AA_large": AA_LARGE,
                       "AAA_normal": AAA_NORMAL, "non_text": NON_TEXT},
        "caveats": [
            "Alpha is ignored; a translucent colour's ratio here is an UPPER "
            "bound.",
            "Non-text marks are graded against SC 1.4.11 (3:1), which is the "
            "right bar for a dot on a map and the WRONG bar for a number "
            "printed in that colour.",
            "⚠ Contrast is necessary and not sufficient. A colour-blind-safe "
            "palette still must not encode meaning by colour ALONE — shape "
            "and label carry it too, which is also what makes the screen "
            "survive a black-and-white projector and the 이장's photocopier.",
        ],
        "not_measured": [
            "Glyph advance widths (arrow, tilde, dash) against a digit: needs "
            "the shipping font file, and no font is vendored in this "
            "repository yet. Until it is, 'the arrow does not break "
            "tabular-nums' is an ASSUMPTION, not a measurement.",
            "13 px Hangul legibility: same reason.",
        ],
    }


# ---------------------------------------------------------------------------


def check_file(path: Path, *, pairs: list[ContrastPair] | None = None) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    html = path.suffix.lower() in (".html", ".htm")
    found = check_offline(text) + check_dashes(text, html=html)
    if pairs:
        found += check_contrast(pairs)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path,
                    help="screen assets to check (HTML/CSS/JS)")
    ap.add_argument("--report", action="store_true",
                    help="print the palette contrast audit and exit")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.report:
        rep = palette_report()
        if args.json:
            print(json.dumps(rep, indent=2, ensure_ascii=False))
            return 0
        print("=" * 78)
        print("  현재 화면 팔레트 — WCAG 2.1 대비 실측")
        print("=" * 78)
        for r in rep["pairs"]:
            mark = "OK " if r["grade"] != "FAIL" else "FAIL"
            print(f"  {mark} {r['ratio']:6.2f}:1  (필요 {r['required']}:1, "
                  f"{r['kind']:10s})  {r['name']}   {r['fg']} on {r['bg']}")
        print(f"\n  기준 미달: {rep['n_fail']}건")
        for c in rep["caveats"]:
            print(f"  · {c}")
        print("\n  측정하지 않은 것:")
        for c in rep["not_measured"]:
            print(f"  ⚠ {c}")
        return 1 if rep["n_fail"] else 0

    if not args.paths:
        ap.error("give at least one path, or --report")

    all_found: list[Finding] = []
    for p in args.paths:
        found = check_file(p)
        all_found += found
        status = "PASS" if not found else f"{len(found)} finding(s)"
        print(f"{p}: {status}")
        for f in found[:20]:
            print(f"  [{f.gate}] line {f.line}: {f.detail}")
            if f.excerpt:
                print(f"      {f.excerpt}")
    if any(f.gate == "dashes" for f in all_found):
        print("\n대시 대체 규칙:")
        for r in DASH_REPLACEMENTS:
            print(f"  · {r}")
    return 1 if all_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
