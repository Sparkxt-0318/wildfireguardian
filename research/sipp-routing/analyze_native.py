"""Recompute native contact-relaxation tables and figures from execution rows."""
from pathlib import Path
import argparse
import json
import hashlib
import statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(); p.add_argument("--run", default=str(Path(__file__).parent / "native-panel-20261030"))
    a = p.parse_args(); folder = Path(a.run)
    rows = [json.loads(line) for line in (folder / "EXECUTIONS.jsonl").read_text().splitlines()]
    pairs = []
    for r in rows:
        if r["method"] != "sweep":
            continue
        s = next(x for x in rows if x["case_index"] == r["case_index"] and x["repetition"] == r["repetition"] and x["method"] == "sipp")
        pairs.append((r, s))
    summary = {"executions": len(rows), "missions": len({r["case_index"] for r in rows}),
               "equivalent_pairs": sum((r["status"], r["arrival"]) == (s["status"], s["arrival"]) and r["status"] != "UNRESOLVED" for r, s in pairs),
               "pairs": len(pairs), "sipp_slower_pairs": sum(s["complete_wall_s"] > r["complete_wall_s"] for r, s in pairs),
               "median_complete_ratio": statistics.median(s["complete_wall_s"] / r["complete_wall_s"] for r, s in pairs),
               "maximum_complete_wall_s": max(r["complete_wall_s"] for r in rows),
               "maximum_sampled_child_rss_mib": max(r["sampled_child_rss_mib"] for r in rows),
               "input_rows_sha256": hashlib.sha256((folder / "EXECUTIONS.jsonl").read_bytes()).hexdigest()}
    (folder / "ANALYSIS.json").write_text(json.dumps(summary, indent=2) + "\n")
    figures = Path(__file__).parent / "figures"; figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "svg.fonttype": "none", "figure.facecolor": "white"})
    fig, ax = plt.subplots(figsize=(3.5, 3.2))
    for panel, color in (("Korean", "#0072B2"), ("Caldor/Rim", "#D55E00")):
        group = [(r, s) for r, s in pairs if r["panel"] == panel]
        ax.scatter([r["complete_wall_s"] for r, _ in group], [s["complete_wall_s"] for _, s in group], s=12, alpha=.75, c=color, label=panel)
    lo = min(r["complete_wall_s"] for r in rows) * .9; hi = max(r["complete_wall_s"] for r in rows) * 1.1
    ax.plot([lo, hi], [lo, hi], color="0.5", lw=.6); ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Frozen sweep complete child time (s)"); ax.set_ylabel("Interval planner complete child time (s)")
    ax.legend(frameon=False); fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figures / ("fig01_time_vs_sweep_paired." + ext), dpi=300)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.2, 3))
    caldor = [(r, s) for r, s in pairs if r["panel"] == "Caldor/Rim"]
    labels = [r["mission"] + " r" + str(r["repetition"]) for r, _ in caldor]
    ax.plot(labels, [r["complete_wall_s"] for r, _ in caldor], "o-", ms=3, c="#0072B2", label="Sweep")
    ax.plot(labels, [s["complete_wall_s"] for _, s in caldor], "s-", ms=3, c="#D55E00", label="Interval")
    ax.set_ylabel("Complete child time (s)"); ax.tick_params(axis="x", rotation=45); ax.legend(frameon=False)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(figures / ("fig03_caldor_breakdown." + ext), dpi=300)
    plt.close(fig)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
