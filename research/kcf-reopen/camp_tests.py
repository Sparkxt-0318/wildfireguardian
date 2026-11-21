"""Step 4 (PROTOCOL §5): the Camp Fire tests with closure windows.
Usage: python3 -I camp_tests.py GRAPH.json OUT_DIR
Inputs, hold-outs, burnover placement and movements are kcf-camp's (research/kcf-camp, unchanged; the burnover
placement loop below is copied from its score_tests12.py). New: the reopening R = max(C, A + tau) of PROTOCOL §1, with
A = the cell's earliest input FIRE_ARRIVAL observation (own cell; "nbr" = any observed cell within 375 m, exploratory).

Rules:  perm     closures permanent (kcf-camp)
        w105/w240/w465   responders, tau = 105 / 240 / 465 min (low / frozen / high, out/tau.json)
        res240   residents: window only where confirmed (PROTOCOL §1.1) by a ROAD_PASSABLE or vehicle-present row u with
                 R <= u <= t, held out like the fire input (not the scored row, not within 500 m and +-60 min of it)
        nbr240   responders, tau 240, neighbour arrival (exploratory)"""
import heapq, json, math, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kcf-camp"))
sys.path.insert(0, str(HERE.parent / "kcf-theorem"))
from model import (HERE as CAMP, HOLD_M, HOLD_MIN, R_ALL, R_RUN, TOL_MIN, TO_UTM, VARIANTS, Field, Graph, closure_min,  # noqa: E402
                   hhmm, minutes, read_csv, verdict, wilson, write_csv)
import checker  # noqa: E402
from wfg_roadlayer import engine  # noqa: E402

G = Graph(sys.argv[1])
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
TAU = json.load(open(HERE / "out/tau.json"))["frozen"]
RULES = {"perm": None, "w105": TAU["tau_low_min"], "w240": TAU["tau_min"], "w465": TAU["tau_high_min"], "res240": TAU["tau_min"],
         "nbr240": TAU["tau_min"]}
assert (TAU["tau_low_min"], TAU["tau_min"], TAU["tau_high_min"]) == (105, 240, 465), TAU
INF = math.inf

obs = {r["obs_id"]: r for r in read_csv(CAMP / "data/observations_dedup.csv") if ":" in r["time"]}
cls = {r["obs_id"]: r["class_final"] for r in read_csv(CAMP / "data/classes_final.csv")}
for k, r in obs.items():
    r["cls"] = cls[k]; r["t"] = minutes(r["day"], r["time"])
    r["x"], r["y"] = TO_UTM.transform(float(r["lon"]), float(r["lat"]))
    r["veh"] = "AVL" in r["location_source"]
    r["cell"] = G.match(r["x"], r["y"])[0]
fire = [r for r in obs.values() if r["cls"] == "FIRE_ARRIVAL"]
fx = np.array([[r["x"], r["y"], r["t"]] for r in fire])
road = [r for r in obs.values() if r["cls"].startswith("ROAD_")]
scored = [r for r in road if r["cls"] in ("ROAD_CLOSED", "ROAD_PASSABLE")]
conf_rows = [r for r in obs.values() if (r["cls"] == "ROAD_PASSABLE" or r["veh"]) and r["cell"] is not None]
vehicle = sorted([r for r in obs.values() if r["veh"] and r["cell"] is not None], key=lambda r: (r["t"], r["obs_id"]))


def holdout_mask(points, rows):
    """True = keep: rows not within HOLD_M and HOLD_MIN of any (x, y, t) in points."""
    a = np.array([[r["x"], r["y"], r["t"]] for r in rows]) if rows else np.zeros((0, 3))
    keep = np.ones(len(rows), bool)
    for x, y, t in points:
        keep &= ~((np.hypot(a[:, 0] - x, a[:, 1] - y) <= HOLD_M) & (np.abs(a[:, 2] - t) <= HOLD_MIN))
    return keep


class WField(Field):
    def __init__(self, G, fobs, conf):
        super().__init__(G, fobs)
        self.conf = {}
        for r in conf:
            self.conf.setdefault(r["cell"], []).append(r["t"])
        self._nbr = {}
        self._cl = {}

    def closure(self, c, variant):
        k = (int(c), variant)
        if k not in self._cl:
            self._cl[k] = super().closure(c, variant)
        return self._cl[k]

    def arrival(self, c, rule):
        if rule == "nbr240":
            if c not in self._nbr:
                if not len(self.cells):
                    self._nbr[c] = None
                else:
                    x, y = self.G.centre(c)
                    d = np.hypot(self.xy[:, 0] - x, self.xy[:, 1] - y)
                    ok = d <= 375.0 + 1e-6
                    self._nbr[c] = float(self.t[ok].min()) if ok.any() else None
            return self._nbr[c]
        return self.first.get(int(c))

    def window(self, c, v, rule, t_query=None):
        """(C, R): closed on [C, R). Residents: R finite only if confirmed at u in [R, t_query]."""
        C = self.closure(c, v)
        tau = RULES[rule]
        if tau is None or not math.isfinite(C):
            return C, INF
        A = self.arrival(c, rule)
        if A is None:
            return C, INF
        R = max(C, A + tau)
        if rule.startswith("res"):
            if t_query is None or not any(R <= u <= t_query for u in self.conf.get(int(c), ())):
                return C, INF
        return C, R


# ------------------------------------------------------------------ Test 4.2 and 4.3 (i): road-state reports
near = np.zeros(len(fire), bool)
for r in scored:
    near |= (np.hypot(fx[:, 0] - r["x"], fx[:, 1] - r["y"]) <= HOLD_M) & (np.abs(fx[:, 2] - r["t"]) <= HOLD_MIN)
strict_fire = [(r["x"], r["y"], r["t"]) for r, d in zip(fire, near) if not d]
conf_keep = holdout_mask([(r["x"], r["y"], r["t"]) for r in scored], conf_rows)
F1 = WField(G, strict_fire, [r for r, k in zip(conf_rows, conf_keep) if k])


def state_at(Fd, c, v, rule, t):
    C, R = Fd.window(c, v, rule, t)
    if C <= t - TOL_MIN and R > t + TOL_MIN:
        return "closed", C, R
    return ("open" if C > t - TOL_MIN else "burned_over"), C, R


rows42, rows43 = [], []
for r in sorted(scored, key=lambda r: (r["t"], r["obs_id"])):
    if r["cell"] is None:
        continue
    row = {"obs_id": r["obs_id"], "class": r["cls"], "day": r["day"], "time": r["time"], "cell": r["cell"], "vehicle_located": r["veh"], "text": r["text"]}
    for v in VARIANTS:
        for rule in RULES:
            C, R = F1.window(r["cell"], v, rule, r["t"])
            if r["cls"] == "ROAD_CLOSED":
                st = "HIT" if (C <= r["t"] + TOL_MIN and R > r["t"] - TOL_MIN) else ("REOPENED_TOO_EARLY" if C <= r["t"] + TOL_MIN else "MISS")
            else:
                st = state_at(F1, r["cell"], v, rule, r["t"])[0]
            row["%s_%s" % (v, rule)] = st
            if rule in ("perm", "w240"):
                row["C_%s" % v] = hhmm(C); row["R_%s_%s" % (v, rule)] = hhmm(R)
    (rows43 if r["cls"] == "ROAD_CLOSED" else rows42).append(row)
write_csv(OUT / "t43_blocked_reports.csv", rows43)
write_csv(OUT / "t42_passable_reports.csv", rows42)

# vehicle-present observations: one field per observation
rowsv = []
for r in vehicle:
    keep = ~((np.hypot(fx[:, 0] - r["x"], fx[:, 1] - r["y"]) <= HOLD_M) & (np.abs(fx[:, 2] - r["t"]) <= HOLD_MIN))
    fin = [(q["x"], q["y"], q["t"]) for q, k in zip(fire, keep) if k and q["obs_id"] != r["obs_id"]]
    ck = holdout_mask([(r["x"], r["y"], r["t"])], conf_rows)
    Fv = WField(G, fin, [q for q, k in zip(conf_rows, ck) if k and q["obs_id"] != r["obs_id"]])
    row = {"obs_id": r["obs_id"], "class": r["cls"], "day": r["day"], "time": r["time"], "cell": r["cell"], "location_source": r["location_source"],
           "text": r["text"]}
    for v in VARIANTS:
        for rule in RULES:
            row["%s_%s" % (v, rule)] = state_at(Fv, r["cell"], v, rule, r["t"])[0]
    rowsv.append(row)
write_csv(OUT / "t42_vehicle_present.csv", rowsv)


def summ42(rows):
    out = {}
    for v in VARIANTS:
        for rule in RULES:
            k = "%s_%s" % (v, rule)
            n = len(rows); cl = sum(r[k] == "closed" for r in rows)
            ci = wilson(cl, n)
            out[k] = {"n": n, "open": sum(r[k] == "open" for r in rows), "burned_over": sum(r[k] == "burned_over" for r in rows), "closed": cl,
                      "closed_share": round(cl / n, 3) if n else None, "closed_ci95": ci, "verdict": verdict(ci, 0.20, False, n),
                      "distinct_cells": len({r["cell"] for r in rows}), "distinct_cells_not_closed": len({r["cell"] for r in rows if r[k] != "closed"})}
    return out


def summ43(rows):
    out = {}
    for v in VARIANTS:
        base = sum(r["%s_perm" % v] == "HIT" for r in rows)
        for rule in RULES:
            k = "%s_%s" % (v, rule)
            h = sum(r[k] == "HIT" for r in rows); e = sum(r[k] == "REOPENED_TOO_EARLY" for r in rows)
            out[k] = {"n": len(rows), "hits": h, "hits_perm": base, "reopened_too_early": e, "verdict": "PASS" if h == base else "FAIL"}
    return out


res = {"tau": TAU, "t42_passable": summ42(rows42), "t42_vehicle": summ42(rowsv), "t43_blocked": summ43(rows43),
       "counts": {"strict_fire_input": len(strict_fire), "confirmation_rows": len(conf_rows), "vehicle_present_placed": len(vehicle),
                  "vehicle_present_cells": len({r["cell"] for r in vehicle})}}
# by class of the vehicle row (a vehicle row is also a fire, road or other report)
res["t42_vehicle_by_class"] = {c: summ42([r for r in rowsv if r["class"] == c]) for c in sorted({r["class"] for r in rowsv})}

# crossfit (PROTOCOL 2.3): reopened-too-early with each half scored by the other half's tau
xm = json.load(open(HERE / "out/tau.json"))["crossfit"]
half_tau = {"west": xm["halves"]["east"]["tau_min"], "east": xm["halves"]["west"]["tau_min"]}
cf = {}
for v in VARIANTS:
    e = 0
    for r in rows43:
        tau = half_tau["west" if G.centre(r["cell"])[0] < xm["split_easting_m"] else "east"]
        C = F1.closure(r["cell"], v); A = F1.first.get(int(r["cell"]))
        R = INF if A is None or not math.isfinite(C) else max(C, A + tau)
        t = minutes(r["day"], r["time"])
        e += C <= t + TOL_MIN and R <= t - TOL_MIN
    cf[v] = {"reopened_too_early": e, "tau_used": half_tau}
res["t43_crossfit"] = cf

# ------------------------------------------------------------------ Test 4.3 (ii): burnovers (placement copied from kcf-camp)
pts_by_name = {}
for e in G.raw["edges"]:
    if e["name"] and (e["reverse_edge"] is None or e["id"].endswith(":f")):
        for a, b in zip(e["geom"][:-1], e["geom"][1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(L // 25))
            for k in range(n + 1):
                pts_by_name.setdefault(e["name"], []).append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
for k in pts_by_name:
    pts_by_name[k] = np.unique(np.round(np.array(pts_by_name[k]), 1), axis=0)


def junction(n1, n2):
    A, B = pts_by_name.get(n1), pts_by_name.get(n2)
    if A is None or B is None:
        return None, "road name not on graph"
    from scipy.spatial import cKDTree
    d, j = cKDTree(B).query(A)
    i = int(np.argmin(d))
    if d[i] > 60:
        return None, "do not meet"
    return A[i], "junction %s / %s" % (n1, n2)


st37 = [r for r in obs.values() if "station 37" in r["text"].lower()]
rows2 = []
for b in read_csv(CAMP / "data/burnovers_tn2252.csv"):
    name = b["loc_road"]; P = pts_by_name.get(name)
    L = float(b["length_affected_m"]) if b["length_affected_m"] else None
    rad = L / 2 if L else 400.0
    sel = None
    if P is None:
        pass
    elif b["loc_method"] in ("point", "obs_point", "road_centroid", "junction"):
        if b["loc_method"] == "point":
            cxy = TO_UTM.transform(float(b["loc_lon"]), float(b["loc_lat"]))
        elif b["loc_method"] == "obs_point":
            r0 = min(st37, key=lambda r: r["t"]); cxy = (r0["x"], r0["y"])
        elif b["loc_method"] == "road_centroid":
            m = P.mean(0); cxy = tuple(P[int(np.argmin(np.hypot(P[:, 0] - m[0], P[:, 1] - m[1])))])
        else:
            cxy, _ = junction(name, b["loc_road2"])
        if cxy is not None:
            d0 = np.hypot(P[:, 0] - cxy[0], P[:, 1] - cxy[1])
            if d0.min() <= 375:
                sel = P[d0 <= max(rad, d0.min() + 1)]
    elif b["loc_method"] in ("between", "between_junctions"):
        if b["loc_method"] == "between":
            a = TO_UTM.transform(float(b["loc_lon"]), float(b["loc_lat"])); bb = TO_UTM.transform(-121.585289, 39.798183)
        else:
            r1, r2 = b["loc_road2"].split("|")
            a, _ = junction(name, r1); bb, _ = junction(name, r2)
        if a is not None and bb is not None:
            D = math.hypot(a[0] - bb[0], a[1] - bb[1])
            dd = np.hypot(P[:, 0] - a[0], P[:, 1] - a[1]) + np.hypot(P[:, 0] - bb[0], P[:, 1] - bb[1])
            sel = P[dd <= D + 200.0]
    if sel is None or not len(sel):
        rows2.append({"bo_id": b["bo_id"], "placed": "no"}); continue
    cells = sorted({G.cell(x, y) for x, y in sel} & G.road_set)
    t0 = minutes(b["date"][5:], b["initiation"])
    keep = np.ones(len(fire), bool)
    pts = sel[:: max(1, len(sel) // 200)]
    for x, y in pts:
        keep &= ~((np.hypot(fx[:, 0] - x, fx[:, 1] - y) <= HOLD_M) & (np.abs(fx[:, 2] - t0) <= HOLD_MIN))
    ck = holdout_mask([(x, y, t0) for x, y in pts], conf_rows)
    Fb = WField(G, [(r["x"], r["y"], r["t"]) for r, k in zip(fire, keep) if k], [q for q, k in zip(conf_rows, ck) if k])
    row = {"bo_id": b["bo_id"], "location": b["location"], "initiation": b["date"][5:] + " " + b["initiation"], "placed": "yes", "n_cells": len(cells)}
    for v in VARIANTS:
        for rule in RULES:
            for lab, tq in (("t-60", t0 - 60), ("t-30", t0 - 30), ("t", t0)):
                ws = [Fb.window(c, v, rule, tq) for c in cells]
                st = "CLOSED" if any(C <= tq < R for C, R in ws) else ("UNSAFE" if any(C <= tq + 30 and R > tq for C, R in ws) else "OPEN")
                row["%s_%s_%s" % (v, rule, lab)] = st
    rows2.append(row)
write_csv(OUT / "t43_burnovers.csv", rows2, list(max(rows2, key=len).keys()))
pl = [r for r in rows2 if r["placed"] == "yes"]
bo = {}
for v in VARIANTS:
    for rule in RULES:
        d = {lab: sum(r["%s_%s_%s" % (v, rule, lab)] in ("CLOSED", "UNSAFE") for r in pl) for lab in ("t-60", "t-30", "t")}
        base = {lab: sum(r["%s_perm_%s" % (v, lab)] in ("CLOSED", "UNSAFE") for r in pl) for lab in ("t-60", "t-30", "t")}
        lost = [r["bo_id"] for r in pl if any(r["%s_perm_%s" % (v, lab)] in ("CLOSED", "UNSAFE") and r["%s_%s_%s" % (v, rule, lab)] == "OPEN"
                                                for lab in ("t-60", "t-30", "t"))]
        bo["%s_%s" % (v, rule)] = {"n": len(pl), "closed_or_unsafe": d, "perm": base, "lost_burnovers": lost, "verdict": "PASS" if not lost else "FAIL"}
res["t43_burnovers"] = bo
(OUT / "camp_tests12.json").write_text(json.dumps(res, indent=1))

# ------------------------------------------------------------------ Test 4.1: the two movements
rd = G.road
Hs, DWELL = 7200, 120
rc = [int(c) for c in rd.road_cells]
rc_xy = np.array([G.centre(c) for c in rc])
name = {j: e["name"] for j, e in enumerate(G.raw["edges"])}
length = {j: e["length_m"] for j, e in enumerate(G.raw["edges"])}
fire_all = [(r["x"], r["y"], r["t"]) for r in fire]


def windows_at(T, v, rule):
    """close_s, open_s in seconds after T (kcf-camp test3 closures; reopening R - T)."""
    first = {}
    for x, y, t in fire_all:
        if t < T:
            c = G.cell(x, y)
            if c is not None and t < first.get(c, INF):
                first[c] = t
    if v in ("M0", "M30"):
        close = {c: 0 for c in first if c in G.road_set}
    else:
        R5, R8 = R_ALL if v == "MR" else R_RUN
        oxy = np.array([G.centre(c) for c in first])
        close = {}
        for c, (x, y) in zip(rc, rc_xy):
            m = closure_min(R5, R8, float(np.min(np.hypot(oxy[:, 0] - x, oxy[:, 1] - y))))
            if m * 60 <= Hs:
                close[c] = int(math.ceil(m * 60))
    tau = RULES[rule]
    opn = {}
    if tau is not None:
        oc = np.array(list(first.keys())); ot = np.array([first[c] for c in oc], float); oxy = np.array([G.centre(c) for c in oc])
        conf = {}
        for r in conf_rows:
            if r["t"] <= T:
                conf.setdefault(r["cell"], []).append(r["t"])
        for c, b in close.items():
            if rule == "nbr240":
                x, y = G.centre(c); d = np.hypot(oxy[:, 0] - x, oxy[:, 1] - y); ok = d <= 375.0 + 1e-6
                A = float(ot[ok].min()) if ok.any() else None
            else:
                A = first.get(c)
            if A is None:
                continue
            r_s = int(math.ceil((A + tau - T) * 60))
            if rule.startswith("res") and not any(A + tau <= u <= T for u in conf.get(c, ())):
                continue
            opn[c] = r_s
    return close, opn


def nearest_node(lat, lon):
    x, y = TO_UTM.transform(lon, lat)
    d = [math.hypot(a - x, b - y) for a, b in rd.node_xy]
    i = int(np.argmin(d)); return i, round(d[i])


def route_summary(edges, roads, alias=()):
    tot = sum(length[j] for j in edges)
    on = sum(length[j] for j in edges if name[j] in roads)
    on2 = sum(length[j] for j in edges if name[j] in roads or name[j] in alias)
    seq = []
    for j in edges:
        if not seq or seq[-1] != (name[j] or "(unnamed)"):
            seq.append(name[j] or "(unnamed)")
    return {"length_m": round(tot), "share_on_documented": round(on / tot, 3) if tot else None,
            "share_incl_osm_alias": round(on2 / tot, 3) if tot else None, "road_sequence": seq}


def check_witness(inst, acc_set, o, dn, t, legs):
    """research/kcf-theorem checker on the route's own edges and nodes."""
    used = {x for k, x, a, b in legs if k == "EDGE"}
    waited = {x for k, x, a, b in legs if k == "WAIT"}
    chk = {"H": inst.H, "n_nodes": inst.n_nodes, "edges": [[a, b, d] for a, b, d in zip(inst.tail, inst.head, inst.D)],
           "waitable": [v for v in range(inst.n_nodes) if inst.waitable[v]], "forbidden": [list(p) for p in inst.forbidden],
           "B": {j: [list(p) for p in inst.B[j]] for j in used}, "W": {v: [list(p) for p in inst.W[v]] for v in waited},
           "A": {j: [list(p) for p in acc_set] for j in rd.inc_by_node.get(dn, [])}, "IB": {o: [list(p) for p in engine.origin_closure(rd, CL, o, inst.H, open_s=OP)]}, "AN": {}}
    return checker.check_route(chk, o, t, [list(l) for l in legs])


mv = {m["movement"]: m for m in read_csv(CAMP / "data/movements_tn2252.csv")}
cases = [("a", "12:00", ["Pearson Road", "Clark Road"], ()), ("b", "13:34", ["Skyway"], ("New Skyway",)), ("b", "13:58", ["Skyway"], ("New Skyway",))]
t41 = {"horizon_s": Hs, "dwell_s": DWELL, "cases": []}
nchk = {"witnesses": 0, "invalid": 0}
for m, t, roads, alias in cases:
    M = mv[m]
    o, _ = nearest_node(float(M["origin_lat"]), float(M["origin_lon"]))
    dn, _ = nearest_node(float(M["dest_lat"]), float(M["dest_lon"]))
    T = minutes("11-08", t)
    case = {"movement": m, "issue": t, "documented_roads": roads, "variants": {}}
    for v in VARIANTS:
        for rule in RULES:
            CL, OP = windows_at(T, v, rule)
            inst = engine.build_instance(rd, CL, Hs, OP)
            acc = engine.accept(rd, CL, dn, Hs, DWELL, open_s=OP)
            ib = engine.origin_closure(rd, CL, o, Hs, open_s=OP)
            args = {"H": inst.H, "n_nodes": inst.n_nodes, "tail": inst.tail, "head": inst.head, "D": inst.D, "waitable": inst.waitable,
                    "forbidden": inst.forbidden, "B": inst.B, "W": inst.W}
            engine._init(args, rd.inc_by_node)
            _, out, _ = engine._shelter_job((dn, acc, [(o, ib)]))
            r = out[o]
            S = [tuple(p) for p in r["set"]]
            row = {"closed_cells": len(CL), "reopening_cells_within_H": sum(1 for c, s in OP.items() if s <= Hs and s > CL[c]),
                   "burned_over_at_issue": sum(1 for c, s in OP.items() if s <= CL[c] or s <= 0),
                   "origin_window_s": ib, "issue_set_s": S, "feasible_at_issue": bool(S) and S[0][0] == 0,
                   "earliest_feasible_departure_s": S[0][0] if S else None, "latest_departure_s": S[-1][1] if S else None}
            for lab, w in (("route_at_issue", r["w_first"]), ("route_at_latest", r["w_last"])):
                if w:
                    edges = [leg[1] for leg in w["legs"] if leg[0] == "EDGE"]
                    row[lab] = route_summary(edges, roads, alias); row[lab]["arrival_s"] = w["arrival"]
                    dep = 0 if lab == "route_at_issue" else S[-1][1]
                    ok, why = check_witness(inst, acc, o, dn, dep, w["legs"])
                    nchk["witnesses"] += 1; nchk["invalid"] += not ok
                    row[lab]["checker"] = "valid" if ok else why
            if S and S[0][0] > 0:
                from wfg_roadlayer.vendor.deadline_field import core
                engine._W["inst"].A = [[] for _ in rd.tail]
                for j in rd.inc_by_node.get(dn, []):
                    engine._W["inst"].A[j] = list(acc)
                engine._W["inst"].IB = {o: ib}; engine._W["inst"].AN = {}
                fld = core.backward(engine._W["inst"])
                w = core.witness(fld, o, S[0][0])
                if w:
                    edges = [leg[1] for leg in w[1] if leg[0] == "EDGE"]
                    row["route_at_earliest"] = route_summary(edges, roads, alias); row["route_at_earliest"]["arrival_s"] = w[0]
                    ok, why = check_witness(inst, acc, o, dn, S[0][0], [list(l) for l in w[1]])
                    nchk["witnesses"] += 1; nchk["invalid"] += not ok
                    row["route_at_earliest"]["checker"] = "valid" if ok else why
            share = row.get("route_at_issue", {}).get("share_on_documented")
            row["pass"] = bool(row["feasible_at_issue"] and share is not None and share >= 0.80)
            case["variants"]["%s_%s" % (v, rule)] = row
    t41["cases"].append(case)
    print(m, t, {k: (x["feasible_at_issue"], x.get("route_at_issue", {}).get("share_on_documented"), x["earliest_feasible_departure_s"])
                 for k, x in case["variants"].items() if k.split("_")[-1] in ("perm", "w240", "res240") and k.startswith(("M0", "MR_"))}, flush=True)
t41["witness_checks"] = nchk
(OUT / "camp_test41_movements.json").write_text(json.dumps(t41, indent=1, default=str))
print(json.dumps({"t43_blocked": {k: (x["hits"], x["reopened_too_early"]) for k, x in res["t43_blocked"].items()},
                  "t42_passable": {k: (x["closed"], x["burned_over"], x["n"]) for k, x in res["t42_passable"].items()},
                  "t42_vehicle": {k: (x["closed"], x["burned_over"], x["n"]) for k, x in res["t42_vehicle"].items()},
                  "bo": {k: (x["closed_or_unsafe"]["t-30"], x["lost_burnovers"]) for k, x in bo.items()}, "witness_checks": nchk}, indent=0))
