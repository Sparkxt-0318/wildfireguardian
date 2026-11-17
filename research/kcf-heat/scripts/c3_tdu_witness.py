"""C.3: thermal dose units along every witness route of the 1-hour reruns (cert and cert_heat variants).

    python scripts/c3_tdu_witness.py --data-root DATA/routing OUT.json FULL_JSON...

A witness is the forward route the deadline field returns for a recorded attempt or route-check job that is feasible
in that variant. Exposure uses kcf_heat.exposure (closed-form law, nearest-front reading, unshielded person, 1-s
midpoint quadrature). Doses are reported for the journey (departure to arrival, driving and waits) and for the
shelter stay (destination dwell) separately, with the old linear dose (integral of q dt, kJ/m2) beside them.

Thresholds (TDU, (kW/m2)^(4/3) s), O'Sullivan & Jagger 2004, HSL/2004/04, Tables 1-2: pain 92, first-degree burn
105, second-degree burn 290, dangerous dose 1000 (1-5 % fatality); 500 = dangerous dose for vulnerable people
(Rew 1997, HSE CRR 129/1997, citing Kinsman 1991). No-harm flux q0 = 1.42 kW/m2 (24 CFR 51.203(a)(2)); sensitivities
q0 = 1.0 (PGS 1 deel 1A, 2003, section 3.6) and 1.6 kW/m2 (HSE SPC/Tech/OSD/30).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import HeatPacketModel, HeatRule  # noqa: E402
from kcf_heat.exposure import RouteExposure, tdu  # noqa: E402

THRESHOLDS = (92, 105, 290, 500, 1000)
Q0 = (1.42, 1.0, 1.6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("full", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, required=True)
    a = ap.parse_args()
    result = {"thresholds_tdu": THRESHOLDS, "q0_kw_m2": Q0, "per_cache": {}}
    for fp in a.full:
        out = json.loads(fp.read_text())
        compact = out["input_time"].replace("-", "").replace(":", "")
        pm = HeatPacketModel(a.data_root / "graphs" / out["region"] / "graph.json",
                             a.data_root / "latest_inputs_try02" / "packets" / out["region"] / compact, heat=HeatRule())
        ex = RouteExposure(pm)
        seen = {}
        per_var = {}
        for var in ("cert", "cert_heat"):
            rows = []
            for r in out["attempts"] + out["jobs"]:
                f = (r.get("field") or {}).get(var)
                if not f or not f.get("feasible"):
                    continue
                key = (json.dumps(f["legs"]), r["dest"], r["dwell"], r["start"], r["offset"])
                if key not in seen:
                    drive, stay, at_o = ex.route_series([tuple(l) for l in f["legs"]], dest=r["dest"], dwell=r["dwell"],
                                                        origin=r["start"], departure=r["offset"])
                    seen[key] = {"peak_drive": max(drive, default=0.0), "peak_stay": max(stay, default=0.0),
                                 "q_origin": at_o or 0.0, "lin_drive_kj_m2": sum(drive), "lin_stay_kj_m2": sum(stay),
                                 **{"tdu_drive_q0_%s" % q0: tdu(drive, q0=q0) for q0 in Q0},
                                 **{"tdu_stay_q0_%s" % q0: tdu(stay, q0=q0) for q0 in Q0},
                                 "tdu_drive_all": tdu(drive), "tdu_stay_all": tdu(stay)}
                rows.append(seen[key])
            c = Counter()
            for s in rows:
                for th in THRESHOLDS:
                    for q0 in Q0:
                        c["drive_q0_%s_ge_%d" % (q0, th)] += s["tdu_drive_q0_%s" % q0] >= th
                        c["stay_q0_%s_ge_%d" % (q0, th)] += s["tdu_stay_q0_%s" % q0] >= th
                    c["drive_all_ge_%d" % th] += s["tdu_drive_all"] >= th
                c["peak_drive_gt_10"] += s["peak_drive"] > 10.0
                c["peak_stay_gt_2.5"] += s["peak_stay"] > 2.5
                c["lin_total_gt_100"] += (s["lin_drive_kj_m2"] + s["lin_stay_kj_m2"]) > 100.0
            per_var[var] = {"witnesses": len(rows), "counts": dict(c),
                            "max_tdu_drive_q0_1.42": max((s["tdu_drive_q0_1.42"] for s in rows), default=0.0),
                            "max_tdu_stay_q0_1.42": max((s["tdu_stay_q0_1.42"] for s in rows), default=0.0),
                            "max_peak_drive": max((s["peak_drive"] for s in rows), default=0.0),
                            "max_peak_stay": max((s["peak_stay"] for s in rows), default=0.0),
                            "max_linear_total_kj_m2": max((s["lin_drive_kj_m2"] + s["lin_stay_kj_m2"] for s in rows), default=0.0)}
        result["per_cache"]["%s %s" % (out["region"], out["input_time"])] = per_var
        print(fp.name, json.dumps({v: {k: per_var[v][k] for k in per_var[v] if k != "counts"} for v in per_var}), flush=True)
    a.out.write_text(json.dumps(result, indent=1) + "\n")


if __name__ == "__main__":
    main()
