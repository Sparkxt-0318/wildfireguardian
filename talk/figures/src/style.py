"""One place for the palette, fonts and sizes used by every talk figure.

Change a colour here and re-run make_all.sh; every figure and the PowerPoint file follow.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ---------------------------------------------------------------- paths
SRC = Path(__file__).resolve().parent
FIGDIR = SRC.parent                       # talk/figures
REPO = FIGDIR.parent.parent               # repository root (worktree)
BUILD = FIGDIR / "build"                  # layout manifests read by build_pptx.py
CHECK = FIGDIR / "check"                  # greyscale and overlap reports
for _d in (BUILD, CHECK):
    _d.mkdir(exist_ok=True)

# ---------------------------------------------------------------- canvas
W_IN, H_IN = 13.333, 7.5                  # 16:9 slide
PNG_WIDTH_PX = 3840
DPI = PNG_WIDTH_PX / W_IN                 # 288 dpi

# ---------------------------------------------------------------- palette (fixed meanings)
INK = "#1A1A1A"        # text, axes
MID = "#8C8C8C"        # earlier method, baselines, roads
LIGHT = "#D9D9D9"      # context; hatched for withheld or unknown
OURS = "#2F5D8A"       # our method (deep blue)
FIRE = "#B5483A"       # fire and closed (muted brick red)
SAFE = "#3B8F8A"       # safe and open (teal)
COST = "#C9A227"       # caution or cost (ochre)
TINT_FORECAST = "#F6EBD0"
TINT_ROUTING = "#F3DAD6"
TINT_OUTPUT = "#DDE7F2"
TINT_DATA = "#E4EEDF"
WHITE = "#FFFFFF"
CONTINUOUS_CMAP = "cividis"               # continuous quantities on maps

PALETTE = [
    ("ink", INK, "text, axes"),
    ("mid grey", MID, "earlier method, baselines, roads"),
    ("light grey", LIGHT, "context; hatched = withheld or unknown"),
    ("deep blue", OURS, "our method"),
    ("brick red", FIRE, "fire and closed"),
    ("teal", SAFE, "safe and open"),
    ("ochre", COST, "caution or cost"),
    ("forecast tint", TINT_FORECAST, "schematic module: forecast"),
    ("routing tint", TINT_ROUTING, "schematic module: routing"),
    ("outputs tint", TINT_OUTPUT, "schematic module: outputs"),
    ("data tint", TINT_DATA, "schematic module: data"),
]

# ---------------------------------------------------------------- type
# Research-paper style (24 Nov 13:35 revision): one size for labels and tick labels, one slightly larger size for
# axis titles, nothing larger. No bold or coloured callout text.
FONT_LATIN = "Helvetica Neue"   # Inter is not installed on this machine (DECISIONS.md D2)
FONT_KOREAN = "NanumGothic"     # fallback for Hangul glyphs
FONT_FAMILY = [FONT_LATIN, FONT_KOREAN]
PT_TEXT = 16          # labels, tick labels, legend, captions (at least 14 pt)
PT_TITLE = 18         # axis titles
PT_MIN = PT_TEXT      # kept for older scripts
PT_BODY = PT_TEXT
PT_LABEL = PT_TITLE
GRID = "#E3E3E3"

LW_AXIS = 0.8
LW_DATA = 1.5
LW_THIN = 0.75        # schematic outlines
TICK_PAD = 6
LABEL_PAD = 12

# canvas regions (inches from the top-left corner)
CAPTION_TOP = 6.45    # captions start here; the graphic ends above it
CAPTION_BOTTOM = 7.38


def apply():
    plt.rcParams.update({
        "font.family": FONT_FAMILY,
        "font.size": PT_TEXT,
        "mathtext.fontset": "stix",
        "text.color": INK,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.linewidth": LW_AXIS,
        "axes.spines.top": True,
        "axes.spines.right": True,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.labelsize": PT_TITLE,
        "axes.labelpad": LABEL_PAD,
        "axes.titlesize": PT_TITLE,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.labelsize": PT_TEXT,
        "ytick.labelsize": PT_TEXT,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.width": LW_AXIS,
        "ytick.major.width": LW_AXIS,
        "xtick.major.size": 4,
        "ytick.major.size": 4,
        "xtick.minor.size": 2.5,
        "ytick.minor.size": 2.5,
        "xtick.major.pad": TICK_PAD,
        "ytick.major.pad": TICK_PAD,
        "lines.linewidth": LW_DATA,
        "figure.facecolor": WHITE,
        "axes.facecolor": WHITE,
        "savefig.facecolor": WHITE,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "hatch.color": INK,
        "hatch.linewidth": 0.6,
        "legend.frameon": True,
        "legend.fancybox": False,
        "legend.edgecolor": INK,
        "legend.framealpha": 1.0,
        "legend.fontsize": PT_TEXT,
        "legend.borderpad": 0.5,
        "patch.linewidth": LW_THIN,
        "errorbar.capsize": 3,
    })


apply()


def panel_letter(fig, x_in, y_in, letter):
    """(a), (b), ... at the top left of a panel."""
    return fig.text(x_in / W_IN, 1 - y_in / H_IN, f"({letter})", fontsize=PT_TEXT, va="center", ha="left")


def new_figure():
    """A 13.333 x 7.5 in white canvas."""
    return plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
