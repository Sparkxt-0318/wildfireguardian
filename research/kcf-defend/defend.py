"""Per (region, arm, horizon, issue hour): base windows and the window gain of every ROAD and FRONT candidate for
delays of 30, 60, 120 min (PROTOCOL.md §2-§4). Output: one JSON per job.

Usage: python3 defend.py OUT_DIR [--workers 4] [--arms ...] [--horizons ...] [--hours 3 ... 15]
"""
from __future__ import annotations

import argparse, json, time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import fastfield as FF

DELAYS = (30, 60, 120)
TILE = 2000.0
REG = {}


def base_state(R, arm, T, H):
    d = R.dist(T)
    f, info = R.curve(arm, T, H)
    cs = np.full(d.shape, np.inf)
    m = np.isfinite(d)
    cs[m] = f(d[m])
    b = R.closures(cs, H)
    return d, f, info, cs, b


def solve_all(R, b, H, shelters=None, fields=None):
    lo = R.edge_lo(b)
    fields = {} if fields is None else dict(fields)
    for s in (range(len(R.shelter_nodes)) if shelters is None else shelters):
        fields[s] = R.shelter_field(b, lo, H, s)
    return lo, fields


def place_values(R, b, lo, fields, places=None):
    """-> {p: (best value, best shelter index or None, per-shelter values)}; ties as replay.run_one."""
    out = {}
    for p in (range(len(R.places)) if places is None else places):
        per = {s: R.issue_value(fields[s], lo, b, p) for s in R.pl_sh[p]}
        best, bs = -1, None
        for s in sorted(per):  # pl_sh holds indices in replay's global shelter order
            if per[s] > best:
                best, bs = per[s], s
        out[p] = (best, bs, per)
    return out


def binding_cells(R, b, lo, g):
    """Cells whose delay can change this shelter field: cells attaining lo_j of binding edges j."""
    bind = (lo - 1) < (g - R.D)
    if not bind.any():
        return set()
    bc = b[R.seg_cell]
    sel = bind[R.seg_edge] & (bc >= 0)
    att = sel & (np.maximum(bc - R.seg_fl, 0) == lo[R.seg_edge])
    return set(np.unique(R.seg_cell[att]).tolist())


def front_tiles(R, T, d, b, H):
    """Per relevant cell (d > 0, 0 <= b <= H): per-tile min distance. -> (cells, tiles, M[cells, tiles])."""
    cells = np.where((d > 0) & np.isfinite(d) & (b >= 0))[0]
    sel = [x for x in FF.DISCS if x["t"] < T]
    if not len(cells) or not sel:
        return cells, [], np.zeros((len(cells), 0))
    cx, cy = R.R.cxy
    X = np.array([x["x"] for x in sel]); Y = np.array([x["y"] for x in sel]); Rr = np.array([x["r_m"] for x in sel])
    key = [(int(np.floor(x / TILE)), int(np.floor(y / TILE))) for x, y in zip(X, Y)]
    tiles = sorted(set(key))
    tix = {t: i for i, t in enumerate(tiles)}
    kt = np.array([tix[k] for k in key])
    M = np.full((len(cells), len(tiles)), np.inf)
    for i in range(0, len(sel), 1000):
        dd = np.sqrt((cx[cells][:, None] - X[None, i:i + 1000]) ** 2 + (cy[cells][:, None] - Y[None, i:i + 1000]) ** 2) - Rr[None, i:i + 1000]
        dd = np.maximum(dd, 0)
        for t in np.unique(kt[i:i + 1000]):
            cols = np.where(kt[i:i + 1000] == t)[0]
            M[:, t] = np.minimum(M[:, t], dd[:, cols].min(1))
    assert np.array_equal(M.min(1), d[cells]), "per-tile distances disagree with replay.cell_distance"
    return cells, tiles, M


def evaluate(R, b, H, lo, fields, base, changes):
    """changes: {cell: new b (-1 = none)}. -> {place: gain seconds > 0}."""
    if not changes:
        return {}
    ch = set(changes)
    aff = [s for s in range(len(R.shelter_nodes))
           if (int(R.node_cell[R.sh_node[s]]) in ch) or (BIND[s] & ch)]
    pl = set()
    for s in aff:
        pl.update(R.sh_places[s])
    for p in range(len(R.places)):
        if int(R.node_cell[R.pl_node[p]]) in ch or (OUTCELLS[p] & ch):
            pl.add(p)
    if not pl:
        return {}
    b2 = b.copy()
    for c, v in changes.items():
        b2[c] = v
    lo2 = R.edge_lo(b2)
    f2 = dict(fields)
    for s in aff:
        f2[s] = R.shelter_field(b2, lo2, H, s)
    vals = place_values(R, b2, lo2, f2, sorted(pl))
    out = {}
    for p, (v, _, _) in vals.items():
        w0 = base[p][0] + 1
        w1 = v + 1
        assert w1 >= w0, ("window shrank under a delay", p, w0, w1)
        if w1 > w0:
            out[p] = w1 - w0
    return out


def candidate_changes(R, T, d, f, b, H):
    """Yields (kind, id, meta, delay_min, {cell: new b}) for every candidate and delay, in a fixed order."""
    region = R.R.region
    for c in R.road_cells:
        c = int(c)
        if not (0 < b[c] <= H and d[c] > 0):
            continue
        for D in DELAYS:
            nb = int(b[c]) + 60 * D
            yield "ROAD", f"ROAD:{region}:{c}", {"cell": c, "b_s": int(b[c])}, D, {c: (nb if nb <= H else -1)}
    cells, tiles, M = front_tiles(R, T, d, b, H)
    if not len(tiles):
        return
    near = M.argmin(1)
    for t in sorted(set(near[b[cells] > 0].tolist())):
        other = np.delete(M, t, axis=1).min(1) if M.shape[1] > 1 else np.full(len(cells), np.inf)
        dS = M[:, t]
        fo = np.full(len(cells), np.inf); fs = np.full(len(cells), np.inf)
        mo = np.isfinite(other); fo[mo] = f(other[mo])
        ms = np.isfinite(dS); fs[ms] = f(dS[ms])
        tx, ty = tiles[t]
        nd = int(sum(1 for x in FF.DISCS if x["t"] < T and (int(np.floor(x["x"] / TILE)), int(np.floor(x["y"] / TILE))) == (tx, ty)))
        for D in DELAYS:
            new = np.minimum(fo, fs + 60 * D)
            nb = np.where(np.isfinite(new) & (new <= H), np.ceil(np.where(np.isfinite(new), new, 0)), -1).astype(np.int64)
            ch = {int(c): int(v) for c, v, o in zip(cells, nb, b[cells]) if v != o}
            for c, v in ch.items():
                assert v == -1 or v >= b[c], "a delay moved a closure earlier"
            yield "FRONT", f"FRONT:{tx}_{ty}", {"tile": [tx, ty], "n_discs": nd}, D, ch


BIND = {}
OUTCELLS = {}


def prepare(R, b, lo, fields):
    BIND.clear(); OUTCELLS.clear()
    for s, g in fields.items():
        BIND[s] = binding_cells(R, b, lo, g)
    for p in range(len(R.places)):
        OUTCELLS[p] = set(R.seg_cell[np.isin(R.seg_edge, R.pl_out[p])].tolist())


def run_job(args):
    region, arm, hz, hour = args
    t0 = time.time()
    R = REG[region]
    H = FF.HORIZONS[hz]
    T = datetime(2025, 3, 25, hour, tzinfo=timezone.utc)
    d, f, info, cs, b = base_state(R, arm, T, H)
    lo, fields = solve_all(R, b, H)
    base = place_values(R, b, lo, fields)
    prepare(R, b, lo, fields)
    # free (no-closure) values for the state label
    nob = np.full_like(b, -1)
    lo0, f0 = solve_all(R, nob, H, shelters=sorted({base[p][1] for p in base if base[p][1] is not None}))
    rows = []
    for p in range(len(R.places)):
        v, s, per = base[p]
        oid = R.places[p]
        inside = bool(d[R.node_cell[R.pl_node[p]]] == 0)
        if v < 0:
            state = "INSIDE" if inside else "NO_WINDOW"
        else:
            free = R.issue_value(f0[s], lo0, nob, p)
            state = "CUT" if v < free else "NOT_CUT_WITHIN_H"
        sh = None
        if s is not None:
            snode = R.shelter_nodes[s]
            sh = next(x for x in R.R.cands[oid][1] if x["properties"]["entry"]["node"] == snode)["properties"]["id"]
        rows.append({"place_id": oid, "ld_s": int(v), "state": state, "shelter_id": sh,
                     "per_shelter": {R.R.cands[oid][1][[x["properties"]["entry"]["node"] for x in R.R.cands[oid][1]].index(R.shelter_nodes[k])]["properties"]["id"]: int(w) for k, w in per.items()},
                     "dist_m": None if not np.isfinite(d[R.node_cell[R.pl_node[p]]]) else float(d[R.node_cell[R.pl_node[p]]])})
    cands = []
    road = []
    for kind, cid, meta, D, ch in candidate_changes(R, T, d, f, b, H):
        if kind == "ROAD" and D == DELAYS[0]:
            road.append(cid)
        if D == DELAYS[0]:
            cands.append(dict(meta, id=cid, type=kind, gains={}))
        cur = cands[-1]
        if kind == "FRONT":
            cur["cells_changed_max"] = max(cur.get("cells_changed_max", 0), len(ch))
        gains = evaluate(R, b, H, lo, fields, base, ch)
        if gains:
            cur["gains"][D] = {str(k): v for k, v in gains.items()}
    ftiles = [c for c in cands if c["type"] == "FRONT"]
    return {"region": region, "arm": arm, "horizon": hz, "issue_utc": T.isoformat(), "arm_class": info,
            "closed_cells": int((b >= 0).sum()), "n_road_candidates": len(road), "n_front_candidates": len(ftiles),
            "places": rows, "candidates": cands, "wall_s": round(time.time() - t0, 1)}


def init(regions):
    FF.load_discs()
    for r in regions:
        REG[r] = FF.FastRegion(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--regions", nargs="+", default=FF.REGIONS)
    ap.add_argument("--arms", nargs="+", default=FF.ARMS)
    ap.add_argument("--horizons", nargs="+", default=list(FF.HORIZONS))
    ap.add_argument("--hours", nargs="+", type=int, default=list(range(3, 16)))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    jobs = [(r, s, h, i) for s in a.arms for h in a.horizons for i in a.hours for r in a.regions]
    jobs = [j for j in jobs if not (out / f"{j[0]}__{j[1]}__{j[2]}__{j[3]:02d}.json").exists()]
    print(len(jobs), "jobs", flush=True)
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(a.regions,)) as ex:
        for res in ex.map(run_job, jobs):
            p = out / f"{res['region']}__{res['arm']}__{res['horizon']}__{res['issue_utc'][11:13]}.json"
            p.write_text(json.dumps(res, default=lambda o: o.item()))
            print(p.name, "road", res["n_road_candidates"], "front", res["n_front_candidates"],
                  "with gain", sum(1 for c in res["candidates"] if c["gains"]), res["wall_s"], "s", flush=True)


if __name__ == "__main__":
    main()
