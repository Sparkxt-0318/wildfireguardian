"""Tests for the alert escalation templates + confirmation loop (Session 8 P3).

Pins the docs/alert_loop.md §3 invariants: a confirmed household leaves the
active dispatch queue; an unconfirmed one does not; re-ranking is a
deterministic partition under the fixed seed; a confirmation can only lower
priority; the door-knock non-evacuation event restores (never raises) it.
"""

from __future__ import annotations

import pytest

from wildfireguardian.delivery.alert_loop import (
    COUNTER_CUE,
    TTS_CONFIRM_PROMPT,
    ConfirmationEvent,
    apply_confirmations,
    build_broadcast_lines,
    build_sms_alert,
    build_tts_call,
    simulate_confirmation_events,
)
from wildfireguardian.delivery.broadcast import MAX_SENTENCE_CHARS
from wildfireguardian.delivery.sms import MAX_CHARS


def _queue(n=6):
    """A dispatch-like queue of dicts, already priority-ordered."""
    return [{"home_node": 100 + i, "closing_window_min": 5.0 * i} for i in range(n)]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_sms_alert_shape_and_cap():
    t = build_sms_alert("신돌석장군공원", 61.7)
    assert len(t) <= MAX_CHARS
    assert "약 61분" in t                     # rounded DOWN — conservative
    assert "신돌석장군공원" in t
    assert COUNTER_CUE in t
    assert "대피하십시오" in t                # 합니다체 imperative
    assert "한다" not in t


def test_sms_alert_long_landmark_compacts_but_keeps_landmark():
    long_lm = "전통생활 정신문화 체험지구공원 서쪽 1km"
    t = build_sms_alert(long_lm, 45.0)
    assert len(t) <= MAX_CHARS
    assert long_lm in t                       # specificity survives compaction
    assert COUNTER_CUE in t


def test_tts_call_has_exactly_one_confirm_prompt():
    t = build_tts_call("신돌석장군공원", 45.0, "영덕군민공원")
    assert t.count(TTS_CONFIRM_PROMPT) == 1
    assert COUNTER_CUE in t
    assert "영덕군민공원" in t


def test_broadcast_lines_respect_sentence_cap_and_repeat_instruction():
    lines = build_broadcast_lines("신돌석장군공원", 45.0, "영덕군민공원")
    assert all(len(ln) <= MAX_SENTENCE_CHARS for ln in lines)
    assert lines.count("지금 대피하십시오.") == 2   # stated, then restated


def test_no_coordinates_anywhere():
    """No coordinate-like number (5+ digit run) in any rung's text."""
    import re
    for t in (build_sms_alert("고래산마을", 30.0),
              build_tts_call("고래산마을", 30.0, "천전공원"),
              " ".join(build_broadcast_lines("고래산마을", 30.0, "천전공원"))):
        assert not re.search(r"\d{5,}", t), t


# ---------------------------------------------------------------------------
# Confirmation loop
# ---------------------------------------------------------------------------


def test_confirmed_household_leaves_active_queue():
    q = _queue()
    ev = [ConfirmationEvent(home_node=102, t_min=10.0, rung="tts_call")]
    st = apply_confirmations(q, ev)
    assert [e["home_node"] for e in st.active] == [100, 101, 103, 104, 105]
    assert st.n_follow_up == 1
    fu = st.follow_up[0]
    assert fu["home_node"] == 102
    assert fu["needs_verification"] is True
    assert fu["confirmation"]["source"] == "synthetic"


def test_unconfirmed_household_stays_at_its_position():
    q = _queue()
    st = apply_confirmations(q, [])
    assert st.active == q and st.n_follow_up == 0


def test_active_relative_order_is_partition_not_rescoring():
    q = _queue(8)
    ev = [ConfirmationEvent(home_node=n, t_min=1.0, rung="sms")
          for n in (101, 104, 106)]
    st = apply_confirmations(q, ev)
    survivors = [e["home_node"] for e in st.active]
    assert survivors == [100, 102, 103, 105, 107]   # original order preserved


def test_doorknock_not_evacuated_returns_home_at_original_key():
    q = _queue()
    ev = [
        ConfirmationEvent(home_node=101, t_min=5.0, rung="tts_call"),
        ConfirmationEvent(home_node=101, t_min=25.0, rung="door_knock",
                          kind="doorknock_not_evacuated"),
    ]
    st = apply_confirmations(q, ev)
    # returned to active, at its original position — restored, never raised
    assert [e["home_node"] for e in st.active] == [100, 101, 102, 103, 104, 105]
    assert st.n_follow_up == 0


def test_duplicates_and_unknown_homes_are_noops():
    q = _queue(3)
    ev = [
        ConfirmationEvent(home_node=101, t_min=1.0, rung="sms"),
        ConfirmationEvent(home_node=101, t_min=2.0, rung="tts_call"),   # dup
        ConfirmationEvent(home_node=999, t_min=3.0, rung="sms"),        # unknown
    ]
    st = apply_confirmations(q, ev)
    assert st.n_active == 2 and st.n_follow_up == 1


def test_partition_is_exhaustive_and_exclusive():
    q = _queue(10)
    ev = simulate_confirmation_events(q, seed=20250603, response_rate=0.5)
    st = apply_confirmations(q, ev)
    assert st.n_active + st.n_follow_up == len(q)
    a = {e["home_node"] for e in st.active}
    f = {e["home_node"] for e in st.follow_up}
    assert not (a & f)


def test_simulator_is_deterministic_and_synthetic_tagged():
    q = _queue(10)
    e1 = simulate_confirmation_events(q, seed=20250603, response_rate=0.4)
    e2 = simulate_confirmation_events(q, seed=20250603, response_rate=0.4)
    assert e1 == e2
    assert all(ev.source == "synthetic" for ev in e1)
    st1 = apply_confirmations(q, e1)
    st2 = apply_confirmations(q, e2)
    assert [e["home_node"] for e in st1.active] == [e["home_node"] for e in st2.active]


def test_event_validation():
    with pytest.raises(ValueError):
        ConfirmationEvent(home_node=1, t_min=0.0, rung="pigeon")
    with pytest.raises(ValueError):
        ConfirmationEvent(home_node=1, t_min=0.0, rung="sms", kind="teleported")
    with pytest.raises(ValueError):
        simulate_confirmation_events(_queue(2), seed=1, response_rate=1.5)
