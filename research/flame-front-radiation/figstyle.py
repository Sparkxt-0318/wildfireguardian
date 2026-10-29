"""Shared figure style: white background, one sans-serif font, Okabe-Ito colours, 300 dpi PNG plus SVG."""
OKABE = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]


def apply_style(plt):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 8,
        "axes.facecolor": "white", "figure.facecolor": "white", "savefig.facecolor": "white",
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
        "svg.fonttype": "none", "svg.hashsalt": "wfg-flamefront", "lines.linewidth": 1.2,
    })


def save(fig, stem):
    stem = str(stem)
    fig.savefig(stem + ".png", dpi=300)
    fig.savefig(stem + ".svg", metadata={"Date": None})
