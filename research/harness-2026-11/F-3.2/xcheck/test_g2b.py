"""G2b rule function and lattice test (no run folders needed). Run: python test_g2b.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import tempfile
from g2b import decision_of, judge, resolve, route_is_integral, route_of  # noqa: E402

OPT, FEAS, REF = "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN", "CHECKED_JOURNEY_FEASIBLE", "FULL_MODEL_REFUSAL_PROVEN"


class Judge(unittest.TestCase):
    def test_a_arrival_at_or_after_relaxation(self):
        self.assertEqual(judge(OPT, 1922, True, "ROUTE", 1922)[0], "PASS")
        self.assertIn("attains", judge(OPT, 1922, True, "ROUTE", 1922)[1])
        self.assertEqual(judge(FEAS, 2000, True, "ROUTE", 1922)[0], "PASS")

    def test_a_violation_arrival_before_relaxation(self):
        self.assertEqual(judge(OPT, 1921, True, "ROUTE", 1922)[0], "VIOLATION")
        self.assertEqual(judge(FEAS, "3843/2", True, "ROUTE", 1922)[0], "VIOLATION")   # exact rational compare

    def test_b_route_against_relaxation_no_route(self):
        self.assertEqual(judge(FEAS, 2500, True, "NO_ROUTE", 3601)[0], "VIOLATION")

    def test_c_refusal_with_relaxation_route_is_listed(self):
        self.assertEqual(judge(REF, None, True, "ROUTE", 1500)[0], "LISTED")
        self.assertEqual(judge(REF, None, True, "NO_ROUTE", 3601)[0], "PASS")

    def test_noninteger_departure_is_not_applicable_never_violation(self):
        self.assertEqual(judge(OPT, 1000, False, "NO_ROUTE", 3601)[0], "NOT_APPLICABLE_NONINTEGER")
        self.assertEqual(judge(OPT, 1000, False, "ROUTE", 1922)[0], "NOT_APPLICABLE_NONINTEGER")

    def test_other_statuses(self):
        self.assertEqual(judge("UNRESOLVED", None, True, "ROUTE", 10)[0], "NOT_APPLICABLE_STATUS")


class Lattice(unittest.TestCase):
    def test_integral_route(self):
        self.assertTrue(route_is_integral({"departure": 0}, {"legs": [{"start": 0}, {"start": "120"}, {"start": 7}]}))
        self.assertFalse(route_is_integral({"departure": 0}, {"legs": [{"start": "1/2"}]}))
        self.assertFalse(route_is_integral({"departure": "0.2"}, {"legs": []}))
        self.assertFalse(route_is_integral({"departure": 0}, {"legs": [{"start": None}]}))


class V2Format(unittest.TestCase):
    """Facts from Priya's real Step 0 folder: decision inside RESULT.json, Z routes in checked_incumbent, absolute JOB paths."""

    def test_route_of_prefers_primary_then_checked_incumbent(self):
        self.assertEqual(route_of({"destination": "n", "legs": [1]})["legs"], [1])
        self.assertEqual(route_of({"destination": None, "checked_incumbent": {"destination": "m", "arrival": 5}})["arrival"], 5)
        self.assertIsNone(route_of({"destination": None, "checked_incumbent": {"destination": None}}))

    def test_decision_read_from_result_with_incumbent_route(self):
        with tempfile.TemporaryDirectory() as t:
            run = Path(t)
            (run / "RESULT.json").write_text(json.dumps({
                "decision": {"authoritative_status": OPT, "journey": {"arrival": 1459}},
                "result": {"destination": None, "checked_incumbent": {"destination": "d", "arrival": 1459,
                                                                     "legs": [{"kind": "EDGE", "start": 0}]}}}))
            status, j, src = decision_of(run, Path("/nonexistent"))
            self.assertEqual((status, j["arrival"], src), (OPT, 1459, "RESULT.decision"))
            self.assertEqual(j["legs"], [{"kind": "EDGE", "start": 0}])

    def test_resolve_absolute_and_relative(self):
        self.assertEqual(resolve("/kit", "/abs/x.json"), Path("/abs/x.json"))
        self.assertEqual(resolve("/kit", "rel/x.json"), Path("/kit/rel/x.json"))


if __name__ == "__main__":
    unittest.main()
