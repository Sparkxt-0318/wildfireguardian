"""Origin sparsity findings, and the A4 one-page budget guard.

The sparsity numbers are easy to over-claim — they describe sampled origins, not
households, and the singleton fraction *does* eventually fall below 40 % once the
clustering has collapsed. Both traps are pinned here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfireguardian.delivery import printable
from wildfireguardian.delivery.villages import Village

REPO = Path(__file__).resolve().parents[1]
SPARSE = REPO / "data" / "processed" / "cluster_sparsity.json"
NUMBERS = REPO / "docs" / "NUMBERS.json"


def _sparse():
    if not SPARSE.exists():
        pytest.skip("cluster_sparsity.json absent")
    return json.loads(SPARSE.read_text())


# ---------------------------------------------------------------------------
# Sparsity
# ---------------------------------------------------------------------------


def test_singleton_fraction_falls_monotonically_until_collapse():
    d = _sparse()
    usable = [r for r in d["eps_sweep"] if r["largest_cluster_fraction"] <= 0.25]
    fracs = [r["singleton_fraction"] for r in usable]
    assert fracs == sorted(fracs, reverse=True), fracs
    assert min(fracs) > 0.40, "within usable radii it must never drop below 40 %"


def test_the_below_40pct_radii_are_flagged_as_collapsed():
    """35.3 % at 2000 m is real, and must not be quotable as a solution."""
    d = _sparse()
    below = [r for r in d["eps_sweep"] if r["singleton_fraction"] <= 0.40]
    assert below, "the sweep must extend far enough to show the collapse"
    for r in below:
        assert r["largest_cluster_fraction"] > 0.25, (
            f"eps={r['eps_m']} drops below 40 % singletons without collapsing — "
            "the framing in docs/cluster_sparsity.md would then be wrong")


def test_rescue_origins_are_more_dispersed_than_origins_in_general():
    d = _sparse()
    nn = d["nearest_neighbour_m"]
    assert nn["origins_needing_rescue"]["median_m"] > nn["all_origins"]["median_m"]
    assert nn["comparison"]["rescue_more_dispersed"] is True
    assert nn["comparison"]["median_ratio_rescue_over_all"] > 1.0


def test_the_comparison_set_covers_all_origins():
    d = _sparse()
    assert d["nearest_neighbour_m"]["all_origins"]["n"] == 441
    assert d["nearest_neighbour_m"]["origins_needing_rescue"]["n"] == 174


def test_artifact_states_these_are_origins_not_households():
    d = _sparse()
    what = d["what_this_measures"].lower()
    assert "not of households" in what
    assert "sampled origins" in what
    assert "road-network" in what or "road network" in what


def test_operational_implication_is_recorded_without_a_remedy():
    d = _sparse()
    imp = d["operational_implication"]
    assert "broadcast" in imp
    assert "no remedy" in imp.lower()


def test_registry_forbids_reading_sparsity_as_household_dispersion():
    if not NUMBERS.exists():
        pytest.skip("NUMBERS.json absent")
    nums = json.loads(NUMBERS.read_text())["numbers"]
    keys = [k for k in nums if k.startswith("sparsity_")]
    assert keys
    for k in keys:
        joined = " ".join(nums[k]["forbidden_phrasings"])
        assert "households" in joined or "가구" in joined
        assert "ORIGINS, NOT HOUSEHOLDS" in nums[k]["caveat"].upper()


# ---------------------------------------------------------------------------
# Page budget
# ---------------------------------------------------------------------------


def test_single_page_is_within_budget():
    r = printable.check_page_budget({"ok": True, "n_pages": 1}, "X")
    assert r["ok"] and r["severity"] == "none"


@pytest.mark.parametrize("pages,severity", [(2, "over"), (3, "far_over")])
def test_multi_page_is_flagged_with_a_remedy(pages, severity):
    r = printable.check_page_budget({"ok": True, "n_pages": pages}, "정자 일대")
    assert not r["ok"]
    assert r["severity"] == severity
    assert "split-unreachable" in r["message"]
    assert "정자 일대" in r["message"]


def test_unknown_page_count_is_not_silently_passed():
    r = printable.check_page_budget({"ok": True, "n_pages": None}, "X")
    assert not r["ok"] and r["severity"] == "unknown"
    r = printable.check_page_budget({"ok": False}, "X")
    assert not r["ok"]


def _village(n_dispatch: int, n_unreach: int) -> Village:
    pts = [{"x": float(i), "y": 0.0, "unreachable": False, "label": f"d{i}",
            "closing_window_min": float(i)} for i in range(n_dispatch)]
    pts += [{"x": float(i), "y": 1.0, "unreachable": True, "label": f"u{i}",
             "reason_ko": "차단"} for i in range(n_unreach)]
    return Village(1, "정자 일대", "test", pts)


@pytest.mark.parametrize("sections,want_dispatch,want_unreach", [
    ("both", True, True), ("dispatch", True, False), ("unreachable", False, True),
])
def test_sections_selects_the_right_tables(sections, want_dispatch, want_unreach):
    h = printable.render_html(_village(3, 2), generated_at="x", git_commit="y",
                              config_hash="z", source_file="s",
                              n_total_dispatch=3, n_total_unreachable=2,
                              sections=sections)
    assert ("구조 필요 지점" in h) is want_dispatch
    assert ("차량 도달 불가" in h) is want_unreach


def test_split_sheets_say_a_companion_sheet_exists():
    h = printable.render_html(_village(3, 2), generated_at="x", git_commit="y",
                              config_hash="z", source_file="s",
                              n_total_dispatch=3, n_total_unreachable=2,
                              sections="dispatch",
                              sheet_note="도달 불가 2곳은 별도 시트에 있습니다.")
    assert "별도 시트" in h


def test_splitting_cannot_help_a_long_all_dispatch_sheet():
    """The honest limit: with no unreachable rows there is nothing to move.

    This is why the eps=1000 24-row sheet still overflows with the option on,
    and why the generator reports resolved_by_split rather than claiming zero.
    """
    v = _village(24, 0)
    h = printable.render_html(v, generated_at="x", git_commit="y", config_hash="z",
                              source_file="s", n_total_dispatch=24,
                              n_total_unreachable=0, sections="unreachable")
    assert "차량 도달 불가" not in h
    assert "구조 필요 지점" not in h
