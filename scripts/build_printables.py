#!/usr/bin/env python
"""Build the booth printables as one A4 PDF, offline, from committed sources only.

WHY THIS EXISTS, AND WHY IT LOOKS LIKE THIS
-------------------------------------------
WFG-007 asks for booth printables "built by a script". Three dev laps did not
ship one, and the reason is visible the moment you look for a PDF toolchain in a
fresh sandbox: there is no ``reportlab``, no ``weasyprint``, no ``wkhtmltopdf``,
no ``pandoc`` and no headless Chromium. Adding one would mean a new pinned
dependency that ``make check-declared-deps`` and ``scripts/env_check.py`` must
then carry to the booth laptop, for prose that never changes shape.

What IS already here: ``matplotlib`` (every figure in this repository is drawn
with it) writes PDF, and ``fontTools`` + ``brotli`` (both already declared) can
decompress the Korean web fonts this project already ships in
``web/assets/fonts/``. So the printables are drawn on the same stack as the
figures, in the same typeface as the screens, with no new dependency at all.

THE FONT IS A SUBSET, AND THAT IS THE DANGEROUS PART
----------------------------------------------------
``IBMPlexSansKR-Regular.woff2`` carries **2,460 codepoints**, not the full
Korean repertoire: it was subset for the finals screens. Every hangul syllable
these documents use is present, but seventeen punctuation and symbol
codepoints are NOT -- ``§ — – ← → ≥ ⚠ 「 」 〔 〕 Ⅱ Ⅲ Ⅴ ② ✅ ❌ ⭕ 🛑``.

A missing glyph in matplotlib does not raise. It renders as a blank or a
fallback box, silently, and the failure surface is a sheet of paper a judge is
holding. CHARTER §8 already knows this hazard in its narrow form ("no em-dashes
in shipped screens (font subset)"); this script generalises it into a gate:
every character is either in the font, or in ``SUBSTITUTIONS`` below, or the
build **refuses to run**. There is no third branch and no silent drop.

WHAT THIS IS NOT
----------------
Not a Markdown renderer. It handles the subset these four documents actually
use -- ATX headings, ``-``/``*`` bullets, blockquotes, fenced code, tables (kept
verbatim in the mono face), horizontal rules, and inline ``**bold**``/``` `code` ```
stripped to plain text. Anything else prints as its own source line, which is
legible and honest rather than clever. Images are dropped and named.

Usage
-----
    python scripts/build_printables.py --stamp 20260906T0620Z

Writes ``docs/auto/finals/printables/WFG_printables_<stamp>.pdf`` and
``manifest_<stamp>.json`` beside it. A stamp is never reused: CHARTER §3.2 says
new results get new filenames, so a later lap's rebuild sits beside this one
rather than overwriting it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import tempfile
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
# Type 42 embeds the TrueType outlines. The default (Type 3) inlines glyph
# procedures and several viewers render CJK from it badly or not at all; this is
# the one rcParam that decides whether the Korean text survives printing.
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["pdf.compression"] = 6

import matplotlib.pyplot as plt  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "web" / "assets" / "fonts"
OUT_DIR = ROOT / "docs" / "auto" / "finals" / "printables"

REGULAR_WOFF2 = FONT_DIR / "IBMPlexSansKR-Regular.woff2"
SEMIBOLD_WOFF2 = FONT_DIR / "IBMPlexSansKR-SemiBold.woff2"
MONO_WOFF2 = FONT_DIR / "IBMPlexMono-Regular.woff2"

# The documents that go on paper, in the order a student would want them in the
# folder. Each entry is (repo-relative path, printed section title). Adding a
# source here is the whole extent of "adding a printable"; the coverage gate
# then decides whether it can be printed at all.
SOURCES: list[tuple[str, str]] = [
    ("docs/auto/finals/BOOTH_SETUP.md", "부스 설치 체크리스트"),
    ("docs/auto/DEMO_SCRIPT_5MIN.md", "5분 시연 대본"),
    ("docs/auto/JUDGE_QA.md", "심사위원 질의응답 카드"),
    ("docs/auto/finals/DETECTION_FLOOR_CARD.md", "탐지 하한 근거 카드"),
]

# Characters the committed font subset does not carry, mapped to something it
# does. Every entry is a deliberate typographic decision, not a fallback: the
# left column is what the source says, the right column is what the paper says.
# CHARTER §8's em-dash rule is the first row of this table.
SUBSTITUTIONS: dict[str, str] = {
    "§": "S",          # § section sign
    "—": " - ",        # — em dash (CHARTER §8)
    "–": "-",          # – en dash
    "←": "<-",         # ←
    "→": "->",         # →
    "≥": ">=",         # ≥
    "≤": "<=",         # ≤
    "⚠": "[!]",        # ⚠
    "「": '"',          # 「
    "」": '"',          # 」
    "〔": "[",          # 〔
    "〕": "]",          # 〕
    "Ⅰ": "I",          # Ⅰ
    "Ⅱ": "II",         # Ⅱ
    "Ⅲ": "III",        # Ⅲ
    "Ⅳ": "IV",         # Ⅳ
    "Ⅴ": "V",          # Ⅴ
    "①": "(1)",        # ①
    "②": "(2)",        # ②
    "③": "(3)",        # ③
    "✅": "[O]",        # ✅
    "❌": "[X]",        # ❌
    "⭕": "[O]",        # ⭕
    "\U0001f6d1": "[STOP]",  # 🛑
    "×": "x",          # ×
    "±": "+/-",        # ±
    "‑": "-",          # non-breaking hyphen
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
    "…": "...",        # …
    " ": " ",          # nbsp
}

# A4 in inches, and the typographic grid. Everything below is measured in
# figure fractions off these two numbers so the layout cannot drift.
A4_W, A4_H = 8.268, 11.693
MARGIN_L, MARGIN_R = 0.085, 0.055
MARGIN_T, MARGIN_B = 0.955, 0.055
LINE_H = 0.0148          # body line height as a fraction of page height
BODY_PT = 8.3
MONO_PT = 7.0
H1_PT, H2_PT, H3_PT = 15.0, 11.5, 9.5

_FENCE = re.compile(r"^\s*```")
_ATX = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d+[.)])\s+(.*)$")
_RULE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_INLINE_CODE = re.compile(r"`([^`]*)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_TABLE_RULE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
# HTML comments in these sources are gate pragmas for check_forbidden.py, not
# content. The first preview printed "<!-- forbidden-ok: 신고보다 -->" in the
# middle of a judge-facing answer card: repository machinery on a handout.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font_codepoints(woff2: Path) -> set[int]:
    """Every codepoint the committed subset can actually draw."""
    f = TTFont(woff2)
    cps: set[int] = set()
    for table in f["cmap"].tables:
        cps |= set(table.cmap.keys())
    f.close()
    return cps


def woff2_to_ttf(woff2: Path, dest_dir: Path) -> Path:
    """Decompress a committed web font to a TTF matplotlib can embed.

    The TTF is a build intermediate written to a temporary directory. It is
    never committed: the woff2 in ``web/assets/fonts/`` stays the single copy
    (CHARTER §3.2), and this is the same "one copy plus a derivation" trade
    ``docs/finals_bundle.md`` argues for the bundle payload.
    """
    # recalcTimestamp=False: fontTools otherwise stamps head.modified with the
    # wall clock on save, which makes the TTF -- and therefore the subset
    # embedded in the PDF -- different on every build. Determinism here is what
    # lets tests/test_printables.py compare a rebuild instead of trusting it.
    font = TTFont(woff2, recalcTimestamp=False)
    font.flavor = None
    out = dest_dir / (woff2.stem + ".ttf")
    font.save(out)
    font.close()
    return out


def substitute(text: str) -> str:
    for src, dst in SUBSTITUTIONS.items():
        if src in text:
            text = text.replace(src, dst)
    return text


def strip_inline(text: str) -> str:
    """Markdown inline markup to plain text, keeping the words and dropping the syntax."""
    text = _IMAGE.sub(lambda m: f"[그림: {m.group(1) or m.group(2)}]", text)
    text = _LINK.sub(r"\1", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _BOLD.sub(r"\1", text)
    text = _ITALIC.sub(r"\1", text)
    # A bold span that OPENS on one line and closes on another survives both
    # regexes, because this parser works a line at a time. The first preview
    # showed six such lines printing their own asterisks on page 1 alone, which
    # on paper reads as a typo rather than as emphasis. Emphasis is dropped
    # here, not reconstructed: this renderer prints one weight of body text.
    return text.replace("**", "").replace("__", "")


class Block:
    """One laid-out thing: a heading, a body line, a rule, or a spacer."""

    __slots__ = ("kind", "text", "indent")

    def __init__(self, kind: str, text: str = "", indent: float = 0.0) -> None:
        self.kind = kind
        self.text = text
        self.indent = indent


def parse_markdown(md: str) -> list[Block]:
    blocks: list[Block] = []
    in_fence = False
    md = _HTML_COMMENT.sub("", md)
    for raw in md.splitlines():
        line = raw.rstrip()
        if _FENCE.match(line):
            in_fence = not in_fence
            blocks.append(Block("space"))
            continue
        if in_fence:
            blocks.append(Block("code", line))
            continue
        if not line.strip():
            blocks.append(Block("space"))
            continue
        if _RULE.match(line):
            blocks.append(Block("rule"))
            continue
        m = _ATX.match(line)
        if m:
            level = len(m.group(1))
            kind = "h1" if level == 1 else ("h2" if level == 2 else "h3")
            blocks.append(Block(kind, strip_inline(m.group(2))))
            continue
        if line.lstrip().startswith("|"):
            # Tables are kept verbatim in the mono face. Re-flowing a table into
            # proportional text is how a printed table stops lining up. Two
            # things are still removed: the |---|---| separator row, which is
            # Markdown scaffolding and prints as a row of dashes, and inline
            # markup inside the cells, which prints as literal asterisks.
            if _TABLE_RULE.match(line):
                continue
            blocks.append(Block("code", _INLINE_CODE.sub(r"\1", line)
                                .replace("**", "").replace("__", "")))
            continue
        if line.lstrip().startswith(">"):
            blocks.append(Block("quote", strip_inline(line.lstrip()[1:].strip()), 0.02))
            continue
        m = _BULLET.match(line)
        if m:
            depth = len(m.group(1)) // 2
            # U+00B7, not U+2022: the Sans KR subset carries the middle dot and
            # not the bullet. The renderer's own furniture goes through the same
            # coverage rule as the sources, because it is drawn on the same page.
            blocks.append(Block("body", "· " + strip_inline(m.group(3)), 0.018 + 0.018 * depth))
            continue
        m = _ORDERED.match(line)
        if m:
            depth = len(m.group(1)) // 2
            blocks.append(
                Block("body", f"{m.group(2)} " + strip_inline(m.group(3)), 0.018 + 0.018 * depth)
            )
            continue
        blocks.append(Block("body", strip_inline(line)))
    return blocks


class Renderer:
    def __init__(self, pdf: PdfPages, fonts: dict[str, FontProperties], stamp: str,
                 face_cps: dict[str, set[int]]) -> None:
        self.pdf = pdf
        self.fonts = fonts
        self.stamp = stamp
        self.face_cps = face_cps
        self.mono_cps = face_cps["mono"]
        self.mono_fallbacks = 0
        self.preview_dir: Path | None = None
        # Every character actually handed to a face, recorded as it is drawn.
        # The pre-flight gate reads the SOURCES; this reads the PAGE, and the
        # two disagree wherever the renderer adds furniture of its own or sends
        # text to a face the pre-flight did not consider. Both defects that got
        # past the first draft were in exactly that gap.
        self.drawn: dict[str, set[str]] = {"regular": set(), "semibold": set(), "mono": set()}
        self.fig = None
        self.y = 0.0
        self.page = 0
        self.section = ""
        self.pages_per_source: dict[str, int] = {}
        # One off-screen A4 figure and one renderer, reused for every width
        # measurement, so measuring never touches the page being drawn.
        self._mfig = plt.figure(figsize=(A4_W, A4_H))
        self._mrenderer = self._mfig.canvas.get_renderer()
        self._cache: dict[tuple[str, int, float], float] = {}

    def _char_width(self, ch: str, prop: FontProperties, size: float) -> float:
        """Advance width of one character, as a fraction of page width.

        Measured once per (character, face, size) and cached. The first draft
        measured whole candidate strings through ``canvas.draw()`` on every
        character of every line, which is one full figure rasterisation per
        character and did not finish a 60-page document in ten minutes. Line
        breaking needs advances, not kerned string extents, so summing cached
        per-character widths is both the fast answer and the right one; the
        error it ignores is sub-kerning and cannot move a break by a character.
        """
        key = (ch, id(prop), size)
        w = self._cache.get(key)
        if w is None:
            t = self._mfig.text(0, 0, ch, fontproperties=prop, fontsize=size)
            bbox = t.get_window_extent(self._mrenderer)
            t.remove()
            w = bbox.width / (self._mfig.get_figwidth() * self._mfig.dpi)
            self._cache[key] = w
        return w

    def _measure(self, text: str, prop: FontProperties, size: float) -> float:
        return sum(self._char_width(c, prop, size) for c in text)

    def _emit(self) -> None:
        self._footer()
        self.pdf.savefig(self.fig)
        if self.preview_dir is not None:
            self.fig.savefig(self.preview_dir / f"page_{self.page:03d}.png", dpi=110)
        plt.close(self.fig)

    def new_page(self) -> None:
        if self.fig is not None:
            self._emit()
        self.fig = plt.figure(figsize=(A4_W, A4_H))
        self.fig.patch.set_facecolor("white")
        self.y = MARGIN_T
        self.page += 1

    def _footer(self) -> None:
        left = substitute(f"WildfireGuardian · {self.section}")
        right = f"{self.stamp}  ·  p.{self.page}"
        self.drawn["regular"] |= set(left)
        self.drawn["mono"] |= set(right)
        self.fig.text(
            MARGIN_L, 0.030, left,
            fontproperties=self.fonts["regular"], fontsize=6.4, color="#555555",
        )
        self.fig.text(
            1 - MARGIN_R, 0.030, right,
            fontproperties=self.fonts["mono"], fontsize=6.4, color="#555555", ha="right",
        )
        self.fig.add_artist(
            plt.Line2D([MARGIN_L, 1 - MARGIN_R], [0.045, 0.045],
                       color="#cccccc", linewidth=0.6, transform=self.fig.transFigure)
        )

    def _room(self, need: float) -> None:
        if self.y - need < MARGIN_B + 0.030:
            self.new_page()

    def wrapped(self, text: str, prop: FontProperties, size: float, indent: float) -> list[str]:
        avail = 1 - MARGIN_L - MARGIN_R - indent
        # Korean does not use spaces the way the wrapper needs, so wrapping is
        # done character by character against measured width. Slower than a
        # word wrapper and correct on mixed Korean/Latin lines, which every one
        # of these documents is.
        lines: list[str] = []
        cur = ""
        for ch in text:
            trial = cur + ch
            if self._measure(trial, prop, size) > avail and cur:
                lines.append(cur)
                cur = ch.lstrip() if ch == " " else ch
            else:
                cur = trial
        lines.append(cur)
        return [ln for ln in lines if ln != ""] or [""]

    def draw(self, blocks: list[Block]) -> None:
        for b in blocks:
            if b.kind == "space":
                self.y -= LINE_H * 0.55
                continue
            if b.kind == "rule":
                self._room(LINE_H)
                self.fig.add_artist(
                    plt.Line2D([MARGIN_L, 1 - MARGIN_R], [self.y, self.y],
                               color="#dddddd", linewidth=0.6,
                               transform=self.fig.transFigure)
                )
                self.y -= LINE_H
                continue
            if b.kind == "h1":
                self.new_page()
                prop, size, gap = self.fonts["semibold"], H1_PT, LINE_H * 2.0
            elif b.kind == "h2":
                self._room(LINE_H * 4)
                self.y -= LINE_H * 0.9
                prop, size, gap = self.fonts["semibold"], H2_PT, LINE_H * 1.5
            elif b.kind == "h3":
                self._room(LINE_H * 3)
                self.y -= LINE_H * 0.5
                prop, size, gap = self.fonts["semibold"], H3_PT, LINE_H * 1.25
            elif b.kind == "code":
                # IBM Plex Mono carries 229 codepoints and no hangul at all, so a
                # Korean table row drawn in it is a row of blanks. Mono is used
                # only where it can draw every character; otherwise the line
                # falls back to the Sans face and the fallback is counted into
                # the manifest rather than happening quietly. Alignment is lost
                # on those rows, which is the lesser of the two damages.
                if all(ord(c) in self.mono_cps for c in substitute(b.text)):
                    prop, size, gap = self.fonts["mono"], MONO_PT, LINE_H * 0.92
                else:
                    self.mono_fallbacks += 1
                    prop, size, gap = self.fonts["regular"], MONO_PT, LINE_H * 0.92
            elif b.kind == "quote":
                prop, size, gap = self.fonts["regular"], BODY_PT, LINE_H
            else:
                prop, size, gap = self.fonts["regular"], BODY_PT, LINE_H

            text = substitute(b.text)
            if b.kind == "code":
                # Never re-wrap a code or table line: a wrapped table row is
                # worse than a clipped one, because it looks like data.
                pieces = [text]
            else:
                pieces = self.wrapped(text, prop, size, b.indent)
            face = next(k for k, v in self.fonts.items() if v is prop)
            for i, piece in enumerate(pieces):
                self.drawn[face] |= set(piece)
                self._room(gap)
                self.fig.text(
                    MARGIN_L + b.indent + (0.0 if i == 0 else 0.012), self.y, piece,
                    fontproperties=prop, fontsize=size, va="top",
                    color="#111111" if b.kind != "quote" else "#444444",
                )
                self.y -= gap

    def finish(self) -> None:
        if self.fig is not None:
            self._emit()
            self.fig = None

    def close(self) -> None:
        plt.close(self._mfig)

    def uncovered_drawn(self) -> dict[str, list[str]]:
        """What was actually put on a page that its face cannot draw.

        The pre-flight ``check_coverage`` reads the four source documents. This
        reads the layout. It is the gate that matters, because it is the only
        one that sees the renderer's own bullet marker and the face each line
        was finally assigned to.
        """
        bad: dict[str, list[str]] = {}
        for face, chars in self.drawn.items():
            missing = sorted(
                c for c in chars
                if c not in "\n\r\t" and ord(c) not in self.face_cps[face]
            )
            if missing:
                bad[face] = missing
        return bad


def check_coverage(texts: dict[str, str], cps: set[int]) -> dict[str, list[str]]:
    """Every character that will be drawn must exist in the committed font.

    Returns the uncovered characters per source. An empty dict is the only
    result that permits a build: a printable with a missing glyph is a sheet of
    paper with a hole in it, and nothing downstream would notice.
    """
    bad: dict[str, list[str]] = {}
    for name, text in texts.items():
        missing = sorted({
            ch for ch in substitute(text)
            if ch not in "\n\r\t" and ord(ch) not in cps
        })
        if missing:
            bad[name] = missing
    return bad


def build(stamp: str, out_dir: Path, preview_dir: Path | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cps = font_codepoints(REGULAR_WOFF2) & font_codepoints(SEMIBOLD_WOFF2)

    texts: dict[str, str] = {}
    for rel, _title in SOURCES:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"[printables] source missing: {rel}")
        texts[rel] = path.read_text(encoding="utf-8")

    uncovered = check_coverage(texts, cps)
    if uncovered:
        print("[printables] REFUSING TO BUILD - the committed font cannot draw:",
              file=sys.stderr)
        for name, chars in uncovered.items():
            listed = ", ".join(f"{c!r} U+{ord(c):04X}" for c in chars)
            print(f"  {name}: {listed}", file=sys.stderr)
        print("  Add each to SUBSTITUTIONS in scripts/build_printables.py, or "
              "remove it from the source. A missing glyph prints as a blank.",
              file=sys.stderr)
        raise SystemExit(2)

    pdf_path = out_dir / f"WFG_printables_{stamp}.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        fonts = {
            "regular": FontProperties(fname=str(woff2_to_ttf(REGULAR_WOFF2, tmpdir))),
            "semibold": FontProperties(fname=str(woff2_to_ttf(SEMIBOLD_WOFF2, tmpdir))),
            "mono": FontProperties(fname=str(woff2_to_ttf(MONO_WOFF2, tmpdir))),
        }
        # A fixed CreationDate makes two builds at the same stamp byte-identical,
        # which is what lets a test compare a rebuild instead of trusting it.
        meta = {
            "Title": f"WildfireGuardian 부스 인쇄물 {stamp}",
            "Author": "Siyeong Park",
            "Subject": "2026 한국코드페어 본선 부스 인쇄물",
            "Creator": "scripts/build_printables.py",
            "CreationDate": _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc),
        }
        face_cps = {
            "regular": font_codepoints(REGULAR_WOFF2),
            "semibold": font_codepoints(SEMIBOLD_WOFF2),
            "mono": font_codepoints(MONO_WOFF2),
        }
        # matplotlib reports a glyph it cannot draw as a UserWarning and then
        # draws a blank. On a booth handout that is the whole failure, so the
        # warning is promoted to an exception for the duration of the build:
        # belt and braces beside the two static checks, and the only one of the
        # three that cannot be out of date with respect to the renderer.
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message=r".*missing from font.*")
            with PdfPages(pdf_path, metadata=meta) as pdf:
                r = Renderer(pdf, fonts, stamp, face_cps)
                r.preview_dir = preview_dir
                for rel, title in SOURCES:
                    r.section = title
                    start = r.page
                    blocks = parse_markdown(texts[rel])
                    if not blocks or blocks[0].kind != "h1":
                        blocks.insert(0, Block("h1", title))
                    r.draw(blocks)
                    r.pages_per_source[rel] = r.page - start + 1
                r.finish()
                pages = r.page
                r.close()

        drawn_bad = r.uncovered_drawn()
        if drawn_bad:
            pdf_path.unlink(missing_ok=True)
            print("[printables] REFUSING - characters reached a face that cannot "
                  "draw them:", file=sys.stderr)
            for face, chars in drawn_bad.items():
                listed = ", ".join(f"{c!r} U+{ord(c):04X}" for c in chars)
                print(f"  {face}: {listed}", file=sys.stderr)
            raise SystemExit(2)

    manifest = {
        "built_by": "scripts/build_printables.py",
        "stamp": stamp,
        "pdf": pdf_path.name,
        "pdf_sha256": sha256(pdf_path),
        "pages": pages,
        "pages_per_source": r.pages_per_source,
        "sources": [
            {"path": rel, "title": title, "sha256": sha256(ROOT / rel)}
            for rel, title in SOURCES
        ],
        "fonts": [
            {"path": str(p.relative_to(ROOT)), "sha256": sha256(p)}
            for p in (REGULAR_WOFF2, SEMIBOLD_WOFF2, MONO_WOFF2)
        ],
        "font_codepoints": len(cps),
        "mono_fallback_lines": r.mono_fallbacks,
        "substitutions": {k: v for k, v in sorted(SUBSTITUTIONS.items())},
        "what_this_does_not_show": (
            "The PDF is a print rendering of four committed Markdown documents and "
            "adds no number, no claim and no source of its own. Every figure in it "
            "is whatever those documents say on the sha256 recorded above; if a "
            "document changes, this PDF is stale until a new stamp is built beside "
            "it. It is not a substitute for the screens: no map, no route and no "
            "figure is rendered here. The A4 evidence sheet (WFG-018), the "
            "related-work table (WFG-026) and the 29 dispatch sheets in "
            "outputs/dispatch are NOT in this file; the first two do not exist yet "
            "and the third is already a set of committed PDFs that print directly."
        ),
    }
    (out_dir / f"manifest_{stamp}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stamp", default=_dt.datetime.now(_dt.timezone.utc)
                    .strftime("%Y%m%dT%H%MZ"),
                    help="UTC stamp for the output filenames; never reuse one")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--preview", type=Path, default=None,
                    help="also write every page as a PNG here, to look at "
                         "before printing; PNGs are build output, not committed")
    ap.add_argument("--check-only", action="store_true",
                    help="run the font-coverage gate and exit without drawing")
    args = ap.parse_args()

    if args.check_only:
        cps = font_codepoints(REGULAR_WOFF2) & font_codepoints(SEMIBOLD_WOFF2)
        texts = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel, _ in SOURCES}
        bad = check_coverage(texts, cps)
        if bad:
            for name, chars in bad.items():
                print(f"{name}: " + ", ".join(f"{c!r} U+{ord(c):04X}" for c in chars))
            return 2
        print(f"[printables] coverage OK: {len(SOURCES)} sources, {len(cps)} codepoints")
        return 0

    if args.preview is not None:
        args.preview.mkdir(parents=True, exist_ok=True)
    m = build(args.stamp, args.out_dir, args.preview)
    print(f"[printables] {m['pdf']}  {m['pages']} pages  sha256={m['pdf_sha256'][:12]}")
    for rel, n in m["pages_per_source"].items():
        print(f"             {n:>3} p  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
