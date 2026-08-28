"""Alert escalation templates + the keypress-confirmation loop.

Session 8, Phase 3. The spec is ``docs/alert_loop.md`` — this module
implements exactly its §2 (templates) and §3 (confirmation loop), and the
invariants promised there are pinned by ``tests/test_alert_loop.py``.

Design constraints inherited from the tree:

- Place names / landmarks only, never coordinates (equipment-level constraint,
  ``docs/firefighter_consultation.md`` §7).
- Formal 합니다체 everywhere. Never 한다체.
- SMS ≤ ``sms.MAX_CHARS`` code points; broadcast sentences ≤
  ``broadcast.MAX_SENTENCE_CHARS``.
- **No telephony/SMS integration.** Text artifacts + simulated events only;
  transmission stays behind the approval statement of
  ``docs/delivery_channels.md`` §0.
- Every simulated confirmation event is tagged ``source = "synthetic"`` and
  the simulator refuses to emit anything else.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .broadcast import MAX_SENTENCE_CHARS
from .sms import MAX_CHARS as SMS_MAX_CHARS

#: The §3 counter-cue line — the direct answer to 「지금 불이 안 보이니까
#: 도망 안 간다」. One sentence, reused verbatim by every rung.
COUNTER_CUE: str = "연기가 보이면 이미 늦습니다."

#: TTS confirmation prompt (rung 2). Exactly one per call text.
TTS_CONFIRM_PROMPT: str = "대피를 시작하셨으면 1번을 눌러 주십시오."

#: The escalation ladder of docs/alert_loop.md §1, machine-readable.
RUNGS: tuple[str, ...] = ("sms", "tts_call", "village_broadcast", "door_knock")


def _about_minutes(arrival_min: float) -> int:
    """Round the arrival estimate DOWN to whole minutes (conservative)."""
    return max(0, int(arrival_min))


def build_sms_alert(landmark: str, arrival_min: float) -> str:
    """Rung 1: 재난문자 text. Landmark + time + instruction + counter-cue.

    ≤ 90 code points (asserted). The refuge name is dropped rather than the
    counter-cue when space is tight — specificity of the *threat* beats
    specificity of the destination in 90 chars.
    """
    m = _about_minutes(arrival_min)
    text = (f"[영덕군 안내] 산불이 약 {m}분 뒤 {landmark} 방면에 도달할 "
            f"것으로 예측됩니다. 지금 즉시 대피하십시오. {COUNTER_CUE}")
    if len(text) > SMS_MAX_CHARS:
        # Long landmark: compact form. The LANDMARK survives (specificity is
        # the lever — Mileti & Sorensen), the connective prose does not.
        text = (f"[영덕군 안내] {landmark} 산불 약 {m}분 뒤 도달 예측. "
                f"지금 즉시 대피하십시오. {COUNTER_CUE}")
    if len(text) > SMS_MAX_CHARS:
        raise ValueError(
            f"SMS alert exceeds {SMS_MAX_CHARS} code points ({len(text)}): "
            f"landmark {landmark!r} is too long for the SMS rung")
    return text


def build_tts_call(landmark: str, arrival_min: float, refuge_name: str) -> str:
    """Rung 2: TTS 자동전화 (landline) text, with exactly one keypress prompt."""
    m = _about_minutes(arrival_min)
    return (f"영덕군 재난안전대책본부입니다. 산불이 약 {m}분 뒤 {landmark} "
            f"방면에 도달할 것으로 예측됩니다. 지금 즉시 {refuge_name}(으)로 "
            f"대피하십시오. {COUNTER_CUE} {TTS_CONFIRM_PROMPT}")


def build_broadcast_lines(landmark: str, arrival_min: float,
                          refuge_name: str) -> list[str]:
    """Rung 3: 마을방송 lines, each ≤ 15 code points, key instruction repeated.

    The instruction is stated, then restated after the detail
    (``broadcast.py``'s repetition rule), and the counter-cue is split to fit
    the sentence cap.
    """
    m = _about_minutes(arrival_min)
    # Long refuge names are word-wrapped across lines rather than rejected —
    # the announcer reads them as one phrase; the cap is per read-aloud line.
    chunks: list[str] = []
    cur = ""
    for word in refuge_name.split():
        cand = f"{cur} {word}".strip()
        if len(cand) <= MAX_SENTENCE_CHARS:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = word
    if cur:
        chunks.append(cur)
    if chunks and len(chunks[-1]) + 4 <= MAX_SENTENCE_CHARS:
        chunks[-1] += "(으)로"
        tail = ["가시기 바랍니다."]
    else:
        tail = ["그곳으로", "가시기 바랍니다."]
    lines = [
        "주민 여러분께 알립니다.",
        "산불이 오고 있습니다.",
        f"약 {m}분 뒤 도달합니다.",
        "지금 대피하십시오.",
        *chunks,
        *tail,
        "연기가 보이면",
        "이미 늦습니다.",
        "지금 대피하십시오.",
    ]
    over = [ln for ln in lines if len(ln) > MAX_SENTENCE_CHARS]
    if over:
        raise ValueError(f"broadcast line(s) over {MAX_SENTENCE_CHARS} chars: {over}")
    return lines


# ---------------------------------------------------------------------------
# Confirmation loop (docs/alert_loop.md §3)
# ---------------------------------------------------------------------------

#: Event kinds. ``keypress_confirmed`` moves active → follow-up;
#: ``doorknock_not_evacuated`` is the ONE upward transition (follow-up →
#: active, at the original key). Nothing marks a household safe.
EVENT_KINDS: tuple[str, str] = ("keypress_confirmed", "doorknock_not_evacuated")


def _home_node(e) -> int:
    """Entry's home node, whether the entry is a DispatchEntry or a dict.

    Written this way (not ``getattr(...) or e[...]``) because node id 0 is a
    legal value and must not fall through the ``or``.
    """
    v = getattr(e, "home_node", None)
    if v is None and isinstance(e, dict):
        v = e["home_node"]
    return int(v)


@dataclass(frozen=True)
class ConfirmationEvent:
    """One resident-side event. Simulated events are ALWAYS ``synthetic``."""

    home_node: int
    t_min: float
    rung: str                       # which rung elicited it (RUNGS)
    kind: str = "keypress_confirmed"
    source: str = "synthetic"       # simulated events must keep this tag

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")
        if self.rung not in RUNGS:
            raise ValueError(f"unknown rung {self.rung!r}")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueueState:
    """The partition of the dispatch queue after applying an event stream.

    ``active`` preserves the committed ordering key (closing window
    ascending) — re-ranking is a PARTITION, never a re-scoring. ``follow_up``
    entries carry ``needs_verification = True`` and the confirming event;
    they are lower priority by construction and are never marked safe.
    """

    active: list = field(default_factory=list)          # DispatchEntry-like
    follow_up: list = field(default_factory=list)       # dicts (entry + event)

    @property
    def n_active(self) -> int:
        return len(self.active)

    @property
    def n_follow_up(self) -> int:
        return len(self.follow_up)


def apply_confirmations(dispatch: list, events: list[ConfirmationEvent]) -> QueueState:
    """Partition the dispatch queue by an event stream (docs/alert_loop.md §3).

    Deterministic and RNG-free: the outcome depends only on the queue and the
    events. Invariants (pinned by tests):

    - a ``keypress_confirmed`` household leaves the active queue;
    - a household with no event stays, at its position (silence changes
      nothing);
    - active-relative order is unchanged (partition, not re-scoring);
    - ``doorknock_not_evacuated`` RETURNS a confirmed household to the active
      queue at its original key — priority is restored, never raised;
    - duplicates and unknown-home events are no-ops;
    - every entry is in exactly one of active / follow-up.
    """
    order = {_home_node(e): i for i, e in enumerate(dispatch)}

    confirmed: dict[int, ConfirmationEvent] = {}
    for ev in sorted(events, key=lambda ev: (ev.t_min, ev.home_node)):
        if ev.home_node not in order:
            continue                                  # unknown home: no-op
        if ev.kind == "keypress_confirmed":
            confirmed.setdefault(ev.home_node, ev)    # duplicate: no-op
        elif ev.kind == "doorknock_not_evacuated":
            confirmed.pop(ev.home_node, None)         # the one upward move

    state = QueueState()
    for e in dispatch:
        node = _home_node(e)
        if node in confirmed:
            entry = e.as_dict() if hasattr(e, "as_dict") else dict(e)
            entry["needs_verification"] = True
            entry["confirmation"] = confirmed[node].as_dict()
            state.follow_up.append(entry)
        else:
            state.active.append(e)
    return state


def simulate_confirmation_events(
    dispatch: list, *, seed: int, response_rate: float = 0.4,
    rung: str = "tts_call", t_min: float = 0.0,
) -> list[ConfirmationEvent]:
    """Draw a SIMULATED confirmation stream. Every event is ``synthetic``.

    ``response_rate`` is a simulation knob, not a measured compliance rate —
    nothing in this tree measures compliance (docs/alert_loop.md §0 scope).
    Deterministic under ``seed``.
    """
    if not 0.0 <= response_rate <= 1.0:
        raise ValueError("response_rate must be in [0, 1]")
    rng = np.random.default_rng(seed)
    events: list[ConfirmationEvent] = []
    for e in dispatch:
        node = _home_node(e)
        if rng.random() < response_rate:
            events.append(ConfirmationEvent(
                home_node=int(node), t_min=float(t_min), rung=rung,
                kind="keypress_confirmed", source="synthetic"))
    return events


__all__ = [
    "COUNTER_CUE",
    "TTS_CONFIRM_PROMPT",
    "RUNGS",
    "EVENT_KINDS",
    "build_sms_alert",
    "build_tts_call",
    "build_broadcast_lines",
    "ConfirmationEvent",
    "QueueState",
    "apply_confirmations",
    "simulate_confirmation_events",
]
