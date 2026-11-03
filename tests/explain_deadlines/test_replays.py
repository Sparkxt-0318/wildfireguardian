"""Whole-file replays of recorded routes (validation ``replay_checked_routes`` / ``replay_travel_only``) and the
fail-closed command line, on synthetic worlds with hand-computed answers.

Geometry (see test_engine.py): A (50,150) -> B (250,150) -> C (350,150); a traversal of A->B (20 ticks) starting at t
occupies cell 5 on [t+5, t+15]. Member 1 ignites cell 5 at 630 s (burning until 4630 s), so a route leaving A at 600 s
passes cell 5 on [605, 615] before the flame (clear), and one leaving at 1200 s meets it at 1205 s in member 1 only.
"""
import hashlib
import json

import pytest

from tools.explain_deadlines import cli
from tools.explain_deadlines.packet import Packet
from tools.explain_deadlines.roads import RoadGraph
from tools.explain_deadlines.validate import ReplayMismatch, replay_contacts, replay_recorded_routes, require_replays_clean

from . import synth

IGNITION = {"ignitions": {1: {5: 630.0}}}
RAW = synth.graph({"A": (50, 150), "B": (250, 150), "C": (350, 150)}, [("AB", "A", "B", 20), ("BC", "B", "C", 10)])


def world(tmp_path):
    g = RoadGraph(RAW)
    synth.write_packet(tmp_path / "pk", **IGNITION)
    return g, Packet(tmp_path / "pk", g.grid)


def route(job_id, depart):
    return synth.route_job(job_id, start="A", dest="C", depart=depart, legs_edges=["AB", "BC"], raw_graph=RAW)


def travel(job_id, depart, contact, status, pk):
    return synth.travel_only_job(job_id, contact=contact, status=status, raw_graph=RAW, member_ids=pk.member_ids,
                                 start="A", dest="C", depart=depart, legs_edges=["AB", "BC"])


def doc(route_checks=None, travel_only=None):
    return {"route_checks": route_checks or {}, "travel_only": travel_only or {}}


# ------------------------------------------------------------------------------------------------ replay engine
def test_replay_contacts_hand_values(tmp_path):
    g, pk = world(tmp_path)
    assert replay_contacts(g, pk, route("j", 600), 3600) == (set(), set(), False)
    assert replay_contacts(g, pk, route("j", 1200), 3600) == ({1}, {1}, False)     # member index 1, both rules


def test_every_recorded_checked_route_is_replayed(tmp_path):
    g, pk = world(tmp_path)
    checks = {"j600": route("j600", 600), "j1800": synth.refusal_job("j1800", start="A", dest="C", depart=1800)}
    stats, problems = replay_recorded_routes(g, pk, doc(checks), 3600)
    assert stats["replay_checked_routes"] == {"unit": "route", "routes": 1, "contact_free": 1, "mismatches": 0, "not_replayed": 0,
                                              "applicable": 1, "passed": 1, "failed": 0}
    require_replays_clean(stats, problems, "synthetic")                             # clean: no exception
    # a route recorded as checked that meets flame at its own recorded times is a mismatch: the run stops
    checks["j1200"] = route("j1200", 1200)
    stats, problems = replay_recorded_routes(g, pk, doc(checks), 3600)
    assert stats["replay_checked_routes"] == {"unit": "route", "routes": 2, "contact_free": 1, "mismatches": 1, "not_replayed": 0,
                                              "applicable": 2, "passed": 1, "failed": 1}
    assert len(problems) == 1 and problems[0].startswith("route_checks/j1200: recorded checked_route meets flame in members [1]")
    with pytest.raises(ReplayMismatch, match="j1200"):
        require_replays_clean(stats, problems, "synthetic")


def test_a_route_that_cannot_be_rebuilt_is_not_filtered_out(tmp_path):
    g, pk = world(tmp_path)
    bad = route("j600", 600)
    bad["result"]["route"]["properties"]["route_sha256"] = "0" * 64                 # legs no longer hash to the record
    stats, problems = replay_recorded_routes(g, pk, doc({"j600": bad}), 3600)
    assert (stats["replay_checked_routes"]["not_replayed"], stats["replay_checked_routes"]["failed"]) == (1, 1)
    with pytest.raises(ReplayMismatch):
        require_replays_clean(stats, problems, "synthetic")


def test_travel_only_flags_compared_with_the_recorded_assessment(tmp_path):
    g, pk = world(tmp_path)
    F_, T_ = False, True
    no_route = synth.refusal_job("t6", start="A", dest="C", depart=1800, verdict="unresolved", reason="CHECK_FAILED")
    tos = {
        "o1": travel("t1", 1200, [F_, T_, F_, F_], "DEFINITE_CONTACT", pk),     # matches: member 1 only
        "o2": travel("t2", 600, [F_, F_, F_, F_], "CLEAR", pk),                 # matches: clear
        "o3": travel("t3", 1200, [F_, F_, F_, F_], "DEFINITE_CONTACT", pk),     # per-member flags differ
        "o4": travel("t4", 1200, [F_, T_, F_, F_], "CLEAR", pk),                # whole-road status differs
        "o5": travel("t5", 600, [F_, F_, F_, F_], "CLEAR", pk),                 # a member missing: not comparable
        "o6": no_route,                                                         # no route: nothing to replay
    }
    del tos["o5"]["result"]["full_policy_assessment"]["per_scenario"][pk.member_ids[3]]
    stats, problems = replay_recorded_routes(g, pk, doc(travel_only=tos), 3600)
    assert stats["replay_travel_only"] == {"unit": "route", "entries": 6, "routes": 5, "matches": 2, "mismatches": 2, "not_replayed": 1,
                                           "member_flags": 16, "with_contact": 2, "applicable": 5, "passed": 2, "failed": 3}
    assert sorted(p.split(":")[0] for p in problems) == ["travel_only/o3", "travel_only/o4", "travel_only/o5"]
    with pytest.raises(ReplayMismatch):
        require_replays_clean(stats, problems, "synthetic")
    clean = {k: tos[k] for k in ("o1", "o2", "o6")}
    stats, problems = replay_recorded_routes(g, pk, doc(travel_only=clean), 3600)
    assert (stats["replay_travel_only"]["matches"], stats["replay_travel_only"]["failed"], problems) == (2, 0, [])


def test_chord_cache_gives_the_same_replay(tmp_path):
    g, pk = world(tmp_path)
    checks = {"j600": route("j600", 600), "j1200": route("j1200", 1200)}
    cache = {}
    assert replay_recorded_routes(g, pk, doc(checks), 3600, cache) == replay_recorded_routes(g, pk, doc(checks), 3600)
    assert set(cache) == {"AB", "BC"}


# ------------------------------------------------------------------------------------------------ command line, end to end
INPUT = "2025-01-01T00:00:00Z"
SET = "synthetic:set"
IDS = ["%s:%d" % (SET, i) for i in range(4)]          # the members synth.write_packet writes


def travel_world(contact, status, depart=1200):
    return {"o1": synth.travel_only_job("t1", contact=contact, status=status, raw_graph=RAW, member_ids=IDS,
                                        start="A", dest="C", depart=depart, legs_edges=["AB", "BC"])}


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def repo_world(tmp_path, *, extra_checks=None, travel_only=None):
    """A complete synthetic repository layout (cache + INDEX, graph, packet, INPUT_FILES.json) for the command line.
    The origin o1 has checked routes at 0 and 600 s and none later (flame on the route from 1200 s)."""
    repo = tmp_path / "repo"
    data = repo / "data" / "routing"
    gpath = data / "graphs" / "synthetic" / "graph.json"
    gpath.parent.mkdir(parents=True)
    gpath.write_text(json.dumps(RAW))
    prel = "latest_inputs_try02/packets/synthetic/20250101T000000Z"
    ids = synth.write_packet(data / prel, **IGNITION)
    assert ids == IDS
    psha = {n: sha(data / prel / n) for n in ("HAZARD.json", "REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")}
    rows = [{"path": "graphs/synthetic/graph.json", "sha256": sha(gpath)}] + [{"path": "%s/%s" % (prel, n), "sha256": h} for n, h in psha.items()]
    (data / "INPUT_FILES.json").write_text(json.dumps(rows))
    prov = dict(graph_sha=sha(gpath), packet_sha=psha, set_id=SET, region="synthetic", input_time=INPUT, member_ids=ids)
    checks, atts = {}, []
    for off in (0, 600, 1200, 1800, 2400, 3000):
        jid = "j%d" % off
        if off <= 600:
            checks[jid] = synth.with_provenance(route(jid, off), **prov)
            atts.append(synth.attempt("C", off, "checked_route", jid, checks[jid]["result"]["arrival_s"]))
        else:
            checks[jid] = synth.with_provenance(synth.refusal_job(jid, start="A", dest="C", depart=off), **prov)
            atts.append(synth.attempt("C", off, "model_no_route", jid))
    for jid, job in (extra_checks or {}).items():
        checks[jid] = synth.with_provenance(job, **prov)
    d = synth.cache_doc([("o1", atts)], checks)
    d.update(scenario_set_id=SET, input_time=INPUT)
    d["plans"][0]["result"]["provenance"] = {"input_hashes": {"graph": prov["graph_sha"], "hazard": psha["HAZARD.json"]}, "scenario_set_id": SET}
    d["travel_only"] = travel_only or {}
    cpath = repo / "planner" / "cache" / "synthetic" / "20250101T000000Z.json"
    cpath.parent.mkdir(parents=True)
    cpath.write_text(json.dumps(d))
    (repo / "planner" / "cache" / "INDEX.json").write_text(json.dumps(
        [{"region_id": "synthetic", "scenario_set_id": SET, "input_time": INPUT, "path": "synthetic/20250101T000000Z.json", "sha256": sha(cpath)}]))
    return repo


def run(repo, out, *extra):
    return cli.main(["generate", "--repo", str(repo), "--out", str(out), "--no-kit", *extra])


def test_cli_writes_replay_counts(tmp_path):
    repo = repo_world(tmp_path, travel_only=travel_world([False, True, False, False], "DEFINITE_CONTACT"))
    out = tmp_path / "out"
    assert run(repo, out) == 0
    f = json.loads((out / "synthetic__20250101T000000Z.json").read_text())
    v = f["summary"]["validation"]
    assert v["replay_checked_routes"] == {"applicable": 2, "contact_free": 2, "failed": 0, "mismatches": 0, "not_replayed": 0,
                                          "passed": 2, "routes": 2, "unit": "route"}
    assert v["replay_travel_only"] == {"applicable": 1, "entries": 1, "failed": 0, "matches": 1, "member_flags": 4, "mismatches": 0,
                                       "not_replayed": 0, "passed": 1, "routes": 1, "unit": "route", "with_contact": 1}
    assert f["origins"]["o1"]["reason_code"] == "flame_on_route"                    # the explanation itself is unchanged
    assert v["a_route"] == {"applicable": 1, "passed": 1, "failed": 0}              # per-origin counts keep their shape


@pytest.mark.parametrize("case", ["checked_route_meets_flame", "travel_only_flags_differ"])
def test_cli_writes_nothing_when_a_recorded_route_does_not_replay(tmp_path, case):
    if case == "checked_route_meets_flame":
        repo = repo_world(tmp_path, extra_checks={"jx": route("jx", 1200)})          # recorded as checked, meets flame
    else:
        repo = repo_world(tmp_path, travel_only=travel_world([False] * 4, "CLEAR"))  # the replay meets flame in member 1
    out = tmp_path / "out"
    with pytest.raises(ReplayMismatch):
        run(repo, out)
    assert not out.exists() or not list(out.glob("*.json"))
