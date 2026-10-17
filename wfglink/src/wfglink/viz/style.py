"""One matplotlib style for every wfglink figure.

- Okabe-Ito palette (distinguishable with the common color-vision deficiencies), in a fixed
  order so a quantity keeps its color across figures.
- Pretendard (vendored, SIL OFL 1.1) so Korean labels render; DejaVu Sans as fallback.
- Axes are labelled with units; light grid; no top or right spine.
- `save` writes a 300 dpi PNG and an SVG side by side and returns both paths. Every figure
  is then opened and inspected before it is quoted (plan section 2).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from wfglink import PROJECT_ROOT  # noqa: E402

OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
# Named roles, so the same quantity has the same color everywhere.
COLORS = {"ink": "#000000", "ember": "#D55E00", "track": "#0072B2", "streak": "#E69F00",
          "truth": "#000000", "goal": "#009E73", "air": "#56B4E9", "neutral": "#999999", "alt": "#CC79A7"}
_DONE = False


def use() -> None:
    """Apply the style (idempotent)."""
    global _DONE
    if _DONE:
        return
    fonts = PROJECT_ROOT / "assets" / "fonts"
    family = ["DejaVu Sans"]
    for f in sorted(fonts.glob("Pretendard-*.otf")):
        font_manager.fontManager.addfont(str(f))
        family = ["Pretendard", "DejaVu Sans"]
    plt.rcParams.update({
        "font.family": family,
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "axes.prop_cycle": matplotlib.cycler(color=OKABE_ITO[1:] + OKABE_ITO[:1]),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#DDDDDD",
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "svg.fonttype": "none",       # keep text as text in SVG
        "axes.unicode_minus": False,  # the hyphen-minus renders in every font
    })
    _DONE = True


def save(fig, path_stem: str | Path) -> tuple[Path, Path]:
    """Write <stem>.png (300 dpi) and <stem>.svg; return both paths."""
    stem = Path(path_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    png, svg = stem.with_suffix(".png"), stem.with_suffix(".svg")
    fig.savefig(png, dpi=300)
    fig.savefig(svg)
    plt.close(fig)
    return png, svg
