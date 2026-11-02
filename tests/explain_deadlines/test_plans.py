"""The cache reader must reproduce the planner's own deadline rules (plan.ts / cache.ts) and rebuild routes exactly."""
import copy

import pytest

from tools.explain_deadlines.plans import CacheModel, RouteError, combine, reconstruct_legs

from . import synth

RAW = synth.graph({"A": (50, 150), "B": (250, 150), "C": (350, 150)}, [("AB", "A", "B", 20), ("BC", "B", "C", 10)],
                  waitable={"B"})


def doc_two_shelters(recheck=False):
    a = synth.attempt
    atts = [a("d1", 0, "checked_route", "j1", 500), a("d2", 0, "checked_route", "j2", 400),
            a("d1", 600, "checked_route", "j3", 1100), a("d2", 600, "model_no_route", "j4"),
            a("d1", 1200, "model_no_route", "j5"), a("d2", 1200, "unresolved", "j6", reason="TIMEOUT")]
    checks = {}
    if recheck:
        rj = synth.route_job("j4r", start="A", dest="C", depart=600, legs_edges=["AB", "BC"], raw_graph=RAW)
        rj["result"]["arrival_s"] = 630
        rj["recheck_of"] = "j4"
        checks["j4r"] = rj
    return synth.cache_doc([("o1", atts)], checks, offsets=(0, 600, 1200))


def test_combine_rule():
    assert combine(["checked_route", "unresolved"]) == "checked_route"
    assert combine(["model_no_route", "model_no_route"]) == "model_no_route"
    assert combine(["model_no_route", "unresolved"]) == "unresolved"
    assert combine([]) == "unresolved"


def test_deadline_best_and_next_cell():
    p = CacheModel(doc_two_shelters()).plans["o1"]
    assert p.best_verdict == "checked_route" and p.latest_s == 600 and p.contiguous_s == 600
    assert p.best.destination_id == "d1" and p.best.job_id == "j3"
    nxt = [c for c in p.sweep if c.offset_s > 600][0]
    assert nxt.offset_s == 1200 and nxt.verdict == "unresolved"          # one shelter unresolved: never model_no_route


def test_recheck_replaces_the_attempt_it_reran():
    p = CacheModel(doc_two_shelters(recheck=True)).plans["o1"]
    cell = [c for c in p.sweep if c.offset_s == 600][0]
    d2 = [x for x in cell.attempts if x.destination_id == "d2"][0]
    assert d2.verdict == "checked_route" and d2.job_id == "j4r" and d2.recheck_of == "j4"
    assert p.best.destination_id == "d2" and p.best.arrival_s == 630     # earliest arrival wins
    assert "recheck_replaced_attempts" in p.notes


def test_research_window_skip_is_not_a_check():
    j0 = synth.route_job("r0", start="A", dest="C", depart=0, legs_edges=["AB", "BC"], raw_graph=RAW)
    rc = [{"origin_id": "research:x:origin", "destination_id": "research:x:destination", "depart_offset_s": 0, "job_id": "r0"},
          {"origin_id": "research:x:origin", "destination_id": "research:x:destination", "depart_offset_s": 600,
           "job_id": None, "skipped": "WINDOW_UNSATISFIABLE"}]
    doc = synth.cache_doc([], {"r0": j0}, research_checks=rc)
    p = CacheModel(doc).plans["research:x:origin"]
    assert p.latest_s == 0 and p.contiguous_s == 0
    skip = [c for c in p.sweep if c.offset_s == 600][0]
    assert skip.skipped == "window_unsatisfiable" and skip.attempts == [] and skip.verdict == "unresolved"


def test_route_rebuild_matches_the_router_hash_including_waits():
    job = synth.route_job("w", start="A", dest="C", depart=300, legs_edges=["AB", "BC"], raw_graph=RAW, waits=[(1, 3)])
    rt = reconstruct_legs(job)
    kinds = [l["kind"] for l in rt["legs"]]
    assert kinds == ["EDGE", "WAIT", "WAIT", "WAIT", "EDGE"]
    assert rt["legs"][1] == {"kind": "WAIT", "node": "B", "start": 320, "end": 321}
    assert rt["arrival"] == 333 and rt["departure"] == 300


def test_route_rebuild_refuses_a_tampered_route():
    job = synth.route_job("w", start="A", dest="C", depart=0, legs_edges=["AB", "BC"], raw_graph=RAW)
    bad = copy.deepcopy(job)
    bad["result"]["route"]["properties"]["times_s"][1] = 21          # one second off
    bad["result"]["route"]["properties"]["times_s"][2] = 31
    bad["result"]["arrival_s"] = 31
    with pytest.raises(RouteError):
        reconstruct_legs(bad)
