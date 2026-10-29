#!/usr/bin/env python3
"""FFI independent trajectory checker (wfg.ffi.independent-checker/1).

Written from the declared WildfireGuardian forecast->routing contract. Imports no routing,
bridge or checker module; numpy + standard library only; deterministic.

Inputs: road graph JSON, hazard packet directory (REPORT.json + constructed_arrays.npz; HAZARD.json is
hashed only, never read for flux/flame), routing request JSON, worker RESULT JSON.

Components (see README.md):
 1 path/mission grammar          2 centre-model exposure (router cell semantics, exact events, own solid angle)
 3 whole-road exact contact      4 whole-road radiation diagnostic (dense sampling, NON-certifying)
 5 independent exact relaxation (time-expanded reachability, contact+peak in all members, dose relaxed)
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path
import numpy as np

VERSION = "wfg.ffi.independent-checker/1"
DT = 1                      # contract: 1 s decision lattice
SOURCE_LAW = "wfg.hazard.construction/1"
MARGIN_REL = 1e-8           # bridge margin: 1e-8*max(1 W/m2, interval map max) per cell (conservative side only)
SAMPLE_M, SAMPLE_S = 5.0, 1.0


class CheckerInputError(ValueError):
    pass


def _fr(x):
    if isinstance(x, bool) or x is None:
        raise CheckerInputError("non-numeric value")
    if isinstance(x, F):
        return x
    if isinstance(x, float) and not math.isfinite(x):
        raise CheckerInputError("non-finite value")
    return F(x)


def _ceil(x: F) -> int:
    return -((-x.numerator) // x.denominator)


def _floor(x: F) -> int:
    return x.numerator // x.denominator


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _utc(text):
    t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise CheckerInputError("naive timestamp")
    return t.astimezone(timezone.utc)


def round_up_sum(a: float, b: float) -> float:
    """Smallest binary64 >= exact a+b (router extinction breakpoint)."""
    s = a + b
    if F(s) < F(a) + F(b):
        s = float(np.nextafter(s, np.inf))
    return s


def rect_integral(x1, x2, y1, y2, h):
    """int int h/(x^2+y^2+h^2)^1.5 dx dy over [x1,x2]x[y1,y2], receiver at origin (closed form)."""
    def G(x, y):
        return np.arctan(x * y / (h * np.sqrt(x * x + y * y + h * h)))
    return G(x2, y2) - G(x1, y2) - G(x2, y1) + G(x1, y1)


# ----------------------------------------------------------------------------- graph
class Graph:
    def __init__(self, g):
        self.raw = g
        gr = g["grid"]
        self.x0, self.y0, self.res = _fr(gr["x0"]), _fr(gr["y0"]), _fr(gr["resolution"])
        self.W, self.H = int(gr["width"]), int(gr["height"])
        self.crs = g.get("crs")
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.node_list = [n["id"] for n in g["nodes"]]
        self.node_idx = {k: i for i, k in enumerate(self.node_list)}
        self.edges = {e["id"]: e for e in g["edges"]}
        self.edge_list = [e["id"] for e in g["edges"]]
        self.edge_idx = {k: i for i, k in enumerate(self.edge_list)}
        self.forbidden = set(tuple(p) for p in g.get("forbidden_turns", []))
        self.mid_edge_reversal = bool(g.get("mid_edge_reversal", False))
        self._npos = {k: (_fr(n["x"]), _fr(n["y"])) for k, n in self.nodes.items()}

    def pos(self, nid):
        return self._npos[nid]

    def cell(self, x: F, y: F) -> int:
        c = _floor((x - self.x0) / self.res); r = _floor((y - self.y0) / self.res)
        if not (0 <= c < self.W and 0 <= r < self.H):
            raise CheckerInputError("coordinate outside grid")
        return r * self.W + c

    def centre(self, rc):
        r, c = divmod(rc, self.W)
        return float(self.x0 + (c + F(1, 2)) * self.res), float(self.y0 + (r + F(1, 2)) * self.res)

    def chord(self, eid, f=F(0), q=F(1)):
        """Router geometry: exact grid-line cuts in [f,q]; open pieces (midpoint cell) + cut points."""
        e = self.edges[eid]; (ux, uy), (vx, vy) = self.pos(e["u"]), self.pos(e["v"])
        cuts = {f, q}
        for a, b, base, ext in ((ux, vx, self.x0, self.W), (uy, vy, self.y0, self.H)):
            if a == b:
                continue
            lo, hi = min(a, b), max(a, b)
            kmin = max(1, _floor((lo - base) / self.res)); kmax = min(ext - 1, _ceil((hi - base) / self.res))
            for k in range(kmin, kmax + 1):
                z = (base + k * self.res - a) / (b - a)
                if f < z < q:
                    cuts.add(z)
        cuts = sorted(cuts)
        pt = lambda z: (ux + z * (vx - ux), uy + z * (vy - uy))
        pieces = [(self.cell(*pt((a + b) / 2)), a, b) for a, b in zip(cuts, cuts[1:])]
        points = [(self.cell(*pt(z)), z) for z in cuts]
        return pieces, points, pt


# ----------------------------------------------------------------------------- packet
class Packet:
    def __init__(self, d, graph: Graph):
        d = Path(d); self.dir = d
        rep = json.loads((d / "REPORT.json").read_text())
        with np.load(d / "constructed_arrays.npz", allow_pickle=False) as z:
            ev = np.array(z["ignition_time_s"], dtype=float); cur = np.array(z["current_active"]); sup = np.array(z["support"])
        md = rep["native_metadata"]; a = md["construction"]["assumptions"]
        if a.get("version") != SOURCE_LAW:
            raise CheckerInputError("source law version %r unsupported" % a.get("version"))
        if cur.dtype != np.bool_ or ev.ndim != 3 or cur.shape != ev.shape[1:]:
            raise CheckerInputError("npz event/current shapes")
        if sup.dtype != np.bool_ or not sup.all():
            raise CheckerInputError("source support not complete (contract requires all true)")
        if np.any(np.isnan(ev)) or np.any(ev < 0) or np.isfinite(ev[:, cur]).any():
            raise CheckerInputError("invalid or overlapping events")
        self.ids = list(rep["rows"][0]["request"]["incurred"])
        S, Hn, Wn = ev.shape
        if len(self.ids) != S or len(set(self.ids)) != S:
            raise CheckerInputError("member ids")
        if (Hn, Wn) != (graph.H, graph.W):
            raise CheckerInputError("grid shape mismatch")
        aff = [_fr(v) for v in md["affine_transform"]]
        want = [graph.res, F(0), graph.x0, F(0), -graph.res, graph.y0 + graph.H * graph.res]
        if aff != want:
            raise CheckerInputError("native affine does not coincide with graph grid")
        if md.get("crs") is not None and graph.crs is not None and md.get("crs") != graph.crs:
            raise CheckerInputError("packet CRS differs from graph CRS")
        cutoff = _utc(md["construction"]["parent_forecast"]["cutoff_utc"]); origin = _utc(md["time_origin"])
        if cutoff != origin:
            raise CheckerInputError("CLOCK_OFFSET_UNSUPPORTED: time_origin != cutoff")
        self.origin_utc = origin
        self.T = _fr(a["burning_duration_s"]); self.R = _fr(a["initial_remaining_s"]); self.horizon = _fr(a["horizon_s"])
        if not (0 <= self.R <= self.T) or self.T <= 0:
            raise CheckerInputError("phase parameters")
        hrr = float(a["fuel_load_kg_m2"]) * float(a["consumed_fraction"]) * float(a["heat_of_combustion_j_kg"]) / float(a["burning_duration_s"])
        self.qrad = hrr * float(a["radiative_fraction"]) * float(a["atmospheric_transmissivity"])   # W/m2 radiant emission density
        self.h = float(a["emission_height_m"]) - float(a["receiver_height_m"])
        if self.h <= 0:
            raise CheckerInputError("height separation")
        self.Tf = float(a["burning_duration_s"]); self.Rf = float(a["initial_remaining_s"])
        self.H, self.W = Hn, Wn; self.graph = graph
        # phases per member, keyed by ROUTER cell index; exact Fractions and router extinction (rounded up)
        self.phases = []
        cur_cells = [int(i) for i in np.flatnonzero(cur.ravel())]
        for s in range(S):
            ph = {}
            for i in cur_cells:
                if self.R > 0:
                    ph[self.native_to_router(i)] = (F(0), self.R, F(self.Rf), "CURRENT")
            for i in np.flatnonzero(np.isfinite(ev[s].ravel())):
                t = float(ev[s].ravel()[i])
                if F(t) >= self.horizon:
                    raise CheckerInputError("ignition outside horizon")
                ph[self.native_to_router(int(i))] = (F(t), F(t) + self.T, F(round_up_sum(t, self.Tf)), "FUTURE")
            self.phases.append(ph)
        self.sources = sorted(set(k for ph in self.phases for k in ph))   # router cells that ever burn
        self.src_index = {c: j for j, c in enumerate(self.sources)}
        rect = []
        for c in self.sources:
            r, col = divmod(c, self.W)
            x1 = float(graph.x0 + col * graph.res); y1 = float(graph.y0 + r * graph.res)
            rect.append((x1, x1 + float(graph.res), y1, y1 + float(graph.res)))
        self.rect = np.array(rect).reshape(-1, 4)
        self.rect_fr = [(graph.x0 + (c % self.W) * graph.res, graph.x0 + (c % self.W + 1) * graph.res,
                         graph.y0 + (c // self.W) * graph.res, graph.y0 + (c // self.W + 1) * graph.res) for c in self.sources]
        # per-member activity arrays over sources (exact and float)
        self.birth = []; self.expiry = []; self.expiry_r = []
        for ph in self.phases:
            b = [ph[c][0] if c in ph else None for c in self.sources]
            e = [ph[c][1] if c in ph else None for c in self.sources]
            er = [ph[c][2] if c in ph else None for c in self.sources]
            self.birth.append(b); self.expiry.append(e); self.expiry_r.append(er)
        self._krow = {}

    def native_to_router(self, i):
        r, c = divmod(i, self.W)
        return (self.H - 1 - r) * self.W + c

    def coeff_points(self, xy):
        """[N,2] receiver points -> [N,M] kW/m2 per unit activity of each source cell."""
        xy = np.asarray(xy, dtype=float).reshape(-1, 2)
        if not len(self.sources):
            return np.zeros((len(xy), 0))
        X = xy[:, :1]; Y = xy[:, 1:2]
        r = self.rect
        val = rect_integral(r[None, :, 0] - X, r[None, :, 1] - X, r[None, :, 2] - Y, r[None, :, 3] - Y, self.h)
        return self.qrad / (4 * math.pi) * val / 1000.0

    def krow(self, rc):
        if rc not in self._krow:
            self._krow[rc] = self.coeff_points([self.graph.centre(rc)])[0]
        return self._krow[rc]

    def active_set(self, s, t: F, conservative=False):
        ex = self.expiry_r[s] if conservative else self.expiry[s]
        return [j for j, (b, e) in enumerate(zip(self.birth[s], ex)) if b is not None and b <= t < e]

    def events(self, s, lo: F, hi: F, conservative=False):
        ex = self.expiry_r[s] if conservative else self.expiry[s]
        out = set()
        for b, e in zip(self.birth[s], ex):
            if b is None:
                continue
            for t in (b, e):
                if lo < t <= hi:
                    out.add(t)
        return sorted(out)


# ----------------------------------------------------------------------------- 1 grammar
def grammar(graph: Graph, request, legs, destination, horizon_hazard: F):
    """Return dict(ok, errors, segments, arrival, finish, dest). Segments carry exact geometry for 2-4."""
    errs = []
    out = {"ok": False, "errors": errs, "segments": [], "arrival": None, "finish": None}
    try:
        dep = _fr(request["departure"]); hor = _fr(request["horizon"])
        if dep < 0 or hor > horizon_hazard or hor < dep:
            errs.append("REQUEST_TIME_OUTSIDE_VALIDITY")
        if dep.denominator != 1 or hor.denominator != 1:
            errs.append("REQUEST_TIME_OFF_LATTICE")
        pos = dict(request["position"]); incoming = request.get("incoming_edge")
        segs = out["segments"]
        if set(pos) == {"node"}:
            if pos["node"] not in graph.nodes:
                raise CheckerInputError("unknown position node")
            if incoming is not None and (incoming not in graph.edges or graph.edges[incoming]["v"] != pos["node"]):
                errs.append("INCOMING_EDGE_CONTEXT")
            p = graph.pos(pos["node"])
            segs.append({"kind": "ISSUE", "start": dep, "end": dep, "p0": p, "p1": p, "pieces": [], "points": [(graph.cell(*p), dep)]})
            at_node, cur_edge, frac, admission = pos["node"], None, None, True
        elif set(pos) == {"edge", "fraction"}:
            e = graph.edges[pos["edge"]]; frac = _fr(pos["fraction"])
            if not (0 < frac <= 1) or incoming != pos["edge"]:
                errs.append("POSITION_EDGE_CONTEXT")
            _, _, pt = graph.chord(pos["edge"])
            p = pt(frac)
            segs.append({"kind": "ISSUE", "start": dep, "end": dep, "p0": p, "p1": p, "pieces": [], "points": [(graph.cell(*p), dep)]})
            if frac == 1:
                at_node, cur_edge, frac, admission = e["v"], None, None, True; incoming = pos["edge"]
            else:
                at_node, cur_edge, admission = None, pos["edge"], False
        else:
            raise CheckerInputError("position grammar")
        now = dep
        if not isinstance(legs, list):
            raise CheckerInputError("legs must be a list")
        for i, leg in enumerate(legs):
            k = leg.get("kind")
            st, en = _fr(leg["start"]), _fr(leg["end"])
            if st != now:
                errs.append("LEG_%d_NONCONTIGUOUS" % i)
            if en <= st:
                errs.append("LEG_%d_NONPOSITIVE" % i)
            if (en - st) / DT != int((en - st) / DT) or st.denominator != 1 or en.denominator != 1:
                errs.append("LEG_%d_OFF_LATTICE" % i)
            if en > hor:
                errs.append("LEG_%d_BEYOND_HORIZON" % i)
            if k == "WAIT":
                if at_node is None or leg.get("node") != at_node:
                    errs.append("LEG_%d_WAIT_NOT_AT_CURRENT_NODE" % i)
                elif graph.nodes[at_node].get("waitable") is not True:
                    errs.append("LEG_%d_WAIT_AT_NON_WAITABLE_NODE" % i)
                n = at_node if at_node is not None else leg.get("node")
                p = graph.pos(n) if n in graph.nodes else (F(0), F(0))
                rc = graph.cell(*p) if n in graph.nodes else None
                segs.append({"kind": "WAIT", "leg_index": i, "node": n, "start": st, "end": en, "p0": p, "p1": p,
                             "pieces": [(rc, st, en)] if rc is not None else [], "points": []})
                admission = False
                if en - st != DT:
                    out.setdefault("notes", []).append("LEG_%d_WAIT_SPANS_%s_s (router emits 1 s waits; accepted as consecutive 1 s waits)" % (i, en - st))
            elif k == "EDGE":
                eid = leg.get("edge")
                if eid not in graph.edges:
                    errs.append("LEG_%d_UNKNOWN_EDGE" % i); raise CheckerInputError("unknown edge")
                e = graph.edges[eid]; f = _fr(leg.get("from_fraction", 0)); q = _fr(leg.get("to_fraction", 1))
                if q != 1 or not (0 <= f < 1):
                    errs.append("LEG_%d_FRACTIONS" % i)
                if cur_edge is not None:            # partial start
                    rev = (graph.mid_edge_reversal and graph.edges[cur_edge].get("reverse_edge") == eid
                           and e.get("reverse_edge") == cur_edge and f == 1 - frac and (cur_edge, eid) not in graph.forbidden)
                    if i != 0 or not ((eid == cur_edge and f == frac) or rev):
                        errs.append("LEG_%d_PARTIAL_POSITION_MISMATCH" % i)
                else:
                    if e["u"] != at_node or f != 0:
                        errs.append("LEG_%d_EDGE_DISCONTINUITY" % i)
                    if incoming is not None and (incoming, eid) in graph.forbidden:
                        errs.append("LEG_%d_FORBIDDEN_TURN(%s->%s)" % (i, incoming, eid))
                ticks = _ceil(e["travel_ticks"] * (1 - f))
                if en - st != ticks * DT:
                    errs.append("LEG_%d_DURATION(%s!=%d)" % (i, en - st, ticks * DT))
                pieces_z, points_z, pt = graph.chord(eid, f, F(1))
                when = lambda z, st=st, en=en, f=f: st + (en - st) * (z - f) / (1 - f)
                segs.append({"kind": "EDGE", "leg_index": i, "edge": eid, "start": st, "end": en, "f": f, "p0": pt(f), "p1": pt(F(1)),
                             "pieces": [(c, when(a), when(b)) for c, a, b in pieces_z], "points": [(c, when(z)) for c, z in points_z],
                             "pieces_z": pieces_z, "points_z": points_z})
                at_node, cur_edge, incoming, admission = e["v"], None, eid, True
            else:
                errs.append("LEG_%d_KIND" % i); raise CheckerInputError("leg kind")
            now = en
        out["arrival"] = now
        dests = [d for d in request["destinations"] if d["node"] == destination]
        if at_node != destination:
            errs.append("ROUTE_DOES_NOT_END_AT_DESTINATION")
        if not admission:
            errs.append("DESTINATION_NOT_ADMITTED_BY_EDGE_ARRIVAL")
        if len(dests) != 1:
            errs.append("DESTINATION_NOT_UNIQUE_IN_REQUEST")
        if dests:
            d = dests[0]; dw = _fr(d["dwell"])
            if dw < 0 or dw.denominator != 1:
                errs.append("DWELL_GRAMMAR")
            fin = now + dw; out["finish"] = fin; out["dwell"] = dw
            if fin > hor:
                errs.append("DWELL_BEYOND_HORIZON")
            if not any(_fr(a) <= now and fin <= _fr(b) for a, b in d["open_intervals"]):
                errs.append("DESTINATION_WINDOW")
            if destination in graph.nodes:
                p = graph.pos(destination); rc = graph.cell(*p)
                segs.append({"kind": "DWELL", "node": destination, "start": now, "end": fin, "p0": p, "p1": p,
                             "pieces": [(rc, now, fin)] if fin > now else [], "points": [(rc, now)] if fin == now else []})
        out["ok"] = not errs
    except (CheckerInputError, KeyError, TypeError, ValueError, ZeroDivisionError) as ex:
        errs.append("STRUCTURE:" + type(ex).__name__ + ":" + str(ex)[:120])
        out["ok"] = False
    return out


# ----------------------------------------------------------------------------- 2 centre model
def _occ_eval(pk: Packet, s, rc, lo: F, hi: F, conservative=False):
    """Contact, peak (kW) and dose (exact Fraction, kJ) on a closed occupancy [lo,hi] of router cell rc."""
    ph = pk.phases[s].get(rc)
    contact = False
    if ph is not None:
        b, e = ph[0], (ph[2] if conservative else ph[1])
        contact = b <= hi and e > lo
    k = pk.krow(rc)
    ts = [lo] + pk.events(s, lo, hi, conservative)
    peak = 0.0
    for t in ts:
        act = pk.active_set(s, t, conservative)
        if act:
            peak = max(peak, math.fsum(float(k[j]) for j in act))
    dose = F(0)
    if hi > lo:
        ex = pk.expiry_r[s] if conservative else pk.expiry[s]
        for j, (b, e) in enumerate(zip(pk.birth[s], ex)):
            if b is None:
                continue
            ov = min(hi, e) - max(lo, b)
            if ov > 0:
                dose += F(float(k[j])) * ov
    return contact, peak, dose


def centre_model(pk: Packet, request, gram, conservative=False):
    """Router-semantics exposure per member from npz events; dose starts at request.incurred."""
    inc_dwell = request.get("exposure_scope") == "including_dwell"
    peak_budget = _fr(request["budgets"]["peak"])
    margin_kw = MARGIN_REL * max(1.0, pk.qrad / 2) / 1000.0 if conservative else 0.0
    res = {}
    for s, mid in enumerate(pk.ids):
        inc = _fr(request["incurred"][mid]); budget = _fr(request["budgets"]["dose"][mid])
        dose = F(0); peak = 0.0; contacts = []; duration = F(0)
        issue_contact = False; issue_peak = 0.0
        for seg in gram["segments"]:
            occs = [(c, a, b, True) for c, a, b in seg["pieces"]] + [(c, t, t, False) for c, t in seg["points"]]
            for c, a, b, pos in occs:
                ct, pk_, ds = _occ_eval(pk, s, c, a, b, conservative)
                if ct:
                    contacts.append({"segment": seg["kind"], "leg_index": seg.get("leg_index"), "router_cell": c, "occupancy": [str(a), str(b)],
                                     "phase": [str(pk.phases[s][c][0]), str(pk.phases[s][c][2] if conservative else pk.phases[s][c][1])]})
                if pk_ > 0:
                    pk_ += margin_kw
                peak = max(peak, pk_)
                if seg["kind"] == "ISSUE":
                    issue_contact |= ct; issue_peak = max(issue_peak, pk_)
                if pos and (seg["kind"] != "DWELL" or inc_dwell) and seg["kind"] != "ISSUE":
                    dose += ds; duration += b - a
        if conservative:
            dose += F(margin_kw) * duration
        total = inc + dose
        res[mid] = {"incurred": float(inc), "route_dose_kj_m2": float(dose), "dose_total_kj_m2": float(total), "dose_total_exact": str(total),
                    "peak_kw_m2": peak, "flame_contact": bool(contacts), "contacts": contacts[:5],
                    "dose_budget": float(budget), "dose_violation": total > budget, "peak_violation": F(peak) > peak_budget,
                    "issue_failure": issue_contact or F(issue_peak) > peak_budget or inc > budget, "charged_duration_s": float(duration)}
    feasible = all(not v["flame_contact"] and not v["dose_violation"] and not v["peak_violation"] for v in res.values())
    return {"feasible": feasible, "per_member": res,
            "semantics": "router cell model: open-piece midpoint cells + cut points, closed occupancy vs half-open phase; "
                         + ("router-conservative (rounded-up extinction, +margin)" if conservative else "exact phases [s,s+T), [0,R), no margin")}


def compare_router(pk: Packet, mine, router_pm, request):
    if not router_pm:
        return {"status": "NOT_AVAILABLE"}
    rate = MARGIN_REL * max(1.0, pk.qrad / 2) / 1000.0 * (1 + 1e-6)
    rows = {}; ok = True
    for mid, m in mine["per_member"].items():
        r = router_pm.get(mid)
        if r is None:
            rows[mid] = {"status": "MISSING"}; ok = False; continue
        rd = _fr(r["dose_exact"]) if isinstance(r.get("dose_exact"), str) else _fr(r["dose"])
        md = F(m["dose_total_exact"])
        tol = F(rate) * F(m["charged_duration_s"]) + F(1, 10**9)
        dd = rd - md; dp = float(r["peak"]) - m["peak_kw_m2"]
        good = (-F(1, 10**9) <= dd <= tol) and (-1e-9 <= dp <= rate + 1e-9)
        ok &= good
        rows[mid] = {"router_dose": float(rd), "own_dose": float(md), "dose_diff": float(dd), "dose_tol": float(tol),
                     "router_peak": float(r["peak"]), "own_peak": m["peak_kw_m2"], "peak_diff": dp, "agree": good}
    return {"status": "AGREE" if ok else "DISAGREE", "per_member": rows,
            "tolerance": "0 <= router-own <= margin_rate*charged_duration + 1e-9 (dose); 0 <= router-own <= margin_rate (+1e-9) (peak); margin_rate=1e-8*max(1,qrad/2)/1000 kW/m2"}


# ----------------------------------------------------------------------------- 3 whole-road contact
def _clip(p0, p1, rect):
    lo, hi = F(0), F(1)
    for x, y, l, r in ((p0[0], p1[0], rect[0], rect[1]), (p0[1], p1[1], rect[2], rect[3])):
        d = y - x
        if d == 0:
            if x < l or x > r:
                return None
        else:
            a, b = (l - x) / d, (r - x) / d
            lo = max(lo, min(a, b)); hi = min(hi, max(a, b))
            if lo > hi:
                return None
    return lo, hi


def whole_road_contact(pk: Packet, gram):
    wit = {}
    for idx, seg in enumerate(gram["segments"]):
        p0, p1, st, en = seg["p0"], seg["p1"], seg["start"], seg["end"]
        bx = (min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1]))
        for j, rect in enumerate(pk.rect_fr):
            if rect[1] < bx[0] or rect[0] > bx[1] or rect[3] < bx[2] or rect[2] > bx[3]:
                continue
            u = _clip(p0, p1, rect)
            if u is None:
                continue
            enter = st + (en - st) * u[0]; leave = st + (en - st) * u[1]
            c = pk.sources[j]
            for s, mid in enumerate(pk.ids):
                ph = pk.phases[s].get(c)
                if ph is None:
                    continue
                w = max(enter, ph[0])
                if w <= leave and w < ph[1]:
                    cand = {"member": mid, "segment_index": idx, "segment_kind": seg["kind"], "edge": seg.get("edge"), "router_cell": c,
                            "time_exact": str(w), "time": float(w), "occupancy_exact": [str(enter), str(leave)], "phase_exact": [str(ph[0]), str(ph[1])], "phase": ph[3]}
                    if mid not in wit or w < F(wit[mid]["time_exact"]):
                        wit[mid] = cand
    return {"status": "DEFINITE_CONTACT" if wit else "CLEAR", "witnesses": wit,
            "semantics": "closed road segments (incl. issue, waits, dwell) vs closed cell rectangles vs exact half-open phases"}


# ----------------------------------------------------------------------------- 4 radiation diagnostic
def radiation_diagnostic(pk: Packet, request, gram):
    inc_dwell = request.get("exposure_scope") == "including_dwell"   # whole-road checker always uses full mission; report both
    out = {}
    peak_budget = float(request["budgets"]["peak"]); nsamp = 0
    for s, mid in enumerate(pk.ids):
        peak = 0.0; dose_trap = 0.0; dose_hi = 0.0; dose_dwell = 0.0; peak_at = None
        for seg in gram["segments"]:
            st, en = seg["start"], seg["end"]
            if seg["p0"] == seg["p1"]:                       # stationary: exact
                p = (float(seg["p0"][0]), float(seg["p0"][1]))
                k = pk.coeff_points([p])[0]
                for t in [st] + pk.events(s, st, en):
                    act = pk.active_set(s, t)
                    v = math.fsum(float(k[j]) for j in act) if act else 0.0
                    if v > peak:
                        peak, peak_at = v, (seg["kind"], float(t))
                if en > st:
                    d = 0.0
                    for j, (b, e) in enumerate(zip(pk.birth[s], pk.expiry[s])):
                        if b is not None:
                            ov = min(en, e) - max(st, b)
                            if ov > 0:
                                d += float(k[j]) * float(ov)
                    if seg["kind"] == "DWELL":
                        dose_dwell += d
                    dose_trap += d; dose_hi += d
                continue
            cuts = [st] + pk.events(s, st, en) + ([en] if en not in pk.events(s, st, en) else [])
            cuts = sorted(set(cuts))
            x0, y0 = float(seg["p0"][0]), float(seg["p0"][1]); x1, y1 = float(seg["p1"][0]), float(seg["p1"][1])
            L = math.hypot(x1 - x0, y1 - y0); dur = float(en - st)
            for a, b in zip(cuts, cuts[1:]):
                act = pk.active_set(s, a)           # constant on [a,b)
                fa, fb = float((a - st) / (en - st)), float((b - st) / (en - st))
                n = max(1, math.ceil(L * (fb - fa) / SAMPLE_M), math.ceil(dur * (fb - fa) / SAMPLE_S))
                us = np.linspace(fa, fb, n + 1)
                nsamp += n + 1
                if not act:
                    continue
                pts = np.stack([x0 + us * (x1 - x0), y0 + us * (y1 - y0)], axis=1)
                k = pk.coeff_points(pts)[:, act].sum(axis=1)
                dt_ = dur * (fb - fa) / n
                dose_trap += float(np.sum((k[1:] + k[:-1]) / 2) * dt_)
                dose_hi += float(np.sum(np.maximum(k[1:], k[:-1])) * dt_)
                i = int(np.argmax(k))
                if k[i] > peak:
                    peak, peak_at = float(k[i]), (seg["kind"], float(st) + dur * float(us[i]))
        inc = float(request["incurred"][mid]); bud = float(request["budgets"]["dose"][mid])
        out[mid] = {"peak_sampled_kw_m2": peak, "peak_at": peak_at, "dose_trapezoid_total_kj_m2": inc + dose_trap,
                    "dose_maxendpoint_total_kj_m2": inc + dose_hi, "dwell_dose_kj_m2": dose_dwell,
                    "dose_trapezoid_route_only_total_kj_m2": inc + dose_trap - dose_dwell,
                    "peak_exceeds_budget": peak > peak_budget, "dose_trapezoid_exceeds_budget": inc + dose_trap > bud}
    return {"per_member": out, "samples": nsamp, "certifying": False,
            "semantics": "exact source-sheet flux at actual road points; moving legs split at member event times and sampled every <=5 m and <=1 s (trapezoid + max-endpoint estimate); stationary waits/dwell exact; non-certifying"}


def runtime_radiation(whole):
    """Extract runtime whole-road status and per-member radiation bounds from a worker whole_road_check."""
    if not isinstance(whole, dict):
        return None, {}
    status = whole.get("status"); pm = {}
    stack = [whole]
    while stack:
        x = stack.pop()
        if not isinstance(x, dict):
            continue
        rad = x.get("radiation")
        if isinstance(rad, dict) and isinstance(rad.get("per_member"), list):
            for r in rad["per_member"]:
                pm.setdefault(r["id"], r)
        ad = x.get("adaptive_fallback")
        if isinstance(ad, dict) and isinstance(ad.get("per_member"), dict):
            for k, r in ad["per_member"].items():
                pm[k] = r
        for key in ("checked_result", "partial_check"):
            if key in x:
                stack.append(x[key])
    return status, pm


# ----------------------------------------------------------------------------- 5 relaxation
class _GraphIndex:
    def __init__(self, graph: Graph):
        self.g = graph
        E = len(graph.edge_list); self.E = E
        self.u = np.array([graph.node_idx[graph.edges[e]["u"]] for e in graph.edge_list], dtype=np.int64)
        self.v = np.array([graph.node_idx[graph.edges[e]["v"]] for e in graph.edge_list], dtype=np.int64)
        self.tau = np.array([int(graph.edges[e]["travel_ticks"]) for e in graph.edge_list], dtype=np.int64)
        if np.any(self.tau < 1):
            raise CheckerInputError("travel ticks")
        self.waitable = np.array([graph.nodes[n].get("waitable") is True for n in graph.node_list])
        out = [[] for _ in graph.node_list]
        for i, e in enumerate(self.u):
            out[e].append(i)
        self.out = out
        forb = set((graph.edge_idx[a], graph.edge_idx[b]) for a, b in graph.forbidden if a in graph.edge_idx and b in graph.edge_idx)
        src, dst = [], []
        for e in range(E):
            for f in out[self.v[e]]:
                if (e, f) not in forb:
                    src.append(e); dst.append(f)
        src = np.array(src, dtype=np.int64); dst = np.array(dst, dtype=np.int64)
        order = np.argsort(src, kind="stable"); src, dst = src[order], dst[order]
        self.indptr = np.zeros(E + 2, dtype=np.int64)          # state E = virtual start (filled per request)
        np.add.at(self.indptr, src + 1, 1); self.indptr = np.cumsum(self.indptr)
        self.succ = dst
        self.forb = forb
        nx = np.array([float(graph.pos(n)[0]) for n in graph.node_list]); ny = np.array([float(graph.pos(n)[1]) for n in graph.node_list])
        self.ncol = np.floor((nx - float(graph.x0)) / float(graph.res)).astype(int); self.nrow = np.floor((ny - float(graph.y0)) / float(graph.res)).astype(int)
        self.ncell = np.array([graph.cell(*graph.pos(n)) for n in graph.node_list], dtype=np.int64)


_GI_CACHE = {}


def _bad_intervals(pk: Packet, request):
    """Router cell -> list of [a,b) (exact) where SOME member has flame or centre flux > peak budget."""
    peak_budget = float(request["budgets"]["peak"])
    bad = {}
    for s in range(len(pk.ids)):
        for c, ph in pk.phases[s].items():
            bad.setdefault(c, []).append((ph[0], ph[1]))
    # peak: only cells whose time-agnostic upper bound can exceed the budget
    if len(pk.sources):
        allc = np.arange(pk.graph.W * pk.graph.H)
        cen = np.array([pk.graph.centre(int(c)) for c in allc])
        K = pk.coeff_points(cen)                        # [cells, M]
        for s in range(len(pk.ids)):
            mask = np.array([b is not None for b in pk.birth[s]])
            ub = K[:, mask].sum(axis=1) if mask.any() else np.zeros(len(allc))
            for c in np.flatnonzero(ub > peak_budget):
                ev = sorted(set([F(0)] + [t for b, e in zip(pk.birth[s], pk.expiry[s]) if b is not None for t in (b, e)]))
                for a, b in zip(ev, ev[1:] + [pk.horizon + 1]):
                    act = pk.active_set(s, a)
                    if act and math.fsum(float(K[c, j]) for j in act) > peak_budget:
                        bad.setdefault(int(c), []).append((a, b))
        pk._peak_K = None
    return bad


def _ban(intervals, tau: F, za: F, zb: F, tmin: int, tmax: int, row: np.ndarray):
    """Ban integer departures t with [t+tau*za, t+tau*zb] intersecting some [a,b)."""
    for a, b in intervals:
        lo = _ceil(a - tau * zb); hi = _ceil(b - tau * za) - 1
        lo = max(lo, tmin); hi = min(hi, tmax)
        if lo <= hi:
            row[lo:hi + 1] = True


def relaxation(graph, packet, request, *, want_witness=True, ignore_hazard=False):
    """Earliest admissible arrival under contact (all members) + peak, dose relaxed. Exact on the 1 s lattice."""
    t0 = time.perf_counter()
    if not isinstance(graph, Graph):
        graph = Graph(graph)
    pk = packet if isinstance(packet, Packet) else Packet(packet, graph)
    key = id(graph.raw)
    gi = _GI_CACHE.get(key)
    if gi is None:
        gi = _GraphIndex(graph); _GI_CACHE.clear(); _GI_CACHE[key] = gi
    E = gi.E; dep = int(_fr(request["departure"])); Hq = int(_fr(request["horizon"]))
    Tn = Hq + 1
    res = {"lower_bound_arrival": None, "status": None, "witness": None}
    if any(_fr(request["incurred"][m]) > _fr(request["budgets"]["dose"][m]) for m in pk.ids):
        res.update(status="INFEASIBLE_INCURRED_EXCEEDS_BUDGET"); res["runtime_s"] = time.perf_counter() - t0; return res
    bad = {} if ignore_hazard else _bad_intervals(pk, request)
    hot = np.zeros((graph.H, graph.W), bool)
    for c in bad:
        hot[c // graph.W, c % graph.W] = True
    # 2D prefix for bbox test (expanded by 1 cell for corner/point cells)
    P = np.zeros((graph.H + 1, graph.W + 1), int); P[1:, 1:] = np.cumsum(np.cumsum(hot, 0), 1)
    def any_hot(r0, r1, c0, c1):
        r0, c0 = max(r0, 0), max(c0, 0); r1, c1 = min(r1, graph.H - 1), min(c1, graph.W - 1)
        if r0 > r1 or c0 > c1:
            return False
        return P[r1 + 1, c1 + 1] - P[r0, c1 + 1] - P[r1 + 1, c0] + P[r0, c0] > 0
    erow = np.full(E, -1, dtype=np.int64); rows = []
    for e in range(E):
        a, b = gi.u[e], gi.v[e]
        if not any_hot(min(gi.nrow[a], gi.nrow[b]) - 1, max(gi.nrow[a], gi.nrow[b]) + 1, min(gi.ncol[a], gi.ncol[b]) - 1, max(gi.ncol[a], gi.ncol[b]) + 1):
            continue
        eid = graph.edge_list[e]; tau = F(int(gi.tau[e]))
        pieces, points, _ = graph.chord(eid)
        row = np.zeros(Tn, bool); hit = False
        for c, za, zb in pieces + [(c, z, z) for c, z in points]:
            if c in bad:
                _ban(bad[c], tau, za, zb, 0, Tn - 1, row); hit = True
        if hit and row.any():
            erow[e] = len(rows); rows.append(row)
    ban_e = np.array(rows) if rows else np.zeros((1, Tn), bool)
    nN = len(graph.node_list); nrow_ = np.full(nN, -1, dtype=np.int64); wrows = []
    for n in range(nN):
        c = int(gi.ncell[n])
        if gi.waitable[n] and c in bad:
            row = np.zeros(Tn, bool); _ban(bad[c], F(1), F(0), F(1), 0, Tn - 1, row)
            if row.any():
                nrow_[n] = len(wrows); wrows.append(row)
    ban_w = np.array(wrows) if wrows else np.zeros((1, Tn), bool)
    # destinations: per node, allowed admission times
    dest_ok = {}
    for d in request["destinations"]:
        n = graph.node_idx[d["node"]]; dw = int(_fr(d["dwell"])); ok = np.zeros(Tn, bool)
        for a, b in d["open_intervals"]:
            lo = _ceil(_fr(a)); hi = min(_floor(_fr(b) - dw), Hq - dw)
            if lo <= hi:
                ok[max(lo, 0):hi + 1] = True
        c = int(gi.ncell[n])
        if c in bad:
            row = np.zeros(Tn, bool); _ban(bad[c], F(dw), F(0), F(1), 0, Tn - 1, row); ok &= ~row
        dest_ok[n] = dest_ok.get(n, np.zeros(Tn, bool)) | ok
    # start state
    pos = request["position"]; inc = request.get("incoming_edge")
    S = E + 1; VIRT = E
    arr = np.zeros((Tn, S), bool)
    parent = np.full((Tn, S), -1, dtype=np.int32) if want_witness else np.full((Tn, 1), -1, dtype=np.int32)
    here = np.zeros(S, bool)
    state_node = np.concatenate([gi.v, [0]])
    issue_bad = False
    if set(pos) == {"node"}:
        on = graph.node_idx[pos["node"]]; c = int(gi.ncell[on])
        issue_bad = c in bad and any(a <= dep < b for a, b in bad[c])
        if inc is not None:
            st = graph.edge_idx[inc]; here[st] = True; start_state = st
        else:
            state_node[VIRT] = on; here[VIRT] = True; start_state = VIRT
            fs = np.array(gi.out[on], dtype=np.int64)
            indptr = gi.indptr.copy(); indptr[E + 1] = indptr[E] + len(fs); succ = np.concatenate([gi.succ, fs])
        if inc is not None:
            indptr = gi.indptr.copy(); indptr[E + 1] = indptr[E]; succ = gi.succ
        zero_leg = (not issue_bad) and on in dest_ok and dest_ok[on][dep]
    else:
        # partial edge start: the forced first leg is evaluated exactly (contact/peak, all members)
        eid = pos["edge"]; f = _fr(pos["fraction"]); e = graph.edge_idx[eid]
        indptr = gi.indptr.copy(); indptr[E + 1] = indptr[E]; succ = gi.succ; start_state = None; zero_leg = False
        pt = graph.chord(eid)[2](f); c = graph.cell(*pt)
        issue_bad = c in bad and any(a <= dep < b for a, b in bad[c])
        if f == 1:
            here[e] = True; start_state = e; zero_leg = (not issue_bad) and gi.v[e] in dest_ok and dest_ok[gi.v[e]][dep]
        else:
            end = dep + _ceil(gi.tau[e] * (1 - f)); pieces, points, _ = graph.chord(eid, f, F(1))
            when = lambda z: F(dep) + (end - dep) * (z - f) / (1 - f)
            okfirst = end <= Hq and not any(c2 in bad and any(a <= when(zb) and b > when(za) for a, b in bad[c2]) for c2, za, zb in pieces + [(c2, z, z) for c2, z in points])
            if okfirst and not issue_bad:
                arr[end, e] = True
                if want_witness:
                    parent[end, e] = -2
    if issue_bad:
        res.update(status="INFEASIBLE_AT_ISSUE"); res["runtime_s"] = time.perf_counter() - t0; return res
    succ_tau = gi.tau[succ]; succ_row = erow[succ]
    is_dest_state = np.zeros(S, bool)
    for n in dest_ok:
        is_dest_state[:E] |= gi.v == n
    found = None
    if zero_leg:
        found = (start_state, dep, "ZERO_LEG")
    wait_row_state = nrow_[state_node]; waitable_state = gi.waitable[state_node]
    t = dep
    while found is None and t <= Hq:
        if t > dep:
            wok = waitable_state.copy()
            m = wait_row_state >= 0
            wok[m] &= ~ban_w[wait_row_state[m], t - 1]
            here = arr[t] | (here & wok)
        # destination admission (EDGE arrival at t)
        cand = np.flatnonzero(arr[t] & is_dest_state)
        for st in cand:
            n = int(gi.v[st])
            if n in dest_ok and dest_ok[n][t]:
                found = (int(st), t, "EDGE_ARRIVAL"); break
        if found is not None or t >= Hq:
            break
        act = np.flatnonzero(here)
        if act.size:
            cnt = indptr[act + 1] - indptr[act]
            tot = int(cnt.sum())
            if tot:
                base = np.repeat(indptr[act], cnt); off = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
                k = base + off; par = np.repeat(act, cnt)
                f_ = succ[k]; end = t + succ_tau[k]
                okm = end <= Hq
                r = succ_row[k]; m = okm & (r >= 0)
                okm[m] &= ~ban_e[r[m], t]
                f_, end, par = f_[okm], end[okm], par[okm]
                new = ~arr[end, f_]
                f_, end, par = f_[new], end[new], par[new]
                arr[end, f_] = True
                if want_witness:
                    parent[end, f_] = par
        t += 1
    res["runtime_s"] = time.perf_counter() - t0
    res["banned_edges"] = len(rows); res["banned_wait_nodes"] = len(wrows)
    if found is None:
        res.update(status="NO_ADMISSIBLE_ARRIVAL"); return res
    res.update(status="ADMISSIBLE_ARRIVAL_FOUND", lower_bound_arrival=found[1], destination=graph.node_list[int(state_node[found[0]])])
    if want_witness:
        legs = []; s, tt = found[0], found[1]
        if found[2] == "EDGE_ARRIVAL":
            mode = "arr"
        else:
            mode = "here"
        guard = 0
        while True:
            guard += 1
            if guard > 10**6:
                raise RuntimeError("witness reconstruction loop")
            if mode == "arr" or (s != VIRT and arr[tt, s] and not (s == start_state and tt == dep)):
                p = int(parent[tt, s]); d0 = tt - int(gi.tau[s]) if p != -2 else dep
                leg = {"kind": "EDGE", "edge": graph.edge_list[s], "start": d0, "end": tt, "from_fraction": 0, "to_fraction": 1}
                if p == -2:
                    leg["from_fraction"] = float(_fr(pos["fraction"]))
                legs.append(leg)
                if p == -2:
                    break
                s, tt, mode = p, d0, "here"
                continue
            if tt == dep and s == start_state:
                break
            n = graph.node_list[int(state_node[s])]
            legs.append({"kind": "WAIT", "node": n, "start": tt - 1, "end": tt}); tt -= 1
        legs.reverse()
        res["witness"] = {"legs": legs, "destination": res["destination"], "arrival": found[1]}
    return res


# ----------------------------------------------------------------------------- top level
def check(graph, hazard_packet_dir, request, legs, destination, *, runtime=None, do_relaxation=True):
    """Components 1-5 for one trajectory (legs may be None for refusal cases)."""
    t_start = time.perf_counter()
    G = graph if isinstance(graph, Graph) else Graph(graph)
    pk = hazard_packet_dir if isinstance(hazard_packet_dir, Packet) else Packet(hazard_packet_dir, G)
    out = {"schema": VERSION, "contradictions": [], "notes": []}
    if set(request["incurred"]) != set(pk.ids) or set(request["budgets"]["dose"]) != set(pk.ids):
        raise CheckerInputError("request member ids differ from packet ids")
    if request.get("objective", "earliest_arrival") != "earliest_arrival":
        raise CheckerInputError("objective")
    runtime = runtime or {}
    rstatus = runtime.get("status")
    has_route = legs is not None and destination is not None
    if has_route:
        gram = grammar(G, request, legs, destination, pk.horizon)
        out["grammar"] = {"ok": gram["ok"], "errors": gram["errors"], "notes": gram.get("notes", []), "arrival": None if gram["arrival"] is None else float(gram["arrival"]),
                          "mission_end": None if gram["finish"] is None else float(gram["finish"]), "legs": len(legs)}
        if runtime.get("arrival") is not None and gram["arrival"] is not None and _fr(runtime["arrival"]) != gram["arrival"]:
            out["contradictions"].append("RUNTIME_ARRIVAL_FIELD_DIFFERS_FROM_LEGS")
        if gram["segments"] and not any(e.startswith("STRUCTURE") for e in gram["errors"]):
            cm = centre_model(pk, request, gram)
            cmc = centre_model(pk, request, gram, conservative=True)
            out["centre_model"] = cm
            out["centre_model_router_conservative"] = {"feasible": cmc["feasible"], "per_member": {k: {kk: v[kk] for kk in ("dose_total_kj_m2", "peak_kw_m2", "flame_contact", "dose_violation", "peak_violation")} for k, v in cmc["per_member"].items()}}
            out["router_metric_agreement"] = compare_router(pk, cm, runtime.get("per_member"), request)
            out["whole_road_contact"] = whole_road_contact(pk, gram)
            out["radiation_diagnostic"] = radiation_diagnostic(pk, request, gram)
            wstat, wpm = runtime_radiation(runtime.get("whole_road_check"))
            out["runtime_whole_road_status"] = wstat
            rd = out["radiation_diagnostic"]
            if wpm:
                cons = {}
                for mid, v in rd["per_member"].items():
                    r = wpm.get(mid)
                    if r:
                        lo, hi = r.get("dose_lower_kj_m2"), r.get("dose_upper_kj_m2")
                        d = v["dose_trapezoid_total_kj_m2"]
                        cons[mid] = {"runtime_dose_bounds": [lo, hi], "sampled": d,
                                     "within_bounds_rel1e-3": (lo is None or d >= lo - 1e-3 * max(1, abs(lo))) and (hi is None or d <= hi + 1e-3 * max(1, abs(hi))),
                                     "runtime_peak_upper": r.get("peak_upper_kw_m2"), "sampled_peak_le_runtime_upper": r.get("peak_upper_kw_m2") is None or v["peak_sampled_kw_m2"] <= r["peak_upper_kw_m2"] * (1 + 1e-9) + 1e-12}
                rd["runtime_bounds_consistency"] = cons
                for mid, cv in cons.items():
                    if wstat == "CERTIFIED_ADMISSIBLE" and not cv["sampled_peak_le_runtime_upper"]:
                        out["contradictions"].append("SAMPLED_PEAK_ABOVE_RUNTIME_CERTIFIED_UPPER_BOUND:" + mid)
                    if not cv["within_bounds_rel1e-3"]:
                        out["notes"].append("SAMPLED_DOSE_OUTSIDE_RUNTIME_BOUNDS(rel 1e-3, approximate):" + mid)
            if wstat == "CERTIFIED_ADMISSIBLE":
                if out["whole_road_contact"]["status"] != "CLEAR":
                    out["contradictions"].append("RUNTIME_CERTIFIED_BUT_WHOLE_ROAD_CONTACT")
                for mid, v in rd["per_member"].items():
                    if v["peak_exceeds_budget"]:
                        out["contradictions"].append("RUNTIME_CERTIFIED_BUT_SAMPLED_PEAK_EXCEEDS_BUDGET:" + mid)
                    if v["dose_trapezoid_exceeds_budget"]:
                        out["contradictions"].append("RUNTIME_CERTIFIED_BUT_SAMPLED_DOSE_EXCEEDS_BUDGET(approximate):" + mid)
            if isinstance(runtime.get("whole_road_check"), dict) and wstat == "DEFINITE_REJECT" and runtime["whole_road_check"].get("reason") == "FLAME_CONTACT_WITNESS" and out["whole_road_contact"]["status"] == "CLEAR":
                out["contradictions"].append("RUNTIME_FLAME_WITNESS_BUT_INDEPENDENT_CONTACT_CLEAR")
            if rstatus in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE", "TIMEOUT") and not (gram["ok"] and cm["feasible"]):
                out["contradictions"].append("RUNTIME_RETURNED_ROUTE_NOT_CENTRE_FEASIBLE" if gram["ok"] else "RUNTIME_RETURNED_ROUTE_GRAMMAR_INVALID")
            if out["router_metric_agreement"]["status"] == "DISAGREE":
                out["contradictions"].append("ROUTER_METRICS_DISAGREE_WITH_INDEPENDENT_CENTRE_MODEL")
        else:
            gram["ok"] = False
            if rstatus in ("CONDITIONAL_OPTIMUM", "CHECKED_ROUTE"):
                out["contradictions"].append("RUNTIME_RETURNED_ROUTE_GRAMMAR_INVALID")
    # 5 relaxation
    if do_relaxation:
        rel = relaxation(G, pk, request)
        out["relaxation"] = {k: v for k, v in rel.items()}
        st_ = relaxation(G, pk, request, want_witness=False, ignore_hazard=True)
        out["relaxation"]["structural_earliest_arrival_no_hazard"] = st_["lower_bound_arrival"]
        out["relaxation"]["hazard_binding"] = st_["lower_bound_arrival"] != rel["lower_bound_arrival"]
        L = rel["lower_bound_arrival"]
        wfeas = None
        if rel.get("witness"):
            wg = grammar(G, request, rel["witness"]["legs"], rel["witness"]["destination"], pk.horizon)
            if not wg["ok"]:
                out["contradictions"].append("INTERNAL_RELAXATION_WITNESS_GRAMMAR_INVALID:" + ";".join(wg["errors"][:3]))
            else:
                we = centre_model(pk, request, wg); wc = centre_model(pk, request, wg, conservative=True)
                if any(v["flame_contact"] or v["peak_violation"] for v in we["per_member"].values()):
                    out["contradictions"].append("INTERNAL_RELAXATION_WITNESS_HAS_CONTACT")
                wfeas = we["feasible"] and wc["feasible"]
                out["relaxation"]["witness_centre_feasible_incl_dose_router_conservative"] = wfeas
                out["relaxation"]["witness_dose_total"] = {k: v["dose_total_kj_m2"] for k, v in wc["per_member"].items()}
        if has_route:
            feasible = out.get("grammar", {}).get("ok") and out.get("centre_model", {}).get("feasible")
            arrival = gram["arrival"]
            if not feasible:
                verdict, why = "NOT_INDEPENDENTLY_CERTIFIED", "route not centre-feasible or grammar invalid"
            elif L is None:
                verdict, why = "NOT_INDEPENDENTLY_CERTIFIED", "relaxation found no admissible arrival although route is feasible (internal inconsistency)"
                out["contradictions"].append("INTERNAL_RELAXATION_MISSED_FEASIBLE_ROUTE")
            elif arrival == L:
                verdict, why = "INDEPENDENTLY_CERTIFIED_OPTIMAL", "centre-feasible route arrival equals relaxation lower bound"
            elif arrival < L:
                verdict, why = "NOT_INDEPENDENTLY_CERTIFIED", "arrival below relaxation bound (internal inconsistency)"
                out["contradictions"].append("INTERNAL_ROUTE_BEATS_RELAXATION_BOUND")
            elif wfeas:
                verdict, why = "NOT_OPTIMAL_COUNTEREXAMPLE", "relaxation witness arriving at %d is centre-feasible incl. dose (router-conservative)" % L
                if rstatus == "CONDITIONAL_OPTIMUM":
                    out["contradictions"].append("RUNTIME_OPTIMUM_CLAIM_CONTRADICTED_BY_EARLIER_FEASIBLE_ROUTE")
            else:
                verdict, why = "NOT_INDEPENDENTLY_CERTIFIED", "arrival %s > relaxation bound %d and relaxation witness violates dose; gap unresolved" % (arrival, L)
        else:
            if L is None:
                verdict = "INDEPENDENTLY_CERTIFIED_REFUSAL" if rstatus == "PROVEN_INFEASIBLE" else "RELAXATION_INFEASIBLE"
                why = "no centre-admissible arrival even with dose relaxed (%s)" % rel["status"]
            elif wfeas:
                verdict, why = "REFUSAL_CONTRADICTED" if rstatus == "PROVEN_INFEASIBLE" else "FEASIBLE_ROUTE_EXISTS", "relaxation witness arriving at %d is centre-feasible incl. dose" % L
                if rstatus == "PROVEN_INFEASIBLE":
                    out["contradictions"].append("RUNTIME_REFUSAL_CONTRADICTED_BY_FEASIBLE_ROUTE")
            else:
                verdict, why = "NOT_INDEPENDENTLY_CERTIFIED", "relaxation admits arrival %d but its witness violates dose; dose-infeasibility not independently decided" % L
        out["optimality_or_refusal"] = {"verdict": verdict, "reason": why, "runtime_status": rstatus}
    # overall
    if out["contradictions"]:
        overall = "CONTRADICTION_FOUND"
    elif not has_route:
        overall = out.get("optimality_or_refusal", {}).get("verdict", "NO_TRAJECTORY")
    elif not out["grammar"]["ok"]:
        overall = "INVALID_TRAJECTORY"
    elif not out["centre_model"]["feasible"]:
        overall = "CENTRE_INFEASIBLE_TRAJECTORY"
    else:
        overall = out.get("optimality_or_refusal", {}).get("verdict", "CENTRE_FEASIBLE")
    out["classification"] = {"overall": overall,
                             "trajectory": None if not has_route else ("VALID" if out["grammar"]["ok"] else "INVALID"),
                             "centre_model": None if not has_route or "centre_model" not in out else ("FEASIBLE" if out["centre_model"]["feasible"] else "INFEASIBLE"),
                             "whole_road_contact": out.get("whole_road_contact", {}).get("status"),
                             "runtime_whole_road_status": out.get("runtime_whole_road_status"),
                             "optimality_or_refusal": out.get("optimality_or_refusal", {}).get("verdict"),
                             "contradictions": list(out["contradictions"])}
    out["runtime_s"] = time.perf_counter() - t_start
    out["scope"] = ("Centre model and relaxation are exact for the declared source law on the 1 s lattice for the supplied members; "
                    "whole-road contact exact; radiation diagnostic non-certifying; all results conditional on the packet's declared policies.")
    return _jsonable(out)


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, F):
        return float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    return x


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for k in ("--graph", "--packet-dir", "--request", "--result", "--out"):
        ap.add_argument(k, required=True)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    graph = json.loads(Path(a.graph).read_text()); request = json.loads(Path(a.request).read_text())
    R = json.loads(Path(a.result).read_text())
    res = R.get("result") if isinstance(R.get("result"), dict) else R
    route, role = None, None
    if res.get("destination") is not None:
        route, role = res, "PRIMARY"
    elif isinstance(res.get("checked_incumbent"), dict) and res["checked_incumbent"].get("destination") is not None:
        route, role = res["checked_incumbent"], "CHECKED_TIMEOUT_INCUMBENT"
    runtime = {"status": res.get("status"), "reason": res.get("reason"), "arrival": None if route is None else route.get("arrival"),
               "per_member": None if route is None else route.get("per_member"), "whole_road_check": R.get("whole_road_check")}
    pdir = Path(a.packet_dir)
    inputs = {"graph": sha256_file(a.graph), "request": sha256_file(a.request), "result": sha256_file(a.result),
              "REPORT.json": sha256_file(pdir / "REPORT.json"), "constructed_arrays.npz": sha256_file(pdir / "constructed_arrays.npz")}
    if (pdir / "HAZARD.json").exists():
        inputs["HAZARD.json(hashed only)"] = sha256_file(pdir / "HAZARD.json")
    try:
        out = check(graph, pdir, request, None if route is None else route.get("legs"), None if route is None else route.get("destination"), runtime=runtime)
    except CheckerInputError as ex:
        out = {"schema": VERSION, "classification": {"overall": "INVALID_INPUT", "reason": str(ex)}}
    out["witness_role"] = role
    out["runtime_status"] = runtime["status"]; out["runtime_reason"] = runtime["reason"]
    out["inputs_sha256"] = inputs
    out["checker_source_sha256"] = sha256_file(__file__)
    out["checker_version"] = VERSION
    out["python"] = sys.version.split()[0]; out["numpy"] = np.__version__
    out["total_runtime_s"] = time.perf_counter() - t0
    Path(a.out).write_text(json.dumps(out, indent=1, allow_nan=False))
    print(json.dumps({"overall": out["classification"]["overall"], "contradictions": out["classification"].get("contradictions"),
                      "optimality_or_refusal": out["classification"].get("optimality_or_refusal"), "runtime_s": round(out["total_runtime_s"], 2)}))


if __name__ == "__main__":
    main()
