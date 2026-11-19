"""25 March 2025 replay: Step 1 (tolerance on the product's raster), the five rules, reconstructed-truth inputs
(PROTOCOL.md sections 3, 4, 5.2).

    python3 replay.py phase1 OUT       # per region-hour, resumable
    python3 replay.py calibrate OUT    # m*, r* for the replay (equal caution, no truth used)
    python3 replay.py phase2 OUT       # product runs b(m*), c(r*)
"""
from __future__ import annotations

import heapq
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import reachpass as RP  # noqa: E402
from twin import M_GRID, R_GRID, P_LIST, S_of, shift_array, shift_close  # noqa: E402

UTC = lib.timezone.utc


def recon_minutes(T):
    """Reconstructed truth: first time a disc of the full record covers the cell centre (kcf-replay analyze)."""
    import analyze as AN
    discs = json.loads((lib.REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]
    for d in discs:
        d["ts"] = lib.datetime.fromisoformat(d["t_utc"]).timestamp()
    cx, cy = lib.cell_centres()
    tc = AN.first_cut_times(discs, cx, cy)
    m = (tc - T.timestamp()) / 60.0
    m = np.where(m > lib.HORIZON_S / 60.0, np.inf, m)
    return m


def inputs(discs, T):
    d = lib.known_distance_m(discs, T)
    r5, r8, cls, info = lib.MA.curve("MEASURED", discs, T, 8)
    X = {"T": T, "cls": cls, "r5": r5, "r8": r8, "m_a": lib.minutes_r90(d, r5, r8),
         "m_f50": lib.minutes_from_curve(d, lib.knots_r50(cls)), "e": {}}
    for p in P_LIST:
        kn, src = lib.knots_expected(T, "DET", p)
        X["e"][p] = (lib.minutes_from_curve(d, kn), kn, src)
    a80 = [r for r in json.loads((lib.REPO / "research/kcf-margin/numbers.json").read_text())["table"]
           if r["fire_set"] == "all28" and r["alpha"] == 0.2 and r["cls"] == cls]
    X["k80"] = lib.knots_measured(*[x["R_km"] for x in sorted(a80, key=lambda r: r["h"])])
    X["m_a80"] = lib.minutes_from_curve(d, X["k80"])
    return X


# ------------------------------------------------------------------------------------------------ single shelter
def one_shelter(g, close_arr, sn, origin_nodes, H=lib.HORIZON_S, dwell=lib.DWELL):
    """Latest departure of each origin to shelter sn at one closure level; also returns (lo, G, acc)."""
    lo = RP.edge_lo(g.sptr, g.scell, g.sfl, close_arr, H)
    b = close_arr[g.node_cell[sn]]
    acc = H - dwell
    if b < RP.NONE:
        acc = min(acc, max(b - dwell, 0) - 1)
    G = np.empty(g.E, np.int64); L = np.empty(g.E, np.int64)
    nh = g.pidx.shape[0] + g.iidx.shape[0] + 16
    RP.shelter_pass(g.E, g.D, g.pptr, g.pidx, g.iptr, g.iidx, lo, sn, acc, G, L, np.empty(nh, np.int64), np.empty(nh, np.int64))
    out = [int(RP.origin_latest(o, g.optr, g.oidx, g.D, lo, G, close_arr[g.node_cell[o]])) for o in origin_nodes]
    return out, lo, G, acc


def witness_from_field(g, road, lo, G, acc, o, sn, t0):
    """Earliest-arrival journey from o departing t0 restricted to the field (no waiting needed: closures are
    permanent). Returns [(edge, start)] and arrival, or None."""
    best = {}
    h = []
    for j in g.oidx[g.optr[o]:g.optr[o + 1]]:
        j = int(j)
        a = t0 + int(g.D[j])
        if t0 <= lo[j] - 1 and a <= G[j]:
            best[j] = (a, None)
            heapq.heappush(h, (a, j))
    while h:
        a, j = heapq.heappop(h)
        if best[j][0] != a:
            continue
        if int(g.head[j]) == sn and a <= acc:
            legs = []
            k = j
            while k is not None:
                ak, pk = best[k]
                legs.append((k, ak - int(g.D[k])))
                k = pk
            return legs[::-1], a
        v = int(g.head[j])
        for k in g.oidx[g.optr[v]:g.optr[v + 1]]:
            k = int(k)
            if (j, k) in road.forbidden:
                continue
            b = a + int(g.D[k])
            if a <= lo[k] - 1 and b <= G[k] and (k not in best or b < best[k][0]):
                best[k] = (b, j)
                heapq.heappush(h, (b, k))
    return None


def binding(g, road, close_arr, o, sns, ob_close):
    """At this closure level: the shelter giving the latest departure, the witness departing at 0, and the element
    with the least slack (edge: closure start - entry second; shelter: latest accepted - arrival; origin)."""
    best = None
    for sn in sns:
        Ls, lo, G, acc = one_shelter(g, close_arr, sn, [o])
        if Ls[0] >= 0 and (best is None or Ls[0] > best[0]):
            best = (Ls[0], sn, lo, G, acc)
    if best is None:
        return None
    L0, sn, lo, G, acc = best
    w = witness_from_field(g, road, lo, G, acc, o, sn, 0)
    if w is None:
        return {"shelter_node": sn, "edge": None, "kind": "none"}
    legs, arr = w
    cand = []
    for j, s in legs:
        if lo[j] < RP.NONE:
            cand.append((int(lo[j]) - s, "edge", j))
    cand.append((acc - arr, "shelter", sn))
    ob = close_arr[g.node_cell[o]]
    if ob < RP.NONE:
        cand.append((int(ob), "origin", o))
    slack, kind, x = min(cand)
    return {"shelter_node": int(sn), "kind": kind, "edge": int(x) if kind == "edge" else None, "slack_s": int(slack),
            "way": road.source_way[x] if kind == "edge" else None, "route_edges": [int(j) for j, _ in legs]}


def timing_tolerance(g, close_arr, o, sns, hi=lib.HORIZON_S, step=60):
    """Largest m on the step grid with a safe departure at 0 when every closure is m s earlier (bisection; L(m) is
    monotone because shifted instances are nested)."""
    def ok(m):
        arr = shift_array(close_arr, m)
        return any(one_shelter(g, arr, sn, [o])[0][0] >= 0 for sn in sns)
    if not ok(0):
        return -1
    if ok(hi):
        return hi
    lo_, hi_ = 0, hi // step  # ok at lo_*step, not at hi_*step
    while hi_ - lo_ > 1:
        mid = (lo_ + hi_) // 2
        if ok(mid * step):
            lo_ = mid
        else:
            hi_ = mid
    return lo_ * step


# ------------------------------------------------------------------------------------------------ phases
def phase1(out):
    out = Path(out); (out / "replay").mkdir(parents=True, exist_ok=True)
    discs = lib.load_discs()
    for rid in lib.REGIONS:
        reg = lib.region(rid)
        road = reg.road
        g = RP.Graph(road)
        for T in lib.REPLAY_ISSUES:
            tag = "%s_%s" % (rid, T.strftime("%H"))
            fp = out / "replay" / (tag + ".json")
            if fp.exists():
                continue
            t0 = time.time()
            X = inputs(discs, T)
            m_tr = recon_minutes(T)
            closes = {"truth": lib.close_s_from_minutes(rid, m_tr), "a": lib.close_s_from_minutes(rid, X["m_a"]),
                      "d": lib.close_s_from_minutes(rid, X["m_f50"]), "e": lib.close_s_from_minutes(rid, X["e"]["90"][0])}
            res = {"rid": rid, "issue_utc": T.isoformat(), "class": X["cls"], "e_source": X["e"]["90"][2], "e_knots": X["e"]["90"][1],
                   "r50_knots": lib.knots_r50(X["cls"]), "a80_knots": X["k80"], "rules": {}, "close_s": {}}
            for k, cl in closes.items():
                rows, _ = lib.run_product(rid, cl, T)
                res["rules"][k] = lib.summarise_rows(rows)
                res["close_s"][k] = {str(c): b for c, b in cl.items()}
            # ---- Step 1 on the product raster: L(r) over the reach grid, tolerated reach, timing tolerance, binding road
            lv = np.stack([lib.close_array_from_minutes(rid, lib.dilate_minutes(X["m_a"], r)) for r in R_GRID])
            Lr = RP.latest_by_level(g, reg, lv, lib.HORIZON_S, lib.DWELL)[0]
            base = lv[0]
            frag = {}
            for o in reg.origins:
                pid = o["id"]
                if pid not in Lr or res["rules"]["a"][pid]["refused"]:
                    continue
                sns = [s["node"] for s in reg.cands[pid]]
                L = Lr[pid]
                ks = [k for k in range(len(R_GRID)) if L[k] >= 0]
                kt = max(ks) if ks else -1
                f = {"L_by_r": [int(x) for x in L], "R_tol_km": R_GRID[kt] if kt >= 0 else None,
                     "R_tol_censored": kt == len(R_GRID) - 1}
                f["reach_binding"] = binding(g, road, lv[kt], o["node"], sns, None) if kt >= 0 else None
                tt = timing_tolerance(g, base, o["node"], sns)
                f["T_tol_s"] = tt
                f["T_tol_censored"] = tt == lib.HORIZON_S
                f["timing_binding"] = binding(g, road, shift_array(base, tt), o["node"], sns, None) if tt >= 0 else None
                frag[pid] = f
            res["fragility"] = frag
            # ---- curves for b, c (F50) and the secondary arms
            fbase = lib.close_array_from_minutes(rid, X["m_f50"])
            curves = {"b": RP.latest_by_level(g, reg, np.stack([shift_array(fbase, m) for m in M_GRID]), lib.HORIZON_S, lib.DWELL)[0],
                      "c": RP.latest_by_level(g, reg, np.stack([lib.close_array_from_minutes(rid, lib.dilate_minutes(X["m_f50"], r))
                                                                for r in R_GRID]), lib.HORIZON_S, lib.DWELL)[0],
                      "other": RP.latest_by_level(g, reg, np.stack([lib.close_array_from_minutes(rid, X["e"][p][0]) for p in P_LIST]
                                                                   + [lib.close_array_from_minutes(rid, X["m_a80"]), base,
                                                                      lib.close_array_from_minutes(rid, m_tr)]),
                                                  lib.HORIZON_S, lib.DWELL, nested=False)[0]}
            np.savez_compressed(out / "replay" / (tag + "_curves.npz"),
                                **{"%s|%s" % (k, oid): v for k, cv in curves.items() for oid, v in cv.items()})
            res["curve_axes"] = {"b_m_s": M_GRID, "c_r_km": R_GRID, "other": ["e%s" % p for p in P_LIST] + ["a80", "a", "truth"]}
            res["close_s"]["f50"] = {str(c): b for c, b in lib.close_s_from_minutes(rid, X["m_f50"]).items()}
            res["e_close_s"] = {p: {str(c): b for c, b in lib.close_s_from_minutes(rid, X["e"][p][0]).items()} for p in P_LIST}
            res["seconds"] = round(time.time() - t0, 1)
            fp.write_text(json.dumps(res))
            print(tag, X["cls"], res["seconds"], "s", flush=True)


def tags():
    return ["%s_%s" % (rid, T.strftime("%H")) for rid in lib.REGIONS for T in lib.REPLAY_ISSUES]


def load_curves(out, tag):
    z = np.load(Path(out) / "replay" / (tag + "_curves.npz"))
    cur = {}
    for k in z.files:
        kind, oid = k.split("|", 1)
        cur.setdefault(kind, {})[oid] = z[k]
    return cur


def calibrate(out):
    out = Path(out)
    discs = lib.load_discs()
    S_a, ev, curves, meta = 0, {}, {}, {}
    for tag in tags():
        res = json.loads((out / "replay" / (tag + ".json")).read_text())
        refused = {pid for k in res["rules"] for pid, r in res["rules"][k].items() if r["refused"]}
        ev[tag] = sorted(pid for pid in res["rules"]["a"] if pid not in refused)
        S_a += S_of(res["rules"]["a"][pid]["L"] for pid in ev[tag])
        curves[tag] = load_curves(out, tag)
        meta[tag] = (res["rid"], lib.datetime.fromisoformat(res["issue_utc"]))
    n = sum(len(v) for v in ev.values())
    Sb = [sum(S_of(curves[t]["b"][p][k] for p in ev[t]) for t in ev) for k in range(len(M_GRID))]
    Sc = [sum(S_of(curves[t]["c"][p][k] for p in ev[t]) for t in ev) for k in range(len(R_GRID))]
    kb = next(k for k, s in enumerate(Sb) if s <= S_a)
    kc = next(k for k, s in enumerate(Sc) if s <= S_a)
    m_star = M_GRID[kb]
    if kb > 0:
        fine = list(range(M_GRID[kb - 1] + 60, M_GRID[kb], 60))
        Sf = [0] * len(fine)
        for t in ev:
            rid, T = meta[t]
            reg = lib.region(rid)
            g = RP.Graph(reg.road)
            X = inputs(discs, T)
            fb = lib.close_array_from_minutes(rid, X["m_f50"])
            best = RP.latest_by_level(g, reg, np.stack([shift_array(fb, m) for m in fine]), lib.HORIZON_S, lib.DWELL)[0]
            for i in range(len(fine)):
                Sf[i] += S_of(best[p][i] for p in ev[t])
        for i, m in enumerate(fine):
            if Sf[i] <= S_a:
                m_star = m
                break
    cal = {"S_a": S_a, "m_star_s": m_star, "r_star_km": R_GRID[kc], "n_place_pairs": n, "mean_leave_by_a_min": S_a / n / 60.0,
           "S_b_curve": dict(zip(map(str, M_GRID), Sb)), "S_c_curve": dict(zip(map(str, R_GRID), Sc))}
    (out / "replay_calibration.json").write_text(json.dumps(cal, indent=1))
    print({k: v for k, v in cal.items() if not k.endswith("curve")})


def phase2(out):
    out = Path(out)
    cal = json.loads((out / "replay_calibration.json").read_text())
    discs = lib.load_discs()
    for tag in tags():
        fp = out / "replay" / (tag + "_bc.json")
        if fp.exists():
            continue
        res = json.loads((out / "replay" / (tag + ".json")).read_text())
        rid, T = res["rid"], lib.datetime.fromisoformat(res["issue_utc"])
        X = inputs(discs, T)
        f50 = lib.close_s_from_minutes(rid, X["m_f50"])
        o = {"m_star_s": cal["m_star_s"], "r_star_km": cal["r_star_km"], "rules": {}, "close_s": {}}
        for k, cl in (("b", shift_close(f50, cal["m_star_s"])),
                      ("c", lib.close_s_from_minutes(rid, lib.dilate_minutes(X["m_f50"], cal["r_star_km"])))):
            rows, _ = lib.run_product(rid, cl, T)
            o["rules"][k] = lib.summarise_rows(rows)
            o["close_s"][k] = {str(c): b for c, b in cl.items()}
        fp.write_text(json.dumps(o))
        print(tag, "b,c done", flush=True)


if __name__ == "__main__":
    {"phase1": phase1, "calibrate": calibrate, "phase2": phase2}[sys.argv[1]](sys.argv[2])
