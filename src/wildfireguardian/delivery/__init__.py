"""Operational output layer: SMS, printable A4, village PA script.

Round-3 PHASE 3.

The 2025 Yeongnam survey (n=300) put the emergency-SMS reception rate in
Yeongdeok at 48 %, while the village PA (마을방송, 144 reports) and neighbours
(93) carried more evacuation information than SMS (112) did; for recovery
information the 이장 was the dominant channel (156 of 471). A single
smartphone-shaped output would miss most of this population, so there are three:

* :mod:`.sms` — family members and welfare workers. Sending requires an
  explicit ``approval_token`` and is off by default (``DEMO_MODE``).
* :mod:`.printable` — an A4 sheet for the 이장. Paper does not need charge,
  coverage, or small-screen eyesight. The most important of the three.
* :mod:`.broadcast` — plain text for a human announcer on the village PA.

:mod:`.villages` groups dispatch points into named spatial clusters. Those are
NOT 행정리; no authoritative boundary data is available to this project.

Nothing in this package transmits anything unless a caller both disables demo
mode and supplies an approval token.
"""

from __future__ import annotations

from . import broadcast, printable, sms, villages

__all__ = ["broadcast", "printable", "sms", "villages"]
