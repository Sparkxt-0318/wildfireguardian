"""F09 speed: earlier method against the deadline field, six recorded caches and the total.

Slide 9, right two thirds. Log time axis, one pair of bars per cache, ratio at the end of each pair.
Source: research/kcf-bench/results_hostB/summary.json and accuracy/*.json (kcf-bench, host B).
"""
import re
from datetime import datetime, timedelta, timezone

import numpy as np

import style as S
from figkit import add_caption, grid, save
from prov import Ledger

BENCH = "research/kcf-bench"
SUMMARY = f"{BENCH}/results_hostB/summary.json"

CACHES = [
    ("uiseong_andong_2025/20250323T010000Z", "Uiseong–Andong"),
    ("uiseong_andong_2025/20250324T090000Z", "Uiseong–Andong"),
    ("uiseong_andong_2025/20250325T170000Z", "Uiseong–Andong"),
    ("yeongdeok_2025/20250325T190000Z", "Yeongdeok"),
    ("yeongdeok_2025/20250325T230000Z", "Yeongdeok"),
    ("yeongdeok_2025/20250326T080000Z", "Yeongdeok"),
]
KST = timezone(timedelta(hours=9), "KST")
SCAN = "product/wfg-roadlayer/examples/SCAN.md"   # the replay's issue hours, one row per hour and region
OLD_NAME = "search per village (earlier)"
NEW_NAME = "one backward pass (ours)"


def kst_label(key):
    """cache key ...T010000Z -> '23 Mar, 10:00 KST' (the cache's input time in Korean local time)."""
    t = datetime.strptime(key.split("/")[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(KST)
    return f"{t.day} {t:%b} {t:%H:%M} KST"


def update_interval(L):
    """Spacing of consecutive issue hours in the hourly replay table (minutes), per region; must be one value."""
    txt = L.text(SCAN)
    rows = re.findall(r"^\| (\d\d):00 \| (\w+) \|", txt, flags=re.M)
    by = {}
    for hh, reg in rows:
        by.setdefault(reg, []).append(int(hh) * 60)
    gaps = {g for v in by.values() for g in np.diff(v)}
    assert len(gaps) == 1, gaps
    gap = int(gaps.pop())
    L.add("Forecast update interval (spacing of the replay's issue hours)", gap, unit="min", shown="hourly",
          file=SCAN, field="difference between consecutive 'issue KST' rows of the table, per region",
          n=f"{len(rows)} issue-hour rows, {len(by)} regions",
          note="cross-check: research/kcf-abstain/PROTOCOL.md asks its question 'at an hourly issue time'")
    return gap * 60

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
    for key, place in CACHES:
        when = kst_label(key)
        c = d["caches"][key]
        old = c["old"]["cold"]["scaled"]["median"]
        new = c["field"]["field"]["cold"]["median"]
        ratio = c["ratios"]["old/field/cold"]["median"]
        n = c["n_cases"]
        lab = f"{place}, {when}"
        # places (villages and care facilities) whose routes the cache checks: the planner requests' origins.
        # The bench case file records the cache's SHA-256, so the count is taken from exactly the timed cache.
        cases_file = f"{BENCH}/cases/{key.replace('/', '__')}.json"
        cf = L.json(cases_file)
        import hashlib
        from prov import git_show
        raw = git_show(f"planner/cache/{key}.json")
        assert hashlib.sha256(raw).hexdigest() == cf["cache_sha256"], key
        import json as _json
        pc = _json.loads(raw)
        places = len({o["id"] for r in pc["requests"] for o in r["origins"]})
        assert cf["n_cases"] == c["n_cases"]
        L.add(f"{lab}: places checked", places, file=f"planner/cache/{key}.json",
              field="distinct requests[*].origins[*].id (SHA-256 equal to cases file cache_sha256)",
              note="1-2 further case origins per cache are synthetic research checks (research_checks) and are not "
                   "counted as places; their cases are in the case count")
        L.add(f"{lab}: route checks timed", c["n_cases"], shown=f"{c['n_cases']:,} checks", file=SUMMARY,
              field=f"caches['{key}'].n_cases", note=f"equal to n_cases in {cases_file}")
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
        rows.append(dict(key=key, place=place, places=places, when=when,
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
    for key, _ in CACHES:
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


def row_labels(rows, tot):
    return [f"{r['when']}, {r['n']:,} checks" for r in rows] + [f"all six hours, {tot['n']:,} checks"]


def row_positions(rows):
    """y of each row (regions separated by a header line) and of each region header."""
    ys, heads, y, prev = [], [], 0.0, None
    for r in rows:
        if r["place"] != prev:
            y += 0.85 if prev is None else 1.9
            heads.append((y - 0.85, r["place"]))
            prev = r["place"]
        else:
            y += 1.0
        ys.append(y)
    return ys + [ys[-1] + 1.45], heads


def draw(rows, tot, fig=None, rect=(3.75, 1.1, 8.7, 4.15), xlim=(8, 2e6), ticks=None, hourly=None, ratio_word=True,
         total_ratio=True, ylabels=True):
    """Framed log axis, gridlines, whiskers = range over the five repeats; optional line at the update interval.
    Returns fig, ax and the two bar handles for a legend placed by the caller."""
    fig = fig or S.new_figure()
    W, H = S.W_IN, S.H_IN
    l, t, w, h = rect
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    ax.set_xscale("log")
    ax.set_xlim(*xlim)
    grid(ax, axis="x")
    allrows = rows + [tot]
    n = len(allrows)
    ys, heads = row_positions(rows)
    bh = 0.34
    hd = []
    for k, (y0, r) in enumerate(zip(ys, allrows)):
        b1 = ax.barh(y0 - bh / 2, r["old"] - X0, left=X0, height=bh, facecolor=S.LIGHT, edgecolor=S.INK,
                     hatch="///", linewidth=0.6, label=OLD_NAME if k == 0 else None)
        b2 = ax.barh(y0 + bh / 2, r["new"] - X0, left=X0, height=bh, facecolor=S.OURS, edgecolor=S.INK,
                     linewidth=0.6, label=NEW_NAME if k == 0 else None)
        if k == 0:
            hd = [b1, b2]
        ax.errorbar(r["old"], y0 - bh / 2, xerr=[[r["old"] - r["old_lo"]], [r["old_hi"] - r["old"]]], fmt="none",
                    ecolor=S.INK, elinewidth=1.0, capsize=3)
        ax.errorbar(r["new"], y0 + bh / 2, xerr=[[r["new"] - r["new_lo"]], [r["new_hi"] - r["new"]]], fmt="none",
                    ecolor=S.INK, elinewidth=1.0, capsize=3)
        if k < n - 1 or total_ratio:
            txt = f"{r['ratio']:.0f}× faster" if ratio_word else f"{r['ratio']:.0f}×"
            ax.annotate(txt, (r["old_hi"], y0 - bh / 2), xytext=(8, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=S.PT_TEXT)
    ax.set_ylim(ys[-1] + 0.7, heads[0][0] - 0.55)
    ax.set_yticks(ys)
    ax.set_yticklabels(row_labels(rows, tot) if ylabels else [])
    ax.tick_params(axis="y", length=0)
    if ylabels:
        from matplotlib.transforms import blended_transform_factory
        tr = blended_transform_factory(fig.transFigure, ax.transData)
        for yh, place in heads:
            npl = {r["places"] for r in rows if r["place"] == place}
            assert len(npl) == 1, (place, npl)
            fig.text(0.45 / W, yh, f"{place}, {npl.pop()} places", transform=tr, ha="left", va="center",
                     fontsize=S.PT_TEXT, style="italic")
    tk = ticks or list(zip(TICKS, TICK_LABELS))
    ax.set_xticks([a for a, _ in tk])
    ax.set_xticklabels([b for _, b in tk])
    ax.minorticks_off()
    ax.set_xlabel("Time to check every village's routes")
    if hourly:
        ln = ax.axvline(hourly, color=S.INK, lw=1.4, ls=(0, (5, 3)), zorder=4)
        ln.set_gid("hourly")
        ax.annotate("forecasts update hourly", (hourly, 1.0), xycoords=("data", "axes fraction"), xytext=(0, 8),
                    textcoords="offset points", ha="center", va="bottom", fontsize=S.PT_TEXT)
    return fig, ax, hd


def legend_row(fig, handles, labels, x_center_in, y_in):
    W, H = S.W_IN, S.H_IN
    leg = fig.legend(handles, labels, loc="center", bbox_to_anchor=(x_center_in / W, 1 - y_in / H), ncol=len(handles),
                     columnspacing=2.0, handleheight=0.9, handlelength=1.8)
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_gid("box:legend")
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    return leg


def caption_text(tot, dis, ncases, num="9"):
    return (f"Figure {num}. Time to check every route of every place (village or care facility) for six forecast hours "
            "of the March 2025 fires, one server core, log time axis. A check: one place, shelter and departure time. Bars: median "
            "of 5 cold repeats; whiskers: range; earlier method scaled from 200 timed checks per hour. "
            f"{dis} disagreements in {ncases:,} checks. Source: research/kcf-bench.")


def main():
    L = Ledger("F09", "Speed: earlier method against the deadline field")
    rows, tot, dis, ncases = read_data(L)
    hourly = update_interval(L)
    fig, ax, hd = draw(rows, tot, hourly=hourly)
    pos = ax.get_position()
    legend_row(fig, hd, [OLD_NAME, NEW_NAME], (pos.x0 + pos.width / 2) * S.W_IN, 0.32)
    L.note("Machine: Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18, one pinned core (BENCH.md §1). "
           "Cold runs shown. Totals are sums of per-cache medians; their ratio equals the 129× in BENCH.md.")
    L.save()
    cap = add_caption(fig, caption_text(tot, dis, ncases), x_in=0.45, width_in=12.45, top_in=6.42)
    save(fig, "F09_speed", caption=cap)


if __name__ == "__main__":
    main()
