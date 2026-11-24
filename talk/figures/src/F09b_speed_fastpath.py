"""F09b: F09 plus the scalar fast path, drawn as its own panel because it was timed on another machine.

Panel a: kcf-bench host B (Intel Xeon 2.10 GHz, one core), as in F09.
Panel b: research/kcf-fastpath on branch research/kcf-fastpath (Apple M5 Pro laptop under load), field time only,
         "full" job sets, median of 5 runs. Seconds are not comparable between panels, so no shared axis.
"""
import statistics

import style as S
from F09_speed import draw, read_data
from figkit import save
from prov import Ledger

REF = "origin/research/kcf-fastpath"
RES = "research/kcf-fastpath/results/RESULTS.json"
KEYS = ["UA0323", "UA0324", "UA0325", "YD0325T19", "YD0325T23", "YD0326"]


def read_fast(L, rows):
    d = L.json(RES, ref=REF)
    host = L.json("research/kcf-fastpath/runs/HOST.json", ref=REF)
    out = []
    for k, r in zip(KEYS, rows):
        base = statistics.median(x["field"] for x in d["runs"][f"full/{k}/baseline"])
        fast = statistics.median(x["field"] for x in d["runs"][f"full/{k}/scalar"])
        ratio = d["ratios"][f"full/{k}/scalar"]["field"]["median"]
        lab = f"{r['place']}, {r['when']}"
        nrun = len(d["runs"][f"full/{k}/scalar"])
        L.add(f"{lab}: field time, deadline field (baseline solver)", base, unit="s", ref=REF, file=RES,
              field=f"median of runs['full/{k}/baseline'][*].field", n=f"{nrun} runs")
        L.add(f"{lab}: field time, scalar fast path", fast, unit="s", ref=REF, file=RES,
              field=f"median of runs['full/{k}/scalar'][*].field", n=f"{nrun} runs")
        L.add(f"{lab}: ratio field time", ratio, shown=f"{ratio:.1f}×", ref=REF, file=RES,
              field=f"ratios['full/{k}/scalar'].field.median", n=f"{nrun} runs", expected="1.8 to 2.6×")
        out.append(dict(base=base, fast=fast, ratio=ratio))
    L.note(f"Panel b machine: {host.get('cpu', host)} (runs/HOST.json on {REF}); panel a machine: Intel Xeon 2.10 GHz "
           "(kcf-bench BENCH.md §1). Different machines, so the panels do not share an axis (DECISIONS.md).")
    return out


def main():
    L = Ledger("F09b", "Speed with the scalar fast path (separate panel, other machine)")
    rows, tot, dis, ncases = read_data(L)
    fast = read_fast(L, rows)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    t = 0.95
    fig, ax, ys = draw(rows, tot, dis, ncases, fig=fig, ax_rect=(2.35, t, 3.55), head_x=0.45, xr_in=7.30,
                       footnote=False, xmax=2.5e6, new_label="deadline field",
                       ticks=[(60, "1 min"), (3600, "1 h"), (360000, "100 h")])
    # panel headers
    fig.text(0.45 / W, 1 - 0.40 / H, "a   Server, one core: earlier method against the field", fontsize=S.PT_BODY,
             fontweight="bold", va="center")
    fig.text(8.05 / W, 1 - 0.40 / H, "b   When roads do not reopen: fast path", fontsize=S.PT_BODY,
             fontweight="bold", va="center")
    # panel b axes, rows aligned with panel a
    h = ax.get_position().height * H
    axb = fig.add_axes([8.05 / W, 1 - (t + h) / H, 3.35 / W, h / H])
    axb.set_ylim(ax.get_ylim())
    bh, gap = 0.15, 0.12
    off = bh / 2 + gap / 2
    for y0, f in zip(ys[:-1], fast):
        axb.barh(y0 - off, f["base"] - 1, height=bh, color=S.OURS, left=1)
        axb.barh(y0 + off, f["fast"] - 1, height=bh, left=1, facecolor=S.WHITE, edgecolor=S.OURS, hatch="////",
                 linewidth=1.2)
    axb.set_yticks([])
    axb.spines["left"].set_visible(False)
    axb.set_xscale("log")
    axb.set_xlim(1, 400)
    axb.set_xticks([1, 10, 100])
    axb.set_xticklabels(["1 s", "10 s", "100 s"])
    axb.minorticks_off()
    axb.set_xlabel("Field time (log scale)")
    axb.annotate("deadline field", (fast[0]["base"], ys[0] - off - 0.06), xytext=(10, 0), textcoords="offset points",
                 color=S.OURS, va="center", fontsize=S.PT_MIN, fontweight="bold")
    axb.annotate("fast path", (fast[5]["fast"], ys[5] + off), xytext=(10, 0), textcoords="offset points",
                 color=S.OURS, va="center", fontsize=S.PT_MIN)
    xr = 12.95 / W
    fig.text(xr, 1 - (t + ys[0] - 0.42) / H, "times faster", ha="right", va="center", fontsize=S.PT_MIN, color=S.MID)
    for y, f in zip(ys[:-1], fast):
        yf = fig.transFigure.inverted().transform(axb.transData.transform((0, y)))[1]
        fig.text(xr, yf, f"{f['ratio']:.1f}×", ha="right", va="center", fontsize=S.PT_LABEL, fontweight="bold",
                 color=S.INK)
    # footnotes
    fig.text(0.45 / W, 1 - 7.08 / H,
             "a: earlier method estimated from 200 timed requests per cache; "
             f"{dis} disagreements in {ncases:,} cases.\n"
             "b: timed on a different machine (laptop under load), so its seconds are not comparable with a.",
             fontsize=S.PT_MIN, color=S.MID, ha="left", va="center", linespacing=1.25)
    L.save()
    save(fig, "F09b_speed_fastpath")


if __name__ == "__main__":
    main()
