"""The finals detection-floor card may not drift from the registry it cites.

WFG-021 (a). The card in `docs/auto/finals/DETECTION_FLOOR_CARD.md` is the fourth
place these figures live (the artifact, `docs/NUMBERS.json`, `docs/detection_floor.md`,
now the card), and this repository's own history is that a retyped number drifts:
WFG-004 was a whole lap spent reconciling one AUC, and the 2026-09-03 survey lap had
to stop reading its figures from notes and read them out of the report instead.

So the card is allowed to exist only with this test under it. Every figure the card
states is read back out of `docs/NUMBERS.json` and compared. The card is prose a judge
reads at a booth; if someone edits a digit in it, the suite says so.

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
    ("0.1939 ha", "det_size_floor_ha_tf750", 0.1939),
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


def test_the_card_carries_no_number_that_has_no_registry_key():
    """Any bare decimal in the card must be one of the values it cites, or a section number.

    This is the check that makes the card safe to copy onto a screen: a figure that
    appears here and nowhere in `docs/NUMBERS.json` is exactly the failure mode
    `docs/detection_floor.md` §4 had to retract in writing.
    """
    allowed = {str(v) for _, _, v in CLAIMS} | {f"{v:g}" for _, _, v in CLAIMS}
    # section numbers, the 3 K / 22 K threshold pair quoted from §4, geometry and
    # sample sizes that the prose defines in place, and the 95 % bound arithmetic.
    allowed |= {"1", "3", "4", "5", "6", "8", "9", "10", "12", "2", "66", "750", "375",
                "0.4", "95", "22", "64", "2022", "2023", "2025", "021", "048", "0.1", "709",
                "0",      # det_false_alarm_steps, the zero numerator
                "19",     # Session 19, the measurement this card summarises
                "119"}    # the emergency number, not a measurement
    bare = {m for m in re.findall(r"\d+(?:\.\d+)?", CARD.read_text(encoding="utf-8"))}
    unexplained = sorted(bare - allowed)
    assert not unexplained, f"figures on the card with no registry key and no in-place definition: {unexplained}"
