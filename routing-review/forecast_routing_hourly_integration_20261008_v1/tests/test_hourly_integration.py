"""Integration contract tests; controls are generated, never real-fire proof."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "candidate"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "routing-package"))
from hourly import build_hazard, request_for_hazard, accept_constructed_update, run_pipeline, replay_pipeline, checked_dose_upper
from hazard_constructor import ConstructionConfig
from forecast_bridge import convert, IntegrationError
from routing.core import solve
from routing.independent import check_route
from routing.prepared import prepare_graph
from routing.session import RoutingSession
from routing.validation import validate_request, ValidationError


def generated():
    case = json.loads((ROOT / "routing-package/fixtures/example.json").read_text())
    g = case["graph"]
    arrays = {"new_burn_probability": np.zeros((2, 4)),
              "probability_valid": np.ones((2, 4), bool),
              "source_burned_area": np.zeros((2, 4)),
              "source_burned_area_valid": np.ones((2, 4), bool),
              "affine_transform": np.array([10, 0, 0, 0, -10, 20.])}
    md = {"cutoff_utc": "2022-03-04T03:00:00Z", "shape": [2, 4], "epsg": 5179,
          "affine_transform": arrays["affine_transform"].tolist(),
          "known_probability_cells": 8, "unknown_probability_cells": 0,
          "complete_expected_flux_available": False,
          "initial_active_burning_probability_supplied": False,
          "finite_expected_flux_cells": 0, "evidence": "GENERATED_CONTROL"}
    return case, arrays, md


class HourlyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case, self.arrays, self.md = generated()
        self.g = self.case["graph"]
        self.h, self.c, self.nmd = build_hazard(self.g, self.arrays, self.md,
                                               mode="research", parent_sha256="a" * 64)
        self.req = request_for_hazard(self.case["request"], self.h)

    def test_strict_launch_retains_unknown_required_information(self):
        h, c, md = build_hazard(self.g, self.arrays, self.md, mode="strict")
        self.assertEqual(md["assumption_id"], "strict-original-support-v1")
        self.assertEqual(c["status"], "UNSUPPORTED")
        self.assertFalse(c["arrays"]["support"].any())
        result = solve(prepare_graph(self.g), h, request_for_hazard(self.case["request"], h))
        self.assertEqual(result["status"], "UNSUPPORTED")

    def test_research_class_and_versioned_support_provenance(self):
        self.assertEqual(self.h["evidence_class"], "RESEARCH_CONSTRUCTION")
        self.assertEqual(self.nmd["schema"], "wfg.forecast.native-intervals/2")
        self.assertEqual(self.nmd["mode"], "research")
        self.assertEqual(self.nmd["original_support"]["finite_expected_flux_cells"], 0)
        self.assertEqual(self.nmd["constructed_support"]["fraction"], 1.)

    def test_v2_rejects_missing_or_mislabelled_assumptions(self):
        members = [{"id": m["id"], **{k: self.c["arrays"][k][i] for k in
                   ("flux_w_m2", "flame_contact", "support")}}
                   for i, m in enumerate(self.h["members"])]
        for field in ("assumption_id", "parent_forecast_sha256", "original_support", "constructed_support"):
            md = deepcopy(self.nmd); del md[field]
            with self.assertRaises(IntegrationError):
                convert(self.g, md, members)
        md = deepcopy(self.nmd); md["evidence_class"] = "MENTOR_FORECAST"
        with self.assertRaises(IntegrationError):
            convert(self.g, md, members)

    def test_same_constructed_hazard_raw_prepared_baseline_equivalence(self):
        raw = solve(self.g, self.h, self.req)
        prepared = solve(prepare_graph(self.g), self.h, self.req)
        keys = ("status", "legs", "arrival", "destination", "per_member", "solver_status")
        for key in keys:
            self.assertEqual(raw.get(key), prepared.get(key))
        self.assertEqual(raw["status"], "CONDITIONAL_OPTIMUM")
        self.assertTrue(check_route(self.g, self.h, self.req, raw["legs"], raw["destination"])["ok"])

    def test_new_version_new_forecast_and_new_assumption_never_reuse_ids(self):
        sets = []
        for version, sha, cfg in [(1, "a" * 64, None), (2, "a" * 64, None),
                                  (1, "b" * 64, None), (1, "a" * 64, replace(ConstructionConfig(), timing="late"))]:
            h, _, _ = build_hazard(self.g, self.arrays, self.md, mode="research",
                                   version=version, config=cfg, parent_sha256=sha)
            ids = set(m["id"] for m in h["members"])
            self.assertTrue(all(not ids & previous for previous in sets))
            sets.append(ids)

    def test_history_max_transfer_and_stale_completions(self):
        session = RoutingSession(self.g, prepare=True)
        self.assertEqual(accept_constructed_update(session, self.h, self.h["available_at"])["status"], "ACCEPTED_UPDATE")
        result = session.plan(self.req)
        self.assertTrue(session.commit(result))
        prior = {m["id"]: i + 1. for i, m in enumerate(self.h["members"])}
        self.assertEqual(session.set_progress(self.req["position"], None, 10, prior, [])["status"], "PROGRESS_ACCEPTED")
        next_h, _, _ = build_hazard(self.g, self.arrays, self.md, mode="research", version=2)
        event = accept_constructed_update(session, next_h, next_h["available_at"])
        self.assertEqual(event["status"], "ACCEPTED_UPDATE")
        self.assertEqual(set(session.progress["incurred"].values()), {4.})
        self.assertFalse(session.commit(result))
        self.assertEqual(accept_constructed_update(session, self.h, self.h["available_at"])["status"], "STALE_UPDATE")

    def test_rational_history_bound_cannot_round_down(self):
        from fractions import Fraction
        self.assertGreaterEqual(Fraction(checked_dose_upper({"dose": 1/3, "dose_exact": "1/3"})), Fraction(1, 3))

    def test_later_cutoff_shift_and_gap_refusal_preserve_exposure(self):
        session = RoutingSession(self.g, prepare=True)
        accept_constructed_update(session, self.h, self.h["available_at"])
        prior = {m["id"]: 2 for m in self.h["members"]}
        session.set_progress(self.req["position"], None, 10, prior, [])
        md = deepcopy(self.md); md["cutoff_utc"] = "2022-03-04T06:00:00Z"
        h, _, _ = build_hazard(self.g, self.arrays, md, mode="research", origin=self.md["cutoff_utc"], version=2)
        self.assertEqual(h["valid_from"], 10800)
        self.assertEqual(h["valid_until"], 14400)
        event = accept_constructed_update(session, h, h["available_at"])
        self.assertEqual(event["reason"], "HISTORY_GAP_REQUIRES_VERIFIED_PROGRESS")
        self.assertEqual(session.progress["incurred"], prior)
        self.assertEqual(session.hazard["version"], 1)

    def test_gap_refusal_invalidates_pending_result_and_labels_old_guidance(self):
        session = RoutingSession(self.g, prepare=True)
        accept_constructed_update(session, self.h, self.h["available_at"])
        result = session.plan(self.req)
        md = deepcopy(self.md); md["cutoff_utc"] = "2022-03-04T06:00:00Z"
        later, _, _ = build_hazard(self.g, self.arrays, md, mode="research", origin=self.md["cutoff_utc"], version=2)
        old_generation = session.generation
        event = accept_constructed_update(session, later, later["available_at"])
        self.assertEqual(event["reason"], "HISTORY_GAP_REQUIRES_VERIFIED_PROGRESS")
        self.assertGreater(session.generation, old_generation)
        self.assertFalse(session.commit(result))
        self.assertEqual(session.last_update["status"], "UNSUPPORTED")
        renewed = session.plan(self.req)
        self.assertEqual(renewed["guidance_version_label"], "OLDER_ACCEPTED_VERSION")

    def test_full_trip_plus_dwell_never_repeats_hourly_horizon(self):
        req = deepcopy(self.req); req["horizon"] = 3601
        with self.assertRaises(ValidationError):
            validate_request(self.g, self.h, req)
        req = deepcopy(self.req); req["destinations"][0]["dwell"] = 3600
        req["destinations"][0]["open_intervals"] = [[0, 3600]]; req["horizon"] = 3600
        result = solve(prepare_graph(self.g), self.h, req)
        self.assertNotIn(result["status"], ("CHECKED_ROUTE", "CONDITIONAL_OPTIMUM"))

    def test_graph_reset_clears_dependent_state(self):
        session = RoutingSession(self.g, prepare=True)
        accept_constructed_update(session, self.h, self.h["available_at"])
        session.plan(self.req)
        replacement = deepcopy(self.g); replacement["revision"] += ":new"
        self.assertEqual(session.replace_graph(replacement)["status"], "INVALID_INPUT")
        self.assertEqual(session.replace_graph(replacement, reset=True)["status"], "GRAPH_REPLACED")
        self.assertIsNone(session.hazard); self.assertIsNone(session.progress)

    def test_portable_generated_control_run_and_replay(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            for name, value in [("graph", self.g), ("metadata", self.md), ("request", self.case["request"])]:
                (p / (name + ".json")).write_text(json.dumps(value))
            np.savez_compressed(p / "sample.npz", **self.arrays)
            report = run_pipeline(p / "graph.json", p / "sample.npz", p / "metadata.json", p / "request.json",
                                  mode="research", repeats=2, output_dir=p / "run")
            self.assertEqual(len(report["rows"]), 2)
            self.assertEqual(report["rows"][0]["result"]["status"], "CONDITIONAL_OPTIMUM")
            self.assertGreater(report["memory"]["serialized_hazard_bytes"], 0)
            replay = replay_pipeline(p / "graph.json", p / "sample.npz", p / "metadata.json", p / "request.json")
            self.assertFalse(next(e for e in replay["events"] if e["kind"] == "stale_result")["committed"])
            from replay_with_provenance import enrich_replay
            enriched = enrich_replay(replay, p / "graph.json", p / "sample.npz", p / "metadata.json", ConstructionConfig())
            context = enriched["initial_forecast_context"]
            self.assertEqual(len(context["npz_sha256"]), 64)
            self.assertEqual(context["graph_revision"], self.g["revision"])
            self.assertEqual(context["scenario_count"], 4)
            self.assertEqual(context["assumption_id"], ConstructionConfig().assumption_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
