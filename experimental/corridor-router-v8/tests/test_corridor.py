"""Small end-to-end graph controls for corridor search semantics."""
import sys
import time
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from corridors import RoadIndex, SearchGraph, partition
from legal import search


def road_graph(waitable=True, restricted_turn=False):
    return {
        "nodes": [
            {"id": "s", "waitable": waitable},
            {"id": "a", "waitable": False},
            {"id": "z", "waitable": False},
        ],
        "edges": [
            {"id": "sa", "u": "s", "v": "a", "travel_ticks": 2},
            {"id": "az", "u": "a", "v": "z", "travel_ticks": 2},
        ],
        "forbidden_turns": [["sa", "az"]] if restricted_turn else [],
    }


def request(open_intervals=((0, 20),), dwell=2):
    return {
        "position": {"node": "s"},
        "incoming_edge": None,
        "destinations": [{"node": "z", "dwell": dwell, "open_intervals": open_intervals}],
        "departure": 0,
        "horizon": 20,
    }


def execute(graph, blocks, q):
    index = RoadIndex(graph)
    parts, _ = partition(index, {"s", "z"})
    compiled = SearchGraph(index, parts)
    forbidden = [blocks.get(index.edges[p[0]]["id"], []) for p in parts]
    return search(compiled, forbidden, {}, q, time.perf_counter() + 5)


class CorridorBehavior(unittest.TestCase):
    def test_waiting_avoids_temporarily_closed_road(self):
        route, stats = execute(road_graph(), {"sa": [(0, 3)]}, request())
        self.assertEqual(route["arrival"], 7)
        self.assertEqual(route["legs"][0], {"kind": "WAIT", "node": "s", "start": 0, "end": 3})
        self.assertEqual([leg["edge"] for leg in route["legs"][1:]], ["sa", "az"])
        self.assertEqual(stats["lower_bound_arrival"], 7)

    def test_forbidden_turn_cannot_be_used(self):
        route, stats = execute(road_graph(restricted_turn=True), {}, request())
        self.assertIsNone(route)
        self.assertTrue(stats["exhausted"])

    def test_cannot_wait_before_closed_destination_and_call_it_arrival(self):
        # Arriving at 4 before opening does not produce a new arrival at 6.
        route, stats = execute(road_graph(waitable=False), {}, request(((6, 12),)))
        self.assertIsNone(route)
        self.assertTrue(stats["exhausted"])

    def test_stay_must_fit_open_window(self):
        route, stats = execute(road_graph(), {}, request(((0, 5),), dwell=2))
        self.assertIsNone(route)
        self.assertTrue(stats["exhausted"])


if __name__ == "__main__":
    unittest.main()
