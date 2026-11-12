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
    ap.add_argument("--control", type=Path, required=True, help="kriged_mean fdyn_run outputs (same starts, h5)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows = []
    starts = sorted({f.name.rsplit("_h5_", 1)[0] for f in a.spot.glob("*_h5_d*.json")})
    for st in starts:
        base = json.loads((a.spot / ("%s_h5_d0.json" % st)).read_text())["origins_detail"]
        ctl_f = a.control / ("%s_h5_kriged_mean.json" % st)
        ctl = json.loads(ctl_f.read_text())["origins_detail"] if ctl_f.exists() else None
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
                                         "(reopening packets as built); lag 0 s isotropic dilation: shifts are upper "
                                         "bounds under this dilation rule, not physical bounds; median is the upper "
                                         "median",
                                 "moves_later_note": "A place can move LATER with d. Checked on UA 24T09 d500 (9 "
                                 "places later): the dilation moves 97 of the 135 cells burning in the d0 packet to "
                                 "arrivals 4,227-47,988 s BEFORE the start; the builder treats them as burned out "
                                 "before the start, so they are not phases and their roads are open. Under the "
                                 "never-clears arm on the same two packets 10 places move later and none earlier. So "
                                 "this is the packets' pre-start burn-out semantics (also in no_reentry/1: cells "
                                 "burned out before the start stay open), not a field fault. Other starts not checked "
                                 "per place.", "rows": rows}, indent=1))
    for r in rows:
        if "places" in r:
            print(r["region_start"][-24:], r["d_m"], "earlier", r["moves_earlier"], r["shift_s"], "before",
                  r["moves_before_start"], "none0", r["no_checked_route_at_d0"], "later", r["moves_later"],
                  r.get("control_vs_kriged_mean", {}).get("places_differing", ""))
        else:
            print(r)


if __name__ == "__main__":
    main()
