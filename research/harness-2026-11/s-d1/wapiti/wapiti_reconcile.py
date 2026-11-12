"""Wapiti reconciliation (WAPITI_PLAN.md, committed at 117932f2 before any number). DEVELOPMENT-ONLY, exposed fire.

(S) six-fire stored entries on Main: heldout/ID-BOF-000683_Wapiti_Wapiti.npz + case receipts (heldout dir at 6a3265a0).
(M) preprint set: owner-archive runs/20261013_observed_stored_validation/cases/* (25 Wapiti cases), read in place;
    every file's sha256 must equal Victor's M548_REPRO.json input_sha256. Nothing from the archive is written out
    except counts, Brier values and hashes.

    python wapiti_reconcile.py --heldout HELDOUT_DIR --cases ARCH_CASES_DIR --m548-repro M548_REPRO.json \
        --events ARCH/wildfire/data/environment/events.json --out RESULTS_wapiti.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

EVENT = "ID-BOF-000683_Wapiti_Wapiti"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stats(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    n = len(y)
    if n == 0:
        return dict(n=0)
    bc, bz = float(np.mean((p - y) ** 2)), float(np.mean(y))  # zero forecast: Brier = mean(y^2) = mean(y)
    return dict(n=int(n), positives=int(y.sum()), brier_c651=bc, brier_zero=bz, diff_c651_minus_zero=bc - bz,
                bss_vs_zero=(1 - bc / bz) if bz > 0 else None, c651_better=bc < bz)


def iso(t):
    return datetime.fromisoformat(t).astimezone(timezone.utc).replace(microsecond=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heldout", type=Path, required=True)
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--m548-repro", type=Path, required=True)
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = dict(plan="WAPITI_PLAN.md @ 117932f2", label="DEVELOPMENT-ONLY; exposed Wapiti (cohort R)")

    # ---- (M): verify inputs, load per case on its own grid
    repro = json.loads(a.m548_repro.read_text())
    bad = [k for k, v in repro["input_sha256"].items() if sha(a.cases / k) != v]
    if bad:
        raise SystemExit(f"archive inputs differ from M548_REPRO: {bad[:3]}")
    out["m_inputs_verified"] = len(repro["input_sha256"])
    M = {}
    for case in sorted(p for p in a.cases.iterdir() if p.is_dir()):
        ref = np.load(case / "reference.npz", allow_pickle=False)
        m = np.load(case / "m548_prediction.npz", allow_pickle=False)
        proto = json.loads((case / "protocol.json").read_text())
        b0, b1 = ref["burned_area"][0, 0], ref["burned_area"][1, 0]
        mask = ref["burned_area_valid"][0, 0] & ref["burned_area_valid"][1, 0] & m["valid"][0, 0] & (b0 == 0)
        M[(iso(proto["cutoff"]), iso(proto["endpoint"]))] = dict(
            case=case.name, mask=mask, y=(b1 == 1), p=m["probability"][0, 0].astype(float),
            label_valid=ref["burned_area_valid"][0, 0] & ref["burned_area_valid"][1, 0], pred_valid=m["valid"][0, 0],
            affine=[float(x) for x in ref["affine_transform"]], epsg=int(ref["epsg"]), shape=list(b0.shape))
    allm = [(v["y"][v["mask"]], v["p"][v["mask"]]) for v in M.values()]
    mtot = stats(np.concatenate([y for y, _ in allm]), np.concatenate([p for _, p in allm]))
    out["M_totals"] = mtot
    ok = (mtot["n"] == repro["entries"] and mtot["positives"] == repro["positives"]
          and abs((1 - mtot["brier_c651"] / mtot["brier_zero"]) - repro["m548"]["bss_vs_always_zero"]) < 1e-9)
    out["M_reproduces_victor"] = bool(ok)
    if not ok:
        a.out.write_text(json.dumps(out, indent=1, default=str))
        raise SystemExit("(M) totals do not reproduce Victor's; stopping per plan")

    # ---- (S): stored entries + receipts
    z = np.load(a.heldout / f"{EVENT}.npz", allow_pickle=False)
    out["S_file_sha256"] = sha(a.heldout / f"{EVENT}.npz")
    t1 = [iso(t) for t in z["t1"]]
    recs = [json.loads(p.read_text()) for p in (a.heldout / "cases").glob("*.json")]
    end_by_cut = {iso(r["case"]["cutoff"]): iso(r["case"]["endpoint"]) for r in recs if r["case"]["event"] == EVENT}
    S_int = z["interval"]
    S = dict(row=z["row"], col=z["col"], y=z["y"].astype(float), p=z["p_c651_mc"].astype(float),
             pers=z["p_persistence"].astype(float))
    out["S_persistence_equals_zero_on_mask"] = bool(np.all(S["pers"] == 0))

    # ---- grids
    ev = next(e for e in json.loads(a.events.read_text()) if e["id"] == EVENT)
    out["S_grid_record"] = {k: ev[k] for k in ev if k in ("transform", "crs", "epsg", "width", "height", "shape",
                                                          "bounds", "grid")}
    affs = {tuple(v["affine"]) for v in M.values()}
    out["M_affines"] = [list(x) for x in affs]

    def s_transform():
        for k in ("transform", "affine_transform", "geotransform"):
            if k in ev:
                return [float(x) for x in ev[k]][:6]
        g = ev.get("grid", {})
        for k in ("transform", "affine_transform"):
            if k in g:
                return [float(x) for x in g[k]][:6]
        return None
    st = s_transform()
    out["S_affine"] = st
    aligned, offset = False, None
    if st is not None and len(affs) == 1:
        ma = list(affs)[0]
        if np.allclose([st[0], st[1], st[3], st[4]], [ma[0], ma[1], ma[3], ma[4]]) and st[1] == 0 and st[3] == 0:
            dc, dr = (st[2] - ma[2]) / ma[0], (st[5] - ma[5]) / ma[4]
            if abs(dc - round(dc)) < 1e-6 and abs(dr - round(dr)) < 1e-6:
                aligned, offset = True, (int(round(dr)), int(round(dc)))  # S(row,col) -> M(row+dr, col+dc)
    out["cell_aligned"] = aligned
    out["S_to_M_offset_rowcol"] = offset

    # ---- steps
    steps = {}
    steps["A0_S_as_stored"] = stats(S["y"], S["p"])
    matched = [k for k, t in enumerate(t1) if (t, end_by_cut.get(t)) in M]
    out["intervals"] = dict(S=len(t1), M=len(M), matched=len(matched),
                            M_unmatched=[str(k) for k in M if not any((t1[i], end_by_cut.get(t1[i])) == k for i in matched)])
    in1 = np.isin(S_int, matched)
    steps["A1_interval_set"] = stats(S["y"][in1], S["p"][in1])
    single = {}
    if aligned:
        dr, dc = offset
        mr, mc = S["row"] + dr, S["col"] + dc
        inM = np.zeros(len(S_int), bool)
        yM = np.full(len(S_int), np.nan)
        pM = np.full(len(S_int), np.nan)
        lvalid = np.zeros(len(S_int), bool)
        pvalid = np.zeros(len(S_int), bool)
        for k in matched:
            v = M[(t1[k], end_by_cut[t1[k]])]
            h, w = v["shape"]
            sel = np.flatnonzero(S_int == k)
            inside = (mr[sel] >= 0) & (mr[sel] < h) & (mc[sel] >= 0) & (mc[sel] < w)
            s2 = sel[inside]
            rr, cc = mr[s2], mc[s2]
            inM[s2] = v["mask"][rr, cc]
            lvalid[s2] = v["label_valid"][rr, cc]
            pvalid[s2] = v["pred_valid"][rr, cc]
            yM[s2] = v["y"][rr, cc]
            pM[s2] = v["p"][rr, cc]
        c2 = in1 & inM
        steps["A2_mask"] = stats(S["y"][c2], S["p"][c2])
        steps["A3_labels"] = stats(yM[c2], S["p"][c2])
        steps["A4_predictions"] = stats(yM[c2], pM[c2])
        # A5: full (M) mask on matched intervals (adds M cells not in S)
        ys, ps = [], []
        for k in matched:
            v = M[(t1[k], end_by_cut[t1[k]])]
            ys.append(v["y"][v["mask"]]), ps.append(v["p"][v["mask"]])
        steps["A5_full_M_mask_matched_intervals"] = stats(np.concatenate(ys), np.concatenate(ps))
        steps["A6_full_M_set"] = mtot
        # single-factor effects applied alone to A1
        lab = np.where(in1 & lvalid, yM, S["y"])
        prd = np.where(in1 & pvalid, pM, S["p"])
        single["mask_alone"] = steps["A2_mask"]
        single["labels_alone"] = dict(stats(lab[in1], S["p"][in1]), cells_relabelled=int((in1 & lvalid).sum()),
                                      labels_changed=int((in1 & lvalid & (yM != S["y"])).sum()))
        single["predictions_alone"] = dict(stats(S["y"][in1], prd[in1]), cells_repredicted=int((in1 & pvalid).sum()))
        single["interval_set_alone"] = steps["A1_interval_set"]
        out["S_cells_in_matched_intervals_outside_M_mask"] = int((in1 & ~inM).sum())
    else:
        steps["A2_A5"] = "NOT COMPUTABLE: grids not cell-aligned (see S_affine / M_affines)"
        steps["A6_full_M_set"] = mtot
    out["steps"] = steps
    out["single_factor_from_A1"] = single
    seq = [(k, v["c651_better"]) for k, v in steps.items() if isinstance(v, dict) and v.get("n")]
    out["sign_by_step"] = seq
    out["first_flip"] = next((seq[i][0] for i in range(1, len(seq)) if seq[i][1] != seq[i - 1][1]), None)
    a.out.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(dict(sign_by_step=seq, first_flip=out["first_flip"], aligned=aligned,
                          intervals=out["intervals"]["matched"]), default=str))


if __name__ == "__main__":
    main()
