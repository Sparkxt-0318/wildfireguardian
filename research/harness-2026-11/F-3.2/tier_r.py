"""Tier A vs Tier R (reconstruction-consistent) unknown-state experiment on the 20 Korean missions.

Orchestrator decision (2026-11-12, from Iris):
  Tier A  every UNKNOWN cell (U_state ∪ U_q) possibly burning on [0, H]: needs no assumption.
  Tier R(v) U_state cells are NOT present fire (the arrival reconstruction has no value there, so the cell never burns
          in the reconstruction that already supplies present fire and burned state). Ignition of every UNKNOWN cell
          inside the window is bounded from d / v, with d measured from present-fire and positive-probability cells
          only (not from U_state). U_state cells with any FIRMS detection during the event are blocked on [0, H].
          Conditional on footprint completeness (step b) and on v.
Steps reported per packet: (a) share of U_state cells outside the reconstruction footprint (KFS_01 raster, 2025
packets only); (b) U_state cells with a FIRMS detection during the event; side check: positive-probability cells inside U_state. Step (c): labels of the 20 missions under Tier A and
Tier R(1.5, 8.2 km/h), each unresolved one attributed by re-running with only the U_state extras and only the U_q
extras. Contact relaxation only: the radiation precondition is NOT evaluated (reported as not computed).
Guard: an event counts only if one supplied FIRMS file spans its whole window (firms_coverage); otherwise a Tier R
mission is 'not_labelled_no_firms' (never checked / unresolved); no_route stands (optimistic instance only).
Usage: python tier_r.py --toa EVENT=TOA.tif ... --firms-dir DIR ... --out DIR --c-checker PATH
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
import p1_check as P1  # noqa: E402
import cases  # noqa: E402
import unknown_support as U  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from p1_check import routable_contact_model  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402

KMH = {"R1.5": F(15, 10), "R8.2": F(82, 10)}
# event windows (acq_date, inclusive): KFS_01 from Leo's F-DYN window; others from Daniel's data-fetch-3 README
EVENT_DAYS = {"KFS_01": ("2025-03-21", "2025-04-01"), "KFS_02": ("2022-03-03", "2022-03-14"),
              "KFS_11": ("2022-05-30", "2022-06-04"), "KFS_05": ("2023-04-01", "2023-04-05")}


def native_masks(packet):
    P1.require_complete_packet_dir(packet)          # F-9.3 rule 2: refuse failed or unfinished writes
    with np.load(Path(packet) / "constructed_arrays.npz", allow_pickle=False) as a:
        P1.require_routable_arrays(a, packet)          # refuse HAZARD-only packets loudly (Leo 588f74e)
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


# Republic of Korea, generous lat/lon box (mainland, Jeju, Ulleungdo): a FIRMS file must have detections here to count
KOREA_BBOX = (33.0, 39.0, 124.5, 131.0)


def packet_bbox(packet):
    """(lat0, lat1, lon0, lon1) of the packet grid's corners, in WGS84: the event's own area."""
    from pyproj import Transformer
    meta = json.loads((Path(packet) / "NATIVE_METADATA.json").read_text())
    a, _, c, _, e, f = meta["affine_transform"]
    H, W = meta["shape"]
    tr = Transformer.from_crs(meta["crs"], "EPSG:4326", always_xy=True)
    pts = [tr.transform(c + a * x, f + e * y) for x in (0, W) for y in (0, H)]
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return (min(lats), max(lats), min(lons), max(lons))


def firms_coverage(firms_dirs, days, bbox=KOREA_BBOX):
    """Does the supplied FIRMS data cover the event window, here? True only if ONE file (a) has an acq_date span that
    contains the event window and (b) has at least one detection inside `bbox` (any date). tier_r passes the event's packet-grid bounds
    (packet_bbox); KOREA_BBOX is only the default. Each FIRMS export is one
    contiguous period for one area, so such a file is evidence that a missing detection means no detection. Neither an
    empty file, one that ends before or starts after the window, a gap between two files, nor a file for another area
    (Mira W5 N1) counts: an empty FIRMS mask would then claim "no detections" where there is only missing data (the first
    Tier R run did exactly this for 2022/23). The span is that of the detections, not the export's nominal period, so a
    file whose first or last detection falls inside the window does not count even if the export covered it
    (conservative: the event is then refused, never mislabelled)."""
    la0, la1, lo0, lo1 = bbox
    spans = []
    for d in firms_dirs:
        for p in sorted(Path(d).glob("*.csv")):
            with open(p, newline="") as fh:
                rows = [row for row in csv.DictReader(fh) if row.get("acq_date")]
            if not rows:
                continue
            here = sum(1 for row in rows if la0 <= float(row["latitude"]) <= la1 and lo0 <= float(row["longitude"]) <= lo1)
            dates = [row["acq_date"] for row in rows]
            spans.append((p.name, min(dates), max(dates), here))
    hit = [n for n, f, l, here in spans if f <= days[0] and l >= days[1] and here > 0]
    return dict(covered=bool(hit), files_spanning=hit, files_read=len(spans))


def tier_label(tier, claim, accepted, opt_no_route, firms_covered):
    """The three-way label, with the coverage guard. Tier A needs no FIRMS. A Tier R 'checked' or 'unresolved' rests on
    the FIRMS mask, so without coverage it is refused ('not_labelled_no_firms'); 'no_route' comes from the optimistic
    instance alone and stands either way."""
    if claim == "ROUTE" and accepted and (tier == "A" or firms_covered):
        return "checked"
    if opt_no_route:
        return "no_route"
    return "unresolved" if (tier == "A" or firms_covered) else "not_labelled_no_firms"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toa", nargs="+", required=True, help="EVENT=path/to/<event>_pswt_ok_toa.tif ...")
    ap.add_argument("--firms-dir", nargs="+", required=True, help="directories of FIRMS country CSVs (all are read)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    packets, rows = {}, []
    for case in cases.korean_cases():
        g = json.loads(Path(case["graph"]).read_text()); r = json.loads(Path(case["request"]).read_text())
        model = routable_contact_model(case["packet"])
        meta = json.loads((Path(case["packet"]) / "NATIVE_METADATA.json").read_text())
        event = meta["construction"]["parent_forecast"]["event_id"]
        u_state, u_q, cur, pos = native_masks(case["packet"])
        key = case["region"] + "/" + case["mission"].split("_")[0]
        toa = dict(x.split("=", 1) for x in a.toa)
        # the area condition uses the event's own packet grid (Mira W5 N1': the Korea box also holds northern Kyushu)
        cov = (firms_coverage(a.firms_dir, EVENT_DAYS[event], packet_bbox(case["packet"])) if event in EVENT_DAYS
               else dict(covered=False, files_spanning=[], files_read=0))
        # step (a), the footprint share, needs the arrival raster only (reported, never used in a label)
        if event in toa:
            info = footprint_share(case["packet"], toa[event])
            info["a_available"] = True
        else:
            info = dict(U_state=int(u_state.sum()), positive_prob=int(pos.sum()),
                        positive_prob_in_U_state=int((pos & u_state).sum()), a_available=False)
        # step (b), FIRMS-detected U_state cells, needs FIRMS coverage only; Tier R labels depend on it (tier_label)
        hit = np.zeros_like(u_state)
        if cov["covered"]:
            ndet = 0
            for fd in a.firms_dir:
                h1, n1 = firms_cells(case["packet"], fd, EVENT_DAYS[event])
                hit |= h1; ndet += n1
            info.update(firms_detections_in_grid=ndet, firms_cells=int(hit.sum()), U_state_with_firms=int((hit & u_state).sum()))
        else:
            info["note"] = "no FIRMS coverage for this event: (b) not computed; Tier R not labelled"
        info.update(event=event, b_available=cov["covered"], firms_coverage=cov)
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
            label = tier_label(tier, res["claim"], res["accepted"], opt_no_route, cov["covered"])
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
