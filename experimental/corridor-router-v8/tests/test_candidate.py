"""End-to-end synthetic candidate discovery, including the compiled search."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from discover import find


class CandidateDiscovery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        cfg = {
            "emission_height_m": 3, "receiver_height_m": 1,
            "fuel_load_kg_m2": 1, "consumed_fraction": 1,
            "heat_of_combustion_j_kg": 1000, "radiative_fraction": 0.1,
            "atmospheric_transmissivity": 1, "burning_duration_s": 10,
            "initial_remaining_s": 10,
        }
        metadata = {
            "construction": {"assumptions": cfg, "scenario_ids": ["a", "b", "c", "d"]},
            "affine_transform": [10, 0, 0, 0, -10, 10],
        }
        (self.path / "NATIVE_METADATA.json").write_text(json.dumps(metadata))
        np.savez(self.path / "constructed_arrays.npz",
                 current_active=np.zeros((1, 1), dtype=bool),
                 ignition_time_s=np.full((4, 1, 1), np.inf))
        self.graph = {
            "nodes": [
                {"id": "s", "waitable": True, "x": 100, "y": 100},
                {"id": "a", "waitable": False, "x": 101, "y": 100},
                {"id": "z", "waitable": False, "x": 102, "y": 100},
            ],
            "edges": [
                {"id": "sa", "u": "s", "v": "a", "travel_ticks": 2},
                {"id": "az", "u": "a", "v": "z", "travel_ticks": 2},
            ],
            "forbidden_turns": [],
        }
        self.q = {
            "position": {"node": "s"}, "incoming_edge": None,
            "destinations": [{"node": "z", "dwell": 2, "open_intervals": [[0, 20]]}],
            "departure": 0, "horizon": 20,
            "budgets": {"dose": {m: 1 for m in "abcd"}},
            "incurred": {m: 0 for m in "abcd"},
        }

    def test_returns_direct_route_in_empty_hazard(self):
        route = find(self.graph, self.q, self.path)
        self.assertIsNotNone(route)
        self.assertEqual(route["arrival"], 4)
        self.assertEqual([leg["edge"] for leg in route["legs"]], ["sa", "az"])

    def test_prohibited_turn_has_no_candidate(self):
        self.graph["forbidden_turns"] = [["sa", "az"]]
        self.assertIsNone(find(self.graph, self.q, self.path))

    def test_closed_destination_has_no_candidate(self):
        self.q["destinations"][0]["open_intervals"] = [[0, 5]]
        self.assertIsNone(find(self.graph, self.q, self.path))

    def test_exhausted_budget_cannot_yield_a_candidate(self):
        self.q["incurred"]["a"] = 1
        self.assertIsNone(find(self.graph, self.q, self.path))


if __name__ == "__main__":
    unittest.main()
