"""F05 data foundation (wildfireguardiandata v0.1), three panels.

(a) the 207,508 US 2018–2020 agency records that no standard satellite product labelled, split by tier
    (verified / probable / record-only), with a zoomed view of the small tiers; whisker = Clopper-Pearson 95% interval
    of the verified share. Source: results/HEADLINE_NUMBERS.md (table, slice S3).
(b) lead of the earlier onset over the first standard detection, for the 45 of 240 fires whose first label moved
    earlier. Source: release/live-v0.1/onset_labels.csv (lead_vs_T0_min); median and CI from HEADLINE_NUMBERS.md.
(c) one real record before and after its reversible patches. Source: release/records-v0.1/patches_us.jsonl.gz;
    run size from run_summary_us.json; run time from results/RECORDS_RESULTS.md (R2).

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
from figkit import add_caption, boxed_legend, grid, save
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


def show(v):
    if isinstance(v, dict) and v.get("__missing__"):
        return "(missing)"
    s = str(v)
    k = len(s) - len(s.rstrip())
    return s.rstrip() + (f" ␣×{k}" if k else "")


def main():
    L = Ledger("F05", "Data foundation (wildfireguardiandata v0.1)")
    d = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    # ---------------- (a) tiers
    la, ta, wa, ha = 1.6, 0.85, 2.3, 0.55
    ax = fig.add_axes([la / W, 1 - (ta + ha) / H, wa / W, ha / H])
    segs = [("verified", d["ver"], S.OURS, None), ("probable", d["prob"], S.LIGHT, "///"),
            ("record-only", d["ronly"], S.WHITE, None)]
    x = 0
    for name, n, col, hatch in segs:
        ax.barh(0, n, left=x, height=0.8, facecolor=col, edgecolor=S.INK, linewidth=0.6, hatch=hatch, label=name)
        x += n
    ax.set_xlim(0, d["nostd"])
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xticks([0, 100000, 200000])
    ax.set_xticklabels(["0", "100k", "200k"])
    ax.set_xlabel("Records")
    # zoom: the two small tiers, with the verified interval
    tz, hz = 2.65, 1.55
    az = fig.add_axes([la / W, 1 - (tz + hz) / H, wa / W, hz / H])
    grid(az, axis="x")
    vals = [("verified", d["ver"], S.OURS, None), ("probable", d["prob"], S.LIGHT, "///")]
    for i, (name, n, col, hatch) in enumerate(vals):
        az.barh(i, n, height=0.55, facecolor=col, edgecolor=S.INK, linewidth=0.6, hatch=hatch)
        az.annotate(f"{n:,}", (n, i), xytext=(10 if i else 22, 0), textcoords="offset points", va="center")
    lo, hi = d["lo"] / 100 * d["nostd"], d["hi"] / 100 * d["nostd"]
    az.errorbar(d["ver"], 0, xerr=[[d["ver"] - lo], [hi - d["ver"]]], fmt="none", ecolor=S.INK, elinewidth=1.0,
                capsize=3)
    az.set_yticks([0, 1])
    az.set_yticklabels(["verified", "probable"])
    az.set_ylim(1.6, -0.6)
    az.set_xlim(0, 40000)
    az.set_xticks([0, 20000, 40000])
    az.set_xticklabels(["0", "20k", "40k"])
    az.set_xlabel("Records (zoom)")
    S.panel_letter(fig, 0.45, 0.42, "a")
    fig.text(0.85 / W, 1 - 0.42 / H, "United States data, 2018 to 2020", fontsize=S.PT_TEXT, va="center")
    # ---------------- (b) leads
    lb, tb, wb, hb = 5.85, 0.85, 1.3, 3.35
    axb = fig.add_axes([lb / W, 1 - (tb + hb) / H, wb / W, hb / H])
    axb.set_yscale("log")
    grid(axb, axis="y")
    rng = np.random.RandomState(4)
    xs = rng.uniform(-0.25, 0.25, len(d["leads"]))
    axb.scatter(xs, d["leads"], s=28, marker="o", facecolors=S.WHITE, edgecolors=S.OURS, linewidths=1.0)
    axb.errorbar([0.55], [d["med"]], yerr=[[d["med"] - d["clo"]], [d["chi"] - d["med"]]], fmt="s", ms=7,
                 color=S.INK, ecolor=S.INK, elinewidth=1.0, capsize=4)
    axb.set_xlim(-0.5, 0.9)
    axb.set_xticks([])
    axb.set_ylim(0.5, 1000)
    axb.set_yticks([1, 10, 100, 1000])
    axb.set_yticklabels(["1", "10", "100", "1,000"])
    axb.set_ylabel("Lead over first standard\ndetection (min)")
    S.panel_letter(fig, 4.3, 0.42, "b")
    fig.text(4.75 / W, 1 - 0.42 / H, f"{len(d['leads'])} of {d['nfires']} fires", fontsize=S.PT_TEXT, va="center")
    # ---------------- (c) record before and after
    lc = 7.45
    S.panel_letter(fig, lc - 0.25, 0.42, "c")
    fig.text((lc + 0.15) / W, 1 - 0.42 / H, f"record {d['patches'][0]['record_id']}", fontsize=S.PT_TEXT, va="center")
    cols = [lc, lc + 2.45]
    y0 = 0.85
    for k, (title, key) in enumerate((("before", "old"), ("after", "new"))):
        yt = y0 + k * 2.15
        fig.add_artist(S.plt.Line2D([lc / W, 12.95 / W], [1 - yt / H] * 2, color=S.INK, lw=1.2))
        fig.text(cols[0] / W, 1 - (yt + 0.25) / H, "field", va="center")
        fig.text(cols[1] / W, 1 - (yt + 0.25) / H, title, va="center")
        fig.add_artist(S.plt.Line2D([lc / W, 12.95 / W], [1 - (yt + 0.5) / H] * 2, color=S.INK, lw=0.7))
        for i, p in enumerate(d["patches"]):
            yy = yt + 0.5 + 0.38 * (i + 0.55)
            fig.text(cols[0] / W, 1 - yy / H, p["field"], va="center")
            t = fig.text(cols[1] / W, 1 - yy / H, show(p[key]), va="center")
            if key == "new":
                t.set_bbox(dict(boxstyle="square,pad=0.15", facecolor="none", edgecolor=S.INK, linewidth=0.8))
        yb = yt + 0.5 + 0.38 * len(d["patches"]) + 0.12
        fig.add_artist(S.plt.Line2D([lc / W, 12.95 / W], [1 - yb / H] * 2, color=S.INK, lw=1.2))
    fig.text(lc / W, 1 - 4.85 / H, "reversible patch: every change is stored\nwith its old value and its rule",
             va="top", linespacing=1.2)
    cap = add_caption(fig, (
        f"Figure 5. United States data. (a) Of {d['nostd']:,} agency fire records (2018 to 2020) that no standard "
        f"satellite product labelled, {d['ver']:,} are verified (blue; whisker: 95% interval, {d['lo']}–{d['hi']}%), "
        f"{d['prob']:,} probable (hatched) and {d['ronly']:,} record-only (white). (b) For {len(d['leads'])} of {d['nfires']} fires "
        f"({d['years'][0]}–{d['years'][-1]}) the first label moved earlier; median lead {d['med']} min (bootstrap 95%: "
        f"{d['clo']}–{d['chi']} min; square with whiskers), each circle one fire. (c) One record's patches (␣×k = k trailing spaces); boxed cells changed. The national "
        f"run cleaned {d['n_rec'] / 1e6:.2f} million records in {d['mins']} minutes. Source: wildfireguardiandata "
        "results/HEADLINE_NUMBERS.md and release v0.1."), x_in=0.45, width_in=12.45, top_in=5.78)
    L.save()
    spec = {"type": "bar_stacked", "categories": ["records"],
            "series": [{"name": n, "values": [v], "color": c} for n, v, c, _ in segs],
            "x_title": "Records", "x_max": d["nostd"]}
    save(fig, "F05_data_foundation", caption=cap, charts=[(ax, spec)])


if __name__ == "__main__":
    main()
