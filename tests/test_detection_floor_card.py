"""The finals detection-floor card may not drift from the registry it cites.

WFG-021 (a). The card in `docs/auto/finals/DETECTION_FLOOR_CARD.md` is the fourth
place these figures live (the artifact, `docs/NUMBERS.json`, `docs/detection_floor.md`,
now the card), and this repository's own history is that a retyped number drifts:
WFG-004 was a whole lap spent reconciling one AUC, and the 2026-09-03 survey lap had
to stop reading its figures from notes and read them out of the report instead.

So the card is allowed to exist only with this test under it. Every figure the card
cites a key for is read back out of `docs/NUMBERS.json` and compared, in its own table
row where the card tabulates it. The card is prose a judge reads at a booth; if someone
edits a digit in it, or moves one fire's delay onto another fire's line, the suite says
so.

What this file does NOT do, said plainly because an overstated test is worse than no
test: it does not prove every number on the card has a registry key. The last test is a
hand-maintained tripwire over new digits, and its escape list holds real measured
quantities that have no key of their own. That list documents each one.

The registry entries are themselves re-derived from their artifacts by
`scripts/verify_numbers.py` (`make verify`), so this test closes the last link:
card -> registry -> artifact.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CARD = REPO / "docs" / "auto" / "finals" / "DETECTION_FLOOR_CARD.md"
NUMBERS = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))["numbers"]

# what the card says -> the key it must agree with. The literal is written the way the
# card writes it, so a reader can grep the card for the left-hand side.
CLAIMS = [
    ("+22분", "det_gk2a_delay_uiseong_andong_min", 22.0),
    ("+34분", "det_gk2a_delay_gangneung_2023_min", 34.0),
    ("+64분", "det_gk2a_delay_hongseong_2023_min", 64.0),
    ("709 스텝", "det_control_steps", 709.0),
    # NOT "0.1939 ha": the registry entry itself says ORDER OF MAGNITUDE ONLY and
    # §6 says do not read the decimals, so the card rounds and the test rounds with it.
    ("약 0.2 ha", "det_size_floor_ha_tf750", 0.1939),
    ("8.328 K", "det_yeongdeok_bg_ring_median_k", 8.328),
    ("11.611 K", "det_gk2a_yeongdeok_best_delta_k", 11.611),
    ("217 스텝", "det_yeongdeok_steps_clearing_clean_threshold", 217.0),
    ("+28분", "det_yeongdeok_best_anomaly_minutes_after_report", 28.0),
]


@pytest.fixture(scope="module")
def card() -> str:
    return CARD.read_text(encoding="utf-8")


@pytest.mark.parametrize("literal,key,expected", CLAIMS, ids=[c[1] for c in CLAIMS])
def test_every_figure_on_the_card_is_the_registry_value(card: str, literal: str, key: str, expected: float):
    assert key in NUMBERS, f"the card cites {key}, which is not registered"
    assert NUMBERS[key]["value"] == pytest.approx(expected), (
        f"{key} moved to {NUMBERS[key]['value']}; the card still says {literal}"
    )
    assert literal in card, f"the card no longer states {literal} for {key}"
    assert key in card, f"the card states {literal} without naming {key}"


ROWS = [
    ("의성·안동 2025", "+22분", "det_gk2a_delay_uiseong_andong_min"),
    ("강릉 2023", "+34분", "det_gk2a_delay_gangneung_2023_min"),
    ("홍성 2023", "+64분", "det_gk2a_delay_hongseong_2023_min"),
]


@pytest.mark.parametrize("fire,literal,key", ROWS, ids=[r[0] for r in ROWS])
def test_each_delay_sits_in_its_own_fire_s_row(card: str, fire: str, literal: str, key: str):
    """Values alone are not the claim; the pairing is.

    The substring assertions above pass unchanged if 강릉's +34 and 홍성's +64 are
    swapped, and a booth card that attributes a delay to the wrong fire is wrong in
    the way a fire scientist notices first. So each table row is matched whole.
    """
    row = next((ln for ln in card.splitlines() if ln.startswith("|") and fire in ln), None)
    assert row is not None, f"no table row for {fire}"
    assert literal in row, f"{fire}'s row does not state {literal}"
    assert key in row, f"{fire}'s row does not name {key}"
    others = [k for _, _, k in ROWS if k != key]
    assert not [k for k in others if k in row], f"{fire}'s row also names another fire's key"


def test_the_false_alarm_count_is_zero_and_the_card_says_upper_bound():
    """A zero numerator is a bound, not a rate; §5 says so three times and so must the card."""
    assert NUMBERS["det_false_alarm_steps"]["value"] == 0.0
    text = CARD.read_text(encoding="utf-8")
    assert "709 스텝 중 0건" in text
    assert "상한" in text


def test_the_card_keeps_the_three_constraints_the_row_put_on_it():
    """WFG-021 constraints: never 'every fire'; no KMA direction experiment; no 1.28 km."""
    text = CARD.read_text(encoding="utf-8")
    assert "모든 산불" not in text.replace("「모든 산불」이라고 말하지 않습니다", "")
    assert "1.28" not in text
    assert "gk2a_direction_experiment" not in text


def test_the_card_states_the_reference_time_caveat_first():
    """§1 is the most important clue in the whole measurement; a card that drops it lies."""
    text = CARD.read_text(encoding="utf-8")
    assert "신고 시각" in text and "발화" in text
    assert text.index("기준 시각") < text.index("+22분"), "the caveat must precede the numbers"


def test_the_card_does_not_claim_the_satellite_buys_time():
    text = CARD.read_text(encoding="utf-8")
    assert "시간을 벌어준다는 주장" in text, "the withdrawn claim must stay named as not-claimed"
    assert "영덕" in text and "교란" in text


def test_the_card_carries_no_number_this_test_has_not_been_shown(card: str):
    """A tripwire, and it is worth being exact about what it is and is not.

    It does NOT prove every figure on the card has a registry key. It compares the
    digit-strings in the card against a list this file maintains by hand, so its only
    real power is over numbers **added later**: a lap that types a new figure onto the
    card trips it and has to justify the addition here. That is the failure mode
    `docs/detection_floor.md` §4 had to retract in writing — four numbers that were in
    no committed artifact.

    The escape list below is the honest part. `66`, `3`, `3.09`, `22`, `375`, `0.4`,
    `95`, `283`, `6`, `8` are measured quantities with no key of their own; they are
    admissible because each travels inside the caveat or derivation text of a
    registered `det_*` entry or of `docs/detection_floor.md`, which is lineage, not
    enforcement. Anything moved from this list to the card's prose without that
    lineage is a §3 rule 3 violation that this test will not catch for you.
    """
    allowed = {str(v) for _, _, v in CLAIMS} | {f"{v:g}" for _, _, v in CLAIMS}
    allowed |= {
        # section numbers and years, which are labels, not measurements
        "1", "4", "5", "9", "10", "12", "2022", "2023", "2025", "021", "048",
        # backlog/session identifiers and the emergency number
        "19", "119",
        # measured quantities carried by a registered entry's caveat or by
        # docs/detection_floor.md, named here so a reader can check each one:
        "2",      # GK2A AMI 2 km pixel / 2-minute cadence (det_* caveat: "GK2A AMI LA 2 km")
        "3",      # the clean-background threshold, ~3 K (§4)
        "3.09",   # ...its exact value, yeongdeok_background_contamination.json
        "6",      # §6, and the +6…+8 K daytime solar-reflection contrast (§4)
        "8",      # §8, and the upper end of that contrast range
        "8.6",    # the size floor's sensitivity to assumed flame temperature (§6)
        "22",     # the contaminated threshold, 22 K (§4)
        "66",     # km from 의성 to 영덕 (§4)
        "283",    # the counterfactual's denominator (§4)
        "375",    # VIIRS resolution in metres (§8)
        "750",    # Tf assumption behind det_size_floor_ha_tf750 (its own key name)
        "0.1",    # the order-of-magnitude range 0.1-1 ha (§6)
        "0.2",    # the rounded size floor, from det_size_floor_ha_tf750
        "0.4",    # the 95 % upper bound per step, in percent (§5)
        "95",     # ...its confidence level
        "709", "0",  # det_control_steps and det_false_alarm_steps
    }
    bare = set(re.findall(r"\d+(?:\.\d+)?", card))
    unexplained = sorted(bare - allowed)
    assert not unexplained, f"figures on the card with no registry key and no in-place definition: {unexplained}"
