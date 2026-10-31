"""Schema: JSON round trips, strict validation of references and values, hazard path resolution."""
import json

import pytest
from pydantic import ValidationError

from evacplan import (
    Budgets, Edge, Instance, InstanceIndex, Node, RoadGraph, Solution, load_instance, load_scenario_set,
    load_solution, save_instance, save_solution, scenario_set_path,
)
from evacplan_testkit import (
    board, drive, facility, grid_graph, instance, itinerary, make_set, nid, path, quiet, shelter, solution, unload,
    vehicle, wait,
)


def small_instance(**kw):
    g = grid_graph(2, 3)
    return instance(g, facilities=[facility("F", nid(0, 0), amb=2, wc=1)], vehicles=[vehicle("V", nid(0, 1))],
                    shelters=[shelter("S", nid(1, 2), windows=((0.0, 100.0), (200.0, 900.0)))], **kw)


def test_instance_and_solution_round_trip(tmp_path):
    inst = small_instance()
    p = save_instance(inst, tmp_path / "inst.json")
    back = load_instance(p)
    assert back == inst
    sol = solution(itinerary("V", drive(path((0, 1), (0, 0)), 0.0), board("F", amb=2), wait(nid(0, 0), 5.0),
                             drive(path((0, 0), (1, 0), (1, 1), (1, 2)), 100.0), unload("S", amb=2)))
    q = save_solution(sol, tmp_path / "sol.json")
    sol2 = load_solution(q)
    assert sol2 == sol
    kinds = [a["kind"] for a in json.loads(q.read_text())["itineraries"][0]["actions"]]
    assert kinds == ["drive", "board", "wait", "drive", "unload"]
    with pytest.raises(FileExistsError):
        save_solution(sol, q)


def test_hazard_folder_resolves_relative_to_the_instance_file(tmp_path):
    inst = small_instance()
    with pytest.raises(ValueError):
        scenario_set_path(inst)                       # no file location yet
    make_set(quiet(2, 3)).write(tmp_path / "case" / "hazard")
    p = save_instance(inst, tmp_path / "case" / "instance.json")
    assert scenario_set_path(load_instance(p)) == (tmp_path / "case" / "hazard").resolve()
    assert load_scenario_set(load_instance(p)).K == 1


def test_rejects_unknown_fields_non_finite_numbers_and_bad_counts():
    inst = small_instance()
    data = json.loads(inst.model_dump_json())
    bad = json.loads(json.dumps(data))
    bad["surprise"] = 1
    with pytest.raises(ValidationError):
        Instance.model_validate(bad)
    with pytest.raises(ValidationError):
        Node(id="a", x=float("inf"), y=0.0)
    with pytest.raises(ValidationError):
        facility("F", "n", amb=-1)
    frac = json.loads(json.dumps(data))
    frac["facilities"][0]["residents"]["ambulatory"] = 2.5
    with pytest.raises(ValidationError):
        Instance.model_validate_json(json.dumps(frac))      # counts are integers (strict)
    whole = json.loads(json.dumps(data))
    whole["facilities"][0]["residents"]["ambulatory"] = 2.0
    with pytest.raises(ValidationError):
        Instance.model_validate_json(json.dumps(whole))
    with pytest.raises(ValidationError):
        Edge(id="e", u="a", v="b", travel_time_s=0.0)       # travel time must be > 0
    with pytest.raises(ValidationError):
        vehicle("V", "n", shift=0.0)


def test_rejects_dangling_references_and_duplicates():
    g = grid_graph(2, 2)
    with pytest.raises(ValidationError):
        instance(g, facilities=[facility("F", "nowhere", amb=1)])
    with pytest.raises(ValidationError):
        instance(g, vehicles=[vehicle("V", nid(0, 0)), vehicle("V", nid(0, 1))])
    with pytest.raises(ValidationError):
        RoadGraph(crs_epsg=3310, nodes=[Node(id="a", x=0, y=0), Node(id="a", x=1, y=1)])
    with pytest.raises(ValidationError):
        RoadGraph(crs_epsg=3310, nodes=[Node(id="a", x=0, y=0)], edges=[Edge(id="e", u="a", v="b", travel_time_s=1)])


def test_forbidden_turns_must_meet_and_exist():
    nodes = [Node(id=k, x=x, y=0.0) for k, x in (("a", 0.0), ("b", 10.0), ("c", 20.0))]
    edges = [Edge(id="ab", u="a", v="b", travel_time_s=1), Edge(id="bc", u="b", v="c", travel_time_s=1),
             Edge(id="ba", u="b", v="a", travel_time_s=1)]
    RoadGraph(crs_epsg=3310, nodes=nodes, edges=edges, forbidden_turns=[("ab", "ba"), ("ab", "bc")])
    with pytest.raises(ValidationError):
        RoadGraph(crs_epsg=3310, nodes=nodes, edges=edges, forbidden_turns=[("bc", "ab")])   # c != a
    with pytest.raises(ValidationError):
        RoadGraph(crs_epsg=3310, nodes=nodes, edges=edges, forbidden_turns=[("ab", "zz")])


def test_edge_geometry_must_join_its_nodes_and_is_snapped():
    nodes = [Node(id="a", x=0.0, y=0.0), Node(id="b", x=100.0, y=0.0)]
    ok = Edge(id="e", u="a", v="b", travel_time_s=5, geometry=[(0.0, 0.0), (50.0, 30.0), (100.0, 1e-7)])
    g = RoadGraph(crs_epsg=3310, nodes=nodes, edges=[ok])
    with pytest.raises(ValidationError):
        RoadGraph(crs_epsg=3310, nodes=nodes,
                  edges=[Edge(id="e", u="a", v="b", travel_time_s=5, geometry=[(0.0, 0.0), (99.0, 0.0)])])
    inst = instance(g)
    geom = InstanceIndex(inst).edge_geometry("e")
    assert geom.tolist() == [[0.0, 0.0], [50.0, 30.0], [100.0, 0.0]]       # end vertex snapped to node b
    chord = InstanceIndex(instance(RoadGraph(crs_epsg=3310, nodes=nodes,
                                             edges=[Edge(id="e", u="a", v="b", travel_time_s=5)])))
    assert chord.edge_geometry("e").tolist() == [[0.0, 0.0], [100.0, 0.0]]  # default: the straight chord


def test_shelter_windows_must_be_sorted_disjoint_and_ordered():
    shelter("S", "n", windows=((0.0, 10.0), (20.0, 30.0)))
    with pytest.raises(ValidationError):
        shelter("S", "n", windows=((0.0, 10.0), (10.0, 30.0)))
    with pytest.raises(ValidationError):
        shelter("S", "n", windows=((5.0, 1.0),))
    with pytest.raises(ValidationError):
        shelter("S", "n", windows=())


def test_budgets_per_member():
    b = Budgets(peak_kw_m2=10.0, dose_kj_m2=[1.0, 2.0])
    peak, dose = b.per_member(2)
    assert peak.tolist() == [10.0, 10.0] and dose.tolist() == [1.0, 2.0]
    with pytest.raises(ValueError):
        b.per_member(3)
    with pytest.raises(ValidationError):
        Budgets(peak_kw_m2=-1.0, dose_kj_m2=1.0)


def test_actions_are_a_discriminated_union():
    s = Solution.model_validate_json(
        '{"itineraries": [{"vehicle": "V", "actions": [{"kind": "wait", "node": "n", "duration_s": 3}]}]}')
    assert s.itineraries[0].actions[0].kind == "wait"
    with pytest.raises(ValidationError):
        Solution.model_validate_json('{"itineraries": [{"vehicle": "V", "actions": [{"kind": "fly"}]}]}')
    with pytest.raises(ValidationError):
        drive([], 0.0)                                  # a drive needs at least one edge
