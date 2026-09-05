"""One figure style for the manuscript. Every figure script imports `apply()`.

The look follows Moreno et al. (2025), which the author chose as the reference on
2026-09-04 (docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md): every panel in a thin
black frame, panel letters inside the frame, bars with a hairline edge and their
values written inside, framed legends inside the panel, a small warm palette (fire
red, steel blue, neutral grey), a yellow-to-red sequential map for probability
fields. 300 dpi, one sans family with real fallbacks, no chart junk. Sizes are in
inches for a single column (3.4) or full width (7.0) of an IEEE two-column page;
the .docx is single-column, so most figures use FULL.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FULL = (7.0, 3.6)
TALL = (7.0, 4.6)
COL = (3.4, 2.6)

# Moreno-style palette. Red is fire / presence / the arm we argue for; blue the
# second arm; grey absences and controls; the rest are extra categories.
PALETTE = {
    "fire": "#E0402A", "blue": "#3A82D2", "grey": "#9A9A9A", "mauve": "#C7B3C3",
    "teal": "#3E9E88", "brown": "#B0641E", "slate": "#5E5E88", "sky": "#7FB3E6",
    "yellow": "#F2C744", "black": "#000000",
}
# Legacy names used by older figure code; they now resolve to the palette above.
OKABE = {"blue": PALETTE["blue"], "orange": PALETTE["brown"], "green": PALETTE["teal"],
         "vermilion": PALETTE["fire"], "purple": PALETTE["slate"], "sky": PALETTE["sky"],
         "yellow": PALETTE["yellow"], "black": PALETTE["black"], "grey": PALETTE["grey"]}
INK, MUTED, LINE = "#111111", "#555555", "#BFBFBF"
SEQ_CMAP = "YlOrRd"                                        # probability fields
EXCEEDANCE = ["#3E8E86", "#A9D9D1", "#E9C9A4", "#A85E27"]  # teal -> brown, four classes


def apply() -> None:
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.04,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "Source Sans 3", "Source Sans Pro", "DejaVu Sans"],
        "font.size": 9, "axes.titlesize": 9, "axes.titleweight": "normal", "axes.titlelocation": "center",
        "axes.titlepad": 4, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
        # framed panels
        "axes.edgecolor": INK, "axes.linewidth": 0.6,
        "axes.spines.top": True, "axes.spines.right": True, "axes.spines.left": True, "axes.spines.bottom": True,
        "axes.grid": False, "grid.color": LINE, "grid.linewidth": 0.5, "grid.alpha": 0.8, "axes.axisbelow": True,
        "xtick.color": INK, "ytick.color": INK, "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 3, "ytick.major.size": 3,
        "axes.labelcolor": INK, "text.color": INK,
        # bars with a hairline edge
        "patch.force_edgecolor": True, "patch.edgecolor": INK, "patch.linewidth": 0.5,
        # framed legends inside the panel
        "legend.fontsize": 7.5, "legend.frameon": True, "legend.fancybox": False, "legend.edgecolor": INK,
        "legend.framealpha": 1.0, "legend.borderpad": 0.4, "legend.handlelength": 1.2, "legend.labelspacing": 0.3,
        "image.cmap": SEQ_CMAP,
        "axes.prop_cycle": matplotlib.cycler(color=[PALETTE["fire"], PALETTE["blue"], PALETTE["grey"],
                                                    PALETTE["teal"], PALETTE["brown"], PALETTE["slate"]]),
        "axes.formatter.use_mathtext": True,
    })


def label_panels(axes, letters: str = "abcdefghij", inside: bool = False, fontsize: float = 9) -> None:
    """Write `a)`, `b)` ... at the top-left of each panel. Moreno et al. put the letter
    inside the frame; ours sits just above the frame's left edge by default so it can
    never cover a bar or a line, and moves inside only when asked."""
    for ax, letter in zip(axes, letters):
        if inside:
            ax.text(0.015, 0.97, f"{letter})", transform=ax.transAxes, ha="left", va="top", fontsize=fontsize, color=INK)
        else:
            ax.text(0.0, 1.015, f"{letter})", transform=ax.transAxes, ha="left", va="bottom", fontsize=fontsize, color=INK)


def boxed_legend(ax, **kw):
    """A legend in a thin black box, inside the panel unless told otherwise."""
    kw.setdefault("loc", "upper left")
    lg = ax.legend(**kw)
    lg.get_frame().set_linewidth(0.5)
    return lg


def finish(fig, out, caption_note: str | None = None) -> None:
    """Save at 300 dpi. No suptitles: captions live in the manuscript."""
    fig.savefig(out, facecolor="white")
    plt.close(fig)
