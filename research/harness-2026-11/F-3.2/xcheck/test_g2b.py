"""G2b rule function and lattice test (no run folders needed). Run: python test_g2b.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from g2b import judge, route_is_integral  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
