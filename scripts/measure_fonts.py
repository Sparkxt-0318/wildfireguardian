#!/usr/bin/env python
"""Measure the two font candidates on the two things that decide the choice.

Round-3 PHASE 21 STEP 1.

WHY MEASURE RATHER THAN PREFER
------------------------------
A situation-room screen is dense and is read from a distance, so the font
question is not "which has more character" but two answerable ones:

1. **Does a glyph in a numeric column break the alignment?**
   ``font-variant-numeric: tabular-nums`` only promises that DIGITS share an
   advance width. It says nothing about an arrow, a tilde or a dash sitting
   beside them. So the advance widths are read straight out of ``hmtx`` and
   compared to the digit width — the EM dash ban is an empirical claim and this
   is where it is either confirmed or withdrawn.

2. **Is Hangul legible at 13 px?**
   Approximated by the metrics that govern small-size legibility: units per em,
   x-height and cap height as a fraction of em (taller x-height reads larger at
   the same nominal size), and the ink density of a representative Hangul
   syllable — a syllable with many strokes in a fixed em box is what fails
   first when the size drops.

⚠ WHAT THIS CANNOT TELL YOU
Metrics are not eyes. They rank candidates and they catch disqualifiers; they
do not settle a close call. Where the numbers are close the report says so
rather than manufacturing a winner, and a rendered PNG is written so the
comparison can also be looked at.

Run:
    python scripts/measure_fonts.py --dir <font dir> --out <json>
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: The glyphs a numeric column might contain, beside the digits themselves.
PROBE_CHARS: dict[str, str] = {
    "digit zero": "0",
    "digit one": "1",
    "digit eight": "8",
    "EM dash": "—",
    "EN dash": "–",
    "hyphen-minus": "-",
    "rightwards arrow": "→",
    "tilde": "~",
    "middle dot": "·",
    "solidus": "/",
    "full stop": ".",
    "space": " ",
}

#: Hangul syllables spanning the stroke-density range, from the simplest to one
#: of the busiest in ordinary operational text. The dense ones are what decide
#: whether 13 px is honest.
HANGUL_PROBES: tuple[str, ...] = ("이", "고", "산", "불", "칠", "될", "뚫", "쫓")

#: Words this screen actually prints, for the rendered comparison.
HANGUL_SAMPLE = "자력 대피 414 · 구조 필요 42 · 도달 불가 2"


def load_font(path: Path):
    from fontTools.ttLib import TTFont
    return TTFont(str(path), lazy=False)


def glyph_for(font, ch: str) -> str | None:
    for table in font["cmap"].tables:
        if table.isUnicode():
            g = table.cmap.get(ord(ch))
            if g:
                return g
    return None


def advance(font, ch: str) -> int | None:
    g = glyph_for(font, ch)
    if g is None:
        return None
    hmtx = font["hmtx"]
    return hmtx[g][0] if g in hmtx.metrics else None


def ink_box(font, ch: str) -> tuple[int, int] | None:
    """(width, height) of the glyph's bounding box, in font units."""
    g = glyph_for(font, ch)
    if g is None:
        return None
    try:
        glyf = font["glyf"][g]
        if glyf.numberOfContours == 0:
            return (0, 0)
        return (glyf.xMax - glyf.xMin, glyf.yMax - glyf.yMin)
    except Exception:  # noqa: BLE001 — CFF fonts have no glyf table
        from fontTools.pens.boundsPen import BoundsPen
        pen = BoundsPen(font.getGlyphSet())
        font.getGlyphSet()[g].draw(pen)
        if pen.bounds is None:
            return (0, 0)
        x0, y0, x1, y1 = pen.bounds
        return (int(x1 - x0), int(y1 - y0))


def measure(path: Path) -> dict:
    font = load_font(path)
    upem = font["head"].unitsPerEm
    os2 = font["OS/2"] if "OS/2" in font else None
    sx = getattr(os2, "sxHeight", None) if os2 else None
    scap = getattr(os2, "sCapHeight", None) if os2 else None

    widths = {}
    for name, ch in PROBE_CHARS.items():
        a = advance(font, ch)
        widths[name] = {
            "char": ch, "codepoint": f"U+{ord(ch):04X}",
            "present": a is not None,
            "advance_units": a,
            "advance_em": (None if a is None else round(a / upem, 4)),
        }

    digit_ws = {k: v["advance_units"] for k, v in widths.items()
                if k.startswith("digit") and v["advance_units"] is not None}
    digit_w = next(iter(digit_ws.values())) if digit_ws else None
    digits_uniform = len(set(digit_ws.values())) == 1 if digit_ws else False

    for name, v in widths.items():
        a = v["advance_units"]
        v["vs_digit"] = (None if (a is None or not digit_w)
                         else round(a / digit_w, 3))
        v["same_as_digit"] = (a == digit_w) if a is not None else None

    hangul = {}
    for ch in HANGUL_PROBES:
        a, box = advance(font, ch), ink_box(font, ch)
        hangul[ch] = {
            "present": a is not None,
            "advance_units": a,
            "ink_w": None if box is None else box[0],
            "ink_h": None if box is None else box[1],
            # Ink height as a fraction of em is what survives a size drop.
            "ink_h_em": (None if box is None else round(box[1] / upem, 4)),
        }
    present = [h for h in hangul.values() if h["present"] and h["ink_h"]]
    mean_ink_h_em = (round(sum(h["ink_h_em"] for h in present) / len(present), 4)
                     if present else None)

    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "kib": round(path.stat().st_size / 1024, 1),
        "units_per_em": upem,
        "x_height_units": sx,
        "x_height_em": (None if sx is None else round(sx / upem, 4)),
        "cap_height_units": scap,
        "cap_height_em": (None if scap is None else round(scap / upem, 4)),
        # At 13 px, how many device pixels does the x-height get? Below about
        # 6 px lowercase Latin starts to mush; Hangul needs more.
        "x_height_px_at_13": (None if sx is None else round(13 * sx / upem, 2)),
        "n_glyphs": len(font.getGlyphOrder()),
        "digits_uniform_width": digits_uniform,
        "digit_advance_units": digit_w,
        "widths": widths,
        "hangul": hangul,
        "hangul_present": sum(1 for h in hangul.values() if h["present"]),
        "hangul_probes": len(HANGUL_PROBES),
        "mean_hangul_ink_h_em": mean_ink_h_em,
        "hangul_ink_px_at_13": (None if mean_ink_h_em is None
                                else round(13 * mean_ink_h_em, 2)),
    }


def verdict(rows: list[dict]) -> dict:
    """What the numbers do and do not settle."""
    notes: list[str] = []
    for r in rows:
        w = r["widths"]
        if not r["digits_uniform_width"]:
            notes.append(
                f"{r['file']}: digits do NOT share an advance width by default; "
                "the screen must set font-variant-numeric: tabular-nums and it "
                "must be verified in the browser, not assumed.")
        for key in ("rightwards arrow", "tilde", "EM dash", "EN dash"):
            v = w[key]
            if not v["present"]:
                notes.append(f"{r['file']}: {key} ({v['codepoint']}) is ABSENT "
                             "— it would render as tofu or fall back to another "
                             "face mid-line.")
            elif v["vs_digit"] is not None and abs(v["vs_digit"] - 1.0) > 0.02:
                notes.append(
                    f"{r['file']}: {key} is {v['vs_digit']}x a digit's width, "
                    "so putting it INSIDE a numeric column shifts that row.")
    return {
        "notes": notes,
        "rule": "A glyph whose advance differs from a digit's is safe in PROSE "
                "and unsafe INSIDE a tabular-nums column. Splitting the column "
                "(Before / After) avoids the question entirely, which is why "
                "that is the table rule regardless of what these numbers say.",
        "not_settled_by_metrics": [
            "Which face is more legible at 13 px when actually rendered and "
            "actually looked at. Metrics rank; they do not adjudicate a close "
            "call.",
            "Hinting and rasterisation differences between platforms.",
        ],
    }


def render_sample(paths: list[Path], out_png: Path, size_px: int = 13) -> str:
    """Render the same Hangul string in each face, for looking at."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # noqa: BLE001
        return f"not rendered: {type(exc).__name__}"
    usable = [p for p in paths if p.suffix.lower() in (".ttf", ".otf")]
    if not usable:
        return ("not rendered: PIL cannot open woff2; a ttf/otf is needed for "
                "the visual comparison")
    scale, pad = 3, 12
    img = Image.new("RGB", (900, pad * 2 + len(usable) * 2 * size_px * scale),
                    "#0b0f14")
    d = ImageDraw.Draw(img)
    y = pad
    for p in usable:
        for sz in (size_px, size_px * 2):
            f = ImageFont.truetype(str(p), sz * scale)
            d.text((pad, y), f"{p.stem} {sz}px: {HANGUL_SAMPLE}",
                   font=f, fill="#e8edf2")
            y += int(sz * scale * 1.6)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return str(out_png)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--png", type=Path, default=None)
    args = ap.parse_args()

    files = sorted(p for p in args.dir.iterdir()
                   if p.suffix.lower() in (".woff2", ".woff", ".ttf", ".otf"))
    if not files:
        ap.error(f"no font files in {args.dir}")

    rows = [measure(p) for p in files]
    doc = {"schema_version": 1, "fonts": rows, "verdict": verdict(rows),
           "probe_chars": {k: f"U+{ord(v):04X}" for k, v in PROBE_CHARS.items()},
           "hangul_probes": list(HANGUL_PROBES)}
    if args.png:
        doc["rendered"] = render_sample(files, args.png)

    print("=" * 96)
    print("  글꼴 실측 — 숫자 열 안전성과 13px 한글")
    print("=" * 96)
    for r in rows:
        print(f"\n  {r['file']}  ({r['kib']} KiB, {r['n_glyphs']:,} glyphs, "
              f"upem {r['units_per_em']})")
        print(f"    x-height {r['x_height_em']} em -> {r['x_height_px_at_13']} px at 13px"
              f"   ·  cap {r['cap_height_em']} em")
        print(f"    한글 {r['hangul_present']}/{r['hangul_probes']}자 있음"
              f"   ·  평균 잉크 높이 {r['mean_hangul_ink_h_em']} em"
              f" -> {r['hangul_ink_px_at_13']} px at 13px")
        print(f"    숫자 등폭: {r['digits_uniform_width']}"
              f"  (digit advance {r['digit_advance_units']})")
        for key in ("rightwards arrow", "tilde", "EM dash", "EN dash",
                    "middle dot", "solidus"):
            v = r["widths"][key]
            if not v["present"]:
                print(f"      {key:20s} {v['codepoint']}  ABSENT")
            else:
                flag = "= digit" if v["same_as_digit"] else f"{v['vs_digit']}x digit"
                print(f"      {key:20s} {v['codepoint']}  {v['advance_units']:5d} u   {flag}")
    print("\n  판정에 쓸 수 있는 것:")
    for n in doc["verdict"]["notes"]:
        print(f"    ⚠ {n}")
    print("\n  이 수치로 정할 수 없는 것:")
    for n in doc["verdict"]["not_settled_by_metrics"]:
        print(f"    · {n}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        print(f"\n  기록: {args.out}")
    _ = unicodedata
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
