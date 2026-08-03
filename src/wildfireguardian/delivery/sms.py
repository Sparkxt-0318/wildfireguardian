"""SMS to family members and welfare workers.

Round-3 PHASE 3.

SAFETY MODEL — read before changing anything here
-------------------------------------------------
1. ``DEMO_MODE`` defaults to **True** and only an explicit environment variable
   turns it off. In demo mode nothing leaves the machine; messages are printed.
2. :func:`send` requires an ``approval_token``. It is a positional, mandatory
   argument with no default, so a caller cannot reach the send path by
   forgetting a keyword. An absent, blank or malformed token raises before any
   provider object is constructed.
3. Credentials come from the environment only. No key is read from a file this
   repository tracks, and none is ever logged.

The generator (``scripts/generate_dispatch_outputs.py``) never calls
:func:`send`. It writes files.

MESSAGE RULES
-------------
* 90 characters maximum, counted in code points (a Korean syllable is one).
* 존댓말 throughout.
* Place names only. Coordinates are never rendered — an operator or family
  member cannot act on ``1165104, 1837119``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Hard cap on message length, in code points.
MAX_CHARS: int = 90

#: Demo mode is ON unless the environment explicitly disables it. The check is
#: deliberately strict: only the exact string "0" disables it, so a typo such as
#: WFG_SMS_DEMO_MODE=false leaves demo mode ON (the safe direction).
DEMO_MODE_ENV: str = "WFG_SMS_DEMO_MODE"
#: Credential variables. Never hard-code these; never log their values.
ENV_ACCOUNT_SID = "TWILIO_ACCOUNT_SID"
ENV_AUTH_TOKEN = "TWILIO_AUTH_TOKEN"
ENV_FROM_NUMBER = "TWILIO_FROM_NUMBER"


class ApprovalRequired(RuntimeError):
    """Raised when :func:`send` is called without a usable approval token."""


def demo_mode() -> bool:
    return os.environ.get(DEMO_MODE_ENV, "1") != "0"


def credentials_present() -> bool:
    return all(os.environ.get(k) for k in (ENV_ACCOUNT_SID, ENV_AUTH_TOKEN,
                                           ENV_FROM_NUMBER))


@dataclass(frozen=True)
class SmsMessage:
    """One rendered message, with the audit fields an operator would need."""

    recipient_role: str          # "가족" | "복지사"
    village: str
    body: str
    n_chars: int
    within_limit: bool

    def as_dict(self) -> dict:
        return {"recipient_role": self.recipient_role, "village": self.village,
                "body": self.body, "n_chars": self.n_chars,
                "within_limit": self.within_limit, "max_chars": MAX_CHARS}


def _fit(body: str) -> str:
    """Trim to MAX_CHARS on a sentence boundary rather than mid-word."""
    if len(body) <= MAX_CHARS:
        return body
    cut = body[:MAX_CHARS]
    for sep in ("。", ". ", ".", " "):
        i = cut.rfind(sep)
        if i > MAX_CHARS * 0.6:
            return cut[:i + len(sep)].strip()
    return cut.strip()


def compose_family(village: str, n_points: int, n_unreachable: int,
                   refuge: str | None = None) -> SmsMessage:
    """Message to a family member. Plain, actionable, no jargon, no numbers-as-IDs."""
    where = f" 대피처는 {refuge}입니다." if refuge else ""
    if n_unreachable:
        body = (f"[산불] {village} 구조 요청 {n_points}곳 중 {n_unreachable}곳은 "
                f"차량 진입이 어렵습니다. 무리한 이동은 삼가시고 소방 지시를 "
                f"따라 주십시오.")
    else:
        body = (f"[산불] {village} 구조 요청 {n_points}곳이 접수되었습니다. "
                f"안전한 곳에서 대기해 주십시오.{where}")
    body = _fit(body)
    return SmsMessage("가족", village, body, len(body), len(body) <= MAX_CHARS)


def compose_welfare(village: str, n_points: int, n_unreachable: int,
                    soonest_min: float | None = None) -> SmsMessage:
    """Message to a welfare worker: operational, still plain language."""
    # A closing window can already be negative — the corridor was predicted to
    # cut before the responder could arrive. Rendering that as "약 0분
    # 남았습니다" is both wrong and falsely reassuring, so an elapsed window is
    # said plainly.
    urgency = ""
    if soonest_min is not None and soonest_min == soonest_min:  # not NaN
        if soonest_min <= 0:
            urgency = " 이미 진입 시한이 지난 곳이 있습니다."
        else:
            urgency = f" 가장 급한 곳은 약 {int(soonest_min)}분 남았습니다."
    body = (f"[산불] {village} 방문 대상 {n_points}곳입니다."
            f"{urgency} 진입 불가 {n_unreachable}곳은 별도 확인 부탁드립니다.")
    body = _fit(body)
    return SmsMessage("복지사", village, body, len(body), len(body) <= MAX_CHARS)


# ---------------------------------------------------------------------------
# 459-series (resident-side, on foot) composers — Round-3 PHASE 6
# ---------------------------------------------------------------------------
#
# The two composers above describe a RESCUE VEHICLE that cannot get in. That is
# correct for the 439 series, which has a responder side. The canonical 459
# series does not: it contrasts a fire-blind walking route with a future-aware
# one and never dispatches a vehicle, so "차량 진입이 어렵습니다" would describe
# a computation that was not performed.
#
# These are separate functions rather than a flag on the originals, so no
# committed 439-series draft can change wording underneath a re-run.


def compose_family_walk(village: str, n_points: int, n_unreachable: int,
                        refuge: str | None = None) -> SmsMessage:
    """Family message for the resident-side (walking) series."""
    where = f" 대피처는 {refuge}입니다." if refuge else ""
    if n_unreachable:
        body = (f"[산불] {village} 안내 대상 {n_points}곳 중 {n_unreachable}곳은 "
                f"안전한 도보 대피로가 없습니다. 자체 이동을 삼가시고 소방 "
                f"지시를 따라 주십시오.")
    else:
        body = (f"[산불] {village} 도보 대피 안내 {n_points}곳입니다. "
                f"안전한 곳에서 대기해 주십시오.{where}")
    body = _fit(body)
    return SmsMessage("가족", village, body, len(body), len(body) <= MAX_CHARS)


def compose_welfare_walk(village: str, n_points: int, n_unreachable: int,
                         soonest_min: float | None = None) -> SmsMessage:
    """Welfare-worker message for the resident-side (walking) series."""
    urgency = ""
    if soonest_min is not None and soonest_min == soonest_min:  # not NaN
        if soonest_min <= 0:
            urgency = " 이미 대피 시한이 지난 곳이 있습니다."
        else:
            urgency = f" 가장 급한 곳은 약 {int(soonest_min)}분 남았습니다."
    body = (f"[산불] {village} 방문 대상 {n_points}곳입니다."
            f"{urgency} 도보 대피 불가 {n_unreachable}곳은 별도 확인 부탁드립니다.")
    body = _fit(body)
    return SmsMessage("복지사", village, body, len(body), len(body) <= MAX_CHARS)


def send(message: SmsMessage, to_number: str, approval_token: str) -> dict:
    """Send one message. **Requires** an explicit approval token.

    ``approval_token`` is mandatory and positional. Calling ``send(msg, num)``
    is a ``TypeError`` at the call site; passing an empty or whitespace token is
    an :class:`ApprovalRequired`. Both fire before any network object exists.

    In demo mode — the default — nothing is transmitted; the message is printed
    and a record returned.
    """
    if not isinstance(approval_token, str) or not approval_token.strip():
        raise ApprovalRequired(
            "SMS send requires a non-empty approval_token. Messages to residents "
            "and families are irreversible; there is no unsend. Obtain explicit "
            "human approval and pass its token.")
    if len(approval_token.strip()) < 8:
        raise ApprovalRequired(
            "approval_token looks like a placeholder (under 8 characters). "
            "Refusing to send.")
    if not message.within_limit:
        raise ValueError(
            f"message is {message.n_chars} chars, over the {MAX_CHARS} limit")

    if demo_mode():
        print(f"[DEMO_MODE] SMS NOT SENT -> {to_number}\n"
              f"            ({message.recipient_role}, {message.village}, "
              f"{message.n_chars} chars)\n            {message.body}")
        return {"sent": False, "demo_mode": True, "to": to_number,
                "reason": "DEMO_MODE is on; nothing was transmitted"}

    if not credentials_present():
        print("[SMS] credentials absent; nothing sent. Set "
              f"{ENV_ACCOUNT_SID}/{ENV_AUTH_TOKEN}/{ENV_FROM_NUMBER}.")
        return {"sent": False, "demo_mode": False, "to": to_number,
                "reason": "provider credentials absent"}

    from twilio.rest import Client  # noqa: PLC0415 - optional dependency

    client = Client(os.environ[ENV_ACCOUNT_SID], os.environ[ENV_AUTH_TOKEN])
    res = client.messages.create(body=message.body,
                                 from_=os.environ[ENV_FROM_NUMBER], to=to_number)
    return {"sent": True, "demo_mode": False, "to": to_number, "sid": res.sid}


__all__ = ["MAX_CHARS", "ApprovalRequired", "SmsMessage", "compose_family",
           "compose_family_walk", "compose_welfare", "compose_welfare_walk",
           "credentials_present", "demo_mode", "send"]
