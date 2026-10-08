import json
from pathlib import Path
import unittest
from copy import deepcopy

from routing.fallback import checked_return
from routing.session import RoutingSession
from routing.replay import replay


def fixture():
    return json.loads((Path(__file__).parents[1] / "fixtures" / "example.json").read_text())


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture()
        self.g, self.h, self.r = (self.f[k] for k in ("graph", "hazard", "request"))

    def session(self):
        s = RoutingSession(self.g)
        self.assertEqual(s.accept_update(self.h, self.r["as_of"])["status"], "ACCEPTED_UPDATE")
        return s

    def at_a(self):
        self.r.update(position={"node": "A"}, incoming_edge="OA", departure=2,
                      incurred={"m0": 2, "m1": 4}, return_endpoint={"node": "O", "dwell": 0, "open_intervals": [[0, 30]]})
        return [{"edge": "OA", "from_fraction": 0, "to_fraction": 1}]

    def test_return_rechecks_current_time_and_history_dose(self):
        result = checked_return(self.g, self.h, self.r, self.at_a(), "O", dwell=2)
        self.assertEqual(result["status"], "CHECKED_ROUTE")
        self.assertEqual(result["arrival"], 4)
        self.assertEqual(result["per_member"]["m1"]["dose"], 8)
        self.assertEqual(result["legs"][0]["edge"], "AO")

    def test_return_dwell_including_dose(self):
        history = self.at_a()
        self.r["exposure_scope"] = "including_dwell"
        result = checked_return(self.g, self.h, self.r, history, "O", dwell=2)
        self.assertEqual(result["per_member"]["m1"]["dose"], 12)

    def test_undeclared_return_dwell_refused(self):
        history = self.at_a()
        self.r.pop("return_endpoint")
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O", dwell=2)["reason"], "RETURN_DWELL_REQUIRES_ENDPOINT_CONDITIONS")
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O")["status"], "CHECKED_ROUTE")

    def test_return_preserves_declared_opening_and_dwell(self):
        history = self.at_a()
        self.r["destinations"] = [{"node": "O", "dwell": 3, "open_intervals": [[0, 6]]}]
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O", dwell=0)["status"], "UNSUPPORTED")

    def test_return_forbidden_turn_refusal_not_infeasible(self):
        history = self.at_a()
        self.g["forbidden_turns"] = [["OA", "AO"]]
        result = checked_return(self.g, self.h, self.r, history, "O")
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("ROUTE_STRUCTURE", result["codes"])

    def test_return_missing_support(self):
        history = self.at_a()
        self.h["members"][0]["support"][0][0] = False
        result = checked_return(self.g, self.h, self.r, history, "O")
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("MISSING_SUPPORT", result["codes"])

    def test_return_dwell_future_flame_refused(self):
        history = self.at_a()
        m = self.h["members"][0]
        m["breakpoints"] = [0, 5, 30]
        for channel in ("flux", "flame", "support"):
            m[channel].append(deepcopy(m[channel][0]))
        m["flame"][1][0] = True
        result = checked_return(self.g, self.h, self.r, history, "O", dwell=2)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("FLAME_CONTACT", result["codes"])

    def test_mid_edge_reversal_requires_permission_and_matching_history(self):
        self.r.update(position={"edge": "OA", "fraction": .5}, incoming_edge="OA", departure=1,
                      incurred={"m0": 1, "m1": 2})
        history = [{"edge": "OA", "from_fraction": 0, "to_fraction": .5}]
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O")["reason"], "MID_EDGE_REVERSAL_NOT_PERMITTED")
        self.g["mid_edge_reversal"] = True
        result = checked_return(self.g, self.h, self.r, history, "O")
        self.assertEqual(result["status"], "CHECKED_ROUTE")
        self.assertEqual(result["legs"][0]["from_fraction"], .5)
        self.assertEqual(result["arrival"], 2)
        self.g["forbidden_turns"] = [["OA", "AO"]]
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O")["status"], "UNSUPPORTED")

    def test_missing_reverse_no_substitute(self):
        history = self.at_a()
        for edge in self.g["edges"]:
            if edge["id"] in ("OA", "AO"):
                edge.pop("reverse_edge")
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O")["reason"], "DIRECTED_REVERSE_EDGE_UNAVAILABLE")

    def test_history_mismatch_and_endpoint_not_on_path(self):
        history = self.at_a()
        self.r.pop("return_endpoint")
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "B")["status"], "UNSUPPORTED")
        self.r["position"] = {"node": "D"}
        self.assertEqual(checked_return(self.g, self.h, self.r, history, "O")["status"], "INVALID_INPUT")

    def test_session_version_and_generation_stale_completions(self):
        s = self.session()
        first = s.plan(self.r)
        second = s.plan(self.r)
        self.assertFalse(s.commit(first))
        self.assertTrue(s.commit(second))
        newer = deepcopy(self.h)
        newer["version"] = 2
        self.assertEqual(s.accept_update(newer, self.r["as_of"])["status"], "ACCEPTED_UPDATE")
        self.assertFalse(s.commit(second))
        self.assertEqual(s.retained_plan()["hazard_version"], 2)

    def test_stale_and_rejected_updates_explicit_retained_version(self):
        s = self.session()
        result = s.plan(self.r)
        self.assertTrue(s.commit(result))
        self.assertEqual(s.accept_update(self.h, self.r["as_of"])["status"], "STALE_UPDATE")
        self.assertFalse(s.commit(result))
        self.assertEqual(s.retained_plan()["guidance_version_label"], "OLDER_ACCEPTED_VERSION")
        invalid = deepcopy(self.h)
        invalid["schema"] = "wrong"
        self.assertEqual(s.accept_update(invalid, self.r["as_of"])["status"], "REJECTED_UPDATE")
        self.assertEqual(s.retained_plan()["update_status"]["status"], "REJECTED_UPDATE")

    def test_time_origin_change_requires_reset(self):
        s = self.session()
        h = deepcopy(self.h)
        h["version"] = 2
        h["time_origin"] = "2026-10-04T01:00:00+08:00"
        self.assertEqual(s.accept_update(h, self.r["as_of"])["reason"], "TIME_ORIGIN_CHANGE_REQUIRES_RESET")

    def test_retained_always_checked_against_new_hazard(self):
        s = self.session()
        self.assertTrue(s.commit(s.plan(self.r)))
        h = deepcopy(self.h)
        h["version"] = 2
        h["members"][0]["flame"][0][1] = True
        s.accept_update(h, self.r["as_of"])
        self.assertEqual(s.retained_plan()["status"], "UNSUPPORTED")

    def test_progress_incurrence_time_history_and_teleport_regression(self):
        s = self.session()
        s.plan(self.r)
        self.assertEqual(s.set_progress({"node": "D"}, "AD", 4, {"m0": 4, "m1": 8}, [])["status"], "INVALID_INPUT")
        history = self.at_a()
        self.assertEqual(s.set_progress(self.r["position"], "OA", 2, self.r["incurred"], history)["status"], "PROGRESS_ACCEPTED")
        self.assertEqual(s.set_progress({"node": "A"}, "OA", 1, self.r["incurred"], history)["reason"], "PROGRESS_TIME_REGRESSION")
        self.assertEqual(s.set_progress({"node": "A"}, "OA", 3, {"m0": 0, "m1": 0}, history)["reason"], "INCURRED_DOSE_REGRESSION")
        stale_request = deepcopy(self.f["request"])
        stale_request.update(position={"node": "O"}, incoming_edge=None, departure=0, incurred={"m0": 0, "m1": 0})
        result = s.plan(stale_request)
        self.assertEqual(result["request"]["position"], {"node": "A"})
        self.assertEqual(result["request"]["incurred"]["m1"], 4)

    def test_identity_change_requires_explicit_conservative_mapping(self):
        s = self.session()
        history = self.at_a()
        s.set_progress(self.r["position"], "OA", 2, self.r["incurred"], history)
        h = deepcopy(self.h)
        h["version"] = 2
        h["members"][1]["id"] = "new"
        self.assertEqual(s.accept_update(h, self.r["as_of"])["status"], "UNSUPPORTED")
        self.assertEqual(s.hazard["version"], 1)
        self.assertEqual(s.accept_update(h, self.r["as_of"], {"m0": 2, "new": 4})["status"], "UNSUPPORTED")
        self.assertEqual(s.accept_update(h, self.r["as_of"], {"m0": 4, "new": 4})["status"], "ACCEPTED_UPDATE")
        self.assertEqual(s.progress["incurred"], {"m0": 4, "new": 4})

    def test_reset_clears_state_and_invalidates_async(self):
        s = self.session()
        result = s.plan(self.r)
        s.commit(result)
        self.assertEqual(s.reset()["status"], "RESET")
        self.assertFalse(s.commit(result))
        self.assertEqual(s.retained_plan()["reason"], "NO_RETAINED_PLAN")

    def test_deterministic_fixture_replay(self):
        self.assertEqual(replay(self.f), replay(self.f))
        result = replay(self.f)
        self.assertEqual(result["evidence_class"], "LABELLED_FIXTURE")
        self.assertNotIn("wall_s", result["result"]["metrics"])


if __name__ == "__main__":
    unittest.main()
