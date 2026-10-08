import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from wildfireguardian_routing import (example, solve, check_route, prepare_graph,
                                     ReleaseRuntime, BackendTimeout)
from wildfireguardian_routing._engine.independent import exhaustive


class RoutingTests(unittest.TestCase):
    def test_installed_route_and_checker(self):
        c = example()
        r = solve(c["graph"], c["hazard"], c["request"])
        self.assertEqual(r["status"], "CONDITIONAL_OPTIMUM")
        self.assertTrue(check_route(c["graph"], c["hazard"], c["request"], r["legs"], r["destination"])["ok"])

    def test_prepared_equivalence_and_no_input_mutation(self):
        c = example(); before = copy.deepcopy(c)
        raw = solve(c["graph"], c["hazard"], c["request"])
        prepared = solve(prepare_graph(c["graph"]), c["hazard"], c["request"])
        for key in ("status", "arrival", "destination", "legs", "exposure"):
            self.assertEqual(raw.get(key), prepared.get(key))
        self.assertEqual(c, before)

    def test_finite_reference_panel(self):
        cases = json.loads(Path(__file__).with_name("evaluation_cases.json").read_text())["cases"]
        for c in cases:
            with self.subTest(c["id"]):
                r = solve(c["graph"], c["hazard"], c["request"])
                ref = exhaustive(c["graph"], c["hazard"], c["request"])
                # Existing fixture contract distinguishes DISCONNECTED from generic infeasibility.
                normal = lambda s: "INFEASIBLE" if s in {"DISCONNECTED", "PROVEN_INFEASIBLE", "INFEASIBLE"} else s
                self.assertEqual(normal(r["status"]), normal(ref["status"]))
                if "arrival" in ref:
                    self.assertEqual(r.get("arrival"), ref["arrival"])
                if r.get("legs") is not None and r.get("destination") is not None:
                    self.assertTrue(check_route(c["graph"], c["hazard"], c["request"], r["legs"], r["destination"])["ok"])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base/"candidate").mkdir()
        (self.base/"candidate/hourly.py").write_text("")
        self.runtime = ReleaseRuntime(self.base)

    def test_missing_release_rejected(self):
        with self.assertRaises(FileNotFoundError): ReleaseRuntime(self.base/"missing")

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError): self.runtime.run_hourly(self.base/"out", mode="guess")
        self.assertFalse((self.base/"out").exists())

    def test_no_output_overwrite(self):
        out = self.base/"out"; out.mkdir(); (out/"sentinel").write_text("keep")
        with self.assertRaises(FileExistsError): self.runtime.run_hourly(out)
        self.assertEqual((out/"sentinel").read_text(), "keep")

    def test_conflicting_native_arguments_rejected(self):
        with self.assertRaises(ValueError): self.runtime.run_hourly(self.base/"out", native=True, snapshot="x")

    def test_invalid_timeout_before_output_creation(self):
        with self.assertRaises(ValueError): self.runtime.run_hourly(self.base/"out", process_timeout_s=0)
        self.assertFalse((self.base/"out").exists())

    def test_process_timeout_stays_unresolved(self):
        with patch("wildfireguardian_routing.runtime.subprocess.run", side_effect=subprocess.TimeoutExpired("backend", 1)):
            with self.assertRaises(BackendTimeout): self.runtime.run_hourly(self.base/"out", process_timeout_s=1)

    def test_checker_exact_json_encoding(self):
        from wildfireguardian_routing._checker_worker import json_exact
        self.assertEqual(json.dumps({"time": Fraction(3,8)}, default=json_exact), '{"time": "3/8"}')

    def test_checker_requires_matching_release(self):
        with self.assertRaises(FileNotFoundError): self.runtime.check_fixed_route(self.base, {}, {}, [], "D")


if __name__ == "__main__": unittest.main()
