"""Unit test of X1's cell classification (no packet data needed). Run: python test_x1_classify.py"""
import sys
import unittest
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from x1_packets import classify  # noqa: E402


class Classify(unittest.TestCase):
    def test_categories(self):
        haz = {1: [(F(0), F(10))], 2: [(F(0), F(10) + F(1, 10**9))], 3: [(F(0), F(18000))], 4: [(F(5), F(9))]}
        con = {1: [(F(0), F(10))], 2: [(F(0), F(10))], 3: [(F(0), F(4270))], 5: [(F(1), F(2))]}
        c = classify(haz, con)
        self.assertEqual((c["identical"], c["end_within_1us"], c["other"], c["only_hazard"], c["only_contact"]), (1, 1, 1, 1, 1))

    def test_start_difference_is_never_tolerated(self):
        c = classify({1: [(F(1, 10**9), F(10))]}, {1: [(F(0), F(10))]})
        self.assertEqual(c["other"], 1)


if __name__ == "__main__":
    unittest.main()
