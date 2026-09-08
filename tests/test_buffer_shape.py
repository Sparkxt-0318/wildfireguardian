"""WFG-127: the buffer-width grid, and the claims the repository rests on it.

Three surfaces once read a **spike** off a five-point grid whose two neighbours
of the best width were each a factor of two away. The grid could not resolve
that shape. This module holds the gate the row asked for — *no surface may
assert the shape while the grid cannot resolve it* — plus the checks that make
the denser grid worth reading beside the committed one.

Everything here reads committed files only: no clock, no timezone, no network,
no path outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMITTED = REPO / "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
DENSE = (REPO / "data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json")
NUMBERS = REPO / "docs/NUMBERS.json"
REGISTRY = REPO / "docs/auto/withdrawn_claims.json"

#: The cells that make a sweep row. If the two runs disagree on any one of
#: these at a shared width, the three new widths are not comparable with the
#: five old ones and nothing else in this module means anything.
CELLS = ("recovered_of_forecast_only", "already_safe_broken", "safe_total",
         "failed_enters_hazard", "failed_unreachable", "failed_over_budget")

#: The claim's own region: the gap between the best width and its thin
#: neighbour, which is where a spike and a shoulder differ.
GAP_LO, GAP_HI = 500.0, 1000.0


def _sweep(path: Path) -> dict[float, dict]:
    art = json.loads(path.read_text(encoding="utf-8"))
    return {float(r["buffer_m"]): r for r in art["buffer_sensitivity"]}


def test_the_five_shared_widths_reproduce_cell_for_cell():
    """The denser run must land the committed run's own widths where they are.

    This is the control for the whole experiment, and it is checked rather than
    assumed: three new points are only readable beside five old ones if the
    five old ones come out identical.
    """
    old, new = _sweep(COMMITTED), _sweep(DENSE)
    assert set(old) <= set(new), (
        f"the dense grid dropped a committed width: {sorted(set(old) - set(new))}")
    for w in sorted(old):
        for cell in CELLS:
            assert old[w][cell] == new[w][cell], (
                f"buffer {w:.0f} m, cell {cell!r}: committed artifact says "
                f"{old[w][cell]}, the dense re-run says {new[w][cell]}. The two "
                f"grids are not comparable and docs/present_perimeter_buffer_shape.md "
                f"must not be read as if they were.")


def test_the_dense_grid_resolves_the_gap_the_claim_was_about():
    """WFG-127 (ii): a measured point strictly inside 500 m .. 1 km."""
    inside = [w for w in _sweep(DENSE) if GAP_LO < w < GAP_HI]
    assert inside, (
        f"no measured width strictly between {GAP_LO:.0f} m and {GAP_HI:.0f} m. "
        f"The shape of the top is then unresolved again, and every surface must "
        f"go back to asserting nothing about it.")


# --------------------------------------------------------------------------
# The gate WFG-127 (iii) actually asked for.
# --------------------------------------------------------------------------
# It is CONDITIONAL on purpose. The defect was never the word "spike"; it was
# asserting a shape a grid could not resolve. So this test bans the assertions
# exactly while the grid cannot support them, and goes quiet when it can. If a
# later lap ever narrows the grid back — a new region, a re-keyed artifact —
# the ban comes back on by itself rather than needing someone to remember.
SHAPE_ASSERTIONS = (
    (re.compile(r"spikes?,?\s+(?:not|rather\s+than)\s+a\s+plateau"),
     "asserts a spike over a plateau"),
    (re.compile(r"고원이\s*아니라\s*\**\s*뾰족한\s*봉우리"),
     "asserts a peak rather than a plateau (Korean)"),
    (re.compile(r"어느\s*폭이\s*맞는지는\s*그날\s*알\s*수\s*없"),
     "rests 'you cannot know the width on the day' on that shape (Korean)"),
)

#: The surfaces the claim actually lived on. Named rather than globbed: a glob
#: would silently start passing the day a file is renamed, which is the failure
#: mode this whole row is about.
SURFACES = (
    "README.md",
    "docs/present_perimeter_arm.md",
    "docs/fair_opponent_line.md",
    "docs/auto/DEMO_SCRIPT_5MIN.md",
    "docs/auto/JUDGE_QA.md",
)

#: A line carrying this token is RECORDING the withdrawn wording, not asserting
#: it — the same pragma `scripts/check_withdrawn_claims.py` honours.
PRAGMA = "forbidden-ok: wc011"


@pytest.mark.parametrize("rel", SURFACES)
def test_no_surface_asserts_a_shape_the_grid_cannot_resolve(rel: str):
    grid_resolves = any(GAP_LO < w < GAP_HI for w in _sweep(DENSE))
    if grid_resolves:
        pytest.skip(
            f"the registered grid has a point strictly between {GAP_LO:.0f} m "
            f"and {GAP_HI:.0f} m, so the shape of the top is measured and this "
            f"ban does not apply. It re-arms automatically if that point goes.")
    text = (REPO / rel).read_text(encoding="utf-8")
    for line_no, line in enumerate(text.splitlines(), 1):
        if PRAGMA in line:
            continue
        for pat, what in SHAPE_ASSERTIONS:
            assert not pat.search(line), (
                f"{rel}:{line_no} {what}, while the registered buffer grid has "
                f"no measured width strictly between {GAP_LO:.0f} m and "
                f"{GAP_HI:.0f} m. Either measure it "
                f"(scripts/run_present_perimeter_arm.py --sweep-extra-m ...) or "
                f"do not write the shape.")


# --------------------------------------------------------------------------
# WC-011's spellings, checked against text the repository really shipped.
# --------------------------------------------------------------------------
# The first draft of the Korean patterns matched ZERO of the four surfaces the
# claim was live on: one had a mistyped syllable, and neither tolerated the
# markdown emphasis sitting inside the phrase. A registered spelling that
# matches nothing is worse than no registration, because it reads as protection.
# The probes below are the sentences as they stood at 97231a1.
WC011_PROBES = {
    "wc011-buffer-width-is-a-spike-ko":
        "sweep 안에서 **고원이 아니라 뾰족한 봉우리**입니다. 그래서 이 항목에서 폭은",
    "wc011-buffer-width-is-a-spike-en":
        "The 1 km row is a **spike, not a plateau**, and the last three columns say why.",
    "wc011-which-width-is-unknowable-ko":
        "그 구분에 기대어 「어느 폭이 맞는지는 그날 알 수 없다」고 말하게 되어 있습니다.",
}


def test_the_wc011_spellings_match_what_the_repository_actually_shipped():
    claims = json.loads(REGISTRY.read_text(encoding="utf-8"))["claims"]
    wc011 = next((c for c in claims if c["id"] == "WC-011"), None)
    assert wc011 is not None, "WC-011 is not in docs/auto/withdrawn_claims.json"
    by_token = {s["token"]: s["pattern"] for s in wc011["spellings"]}
    assert set(by_token) == set(WC011_PROBES), (
        f"WC-011's tokens moved: registry {sorted(by_token)}, probes "
        f"{sorted(WC011_PROBES)}")
    for token, probe in WC011_PROBES.items():
        assert re.search(by_token[token], probe), (
            f"WC-011 spelling {token!r} does not match the sentence the "
            f"repository actually shipped:\n  pattern: {by_token[token]}\n"
            f"  probe:   {probe}\n"
            f"A pattern that matches nothing registers nothing.")


def test_every_dense_grid_number_in_the_doc_is_registered():
    """The three new widths' cells are all in docs/NUMBERS.json under one prefix."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    sweep = _sweep(DENSE)
    for w in (750.0, 1250.0, 1500.0):
        assert w in sweep, f"the dense artifact has no {w:.0f} m row"
        for cell, suffix in zip(CELLS, ("recovered", "broken", "safe", "burns",
                                        "unreachable", "late")):
            key = f"ppshape_uiseong_w{int(w)}m_{suffix}"
            assert key in numbers, f"{key} is not registered"
            assert numbers[key]["value"] == sweep[w][cell], (
                f"{key} is stale: registry {numbers[key]['value']}, artifact "
                f"{sweep[w][cell]}. Re-run scripts/register_buffer_shape.py.")


def test_the_committed_artifact_still_holds_exactly_its_five_widths():
    """CHARTER §3 rule 2: this lap added an artifact, it did not move one."""
    assert sorted(_sweep(COMMITTED)) == [250.0, 500.0, 1000.0, 2000.0, 3000.0]
