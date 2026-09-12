"""WFG-264 / NH-060 (C) — the vehicle-side 사유 line states the code condition and no more.

The walk-side twin is `tests/test_no_safe_route_origin_split.py` §2 (「the sheet
sentence asserts no cause」). This is the same predicate for the 439-series A4
sheet that `scripts/generate_dispatch_outputs.py` prints for every home in
`no_surviving_vehicle_ingress`.

What the class establishes (`src/wildfireguardian/routing/rescue.py`,
`rescuer_reachable` → `classify_origin`): every depot's survival-aware,
exposure-minimising responder route on the drive network was tried and none
returned `reached and not enters_hazard` within the responder time budget under
the vehicle cutoff. Three different return sites of `future_aware_route` collapse
into that one outcome — a depot node already at/above the cutoff (no edge
relaxed), an exhausted search (budget, hazard gate, or no road at all, merged),
and a route that reached the home but was marked `enters_hazard`. So the line
may say 「every depot was tried, no such route was confirmed」. It may NOT name
fire as the cause, a budget consumed, or detours tried; `docs/routing_limitations.md`
§7 and `tests/test_vehicle_unreachable_split.py` show a member of the class for
which each of those is false.

Deliberately clock-free and network-free: the only file read is the committed
`data/processed/rescue_routing.json`, and nothing under `outputs/` is touched.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "generate_dispatch_outputs.py"
ARTIFACT = REPO / "data" / "processed" / "rescue_routing.json"
ARTIFACT_FULL = REPO / "data" / "processed" / "rescue_routing_full.json"

#: The three assertions the superseded line made and the condition does not
#: establish. 「화재로 차단」 is the bare cause claim; 「예산」 and 「우회」 are the
#: two clauses §1 and §6 removed from the walk-side buckets for the same reason.
BARE_CAUSE_TOKENS = ("화재로 차단", "예산", "우회")


@pytest.fixture(scope="module")
def gdo():
    """The emitter, loaded as a module so the constants are read, not retyped."""
    sys.path.insert(0, str(REPO / "src"))
    spec = importlib.util.spec_from_file_location("_wfg_gdo_sentence", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. The sentence itself
# --------------------------------------------------------------------------

def test_the_vehicle_unreachable_sheet_sentence_asserts_no_cause(gdo) -> None:
    """State the code condition and nothing more (docs/routing_limitations.md §7)."""
    text = gdo.UNREACHABLE_REASON_KO
    for banned in BARE_CAUSE_TOKENS:
        assert banned not in text, (
            f"the no_surviving_vehicle_ingress sheet line asserts {banned!r}, which "
            f"the code condition does not establish: {text!r}. rescuer_reachable "
            "only knows that no depot's route returned `reached and not "
            "enters_hazard`; two of the three ways into the class happen on a "
            "field with no fire anywhere (tests/test_vehicle_unreachable_split.py).")
    assert "확인되지 않음" in text, (
        f"the line should report a NON-CONFIRMATION, the form §1, §6 and §7 "
        f"settled on: {text!r}")
    assert text.endswith("확인되지 않음"), text


def test_the_sentence_names_what_was_actually_tested(gdo) -> None:
    """The one thing the loop DOES establish is that every depot was tried."""
    text = gdo.UNREACHABLE_REASON_KO
    assert "어느 거점에서도" in text, (
        f"rescuer_reachable iterates every depot; the line should say so: {text!r}")
    assert "차량 진입" in text, (
        f"this is the responder/vehicle arm, not the walk-out: {text!r}")
    assert "—" not in text, (
        f"CHARTER §8: no em-dashes in shipped screens (font subset): {text!r}")


def test_the_superseded_sentence_is_kept_as_the_record(gdo) -> None:
    """HANDOFF §5 rule 7 / CHARTER §3.7: the withdrawn line is recorded, not erased.

    It is also the control for the test above: the predicate must be red on the
    line the committed sheets carry, or it is green by construction.
    """
    old = gdo.SUPERSEDED_UNREACHABLE_REASON_KO
    assert old != gdo.UNREACHABLE_REASON_KO
    hits = [t for t in BARE_CAUSE_TOKENS if t in old]
    assert hits == list(BARE_CAUSE_TOKENS), (
        f"the recorded superseded line no longer carries the three assertions the "
        f"repair removed ({hits}); the record has drifted: {old!r}")


# --------------------------------------------------------------------------
# 2. The emit path: every unreachable point carries the current line, so the
#    delivery layer's byte-identity fallback (`printable.UNREACHABLE_REASON_FALLBACK`,
#    which still names a cause) is never what a 439-series sheet prints.
# --------------------------------------------------------------------------

def test_every_unreachable_point_emitted_carries_the_current_line(gdo, artifact) -> None:
    from wildfireguardian.delivery import printable

    pts = gdo.build_points(artifact)
    unreachable = [p for p in pts if p["unreachable"]]
    assert unreachable, "the committed artifact carries unreachable homes"
    for p in unreachable:
        assert p.get("reason_ko") == gdo.UNREACHABLE_REASON_KO, p
        assert p["reason_ko"] != printable.UNREACHABLE_REASON_FALLBACK
    assert all("reason_ko" not in p for p in pts if not p["unreachable"]), (
        "a dispatch point carries a 사유 line; only unreachable points do")


@pytest.mark.skipif(not ARTIFACT_FULL.exists(), reason="no full-coverage artifact")
def test_every_unreachable_point_in_the_full_run_carries_the_current_line(gdo) -> None:
    data = json.loads(ARTIFACT_FULL.read_text(encoding="utf-8"))
    pts = gdo.build_points_full(data)
    unreachable = [p for p in pts if p["unreachable"]]
    assert unreachable
    assert all(p.get("reason_ko") == gdo.UNREACHABLE_REASON_KO for p in unreachable)


# --------------------------------------------------------------------------
# 3. The render path: what the A4 sheet actually prints for such a home.
# --------------------------------------------------------------------------

def test_a_rendered_sheet_prints_the_condition_and_not_the_cause(gdo, artifact) -> None:
    """Render one village that holds an unreachable home, the way main() does."""
    from wildfireguardian.delivery import printable
    from wildfireguardian.delivery.villages import cluster_points

    pts = gdo.build_points(artifact)
    villages = cluster_points(pts, artifact["destinations"], eps_m=500.0)
    with_unreachable = [v for v in villages if v.n_unreachable]
    assert with_unreachable, "some cluster holds an unreachable home"
    v = with_unreachable[0]
    html = printable.render_html(
        v, generated_at="2026-09-12 00:00 UTC", git_commit="test",
        config_hash="test", source_file="data/processed/rescue_routing.json",
        n_total_dispatch=artifact["responder_exposure"]["n_dispatch"],
        n_total_unreachable=len(artifact["unreachable_homes"]))
    assert gdo.UNREACHABLE_REASON_KO in html
    assert gdo.SUPERSEDED_UNREACHABLE_REASON_KO not in html
    assert printable.UNREACHABLE_REASON_FALLBACK not in html, (
        "the sheet reached the delivery layer's cause-naming fallback; a 439 "
        "point lost its reason_ko")
    assert "화재로 차단" not in html, (
        "the rendered sheet names fire as the cause of a vehicle-unreachable "
        "home; the code condition does not establish that (§7)")
