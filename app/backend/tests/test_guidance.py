"""The section-6 triage truth table.  THIS FILE IS THE SPEC (ARCHITECTURE.md §6).

Rules, first match wins:
1. No active fire within 30 km                                  -> SAFE
2. Fire within 30 km, but ETA > 180 min or wind not toward user -> WATCH
3. ETA <= 180 min, or (distance < 5 km and wind toward user)    -> GO
Fallback (within 30 km, ETA unknown, wind toward, distance >=5) -> WATCH
"""

from __future__ import annotations

import pytest

from guardian_app.guidance import build_cards, make_danger, triage_level

VALID_KINDS = {"action", "info", "route", "contact"}
VALID_ICONS = {"flame", "wind", "route", "phone", "shelter", "clock", "check", "home"}
VALID_ACTIONS = {"open_map", "open_route", "call", "none"}

TRUTH_TABLE = [
    # (fire_active, distance_km, eta_minutes, wind_toward_user, route_status) -> level
    # --- rule 1: no active fire within 30 km -> SAFE ----------------------
    ((False, None, None, False, "ok"), "SAFE"),
    ((False, 2.0, 10, True, "ok"), "SAFE"),       # no fire trumps everything
    ((True, None, None, True, "ok"), "SAFE"),     # unknown distance = not within 30 km
    ((True, 30.1, 10, True, "ok"), "SAFE"),       # beyond the radius, ETA ignored
    ((True, 100.0, None, True, "ok"), "SAFE"),
    # --- rule 2: within 30 km but ETA > 180 or wind away -> WATCH ---------
    ((True, 30.0, None, False, "ok"), "WATCH"),   # 30.0 km is within the radius
    ((True, 10.0, 181, True, "ok"), "WATCH"),     # ETA just above the line
    ((True, 10.0, 300, False, "ok"), "WATCH"),
    ((True, 4.0, None, False, "ok"), "WATCH"),    # close but wind away
    ((True, 3.0, 200, True, "ok"), "WATCH"),      # rule 2 fires before rule 3's
                                                  # distance clause (first match wins)
    # --- rule 3: ETA <= 180, or close + wind toward -> GO -----------------
    ((True, 10.0, 180, True, "ok"), "GO"),        # ETA boundary is inclusive
    ((True, 10.0, 60, True, "ok"), "GO"),
    ((True, 0.5, 0, True, "ok"), "GO"),
    ((True, 4.9, None, True, "ok"), "GO"),        # <5 km + wind toward, ETA unknown
    ((True, 2.0, 10, True, "no_safe_walk"), "GO"),  # route status never changes level
    ((True, 2.0, 10, True, "outside_region"), "GO"),
    # --- fallback: within 30 km, ETA unknown, wind toward, >=5 km -> WATCH
    ((True, 5.0, None, True, "ok"), "WATCH"),     # 5.0 is not < 5
    ((True, 29.0, None, True, "ok"), "WATCH"),
]


@pytest.mark.parametrize("inputs,expected", TRUTH_TABLE)
def test_triage_truth_table(inputs, expected):
    assert triage_level(*inputs) == expected


# ---------------------------------------------------------------- cards --


def _check_card_shape(card):
    for f in ("title_ko", "title_en", "body_ko", "body_en", "id"):
        assert getattr(card, f), f"empty {f} on card {card.id}"
    assert card.kind in VALID_KINDS
    assert card.icon in VALID_ICONS
    assert card.action.type in VALID_ACTIONS


def test_safe_cards():
    cards = build_cards("SAFE")
    assert [c.id for c in cards] == ["conditions", "know_shelter", "contacts", "kit"]
    assert len(cards) <= 6
    for c in cards:
        _check_card_shape(c)


def test_watch_cards():
    cards = build_cards(
        "WATCH",
        distance_km=12.0,
        bearing_text_ko="북서쪽",
        bearing_text_en="northwest",
        wind_speed_ms=9.0,
        wind_toward_user=True,
    )
    assert [c.id for c in cards] == ["fire_info", "wind", "prepare", "family", "charge"]
    assert len(cards) <= 6
    assert "북서쪽" in cards[0].body_ko and "northwest" in cards[0].body_en
    for c in cards:
        _check_card_shape(c)


def test_go_cards_with_route():
    cards = build_cards(
        "GO", route_status="ok", shelter_name_ko="가상 대피소", shelter_name_en="Test Shelter"
    )
    assert [c.id for c in cards] == ["route", "shelter", "call119", "donots"]
    assert len(cards) <= 4
    assert [c.priority for c in cards] == [1, 2, 3, 4]
    assert cards[0].kind == "route" and cards[0].action.type == "open_route"
    assert cards[2].action.type == "call" and cards[2].action.value == "119"
    for c in cards:
        _check_card_shape(c)


def test_go_cards_no_safe_walk_leads_with_call_119():
    cards = build_cards("GO", route_status="no_safe_walk")
    ids = [c.id for c in cards]
    assert ids[0] == "call119_now"
    assert "route" not in ids
    assert len(cards) <= 4
    assert len(ids) == len(set(ids)), "no duplicate cards"
    assert cards[0].action.type == "call" and cards[0].action.value == "119"
    assert ids[-1] == "donots"
    for c in cards:
        _check_card_shape(c)


def test_go_never_exceeds_four_cards():
    for status in ("ok", "no_safe_walk", "outside_region"):
        assert len(build_cards("GO", route_status=status)) <= 4


# ---------------------------------------------------------------- danger --


def test_danger_labels_bilingual():
    for level, ko, en in (("SAFE", "안전", "SAFE"), ("WATCH", "주의", "CAUTION"), ("GO", "대피", "EVACUATE")):
        d = make_danger(level, 10.0, "북서쪽", "northwest", 90, True)
        if d.level == level:
            assert d.label_ko and d.label_en
    d = make_danger("GO", 3.0, "북서쪽", "northwest", 45, True)
    assert d.label_ko == "대피" and d.label_en == "EVACUATE"
    assert "45" in d.reason_ko and "45" in d.reason_en
    d = make_danger("SAFE", None, None, None, None, False)
    assert d.label_ko == "안전" and d.reason_ko and d.reason_en
