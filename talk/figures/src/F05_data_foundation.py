"""F05 data foundation (wildfireguardiandata v0.1), three panels, each headed by its result.

(a) the 207,508 US 2018–2020 agency records that no standard satellite product labelled, one bar per tier
    (verified / probable / record-only) on one linear axis, counts at the bar ends, the verified share with its
    Clopper-Pearson 95% interval. Source: results/HEADLINE_NUMBERS.md (table, slice S3).
(b) how much earlier the first label is than the first standard detection, for the 45 of 240 fires whose first
    label moved earlier; axis in minutes and hours; median and bootstrap interval from HEADLINE_NUMBERS.md.
(c) one real record before and after its reversible patches, trailing spaces drawn as small squares.
    Source: release/records-v0.1/patches_us.jsonl.gz; run size from run_summary_us.json; run time from
    results/RECORDS_RESULTS.md (R2).

The data repository is read only and is not cloned into this one. Its files are read from $WGD_DIR (default
talk/figures/.cache/wgd), filled by `make_all.sh` with `gh api` (see README.md).
"""
import csv
import gzip
import json
import os
import re
import statistics
from pathlib import Path

import numpy as np

import style as S
from matplotlib.patches import Rectangle

from figkit import add_caption, grid, save
from prov import Ledger

WGD = Path(os.environ.get("WGD_DIR", S.FIGDIR / ".cache" / "wgd"))
REPO = "Sparkxt-0318/wildfireguardiandata"
RECORD = "fod:1389433"


def commits():
    out = {}
    for line in (WGD / "COMMITS.txt").read_text().splitlines():
        p, h = line.split()
        out[p] = h
    return out


def read(L):
    C = commits()
    hn = (WGD / "HEADLINE_NUMBERS.md").read_text()
    m = re.search(r"\| S3 US 2018-2020 \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \(([\d.]+)-([\d.]+) %\) \| "
                  r"([\d,]+) \| ([\d,]+) \|", hn)
    rec, std, nostd, ver, lo, hi, prob, ronly = m.groups()
    toi = lambda x: int(x.replace(",", ""))  # noqa: E731
    nostd, ver, prob, ronly = toi(nostd), toi(ver), toi(prob), toi(ronly)
    kw = dict(repo_name=REPO, commit=C["results/HEADLINE_NUMBERS.md"], file="results/HEADLINE_NUMBERS.md")
    L.add("Records with no standard satellite label (US 2018–2020, S3)", nostd, field="table row S3, column "
          "'no standard label'", expected="207,508", **kw)
    L.add("Verified / probable / record-only", [ver, prob, ronly], field="table row S3, columns verified, probable, "
          "record-only", expected="4,343 / 20,913 / 182,252", **kw)
    L.add("Verified share, Clopper-Pearson 95% interval (%)", [float(lo), float(hi)], field="table row S3, verified "
          "(lo-hi %)", **kw)
    L.add("Verified share of the records with no standard label (%)", round(100 * ver / nostd, 1),
          shown=f"{100 * ver / nostd:.1f}%", field="computed: verified / no standard label, table row S3",
          expected="2.09 % (item 1 sentence)", **kw)
    assert ver + prob + ronly == nostd
    # (b) onset leads
    rows = list(csv.DictReader(open(WGD / "onset_labels.csv")))
    leads = [float(r["lead_vs_T0_min"]) for r in rows if r["lead_vs_T0_min"]]
    years = sorted({r["fire_id"][:4] for r in rows})
    m2 = re.search(r"median\s+lead over the first standard detection is (\d+) min \(fire bootstrap 95 %: (\d+)-(\d+) min\)",
                   hn.replace("\n", " "))
    med, clo, chi = (int(x) for x in m2.groups())
    kwb = dict(repo_name=REPO, commit=C["release/live-v0.1/onset_labels.csv"],
               file="release/live-v0.1/onset_labels.csv")
    L.add("Fires whose first label moved earlier", len(leads), shown=f"{len(leads)} of {len(rows)}",
          field="rows with lead_vs_T0_min present", n=f"{len(rows)} fires ({years[0]}–{years[-1]})",
          expected="45 of 240", **kwb)
    L.add("Median lead and bootstrap 95% interval (min)", [med, clo, chi], field="item 3 sentence", n="45 fires",
          expected="42 min", note=f"recomputed median of lead_vs_T0_min = {statistics.median(leads):.1f} min", **kw)
    # (c) one record's patches
    patches = []
    with gzip.open(WGD / "patches_us.jsonl.gz", "rt") as f:
        for line in f:
            d = json.loads(line)
            if d.get("record_id") == RECORD:
                patches.append(d)
    run = json.loads((WGD / "run_summary_us.json").read_text())
    n_rec = run["location"]["n_checked"]
    rr = (WGD / "RECORDS_RESULTS.md").read_text()
    secs, mins = re.search(r"\*\*met\*\*: (\d+) s \(([\d.]+) min\) for the national run", rr).groups()
    L.add("Patches of the example record", len(patches), file="release/records-v0.1/patches_us.jsonl.gz",
          field=f"lines with record_id == {RECORD}: field, old, new, rule", repo_name=REPO,
          commit=C["release/records-v0.1/patches_us.jsonl.gz"])
    L.add("Records in the national run", n_rec, shown=f"{n_rec / 1e6:.2f} million", repo_name=REPO,
          commit=C["release/records-v0.1/run_summary_us.json"], file="release/records-v0.1/run_summary_us.json",
          field="location.n_checked", expected="2.66 million")
    L.add("National run wall time", float(mins), unit="min", shown=f"{mins} minutes", repo_name=REPO,
          commit=C["results/RECORDS_RESULTS.md"], file="results/RECORDS_RESULTS.md",
          field=f"R2 wall time row: {secs} s ({mins} min)", expected="7.9 minutes")
    return dict(nostd=nostd, ver=ver, prob=prob, ronly=ronly, lo=float(lo), hi=float(hi), leads=leads, nfires=len(rows),
                years=years, med=med, clo=clo, chi=chi, patches=patches, n_rec=n_rec, mins=mins)


def trailing(v):
    """Value without its trailing spaces, and how many there were."""
    if isinstance(v, dict) and v.get("__missing__"):
        return "missing", 0
    s = str(v)
    return s.rstrip(), len(s) - len(s.rstrip())


def main():
    L = Ledger("F05", "Data foundation (wildfireguardiandata v0.1)")
    d = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    head_y = 0.42

    def heading(x, letter, text):
        S.panel_letter(fig, x, head_y, letter)
        fig.text((x + 0.42) / W, 1 - head_y / H, text, fontsize=S.PT_TEXT, va="center")

    # ---------------- (a) tiers, one linear axis
    la, ta, wa, ha = 1.75, 1.0, 2.35, 2.3
    ax = fig.add_axes([la / W, 1 - (ta + ha) / H, wa / W, ha / H])
    grid(ax, axis="x")
    tiers = [("verified", d["ver"], S.OURS, None), ("probable", d["prob"], S.LIGHT, "///"),
             ("record-only", d["ronly"], S.WHITE, None)]
    for i, (name, n, col, hatch) in enumerate(tiers):
        ax.barh(i, n, height=0.6, facecolor=col, edgecolor=S.INK, linewidth=0.6, hatch=hatch)
        ax.annotate(f"{n:,}", (n, i), xytext=(8, 0), textcoords="offset points", va="center")
    ax.set_yticks(range(3))
    ax.set_yticklabels([t[0] for t in tiers])
    ax.set_ylim(2.6, -0.6)
    ax.set_xlim(0, 330000)
    ax.set_xticks([0, 100000, 200000])
    ax.set_xticklabels(["0", "100k", "200k"])
    grid(ax, axis="x")
    ax.set_xlabel("US fire records, 2018–2020", labelpad=S.LABEL_PAD)
    heading(0.45, "a", "Records with no satellite label")
    share = 100 * d["ver"] / d["nostd"]
    fig.text(0.45 / W, 1 - 4.45 / H, f"verified: {share:.1f}% ({d['lo']}–{d['hi']}%)\nnot yet checked for false labels",
             va="top", linespacing=1.3)
    # ---------------- (b) how much earlier
    lb, tb, wb, hb = 6.3, 1.0, 1.65, 3.55
    axb = fig.add_axes([lb / W, 1 - (tb + hb) / H, wb / W, hb / H])
    axb.set_yscale("log")
    grid(axb, axis="y")
    rng = np.random.RandomState(4)
    xs = rng.uniform(-0.25, 0.25, len(d["leads"]))
    axb.scatter(xs, d["leads"], s=28, marker="o", facecolors=S.WHITE, edgecolors=S.OURS, linewidths=1.0)
    axb.errorbar([0.6], [d["med"]], yerr=[[d["med"] - d["clo"]], [d["chi"] - d["med"]]], fmt="s", ms=7,
                 color=S.INK, ecolor=S.INK, elinewidth=1.0, capsize=4)
    axb.text(0.85, d["med"], f"median\n{d['med']} min", va="center", ha="left", linespacing=1.2)
    axb.set_xlim(-0.45, 2.3)
    axb.set_xticks([])
    axb.set_ylim(0.5, 1000)
    axb.set_yticks([1, 10, 60, 600])
    axb.set_yticklabels(["1 min", "10 min", "1 h", "10 h"])
    axb.minorticks_off()
    axb.set_ylabel("Earlier than first\nsatellite detection", labelpad=S.LABEL_PAD)
    heading(4.95, "b", f"Earlier for {len(d['leads'])} of {d['nfires']} fires")
    # ---------------- (c) one record before and after
    lc, xr = 8.45, 12.95
    heading(lc, "c", "One record, cleaned reversibly")
    xv = lc + 0.9
    sq, pitch = 0.065, 0.08
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    y = 1.05
    fig.add_artist(S.plt.Line2D([lc / W, xr / W], [1 - y / H] * 2, color=S.INK, lw=1.2))
    dy = 0.385
    n_sp = []
    for i, p in enumerate(d["patches"]):
        y += 0.28
        fig.text(lc / W, 1 - y / H, p["field"], va="center", color=S.MID)
        for key, word in (("old", "before"), ("new", "after")):
            y += dy
            val, k = trailing(p[key])
            fig.text(lc / W, 1 - y / H, word, va="center")
            t = fig.text(xv / W, 1 - y / H, val, va="center", color=S.OURS if key == "new" else S.INK)
            n_sp.append(k)
            if k:
                x_end = t.get_window_extent(rend).x1 / S.DPI + 0.12
                for j in range(k):
                    r = Rectangle(((x_end + j * pitch) / W, 1 - (y + sq / 2) / H), sq / W, sq / H,
                                  transform=fig.transFigure, facecolor=S.FIRE, edgecolor="none")
                    r.set_gid("bg:space")
                    fig.add_artist(r)
        y += 0.22
        if i < len(d["patches"]) - 1:
            fig.add_artist(S.plt.Line2D([lc / W, xr / W], [1 - y / H] * 2, color=S.INK, lw=0.5))
    fig.add_artist(S.plt.Line2D([lc / W, xr / W], [1 - y / H] * 2, color=S.INK, lw=1.2))
    yk = 0.82
    r = Rectangle((lc / W, 1 - (yk + sq / 2) / H), sq / W, sq / H, transform=fig.transFigure, facecolor=S.FIRE,
                  edgecolor="none")
    r.set_gid("bg:legend handle")
    fig.add_artist(r)
    fig.text((lc + 0.2) / W, 1 - yk / H, "one hidden trailing space", va="center")
    fig.text(lc / W, 1 - (y + 0.22) / H, f"Whole US file: {d['n_rec'] / 1e6:.2f} million\nrecords in {d['mins']} min",
             va="top", linespacing=1.2)
    cap = add_caption(fig, (
        f"Figure 5. (a) Of {d['nostd']:,} US fire records (2018–2020) that no standard satellite product "
        f"labelled, {d['ver']:,} are verified ({share:.1f}%, 95% interval {d['lo']}–{d['hi']}%); how many verified "
        f"labels are false has not been measured. (b) For {len(d['leads'])} of {d['nfires']} fires "
        f"({d['years'][0]}–{d['years'][-1]}) the first label is earlier than the first standard satellite detection "
        f"(median {d['med']} min, bootstrap 95%: {d['clo']}–{d['chi']} min); this onset "
        f"is not shown to be the ignition. (c) Each patch keeps the old value and its rule. Source: wildfireguardiandata v0.1."),
        x_in=0.45, width_in=12.45, top_in=5.95)
    L.add("Trailing spaces drawn per value (before, after)", n_sp, file="release/records-v0.1/patches_us.jsonl.gz",
          field=f"len(old) - len(old.rstrip()) and the same for new, record {RECORD}", repo_name=REPO,
          commit=commits()["release/records-v0.1/patches_us.jsonl.gz"])
    L.save()
    save(fig, "F05_data_foundation", caption=cap)


if __name__ == "__main__":
    main()
