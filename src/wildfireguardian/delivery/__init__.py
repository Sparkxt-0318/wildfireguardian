"""Operational output layer: SMS, printable A4, village PA script.

Round-3 PHASE 3.

The 2025 Yeongnam survey (n=300) put the emergency-SMS reception rate in
Yeongdeok at 48 %, while the village PA (마을방송, 144 reports) and neighbours
(93) carried more evacuation information than SMS (112) did; for recovery
information the 이장 was the dominant channel (156 of 471). A single
smartphone-shaped output would miss most of this population, so there are three:

* :mod:`.sms` — family members and welfare workers. **DEMO_MODE only**: the
  Twilio trial account cannot verify a Korean mobile number without an upgrade,
  so this channel composes drafts and stops. ``docs/delivery_channels.md``.
* :mod:`.email` — the same two audiences, over Gmail SMTP. **This channel can
  actually send**, behind the approval gate described below.
* :mod:`.printable` — an A4 sheet for the 이장. Paper does not need charge,
  coverage, or small-screen eyesight. The most important of the four.
* :mod:`.broadcast` — plain text for a human announcer on the village PA.

:mod:`.villages` groups dispatch points into named spatial clusters. Those are
NOT 행정리; no authoritative boundary data is available to this project.

THE SAFETY CLAIM — state it this way, and not the old way
---------------------------------------------------------
The project used to say "delivery is simulated; nothing is ever sent". That was
true when every channel wrote files, and it stopped being true when the email
channel landed. Repeating it now would understate what the system does, which
is its own kind of inaccuracy. The accurate statement is:

    전달 문구는 자동으로 발송되지 않으며, 승인 권한을 가진 사람이 명시적으로
    확인한 뒤에만 발송됩니다. 발송 함수는 승인 토큰 없이 호출될 수 없습니다.

    Delivery text is never transmitted automatically. It is sent only after a
    person with approval authority has explicitly confirmed, and the send
    function cannot be called without an approval token.

Concretely, for every channel: ``send`` takes ``approval_token`` as a
positional, mandatory argument; the email path additionally defaults to
``dry_run=True``, refuses any recipient other than ``DEMO_RECIPIENT``, and is
reachable from ``scripts/send_dispatch_email.py`` only after an operator has
typed a confirmation word in full.
"""

from __future__ import annotations

from . import broadcast, email, printable, sms, villages

__all__ = ["broadcast", "email", "printable", "sms", "villages"]
