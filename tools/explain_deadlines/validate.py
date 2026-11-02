"""Mandatory validation of every explanation, plus an independent cross-check.

Own assertions (exact rational arithmetic, run for every origin before anything is written):
  (a)  binding item: at the deadline D the checked route is clear of flame on the binding segment in every member
       (closed-footprint and router rules) and leaves every contact cell strictly before the flame arrives
       (slack > 0);
  (a') every route the API checked at D for the origin is clear of flame along its whole journey (issue point, legs,
       destination stay) at its recorded times -- re-verifies the identified packet against the recorded result;
  (b)  binding item: at the next offset N the rigidly shifted route meets flame on the binding segment in exactly the
       stated members (closed rule), and no earlier segment meets flame under either rule;
  (c)  every reported event time (deadline and next offset, flame, contact and pass times) lies in the recorded scenario
       window [valid_from, valid_until] of the packet;
  (w)  window claims: next + fastest road time + dwell > close (fire-free claim) re-derived with an independent
       node-based Dijkstra lower bound that ignores turn restrictions; "a fire-free road would fit" claims re-derived
       by a separate turn-restricted search; flame-avoiding claims re-derived by the relaxation (also without turn
       restrictions); the deadline cause must follow from these claims;
  (e)  exits: every exit road is flame-blocked for every start second from the moment it can first be reached until
       the window ends, no road leaving the reached area is cut by time, and no candidate shelter is reached;
       "no route even without fire" re-derived with the node lower bound.
A failed assertion turns the origin into ``not_explainable`` (``validation_failed:<id>``); counts are reported.

Independent cross-check (``kit``): the kit's frozen independent checker (integration/kit/runner/
ffi_independent_checker.py, hash-pinned in CANDIDATE_MANIFEST.json; numpy + standard library, reads
constructed_arrays.npz rather than HAZARD.json) re-checks (a') with its ``whole_road_contact`` and router-conservative
``centre_model``, and (b) with ``whole_road_contact`` on the shifted route truncated after the binding leg.
"""
from __future__ import annotations

import hashlib
import heapq
import importlib.util
import json
from fractions import Fraction as F
from pathlib import Path

from .reach import earliest_free, flame_avoiding
from .replay import any_contact, segment_contact

REPO = Path(__file__).resolve().parents[2]
KIT_CHECKER = REPO / "integration" / "kit" / "runner" / "ffi_independent_checker.py"
KIT_MANIFEST = REPO / "integration" / "kit" / "CANDIDATE_MANIFEST.json"


# ------------------------------------------------------------------------------------------------ own assertions
def node_lower_bound(graph, start: str, target: str, max_ticks: int):
    """Shortest travel ticks over directed edges ignoring turn restrictions (a lower bound; independent algorithm)."""
    dist = {start: 0}
    heap = [(0, start)]
    while heap:
        d, n = heapq.heappop(heap)
        if d != dist.get(n):
            continue
        if n == target and d > 0:
            return d
        for e in graph.out.get(n, []):
            nd = d + graph.ticks[e]
            if nd <= max_ticks and nd < dist.get(graph.v[e], 1 << 62):
                dist[graph.v[e]] = nd
                heapq.heappush(heap, (nd, graph.v[e]))
    return None


def turn_fastest(graph, start: str, target: str, max_ticks: int):
    """Fastest fire-free travel ticks start -> target honouring forbidden turns, admitted on arrival over an edge
    (a separate implementation of roads.fastest_ticks, used to re-derive "a fire-free road would fit" claims)."""
    best: dict = {}
    heap = []
    for e in graph.out.get(start, []):
        t = graph.ticks[e]
        if t <= max_ticks and t < best.get(e, 1 << 62):
            best[e] = t
            heapq.heappush(heap, (t, e))
    while heap:
        d, e = heapq.heappop(heap)
        if d != best.get(e):
            continue
        if graph.v[e] == target:
            return d
        for f in graph.out.get(graph.v[e], []):
            if (e, f) in graph.forbidden:
                continue
            nd = d + graph.ticks[f]
            if nd <= max_ticks and nd < best.get(f, 1 << 62):
                best[f] = nd
                heapq.heappush(heap, (nd, f))
    return None


def validate(ctx, rec: dict, ev) -> dict:
    """Run the assertions that apply to this origin. Returns {id: True/False} for applicable ones only."""
    pk, H = ctx.packet, F(ctx.horizon)
    out = {}
    # (a') routes checked at the deadline are flame-free at their recorded times
    if ev.deadline_routes:
        out["a_route"] = all(not any_contact(pk, segs, F(0), H) for _, _, _, segs, _ in ev.deadline_routes)
    # (a) and (b) for binding items
    if ev.binding_checks:
        ok_a, ok_b = True, True
        for chk in ev.binding_checks:
            segs, i, shift = chk["segs"], chk["segment_index"], chk["shift"]
            seg = segs[i]
            sc0 = segment_contact(pk, seg, F(0), H)
            if sc0.pairs or sc0.router_members or not chk["slack"] > 0 or chk["slack"] > shift:
                ok_a = False
            sc = segment_contact(pk, seg, shift, H)
            if not sc.pairs or {p[0] for p in sc.pairs} != chk["members"]:
                ok_b = False
            for earlier in segs[:i]:
                se = segment_contact(pk, earlier, shift, H)
                if se.pairs or se.router_members:
                    ok_b = False
                    break
        out["a"], out["b"] = ok_a, ok_b
    # (c) event times inside the recorded scenario window
    lo, hi = pk.valid_from, pk.valid_until
    times = list(ev.times)
    for it in rec.get("binding", []) + rec.get("exits", []):
        times += [it.get("flame_time_s"), it.get("contact_time_s"), it.get("pass_time_at_deadline_s")]
    if rec.get("deadline_offset_s") is not None:
        times.append(rec["deadline_offset_s"])
    if rec.get("next_offset_s") is not None:
        times.append(rec["next_offset_s"])
    times = [t for t in times if t is not None]
    if times:
        out["c"] = all(lo <= F(t) <= hi for t in times)
    # (w) window proofs and the deadline cause (checked origins)
    proofs = [w for w in ev.window_proofs if not w.get("no_route_attempt")]
    if proofs:
        ok = True
        for w in proofs:
            if w.get("zero_travel"):
                ok &= max(w["next"], w["open"]) + w["dwell"] > w["close"]
                continue
            if w["fire_free_late"]:
                lb = node_lower_bound(ctx.graph, w["start"], w["destination"], ctx.horizon)
                ok &= (lb is None or w["next"] + lb + w["dwell"] > w["close"]) and \
                    (w["fastest_ticks"] is None or w["next"] + w["fastest_ticks"] + w["dwell"] > w["close"])
            else:
                # "a fire-free road would still fit": the fastest time is re-derived by a separate search
                ok &= w["fastest_ticks"] is not None and \
                    turn_fastest(ctx.graph, w["start"], w["destination"], ctx.horizon) == w["fastest_ticks"] and \
                    w["next"] + w["fastest_ticks"] + w["dwell"] <= w["close"]
                if w["relax_late"]:
                    again = flame_avoiding(ctx.index, w["start"], w["next"], [w["destination"]], w["close"] - w["dwell"], turns=False)
                    ok &= again["arrival"][w["destination"]] is None or \
                        flame_avoiding(ctx.index, w["start"], w["next"], [w["destination"]], w["close"] - w["dwell"])["arrival"][w["destination"]] is None
        real = [w for w in proofs if not w.get("zero_travel")]
        dest = (rec.get("deadline_route") or {}).get("destination_id")
        if rec.get("detail_code") in ("window_fire_free", "window_fire_detour", "other_shelters_flame_blocked"):
            # the shown destination's own claim must be one of the proven kinds
            ok &= any((w.get("fire_free_late") or w.get("relax_late")) for w in real if w.get("destination_id") == dest)
        if rec.get("deadline_cause") == "time_window":
            ok &= bool(real) and all(w["fire_free_late"] for w in real)
        if rec.get("deadline_cause") == "flames":
            ok &= any(not w["fire_free_late"] and (w["relax_late"] or w["dwell_blocked"]) for w in real)
        out["w"] = bool(ok)
    # (e) exits / no-route attempts
    nr = [w for w in ev.window_proofs if w.get("no_route_attempt")]
    if nr:
        ok = all(w["late"] for w in nr)
        if rec.get("detail_code") == "no_route_even_without_fire":
            for w in nr:
                lb = node_lower_bound(ctx.graph, w["start"], w["destination"], ctx.horizon)
                ok &= w["fire_free_late"] and (lb is None or w["offset"] + lb + w["dwell"] > w["close"])
        if rec.get("deadline_cause") == "flames":
            # some attempt would fit on a fire-free road (re-derived by the separate search)
            ok &= any(w["fastest_ticks"] is not None and w["offset"] + w["fastest_ticks"] + w["dwell"] <= w["close"] and
                      turn_fastest(ctx.graph, w["start"], w["destination"], ctx.horizon) == w["fastest_ticks"] for w in nr)
        if rec.get("reason_code") == "all_exits_blocked":
            ok &= all(w["unreachable"] for w in nr)
            if ev.exits_proof:
                g = ctx.graph
                for edge_id, at in ev.exits_proof["frontier"]:
                    e = g.edge_index[edge_id]
                    # a genuine flame block: startable before the window ends, yet every start second meets flame
                    ok &= at <= ctx.horizon - g.ticks[e]
                    ok &= earliest_free(ctx.index.edge_blocks(e), at, ctx.horizon - g.ticks[e]) is None
                ok &= not ev.exits_proof.get("horizon_cut")
        out["e"] = bool(ok)
    return out


def apply_checks(rec: dict, checks: dict) -> dict:
    """Attach the assertion results; any failed assertion withdraws the explanation (never published unverified)."""
    failed = sorted(k for k, v in checks.items() if v is False)
    if failed:
        rec["notes"].append("withdrawn %s/%s: validation failed (%s)" % (rec["status"], rec["reason_code"], ",".join(failed)))
        rec.update(status="not_explainable", reason_code="other", detail_code="validation_failed:" + ",".join(failed),
                   binding=[], exits=[])
    rec["checks"] = checks
    return rec


# ------------------------------------------------------------------------------------------------ kit cross-check
def load_kit_checker():
    manifest = json.loads(KIT_MANIFEST.read_text())
    want = manifest["files"]["runner/ffi_independent_checker.py"]
    got = hashlib.sha256(KIT_CHECKER.read_bytes()).hexdigest()
    if got != want:
        raise RuntimeError("kit independent checker hash differs from CANDIDATE_MANIFEST.json")
    spec = importlib.util.spec_from_file_location("wfg_kit_ffi_independent_checker_ro", KIT_CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, got


def kit_request(packet, req: dict, departure: int, horizon: int) -> dict:
    ids = packet.member_ids
    return {"position": {"node": req["start"]}, "incoming_edge": None, "departure": departure, "horizon": horizon,
            "destinations": [{"node": req["destination"], "dwell": req["dwell"], "open_intervals": [[req["open"], req["close"] if req["close"] is not None else horizon]]}],
            "incurred": {m: 0 for m in ids}, "objective": "earliest_arrival", "exposure_scope": "including_dwell",
            "budgets": {"peak": 10, "dose": {m: 100 for m in ids}}}


def kit_crosscheck(I, KG, KP, packet, rec: dict, ev, horizon: int) -> dict:
    """Independent re-check of (a') and (b) with the kit checker objects (I = module, KG = I.Graph, KP = I.Packet)."""
    out = {}
    if ev.deadline_routes:
        ok = True
        for _, _, route, _, req in ev.deadline_routes:
            r = kit_request(packet, req, route["departure"], horizon)
            gram = I.grammar(KG, r, route["legs"], route["destination"], KP.horizon)
            if not gram["ok"]:
                ok = False
                continue
            ok &= I.whole_road_contact(KP, gram)["status"] == "CLEAR"
            # the kit centre model's contact flag only depends on occupancies of cells that ever burn; dropping the other
            # segments leaves it unchanged and skips their (unused) exact peak/dose integration
            burning = set(KP.sources)
            near = [sg for sg in gram["segments"] if any(c in burning for c, *_ in sg["pieces"]) or any(c in burning for c, _ in sg["points"])]
            cm = I.centre_model(KP, r, dict(gram, segments=near), conservative=True)
            ok &= not any(v["flame_contact"] for v in cm["per_member"].values())
        out["kit_a_route"] = bool(ok)
    if ev.binding_checks:
        ok = True
        for chk in ev.binding_checks:
            dest = chk["destination_id"]                 # the route that produced this item
            route, req = next((rt, rq) for d, _, rt, _, rq in ev.deadline_routes if d == dest)
            shift = int(chk["shift"])
            seg = chk["segs"][chk["segment_index"]]
            if seg.kind not in ("EDGE", "WAIT"):
                continue                                # issue/dwell items are checked by (a)/(b) only
            legs = [dict(l, start=l["start"] + shift, end=l["end"] + shift) for l in route["legs"][:seg.leg_index + 1]]
            r = kit_request(packet, req, route["departure"] + shift, horizon)
            r["horizon"] = max(horizon, legs[-1]["end"])          # grammar only; contact uses the packet phases
            gram = I.grammar(KG, r, legs, None, F(10 ** 9))
            wit = I.whole_road_contact(KP, gram)["witnesses"]
            # the kit reports each member's earliest witness without the hazard-window cut; ours keeps times <= horizon
            inside = {packet.member_ids.index(m): w for m, w in wit.items() if F(w["time_exact"]) <= horizon}
            ok &= set(inside) == chk["members"]
            for s, w in inside.items():
                ok &= w["segment_index"] == seg.index            # kit segments: ISSUE = 0, legs from 1, same order
                ok &= F(w["time_exact"]) == chk["member_times"][s]
        out["kit_b"] = bool(ok)
    return out
