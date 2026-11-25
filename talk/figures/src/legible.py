"""Shared layout for the legible slide figures in talk/figures/kcf_legible/ (DECISIONS.md D48).

Each figure has a slot on a 1920 x 1080 slide (SLOTS, slide pixels). The canvas is the slot at 100 slide px per inch,
so a font of s pt is s * 100 / 72 slide px; the PNG is written at 200 dpi, twice the slot. Text sizes:
  BODY 23 pt  -> 31.9 px font, Helvetica Neue cap height (0.714 em) 22.8 px   (limit: cap >= 22 px)
  MATH 24 pt  -> 33.3 px font, STIX cap height (0.662 em) 22.1 px, for labels with mathtext
  TICK 18 pt  -> 25.0 px font (limit for axis tick labels: font >= 24 px)
The numbers come from the original figure scripts' readers, unchanged; only layout and text size differ.
"""
import json
import re

import matplotlib.pyplot as plt

import style as S
from figkit import check_collisions

OUT = S.FIGDIR / "kcf_legible"
LAYOUT = OUT / "layout"
SLOTS = {
    "F04a_overview_forecast": (1700, 620),
    "F04b_overview_roads": (1700, 620),
    "F07_map": (1700, 640),
    "F08_map": (760, 600),
    "F12_forecast_maps": (900, 520),
    "F14_reliability": (760, 600),
    "F09_speed": (1100, 560),
    "F10_camp_fire": (1212, 560),
}
PXI = 100           # slide px per canvas inch
DPI_OUT = 2 * PXI   # PNG at twice the slot
BODY, MATH, TICK = 23, 24, 18


def setup():
    S.PT_TEXT = BODY      # realmap's labels, scale bar and attribution read this at call time
    plt.rcParams.update({
        "font.size": BODY, "axes.labelsize": BODY, "axes.titlesize": BODY, "legend.fontsize": BODY,
        "xtick.labelsize": TICK, "ytick.labelsize": TICK, "axes.linewidth": 1.0, "lines.linewidth": 2.0,
        "xtick.major.width": 1.0, "ytick.major.width": 1.0, "xtick.major.size": 6, "ytick.major.size": 6,
        "xtick.major.pad": 6, "ytick.major.pad": 6, "axes.labelpad": 10, "hatch.linewidth": 1.0,
    })


def figure(name):
    setup()
    w, h = SLOTS[name]
    fig = plt.figure(figsize=(w / PXI, h / PXI), dpi=DPI_OUT)
    fig._wh = (w / PXI, h / PXI)
    return fig


def ax_in(fig, x, y, w, h, **kw):
    """Axes from inches, origin at the top-left corner."""
    W, H = fig._wh
    return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], **kw)


def text_in(fig, x, y, s, **kw):
    W, H = fig._wh
    kw.setdefault("va", "center")
    if "$" in s:
        kw.setdefault("fontsize", MATH)
    return fig.text(x / W, 1 - y / H, s, **kw)


def strip(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(1.0)
        sp.set_color(S.INK)


def _tick_texts(fig):
    out = set()
    for ax in fig.axes:
        out |= set(ax.get_xticklabels()) | set(ax.get_yticklabels())
        out |= set(ax.xaxis.get_offset_text() for _ in [0]) | set(ax.yaxis.get_offset_text() for _ in [0])
    return out


def visible_texts(fig):
    out = []
    for t in fig.findobj(plt.Text):
        if not t.get_visible() or not t.get_text().strip():
            continue
        if t.axes is not None and not t.axes.get_visible():
            continue
        out.append(t)
    return out


def save(fig, name, allow_pairs=(), notes=()):
    """Collision check (figkit rules), PNG at 2x slot, layout JSON with every text item for legible_check.py."""
    OUT.mkdir(exist_ok=True)
    LAYOUT.mkdir(exist_ok=True)
    import figkit
    old = figkit.DPI
    figkit.DPI = DPI_OUT          # figkit's padding is in points at its own dpi; use this figure's dpi
    try:
        probs = check_collisions(fig, allow_pairs)
    finally:
        figkit.DPI = old
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    ticks = _tick_texts(fig)
    W, H = fig._wh
    sw, sh = SLOTS[name]
    texts = []
    for t in visible_texts(fig):
        bb = t.get_window_extent(r)
        k = sw / (W * DPI_OUT)            # canvas px -> slide px
        texts.append({"text": t.get_text(), "size_pt": t.get_fontproperties().get_size_in_points(),
                      "tick": t in ticks, "math": bool(re.search(r"\$[^$]+\$", t.get_text())),
                      "family": t.get_fontproperties().get_family(),
                      "box_slot_px": [round(bb.x0 * k, 1), round((H * DPI_OUT - bb.y1) * k, 1),
                                      round(bb.width * k, 1), round(bb.height * k, 1)]})
    fig.savefig(OUT / f"{name}.png", dpi=DPI_OUT, transparent=True)
    (LAYOUT / f"{name}.json").write_text(json.dumps(
        {"name": name, "slot_px": [sw, sh], "canvas_in": [W, H], "dpi": DPI_OUT, "px_per_in_in_slot": PXI,
         "collisions": probs, "notes": list(notes), "texts": texts}, indent=1, ensure_ascii=False))
    print(f"{name}: collision check {'PASS' if not probs else 'FAIL'}; {len(texts)} texts")
    for p in probs[:20]:
        print("   ", p)
    if probs:
        raise SystemExit(f"{name}: text collides")
