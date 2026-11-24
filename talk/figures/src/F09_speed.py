"""F09 speed: earlier method against the deadline field, six recorded caches and the total.

Slide 9, right two thirds. Log time axis, one pair of bars per cache, ratio at the end of each pair.
Source: research/kcf-bench/results_hostB/summary.json and accuracy/*.json (kcf-bench, host B).
"""
import re

import numpy as np

import style as S
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger

BENCH = "research/kcf-bench"
SUMMARY = f"{BENCH}/results_hostB/summary.json"

CACHES = [
    ("uiseong_andong_2025/20250323T010000Z", "Uiseong–Andong", "23 Mar 01:00"),
    ("uiseong_andong_2025/20250324T090000Z", "Uiseong–Andong", "24 Mar 09:00"),
    ("uiseong_andong_2025/20250325T170000Z", "Uiseong–Andong", "25 Mar 17:00"),
    ("yeongdeok_2025/20250325T190000Z", "Yeongdeok", "25 Mar 19:00"),
    ("yeongdeok_2025/20250325T230000Z", "Yeongdeok", "25 Mar 23:00"),
    ("yeongdeok_2025/20250326T080000Z", "Yeongdeok", "26 Mar 08:00"),
]

X0 = 8.0
TICKS = [60, 600, 3600, 36000, 360000]
TICK_LABELS = ["1 min", "10 min", "1 h", "10 h", "100 h"]


def fmt_dur(s):
    if s >= 3600:
        return f"{s / 3600:.1f} h"
    if s >= 60:
        return f"{s / 60:.0f} min"
    return f"{s:.0f} s"


def read_data(L):
    d = L.json(SUMMARY)
    rows = []
    for key, place, when in CACHES:
        c = d["caches"][key]
        old = c["old"]["cold"]["scaled"]["median"]
        new = c["field"]["field"]["cold"]["median"]
        ratio = c["ratios"]["old/field/cold"]["median"]
        n = c["n_cases"]
        lab = f"{place}, {when}"
        L.add(f"{lab}: earlier method, cold, scaled", old, unit="s", n=f"{n} cases (200 timed requests x 5 repeats)",
              file=SUMMARY, field=f"caches['{key}'].old.cold.scaled.median")
        L.add(f"{lab}: deadline field, cold", new, unit="s", n=f"{n} cases, 5 repeats",
              file=SUMMARY, field=f"caches['{key}'].field.field.cold.median")
        L.add(f"{lab}: ratio", ratio, shown=f"{ratio:.0f}×", n="5 repeats",
              file=SUMMARY, field=f"caches['{key}'].ratios['old/field/cold'].median")
        oc, fc = c["old"]["cold"]["scaled"], c["field"]["field"]["cold"]
        L.add(f"{lab}: earlier method range over repeats", [oc["min"], oc["max"]], unit="s", n="5 repeats",
              file=SUMMARY, field=f"caches['{key}'].old.cold.scaled.min/max", shown="whisker")
        L.add(f"{lab}: deadline field range over repeats", [fc["min"], fc["max"]], unit="s", n="5 repeats",
              file=SUMMARY, field=f"caches['{key}'].field.field.cold.min/max", shown="whisker")
        rows.append(dict(key=key, place=place, short="UA" if place.startswith("Uiseong") else "YD", when=when,
                         old=old, new=new, ratio=ratio, n=n, old_lo=oc["min"], old_hi=oc["max"],
                         new_lo=fc["min"], new_hi=fc["max"]))
    # total = sum of per-cache medians (the same total BENCH.md states)
    t_old = sum(r["old"] for r in rows)
    t_new = sum(r["new"] for r in rows)
    t_n = sum(r["n"] for r in rows)
    bench = L.text(f"{BENCH}/BENCH.md")
    m = re.search(r"\*\*([\d.]+) h\*\* cold", bench)
    m2 = re.search(r"Ratio \*\*(\d+)×\*\* cold", bench)
    L.add("All six: earlier method total (sum of the six cache medians)", t_old, unit="s",
          shown=fmt_dur(t_old), n=f"{t_n} cases", file=SUMMARY, field="sum over caches of old.cold.scaled.median",
          expected="43.6 h", note=f"BENCH.md states {m.group(1)} h (cross-check)")
    L.add("All six: deadline field total (sum of the six cache medians)", t_new, unit="s",
          shown=fmt_dur(t_new), n=f"{t_n} cases", file=SUMMARY, field="sum over caches of field.field.cold.median",
          expected="20 min")
    L.add("All six: ratio of totals", t_old / t_new, shown=f"{t_old / t_new:.0f}×", n=f"{t_n} cases",
          file=SUMMARY, field="ratio of the two sums", expected="about 129×",
          note=f"BENCH.md states {m2.group(1)}× [114–151] (cross-check)")
    assert f"{t_old / 3600:.1f}" == m.group(1), "total differs from BENCH.md"
    # agreement: zero disagreements over all cases
    dis, ncases = 0, 0
    for key, _, _ in CACHES:
        a = L.json(f"{BENCH}/results_hostB/accuracy/{key.replace('/', '__')}.json")
        cnt = a["counts"]
        dis += sum(v for k, v in cnt.items() if k.endswith("_MISMATCH"))
        ncases += a["n_cases"]
    L.add("Disagreements between the field and the earlier method / recorded answers", dis,
          shown=f"0 disagreements in {ncases:,} cases", n=f"{ncases} cases",
          file=f"{BENCH}/results_hostB/accuracy/*.json", field="counts.*_MISMATCH (recorded vs field, recorded vs margin@0, earlier vs field, earlier vs margin@0), summed; n_cases summed",
          note="'disagreements.old_unstable' lists earlier-method cases that were decided in one repeat and unresolved in another (time limit); these are not disagreements and are not counted",
          expected="0 on 9,722")
    L.add("Timed requests per cache (earlier method)", 200, shown="200",
          file=f"{BENCH}/BENCH.md", field="§2 Methods: 'a fixed random sample of 200 requests per cache'")
    tot = dict(old=t_old, new=t_new, n=t_n, ratio=t_old / t_new,
               old_lo=sum(r["old_lo"] for r in rows), old_hi=sum(r["old_hi"] for r in rows),
               new_lo=sum(r["new_lo"] for r in rows), new_hi=sum(r["new_hi"] for r in rows))
    L.add("All six: whiskers (sums of per-cache minima and maxima over repeats)",
          [tot["old_lo"], tot["old_hi"], tot["new_lo"], tot["new_hi"]], unit="s", file=SUMMARY,
          field="sum of old.cold.scaled.min / max and field.field.cold.min / max", shown="whisker",
          note="equal to BENCH.md's 41.3–45.5 h and 18–22 min")
    return rows, tot, dis, ncases


def draw(rows, tot, fig=None, rect=(6.85, 0.85, 6.05, 3.85), xlim=(8, 6e5), ticks=None, legend_loc="lower right"):
    """Framed log axis, gridlines, boxed legend, whiskers = range over the five repeats."""
    fig = fig or S.new_figure()
    W, H = S.W_IN, S.H_IN
    l, t, w, h = rect
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    ax.set_xscale("log")
    ax.set_xlim(*xlim)
    grid(ax, axis="x")
    allrows = rows + [tot]
    n = len(allrows)
    ys = [i + (0.5 if i == n - 1 else 0) for i in range(n)]
    bh = 0.34
    for k, (y0, r) in enumerate(zip(ys, allrows)):
        lab_old = "earlier method" if k == 0 else None
        lab_new = "deadline field" if k == 0 else None
        ax.barh(y0 - bh / 2, r["old"] - X0, left=X0, height=bh, facecolor=S.LIGHT, edgecolor=S.INK,
                hatch="///", linewidth=0.6, label=lab_old)
        ax.barh(y0 + bh / 2, r["new"] - X0, left=X0, height=bh, facecolor=S.OURS, edgecolor=S.INK,
                linewidth=0.6, label=lab_new)
        ax.errorbar(r["old"], y0 - bh / 2, xerr=[[r["old"] - r["old_lo"]], [r["old_hi"] - r["old"]]], fmt="none",
                    ecolor=S.INK, elinewidth=1.0, capsize=3)
        ax.errorbar(r["new"], y0 + bh / 2, xerr=[[r["new"] - r["new_lo"]], [r["new_hi"] - r["new"]]], fmt="none",
                    ecolor=S.INK, elinewidth=1.0, capsize=3)
        if k < n - 1:
            ax.annotate(f"{r['ratio']:.0f}×", (r["old_hi"], y0 - bh / 2), xytext=(8, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=S.PT_TEXT)
    ax.set_ylim(ys[-1] + 0.75, -0.7)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{r['short']} {r['when']}" for r in rows] + ["all six"])
    ax.tick_params(axis="y", length=0)
    tk = ticks or list(zip(TICKS, TICK_LABELS))
    ax.set_xticks([a for a, _ in tk])
    ax.set_xticklabels([b for _, b in tk])
    ax.minorticks_off()
    ax.set_xlabel("Time to answer every case (log scale)")
    boxed_legend(ax, loc=legend_loc, bbox_to_anchor=(1.0, 1.03), ncol=2, borderaxespad=0.0, columnspacing=1.5,
                 handleheight=0.9)
    return fig, ax


def caption_text(tot, dis, ncases, num="9"):
    return (f"Figure {num}. Time to answer all {ncases:,} recorded cases of six planner caches (UA, Uiseong–Andong; "
            "YD, Yeongdeok; UTC) on one server core. Bars: median of 5 cold repeats; whiskers: range. In total, "
            f"{fmt_dur(tot['old'])} for the earlier method (hatched; scaled from 200 timed requests per cache) against "
            f"{fmt_dur(tot['new'])} for the deadline field ({tot['ratio']:.0f}×), with {dis} disagreements. "
            "Source: research/kcf-bench/results_hostB.")


def main():
    L = Ledger("F09", "Speed: earlier method against the deadline field")
    rows, tot, dis, ncases = read_data(L)
    fig, ax = draw(rows, tot)
    L.note("Machine: Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18, one pinned core (BENCH.md §1). "
           "Cold runs shown. Totals are sums of per-cache medians; their ratio equals the 129× in BENCH.md.")
    L.save()
    cap = add_caption(fig, caption_text(tot, dis, ncases), x_in=4.55, width_in=8.35, top_in=5.80)
    save(fig, "F09_speed", caption=cap)


if __name__ == "__main__":
    main()
