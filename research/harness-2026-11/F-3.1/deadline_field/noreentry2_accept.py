"""no_reentry/2 acceptance 6-7, Richard's side (rule: NOREENTRY2_ACCEPTANCE_RULE.md, committed before any run).

B0 is recomputed here from the export npz and the variant arrival raster, independently of the /2 plan:
  C0 = export known-burned (source_burned_area_valid & source_burned_area == 1)
       ∪ {variant arrival finite and round(arrival_h * 3.6e6) <= h_ms}       (h = start - t0, ms; inclusive)
  raster/export pixel of a router cell = the pixel containing the cell centre (north-up affine; router grid south-up)
  B0[s] = C0 ∩ router grid  minus  cells whose /1 phase in member s is [0, >=H)
    python3 -m deadline_field.noreentry2_accept --graph G --nr1 P1 --nr2 P2 --export NPZ --raster R --start START \
        --instance-json I --region REGION --horizon-s HS [--plan-meta JSON] --out OUT
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

T0 = datetime(2025, 3, 22, 2, 24, tzinfo=timezone.utc)
STEP = 1800
FLUX_NOTE = "dose/peak columns carry Leo's fdyn.no_reentry_flux label verbatim (read from the /2 packet identity)"


def read_raster(p: Path):
    if p.suffix == ".npz":
        z = np.load(p, allow_pickle=False)
        return np.asarray(z["arrival_h"], float), tuple(float(v) for v in z["affine_transform"])
    import rasterio
    with rasterio.open(p) as r:
        a = r.read(1).astype(float)
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
        t = r.transform
        return a, (t.a, t.b, t.c, t.d, t.e, t.f)


def pixel_of(aff, x, y, shape):
    """Pixel containing (x, y) under a north-up affine (a, b, c, d, e, f); None outside."""
    a, b, c, d, e, f = aff
    assert b == 0 and d == 0 and e < 0 < a, aff
    col = int(np.floor((x - c) / a))
    row = int(np.floor((y - f) / e))
    return (row, col) if (0 <= row < shape[0] and 0 <= col < shape[1]) else None


def c0_cells(grid, export: Path, raster: Path, start: str):
    st = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    h_ms = int(round((st - T0).total_seconds() * 1000))
    z = np.load(export, allow_pickle=True)
    burned = np.asarray(z["source_burned_area_valid"], bool) & (np.asarray(z["source_burned_area"]) == 1)
    eaff = tuple(float(v) for v in z["affine_transform"])
    arr, raff = read_raster(raster)
    fin = np.isfinite(arr)
    a_ms = np.where(fin, np.round(np.where(fin, arr, 0) * 3.6e6), np.inf)
    before = fin & (a_ms <= h_ms)
    exp_c, var_c, outside = set(), set(), Counter()
    for cell in range(grid.W * grid.H):
        x, y = (float(v) for v in grid.centre(cell))
        pe, pr = pixel_of(eaff, x, y, burned.shape), pixel_of(raff, x, y, arr.shape)
        if pe is None:
            outside["export"] += 1
        elif burned[pe]:
            exp_c.add(cell)
        if pr is None:
            outside["raster"] += 1
        elif before[pr]:
            var_c.add(cell)
    # C0 pixels that no router cell centre falls in (reported only)
    return {"h_ms": h_ms, "export_burned": exp_c, "variant_before_start": var_c, "router_cells_outside": dict(outside),
            "export_burned_pixels_total": int(burned.sum()), "variant_before_start_pixels_total": int(before.sum())}


def norm(ph, H):
    b, xe, xr, _k = ph
    cap = lambda x: "H+" if x >= H else str(F(x))
    return (str(F(b)), cap(xe), cap(xr))


def origin_fields(pm, specs, var):
    out = {}
    for (dnode, dwell), origins in sorted(specs.items()):
        fld = backward(pm.instance(var, [{"node": dnode, "dwell": dwell, "window": [0, pm.H]}], sorted(origins)))
        for o in origins:
            out[(dnode, dwell, o)] = issue_set(fld, pm.nidx[o])
        del fld
    return out


def run(a):
    t0 = time.perf_counter()
    doc = json.loads(Path(a.instance_json).read_text())
    inst = next(i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == int(a.horizon_s)
                and i["start_tag"] == (a.instance_start or a.start))
    specs = {}
    for o in inst["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    peak_l, dose_l = inst["limits"]["peak_kw_m2"], inst["limits"]["dose_kj_m2"]
    p1, p2 = PacketModel(a.graph, a.nr1), PacketModel(a.graph, a.nr2)
    H = p1.H
    assert p2.H == H and p1.pk.S == p2.pk.S
    bs2 = json.loads((Path(a.nr2) / "BUILD_SUMMARY.json").read_text())
    wid = bs2.get("writer_identity") or {}
    c0 = c0_cells(p1.g.grid, Path(a.export), Path(a.raster), a.start)
    C0 = c0["export_burned"] | c0["variant_before_start"]
    present = set(p1.pk.present_cells)
    # ---- B0 per member and 6a phases
    b0, b0_split, mism = [], [], []
    for s in range(p1.pk.S):
        ph1, ph2 = p1.pk.phases[s], p2.pk.phases[s]
        full0 = {c for c, v in ph1.items() if v[0] == 0 and v[1] >= H}
        B = C0 - full0
        b0.append(B)
        b0_split.append({"export_burned_not_present": len((c0["export_burned"] - present) & B),
                         "variant_burned_out": len((c0["variant_before_start"] - c0["export_burned"]) & B),
                         "export_burned_and_present_but_not_full0": len(c0["export_burned"] & present & B)})
        exp = {c: norm(v, H) for c, v in ph1.items()}
        for c in B:
            exp[c] = ("0", "H+", "H+")
        got = {c: norm(v, H) for c, v in ph2.items()}
        for c in sorted(set(exp) | set(got)):
            if exp.get(c) != got.get(c):
                mism.append({"member": s, "cell": c, "expected": exp.get(c), "got": got.get(c), "in_B0": c in B})
    b0_same = all(b == b0[0] for b in b0)
    # ---- 6d counts vs plan meta (reported if given)
    plan = json.loads(Path(a.plan_meta).read_text()) if a.plan_meta else None
    # ---- 6b fields: /2 vs /1 + extra_blocks{B0 (union over members): 0}
    union = set().union(*b0)
    px = PacketModel(a.graph, a.nr1, extra_blocks={c: 0 for c in union})
    field_diff, fields2 = Counter(), {}
    for var in ("cert", "router"):
        f2, fx = origin_fields(p2, specs, var), origin_fields(px, specs, var)
        fields2[var] = f2
        for k in f2:
            lb2 = f2[k][-1][1] if f2[k] else None
            lbx = fx[k][-1][1] if fx[k] else None
            same_lb = (lb2 is None and lbx is None) or (lb2 is not None and lbx is not None
                                                        and float("%.9g" % lb2) == float("%.9g" % lbx))
            grid_same = all(iv.contains(f2[k], t) == iv.contains(fx[k], t) for t in range(0, H + 1, STEP))
            field_diff["%s:leave_by_%s" % (var, "equal" if same_lb else "DIFF")] += 1
            field_diff["%s:grid_%s" % (var, "equal" if grid_same else "DIFF")] += 1
        del fx
    del px
    # ---- 6c / 7 witnesses: /2 CERT leave-by witnesses, full_check on /2 HAZARD and on /1 HAZARD
    hz1 = json.loads((Path(a.nr1) / "HAZARD.json").read_text())
    hz2 = json.loads((Path(a.nr2) / "HAZARD.json").read_text())
    wc, rcl = Counter(), []
    for (dnode, dwell), origins in sorted(specs.items()):
        fld = backward(p2.instance("cert", [{"node": dnode, "dwell": dwell, "window": [0, H]}], sorted(origins)))
        for o in sorted(origins):
            f = issue_set(fld, p2.nidx[o])
            if not f:
                continue
            ld = f[-1][1]
            w = witness_greedy(fld, p2.nidx[o], ld)
            legs = [(k, (p2.g.edge_ids[x] if k == "EDGE" else p2.node_ids[x]), s_, e_) for k, x, s_, e_ in w[1]]
            kw = dict(origin=o, legs=legs, dest=dnode, dwell=dwell, window=[0, H], departure=ld, incurred=0.0,
                      peak=peak_l, dose=dose_l)
            c2, c1 = full_check(p2, hz2, **kw), full_check(p1, hz1, **kw)
            wc["contact_clear_on_/2:%s" % c2["closed_and_router_replay_clear"]] += 1
            wc["contact_clear_on_/1:%s" % c1["closed_and_router_replay_clear"]] += 1
            wc["full_/2:%s|full_/1:%s" % (c2["full_policy_ok"], c1["full_policy_ok"])] += 1
            rad_only = (not c2["full_policy_ok"] and c2["closed_and_router_replay_clear"]
                        and all(str(x).upper().startswith(("DOSE", "PEAK")) for x in c2["codes"]) and c2["codes"]
                        and c1["full_policy_ok"])
            if rad_only:
                rcl.append({"origin": o, "dest": dnode, "dwell": dwell, "leave_by_s": ld, "codes_/2": c2["codes"]})
        del fld
    return {"what": "no_reentry/2 acceptance 6-7 (NOREENTRY2_ACCEPTANCE_RULE.md)", "region": a.region,
            "start": a.start, "H": H, "instance_start_tag": a.instance_start or a.start, "packets": {"nr1": str(a.nr1), "nr2": str(a.nr2)},
            "writer_identity_nr2": wid, "flux_label": FLUX_NOTE,
            "C0": {"h_ms": c0["h_ms"], "export_burned_router_cells": len(c0["export_burned"]),
                   "variant_before_start_router_cells": len(c0["variant_before_start"]), "C0_router_cells": len(C0),
                   "router_cells_outside": c0["router_cells_outside"],
                   "export_burned_pixels_total": c0["export_burned_pixels_total"],
                   "variant_before_start_pixels_total": c0["variant_before_start_pixels_total"]},
            "B0_per_member": [len(b) for b in b0], "B0_split_per_member": b0_split, "B0_same_all_members": b0_same,
            "6a_phase_mismatches": len(mism), "6a_mismatch_sample": mism[:50],
            "6b_field": dict(field_diff), "6c_witness": dict(wc),
            "6d_plan_meta": (plan or {}).get("no_reentry2") if plan else "not supplied",
            "7_radiation_convention_limited": {"label": "radiation-convention-limited (burned-out ground held at "
                                                        "burning intensity)", "count": len(rcl), "jobs": rcl},
            "wall_s": time.perf_counter() - t0}


def main():
    ap = argparse.ArgumentParser()
    for k in ("graph", "nr1", "nr2", "export", "raster", "start", "instance-json", "region", "horizon-s", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--plan-meta")
    ap.add_argument("--instance-start", help="INSTANCE entry to take places from when the start has none (labelled)")
    a = ap.parse_args()
    out = run(a)
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("C0", "B0_per_member", "6a_phase_mismatches", "6b_field", "6c_witness")},
                     default=str))
    print("radiation_convention_limited", out["7_radiation_convention_limited"]["count"])


if __name__ == "__main__":
    main()
