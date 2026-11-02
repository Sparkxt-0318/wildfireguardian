"""End-to-end classification on synthetic worlds with hand-computed answers.

Geometry (see test_engine.py): A (50,150) -> B (250,150) -> C (350,150); a traversal of A->B starting at t occupies
cell 5 on [t+5, t+15] (20-tick edge). The origin enters at A, the shelter is C (dwell 120 s, window [0, 3600]).
"""
import json
from fractions import Fraction as F

from tools.explain_deadlines.explain import Context, explain_plan
from tools.explain_deadlines.packet import Packet
from tools.explain_deadlines.plans import CacheModel
from tools.explain_deadlines.reach import ContactIndex
from tools.explain_deadlines.roads import RoadGraph
from tools.explain_deadlines.validate import apply_checks, kit_crosscheck, load_kit_checker, validate

from . import synth

OFFSETS = (0, 600, 1200, 1800, 2400, 3000)


def line_world(ab=20, bc=10):
    return synth.graph({"A": (50, 150), "B": (250, 150), "C": (350, 150)}, [("AB", "A", "B", ab), ("BC", "B", "C", bc)])


def build(tmp_path, raw, verdicts, packet_kw, start="A", dest="C", edges=("AB", "BC"), origin="o1"):
    """verdicts: {offset: 'checked_route' | 'model_no_route' | ('unresolved', code)}."""
    checks, atts = {}, []
    for off in OFFSETS:
        v = verdicts[off]
        jid = "j%d" % off
        if v == "checked_route":
            job = synth.route_job(jid, start=start, dest=dest, depart=off, legs_edges=list(edges), raw_graph=raw)
            atts.append(synth.attempt("s1", off, v, jid, job["result"]["arrival_s"]))
        elif v == "model_no_route":
            job = synth.refusal_job(jid, start=start, dest=dest, depart=off)
            atts.append(synth.attempt("s1", off, v, jid))
        else:
            job = synth.refusal_job(jid, start=start, dest=dest, depart=off, verdict="unresolved", reason=v[1])
            atts.append(synth.attempt("s1", off, "unresolved", jid, reason=v[1]))
        checks[jid] = job
    doc = synth.cache_doc([(origin, atts)], checks)
    g = RoadGraph(raw)
    synth.write_packet(tmp_path / "pk", **packet_kw)
    pk = Packet(tmp_path / "pk", g.grid)
    ctx = Context(region_id="synthetic", input_time="2025-01-01T00:00:00Z", scenario_set_id="synthetic:set", graph=g, packet=pk,
                  index=ContactIndex(g, pk), places=None, model=CacheModel(doc), to_lonlat=synth.lonlat_identity, horizon=3600)
    rec, ev = explain_plan(ctx, ctx.model.plans[origin])
    return ctx, rec, ev


def test_flame_on_route_hand_values(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = v[600] = "checked_route"
    ctx, rec, ev = build(tmp_path, line_world(), v, {"ignitions": {1: {5: 630.0}}})
    assert (rec["status"], rec["reason_code"]) == ("explained", "flame_on_route")
    assert rec["deadline_offset_s"] == 600 and rec["next_offset_s"] == 1200 and rec["next_verdict"] == "model_no_route"
    b = rec["binding"][0]
    assert b["edge_id"] == "AB" and b["members"] == [1] and b["members_total"] == 4
    assert b["flame_time_s"] == 630.0          # member 1 ignites cell 5 at 630 s
    assert b["pass_time_at_deadline_s"] == 615.0   # leaving at 600 the vehicle leaves cell 5 at 615 s
    assert b["slack_s"] == 15.0
    assert b["contact_time_s"] == 1205.0       # leaving at 1200 it enters the burning cell at 1205 s
    assert b["label_source"] == "unnamed" and b["label_ko"] is None and b["near_node_id"] == "A"
    assert rec["window"]["fire_free"] is False and rec["window"]["fastest_end_s"] == 1200 + 30 + 120
    checks = validate(ctx, rec, ev)
    assert checks == {"a_route": True, "a": True, "b": True, "c": True, "w": True}
    I, _ = load_kit_checker()
    KG = I.Graph(line_world())
    KP = I.Packet(tmp_path / "pk", KG)
    assert kit_crosscheck(I, KG, KP, ctx.packet, rec, ev, 3600) == {"kit_a_route": True, "kit_b": True}


def test_window_fire_free(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = v[600] = "checked_route"
    ctx, rec, ev = build(tmp_path, line_world(1500, 1000), v, {})
    assert (rec["status"], rec["reason_code"], rec["detail_code"]) == ("explained", "window", "window_fire_free")
    # the relaxed arrival 1200 + 2500 = 3700 s lies beyond the 3600 s hazard horizon, so none is reported
    assert rec["window"] == {"close_s": 3600, "dwell_s": 120, "fire_free": True, "fastest_end_s": 1200 + 2500 + 120,
                             "flame_avoiding_arrival_s": None, "limit": "scenario_window", "horizon_s": 3600}
    assert rec["binding"] == []
    assert validate(ctx, rec, ev)["w"] is True


def test_last_checked_offset(tmp_path):
    ctx, rec, ev = build(tmp_path, line_world(), {o: "checked_route" for o in OFFSETS}, {})
    assert (rec["status"], rec["reason_code"], rec["deadline_offset_s"], rec["next_offset_s"]) == ("explained", "no_later_offset", 3000, None)
    assert validate(ctx, rec, ev)["a_route"] is True


def test_unresolved_next_is_never_turned_into_a_reason(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = "checked_route"
    v[600] = ("unresolved", "TIMEOUT")
    ctx, rec, ev = build(tmp_path, line_world(), v, {"ignitions": {1: {5: 30.0}}})
    assert (rec["status"], rec["reason_code"], rec["next_verdict"]) == ("not_explainable", "unresolved_next", "unresolved")
    assert rec["next_attempt_verdicts"] == {"unresolved/TIMEOUT": 1}
    assert rec["binding"] == [] and rec["exits"] == []


def test_refusal_without_a_rigorous_cause_is_not_explained(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = "checked_route"          # no fire at all and a 30 s trip: nothing explains the refusal at 600 s
    ctx, rec, ev = build(tmp_path, line_world(), v, {})
    assert (rec["status"], rec["reason_code"], rec["detail_code"]) == ("not_explainable", "other", "refusal_not_reproduced")
    assert rec["binding"] == []


def test_all_exits_blocked(tmp_path):
    nodes = {"S": (50, 50), "M": (150, 50), "T": (350, 50), "N": (50, 250), "P": (350, 250)}
    raw = synth.graph(nodes, [("SM", "S", "M", 10), ("MT", "M", "T", 20), ("SN", "S", "N", 20), ("NP", "N", "P", 30), ("PT", "P", "T", 20)])
    ctx, rec, ev = build(tmp_path, raw, {o: "model_no_route" for o in OFFSETS}, {"current": [2, 11], "R": 3700.0},
                         start="S", dest="T", edges=())
    assert (rec["status"], rec["reason_code"], rec["verdict_summary"]) == ("explained", "all_exits_blocked", "model_no_route")
    ex = {e["edge_id"]: e for e in rec["exits"]}
    assert sorted(ex) == ["MT", "NP"] and rec["reachable_nodes"] == 3
    assert ex["MT"]["reached_at_s"] == 10 and ex["MT"]["contact_time_s"] == 15.0 and ex["MT"]["flame_time_s"] == 0.0
    assert ex["NP"]["reached_at_s"] == 20 and ex["NP"]["contact_time_s"] == 45.0      # enters cell 11 at x = 300 (z = 5/6)
    assert ex["MT"]["members"] == [0, 1, 2, 3]
    assert validate(ctx, rec, ev) == {"c": True, "e": True}


def test_failed_assertion_withdraws_the_explanation(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = v[600] = "checked_route"
    ctx, rec, ev = build(tmp_path, line_world(), v, {"ignitions": {1: {5: 630.0}}})
    ev.binding_checks[0]["members"] = {0}                 # pretend the stated members were wrong
    checks = validate(ctx, rec, ev)
    assert checks["b"] is False
    out = apply_checks(rec, checks)
    assert (out["status"], out["reason_code"], out["detail_code"]) == ("not_explainable", "other", "validation_failed:b")
    assert out["binding"] == [] and any(n.startswith("withdrawn explained/flame_on_route") for n in out["notes"])


def test_record_is_json_serialisable(tmp_path):
    v = {o: "model_no_route" for o in OFFSETS}
    v[0] = v[600] = "checked_route"
    _, rec, _ = build(tmp_path, line_world(), v, {"ignitions": {1: {5: 630.0}}})
    json.dumps(rec, allow_nan=False)


def test_routes_meeting_the_same_road_at_different_times_are_not_merged(tmp_path):
    """Shelter s1 via A-B-C reaches road A->B at once; shelter s2 via A-Y-A-B-D reaches it 10 s later. Member 2 ignites
    cell 5 (on A->B) at 650 s. Leaving at 600 both are clear (they leave cell 5 at 615 and 625); leaving at 1200 both
    meet it, so the binding lists two items with their own pass times and slack (35 s and 25 s)."""
    raw = synth.graph({"A": (50, 150), "B": (250, 150), "C": (350, 150), "Y": (50, 250), "D": (250, 50)},
                      [("AB", "A", "B", 20), ("BC", "B", "C", 10), ("AY", "A", "Y", 5), ("YA", "Y", "A", 5), ("BD", "B", "D", 10)])
    checks, atts = {}, []
    for off in OFFSETS:
        for dest, node, edges in (("s1", "C", ["AB", "BC"]), ("s2", "D", ["AY", "YA", "AB", "BD"])):
            jid = "%s_%d" % (dest, off)
            if off <= 600:
                job = synth.route_job(jid, start="A", dest=node, depart=off, legs_edges=edges, raw_graph=raw)
                atts.append(synth.attempt(dest, off, "checked_route", jid, job["result"]["arrival_s"]))
            else:
                job = synth.refusal_job(jid, start="A", dest=node, depart=off)
                atts.append(synth.attempt(dest, off, "model_no_route", jid))
            checks[jid] = job
    doc = synth.cache_doc([("o1", atts)], checks)
    g = RoadGraph(raw)
    synth.write_packet(tmp_path / "pk", ignitions={2: {5: 650.0}})
    pk = Packet(tmp_path / "pk", g.grid)
    ctx = Context(region_id="synthetic", input_time="2025-01-01T00:00:00Z", scenario_set_id="synthetic:set", graph=g, packet=pk,
                  index=ContactIndex(g, pk), places=None, model=CacheModel(doc), to_lonlat=synth.lonlat_identity, horizon=3600)
    rec, ev = explain_plan(ctx, ctx.model.plans["o1"])
    assert (rec["status"], rec["reason_code"]) == ("explained", "flame_on_route")
    assert rec["deadline_route"]["destination_id"] == "s1"               # earliest arrival at 600 s
    items = {tuple(b["destination_ids"]): b for b in rec["binding"]}
    assert set(items) == {("s1",), ("s2",)}
    assert (items[("s1",)]["pass_time_at_deadline_s"], items[("s1",)]["slack_s"]) == (615.0, 35.0)
    assert (items[("s2",)]["pass_time_at_deadline_s"], items[("s2",)]["slack_s"]) == (625.0, 25.0)
    assert rec["binding"][0]["destination_ids"] == ["s1"]                # the shown route's item first
    checks_ = validate(ctx, rec, ev)
    assert checks_["a"] and checks_["b"]
    I, _ = load_kit_checker()
    KG = I.Graph(raw)
    assert kit_crosscheck(I, KG, I.Packet(tmp_path / "pk", KG), pk, rec, ev, 3600)["kit_b"] is True
