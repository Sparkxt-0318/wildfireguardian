"""SYNTHETIC instance generators: determinism, sizes, labels, tightness knobs and the fire's threat.

Seeds here (1-60, 9000+) are outside the frozen split's dev (101-110) and test (201-210) seeds."""
import math

import numpy as np
import pytest

from evacplan import Oracle, Solution, load_instance, load_scenario_set, validate_solution
from evacplan.generators import SIZES, SyntheticConfig, generate, tightness_params
from evacplan.generators.graphs import components, geo_layout, grid_layout, is_connected
from evacplan.generators.synthetic import SPEED_KMH, VEHICLE_TYPES
from evacplan.instances import fingerprint


@pytest.fixture(scope="module")
def gens():
    cache = {}

    def get(size, t, graph, seed):
        key = (size, t, graph, seed)
        if key not in cache:
            cache[key] = generate(SyntheticConfig(size=size, tightness=t, graph=graph, seed=seed))
        return cache[key]
    return get


# ------------------------------------------------------------------------------ determinism
@pytest.mark.parametrize("size,graph", [("S", "grid"), ("S", "geo"), ("M", "geo")])
def test_deterministic_from_config(size, graph):
    cfg = SyntheticConfig(size=size, tightness=0.6, graph=graph, seed=7)
    a, b = generate(cfg), generate(cfg.model_dump())
    assert a.instance == b.instance and a.instance.model_dump_json() == b.instance.model_dump_json()
    for name in ("ignite_s", "extinguish_s", "supported"):
        np.testing.assert_array_equal(getattr(a.hazard, name), getattr(b.hazard, name))
    assert a.hazard.meta == b.hazard.meta and a.fingerprint() == b.fingerprint()
    other = generate(cfg.model_copy(update={"seed": 8}))
    assert other.fingerprint() != a.fingerprint()


def test_files_round_trip_keep_the_fingerprint(tmp_path, gens):
    g = gens("S", 0.75, "geo", 3)
    g.write(tmp_path / "x")
    inst = load_instance(tmp_path / "x" / "instance.json")
    ss = load_scenario_set(inst)
    assert inst == g.instance and fingerprint(inst, ss) == g.fingerprint()
    with pytest.raises(FileExistsError):
        g.write(tmp_path / "x")


# ----------------------------------------------------------------------------- sizes, labels
@pytest.mark.parametrize("size,graph,seed", [("S", "grid", 11), ("S", "geo", 12), ("M", "grid", 13),
                                             ("M", "geo", 14), ("L", "grid", 15)])
@pytest.mark.parametrize("t", [0.0, 0.5, 1.0])
def test_sizes(size, graph, seed, t, gens):
    g = gens(size, t, graph, seed)
    inst = g.instance
    spec = SIZES[size]
    want = {"S": (2, (1, 2), (20, 40)), "M": (6, (3, 5), (130, 170)), "L": (15, (8, 12), (550, 650))}[size]
    assert len(inst.facilities) == want[0]
    assert want[1][0] <= len(inst.vehicles) <= want[1][1] and len(inst.vehicles) == tightness_params(g.config)["n_vehicles"]
    assert want[2][0] <= inst.residents_total <= want[2][1]
    assert len(inst.shelters) == spec.n_shelters and all(f.residents.total >= 3 for f in inst.facilities)
    if size == "L" and t == 0.5:
        assert len(inst.vehicles) == 10
    nodes = [f.node for f in inst.facilities] + [s.node for s in inst.shelters]
    assert len(set(nodes)) == len(nodes) and not set(nodes) & {v.depot for v in inst.vehicles}
    for v in inst.vehicles:
        assert v.capacity() == VEHICLE_TYPES[v.kind] and 0 <= v.start_s <= 900 and v.start_s % 60 == 0
    assert g.hazard.meta.horizon_s == spec.horizon_s and g.hazard.K == 8


@pytest.mark.parametrize("size,graph", [("S", "grid"), ("M", "geo")])
def test_labelled_synthetic_everywhere(size, graph, gens):
    g = gens(size, 0.5, graph, 21)
    inst, meta = g.instance, g.hazard.meta
    assert inst.synthetic and inst.name == g.instance_id and inst.name.startswith("SYNTHETIC-")
    assert inst.provenance["label"] == "SYNTHETIC" and inst.graph.provenance["label"] == "SYNTHETIC"
    assert meta.synthetic and meta.source == "synthetic" and meta.weather_source == "SYNTHETIC"
    assert meta.provenance["label"] == "SYNTHETIC" and meta.provenance["instance"] == g.instance_id
    assert all(f.name.startswith("SYNTHETIC ") for f in inst.facilities)
    assert all(s.name.startswith("SYNTHETIC ") for s in inst.shelters)
    r = Oracle(inst, g.hazard).check_plan(Solution(instance=inst.name, method="empty"))
    assert r.label == "SYNTHETIC" and r.scope.synthetic


def test_instance_id_format():
    assert SyntheticConfig(size="M", tightness=0.25, graph="geo", seed=5).instance_id == "SYNTHETIC-M-geo-t25-s5"
    assert SyntheticConfig(size="L", tightness=1.0, graph="grid", seed=0).instance_id == "SYNTHETIC-L-grid-t100-s0"
    with pytest.raises(ValueError):
        SyntheticConfig(size="XL", tightness=0.5, seed=1)
    with pytest.raises(ValueError):
        SyntheticConfig(size="S", tightness=1.5, seed=1)


# ----------------------------------------------------------------------------- graph rules
@pytest.mark.parametrize("graph", ["grid", "geo"])
def test_road_graph_follows_the_router_conventions(graph, gens):
    g = gens("M", 0.5, graph, 31)
    rg = g.instance.graph
    nodes = {n.id: n for n in rg.nodes}
    edges = {e.id: e for e in rg.edges}
    und = np.array([[int(e.u[1:]), int(e.v[1:])] for e in rg.edges])
    assert is_connected(len(nodes), und)
    for e in rg.edges:                                  # two-way, chord travel time rounded up
        back = edges[f"{e.v}>{e.u}"]
        assert back.travel_time_s == e.travel_time_s
        length = math.hypot(nodes[e.u].x - nodes[e.v].x, nodes[e.u].y - nodes[e.v].y)
        assert e.travel_time_s == max(1, math.ceil(length / (SPEED_KMH / 3.6)))
    deg = {n: 0 for n in nodes}
    for e in rg.edges:
        deg[e.u] += 1
    turns = set(rg.forbidden_turns)
    for e in rg.edges:                                  # U-turns banned except at dead ends
        assert ((e.id, f"{e.v}>{e.u}") in turns) == (deg[e.v] >= 2)
    sites = {f.node for f in g.instance.facilities} | {s.node for s in g.instance.shelters} | \
        {v.depot for v in g.instance.vehicles}
    for n in rg.nodes:
        assert n.waitable == (deg[n.id] == 1 or n.id in sites)


@pytest.mark.parametrize("seed", range(6))
def test_layouts_are_connected_and_planar_enough(seed):
    rng = np.random.default_rng(seed)
    a = grid_layout(rng, 6000.0, 4500.0, 750.0)
    b = geo_layout(rng, 6000.0, 4500.0, 750.0)
    for lay in (a, b):
        assert is_connected(lay.n, lay.edges) and np.all(components(lay.n, lay.edges) == 0)
        assert np.all(lay.edges[:, 0] < lay.edges[:, 1]) and len(np.unique(lay.edges, axis=0)) == len(lay.edges)
        assert lay.xy[:, 0].min() >= 0 and lay.xy[:, 0].max() <= 6000 and lay.xy[:, 1].max() <= 4500
    assert np.min(b.lengths()) >= 0.6 * 750.0 - 0.02          # dart-throwing spacing
    assert 2.5 < b.degree().mean() < 5.5 and 2.5 < a.degree().mean() < 4.0


# ------------------------------------------------------------------------------- tightness
@pytest.mark.parametrize("size,graph,seed", [("S", "geo", 41), ("M", "grid", 42), ("L", "geo", 43)])
def test_tightness_moves_only_its_knobs(size, graph, seed, gens):
    lo, hi = gens(size, 0.1, graph, seed), gens(size, 0.9, graph, seed)
    a, b = lo.instance, hi.instance
    assert a.graph == b.graph                                      # same roads
    assert [(f.id, f.node, f.residents, f.boarding_s) for f in a.facilities] == \
        [(f.id, f.node, f.residents, f.boarding_s) for f in b.facilities]
    assert a.shelters == b.shelters or [s.node for s in a.shelters] != [s.node for s in b.shelters]
    pa, pb = tightness_params(lo.config), tightness_params(hi.config)
    assert pb["lead_s"] < pa["lead_s"] and pb["ros_m_s"] > pa["ros_m_s"]
    assert lo.diagnostics["lead_realized_s"] > hi.diagnostics["lead_realized_s"]
    assert lo.hazard.meta.provenance["ros_m_s"] < hi.hazard.meta.provenance["ros_m_s"]
    assert all(fb.release_s >= fa.release_s for fa, fb in zip(a.facilities, b.facilities))
    assert max(f.release_s for f in b.facilities) <= pb["release_max_s"]
    assert all(v.shift_limit_s == pa["shift_limit_s"] for v in a.vehicles)
    assert all(v.shift_limit_s == pb["shift_limit_s"] for v in b.vehicles) and pb["shift_limit_s"] < pa["shift_limit_s"]
    assert len(b.vehicles) <= len(a.vehicles)
    assert [(v.kind, v.start_s, v.depot) for v in b.vehicles] == [(v.kind, v.start_s, v.depot) for v in a.vehicles[:len(b.vehicles)]]


# ------------------------------------------------------------------------------ the threat
@pytest.mark.parametrize("size,graph,t,seed", [("S", "grid", 0.25, 51), ("S", "geo", 0.75, 52),
                                               ("M", "grid", 0.75, 53), ("M", "geo", 0.25, 54),
                                               ("L", "grid", 0.5, 55)])
def test_fire_threatens_the_facilities_but_not_the_shelters(size, graph, t, seed, gens):
    g = gens(size, t, graph, seed)
    inst, ss = g.instance, g.hazard
    nodes = {n.id: n for n in inst.graph.nodes}
    H = ss.meta.horizon_s
    target = tightness_params(g.config)["lead_s"]
    lead = g.diagnostics["lead_realized_s"]
    assert lead is not None and abs(lead - target) <= 1.0          # earliest arrival at any facility
    assert g.diagnostics["facilities_reached_within_horizon"] >= 1
    first = min(inst.facilities, key=lambda f: g.diagnostics["facility_fire_arrival_s"][f.id] or math.inf)
    p = np.array([nodes[first.node].x, nodes[first.node].y])
    before = ss.query(p, 0.0, lead - 1.0)
    after = ss.query(p, lead, lead + 60.0)
    assert not any(h.contact for h in before) and all(h.supported for h in before)
    assert any(h.contact for h in after)                           # some member burns it at the lead
    reach = {**g.diagnostics["shelter_access_fire_arrival_s"], **g.diagnostics["depot_access_fire_arrival_s"]}
    sites = [(s.id, s.node) for s in inst.shelters] + [(v.depot, v.depot) for v in inst.vehicles]
    for key, node in sites:                                        # diagnostics agree with the hazard
        hz = ss.query(np.array([nodes[node].x, nodes[node].y]), 0.0, H)
        if reach[key] is None:
            assert all(h.contact is False and h.supported for h in hz)
    assert all(v is None for v in reach.values())                  # these seeds: sites out of reach
    assert np.all(ss.supported) and np.all(np.isinf(ss.extinguish_s) | (ss.extinguish_s > H))   # burned roads stay closed
    assert np.all(np.floor(ss.ignite_s[np.isfinite(ss.ignite_s)]) == ss.ignite_s[np.isfinite(ss.ignite_s)])


def test_empty_plan_is_valid_and_delivers_nobody(gens):
    g = gens("S", 0.5, "grid", 61)
    empty = Solution(instance=g.instance.name, method="empty")
    assert validate_solution(g.instance, empty).ok
    r = Oracle(g.instance, g.hazard).check_plan(empty)
    assert r.delivered_total == r.unresolved_total == r.model_no_route_total == 0
    assert r.not_planned_total == g.instance.residents_total and r.makespan_s is None and r.min_slack_s is None
