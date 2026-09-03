"""One figure style for the manuscript. Every figure script imports `apply()`.

Colour-blind-safe palette (Okabe-Ito), 300 dpi, a single sans family with real
fallbacks, tabular digits, no chart junk. Sizes are in inches for a single
column (3.4) or full width (7.0) of an IEEE two-column page; the .docx is
single-column, so most figures use FULL.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FULL = (7.0, 3.6)
TALL = (7.0, 4.6)
COL = (3.4, 2.6)

OKABE = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "vermilion": "#D55E00",
         "purple": "#CC79A7", "sky": "#56B4E9", "yellow": "#F0E442", "black": "#000000", "grey": "#7F7F7F"}
INK, MUTED, LINE = "#1B1F23", "#5B5F66", "#C9CCD1"


def apply() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.04,
        "font.family": "sans-serif",
        "font.sans-serif": ["Source Sans 3", "Source Sans Pro", "DejaVu Sans", "Helvetica", "Arial"],
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 8, "legend.frameon": False,
        "axes.edgecolor": LINE, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": LINE, "grid.linewidth": 0.5, "grid.alpha": 0.7, "axes.axisbelow": True,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK, "text.color": INK,
        "axes.prop_cycle": matplotlib.cycler(color=[OKABE["blue"], OKABE["orange"], OKABE["green"], OKABE["vermilion"], OKABE["purple"], OKABE["sky"]]),
        "axes.formatter.use_mathtext": True,
    })


def finish(fig, out, caption_note: str | None = None) -> None:
    """Save at 300 dpi. No suptitles: captions live in the manuscript."""
    fig.savefig(out, facecolor="white")
    plt.close(fig)
