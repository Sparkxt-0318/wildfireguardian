"""Summarise the 1-hour heat reruns: reproduction of F-3.1's committed cert deadlines, and the heat effect per cache.

    python scripts/c2_summarize.py OUT.json SUMMARY_JSON...

'Leave-by' is F-3.1's exact 1-second planner deadline: the latest departure in [0, last planner offset] with a
feasible journey (field_deadline_exact_<variant>); the 10-minute grid deadline is reported beside it.
A place 'loses its route' when cert has a feasible departure in that range and cert_heat has none.
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMMITTED = ROOT / "research" / "harness-2026-11" / "F-3.1" / "results" / "DEADLINES_per_origin.json"


def main(out, *paths):
    committed = {(r["cache"], r["origin"]): r for r in json.loads(COMMITTED.read_text())}
    rows, total = [], {"origins": 0, "with_leave_by": 0, "moved": 0, "moved_grid": 0, "lost": 0, "reproduced": 0,
                       "compared": 0, "shifts": []}
    for p in sorted(paths):
        s = json.loads(Path(p).read_text())
        cache = s["cache_file"]
        o = s["origins"]
        rep = cmp_ = 0
        shifts, grid_moved, lost, with_lb = [], 0, 0, 0
        for oid, r in o.items():
            c = committed.get((cache, oid))
            if c is not None:
                cmp_ += 1
                rep += all(c[k] == r[k] for k in ("field_deadline_grid_cert", "field_deadline_exact_cert",
                                                  "field_deadline_exact_uncapped_cert"))
            a, b = r["field_deadline_exact_cert"], r["field_deadline_exact_cert_heat"]
            if a is None:
                continue
            with_lb += 1
            if b is None:
                lost += 1
            elif b != a:
                shifts.append(a - b)
            ga, gb = r["field_deadline_grid_cert"], r["field_deadline_grid_cert_heat"]
            grid_moved += (ga != gb)
        row = {"cache": cache, "origins": len(o), "with_leave_by": with_lb, "moved": len(shifts), "moved_grid": grid_moved,
               "lost": lost, "shift_median_s": statistics.median(shifts) if shifts else None,
               "shift_max_s": max(shifts) if shifts else None, "shift_min_s": min(shifts) if shifts else None,
               "cert_reproduces_F31": "%d/%d" % (rep, cmp_), "heat_rule": s["heat_rule"],
               "field_time_s": s["timing_s"]["fields"], "peak_rss_mib": s["peak_rss_mib"]}
        rows.append(row)
        for k in ("origins", "with_leave_by", "moved", "moved_grid", "lost"):
            total[k] += row[k]
        total["reproduced"] += rep; total["compared"] += cmp_; total["shifts"] += shifts
    sh = total.pop("shifts")
    total.update(shift_median_s=statistics.median(sh) if sh else None, shift_max_s=max(sh) if sh else None,
                 shift_min_s=min(sh) if sh else None, shift_hist={b: sum(1 for v in sh if lo <= v < hi) for b, (lo, hi) in
                                                                   {"1-60": (1, 61), "61-120": (61, 121), "121-350": (121, 351),
                                                                    ">350": (351, 10 ** 9)}.items()})
    Path(out).write_text(json.dumps({"per_cache": rows, "total": total}, indent=1) + "\n")
    for r in rows:
        print("%-55s origins %3d with-LB %3d moved %3d (grid %3d) lost %2d shift med %s max %s  cert==F31 %s" % (
            r["cache"], r["origins"], r["with_leave_by"], r["moved"], r["moved_grid"], r["lost"], r["shift_median_s"],
            r["shift_max_s"], r["cert_reproduces_F31"]))
    print("TOTAL", json.dumps(total))


if __name__ == "__main__":
    main(*sys.argv[1:])
