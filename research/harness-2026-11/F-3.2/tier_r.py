"""Tier A vs Tier R (reconstruction-consistent) unknown-state experiment on the 20 Korean missions.

Orchestrator decision (2026-11-12, from Iris):
  Tier A  every UNKNOWN cell (U_state ∪ U_q) possibly burning on [0, H]: needs no assumption.
  Tier R(v) U_state cells are NOT present fire (the arrival reconstruction has no value there, so the cell never burns
          in the reconstruction that already supplies present fire and burned state). Ignition of every UNKNOWN cell
          inside the window is bounded from d / v, with d measured from present-fire and positive-probability cells
          only (not from U_state). U_state cells with any FIRMS detection during the event are blocked on [0, H].
          Conditional on footprint completeness (step b) and on v.
Steps reported per packet: (a) share of U_state cells outside the reconstruction footprint (KFS_01 raster, 2025
packets only); (b) U_state cells with a FIRMS detection during the event (2025 only; other years' FIRMS not available
here); side check: positive-probability cells inside U_state. Step (c): labels of the 20 missions under Tier A and
Tier R(1.5, 8.2 km/h), each unresolved one attributed by re-running with only the U_state extras and only the U_q
extras. Contact relaxation only: the radiation precondition is NOT evaluated (reported as not computed).
Usage: python tier_r.py --kfs01 TOA.tif --firms-dir DIR --out DIR --c-checker PATH
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
import unknown_support as U  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402

KMH = {"R1.5": F(15, 10), "R8.2": F(82, 10)}
EVENT_DAYS = {"KFS_01": ("2025-03-21", "2025-04-01")}


def native_masks(packet):
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        g = lambda k: a["mask__" + k].astype(bool)
        u_state = g("unknown_cumulative_state")
        u_q = g("policy_assigned_zero") & ~g("known_burned") & ~u_state
        cur = a["current_active"].astype(bool)
        pos = g("positive_native_probability")
    return u_state, u_q, cur, pos


def cell_centres(meta):
    a, _, c, _, e, f = meta["affine_transform"]
    H, W = meta["shape"]
    cols, rows = np.meshgrid(np.arange(W), np.arange(H))
    return c + (cols + 0.5) * a, f + (rows + 0.5) * e


def footprint_share(packet, toa_path):
    import rasterio
    meta = json.loads((Path(packet) / "NATIVE_METADATA.json").read_text())
    u_state, _, _, pos = native_masks(packet)
    xs, ys = cell_centres(meta)
    with rasterio.open(toa_path) as r:
        toa = r.read(1)
        rr, cc = rasterio.transform.rowcol(r.transform, xs.ravel(), ys.ravel())
    rr, cc = np.array(rr).reshape(xs.shape), np.array(cc).reshape(xs.shape)
    inside = (rr >= 0) & (rr < toa.shape[0]) & (cc >= 0) & (cc < toa.shape[1])
    val = np.full(xs.shape, np.nan, dtype=float)
    val[inside] = toa[rr[inside], cc[inside]]
    in_fp = np.isfinite(val)
    return dict(U_state=int(u_state.sum()), U_state_outside_footprint=int((u_state & ~in_fp).sum()),
                U_state_inside_footprint=int((u_state & in_fp).sum()),
                positive_prob=int(pos.sum()), positive_prob_outside_footprint=int((pos & ~in_fp).sum()),
                positive_prob_in_U_state=int((pos & u_state).sum()))


def firms_cells(packet, firms_dir, days):
    from pyproj import Transformer
    meta = json.loads((Path(packet) / "NATIVE_METADATA.json").read_text())
    a, _, c, _, e, f = meta["affine_transform"]
    H, W = meta["shape"]
    tr = Transformer.from_crs("EPSG:4326", meta["crs"], always_xy=True)
    hit = np.zeros((H, W), dtype=bool)
    n = 0
    for p in sorted(Path(firms_dir).glob("*.csv")):
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh):
                if not (days[0] <= row["acq_date"] <= days[1]):
                    continue
                x, y = tr.transform(float(row["longitude"]), float(row["latitude"]))
                col, r = int(np.floor((x - c) / a)), int(np.floor((y - f) / e))
                if 0 <= r < H and 0 <= col < W:
                    hit[r, col] = True
                    n += 1
    return hit, n


def extras(model, graph, cells_block_all, cells_ignite, s0, H, v):
    """{graph cell: (b, H+1)}: cells_block_all on [0, H]; cells_ignite from d/v (d from s0 centres), if <= H."""
    W = s0.shape[1]
    res = F(graph["grid"]["resolution"])
    end = F(H) + 1
    out = {}
    for r, c in zip(*np.nonzero(cells_block_all)):
        out[model._g(int(r) * W + int(c))] = (F(0), end)
    src = np.argwhere(s0)
    vv = v * 1000 / 3600
    for r, c in zip(*np.nonzero(cells_ignite & ~cells_block_all)):
        if len(src) == 0:
            break
        d2 = F(int(((src - np.array([r, c])) ** 2).sum(axis=1).min())) * res * res
        if d2 > (F(H) * vv) ** 2:
            continue
        d_lo = F(int(np.floor(np.sqrt(float(d2)))))
        while d_lo * d_lo > d2:
            d_lo -= 1
        out[model._g(int(r) * W + int(c))] = (max(F(0), d_lo / vv), end)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kfs01", required=True)
    ap.add_argument("--firms-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    packets, rows = {}, []
    for case in cases.korean_cases():
        g = json.loads(Path(case["graph"]).read_text()); r = json.loads(Path(case["request"]).read_text())
        model = ContactModel.from_packet(case["packet"])
        meta = json.loads((Path(case["packet"]) / "NATIVE_METADATA.json").read_text())
        event = meta["construction"]["parent_forecast"]["event_id"]
        u_state, u_q, cur, pos = native_masks(case["packet"])
        key = case["region"] + "/" + case["mission"].split("_")[0]
        if event in EVENT_DAYS:
            info = footprint_share(case["packet"], a.kfs01)
            hit, ndet = firms_cells(case["packet"], a.firms_dir, EVENT_DAYS[event])
            info.update(event=event, firms_detections_in_grid=ndet, firms_cells=int(hit.sum()),
                        U_state_with_firms=int((hit & u_state).sum()), b_available=True)
        else:
            hit = np.zeros_like(u_state)
            info = dict(event=event, U_state=int(u_state.sum()), positive_prob=int(pos.sum()),
                        positive_prob_in_U_state=int((pos & u_state).sum()), b_available=False,
                        note="no arrival raster / FIRMS for this event here: (a)/(b) not computed")
        packets[key] = info
        H = int(F(r["horizon"]))
        unknown = u_state | u_q
        s0_A = cur | u_state | pos
        s0_R = cur | pos
        row = dict(mission=case["mission"], region=case["region"], event=event, b_available=info["b_available"])
        inst_opt, _ = build_instance(g, r, model)
        row["optimistic"] = U.certify_and_check(inst_opt, out / (case["mission"] + "__opt.wfgc"), a.c_checker)
        opt_no_route = row["optimistic"]["claim"] == "NO_ROUTE" and row["optimistic"]["accepted"]
        variants = {"A": (unknown, np.zeros_like(unknown), s0_A, F(1))}
        for tier, v in KMH.items():
            variants[tier] = (hit & u_state, unknown, s0_R, v)
        for tier, (block_all, ignite, s0, v) in variants.items():
            ex = extras(model, g, block_all, ignite, s0, H, v)
            inst, _ = build_instance(g, r, U.Augmented(model, ex))
            res = U.certify_and_check(inst, out / ("%s__%s.wfgc" % (case["mission"], tier)), a.c_checker)
            res["extra_cells"] = len(ex)
            label = "checked" if res["claim"] == "ROUTE" and res["accepted"] else "no_route" if opt_no_route else "unresolved"
            cause = None
            if label == "unresolved":
                causes = []
                for name, mask in (("U_state", u_state), ("U_q", u_q)):
                    ex1 = extras(model, g, block_all & mask, ignite & mask, s0, H, v)
                    i1, _ = build_instance(g, r, U.Augmented(model, ex1))
                    if U.generate.certify(i1)[0] == "NO_ROUTE":
                        causes.append(name)
                cause = "+".join(causes) if causes else "U_state and U_q only jointly"
            row[tier] = dict(res, label=label, cause=cause)
            Path(out / ("%s__%s.wfgc" % (case["mission"], tier))).unlink(missing_ok=True)
        row["radiation_precondition"] = "not computed (contact relaxation only)"
        rows.append(row)
        print(json.dumps({"mission": row["mission"], **{t: "%s %s %s" % (row[t]["label"], row[t]["T"], row[t]["cause"] or "") for t in variants}}), flush=True)
    (HERE / "results" / "tier_r.json").write_text(json.dumps({"packets": packets, "rows": rows}, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
