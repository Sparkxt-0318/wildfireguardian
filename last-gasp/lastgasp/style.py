"""Shared figure style: Okabe-Ito colorblind-safe palette, readable sizes, PNG 300 dpi + SVG."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "skyblue": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "grey": "#999999",
}
METHOD_COLORS = {
    "idw_naive": OKABE_ITO["grey"],
    "idw_topology": OKABE_ITO["blue"],
    "huygens": OKABE_ITO["vermillion"],
    "oracle_idw": OKABE_ITO["black"],
}
METHOD_LABELS = {
    "idw_naive": "IDW, all deaths (naive)",
    "idw_topology": "IDW, after grid filtering",
    "huygens": "Huygens fit, after grid filtering",
    "oracle_idw": "Floor: IDW of true times",
}
CAUSE_COLORS = {
    "fire": OKABE_ITO["vermillion"], "fire_local": OKABE_ITO["orange"], "fire_grid": OKABE_ITO["blue"],
    "random_grid": OKABE_ITO["skyblue"], "upstream_grid": OKABE_ITO["purple"],
    "random_device": OKABE_ITO["green"],
}
CAUSE_LABELS = {
    "fire": "Fire reached building", "fire_local": "Fire at own transformer pole",
    "fire_grid": "Upstream line fault (fire caused)", "random_grid": "Unrelated grid outage",
    "upstream_grid": "Substation or transmission trip", "random_device": "Unrelated device failure",
}
SYNTH_NOTE = "Synthetic simulation, not real-world data"


def apply():
    plt.rcParams.update({
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8,
        "ytick.labelsize": 8, "legend.fontsize": 8, "figure.titlesize": 11, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
        "font.family": "DejaVu Sans", "svg.fonttype": "none", "axes.titleweight": "normal",
    })


def save(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=300)
    fig.savefig(out_dir / f"{name}.svg")
    plt.close(fig)
    return out_dir / f"{name}.png"
