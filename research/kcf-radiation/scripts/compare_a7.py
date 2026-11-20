"""PROTOCOL A7: old table and new table side by side, and every leave-by time that changes because of the fix.

    python scripts/compare_a7.py OUT_DIR   # OUT_DIR from run_panels_a7.py (old/, new/, log/); runs summarize.py on both
Writes OUT_DIR/summary_old.json, summary_new.json, A7_table.md, A7_leave_by_changes.csv, A7_fix_log.json.
"""
from __future__ import annotations

import csv
import gzip
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = [("old_7", "old law, 7"), ("old_4.7", "old law, 4.7"), ("old_2.5", "old law, 2.5"),
        ("baseline_7", "baseline, 7"), ("baseline_4.7", "baseline, 4.7"), ("baseline_2.5", "baseline, 2.5"),
        ("fuel_low_4.7", "4.7, fuel low"), ("fuel_high_4.7", "4.7, fuel high"), ("T1090_4.7", "4.7, 1090 K"),
        ("T1400_4.7", "4.7, 1400 K"), ("vf_max_4.7", "4.7, worst angle"), ("vf_planar_4.7", "4.7, vertical plane"),
        ("vf_cylinder_4.7", "4.7, Mudan cylinder"), ("no_tau_4.7", "4.7, no transmissivity")]


def cell(a, v):
    r = a["variants"].get(v)
    if r is None:
        return None
    lb = r["leave_by_vs_none"]
    sh = lb["shift_s_p50_max"]
    shift = "%.1f/%.1f" % (sh[0] / 60, sh[1] / 60) if sh else "-"
    vs = r.get("leave_by_vs_old")
    return {"cells": r["road_cells_changed_vs_none"], "halo": r["unreached_road_cells_partly_closed_by_halo"],
            "changed": lb["changed"], "lost": lb["lost_window"], "shift": shift,
            "vs_old": "%d (%d later)" % (vs["changed"], vs["later_than_ref"]) if vs else "-", "n": lb["with_leave_now_window"]}


def main():
    out = Path(sys.argv[1])
    for rule in ("old", "new"):
        subprocess.run([sys.executable, str(HERE / "summarize.py"), str(out / rule), str(out / ("summary_%s.json" % rule))],
                       check=True, stdout=subprocess.DEVNULL)
    S = {r: json.loads((out / ("summary_%s.json" % r)).read_text()) for r in ("old", "new")}
    md = []
    for panel, title in (("A", "A replay"), ("B", "B packets")):
        if panel not in S["old"]:
            continue
        n = cell(S["old"][panel], "baseline_4.7")["n"]
        md.append("**Panel %s** (%d place-inputs with a leave-now window). Old rule = flat known-fire cells at the 150 m/min cap; "
                  "new rule = nearest real-gradient spread rate (A7). Same columns as RESULTS.md.\n" % (title, n))
        md.append("| heat rule | road cells closed earlier (old → new) | unreached cells partly closed (old → new) | "
                  "leave-by times changed (old → new) | windows lost (old → new) | shift median/max, min (old → new) | "
                  "vs old law (old → new) |")
        md.append("|---|---|---|---|---|---|---|")
        for v, label in ROWS:
            o, w = cell(S["old"][panel], v), cell(S["new"][panel], v)
            if o is None or w is None:
                continue
            md.append("| %s | %d → %d | %d → %d | %d → %d | %d → %d | %s → %s | %s → %s |" % (
                label, o["cells"], w["cells"], o["halo"], w["halo"], o["changed"], w["changed"], o["lost"], w["lost"],
                o["shift"], w["shift"], o["vs_old"], w["vs_old"]))
        md.append("")
    (out / "A7_table.md").write_text("\n".join(md))
    # every leave-by time that differs between the rules
    changes = []
    totals = defaultdict(int)
    for f in sorted((out / "new").glob("*.json.gz")):
        new = json.load(gzip.open(f, "rt"))
        old = json.load(gzip.open(out / "old" / f.name, "rt"))
        for v in new["leave"]:
            for oid, nr in new["leave"][v].items():
                orr = old["leave"][v].get(oid)
                totals[(new["panel"], v)] += 0
                if orr is None:
                    continue
                if orr["leave_by"] != nr["leave_by"]:
                    changes.append({"panel": new["panel"], "region": new["region"], "issue_utc": new["issue_utc"],
                                    "variant": v, "origin": oid, "old_rule_leave_by_s": orr["leave_by"],
                                    "new_rule_leave_by_s": nr["leave_by"],
                                    "delta_min": None if orr["leave_by"] is None or nr["leave_by"] is None
                                    else round((nr["leave_by"] - orr["leave_by"]) / 60, 2)})
    with open(out / "A7_leave_by_changes.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["panel", "region", "issue_utc", "variant", "origin", "old_rule_leave_by_s",
                                           "new_rule_leave_by_s", "delta_min"])
        w.writeheader()
        w.writerows(changes)
    per = defaultdict(int)
    for c in changes:
        per[(c["panel"], c["variant"])] += 1
    print("leave-by times that differ between the rules:", len(changes))
    for k in sorted(per):
        print("  ", k, per[k])
    logs = [json.loads(p.read_text()) for p in sorted((out / "log").glob("*.json"))]
    (out / "A7_fix_log.json").write_text(json.dumps(logs, indent=1))
    print(open(out / "A7_table.md").read())


if __name__ == "__main__":
    main()
