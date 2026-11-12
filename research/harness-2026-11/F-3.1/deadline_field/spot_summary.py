"""Spotting-distance envelope summary (rule: SPOTTING_RULE.md, committed before tabulating).

Per region-start and d (never pooled): per place contiguous deadline (merged rule: end of the feasible piece that
contains t = 0, CERT field) and its shift against d = 0; counts as in the rule; control d = 0 vs the kriged_mean field.
Research variant: packets as built (fixed burning duration, reopening after burn-out), not the no-re-entry headline arm.
    python3 -m deadline_field.spot_summary --spot DIR --control DIR --out OUT
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def contiguous(row):
    u = row["union_cert"]
    return u[0][1] if u and u[0][0] == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spot", type=Path, required=True)
    ap.add_argument("--control", type=Path, default=None, help="kriged_mean fdyn_run outputs (same starts, h5)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    starts = sorted({f.name.rsplit("_h5_", 1)[0] for f in a.spot.glob("*_h5_d*.json")})
    for st in starts:
        base = json.loads((a.spot / ("%s_h5_d0.json" % st)).read_text())["origins_detail"]
        ctl_f = a.control / ("%s_h5_kriged_mean.json" % st) if a.control else None
        ctl = json.loads(ctl_f.read_text())["origins_detail"] if ctl_f and ctl_f.exists() else None
        d0 = {o: contiguous(r) for o, r in base.items()}
        control = None
        if ctl is not None:
            diff = sorted(o for o in base if base[o]["union_cert"] != ctl[o]["union_cert"]
                          or base[o]["union_free"] != ctl[o]["union_free"])
            control = {"control_file": ctl_f.name, "places_differing": len(diff), "differing": diff[:20]}
        for d in (0, 500, 1000, 2000):
            f = a.spot / ("%s_h5_d%d.json" % (st, d))
            if not f.exists():
                rows.append({"region_start": st, "d_m": d, "status": "NOT_RUN"})
                continue
            x = json.loads(f.read_text())
            od = x["origins_detail"]
            shifts, before, none0, later = [], [], 0, 0
            for o, r in od.items():
                c, b = contiguous(r), d0[o]
                if b is None:
                    none0 += 1
                    continue
                if c is None:
                    before.append(o)
                elif c < b:
                    shifts.append(b - c)
                elif c > b:
                    later += 1
            shifts.sort()
            rows.append({"region_start": st, "d_m": d, "places": len(od), "no_checked_route_at_d0": none0,
                         "moves_earlier": len(shifts),
                         "shift_s": {"median_upper": shifts[len(shifts) // 2] if shifts else None,
                                     "max": shifts[-1] if shifts else None},
                         "moves_before_start": len(before), "moves_later": later,
                         "witness_checks": x["witness_checks"], "classes": x["classes"],
                         "hazard_sha256": x.get("spot", {}).get("hazard_sha256"),
                         **({"control_vs_kriged_mean": control} if d == 0 else {})})
    a.out.write_text(json.dumps({"what": "spotting-distance envelope (SPOTTING_RULE.md); per region-start and d, never "
                                         "pooled; CERT contact field; SCENARIO, not what happened; research variant "
                                         "(reopening packets as built); lag 0 s isotropic dilation; shifts are NOT upper "
                                         "bounds (see moves_later_note); median is the upper "
                                         "median",
                                 "moves_later_note": "CONSTRUCTION ARTEFACT (Nora row 61): dilating the whole raster moves cells "
                                 "that were NOT burned at the start (per the export) to pre-start arrivals; the builder "
                                 "treats them as burned out, so their roads open and places move LATER. Spotting makes "
                                 "places safer here, the shifts are NOT upper bounds even under the dilation rule, and "
                                 "moves_earlier can be understated. UA 24T09 d500: 97 of 135 d0 phase cells dropped, 9 "
                                 "places later (10 under never-clears, 0 earlier). Fix before any non-research use: "
                                 "a_d = max(dilate(a), t_start) for cells not burned at the start.", "rows": rows}, indent=1))
    for r in rows:
        if "places" in r:
            print(r["region_start"][-24:], r["d_m"], "earlier", r["moves_earlier"], r["shift_s"], "before",
                  r["moves_before_start"], "none0", r["no_checked_route_at_d0"], "later", r["moves_later"],
                  (r.get("control_vs_kriged_mean") or {}).get("places_differing", ""))
        else:
            print(r)


if __name__ == "__main__":
    main()
