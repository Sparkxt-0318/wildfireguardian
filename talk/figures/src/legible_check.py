"""Legibility check for talk/figures/kcf_legible/ (DECISIONS.md D48).

For each figure: scale its PNG to its slot (slide pixels), take every text item from its layout JSON, and compute the
text's size on the slide:
    font_px = size_pt / 72 * png_dpi * (slot_width / png_width)
    cap_px  = font_px * cap-height ratio of the font that draws it (read from the font file's OS/2 sCapHeight:
              Helvetica Neue for text, STIX for text containing mathtext, the more conservative of the two)
Rule: cap_px >= 22 for every text; axis tick labels instead need font_px >= 24.
Fails (exit 1) if any text is under its limit, if the PNG is not 2x its slot, or if the figure's collision check failed.
Writes kcf_legible/LEGIBILITY.md and prints the smallest text per figure.
"""
import json
import sys

import matplotlib.font_manager as fm
from PIL import Image

import legible as G
import style as S

CAP_MIN, TICK_MIN = 22.0, 24.0


def cap_ratio(family):
    p = fm.fontManager._find_fonts_by_props(fm.FontProperties(family=family))[0]
    f = fm.get_font([p])
    return f.get_sfnt_table("OS/2")["sCapHeight"] / f.units_per_EM, f.family_name


def main():
    r_text, n_text = cap_ratio(S.FONT_LATIN)
    r_math, n_math = cap_ratio("STIXGeneral")
    rows, fails = [], []
    for name, (sw, sh) in G.SLOTS.items():
        png = G.OUT / f"{name}.png"
        lay = G.LAYOUT / f"{name}.json"
        if not png.exists() or not lay.exists():
            fails.append(f"{name}: not built")
            rows.append((name, None, None, None, "not built"))
            continue
        L = json.loads(lay.read_text())
        pw, ph = Image.open(png).size
        if (pw, ph) != (2 * sw, 2 * sh):
            fails.append(f"{name}: PNG {pw}x{ph}, expected {2 * sw}x{2 * sh}")
        scale = sw / pw
        worst_cap, worst_tick, bad = None, None, []
        for t in L["texts"]:
            font_px = t["size_pt"] / 72 * L["dpi"] * scale
            if t["tick"]:
                if worst_tick is None or font_px < worst_tick[0]:
                    worst_tick = (font_px, t["text"])
                if font_px < TICK_MIN - 1e-6:
                    bad.append(f"tick '{t['text']}' font {font_px:.1f} px")
            else:
                cap = font_px * (r_math if t["math"] else r_text)
                if worst_cap is None or cap < worst_cap[0]:
                    worst_cap = (cap, t["text"])
                if cap < CAP_MIN - 1e-6:
                    bad.append(f"'{t['text'][:40]}' cap {cap:.1f} px")
        if L["collisions"]:
            bad.append(f"{len(L['collisions'])} collisions")
        fails += [f"{name}: {b}" for b in bad]
        rows.append((name, (sw, sh), worst_cap, worst_tick, "PASS" if not bad else "FAIL"))
    lines = ["# Legibility check", "",
             f"Each PNG scaled to its slot (slide px). Text: cap height >= {CAP_MIN:g} px "
             f"({n_text} cap height {r_text:.3f} em; text with mathtext measured with {n_math}, {r_math:.3f} em). "
             f"Axis tick labels: font size >= {TICK_MIN:g} px. Sizes from the layout JSON of each figure "
             "(`layout/<name>.json`), every text item.", "",
             "| figure | slot (px) | smallest text (cap height, slide px) | smallest tick label (font size, slide px) | result |",
             "|---|---|---|---|---|"]
    for name, slot, wc, wt, res in rows:
        q = lambda t, n: t[:n].replace("\n", " ").replace("|", "\\|")  # noqa: E731
        lines.append(f"| {name} | {slot[0]} x {slot[1] if slot else ''} | "
                     f"{f'{wc[0]:.1f} (“{q(wc[1], 30)}”)' if wc else '–'} | "
                     f"{f'{wt[0]:.1f} (“{q(wt[1], 20)}”)' if wt else 'none'} | {res} |" if slot else
                     f"| {name} | | | | {res} |")
    (G.OUT / "LEGIBILITY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if fails:
        print("\nFAIL:\n  " + "\n  ".join(fails))
        sys.exit(1)
    print("\nPASS")


if __name__ == "__main__":
    main()
