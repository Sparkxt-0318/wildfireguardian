"""Demo layer: delay outcomes on the fictional fixtures, Korean explanations, offline export."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import demo  # noqa: E402
from kcf_planner import replay  # noqa: E402

EXPECT_TWO = {0: ("CHECKED_ROUTE", 2100), 5: ("CHECKED_ROUTE", 2400), 10: ("CHECKED_ROUTE", 3400),
              15: ("MISSING_INPUT", None), 20: ("MISSING_INPUT", None), 25: ("MODEL_SCOPED_NO_ROUTE", None),
              30: ("MODEL_SCOPED_NO_ROUTE", None)}
EXPECT_SHUTTLE = {0: ("CHECKED_ROUTE", 5000), 5: ("MISSING_INPUT", None), 15: ("MODEL_SCOPED_NO_ROUTE", None)}


class Demo(unittest.TestCase):
    def test_two_vehicle_delays(self):
        for m, (status, final) in EXPECT_TWO.items():
            p = demo.plan("two", m * 60)
            self.assertEqual((p["after"]["status"], p["after"]["final_unload_s"]), (status, final), m)
            self.assertEqual(p["before"]["status"], "CHECKED_ROUTE")
            raw = demo.X.apply_delay(demo.load("two"), 1, m * 60)
            self.assertEqual(replay.replay(raw, p["after"]), [])
            # V1 is never affected by V2's delay
            v1 = [t for t in p["after"]["trips"] if t["vehicle_id"] == "V1"]
            self.assertEqual(v1[0]["unloading_end_s"], 1800)
            self.assertEqual(sum(t["vehicle_id"] == "V2" for t in p["after"]["trips"]), 1 if final else 0)

    def test_ten_minute_story(self):
        p = demo.plan("two", 600)
        c = p["compare"]
        self.assertTrue(c["route_changed"])
        self.assertEqual(c["final_delta_s"], 1300)
        self.assertEqual(c["binding"][0]["code"], "ORIGINAL_ROAD_BLOCKED")
        self.assertEqual(c["binding"][0]["edge_id"], "e_j1_br")
        v2 = p["after"]["trips"][1]
        self.assertEqual((v2["ready_s"], v2["boarding_start_s"], v2["departure_s"], v2["arrival_s"]),
                         (1500, 1500, 1800, 3100))
        self.assertEqual(v2["length_m"], 11600)
        self.assertTrue(any(h["code"] == "TIGHT_MARGIN" for h in p["checks_after"]))
        self.assertTrue(any("열 노출" in h["text_ko"] for h in p["checks_after"]))

    def test_five_minute_zero_margin_is_flagged(self):
        p = demo.plan("two", 300)
        m = [h for h in p["checks_after"] if h["code"] == "TIGHT_MARGIN" and h["edge_id"] == "e_j1_br"]
        self.assertTrue(m and m[0]["margin_s"] == 0)

    def test_distinct_explanations(self):
        self.assertIn("FEASIBLE_ONLY_IF_UNKNOWN_OPEN", demo.plan("two", 900)["after"]["reason_codes"])
        self.assertIn("OUT_OF_HORIZON", demo.plan("two", 1500)["after"]["reason_codes"])
        r30 = demo.plan("two", 1800)["after"]["reason_codes"]
        self.assertNotIn("OUT_OF_HORIZON", r30)
        self.assertIn("DESTINATION_WINDOW", r30)

    def test_shuttle(self):
        for m, (status, final) in EXPECT_SHUTTLE.items():
            p = demo.plan("shuttle", m * 60)
            self.assertEqual((p["after"]["status"], p["after"]["final_unload_s"]), (status, final), m)
            self.assertEqual({t["vehicle_id"] for t in p["after"]["trips"]}, {"V1"})
        kinds = [t["kind"] for t in demo.plan("shuttle", 0)["after"]["trips"]]
        self.assertEqual(kinds, ["outbound", "empty_return", "outbound"])

    def test_text_and_export_offline(self):
        txt = demo.text_report("two", 600)
        self.assertIn("T+56:40", txt)
        self.assertIn("사람이 확인할 부분", txt)
        with tempfile.TemporaryDirectory() as d:
            demo.MAX_DELAY_MIN, old = 2, demo.MAX_DELAY_MIN
            try:
                demo.export(d)
            finally:
                demo.MAX_DELAY_MIN = old
            html = (Path(d) / "kcf_demo.html").read_text(encoding="utf-8")
            self.assertIn('"two|60"', html)
            for bad in ("http://", "https://"):
                self.assertNotIn(bad + "cdn", html)
            self.assertNotIn("<script src", html)
            self.assertNotIn("<link", html)
        self.assertNotIn("/Users/", (ROOT / "web" / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
