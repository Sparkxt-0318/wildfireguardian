"""BORDER_TOUCH_RULE.md (+ amendment 1): per place, re-derive CERT / ROUTER leave-by on the /2 packet, take the
witness at the leave-by for every destination containing it, and test each witness's closed-rule footprint against
padding cells of the widened lattice (export grid + 14 cells). Also the outer-ring proxy and the boundary test.
    python3 -m deadline_field.border_touch --graph G --packet P2 --instance-json I --region R --start S --horizon-s HS
        --variant V --summary results/HEADLINE_NR2_summary.json --out OUT"""
from __future__ import annotations
import argparse, json, sys, time
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402
from tools.explain_deadlines.geometry import Grid, clip_closed  # noqa: E402

PAD = 14


def tests(grid, wide, pts_or_segs):
    """(footprint_padding, ring_proxy, boundary) for a list of (p0, p1) segments (points: p0 == p1)."""
    x0, y0 = grid.x0, grid.y0
    x1, y1 = x0 + grid.W * grid.res, y0 + grid.H * grid.res
    foot = ring = bnd = False
    for p0, p1 in pts_or_segs:
        for c in wide.cells_touching_box(min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1])):
            if clip_closed(p0, p1, wide.rect(c)) is None:
                continue
            r, k = divmod(c, wide.W)
            if r < PAD or r >= grid.H + PAD or k < PAD or k >= grid.W + PAD:
                foot = True
            else:
                er, ek = r - PAD, k - PAD
                if er in (0, grid.H - 1) or ek in (0, grid.W - 1):
                    ring = True
        for p in (p0, p1):
            if p[0] <= x0 or p[0] >= x1 or p[1] <= y0 or p[1] >= y1:
                bnd = True
    return foot, ring or foot, bnd


def main():
    ap = argparse.ArgumentParser()
    for k in ("graph", "packet", "instance-json", "region", "start", "horizon-s", "variant", "summary", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    t0 = time.perf_counter()
    doc = json.loads(Path(a.instance_json).read_text())
    inst = next(i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == int(a.horizon_s)
                and i["start_tag"] == a.start)
    h = int(a.horizon_s) // 3600
    summ = {p["origin"]: p for p in json.loads(Path(a.summary).read_text())["places"]
            if p["region"] == a.region and p["start"] == a.start and p["horizon_h"] == h}
    peak_l, dose_l = inst["limits"]["peak_kw_m2"], inst["limits"]["dose_kj_m2"]
    pm = PacketModel(a.graph, a.packet)
    H = pm.H
    grid = pm.g.grid
    wide = Grid(grid.x0 - PAD * grid.res, grid.y0 - PAD * grid.res, grid.res, grid.W + 2 * PAD, grid.H + 2 * PAD)
    hz = json.loads((Path(a.packet) / "HAZARD.json").read_text())
    specs = {}
    for o in inst["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    feas, flds = {}, {}
    rows, mism, disagree = [], [], []
    cnt = Counter()
    for var in ("cert", "router"):
        for (dnode, dwell), origins in sorted(specs.items()):
            fld = backward(pm.instance(var, [{"node": dnode, "dwell": dwell, "window": [0, H]}], sorted(origins)))
            for o in origins:
                feas[(var, dnode, dwell, o)] = issue_set(fld, pm.nidx[o])
            flds[(var, dnode, dwell)] = fld
        for o in inst["origins"]:
            e = o["entry_node"]
            u = iv.normalize([p for d in o["destinations"] for p in feas[(var, d["node"], d["dwell_s"], e)]])
            lb = u[-1][1] if u and u[0][0] == 0 else None
            want = summ[o["origin_id"]]["nr_" + var]["per_variant"][a.variant] if a.variant != "envelope_burnset" else \
                {"leave_by_s": (summ[o["origin_id"]].get("static_final_footprint_row") or {}).get("nr_" + var)}
            want_lb = want.get("leave_by_s") if isinstance(want, dict) else None
            if lb != want_lb:
                mism.append({"origin": o["origin_id"], "field": var, "recomputed": lb, "committed": want_lb})
                continue
            if lb is None:
                cnt[var + ":no_witness"] += 1
                continue
            ws = []
            for d in o["destinations"]:
                if not iv.contains(feas[(var, d["node"], d["dwell_s"], e)], lb):
                    continue
                w = witness_greedy(flds[(var, d["node"], d["dwell_s"])], pm.nidx[e], lb)
                legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), s_, t_) for k, x, s_, t_ in w[1]]
                segs = [(pm.g.xy(e), pm.g.xy(e)), (pm.g.xy(d["node"]), pm.g.xy(d["node"]))]
                for k, x, _s, _t in w[1]:
                    if k == "EDGE":
                        segs.append((pm.g.xy(pm.g.u[x]), pm.g.xy(pm.g.v[x])))
                    else:
                        p = pm.g.xy(pm.node_ids[x]); segs.append((p, p))
                foot, ring, bnd = tests(grid, wide, segs)
                if foot != bnd:
                    disagree.append({"origin": o["origin_id"], "field": var, "dest": d["node"], "footprint": foot, "boundary": bnd})
                chk = full_check(pm, hz, origin=e, legs=legs, dest=d["node"], dwell=d["dwell_s"], window=[0, H],
                                 departure=lb, incurred=0.0, peak=peak_l, dose=dose_l)
                ok = chk["full_policy_ok"] and chk["closed_and_router_replay_clear"]
                cnt["%s:witness_check_%s" % (var, "PASS" if ok else "FAIL")] += 1
                ws.append({"dest": d["node"], "touch_footprint": foot, "touch_ring_proxy": ring, "touch_boundary": bnd,
                           "check_pass": ok, "codes": chk["codes"], "legs": legs})
                cnt[var + ":witnesses"] += 1
                cnt[var + ":witnesses_touch_footprint"] += foot
                cnt[var + ":witnesses_touch_ring_proxy"] += ring
            anyt, allt = any(w["touch_footprint"] for w in ws), all(w["touch_footprint"] for w in ws)
            cnt[var + ":places_with_witness"] += 1
            cnt[var + ":places_touch_any"] += anyt
            cnt[var + ":places_touch_all"] += allt
            cnt[var + ":places_ring_proxy_any"] += any(w["touch_ring_proxy"] for w in ws)
            rows.append({"origin": o["origin_id"], "field": var, "leave_by_s": lb, "touch_any": anyt, "touch_all": allt,
                         "witnesses": ws})
    out = {"what": "border-touch witnesses (BORDER_TOUCH_RULE.md + amendment 1); UPPER BOUND, see rule",
           "region": a.region, "start": a.start, "horizon_h": h, "variant": a.variant, "H": H,
           "export_grid": [str(grid.x0), str(grid.y0), str(grid.res), grid.W, grid.H], "pad_cells": PAD,
           "counts": dict(cnt), "leave_by_mismatches": mism, "footprint_vs_boundary_disagreements": disagree,
           "rows": rows, "wall_s": time.perf_counter() - t0}
    Path(a.out).write_text(json.dumps(out, default=str))
    print(json.dumps({"counts": out["counts"], "mismatches": len(mism), "disagree": len(disagree)}))


if __name__ == "__main__":
    main()
