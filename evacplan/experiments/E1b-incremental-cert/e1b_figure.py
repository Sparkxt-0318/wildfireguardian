"""E1b figure (SYNTHETIC): per dev instance, residents delivered by E1b (median over seeds, line = min-max) against B2
in the same interleaved holds, as a share of the instance's residents, with the counts beside each row. Reads the
harness's committed rows (``evacplan/results/*.csv``, B2 paired by hold and pair as in ``e1b_analysis.py``) and the
split's resident counts; runs nothing. Dev rows of one host only (default: this machine's host string). Writes
``figures/SYNTHETIC_e1b_vs_b2_delivered_by_instance.png``.

    .venv/bin/python evacplan/experiments/E1b-incremental-cert/e1b_figure.py [--host HOST] [--results-dir DIR]
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from evacplan import harness
from evacplan.instances import load_split

HERE = Path(__file__).resolve().parent
SET, BUDGET, METHOD, B2 = "dev", 60.0, "e1b_alns", "b2_vrptw"
OUT = HERE / "figures" / "SYNTHETIC_e1b_vs_b2_delivered_by_instance.png"
LABELS = {METHOD: "E1b", B2: "B2 OR-Tools VRPTW (same holds)"}
INK, INK_2, MUTED, GRID, AXIS, SURFACE = (harness._INK, harness._INK_2, harness._MUTED, harness._GRID, harness._AXIS,
                                          harness._SURFACE)


def stat(xs) -> str:
    m = statistics.median(xs)
    return f"{m:g}" if min(xs) == max(xs) else f"{m:g} [{min(xs):g}–{max(xs):g}]"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default=None)
    ap.add_argument("--results-dir", type=Path, default=harness.RESULTS_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    host = args.host or harness.host_string()
    entries = load_split().entries(SET)
    residents = {e.id: int(e.stats["residents"]) for e in entries}
    held = [r for r in harness.all_rows(args.results_dir)
            if harness.table_key(r) == (SET, BUDGET, host) and r["instance"] in residents
            and r["method"] in (METHOD, B2) and harness.row_config(r).get("hold")]
    pair = {(harness.row_config(r)["hold"], harness.row_config(r)["pair"], r["method"]): r for r in held}
    vals = {(m, e.id): [] for m in (METHOD, B2) for e in entries}
    seeds = set()
    for r in held:
        if r["method"] != METHOD:
            continue
        c = harness.row_config(r)
        vals[(METHOD, r["instance"])].append(int(r["delivered_checked"]))
        seeds.add(int(r["seed"]))
        b = pair.get((c["hold"], c["pair"], B2))
        if b:
            vals[(B2, r["instance"])].append(int(b["delivered_checked"]))
    ids = [e.id for e in entries if vals[(METHOD, e.id)]]
    if not ids:
        print(f"no interleaved {METHOD} rows for {SET} at {BUDGET:g} s on host {host}")
        return 1
    seed_txt = (f"seeds {min(seeds)}-{max(seeds)}" if seeds == set(range(min(seeds), max(seeds) + 1))
                else "seeds " + ", ".join(map(str, sorted(seeds))))
    title = (f"SYNTHETIC - residents delivered per instance: E1b vs B2 in the same interleaved holds\n"
             f"{SET}, budget {BUDGET:g} s, {seed_txt}, host {host}")

    import matplotlib.style
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    style = harness._series_style([B2, METHOD])          # the leaderboard's colour and marker for each method
    with matplotlib.style.context("default"), rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        fig = Figure(figsize=(8.0, 5.0), dpi=100, facecolor=SURFACE)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot()
        ax.set_facecolor(SURFACE)
        ys = list(range(len(ids)))[::-1]
        for m, off in ((METHOD, 0.15), (B2, -0.15)):
            colour, marker, _ = style[m]
            for y, i in zip(ys, ids):
                v = vals[(m, i)]
                if not v:
                    continue
                lo, mid, hi = (100.0 * x / residents[i] for x in (min(v), statistics.median(v), max(v)))
                if hi > lo:
                    ax.plot([lo, hi], [y + off] * 2, color=colour, linewidth=2, solid_capstyle="round", zorder=2)
                ax.plot([mid], [y + off], marker=marker, markersize=8, color=colour, markeredgecolor=SURFACE,
                        markeredgewidth=1.2, linestyle="none", zorder=3, label=LABELS[m] if y == ys[0] else None)
        for y, i in zip(ys, ids):
            b2 = vals[(B2, i)]
            ax.annotate(f"E1b {stat(vals[(METHOD, i)])} · B2 {stat(b2) if b2 else '–'}", (1.0, y),
                        xycoords=("axes fraction", "data"), xytext=(8, 0), textcoords="offset points", ha="left",
                        va="center", color=INK_2, fontsize=8)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{i.replace('SYNTHETIC-', '')} ({residents[i]})" for i in ids], color=INK_2)
        ax.set_ylim(-0.6, len(ids) - 0.4)
        ax.set_xlim(0, 102)
        ax.set_xlabel("residents delivered (checked in all K members), % of the instance's residents\n"
                      "marker: median over seeds; line: min-max; right: delivered counts, median [min-max]",
                      color=INK_2)
        ax.tick_params(colors=MUTED, labelcolor=INK_2)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.legend(loc="lower left", frameon=False, fontsize=8, labelcolor=INK)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.out, dpi=100, facecolor=SURFACE, bbox_inches="tight",
                    metadata={"Software": None, "Title": title})
    print(f"-> {args.out} ({len(ids)} instances, {seed_txt}, SYNTHETIC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
