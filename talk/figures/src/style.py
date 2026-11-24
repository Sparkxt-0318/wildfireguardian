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
FONT_LATIN = "Helvetica Neue"   # Inter is not installed on this machine (DECISIONS.md D2)
FONT_KOREAN = "NanumGothic"     # fallback for Hangul glyphs
FONT_FAMILY = [FONT_LATIN, FONT_KOREAN]
PT_MIN = 16           # no text smaller than this at canvas size
PT_BODY = 18
PT_LABEL = 20
PT_KEY = 32           # key numbers 28 to 40 pt
PT_KEY_BIG = 40

LW_AXIS = 1.0
LW_DATA = 2.0
LW_THIN = 0.8
TICK_PAD = 9          # pt between tick and its label
LABEL_PAD = 10


def apply():
    plt.rcParams.update({
        "font.family": FONT_FAMILY,
        "font.size": PT_BODY,
        "text.color": INK,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.linewidth": LW_AXIS,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.labelsize": PT_LABEL,
        "axes.labelpad": LABEL_PAD,
        "axes.titlesize": PT_LABEL,
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.labelsize": PT_BODY,
        "ytick.labelsize": PT_BODY,
        "xtick.major.width": LW_AXIS,
        "ytick.major.width": LW_AXIS,
        "xtick.major.size": 5,
        "ytick.major.size": 5,
        "xtick.minor.size": 3,
        "ytick.minor.size": 3,
        "xtick.major.pad": TICK_PAD,
        "ytick.major.pad": TICK_PAD,
        "lines.linewidth": LW_DATA,
        "figure.facecolor": WHITE,
        "axes.facecolor": WHITE,
        "savefig.facecolor": WHITE,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "hatch.color": MID,
        "hatch.linewidth": 1.0,
        "legend.frameon": False,
    })


apply()


def new_figure():
    """A 13.333 x 7.5 in white canvas."""
    return plt.figure(figsize=(W_IN, H_IN), dpi=DPI)
