"""Counts for RESULTS.md from the run_panels.py outputs (PROTOCOL.md 7.3).

    python scripts/summarize.py PANEL_DIR OUT_JSON
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

THR = ("7", "4.7", "2.5")
SETTINGS = ("baseline", "fuel_low", "fuel_high", "T1090", "T1400", "vf_planar", "vf_max", "vf_cylinder", "no_tau")


def pct(v, ps):
    v = [x for x in v if x is not None]
    return [round(float(x), 1) for x in np.percentile(v, ps)] if v else None


def main():
    pdir, out = Path(sys.argv[1]), Path(sys.argv[2])
    res = {}
    for panel in ("A", "B"):
        files = sorted(pdir.glob("%s_*.json.gz" % panel))
        if not files:
            continue
        agg = {"inputs": len(files), "road_cell_rows": 0}
        cells = []
        leave = defaultdict(dict)  # variant -> {(input, origin): leave_by}
        latest = defaultdict(dict)
        halo = defaultdict(int)
        halo_cells = defaultdict(int)
        regions = set()
        for f in files:
            d = json.load(gzip.open(f, "rt"))
            regions.add(d["region"])
            key = d["region"] + "@" + d["issue_utc"]
            cells.extend(d["cells"])
            for v, rows in d["leave"].items():
                for oid, r in rows.items():
                    leave[v][(key, oid)] = r["leave_by"]
                    latest[v][(key, oid)] = r["latest"]
            for v, n in d["halo_pieces"].items():
                halo[v] += n
            for v, cl in d.get("halo_cells", {}).items():
                halo_cells[v] += len(cl)
        agg["regions"] = sorted(regions)
        agg["road_cell_rows"] = len(cells)
        # physics on road cells (baseline)
        agg["crown_share"] = round(float(np.mean([c["crown"] for c in cells])), 3) if cells else None
        agg["flame_length_m_p50_90_99_max"] = pct([c["flame_length_m"] for c in cells], [50, 90, 99, 100])
        agg["flame_height_m_p50_90_99_max"] = pct([c["flame_height_m"] for c in cells], [50, 90, 99, 100])
        agg["ros_m_min_p50_90_99"] = pct([c["ros_m_min"] for c in cells], [50, 90, 99])
        agg["fuel_groups"] = {g: sum(1 for c in cells if c["fuel_group"] == g) for g in sorted({c["fuel_group"] for c in cells})}
        for t in THR:
            ds = [c["dstar_%s_m" % t] for c in cells]
            agg["dstar_%s_m_p50_90_99_max" % t] = pct(ds, [50, 90, 99, 100])
            agg["share_dstar_%s_below_375m" % t] = round(float(np.mean([x < 375 for x in ds])), 4) if ds else None
            agg["lead_%s_s_p50_90_99_max" % t] = pct([c["lead_%s_s" % t] for c in cells], [50, 90, 99, 100])
            for s in SETTINGS[1:]:
                k = "dstar_%s_m_%s" % (t, s)
                v = [c.get(k) for c in cells if c.get(k) is not None]
                if v:
                    agg["dstar_%s_m_p50_90_max__%s" % (t, s)] = pct(v, [50, 90, 100])
                    agg["share_dstar_%s_below_375m__%s" % (t, s)] = round(float(np.mean([x < 375 for x in v])), 4)
        zones = defaultdict(int)
        for c in cells:
            zones[c.get("zone_from_adjacent") or "no earlier neighbour"] += 1
        agg["zone_from_adjacent_cell"] = dict(zones)
        agg["flux_from_adjacent_kw_m2_p50_90_99_max"] = pct([c.get("flux_from_adjacent_kw_m2") for c in cells], [50, 90, 99, 100])
        # closure changes on road cells: earliest piece closure in the cell
        def cell_close(c, v):
            return c.get("close_min_s_%s" % v)
        variants = sorted({k[len("close_min_s_"):] for c in cells for k in c if k.startswith("close_min_s_")})
        comp = {}
        for v in variants:
            if v == "none":
                continue
            ch_none = [cell_close(c, v) - cell_close(c, "none") for c in cells
                       if cell_close(c, v) is not None and cell_close(c, "none") is not None and cell_close(c, v) != cell_close(c, "none")]
            t = v.rsplit("_", 1)[1]
            rec = {"road_cells_changed_vs_none": len(ch_none), "shift_s_p50_max_vs_none": pct([-x for x in ch_none], [50, 100]),
                   "halo_pieces_outside_reached_cells": halo[v],
                   "unreached_road_cells_partly_closed_by_halo": halo_cells[v]}
            if not v.startswith("old_"):
                old = "old_" + t
                ch_old = [cell_close(c, v) - cell_close(c, old) for c in cells
                          if cell_close(c, v) is not None and cell_close(c, old) is not None and cell_close(c, v) != cell_close(c, old)]
                rec["road_cells_changed_vs_old"] = len(ch_old)
                rec["earlier_than_old"] = sum(1 for x in ch_old if x < 0)
                rec["later_than_old"] = sum(1 for x in ch_old if x > 0)
            # leave-by
            for ref in ("none",) + (() if v.startswith("old_") else ("old_" + t,)):
                base = leave[ref]
                diffs, lost, n = [], 0, 0
                for k, lb in base.items():
                    if lb is None:
                        continue
                    n += 1
                    nv = leave[v].get(k)
                    if nv is None:
                        lost += 1
                    elif nv != lb:
                        diffs.append(lb - nv)
                rec["leave_by_vs_%s" % ref.split("_")[0]] = {"with_leave_now_window": n, "changed": len(diffs) + lost,
                                                             "lost_window": lost, "shift_s_p50_max": pct(diffs, [50, 100]),
                                                             "later_than_ref": sum(1 for x in diffs if x < 0)}
                ldiff = [latest[ref][k] - latest[v][k] for k in latest[ref]
                         if latest[ref][k] is not None and latest[v].get(k) is not None and latest[ref][k] != latest[v][k]]
                rec["latest_departure_vs_%s" % ref.split("_")[0]] = {"changed": len(ldiff), "shift_s_p50_max": pct(ldiff, [50, 100])}
            comp[v] = rec
        agg["variants"] = comp
        res[panel] = agg
    out.write_text(json.dumps(res, indent=1))
    for p, a in res.items():
        print("== panel", p, a["inputs"], "inputs", a["regions"], "road cells", a["road_cell_rows"])
        for t in THR:
            print("  d*%s" % t, a["dstar_%s_m_p50_90_99_max" % t], "share<375", a["share_dstar_%s_below_375m" % t], "lead", a["lead_%s_s_p50_90_99_max" % t])
        for v in ("old_7", "old_4.7", "old_2.5", "baseline_7", "baseline_4.7", "baseline_2.5", "vf_max_4.7", "fuel_high_4.7", "T1400_4.7"):
            if v in a["variants"]:
                print("  ", v, json.dumps(a["variants"][v]))


if __name__ == "__main__":
    main()
