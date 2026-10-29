"""Shared figure conventions for the track 1C evidence folders: matplotlib, white background, one sans-serif font,
Okabe-Ito colour-blind-safe palette, single column 3.5 in or double column 7.2 in wide, 300 dpi PNG plus SVG."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OKABE_ITO = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
             "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000", "grey": "#999999"}
CYCLE = [OKABE_ITO[k] for k in ("blue", "orange", "green", "vermillion", "purple", "sky", "yellow", "black")]
SINGLE, DOUBLE = 3.5, 7.2


def setup():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 8, "axes.titlesize": 8,
        "axes.labelsize": 8, "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "axes.spines.top": False, "axes.spines.right": False, "axes.prop_cycle": matplotlib.cycler(color=CYCLE),
        "svg.fonttype": "none", "svg.hashsalt": "wfg-track-1c", "path.simplify": False,
    })


def save(fig, out_dir, name):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / (name + ".png"), dpi=300, bbox_inches="tight")
    fig.savefig(out / (name + ".svg"), bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    return out / (name + ".png"), out / (name + ".svg")


def wilson(k, n, z=1.959963984540054):
    """Wilson score interval for k successes out of n (returns (lo, hi); (0, 1) for n = 0)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z / d * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, c - h), min(1.0, c + h)
