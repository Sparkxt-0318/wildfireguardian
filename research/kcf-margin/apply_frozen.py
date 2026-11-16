"""Apply the frozen GOFER R(h) (numbers.json, fire set all28) to NIROPS 12-48 h pairs and to Gyeongbuk 25 March 2025.

    python apply_frozen.py --work WORK --numbers numbers.json
Adds keys "nirops_check" and "gyeongbuk_stress" to numbers.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from calibrate import QUIET, RUNNING  # noqa: E402
from reach import clopper_pearson  # noqa: E402


def frozen(num, h, cls, alpha):
    for r in num["table"]:
        if r["fire_set"] == "all28" and r["h"] == h and r["cls"] == cls and abs(r["alpha"] - alpha) < 1e-9:
            return r["R_km"]
    raise KeyError((h, cls, alpha))


def prior_class(km):
    return "quiet" if km < QUIET else "slow" if km < RUNNING else "running"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--numbers", required=True)
    a = ap.parse_args()
    work = Path(a.work)
    num = json.loads(Path(a.numbers).read_text())

    # NIROPS
    nir = pd.read_csv(work / "nirops_pairs.csv.gz")
    hz = sorted(int(h) for h in num["frozen_R_by_horizon_all28"] if h != "label")
    out_n = dict(source="NIROPS 2020-2024, S-D9 PART_A_ALLOWLIST_FINAL incidents only; consecutive survey pairs, gap 12-48 h",
                 R_interpolation=dict(value="R(h) linearly interpolated between GOFER horizons " + str(hz), label="ASSUMED"),
                 pairs=dict(value=int(len(nir)), label="MEASURED"), incidents=dict(value=int(nir.incident.nunique()), label="MEASURED"),
                 gap_h_median=dict(value=float(nir.gap_h.median()), label="MEASURED"),
                 reach_km_q50_q90=dict(value=[float(nir.reach_km.median()), float(nir.reach_km.quantile(0.9))], label="MEASURED"),
                 by_alpha={})
    for al in (0.1, 0.2):
        Rh = [num["frozen_R_by_horizon_all28"][str(h)][str(al)] for h in hz]
        R = np.interp(nir.gap_h, hz, Rh)
        miss = nir.reach_km > R
        per = miss.groupby(nir.incident).mean()
        lo, hi = clopper_pearson(float(per.sum()), len(per))
        bands = {}
        for b0, b1 in ((12, 24), (24, 36), (36, 48.01)):
            m = (nir.gap_h >= b0) & (nir.gap_h < b1)
            p = miss[m].groupby(nir.incident[m]).mean()
            bands[f"{b0}-{int(b1)}h"] = dict(miss_fire_weighted=float(p.mean()), n_incidents=int(len(p)),
                                             ci95=list(clopper_pearson(float(p.sum()), len(p))))
        out_n["by_alpha"][str(al)] = dict(miss_fire_weighted=float(per.mean()), ci95=[lo, hi], n_incidents=int(len(per)),
                                          miss_pairs_pooled=float(miss.mean()), by_gap=bands, label="MEASURED")
        print("NIROPS", al, out_n["by_alpha"][str(al)])
    num["nirops_check"] = out_n

    # Gyeongbuk
    gy = pd.read_csv(work / "gyeongbuk_reach.csv")
    rows = []
    for _, r in gy.iterrows():
        c = prior_class(r.prior3_km)
        rec = dict(kst_hour=int(r.kst_hour), h=int(r.h), complete=bool(r.complete), reach_km=float(r.reach_km),
                   prior3_km=float(r.prior3_km), prior_class=c)
        for al in (0.1, 0.2):
            ra, rc = frozen(num, int(r.h), "all", al), frozen(num, int(r.h), c, al)
            rec[f"R_all_{al}"] = ra
            rec[f"miss_all_{al}"] = bool(r.reach_km > ra)
            rec[f"R_class_{al}"] = rc
            rec[f"miss_class_{al}"] = bool(r.reach_km > rc)
        rows.append(rec)
    g = pd.DataFrame(rows)
    summ = {}
    for h in (5, 8):
        d = g[(g.h == h) & g.complete]
        summ[str(h)] = dict(issue_hours_complete=int(len(d)), **{
            f"{k}_{al}_missed_hours": int(d[f"miss_{k}_{al}"].sum()) for k in ("all", "class") for al in (0.1, 0.2)},
            missed_kst_hours_class_0_1=d[d["miss_class_0.1"]].kst_hour.tolist(),
            max_reach_km=float(d.reach_km.max()))
    num["gyeongbuk_stress"] = dict(
        source="FIRMS VIIRS (375 m) + Himawari-9 AHI B07/B14 hotspots (2 km) over the KFS_01 rectangle; detections, "
               "not perimeters (ASSUMED proxy); one fire, one day: no rate is claimed", summary=summ,
        hourly=rows, label="MEASURED")
    print(json.dumps(summ, indent=1))
    Path(a.numbers).write_text(json.dumps(num, indent=1, default=float))


if __name__ == "__main__":
    main()
