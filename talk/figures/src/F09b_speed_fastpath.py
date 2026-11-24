"""F09b: F09 plus the scalar fast path, drawn as its own panel because it was timed on another machine.

Panel (a): kcf-bench host B (Intel Xeon 2.10 GHz, one core), as in F09.
Panel (b): research/kcf-fastpath on branch research/kcf-fastpath (Apple M5 Pro laptop under load), field time only,
           "full" job sets, median of 5 runs, whiskers = range. Seconds are not comparable between panels.
"""
import statistics

import style as S
from F09_speed import draw, fmt_dur, read_data
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger

REF = "origin/research/kcf-fastpath"
RES = "research/kcf-fastpath/results/RESULTS.json"
KEYS = ["UA0323", "UA0324", "UA0325", "YD0325T19", "YD0325T23", "YD0326"]


def read_fast(L, rows):
    d = L.json(RES, ref=REF)
    host = L.json("research/kcf-fastpath/runs/HOST.json", ref=REF)
    out = []
    for k, r in zip(KEYS, rows):
        b = [x["field"] for x in d["runs"][f"full/{k}/baseline"]]
        f = [x["field"] for x in d["runs"][f"full/{k}/scalar"]]
        ratio = d["ratios"][f"full/{k}/scalar"]["field"]["median"]
        lab = f"{r['short']} {r['when']}"
        L.add(f"{lab}: field time, deadline field (baseline solver), median and range",
              [statistics.median(b), min(b), max(b)], unit="s", ref=REF, file=RES,
              field=f"runs['full/{k}/baseline'][*].field", n=f"{len(b)} runs")
        L.add(f"{lab}: field time, scalar fast path, median and range", [statistics.median(f), min(f), max(f)],
              unit="s", ref=REF, file=RES, field=f"runs['full/{k}/scalar'][*].field", n=f"{len(f)} runs")
        L.add(f"{lab}: ratio of field times", ratio, shown=f"{ratio:.1f}×", ref=REF, file=RES,
              field=f"ratios['full/{k}/scalar'].field.median", n=f"{len(f)} runs", expected="1.8 to 2.6×")
        out.append(dict(base=statistics.median(b), b_lo=min(b), b_hi=max(b), fast=statistics.median(f),
                        f_lo=min(f), f_hi=max(f), ratio=ratio))
    L.note(f"Panel b machine: {host['cpu_model']}, {host['platform']} (runs/HOST.json on {REF}); panel a machine: "
           "Intel Xeon 2.10 GHz (kcf-bench BENCH.md §1). Different machines, so the panels do not share an axis.")
    return out, host


def main():
    L = Ledger("F09b", "Speed with the scalar fast path (separate panel, other machine)")
    rows, tot, dis, ncases = read_data(L)
    fast, host = read_fast(L, rows)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    top, h = 0.85, 3.85
    fig, ax = draw(rows, tot, fig=fig, rect=(2.25, top, 4.45, h),
                   ticks=[(60, "1 min"), (3600, "1 h"), (360000, "100 h")])
    S.panel_letter(fig, 0.45, 0.42, "a")
    # panel b, rows aligned with panel a (no total row: the fast-path study has no all-cache total)
    axb = fig.add_axes([8.75 / W, 1 - (top + h) / H, 4.15 / W, h / H])
    axb.set_xscale("log")
    axb.set_xlim(1, 400)
    axb.set_ylim(ax.get_ylim())
    grid(axb, axis="x")
    bh = 0.34
    for i, f in enumerate(fast):
        axb.barh(i - bh / 2, f["base"] - 1, left=1, height=bh, facecolor=S.OURS, edgecolor=S.INK, linewidth=0.6,
                 label="deadline field" if i == 0 else None)
        axb.barh(i + bh / 2, f["fast"] - 1, left=1, height=bh, facecolor=S.WHITE, edgecolor=S.OURS, hatch="\\\\\\",
                 linewidth=0.8, label="fast path" if i == 0 else None)
        axb.errorbar(f["base"], i - bh / 2, xerr=[[f["base"] - f["b_lo"]], [f["b_hi"] - f["base"]]], fmt="none",
                     ecolor=S.INK, elinewidth=1.0, capsize=3)
        axb.errorbar(f["fast"], i + bh / 2, xerr=[[f["fast"] - f["f_lo"]], [f["f_hi"] - f["fast"]]], fmt="none",
                     ecolor=S.INK, elinewidth=1.0, capsize=3)
        axb.annotate(f"{f['ratio']:.1f}×", (f["b_hi"], i - bh / 2), xytext=(8, 0), textcoords="offset points",
                     va="center", fontsize=S.PT_TEXT)
    axb.set_yticks(range(len(fast)))
    axb.set_yticklabels([])
    axb.tick_params(axis="y", length=0)
    axb.set_xticks([1, 10, 100])
    axb.set_xticklabels(["1 s", "10 s", "100 s"])
    axb.minorticks_off()
    axb.set_xlabel("Field time (log scale)")
    boxed_legend(axb, loc="lower right", bbox_to_anchor=(1.0, 1.03), ncol=2, borderaxespad=0.0, columnspacing=1.5,
                 handleheight=0.9)
    S.panel_letter(fig, 7.45, 0.42, "b")
    rng = [f["ratio"] for f in fast]
    cap = add_caption(fig, (
        "Figure 9b. (a) As Figure 9: earlier method (hatched grey) against the deadline field (blue) on one server "
        f"core; in total {fmt_dur(tot['old'])} against {fmt_dur(tot['new'])} ({tot['ratio']:.0f}×), {dis} "
        f"disagreements in {ncases:,} cases. (b) When roads do not reopen, the scalar fast path cuts the field time "
        f"{min(rng):.1f}× to {max(rng):.1f}× (median of 5 runs; whiskers: range). Panel (b) was timed on a different "
        f"machine ({host['cpu_model']} laptop under load), so its seconds are not comparable with (a). Sources: "
        "research/kcf-bench/results_hostB; research/kcf-fastpath/results (branch research/kcf-fastpath)."),
        x_in=0.45, width_in=12.45, top_in=5.85)
    L.save()
    save(fig, "F09b_speed_fastpath", caption=cap)


if __name__ == "__main__":
    main()
