"""Hand-computed checks of the contact engine on a 4 x 3 toy lattice (100 m cells, origin 0,0).

Router cell index = row * 4 + col with rows counted from the south. Node A (50,150) lies in cell 4, B (250,150) in
cell 6, C (350,150) in cell 7. Edge A->B (20 ticks) runs along y = 150 and crosses x = 100 at z = 1/4 and x = 200 at
z = 3/4, so a traversal starting at t spends [t, t+5] in cell 4, [t+5, t+15] in cell 5 and [t+15, t+20] in cell 6.
"""
from fractions import Fraction as F

import pytest

from tools.explain_deadlines.geometry import Grid, chord_cuts, chord_pieces, clip_closed
from tools.explain_deadlines.packet import Packet, PacketError
from tools.explain_deadlines.reach import ContactIndex, earliest_free, flame_avoiding, dwell_free_arrival
from tools.explain_deadlines.replay import build_segments, first_contact, min_contact_shift, segment_contact
from tools.explain_deadlines.roads import RoadGraph

from . import synth

G = Grid(0, 0, 100, 4, 3)
A, B, C = (F(50), F(150)), (F(250), F(150)), (F(350), F(150))


def world(tmp_path, **packet_kw):
    raw = synth.graph({"A": (50, 150), "B": (250, 150), "C": (350, 150)},
                      [("AB", "A", "B", 20), ("BC", "B", "C", 10)])
    g = RoadGraph(raw)
    synth.write_packet(tmp_path / "pk", **packet_kw)
    return g, Packet(tmp_path / "pk", g.grid)


def segments(g, pk, depart=0, dwell=120):
    legs = [{"kind": "EDGE", "edge": "AB", "start": depart, "end": depart + 20, "from_fraction": 0, "to_fraction": 1},
            {"kind": "EDGE", "edge": "BC", "start": depart + 20, "end": depart + 30, "from_fraction": 0, "to_fraction": 1}]
    return build_segments(grid=g.grid, packet=pk, xy=g.xy, legs=legs, edges=g.edge, start_node="A", departure=depart,
                          destination="C", dwell=dwell)


# ------------------------------------------------------------------------------------------------ geometry
def test_cell_index_and_rectangles():
    assert G.cell_of(*A) == 4 and G.cell_of(*B) == 6 and G.cell_of(*C) == 7
    assert G.cell_of(F(100), F(150)) == 5          # a point on a grid line belongs to the cell to its right/top
    assert G.rect(5) == (100, 200, 100, 200)
    assert sorted(G.cells_touching_box(F(100), F(100), F(150), F(150))) == [4, 5]


def test_clip_closed_hand_values():
    assert clip_closed(A, B, G.rect(5)) == (F(1, 4), F(3, 4))
    assert clip_closed(A, B, G.rect(4)) == (F(0), F(1, 4))
    assert clip_closed(A, B, G.rect(9)) is None                      # row above: y = 150 is outside [200, 300]
    # a road lying ON the grid line y = 200 touches the closed rectangles of both rows
    p0, p1 = (F(50), F(200)), (F(250), F(200))
    assert clip_closed(p0, p1, G.rect(5)) == (F(1, 4), F(3, 4))
    assert clip_closed(p0, p1, G.rect(9)) == (F(1, 4), F(3, 4))
    # a corner touch is a contact interval of length zero
    assert clip_closed((F(0), F(0)), (F(200), F(200)), G.rect(4)) == (F(1, 2), F(1, 2))


def test_router_pieces_hand_values():
    assert chord_cuts(G, A, B) == [F(0), F(1, 4), F(3, 4), F(1)]
    pieces, points = chord_pieces(G, A, B)
    assert pieces == [(4, F(0), F(1, 4)), (5, F(1, 4), F(3, 4)), (6, F(3, 4), F(1))]
    assert points == [(4, F(0)), (5, F(1, 4)), (6, F(3, 4)), (6, F(1))]


# ------------------------------------------------------------------------------------------------ packet
def test_packet_phases_and_hazard_agree(tmp_path):
    g, pk = world(tmp_path, current=[7], R=3700.0, ignitions={1: {5: 30.0}})
    assert pk.consistency["status"] == "HAZARD_FLAME_EQUALS_NPZ_PHASES"
    assert pk.phases[1][5][:2] == (F(30), F(30) + F(4000))
    assert 5 not in pk.phases[0]
    assert all(pk.phases[s][7][:2] == (F(0), F(3700)) for s in range(4))
    assert pk.member_label(1) == 1


def test_packet_rejects_inconsistent_hazard(tmp_path):
    import json
    synth.write_packet(tmp_path / "pk", ignitions={1: {5: 30.0}})
    hz = json.loads((tmp_path / "pk" / "HAZARD.json").read_text())
    hz["members"][1]["flame"][0][5] = True        # claim cell 5 burns before its ignition
    (tmp_path / "pk" / "HAZARD.json").write_text(json.dumps(hz))
    with pytest.raises(PacketError):
        Packet(tmp_path / "pk", G)


# ------------------------------------------------------------------------------------------------ replay
def test_shifted_route_first_contact_and_slack(tmp_path):
    g, pk = world(tmp_path, ignitions={1: {5: 30.0}})
    segs = segments(g, pk)
    H = F(3600)
    assert first_contact(pk, segs, F(0), H) is None                     # clear at the recorded time
    ab = segs[1]
    assert ab.kind == "EDGE" and ab.edge == "AB"
    assert ab.closed == [(5, 5, 15)]                                    # only burning cells are kept
    assert ab.router == [(5, 5, 15), (5, 5, 5)]                         # open piece + cut point x = 100
    s_star, pair = min_contact_shift(pk, ab, H)
    assert s_star == 15 and pair[0] == 1 and pair[1] == 5               # flame at 30, vehicle leaves cell 5 at 15
    assert first_contact(pk, segs, F(14), H) is None
    fc = first_contact(pk, segs, F(15), H)
    assert fc.segment is ab and fc.members == [1] and fc.pairs[0][2] == 30      # closed occupancy meets [30, ...) at 30
    assert fc.router_members == {1}                                     # router samples 30 in the flame bin
    later = segment_contact(pk, ab, F(600), H)
    assert later.pairs[0][2] == 605                                     # enters the already burning cell at 605


def test_closed_rule_sees_boundary_contact_the_router_rule_does_not(tmp_path):
    raw = synth.graph({"F": (50, 200), "G": (250, 200)}, [("FG", "F", "G", 20)])
    g = RoadGraph(raw)
    synth.write_packet(tmp_path / "pk", current=[5], R=3700.0)
    pk = Packet(tmp_path / "pk", g.grid)
    legs = [{"kind": "EDGE", "edge": "FG", "start": 0, "end": 20, "from_fraction": 0, "to_fraction": 1}]
    segs = build_segments(grid=g.grid, packet=pk, xy=g.xy, legs=legs, edges=g.edge, start_node="F", departure=0,
                          destination="G", dwell=0)
    sc = segment_contact(pk, segs[1], F(0), F(3600))
    assert sc.members == [0, 1, 2, 3] and sc.router_members == set()   # road on the top edge of burning cell 5


def test_destination_stay_contact(tmp_path):
    g, pk = world(tmp_path, ignitions={2: {7: 100.0}})
    segs = segments(g, pk)
    fc = first_contact(pk, segs, F(0), F(3600))
    assert fc.segment.kind == "DWELL" and fc.members == [2] and fc.pairs[0][2] == 100


# ------------------------------------------------------------------------------------------------ relaxation
def test_earliest_free_hand_values():
    blocks = [(F(10), F(20), 0, 0, F(10)), (F(19), F(35), 0, 0, F(19))]
    assert earliest_free(blocks, 5, 100) == 5
    assert earliest_free(blocks, 12, 100) == 35          # [10,20) then [19,35): first free integer is 35
    assert earliest_free(blocks, 12, 34) is None
    assert earliest_free([(F(10), F(41, 2), 0, 0, F(10))], 10, 100) == 21   # ceil of an exclusive non-integer end


def exits_world(tmp_path, blocked_alt: bool):
    nodes = {"S": (50, 50), "M": (150, 50), "T": (350, 50), "N": (50, 250), "P": (350, 250)}
    edges = [("SM", "S", "M", 10), ("MT", "M", "T", 20), ("SN", "S", "N", 20), ("NP", "N", "P", 30), ("PT", "P", "T", 20)]
    g = RoadGraph(synth.graph(nodes, edges))
    synth.write_packet(tmp_path / ("pk%d" % blocked_alt), current=[2] + ([11] if blocked_alt else []), R=3700.0)
    return g, Packet(tmp_path / ("pk%d" % blocked_alt), g.grid)


def test_flame_avoiding_detour_and_window(tmp_path):
    g, pk = exits_world(tmp_path, blocked_alt=False)
    idx = ContactIndex(g, pk)
    assert g.fastest_ticks("S", ["T"])["T"] == 30                       # S-M-T, fire ignored
    run = flame_avoiding(idx, "S", 0, ["T"], 3600)
    assert run["arrival"]["T"] == 70                                    # M-T crosses burning cell 2: detour S-N-P-T
    assert ("MT", 10) in run["frontier"]
    late = flame_avoiding(idx, "S", 0, ["T"], 60)
    assert late["arrival"]["T"] is None and ("PT", 50) in late["horizon_cut"]


def test_flame_avoiding_closed_area(tmp_path):
    g, pk = exits_world(tmp_path, blocked_alt=True)
    run = flame_avoiding(ContactIndex(g, pk), "S", 0, ["T"], 3600, turns=False)
    assert run["arrival"]["T"] is None
    assert run["frontier"] == [("MT", 10), ("NP", 20)] and run["horizon_cut"] == []
    assert run["reached_nodes"] == 3


def test_dwell_free_arrival(tmp_path):
    g, pk = world(tmp_path, ignitions={0: {7: 500.0}})
    idx = ContactIndex(g, pk)
    assert dwell_free_arrival(idx, "C", 300, 3480, 120) == 300           # stay [300, 420] ends before 500
    assert dwell_free_arrival(idx, "C", 400, 3480, 120) is None          # every later stay meets the flame
