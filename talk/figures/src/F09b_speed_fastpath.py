"""F09b: F09 plus the scalar fast path, drawn as its own panel because it was timed on another machine.

Panel (a): kcf-bench host B (Intel Xeon 2.10 GHz, one core), as in F09.
Panel (b): research/kcf-fastpath on branch research/kcf-fastpath (Apple M5 Pro laptop under load), field time only,
           "full" job sets, median of 5 runs, whiskers = range. Seconds are not comparable between panels.
"""
import statistics

import style as S
from F09_speed import NEW_NAME, OLD_NAME, draw, fmt_dur, legend_row, read_data, row_positions, update_interval

FAST_NAME = "fast path (ours)"
from figkit import add_caption, grid, save
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
        lab = f"{r['place']}, {r['when']}"
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
    hourly = update_interval(L)
    fast, host = read_fast(L, rows)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    top, h = 1.1, 4.15
    fig, ax, hd = draw(rows, tot, fig=fig, rect=(3.75, top, 4.4, h), xlim=(8, 6e5), hourly=hourly,
                       ticks=[(60, "1 min"), (3600, "1 h"), (360000, "100 h")], ratio_word=False, total_ratio=False)
    S.panel_letter(fig, 3.75, top - 0.25, "a")
    # panel b, rows aligned with panel a (no total row: the fast-path study has no all-cache total)
    ys, _ = row_positions(rows)
    axb = fig.add_axes([8.7 / W, 1 - (top + h) / H, 4.2 / W, h / H])
    axb.set_xscale("log")
    axb.set_xlim(1, 400)
    axb.set_ylim(ax.get_ylim())
    grid(axb, axis="x")
    bh = 0.34
    hb = []
    for y0, f in zip(ys, fast):
        b1 = axb.barh(y0 - bh / 2, f["base"] - 1, left=1, height=bh, facecolor=S.OURS, edgecolor=S.INK, linewidth=0.6)
        b2 = axb.barh(y0 + bh / 2, f["fast"] - 1, left=1, height=bh, facecolor=S.WHITE, edgecolor=S.OURS,
                      hatch="\\\\\\", linewidth=0.8)
        hb = hb or [b1, b2]
        axb.errorbar(f["base"], y0 - bh / 2, xerr=[[f["base"] - f["b_lo"]], [f["b_hi"] - f["base"]]], fmt="none",
                     ecolor=S.INK, elinewidth=1.0, capsize=3)
        axb.errorbar(f["fast"], y0 + bh / 2, xerr=[[f["fast"] - f["f_lo"]], [f["f_hi"] - f["fast"]]], fmt="none",
                     ecolor=S.INK, elinewidth=1.0, capsize=3)
        axb.annotate(f"{f['ratio']:.1f}×", (f["b_hi"], y0 - bh / 2), xytext=(8, 0), textcoords="offset points",
                     va="center", fontsize=S.PT_TEXT)
    axb.set_yticks(ys[:-1])
    axb.set_yticklabels([])
    axb.tick_params(axis="y", length=0)
    axb.set_xticks([1, 10, 100])
    axb.set_xticklabels(["1 s", "10 s", "100 s"])
    axb.minorticks_off()
    axb.set_xlabel("Backward pass, other machine")
    S.panel_letter(fig, 8.7, top - 0.25, "b")
    legend_row(fig, hd + [hb[1]], [OLD_NAME, NEW_NAME, FAST_NAME], W / 2 + 1.5, 0.32)
    rng = [f["ratio"] for f in fast]
    cap = add_caption(fig, (
        f"Figure 9b. (a) As Figure 9: {fmt_dur(tot['old'])} for per-village search against "
        f"{fmt_dur(tot['new'])} for one backward pass ({tot['ratio']:.0f}× faster), {dis} disagreements in {ncases:,} "
        f"checks. (b) When roads never reopen, the fast path is a further {min(rng):.1f}× to {max(rng):.1f}× faster "
        f"(median of 5 runs; whiskers: range), timed on another machine ({host['cpu_model']} laptop under load), so its "
        "seconds do not compare with (a)."),
        x_in=0.45, width_in=12.45, top_in=6.4)
    L.save()
    save(fig, "F09b_speed_fastpath", caption=cap)


if __name__ == "__main__":
    main()
