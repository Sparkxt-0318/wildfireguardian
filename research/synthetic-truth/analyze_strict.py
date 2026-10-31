"""Plot availability and diagnostic skill, never replace null risk by zero."""
from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(); p.add_argument("--run", default=str(Path(__file__).parent / "strict-support-20261030"))
    a = p.parse_args(); result = json.loads((Path(a.run) / "RESULTS.json").read_text())
    out = Path(__file__).parent / "figures"; out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "figure.facecolor": "white", "svg.fonttype": "none"})
    rows = [r for r in result["summaries"] if r["campaign"] == "C1"]
    fig, ax = plt.subplots(figsize=(7.2, 3))
    ax.bar([r["forecast_source"] for r in rows], [r["cases"] - r["scorable_truth_cases"] for r in rows], color="#E69F00")
    ax.set_ylabel("Unscorable truth cases (count)"); ax.set_title("Strict unknown-source admission: risk rates unavailable")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / ("fig01_truth_score_availability." + ext), dpi=300)
    plt.close(fig)
    rows = [r for r in result["summaries"] if r["campaign"] == "C2"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    palette = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]
    markers = ["o", "s", "^", "D", "P", "x"]
    for r, color, marker in zip(rows, palette, markers):
        kwargs = {"edgecolors": color, "facecolors": "none"} if marker == "D" else {"color": color}
        ax.scatter(r["mean_brier_joint_known_support"], r["unresolved"] / r["cases"], label=r["forecast_source"], s=24, marker=marker, **kwargs)
    ax.set_xlabel("Brier score on joint known cells (dimensionless)"); ax.set_ylabel("Unresolved admission fraction")
    ax.set_ylim(.9, 1.05); ax.legend(loc="center left", bbox_to_anchor=(1, .5), frameon=False)
    ax.set_title("Truth error rates unavailable under strict admission")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / ("fig02_decision_vs_forecast_quality." + ext), dpi=300)
    plt.close(fig)
    (Path(__file__).parent / "RESULTS.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
