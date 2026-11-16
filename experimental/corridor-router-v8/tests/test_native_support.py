"""Closed-cell and time-boundary controls for native forecast support."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

PACKAGE = Path(os.environ.get("WFG_SUPPORT_PACKAGE_DIR", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(PACKAGE))

from corridors import RoadIndex, SearchGraph, partition
from legal import search
from native_support import constraints, missing_intervals, route_supported


def make_graph():
    return {
        "grid": {"x0": 0, "y0": 0, "resolution": 10, "width": 3, "height": 3},
        "nodes": [
            {"id": "s", "x": 5, "y": 15, "waitable": False},
            {"id": "a", "x": 5, "y": 25, "waitable": False},
            {"id": "b", "x": 25, "y": 25, "waitable": False},
            {"id": "z", "x": 25, "y": 15, "waitable": False},
        ],
        "edges": [
            {"id": "direct", "u": "s", "v": "z", "travel_ticks": 20, "segments": []},
            {"id": "up", "u": "s", "v": "a", "travel_ticks": 10, "segments": []},
            {"id": "across", "u": "a", "v": "b", "travel_ticks": 20, "segments": []},
            {"id": "down", "u": "b", "v": "z", "travel_ticks": 10, "segments": []},
        ],
        "forbidden_turns": [],
    }


def make_request(horizon=100):
    return {
        "position": {"node": "s"}, "incoming_edge": None,
        "departure": 0, "horizon": horizon,
        "destinations": [{"node": "z", "dwell": 1, "open_intervals": [[0, horizon]]}],
    }


def compile_graph(graph, request):
    index = RoadIndex(graph)
    parts, _ = partition(index, {request["position"]["node"], request["destinations"][0]["node"]})
    return SearchGraph(index, parts)


class SupportMaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.packet = Path(self.tmp.name)
        self.graph = make_graph()

    def tearDown(self):
        self.tmp.cleanup()

    def save_mask(self, mask):
        np.savez(self.packet / "constructed_arrays.npz", native_hourly_valid=mask)

    def test_requires_all_members_and_uses_top_down_rows(self):
        mask = np.ones((1, 4, 3, 3), dtype=np.bool_)
        mask[0, 2, 1, 1] = False
        self.save_mask(mask)
        self.assertEqual(missing_intervals(self.packet, self.graph, 100), {4: [(0, 101)]})

    def test_missing_or_malformed_native_mask_is_not_assumed_valid(self):
        np.savez(self.packet / "constructed_arrays.npz", support=np.ones((4, 3, 3), dtype=bool))
        with self.assertRaises(KeyError):
            missing_intervals(self.packet, self.graph, 100)
        self.save_mask(np.ones((1, 4, 3, 3), dtype=np.int8))
        with self.assertRaisesRegex(ValueError, "INVALID_NATIVE_HOURLY_VALID"):
            missing_intervals(self.packet, self.graph, 100)

    def test_last_native_hour_remains_valid_through_horizon(self):
        mask = np.ones((2, 4, 3, 3), dtype=np.bool_)
        mask[1, 0, 1, 1] = False
        self.save_mask(mask)
        self.assertEqual(missing_intervals(self.packet, self.graph, 7200), {4: [(3600, 7201)]})

    def test_hour_boundary_on_road_uses_closed_cell_contact(self):
        request = make_request(7200)
        compiled = compile_graph(self.graph, request)
        extra, _ = constraints(self.graph, compiled, {4: [(3600, 7201)]}, request, time.perf_counter() + 5)
        direct = next(i for i, part in enumerate(compiled.parts)
                      if compiled.index.edges[part[0]]["id"] == "direct")
        # Direct road intersects the closed missing cell from 1/4 to 3/4.
        self.assertIn((3585, 7196), extra[direct])

    def test_closed_gridline_and_outside_grid_are_blocked(self):
        graph = make_graph()
        graph["nodes"][0].update(x=5, y=10, waitable=True)
        graph["nodes"][-1].update(x=25, y=10)
        graph["edges"] = graph["edges"][:1]
        request = make_request()
        compiled = compile_graph(graph, request)
        extra, points = constraints(graph, compiled, {1: [(0, 101)]}, request, time.perf_counter() + 5)
        self.assertEqual(extra, [[(0, 96)]])
        graph["nodes"][0]["x"] = 0
        extra, points = constraints(graph, compiled, {}, request, time.perf_counter() + 5)
        self.assertEqual(extra, [[(0, 101)]])
        self.assertEqual(points["s"], [(0, 101)])

    def test_supported_detour_is_found(self):
        request = make_request()
        compiled = compile_graph(self.graph, request)
        support, points = constraints(self.graph, compiled, {4: [(0, 101)]}, request, time.perf_counter() + 5)
        route, _ = search(compiled, support, points, request, time.perf_counter() + 5)
        self.assertEqual([leg["edge"] for leg in route["legs"]], ["up", "across", "down"])
        self.assertEqual(route["arrival"], 40)


class RouteSupportTests(unittest.TestCase):
    def setUp(self):
        class World:
            h = w = 2
            valid = np.ones((2, 2, 2), dtype=np.bool_)
            edges = {"road": {"u": "s", "v": "z"}}

            @staticmethod
            def cells(u, v):
                if u == "s" and v == "z":
                    return [(0, 0, 0, 1, True)]
                if u == "z":
                    return [(0, 1, 0, 1, True)]
                return [(1, 0, 0, 1, True)]
        self.world = World()
        self.req = {"position": {"node": "s"}, "destinations": [{"dwell": 20}]}
        self.route = {
            "legs": [
                {"kind": "WAIT", "node": "s", "start": 3580, "end": 3590},
                {"kind": "EDGE", "edge": "road", "start": 3590, "end": 3600},
            ],
            "arrival": 3600,
        }

    def test_wait_movement_and_stay_all_checked_by_hour(self):
        self.assertTrue(route_supported(self.world, self.req, self.route))
        self.world.valid[1, 0, 0] = False
        self.assertFalse(route_supported(self.world, self.req, self.route))
        self.world.valid[1, 0, 0] = True
        self.world.valid[1, 0, 1] = False
        self.assertFalse(route_supported(self.world, self.req, self.route))
        self.world.valid[1, 0, 1] = True
        self.world.valid[0, 1, 0] = False
        self.assertFalse(route_supported(self.world, self.req, self.route))

    def test_out_of_grid_cell_is_not_covered(self):
        self.world.cells = lambda u, v: [(-1, 0, 0, 1, True)]
        self.assertFalse(route_supported(self.world, self.req, self.route))


class WorkerOutcomeTests(unittest.TestCase):
    def test_exhausted_support_restricted_search_stays_unresolved(self):
        # The unrestricted mock graph is reachable. Missing support blocks the
        # strict search; exhaustion therefore cannot prove physical/model absence.
        import update

        graph = make_graph()
        request = make_request()
        request["incurred"] = {"member": 0}
        request["exposure_scope"] = "including_dwell"
        request["as_of"] = 0
        hazard = {"dt": 1, "time_origin": "issue"}
        meta = {"time_origin": "issue", "graph_revision": "r", "crs": "C"}
        graph.update(revision="r", crs="C")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            job = {
                "output_path": str(out), "source_root": str(out / "candidate"),
                "source_directory": str(out / "packet"), "decision_dir": str(out / "decision"),
                "input_sha256": {}, "source_sha256": {}, "checker_sha256": {},
                "phaseB_sha256": {"rda_worker_v1_1.py": "same"}, "core_sha256": "same",
                "graph_path": "graph", "request_path": "request", "hazard_path": "hazard",
                "update_arm": "corridor",
            }
            def fake_read(path):
                key = str(path)
                if key == "job":
                    return job
                if key == "graph":
                    return graph
                if key == "request":
                    return request
                if key == "hazard":
                    return hazard
                if key.endswith("NATIVE_METADATA.json"):
                    return meta
                raise AssertionError(key)

            module = lambda **items: types.SimpleNamespace(**items)
            validation = module(validate_hazard=lambda *a, **k: object(),
                                validate_request=lambda *a, **k: object())
            mods = {
                "adaptive_checker": module(HybridChecker=object),
                "clock_scope": module(check_clock_scope=lambda *a, **k: {"supported": True}),
                "contact_first": module(ContactSources=module(from_case=lambda *a, **k: types.SimpleNamespace(content_sha256="x"))),
                "mission_contract": module(graph_digest=lambda *a: "x"),
                "preparation_mode": module(prepare_graph=lambda *a, **k: module(snapshot=lambda: object())),
                "routing": module(validation=validation),
                "world": module(make_world=lambda *a: object()),
                "native_support": module(
                    route_supported=lambda *a: False,
                    missing_intervals=lambda *a: {},
                    constraints=lambda graph, compiled, *a: ([[(0, 101)]] * len(compiled.parts), {}),
                ),
            }
            with patch.object(update, "read", side_effect=fake_read), \
                 patch.object(update, "sha", return_value="same"), \
                 patch.object(update, "get_contact", return_value=({}, {})), \
                 patch.dict(sys.modules, mods), \
                 patch.object(sys, "argv", ["update.py", "job"]), \
                 patch.dict(os.environ, {"WFG_OUTER_MONOTONIC_START": str(time.perf_counter())}):
                with self.assertRaises(update.StopStrict):
                    update.main()
            result = json.loads((out / "RESULT.json").read_text())
            self.assertEqual(result["decision"]["authoritative_status"], "UNRESOLVED")
            self.assertEqual(result["decision"]["reason"], "SUPPORT_RESTRICTED_SEARCH_NO_ROUTE")
            self.assertEqual(result["result"]["status"], "UNRESOLVED")


class SupportRefinementTests(unittest.TestCase):
    def run_refinement(self, supported, checker_status, via_least_driving=False):
        import update

        graph = make_graph()
        request = make_request()
        request.update(incurred={"member": 0}, exposure_scope="including_dwell", as_of=0)
        graph.update(revision="r", crs="C")
        hazard = {"dt": 1, "time_origin": "issue"}
        meta = {"time_origin": "issue", "graph_revision": "r", "crs": "C"}
        candidate = {
            "arrival": 20, "destination": "z", "_supported": supported,
            "legs": [
                {"kind": "WAIT", "node": "s", "start": 0, "end": 10},
                {"kind": "EDGE", "edge": "short", "start": 10, "end": 20},
            ],
        }
        calls = []
        class Checker:
            def __init__(self, packet):
                pass
            def check(self, graph, req, legs, destination, **kwargs):
                calls.append(legs)
                return {"status": "CERTIFIED_ADMISSIBLE" if len(calls) == 1 else checker_status}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            job = {
                "output_path": str(out), "source_root": str(out / "candidate"),
                "source_directory": str(out / "packet"), "decision_dir": str(out / "decision"),
                "input_sha256": {}, "source_sha256": {}, "checker_sha256": {},
                "phaseB_sha256": {"rda_worker_v1_1.py": "same"}, "core_sha256": "same",
                "graph_path": "graph", "request_path": "request", "hazard_path": "hazard",
                "update_arm": "corridor", "support_policy": "REQUIRE_NATIVE_SUPPORT",
            }
            def fake_read(path):
                key = str(path)
                if key == "job": return job
                if key == "graph": return graph
                if key == "request": return request
                if key == "hazard": return hazard
                if key.endswith("NATIVE_METADATA.json"): return meta
                raise AssertionError(key)
            module = lambda **items: types.SimpleNamespace(**items)
            validation = module(validate_hazard=lambda *a, **k: object(),
                                validate_request=lambda *a, **k: object())
            mods = {
                "adaptive_checker": module(HybridChecker=Checker),
                "clock_scope": module(check_clock_scope=lambda *a, **k: {"supported": True}),
                "contact_first": module(ContactSources=module(from_case=lambda *a, **k: types.SimpleNamespace(content_sha256="x"))),
                "mission_contract": module(graph_digest=lambda *a: "x"),
                "preparation_mode": module(prepare_graph=lambda *a, **k: module(snapshot=lambda: object())),
                "routing": module(validation=validation),
                "world": module(make_world=lambda *a: object()),
                "native_support": module(route_supported=lambda world, req, route: route.get("_supported", True),
                                         constraints=lambda *a: None, missing_intervals=lambda *a: None),
            }
            plans = [] if via_least_driving else [(10, candidate)]
            minimum = ("RELAXED_MINIMUM", candidate, 1) if via_least_driving else ("WORK_LIMIT", None, 0)
            with patch.object(update, "read", side_effect=fake_read), \
                 patch.object(update, "sha", return_value="same"), \
                 patch.object(update, "get_contact", return_value=({}, {})), \
                 patch.object(update, "candidate_plans", return_value=plans), \
                 patch.object(update, "least_driving", return_value=minimum), \
                 patch.dict(sys.modules, mods), \
                 patch.object(sys, "argv", ["update.py", "job"]), \
                 patch.dict(os.environ, {"WFG_OUTER_MONOTONIC_START": str(time.perf_counter())}):
                update.main()
            result = json.loads((out / "RESULT.json").read_text())
            trace = json.loads((out / "TIEBREAK_TRACE.json").read_text())
            return result, trace, calls

    def test_unsupported_refinement_does_not_replace_or_get_checked(self):
        for via_minimum in (False, True):
            with self.subTest(via_minimum=via_minimum):
                result, trace, calls = self.run_refinement(False, "CERTIFIED_ADMISSIBLE", via_minimum)
                self.assertEqual(result["result"]["legs"][0]["edge"], "direct")
                self.assertEqual(len(calls), 1)
                self.assertFalse(trace["minimum_drive_proved"])
                self.assertEqual(result["optimality_certificate"]["scope"], "supported_journeys")

    def test_supported_refinement_requires_full_heat_check(self):
        result, trace, calls = self.run_refinement(True, "UNRESOLVED")
        self.assertEqual(result["result"]["legs"][0]["edge"], "direct")
        self.assertEqual(len(calls), 2)
        self.assertFalse(trace["minimum_drive_proved"])

    def test_supported_and_heat_checked_refinement_is_kept(self):
        result, trace, calls = self.run_refinement(True, "CERTIFIED_ADMISSIBLE")
        self.assertEqual(result["result"]["legs"][1]["edge"], "short")
        self.assertEqual(len(calls), 2)
        self.assertEqual(trace["final_drive_s"], 10)
        self.assertFalse(trace["minimum_drive_proved"])

    def test_checked_relaxed_minimum_proves_minimum_on_supported_domain(self):
        result, trace, calls = self.run_refinement(True, "CERTIFIED_ADMISSIBLE", True)
        self.assertEqual(result["result"]["legs"][1]["edge"], "short")
        self.assertEqual(len(calls), 2)
        self.assertTrue(trace["minimum_drive_proved"])
        self.assertEqual(result["decision"]["authoritative_status"], "CHECKED_JOURNEY_SUPPORTED_OPTIMUM_PROVEN")


if __name__ == "__main__":
    unittest.main()
