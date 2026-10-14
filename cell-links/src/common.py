"""Shared helpers: paths, figure style, and the NUMBERS.json ledger.

Every number quoted in README, RESULTS or LOG summaries is written through
`record()` so that its producing script, config and git commit are traceable.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "configs"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
RAW = ROOT / "data" / "raw"
NUMBERS = RESULTS / "NUMBERS.json"

# Okabe-Ito colorblind-safe palette.
OI = {
    "black": "#000000", "orange": "#E69F00", "skyblue": "#56B4E9",
    "green": "#009E73", "yellow": "#F0E442", "blue": "#0072B2",
    "vermillion": "#D55E00", "purple": "#CC79A7", "grey": "#999999",
}
CYCLE = [OI[k] for k in ("blue", "vermillion", "green", "orange", "purple", "skyblue", "black", "yellow")]


def style() -> None:
    mpl.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 300, "font.size": 10,
        "axes.titlesize": 11, "axes.labelsize": 10, "legend.fontsize": 8.5,
        "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
        "grid.linewidth": 0.6, "lines.linewidth": 1.6,
        "axes.prop_cycle": mpl.cycler(color=CYCLE), "svg.fonttype": "none",
        "font.family": "DejaVu Sans", "legend.frameon": False,
    })


def savefig(fig, name: str) -> list[Path]:
    FIGURES.mkdir(exist_ok=True)
    out = [FIGURES / f"{name}.png", FIGURES / f"{name}.svg"]
    fig.savefig(out[0], dpi=300, bbox_inches="tight")
    fig.savefig(out[1], bbox_inches="tight")
    plt.close(fig)
    return out


def load_config(name: str) -> dict:
    with open(CONFIGS / name) as f:
        return json.load(f)


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT), "describe", "--always", "--dirty", "--abbrev=12"],
            text=True).strip()
    except Exception:
        return "unknown"


def now_cst() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M %Z")


def record(entries: dict, script: str, config: str | None, kind: str = "modeled") -> None:
    """Merge numbers into results/NUMBERS.json.

    entries: {key: (value, unit, description)}
    kind: "modeled" (simulation output), "measured" (from a cited source) or "assumed".
    """
    RESULTS.mkdir(exist_ok=True)
    data = json.loads(NUMBERS.read_text()) if NUMBERS.exists() else {}
    commit, ts = git_commit(), now_cst()
    for key, (value, unit, desc) in entries.items():
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float):
            value = float(f"{value:.6g}")
        data[key] = {"value": value, "unit": unit, "description": desc, "kind": kind,
                     "script": script, "config": config, "commit": commit, "time": ts}
    NUMBERS.write_text(json.dumps(dict(sorted(data.items())), indent=1) + "\n")
