"""Table, CSV and figure of the extended-horizon exploratory panel (never pooled with the frozen counts).

  python research/synthetic-truth/analyze_extended.py [--prefix FIXTURE]
"""
import argparse
import collections
import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import figures as FG  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="FIXTURE")
    a = ap.parse_args()
    d = HERE / "data" / "extended_panel"
    with gzip.open(d / ("%s_extended_records.jsonl.gz" % a.prefix), "rt") as f:
        rows = [json.loads(l) for l in f]
    groups = collections.OrderedDict()
    for r in rows:
        groups.setdefault((r["horizon_s"] // 3600, r["law"]), []).append(r)
    table = []
    for (h, law), rs in groups.items():
        n = len(rs)
        clair = [r for r in rs if r["clairvoyant_status"] == "ROUTE"]
        fs = sum(1 for r in rs if r["false_safe"])
        fr = sum(1 for r in clair if r["false_refusal"])
        v = collections.Counter(r["verdict"] for r in rs)
        table.append({"data": a.prefix, "panel": rs[0]["panel"], "horizon_h": h, "law": law, "cases": n,
                      "missions": len({r["mission"] for r in rs}), "checked_route": v.get("checked_route", 0),
                      "model_no_route": v.get("model_no_route", 0), "unresolved": v.get("unresolved", 0), "false_safe": fs,
                      "false_safe_wilson95": FG.wilson(fs, n), "false_refusal": fr, "cases_with_clairvoyant_route": len(clair),
                      "missions_with_false_safe": sorted({r["mission"] for r in rs if r["false_safe"]})})
    with open(HERE / ("EXTENDED_%s_SUMMARY.csv" % a.prefix), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        for t in table:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, tuple)) else v) for k, v in t.items()})
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.SINGLE + 0.8, 2.4))
    labels = ["%d h\n%s" % (t["horizon_h"], t["law"].replace("_", " ")) for t in table]
    x = np.arange(len(table))
    ax.bar(x - 0.2, [t["false_safe"] / t["cases"] for t in table], 0.38, color=FG.OKABE_ITO["vermillion"], label="false-safe")
    ax.bar(x + 0.2, [t["false_refusal"] / max(1, t["cases_with_clairvoyant_route"]) for t in table], 0.38,
           color=FG.OKABE_ITO["blue"], label="false-refusal")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6)
    ax.set_ylabel("rate (fraction of cases)")
    ax.set_title("%s: extended-horizon exploratory panel, not frozen missions" % a.prefix, fontsize=7)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    FG.save(fig, HERE / "figures", "fig06_extended_horizon_%s" % a.prefix.lower())
    print(json.dumps(table, indent=0, default=str))


if __name__ == "__main__":
    main()
