"""F09 speed: earlier method against the deadline field, six recorded caches and the total.

Slide 9, right two thirds. Log time axis, one pair of bars per cache, ratio at the end of each pair.
Source: research/kcf-bench/results_hostB/summary.json and accuracy/*.json (kcf-bench, host B).
"""
import re

import numpy as np

import style as S
from figkit import save
from prov import Ledger

BENCH = "research/kcf-bench"
SUMMARY = f"{BENCH}/results_hostB/summary.json"

CACHES = [
    ("uiseong_andong_2025/20250323T010000Z", "Uiseong–Andong", "23 Mar 01 UTC"),
    ("uiseong_andong_2025/20250324T090000Z", "Uiseong–Andong", "24 Mar 09 UTC"),
    ("uiseong_andong_2025/20250325T170000Z", "Uiseong–Andong", "25 Mar 17 UTC"),
    ("yeongdeok_2025/20250325T190000Z", "Yeongdeok", "25 Mar 19 UTC"),
    ("yeongdeok_2025/20250325T230000Z", "Yeongdeok", "25 Mar 23 UTC"),
    ("yeongdeok_2025/20250326T080000Z", "Yeongdeok", "26 Mar 08 UTC"),
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
        rows.append(dict(key=key, place=place, when=when, old=old, new=new, ratio=ratio, n=n))
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
    return rows, dict(old=t_old, new=t_new, n=t_n), dis, ncases


def layout_rows(rows):
    """Row centres in inches from the top of the axes; group headers before each place."""
    y, out, heads, last = 0.22, [], [], None
    for r in rows:
        if r["place"] != last:
            if last is not None:
                y += 0.12
            heads.append((r["place"], y))
            y += 0.36
            last = r["place"]
        out.append(y)
        y += 0.51
    y += 0.18
    out.append(y)          # total row
    return out, heads, y + 0.34


def draw(rows, tot, dis, ncases, fig=None, ax_rect=None, footnote=True, foot_y=7.02, xmax=2.5e6,
         head_x=4.62, xr_in=12.95, ticks=None, new_label="deadline field (ours)"):
    """Pairs: blue (ours) on top, grey (earlier) below; ratio column at the right."""
    fig = fig or S.new_figure()
    W, H = S.W_IN, S.H_IN
    ys, heads, ybot = layout_rows(rows)
    l, t, w = (ax_rect or (6.55, 0.95, 5.0))[:3]
    h = ybot
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    ax.set_xscale("log")
    ax.set_xlim(X0, xmax)
    bh, gap = 0.15, 0.12
    off = bh / 2 + gap / 2
    allrows = rows + [dict(old=tot["old"], new=tot["new"], ratio=tot["old"] / tot["new"])]
    for y0, r in zip(ys, allrows):
        # bars start at the axis origin (8 s) and end exactly at the value
        ax.barh(y0 - off, r["new"] - X0, height=bh, color=S.OURS, left=X0)
        ax.barh(y0 + off, r["old"] - X0, height=bh, color=S.MID, left=X0)
    ax.set_ylim(ybot, 0)
    ax.set_yticks(ys)
    labels = [r["when"] for r in rows] + ["All six caches"]
    ax.set_yticklabels(labels, fontsize=S.PT_MIN)
    ax.get_yticklabels()[-1].set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    for name, yh in heads:
        disp = ax.transData.transform((10, yh))
        fig.text(head_x / W, fig.transFigure.inverted().transform(disp)[1], name, ha="left", va="center",
                 fontsize=S.PT_MIN, fontweight="bold")
    tk = ticks or list(zip(TICKS, TICK_LABELS))
    ax.set_xticks([a for a, _ in tk])
    ax.set_xticklabels([b for _, b in tk])
    ax.minorticks_off()
    ax.set_xlabel("Time to answer every case (log scale)")
    # direct series labels on the first pair
    r0 = rows[0]
    ax.annotate(new_label, (r0["new"], ys[0] - off - 0.06), xytext=(10, 0),
                textcoords="offset points", color=S.OURS, va="center",
            fontsize=S.PT_MIN, fontweight="bold")
    ax.annotate("earlier method", (r0["old"], ys[0] + off), xytext=(10, 0), textcoords="offset points",
                color=S.MID, va="center", fontsize=S.PT_MIN)
    # totals at the bar ends
    ax.annotate(fmt_dur(tot["new"]), (tot["new"], ys[-1] - off - 0.06), xytext=(10, 0),
                textcoords="offset points", color=S.OURS, va="center",
            fontsize=S.PT_MIN, fontweight="bold")
    ax.annotate(fmt_dur(tot["old"]), (tot["old"], ys[-1] + off), xytext=(10, 0), textcoords="offset points",
                color=S.INK, va="center",
            fontsize=S.PT_MIN)
    # ratio column at the end of each pair
    xr = xr_in / W
    fig.text(xr, 1 - (t + ys[0] - 0.42) / H, "times faster", ha="right", va="center", fontsize=S.PT_MIN,
             color=S.MID)
    for i, y in enumerate(ys):
        disp = ax.transData.transform((10, y))
        yf = fig.transFigure.inverted().transform(disp)[1]
        is_tot = i == len(ys) - 1
        ratio = allrows[i]["ratio"]
        fig.text(xr, yf, f"{ratio:.0f}×", ha="right", va="center",
                 fontsize=S.PT_KEY_BIG if is_tot else S.PT_LABEL,
                 fontweight="bold", color=S.OURS if is_tot else S.INK)
    if footnote:
        fig.text(head_x / W, 1 - foot_y / H,
                 f"Earlier method estimated from 200 timed requests per cache.\n"
                 f"{dis} disagreements between the two methods in {ncases:,} cases.",
                 fontsize=S.PT_MIN, color=S.MID, ha="left", va="center", linespacing=1.25)
    return fig, ax, ys


def main():
    L = Ledger("F09", "Speed: earlier method against the deadline field")
    rows, tot, dis, ncases = read_data(L)
    fig, ax, _ = draw(rows, tot, dis, ncases)
    L.note("Machine: Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18, one pinned core (BENCH.md §1). "
           "Cold runs shown. Totals are sums of per-cache medians; their ratio equals the 129× in BENCH.md.")
    L.save()
    save(fig, "F09_speed")


if __name__ == "__main__":
    main()
