"""The decision metric on SYNTHETIC fires, road graphs and models: requests, truth, oracle verdicts, rates, K curve.

Every fire, graph, model and number here is SYNTHETIC; nothing is written to firecast-lab/results/."""
import dataclasses
import re

import numpy as np
import pytest
from evacplan import Instance, Solution, validate_solution
from hazard_contract import Grid, ScenarioSet
from hazard_contract.geometry import polyline_cells
from PIL import Image

import synthetic as syn
from firecast_lab import baselines as bl
from firecast_lab import decision as dm
from firecast_lab import producer
from firecast_lab.splits import LAB

T = producer.PACKET_HEAT.burn_duration_s


@pytest.fixture(scope="module")
def case():
    """A SYNTHETIC window (cutoff 24 h after ignition), its lattice road graph, 12 requests and reconstruction truth."""
    arrival, *_ = syn.fire(seed=2)
    window = syn.windows("SYNTHETIC_D", arrival)[1]
    graph = syn.road_graph(arrival.shape)
    requests = dm.requests_for(window, graph, seed=0, config=dm.RequestConfig(n_requests=12))
    return window, graph, requests, dm.truth_from_reconstruction(window)


@pytest.fixture(scope="module")
def truth_out(case):
    _, _, requests, truth = case
    return [dm.truth_outcome(*s) for s in dm.oracle_states(requests, truth)]


@pytest.fixture(scope="module")
def model():
    train = syn.windows("SYNTHETIC_T0", *syn.fire(seed=0)) + syn.windows("SYNTHETIC_T1", *syn.fire(seed=1))
    return bl.CalibratedDilation().fit(train)


def _rates(window, verdicts, truth_out):
    cleared = [state == "checked" for state, _, _ in verdicts]
    return dm.summarize([window.fire] * len(cleared), cleared, truth_out, draws=200)


def _model_set(window, hours, name):
    return producer.scenario_set(hours, transform=window.transform, crs_epsg=window.epsg,
                                 issue_time_utc=window.cutoff_utc, horizon_h=window.lead_h, model_version=name,
                                 weather_source="none", seed=0, config={}, synthetic=True)


# ------------------------------------------------------------------------------------------- requests
def test_requests_are_valid_cutoff_itineraries(case):
    window, graph, _, _ = case
    config = dm.RequestConfig(n_requests=12, wait_share=1.0)
    requests = dm.requests_for(window, graph, seed=0, config=config)
    assert len(requests.requests) == 12 and requests.origin_candidates > 12
    assert requests.requests == dm.requests_for(window, graph, seed=0, config=config).requests      # deterministic
    grid = Grid(window.transform, *window.inputs.shape)
    nodes = {n.id: n for n in graph.nodes}
    for r in requests.requests:
        rows, cols, outside = polyline_cells(grid, np.array([[nodes[r.origin].x, nodes[r.origin].y]]))
        assert not outside and not window.inputs.burned[rows, cols].any()          # outside the cutoff burned area
        assert 0 < r.front_m <= config.origin_max_m
        o, d = nodes[r.origin], nodes[r.destination]
        assert config.trip_m[0] <= np.hypot(o.x - d.x, o.y - d.y) <= config.trip_m[1]
        assert 0 <= r.start_s and r.depart_s == r.start_s + r.wait_s and r.arrive_s < 3600 * window.lead_h
        assert r.wait_s == 0 or o.waitable
    assert any(r.wait_s > 0 for r in requests.requests)
    itineraries = [r.itinerary() for r in requests.requests]
    assert validate_solution(requests.instance, Solution(itineraries=itineraries)).ok
    assert {v.id: (v.depot, v.start_s) for v in requests.instance.vehicles} == \
        {r.id: (r.origin, r.start_s) for r in requests.requests}


def test_requests_use_no_information_after_the_cutoff():
    arrival, *_ = syn.fire(seed=4)
    after = np.isfinite(arrival) & (arrival > 24.0)
    other = arrival.copy()
    other[after] += 5.0                                         # the fire after the cutoff is slower ...
    other[after & (arrival > 36.0)] = np.nan                    # ... and stops earlier: another final perimeter
    w1, w2 = (next(w for w in syn.windows("SYNTHETIC_L", a) if w.cutoff_h == 24.0) for a in (arrival, other))
    assert np.array_equal(w1.inputs.burned, w2.inputs.burned)
    assert not np.array_equal(w1.outcome_h, w2.outcome_h)
    t1, t2 = dm.truth_from_reconstruction(w1), dm.truth_from_reconstruction(w2)
    assert not np.array_equal(t1.ignite_s, t2.ignite_s, equal_nan=True)            # the truth sets differ
    graph = syn.road_graph(arrival.shape)
    r1, r2 = (dm.requests_for(w, graph, seed=3, config=dm.RequestConfig(n_requests=10)) for w in (w1, w2))
    assert len(r1.requests) == 10 and r1.requests == r2.requests and r1.window_seed == r2.window_seed
    assert dm.requests_for(w1, graph, seed=4, config=dm.RequestConfig(n_requests=10)).requests != r1.requests


def test_shortest_paths_keep_turn_rules():
    # SYNTHETIC 2 x 3 lattice: n0_0 -> n0_2 goes straight through n0_1 unless that turn is forbidden
    plain = syn.road_graph((2, 3))
    banned = syn.road_graph((2, 3), forbidden=[("n0_0>n0_1", "n0_1>n0_2")])
    grid = Grid((375.0, 0.0, 1_000_000.0, 0.0, -375.0, 2_000_000.0), 2, 3)
    paths = []
    for graph in (plain, banned):
        roads = dm._Roads(Instance(name="SYNTHETIC", synthetic=True, graph=graph, hazard=dm._hazard_ref(0.0)), grid)
        times, last, prev = roads.shortest_from("n0_0")
        paths.append((dm._path("n0_2", last, prev), times[roads.position["n0_2"]]))
    assert paths[0] == (["n0_0>n0_1", "n0_1>n0_2"], 68.0)
    path, time = paths[1]
    assert time == 4 * 34.0 and len(path) == 4 and ("n0_0>n0_1", "n0_1>n0_2") not in zip(path, path[1:])


# ---------------------------------------------------------------------------------------------- truth
def test_reconstruction_truth_is_the_hourly_envelope_on_the_scoring_domain(case):
    window = case[0]
    domain = window.domain.copy()
    domain[:2, :] = False                                       # a SYNTHETIC hole in the scoring domain
    truth = dm.truth_from_reconstruction(dataclasses.replace(window, domain=domain))
    out, ig, ex, sup = window.outcome_h, truth.ignite_s[0], truth.extinguish_s[0], truth.supported[0]
    burning = np.isfinite(out) & (out <= window.lead_h)          # inside an isochrone up to the lead
    burns = domain & burning
    assert burns.any() and (domain & (out <= 0)).any()
    assert np.array_equal(ig[burns], 3600.0 * (np.ceil(out[burns]) - 1.0))     # (h - 1, h] -> [h - 1, h + T)
    assert np.array_equal(ex[burns], 3600.0 * np.ceil(out[burns]) + T)
    # Partly burned candidates (A-M1): outside the finite-arrival mask with a burned 8-neighbour. Each burns from the
    # earliest ignition to the latest extinction of its burned neighbours, also those outside the domain.
    height, width = out.shape
    ring = np.zeros_like(domain)
    for r, c in np.argwhere(domain & ~np.isfinite(out)):
        near = [(i, j) for i in range(r - 1, r + 2) for j in range(c - 1, c + 2)
                if 0 <= i < height and 0 <= j < width and burning[i, j]]
        if near:
            ring[r, c] = True
            hours = np.ceil([out[i, j] for i, j in near])
            assert (ig[r, c], ex[r, c]) == (3600.0 * (hours.min() - 1.0), 3600.0 * hours.max() + T)
    assert ring.any() and truth.meta.provenance["partly_burned_cells"] == int(ring.sum())
    never = domain & ~burning & ~ring
    assert never.any() and np.isinf(ig[never]).all() and np.isinf(ex[never]).all() and sup[never].all()
    assert not sup[~domain].any() and np.isnan(ig[~domain]).all()              # outside the domain: unknown
    meta = truth.meta
    assert (meta.K, meta.horizon_s, meta.source, meta.synthetic) == (1, 3600.0 * window.lead_h, "perimeter", True)
    assert meta.provenance["mode"] == dm.TRUTH_MODE and "reconstruction truth" in meta.model_version
    assert meta.heat_source == producer.PACKET_HEAT and meta.issue_time_utc.isoformat()[:19] == window.cutoff_utc[:19]
    unknown = out.copy()
    unknown[5, 5] = np.nan                                      # an unknown outcome is never read as unburned
    assert not dm.truth_from_reconstruction(dataclasses.replace(window, outcome_h=unknown)).supported[0, 5, 5]


def _column_road(column: int, rows: range, *, depart_s: float, window) -> dm.RequestSet:
    """One SYNTHETIC request: a straight road through the centres of ``column`` (``rows``), driven from ``depart_s``."""
    from evacplan import Edge, Node, RoadGraph, Vehicle

    x = 1_000_000.0 + (column + 0.5) * syn.CELL
    nodes = [Node(id=f"c{r}", x=x, y=2_000_000.0 - (r + 0.5) * syn.CELL) for r in rows]
    edges = [Edge(id=f"c{a}>c{b}", u=f"c{a}", v=f"c{b}", travel_time_s=34.0) for a, b in zip(rows, rows[1:])]
    graph = RoadGraph(crs_epsg=5179, nodes=nodes, edges=edges, provenance={"generator": "SYNTHETIC column road"})
    request = dm.Request(id="R000", origin=nodes[0].id, destination=nodes[-1].id, front_m=0.0, start_s=depart_s,
                         wait_s=0.0, depart_s=depart_s, arrive_s=depart_s + 34.0 * len(edges),
                         edges=tuple(e.id for e in edges), length_m=syn.CELL * len(edges))
    instance = Instance(name="SYNTHETIC column road", synthetic=True, graph=graph, hazard=dm._hazard_ref(0.0),
                        vehicles=[Vehicle(id="R000", depot=nodes[0].id, start_s=depart_s, seats=0)])
    return dm.RequestSet(fire=window.fire, cutoff_utc=window.cutoff_utc, lead_h=window.lead_h, window_seed=0,
                         config=dm.RequestConfig(), requests=(request,), instance=instance, origin_candidates=1)


def test_reconstruction_truth_counts_partly_burned_edge_cells():
    """Review finding A-M1 (SYNTHETIC 10 x 10 grid). The front moves east one cell per hour and stops at +5 h, 40%
    into column 6. A centre-in reconstruction (Choi's Korean rule) leaves column 6 out, although 40% of every
    column-6 cell burned. A road along column 6 driven at +4.5 h meets the fire: truth must call it a hit, as the
    all-touched perimeter truth of the same fire does."""
    front = lambda t: 1.4 + t                                   # front position (cells from the west edge) at t h
    columns = np.arange(10)
    arrival = np.where(columns + 0.5 <= front(5.0), columns + 0.5 - 1.4, np.inf)   # centre-in: columns 0-5 only
    outcome = np.repeat(arrival[None], 10, axis=0)
    window = syn.window(outcome <= 0, outcome, lead_h=24)
    requests = _column_road(6, range(1, 9), depart_s=4.5 * 3600.0, window=window)
    reconstruction = dm.oracle_states(requests, dm.truth_from_reconstruction(window))[0]
    assert dm.truth_outcome(*reconstruction) == "hit" and reconstruction[1] == "FLAME_CONTACT"

    x0, y0, cell = 1_000_000.0, 2_000_000.0, syn.CELL           # the same fire as perimeters, rasterized all-touched
    ring = lambda t: [[x0 + 0.01 * cell, y0 - 0.01 * cell], [x0 + front(t) * cell, y0 - 0.01 * cell],
                      [x0 + front(t) * cell, y0 - 9.99 * cell], [x0 + 0.01 * cell, y0 - 9.99 * cell]]
    perimeters = dm.truth_from_perimeters(window, [(3600.0 * t, ring(t)) for t in range(6)])
    assert dm.truth_outcome(*dm.oracle_states(requests, perimeters)[0]) == "hit"
    # The burned neighbours count even outside the scoring domain: they burned, the domain only limits scoring.
    east = np.zeros((10, 10), bool)
    east[:, 6:] = True
    cropped = dm.truth_from_reconstruction(dataclasses.replace(window, domain=east))
    assert dm.truth_outcome(*dm.oracle_states(requests, cropped)[0]) == "hit"
    # Column 6 burns from its neighbours' earliest ignition (column 5 arrives in hour 5) to their latest extinction.
    truth = dm.truth_from_reconstruction(window)
    assert (truth.ignite_s[0, 3, 6], truth.extinguish_s[0, 3, 6]) == (4 * 3600.0, 5 * 3600.0 + T)
    assert np.isinf(truth.ignite_s[0, :, 7:]).all() and truth.meta.provenance["partly_burned_cells"] == 10
    # ... and a road two columns further east, which no burned cell touches, stays safe
    clear = _column_road(8, range(1, 9), depart_s=4.5 * 3600.0, window=window)
    assert dm.truth_outcome(*dm.oracle_states(clear, truth)[0]) == "safe"


def test_perimeter_truth_horizon_is_the_last_survey(case):
    window = case[0]
    out = window.outcome_h
    series = [(0.0, out <= 0), ("2030-01-02T06:00:00Z", out <= 6), (12 * 3600.0, out <= 12)]
    truth = dm.truth_from_perimeters(window, series)
    assert truth.meta.horizon_s == 12 * 3600.0 and truth.meta.provenance["mode"] == "envelope"
    cell = np.argwhere((out > 6) & (out <= 12))[0]
    assert (truth.ignite_s[0, cell[0], cell[1]], truth.extinguish_s[0, cell[0], cell[1]]) == (6 * 3600.0,
                                                                                              12 * 3600.0 + T)
    with pytest.raises(ValueError, match="none after it"):
        dm.truth_from_perimeters(window, series + [(25 * 3600.0, out <= 25)])


# ------------------------------------------------------------------------------------- verdicts and rates
def test_members_identical_to_truth_give_false_safe_zero(case, truth_out):
    window, _, requests, truth = case
    assert {"hit", "safe"} <= set(truth_out)                                    # a non-trivial request set
    verdicts = dm.model_verdicts(requests, dm.member_subset(truth, [0, 0, 0]), repeats=2)
    rates = _rates(window, verdicts, truth_out)
    assert rates["counts"]["cleared"] == rates["counts"]["safe"] > 0
    assert rates["false_safe"]["point"] == rates["miss_rate"]["point"] == rates["false_unsafe"]["point"] == 0.0


def test_a_model_that_marks_everything_burning_clears_nothing(case, truth_out):
    window, _, requests, truth = case
    K, (h, w) = 4, window.inputs.shape
    meta = truth.meta.model_copy(update=dict(K=K, source="model", model_version="SYNTHETIC: everything burns"))
    burning = ScenarioSet(np.full((K, h, w), -1.0), np.full((K, h, w), 2 * meta.horizon_s), np.ones((K, h, w), bool),
                          meta)
    verdicts = dm.model_verdicts(requests, burning, repeats=2)
    assert {(s, c) for s, c, _ in verdicts} == {("model_no_route", "FLAME_CONTACT")}
    rates = _rates(window, verdicts, truth_out)
    assert rates["clearance_rate"]["point"] == 0.0 and rates["clearance_rate"]["defined"]
    assert rates["false_safe"]["point"] is None and not rates["false_safe"]["defined"]
    assert "undefined" in rates["false_safe"]["note"] and "clearance 0" in dm.rate_text(rates["false_safe"])
    curve = dm.k_curve(["|".join(map(str, u)) for _, _, u in verdicts], truth_out, K)
    assert all(p["cleared"] == 0 and p["false_safe"] is None for p in curve)


def test_a_too_slow_model_is_falsely_safe(case, truth_out):
    window, _, requests, _ = case
    out = window.outcome_h
    slow = np.where(out <= 0, out, 3.0 * out)                                   # new burns arrive 3 times later
    hours = np.where(slow <= window.lead_h, slow, np.inf)[None]
    rates = _rates(window, dm.model_verdicts(requests, _model_set(window, hours, "SYNTHETIC slow"), repeats=1),
                   truth_out)
    assert rates["false_safe"]["point"] > 0 and rates["miss_rate"]["point"] > 0
    assert rates["counts"]["cleared_hit"] == rates["false_safe"]["numerator"] > 0


@pytest.mark.parametrize("coupling", ["shared", "copula"])
def test_adding_members_never_increases_clearance(case, model, coupling):
    window, graph, _, _ = case
    requests = dm.requests_for(window, graph, seed=1, config=dm.RequestConfig(n_requests=8))
    K = 4
    hours, _ = bl.forecast(model, window, K=K, seed=7, coupling=coupling, length_cells=3.0 if coupling == "copula"
                           else None)
    scenarios = producer.from_window(window, hours, model=model, seed=7, config={})
    verdicts = dm.model_verdicts(requests, scenarios, repeats=2, seed=0)
    for r in range(2):
        order = dm.member_order(K, r, 0)
        cleared = np.array([[s == "checked" for s, _ in dm.oracle_states(requests, dm.member_subset(scenarios,
                                                                                                    order[:k]))]
                            for k in range(1, K + 1)])                           # every nested subset, no shortcut
        assert (cleared[1:] <= cleared[:-1]).all()                              # adding members never clears
        assert cleared[0].sum() > cleared[-1].sum()                             # ... and here they do remove some
        assert np.array_equal(cleared[-1], [s == "checked" for s, _, _ in verdicts])
        expected = [max([k for k in dm.k_values(K) if cleared[k - 1, i]], default=0) for i in range(cleared.shape[1])]
        assert [u[r] for _, _, u in verdicts] == expected                      # the binary search agrees
    curve = dm.k_curve([u for _, _, u in verdicts], ["safe"] * len(verdicts), K)
    for r in range(2):
        rates = [p["clearance_rate"] for p in curve if p["repeat"] == r]
        assert rates == sorted(rates, reverse=True)


def test_truth_unresolved_requests_are_excluded_and_counted(case):
    window, _, requests, _ = case
    out = window.outcome_h
    domain = window.domain.copy()
    domain[:, :6] = False                                       # a hole in the mapped domain (west)
    short = dataclasses.replace(window, domain=domain)
    truth = dm.truth_from_perimeters(short, [(0.0, out <= 0), (6 * 3600.0, out <= 6), (12 * 3600.0, out <= 12)])
    states = dm.oracle_states(requests, truth)
    outcome = [dm.truth_outcome(*s) for s in states]
    causes = {c for (s, c) in states if s == "unresolved"}
    assert {"BEYOND_HORIZON"} <= causes and outcome.count("unresolved") >= 2   # trips after the last survey
    everything = [True] * len(outcome)                         # a SYNTHETIC model that clears every request
    rates = dm.summarize([window.fire] * len(outcome), everything, outcome, draws=100)
    n_unresolved = outcome.count("unresolved")
    assert rates["truth_unresolved"] == rates["cleared_truth_unresolved"] == n_unresolved
    assert rates["counts"]["scored"] == rates["counts"]["cleared"] == len(outcome) - n_unresolved
    assert rates["counts"]["safe"] == outcome.count("safe")                     # unresolved is never safe
    assert rates["clearance_rate"]["point"] == 1.0


def test_rates_pool_requests_and_resample_whole_fires():
    fire = ["A"] * 4 + ["B"] * 4 + ["C"] * 2
    cleared = [1, 1, 0, 0, 1, 0, 1, 1, 1, 0]
    truth = ["hit", "safe", "hit", "safe", "safe", "hit", "unresolved", "safe", "hit", "unresolved"]
    s = dm.summarize(fire, cleared, truth, draws=2000, seed=3)
    assert s["counts"] == dict(cleared_hit=2, cleared=5, hit=4, not_cleared_safe=1, safe=4, scored=8)
    assert (s["requests"], s["truth_unresolved"], s["cleared_truth_unresolved"], s["fires"]) == (10, 2, 1, 3)
    for name, value in dict(false_safe=2 / 5, miss_rate=2 / 4, clearance_rate=5 / 8, false_unsafe=1 / 4).items():
        lo, hi = s[name]["interval"]
        assert s[name]["point"] == pytest.approx(value) and lo <= value <= hi and s[name]["seed"] == 3
    assert s["false_safe"]["undefined_draws"] == 0                # every fire clears something
    assert s["false_unsafe"]["undefined_draws"] > 0               # draws of fire C alone have no safe request
    assert dm.summarize(fire, cleared, truth, draws=2000, seed=3) == s                                   # seeded
    one = dm.summarize(["A"] * 4, cleared[:4], truth[:4], draws=500)
    assert one["false_safe"]["interval"] == [0.5, 0.5]                          # one fire: a degenerate interval
    none = dm.summarize(["A", "B"], [True, False], ["unresolved", "unresolved"], draws=100)
    assert none["fires"] == 0 and not any(none[k]["defined"] for k in dm.RATES)
    with pytest.raises(ValueError, match="truth outcomes"):
        dm.summarize(["A"], [True], ["checked"])


def test_report_never_pools_countries_or_truth_kinds():
    row = dict(fire="SYNTHETIC_A", country="KR", truth_kind="reconstruction", coupling="shared", length_cells=None,
               members=2, cleared=True, truth="safe", truth_cause=None, truth_centre_in="safe", model_state="checked",
               cleared_up_to="2|2", synthetic=True)
    out = dm.report([row, dict(row, fire="SYNTHETIC_B", cleared=False, truth="hit", truth_centre_in="safe",
                               model_state="model_no_route", cleared_up_to="1|0")], draws=50)
    assert out["shared"]["headline"]["counts"]["scored"] == 2 and out["shared"]["headline"]["fires"] == 2
    assert out["shared"]["truth_ring_flips"] == {"safe->hit": 1}           # the partly burned ring made one hit
    with pytest.raises(ValueError, match="never pool"):
        dm.report([row, dict(row, country="US", truth_kind="perimeters")])


def test_k_curve_reads_the_nested_verdicts():
    up = ["8|8", "2|4", "0|1", "4|0"]
    truth = ["safe", "hit", "hit", "unresolved"]
    curve = {(p["repeat"], p["k"]): p for p in dm.k_curve(up, truth, 8)}
    assert dm.k_values(8) == [1, 2, 4, 8] and dm.k_values(6) == [1, 2, 4, 6] and dm.k_values(1) == [1]
    assert [curve[0, k]["cleared"] for k in (1, 2, 4, 8)] == [2, 2, 1, 1]
    assert [curve[1, k]["cleared"] for k in (1, 2, 4, 8)] == [3, 2, 2, 1]
    assert curve[0, 2]["false_safe"] == 0.5 and curve[1, 8]["false_safe"] == 0.0 and curve[0, 1]["scored"] == 3


def test_tradeoff_plot_is_labelled_synthetic(tmp_path):
    curve = dm.k_curve(["8|8", "2|4", "0|1"], ["safe", "hit", "hit"], 8)
    blocked = dm.k_curve(["0|0", "0|0"], ["safe", "hit"], 8)
    path = dm.plot_tradeoff({"shared": curve, "copula": blocked}, tmp_path / "tradeoff.png", synthetic=True,
                            title="decision metric (test)", labels={"copula": "copula, L = 3 cells"})
    with Image.open(path) as image:
        assert image.format == "PNG" and image.info["Title"].startswith("SYNTHETIC")


def test_only_evacplan_oracle_declares_states():
    """Program rule 3: firecast_lab reads oracle states and never constructs states or oracle results."""
    declare = re.compile(r"\bState\b|\b(LegResult|ActionResult|TripResult|ItineraryResult|PlanResult)\(")
    offenders = [f"{f.name}:{i}" for f in sorted((LAB / "src" / "firecast_lab").glob("*.py"))
                 for i, line in enumerate(f.read_text().splitlines(), 1) if declare.search(line)]
    assert not offenders
    assert "Oracle(" in (LAB / "src" / "firecast_lab" / "decision.py").read_text()
