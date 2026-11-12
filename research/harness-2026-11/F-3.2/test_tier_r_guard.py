"""Tier R FIRMS-coverage guard (orchestrator, 2026-11-12): no Tier R label may rest on missing FIRMS data.

Run: PYTHONPATH=experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src \\
     python3 research/harness-2026-11/F-3.2/test_tier_r_guard.py   (the directory name is not a module path)
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tier_r as TR  # noqa: E402

KFS_02 = TR.EVENT_DAYS["KFS_02"]          # 2022-03-03 .. 2022-03-14


def write_firms(d, dates):
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "firms.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["latitude", "longitude", "acq_date"])
        w.writeheader()
        for x in dates:
            w.writerow({"latitude": "37.0", "longitude": "129.3", "acq_date": x})


class Coverage(unittest.TestCase):
    def test_window_spanned(self):
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t), ["2022-03-01", "2022-03-08", "2022-03-20"])
            self.assertTrue(TR.firms_coverage([t], KFS_02)["covered"])

    def test_first_run_situation_2025_files_only(self):
        # the first Tier R run had only 2025 FIRMS: the 2022 event must NOT count as covered
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t), ["2025-03-21", "2025-04-01"])
            self.assertFalse(TR.firms_coverage([t], KFS_02)["covered"])

    def test_ends_a_day_early_or_starts_a_day_late(self):
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t), ["2022-03-01", "2022-03-13"])
            self.assertFalse(TR.firms_coverage([t], KFS_02)["covered"])
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t), ["2022-03-04", "2022-03-20"])
            self.assertFalse(TR.firms_coverage([t], KFS_02)["covered"])

    def test_empty_or_missing(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertFalse(TR.firms_coverage([t], KFS_02)["covered"])
            write_firms(Path(t), [])
            self.assertFalse(TR.firms_coverage([t], KFS_02)["covered"])

    def test_a_gap_between_files_is_not_coverage(self):
        # a 2022 file and a 2025 file together span 2023, but say nothing about it
        days_2023 = TR.EVENT_DAYS["KFS_05"]
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t) / "a", ["2022-01-01", "2022-12-31"])
            write_firms(Path(t) / "b", ["2025-01-01", "2025-12-31"])
            self.assertFalse(TR.firms_coverage([Path(t) / "a", Path(t) / "b"], days_2023)["covered"])
            write_firms(Path(t) / "c", ["2023-01-01", "2023-12-31"])
            self.assertTrue(TR.firms_coverage([Path(t) / "a", Path(t) / "b", Path(t) / "c"], days_2023)["covered"])

    def test_two_files_meeting_inside_the_window_are_not_coverage(self):
        with tempfile.TemporaryDirectory() as t:
            write_firms(Path(t) / "a", ["2022-03-01", "2022-03-08"])
            write_firms(Path(t) / "b", ["2022-03-08", "2022-03-20"])
            self.assertFalse(TR.firms_coverage([Path(t) / "a", Path(t) / "b"], KFS_02)["covered"])


class Labels(unittest.TestCase):
    def test_tier_r_without_coverage_is_never_checked_or_unresolved(self):
        for tier in ("R1.5", "R8.2"):
            self.assertEqual(TR.tier_label(tier, "ROUTE", True, False, False), "not_labelled_no_firms")
            self.assertEqual(TR.tier_label(tier, "NO_ROUTE", True, False, False), "not_labelled_no_firms")

    def test_no_route_stands_without_coverage(self):
        # optimistic-instance proof: independent of FIRMS
        self.assertEqual(TR.tier_label("R1.5", "NO_ROUTE", True, True, False), "no_route")

    def test_tier_a_needs_no_firms(self):
        self.assertEqual(TR.tier_label("A", "ROUTE", True, False, False), "checked")
        self.assertEqual(TR.tier_label("A", "NO_ROUTE", True, False, False), "unresolved")

    def test_with_coverage_unchanged(self):
        self.assertEqual(TR.tier_label("R1.5", "ROUTE", True, False, True), "checked")
        self.assertEqual(TR.tier_label("R1.5", "NO_ROUTE", True, False, True), "unresolved")
        self.assertEqual(TR.tier_label("R8.2", "NO_ROUTE", True, True, True), "no_route")
        self.assertEqual(TR.tier_label("R8.2", "ROUTE", False, False, True), "unresolved")   # rejected certificate


if __name__ == "__main__":
    unittest.main()
