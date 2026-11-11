"""Planner tests: contract fixtures, oracle equivalence, replay mutations, CLI behaviour. Standard library only.

Run from experimental/kcf-facility-planner:  python3 -m unittest discover -s tests -v
KCF_RANDOM_CASES overrides the number of random oracle cases (default 1500).
"""
import copy
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import oracle  # noqa: E402
from kcf_planner import replay as R  # noqa: E402
from kcf_planner import sipp_check  # noqa: E402
from kcf_planner.model import parse_case  # noqa: E402
from kcf_planner.run import run_case  # noqa: E402

FIX = ROOT / "fixtures" / "contract"
N_RANDOM = int(os.environ.get("KCF_RANDOM_CASES", "1500"))


def load(name):
    return json.loads((FIX / ("%s.json" % name)).read_text())


def edges_of(trip):
    return [(e["edge_id"], e["entry_s"], e["exit_s"]) for e in trip["edges"]]


class ContractFixtures(unittest.TestCase):
    def check(self, res):
        self.assertEqual(res["verification"]["independent_replay"]["violations"], [])
        self.assertTrue(res["verification"]["wfg_sipp"]["all_ok"], res["verification"]["wfg_sipp"])

    def test_normal(self):
        r = run_case(load("normal"))
        self.check(r)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        self.assertEqual(r["final_unload_s"], 13)
        self.assertEqual(r["people_with_checked_transport"], 12)
        self.assertEqual(edges_of(r["trips"][1]), [("e1", 3, 6), ("e2", 6, 11)])

    def test_delayed_second_vehicle_changes_road(self):
        r = run_case(load("delayed"))
        self.check(r)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        self.assertEqual(r["final_unload_s"], 25)
        # e1 is closed [10,30): V2 (ready 10, boarding to 11) takes e3/e4 rather than waiting until 30.
        self.assertEqual(edges_of(r["trips"][1]), [("e3", 11, 17), ("e4", 17, 23)])
        self.assertEqual(edges_of(r["trips"][0]), [("e1", 1, 4), ("e2", 4, 9)])

    def test_no_route(self):
        r = run_case(load("no_route"))
        self.check(r)
        self.assertEqual(r["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertIsNone(r["final_unload_s"])
        self.assertEqual(r["trips"], [])
        self.assertEqual(r["people_with_checked_transport"], 0)
        self.assertIn("CLOSURES_BLOCK_ALL_ROUTES", r["reason_codes"])
        case = parse_case(load("no_route"))
        for v in ("optimistic", "supported"):
            for c in sipp_check.check_no_route(case, view=v):
                self.assertIn(c["sipp_status"], ("EXHAUSTED", "DEPARTURE_AFTER_HORIZON"))
                self.assertIsNone(c["bruteforce"])

    def test_missing_input(self):
        r = run_case(load("missing_input"))
        self.check(r)
        self.assertEqual(r["status"], "MISSING_INPUT")
        self.assertIsNone(r["final_unload_s"])
        self.assertEqual(r["trips"], [])
        self.assertEqual(r["conditional_final_unload_s"], 11)
        self.assertEqual(len(r["missing_information"]), 1)
        m = r["missing_information"][0]
        self.assertEqual((m["edge_id"], m["unknown_interval"], m["traversal"]), ("e1", [0, 40], [1, 4]))

    def test_horizon_boundary_inclusive(self):
        r = run_case(load("horizon_boundary"))
        self.check(r)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        self.assertEqual(r["final_unload_s"], 11)  # exactly horizon_s
        r2 = run_case(load("horizon_boundary_minus_one"))
        self.assertEqual(r2["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertIn("OUT_OF_HORIZON", r2["reason_codes"])

    def test_closure_touching_at_endpoint_is_allowed(self):
        c = load("normal")
        c["edges"][0]["closed"] = [[4, 8]]
        r = run_case(c)
        self.assertEqual(edges_of(r["trips"][0])[0], ("e1", 1, 4))  # exit == closure start: no positive overlap
        c["edges"][0]["closed"] = [[3, 8]]
        r = run_case(c)
        self.assertNotEqual(edges_of(r["trips"][0])[0], ("e1", 1, 4))

    def test_shuttle(self):
        r = run_case(load("shuttle"))
        self.check(r)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        self.assertEqual(r["final_unload_s"], 28)
        kinds = [t["kind"] for t in r["trips"]]
        self.assertEqual(kinds, ["outbound", "empty_return", "outbound"])
        self.assertEqual({t["vehicle_id"] for t in r["trips"]}, {"V1"})
        ret = r["trips"][1]
        self.assertEqual(ret["incoming_edge_at_start"], "e2")
        self.assertEqual([e[0] for e in edges_of(ret)], ["e6", "e7", "e8"])  # e2->e5 U-turn forbidden
        self.assertEqual(ret["ready_s"], r["trips"][0]["unloading_end_s"])
        self.assertEqual(r["trips"][2]["ready_s"], ret["arrival_s"])

    def test_shuttle_turn_rule_persists_through_wait(self):
        c = load("shuttle")
        c["edges"][3]["closed"] = [[0, 60]]  # e6 closed: only the forbidden U-turn e5 remains
        r = run_case(c)
        self.assertEqual(r["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertEqual(r["people_with_checked_transport"], 6)  # G1 witnessed, G2 awaiting
        self.assertEqual(r["groups_awaiting_checked_transport"], ["G2"])
        self.assertEqual(r["verification"]["independent_replay"]["violations"], [])

    def test_no_second_vehicle_introduced(self):
        c = load("normal")
        c["vehicles"] = c["vehicles"][:1]
        r = run_case(c)
        self.assertEqual(r["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertIn("NO_VEHICLE_ASSIGNED", r["reason_codes"])
        self.assertEqual(r["people_with_checked_transport"], 6)
        c = load("shuttle")
        c["vehicles"].append({"id": "V2", "available_s": 0, "seats": 6})
        self.assertEqual(run_case(c)["status"], "INVALID_INPUT")

    def test_capacity(self):
        c = load("normal")
        c["groups"][1]["people"] = 7
        r = run_case(c)
        self.assertEqual(r["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertIn("CAPACITY", r["reason_codes"])

    def test_destination_window_and_early_arrival(self):
        c = load("horizon_boundary")
        c["horizon_s"] = 40
        c["destination_window"] = [20, 40]
        r = run_case(c)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        t = r["trips"][0]
        self.assertEqual(t["arrival_s"], 20)  # cannot arrive at 9 and wait at the destination
        self.assertEqual(t["edges"][-1]["entry_s"], 15)
        # hold is placed at the facility before boarding, with the window as the binding cause
        self.assertEqual(t["waits"][0]["phase"], "before_boarding")
        self.assertEqual(t["waits"][0]["causes"][0]["code"], "DESTINATION_NOT_OPEN")

    def test_unresolved_on_cap(self):
        r = run_case(load("normal"), max_labels=1)
        self.assertEqual(r["status"], "UNRESOLVED")
        self.assertIn("SEARCH_CAP", r["reason_codes"])
        self.assertIsNone(r["final_unload_s"])
        r = run_case(load("no_route"), max_labels=1)
        self.assertEqual(r["status"], "UNRESOLVED")  # a cap is never a no-route proof

    def test_checked_route_reports_unknown_that_could_help(self):
        c = load("delayed")
        c["edges"][0]["closed"] = []
        c["edges"][0]["unknown"] = [[10, 30]]
        r = run_case(c)
        self.assertEqual(r["status"], "CHECKED_ROUTE")
        self.assertEqual(r["final_unload_s"], 25)
        self.assertEqual(r["optimistic_final_unload_s"], 21)
        self.assertTrue(r["missing_information"])
        self.assertEqual(r["missing_information"][0]["needed_for"], "EARLIER_COMPLETION_IF_OPEN")

    def test_invalid_inputs(self):
        for mutate in (lambda c: c.update(schema_version=2), lambda c: c.pop("edges"),
                       lambda c: c["edges"][0].update(travel_s=0), lambda c: c["edges"][0].update(travel_s=1.5),
                       lambda c: c.update(destination="A"), lambda c: c.update(mode="convoy"),
                       lambda c: c["forbidden_turns"].append(["e1", "nope"]), lambda c: c.update(groups=[]),
                       lambda c: c["edges"].append(dict(c["edges"][0]))):
            c = load("normal")
            mutate(c)
            self.assertEqual(run_case(c)["status"], "INVALID_INPUT")


# --------------------------------------------------------------------------------------------------------------------
def random_case(rng, k):
    n = rng.randint(2, 5)
    nodes = ["N%d" % i for i in range(n)]
    H = rng.randint(8, 45)
    edges = []
    for j in range(rng.randint(1, 10)):
        u, v = rng.sample(nodes, 2)
        if j < 3 and rng.random() < 0.6:  # bias toward origin->...->destination and return connectivity
            u, v = [(nodes[0], nodes[1]), (nodes[1], nodes[0]), (nodes[0], nodes[-1])][j]

        def ivs():
            out = []
            for _ in range(rng.choice((0, 0, 1, 1, 2))):
                a = rng.randint(0, H)
                out.append([a, min(H + 5, a + rng.randint(0, 15))])
            return out
        edges.append({"id": "e%d" % j, "u": u, "v": v, "travel_s": rng.randint(1, 5), "closed": ivs(),
                      "unknown": ivs()})
    turns = []
    for _ in range(rng.randint(0, 3)):
        a, b = rng.choice(edges), rng.choice(edges)
        if a["v"] == b["u"]:
            turns.append([a["id"], b["id"]])
    mode = rng.choice(("parallel", "shuttle"))
    ng = rng.randint(1, 3)
    groups = [{"id": "G%d" % i, "people": rng.randint(1, 7)} for i in range(ng)]
    nv = 1 if mode == "shuttle" else rng.choice((ng, ng, max(1, ng - 1), ng + 1))
    vehicles = [{"id": "V%d" % i, "available_s": rng.randint(0, 10), "seats": rng.randint(5, 7)} for i in range(nv)]
    wlo = rng.choice((0, 0, rng.randint(0, H)))
    whi = rng.choice((H, H + 5, rng.randint(wlo, H + 5)))
    return {"schema_version": 1, "case_id": "rand-%d" % k, "horizon_s": H, "origin": nodes[0],
            "destination": nodes[1], "edges": edges, "vehicles": vehicles, "groups": groups,
            "board_s": rng.randint(0, 3), "unload_s": rng.randint(0, 3), "destination_window": [wlo, whi],
            "forbidden_turns": turns, "mode": mode}


class OracleEquivalence(unittest.TestCase):
    def test_random_cases_match_bruteforce_and_replay(self):
        rng = random.Random(20261111)
        counts = {}
        for k in range(N_RANDOM):
            c = random_case(rng, k)
            r = run_case(copy.deepcopy(c))
            o = oracle.solve(c)
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            msg = json.dumps(c)
            self.assertNotIn("gated_from_status", r, msg)
            self.assertEqual(r["status"], o["status"], msg)
            self.assertEqual(r["final_unload_s"], o["final"], msg)
            self.assertEqual(r["people_with_checked_transport"], o["people_checked"], msg)
            if r["status"] == "MISSING_INPUT":
                self.assertEqual(r["conditional_final_unload_s"], o["conditional_final"], msg)
            self.assertEqual(r["verification"]["independent_replay"]["violations"], [], msg)
            self.assertTrue(r["verification"]["wfg_sipp"].get("all_ok", True), msg)
        for s in ("CHECKED_ROUTE", "MISSING_INPUT", "MODEL_SCOPED_NO_ROUTE"):
            self.assertGreater(counts.get(s, 0), N_RANDOM // 50, counts)
        print("\nrandom status counts:", counts, file=sys.stderr)


class ReplayMutations(unittest.TestCase):
    """Each rule of the independent replay is detected by an isolated mutation of a valid witness."""

    def base(self):
        c = load("shuttle")
        r = run_case(copy.deepcopy(c))
        self.assertEqual(R.replay(c, r), [])
        return c, r

    def rules(self, c, r):
        return {v["rule"] for v in R.replay(c, r)}

    def test_mutations(self):
        cases = {
            "R-DURATION": lambda c, r: r["trips"][0]["edges"][0].update(exit_s=r["trips"][0]["edges"][0]["exit_s"] + 1),
            "R-CLOSED": lambda c, r: c["edges"][0].update(closed=[[0, 2]]),
            "R-UNKNOWN": lambda c, r: c["edges"][0].update(unknown=[[1, 2]]),
            "R-TURN": lambda c, r: c["forbidden_turns"].append(["e1", "e2"]),
            "R-CAPACITY": lambda c, r: c["vehicles"][0].update(seats=5),
            "R-BOARD": lambda c, r: r["trips"][0].update(boarding_start_s=-1),
            "R-WINDOW": lambda c, r: c.update(destination_window=[9, 60]),
            "R-HORIZON": lambda c, r: c.update(horizon_s=27),
            "R-CONTINUITY": lambda c, r: r["trips"][2].update(ready_s=r["trips"][2]["ready_s"] - 1),
            "R-CONTIG": lambda c, r: r["trips"][0].update(departure_s=0),
            "R-EDGE": lambda c, r: r["trips"][1]["edges"].pop(),
            "R-COVERAGE": lambda c, r: r.update(people_with_checked_transport=13),
            "R-STATUS": lambda c, r: r.update(final_unload_s=27),
            "R-ASSIGN": lambda c, r: c["groups"].reverse(),
            "R-SCHEMA": lambda c, r: r.pop("missing_information"),
        }
        for rule, mut in cases.items():
            c, r = self.base()
            mut(c, r)
            self.assertIn(rule, self.rules(c, r), rule)

    def test_turn_carried_between_legs(self):
        c, r = self.base()
        c["forbidden_turns"].append(["e8", "e1"])  # return arrives on e8; next outbound starts with e1
        self.assertIn("R-TURN", self.rules(c, r))

    def test_teleport_and_extra_vehicle(self):
        c, r = self.base()
        r["trips"][2]["vehicle_id"] = "V9"
        self.assertIn("R-ASSIGN", self.rules(c, r))
        c, r = self.base()
        r["trips"][1]["incoming_edge_at_start"] = "e5"
        self.assertIn("R-CONTINUITY", self.rules(c, r))


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "cli.py"), *args], capture_output=True, text=True,
                              cwd=tempfile.gettempdir(), timeout=120)

    def test_cli_absolute_paths_atomic_output(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "nested" / "result.json"
            p = self.run_cli("--case", str(FIX / "shuttle.json"), "--output", str(out))
            self.assertEqual(p.returncode, 0, p.stderr)
            r = json.loads(out.read_text())
            self.assertEqual(r["status"], "CHECKED_ROUTE")
            self.assertEqual(sorted(os.listdir(out.parent)), ["result.json"])  # no temp files left

    def test_cli_invalid_and_cap(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text("{not json")
            p = self.run_cli("--case", str(bad), "--output", str(Path(d) / "o.json"))
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads((Path(d) / "o.json").read_text())["status"], "INVALID_INPUT")
            p = self.run_cli("--case", str(FIX / "normal.json"), "--output", str(Path(d) / "c.json"),
                             "--max-labels", "1")
            self.assertEqual(p.returncode, 0)
            self.assertEqual(json.loads((Path(d) / "c.json").read_text())["status"], "UNRESOLVED")

    def test_sample_output_is_current(self):
        sample = json.loads((ROOT / "examples" / "sample_result_shuttle.json").read_text())
        fresh = run_case(load("shuttle"))
        for k in ("status", "final_unload_s", "trips", "people_with_checked_transport"):
            self.assertEqual(sample[k], fresh[k], k)


if __name__ == "__main__":
    unittest.main()


class ReviewRegressions(unittest.TestCase):
    """Regressions for issues confirmed by the adversarial review (see MEASUREMENTS.md)."""

    def test_gate_resets_all_coverage_fields(self):
        from unittest import mock
        from kcf_planner import planner
        real = planner.solve_case

        def broken(case, **kw):
            r = real(case, **kw)
            r["trips"][0]["edges"][0]["exit_s"] += 1
            return r
        with mock.patch.object(planner, "solve_case", broken):
            r = run_case(load("delayed"))
        self.assertEqual(r["status"], "UNRESOLVED")
        self.assertEqual(r["gated_from_status"], "CHECKED_ROUTE")
        self.assertEqual((r["groups_with_checked_transport"], r["groups_awaiting_checked_transport"],
                          r["people_awaiting_checked_transport"]), ([], ["G1", "G2"], 12))

    def test_replay_rejects_inconsistent_extensions(self):
        c = load("shuttle")
        base = run_case(copy.deepcopy(c))
        muts = [lambda r: r.update(schema_version=99), lambda r: r.update(final_unload_s=28.0),
                lambda r: r["trips"][0].update(ready_s=0.0), lambda r: r.update(groups_with_checked_transport=["X"]),
                lambda r: r.update(people_awaiting_checked_transport=999),
                lambda r: r.update(conditional_trips=[{"garbage": 1}]),
                lambda r: r["missing_information"].append({"kind": "UNKNOWN_EDGE_INTERVAL", "needed_for":
                                                          "ANY_FEASIBLE_SCHEDULE"}),
                lambda r: r.update(reason=None),
                lambda r: (r["trips"][0]["edges"][1].pop("from"), r["trips"][0]["edges"][1].update(to="Z"))]
        for k, m in enumerate(muts):
            r = copy.deepcopy(base)
            m(r)
            self.assertTrue(R.replay(c, r), k)

    def test_missing_input_lists_exactly_the_needed_unknowns(self):
        c = load("normal")
        c["edges"][0]["unknown"] = [[0, 40]]          # e1 unknown for everyone
        c["edges"][2]["closed"] = [[8, 40]]           # e3 [1,7) usable by V1; V2's [3,9) is blocked
        r = run_case(c)
        self.assertEqual(r["status"], "MISSING_INPUT")
        self.assertEqual(r["people_with_checked_transport"], 6)
        self.assertEqual({m["vehicle_id"] for m in r["missing_information"]}, {"V2"})
        v1 = [t for t in r["conditional_trips"] if t["vehicle_id"] == "V1"][0]
        self.assertFalse(v1["uses_unknown_input"])
        self.assertEqual(R.replay(c, r), [])

    def test_capped_diagnostics_never_invent_a_cause(self):
        c = load("no_route")
        from kcf_planner import planner
        from kcf_planner.model import parse_case as pc
        from unittest import mock
        from kcf_planner import solver as S
        real = S.plan

        def capped(case, view, budget, **kw):
            if view == "topology" or kw.get("horizon") is not None:
                raise S.CapReached("forced cap in diagnostics")
            return real(case, view, budget, **kw)
        with mock.patch.object(S, "plan", capped):
            r = planner.solve_case(pc(c))
        self.assertEqual(r["status"], "MODEL_SCOPED_NO_ROUTE")
        self.assertNotIn("NO_PATH_IN_ROAD_MODEL", r["reason_codes"])
        self.assertIn("DIAGNOSTICS_INCOMPLETE", r["reason_codes"])


class ZeroLengthIntervals(unittest.TestCase):
    def test_zero_length_unknown_never_reported_as_touched(self):
        c = {"schema_version": 1, "case_id": "rand-5296", "horizon_s": 21, "origin": "N0", "destination": "N1", "edges": [{"id": "e0", "u": "N2", "v": "N0", "travel_s": 5, "closed": [[2, 11]], "unknown": [[13, 26], [3, 13]]}, {"id": "e1", "u": "N3", "v": "N0", "travel_s": 5, "closed": [], "unknown": [[3, 3]]}, {"id": "e2", "u": "N0", "v": "N3", "travel_s": 4, "closed": [[0, 0]], "unknown": [[20, 26]]}, {"id": "e3", "u": "N0", "v": "N3", "travel_s": 5, "closed": [[8, 15], [15, 26]], "unknown": []}, {"id": "e4", "u": "N1", "v": "N3", "travel_s": 4, "closed": [], "unknown": [[10, 10]]}, {"id": "e5", "u": "N0", "v": "N2", "travel_s": 2, "closed": [[20, 26]], "unknown": [[13, 13]]}, {"id": "e6", "u": "N3", "v": "N0", "travel_s": 1, "closed": [], "unknown": [[11, 12]]}, {"id": "e7", "u": "N3", "v": "N0", "travel_s": 2, "closed": [], "unknown": [[8, 19]]}, {"id": "e8", "u": "N0", "v": "N1", "travel_s": 1, "closed": [], "unknown": [[20, 26]]}], "vehicles": [{"id": "V0", "available_s": 5, "seats": 7}], "groups": [{"id": "G0", "people": 7}, {"id": "G1", "people": 3}, {"id": "G2", "people": 7}], "board_s": 0, "unload_s": 1, "destination_window": [0, 21], "forbidden_turns": [["e1", "e8"]], "mode": "shuttle"}  # noqa: E501
        r = run_case(c)
        self.assertEqual(r["status"], "MISSING_INPUT")
        self.assertNotIn("gated_from_status", r)
        self.assertFalse(any(m["unknown_interval"][0] == m["unknown_interval"][1] for m in r["missing_information"]))
