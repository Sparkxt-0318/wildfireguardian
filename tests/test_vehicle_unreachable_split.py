"""WFG-264 — what the 439-series 「차량 도달 불가」 class does and does not establish.

`docs/routing_limitations.md` §7. Two halves:

**Reproductions.** Three constructed fields, each putting a home in
`build_dispatch_list`'s unreachable set — the set whose every member printed
「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」 on the A4 sheet a judge is
handed. In the first, no detour was ever tried. In the second and third, there
is **no fire anywhere in the field at all**. So the sentence's three assertions
(fire as the cause, a budget consumed, detours tried) are each false on a case
this code actually produces, and the repair is not an argument from a docstring.

**The committed measurement.** The doc's table of counts is bound to the
artifact `scripts/measure_vehicle_unreachable_split.py` wrote, so a number in
the prose cannot drift from the file it came from.

Deliberately clock-free, network-free and DEM-free: networks and hazards are
built here, and the only files read are two committed JSONs in this repository.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.routing.evacuation import ORIGIN_REFUSED_NOTE
from wildfireguardian.routing.future_front import RoadNetwork
from wildfireguardian.routing.hazard import HazardSequence
from wildfireguardian.routing.rescue import (
    RescueConfig,
    build_dispatch_list,
    rescuer_reachable,
    rescuer_route,
)
from wildfireguardian.spread_v2.grid import CoarseGrid

REPO = Path(__file__).resolve().parents[1]
ARTIFACT = (REPO / "data" / "processed" / "vehicle_unreachable_split" /
            "split_20260912T033329Z.json")
DOC = REPO / "docs" / "routing_limitations.md"

CELL = 500.0
NCOLS = 21


def _grid(ncols: int = NCOLS) -> CoarseGrid:
    return CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * CELL, maxy=CELL,
                      cell_size_m=CELL, nrows=1, ncols=ncols)


def _no_fire_hazard(ncols: int = NCOLS) -> HazardSequence:
    """A field with zero ignition probability everywhere, at every time."""
    return HazardSequence(grid=_grid(ncols), times_min=np.array([0.0, 600.0]),
                          surfaces=[np.zeros((1, ncols)), np.zeros((1, ncols))])


def _chain(ncols: int, speed_ms: float = 10.0) -> nx.Graph:
    g = nx.Graph()
    for i in range(ncols):
        g.add_node(i, x=i * CELL, y=250.0)
    t = (CELL / speed_ms) / 60.0
    for i in range(ncols - 1):
        g.add_edge(i, i + 1, length_m=CELL, time_min=t)
    return g


def _cfg(**kw) -> RescueConfig:
    base = dict(vehicle_cutoff=0.7, responder_dispatch_delay_min=30.0,
                responder_safety_margin_min=12.0, responder_time_budget_min=75.0,
                ingress_sample_spacing_m=150.0)
    base.update(kw)
    return RescueConfig(**base)


# ---------------------------------------------------------------------------
# Return site (A): the DEPOT's own node is already in the fire at dispatch
# ---------------------------------------------------------------------------


def test_a_depot_already_in_the_fire_produces_an_unreachable_home_with_no_search():
    """No detour was tried, so 「(우회 포함)」 was false for this member.

    `rescuer_route` calls `future_aware_route` with the DEPOT as `start`, so
    evacuation.py's pre-search refusal fires on the depot's own node. WFG-262
    measured that branch at zero for ORIGINS, because every copy of
    `candidate_origins` filters origins by the same predicate. **Nothing filters
    depots**, which is why §6's zero does not carry across and why this row was
    forbidden to repair the sentence by analogy.
    """
    g = _grid()
    # The whole west end is above the vehicle cutoff from t = 0; the depot is
    # node 0 and sits in it. The home (node 20) is in clear air.
    surfaces = []
    for _t in (0.0, 600.0):
        s = np.zeros((1, NCOLS))
        s[0, 0:3] = 1.0
        surfaces.append(s)
    haz = HazardSequence(grid=g, times_min=np.array([0.0, 600.0]), surfaces=surfaces)
    drive = RoadNetwork(graph=_chain(NCOLS), shelters=set())
    cfg = _cfg()

    rt = rescuer_route(drive, depot_node=0, home_node=20, hazard=haz, cfg=cfg)
    assert not rt.reached
    assert rt.note == ORIGIN_REFUSED_NOTE, (
        "the pre-search refusal did not fire; this test no longer reproduces "
        "return site (A)")
    assert rt.route == [], "a route was built, so a search did run"

    reachable, _sa, _di = rescuer_reachable(drive, [0], 20, haz, cfg)
    assert not reachable
    dispatch, unreachable = build_dispatch_list([20], drive, [0], [], haz, cfg)
    assert not dispatch
    assert [u["home_node"] for u in unreachable] == [20], (
        "the home did not land in the class whose sheet line asserts that "
        "detours were tried")


# ---------------------------------------------------------------------------
# Return site (B), disconnection: no road at all, and no fire anywhere
# ---------------------------------------------------------------------------


def test_a_home_on_a_disconnected_road_component_is_called_blocked_by_fire():
    """There is no fire in this field. 「화재로 차단됨」 was false by construction.

    `best_closing_window_min` is null here (`ingress_corridor` stores -inf when
    there is no path), and it is null for no home in either committed artifact.
    ⚠ That does NOT make null a detector for this case: the over-budget test
    below produces a null window with a road present, from the other infinity.
    """
    g = _chain(NCOLS)
    g.remove_edge(10, 11)                       # home side is now unreachable
    drive = RoadNetwork(graph=g, shelters=set())
    haz = _no_fire_hazard()
    cfg = _cfg()

    assert not nx.has_path(g, 0, 20)
    dispatch, unreachable = build_dispatch_list([20], drive, [0], [], haz, cfg)
    assert not dispatch
    assert len(unreachable) == 1
    assert unreachable[0]["best_closing_window_min"] is None, (
        "a missing road no longer serialises as a null window; §7's reading "
        "of that field has to be re-derived")
    # And the field really is fireless, so nothing here was blocked by fire.
    assert float(np.max(haz.surfaces[-1])) == 0.0


# ---------------------------------------------------------------------------
# Return site (B), budget: a road exists, no fire anywhere, the budget binds
# ---------------------------------------------------------------------------


def test_a_home_beyond_the_responder_budget_is_called_blocked_by_fire():
    """A budget WAS consumed here — and there is still no fire to blame."""
    ncols = 41
    # 40 edges of 500 m at 1 m/s is 333 min of driving against a 75-min budget.
    drive = RoadNetwork(graph=_chain(ncols, speed_ms=1.0), shelters=set())
    haz = _no_fire_hazard(ncols)
    cfg = _cfg()

    dispatch, unreachable = build_dispatch_list([ncols - 1], drive, [0], [], haz, cfg)
    assert not dispatch
    assert len(unreachable) == 1
    assert float(np.max(haz.surfaces[-1])) == 0.0
    # ⚠ THIS IS THE ASSERTION THAT FAILED AND CORRECTED §7. The draft claimed a
    # null window meant "no drive path from any depot". Here a road exists, and
    # the window is null anyway, because a corridor the fire never crosses has
    # infinite survival time and +inf serialises the same way as -inf.
    assert unreachable[0]["best_closing_window_min"] is None, (
        "a never-cut corridor no longer serialises as a null window; §7's "
        "reading of that field has to be re-derived")


def test_the_fireless_cases_carry_the_same_stored_reason():
    """One sentence, several worlds — the whole of §7 in one assertion.

    The class and `build_dispatch_list`'s stored reason are identical in both
    fireless cases; only the sheet line claimed to know which world it was in.
    """
    cfg = _cfg()
    haz_clear = _no_fire_hazard()
    g_cut = _chain(NCOLS)
    g_cut.remove_edge(10, 11)
    cases = {
        "disconnected": (RoadNetwork(graph=g_cut, shelters=set()), haz_clear),
        "over_budget": (RoadNetwork(graph=_chain(41, speed_ms=1.0), shelters=set()),
                        _no_fire_hazard(41)),
    }
    for name, (drive, haz) in cases.items():
        home = max(drive.graph.nodes)
        _d, unreachable = build_dispatch_list([home], drive, [0], [], haz, cfg)
        assert len(unreachable) == 1, name
        assert unreachable[0]["reason"] == (
            "no surviving vehicle ingress (even with detours) in budget"), (
            f"{name}: build_dispatch_list's stored reason changed; §7 quotes it")


# ---------------------------------------------------------------------------
# The committed measurement, bound to the doc
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_identity_controls_are_recorded_and_agree(artifact):
    """A count over a population that is not the committed one means nothing."""
    for arm in artifact["arms"]:
        ic = arm["identity_controls"]
        assert ic["four_way_counts_agrees"] and ic["responder_exposure_agrees"]
        assert ic["four_way_sums_to_n"]
        assert ic["n_unreachable"] == arm["n_unreachable"]
        assert ic["responder_safety_margin_min_read_from_artifact"] == 12.0


def test_every_committed_member_has_a_finite_best_window(artifact):
    """Empty on both fields, published as empty — the WFG-262 discipline.

    A zero here rules out BOTH infinities at once and neither on its own: no
    home in the class lacked a road, and none had a corridor the fire never
    crosses. That is weaker than the draft claimed and is what the field says.
    """
    for arm in artifact["arms"]:
        assert arm["n_no_finite_best_closing_window"] == 0


def test_the_doc_table_quotes_the_artifact(artifact):
    """§7's table of counts is the artifact's, not a transcription."""
    text = DOC.read_text(encoding="utf-8")
    start = text.index("### What the committed 영덕 fields say")
    block = text[start:start + 2000]
    slice_arm, full_arm = artifact["arms"]
    rows = [
        ("homes in the class", "n_unreachable"),
        ("no finite best closing window", "n_no_finite_best_closing_window"),
        ("direct corridor survives past the responder's ETA",
         "n_corridor_survives_past_responder_eta"),
        ("direct corridor reachable by the screening test itself",
         "n_corridor_reachable_by_the_screening_test"),
    ]
    for label, key in rows:
        line = next((ln for ln in block.splitlines() if ln.startswith("|")
                     and label in ln), None)
        assert line is not None, f"§7's table has no row for {label!r}"
        cells = [c.strip().strip("*") for c in line.strip().strip("|").split("|")]
        assert cells[-2] == str(slice_arm[key]), (
            f"§7's {label!r} dispatch-slice cell is {cells[-2]}, artifact says "
            f"{slice_arm[key]}")
        assert cells[-1] == str(full_arm[key]), (
            f"§7's {label!r} full-coverage cell is {cells[-1]}, artifact says "
            f"{full_arm[key]}")


def test_the_registry_values_come_from_this_artifact(artifact):
    """The eight `vus_` keys re-derive, so §7's prose cannot outrun the file."""
    numbers = json.loads((REPO / "docs" / "NUMBERS.json").read_text(
        encoding="utf-8"))["numbers"]
    keys = [k for k in numbers if k.startswith("vus_")]
    assert len(keys) == 8, f"expected 8 vus_ keys, found {len(keys)}"
    for k in keys:
        entry = numbers[k]
        cur = artifact
        for part in entry["json_path"].split("."):
            cur = cur[int(part)] if part.isdigit() else cur[part]
        assert entry["value"] == cur, k
        assert "NOT A MISCLASSIFICATION COUNT" in entry["caveat"], k
