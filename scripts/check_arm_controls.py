#!/usr/bin/env python
"""Fail if an arm changes the feature count without a matched control.

Session 13 Phase 4. Session 12 established, and Session 13 quantified, that
adding columns raises pooled AUC on its own: over 60 draws of two PURE NOISE
columns the pooled delta is centred at +0.0041 with sd 0.0040, and far-band
spans -0.0363 to +0.0425 (docs/column_addition_envelope.json). An arm that
changes the feature count and reports a gain without a matched null has not
reported a result.

This gate makes that a rule the repository enforces rather than a paragraph it
remembers. It checks three things against docs/arm_protocol.json:

1. every ``arm`` value used in docs/NUMBERS.json is declared in the protocol;
2. every declared arm whose feature count differs from the baseline's carries
   ``control_required: true``, a ``control_arm`` and a ``control_number_key``;
3. that ``control_number_key`` is actually a registered number.

⚠ WHAT IT DOES NOT CHECK. It cannot tell whether the control was drawn on the
matching feature count — Arm D added seven columns and is checked against a
two-column envelope, which the protocol records as an inexact substitution. A
gate that claimed otherwise would be lying with a green tick.

Run:  python scripts/check_arm_controls.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROTOCOL = REPO / "docs" / "arm_protocol.json"
NUMBERS = REPO / "docs" / "NUMBERS.json"


def main() -> int:
    if not PROTOCOL.exists():
        print(f"FAIL: {PROTOCOL.relative_to(REPO)} missing")
        return 1
    proto = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    nums = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]

    arms = proto["arms"]
    baseline_n = proto["baseline_n_features"]
    problems: list[str] = []

    used = sorted({e.get("arm") for e in nums.values() if e.get("arm")})
    for a in used:
        if a not in arms:
            problems.append(
                f"arm {a!r} appears in NUMBERS.json but is not declared in "
                f"{PROTOCOL.name} — declare it, with or without a control")

    for name, spec in arms.items():
        n = spec.get("n_features")
        changed = n is not None and n != baseline_n
        if spec.get("is_control"):
            # The null cannot be its own null. Exempt, explicitly and by name.
            if not spec.get("reason_no_control"):
                problems.append(f"arm {name!r} is_control but gives no reason_no_control")
            continue
        if changed and not spec.get("control_required"):
            problems.append(
                f"arm {name!r} declares {n} features against a baseline of "
                f"{baseline_n} but sets control_required=false")
        if not spec.get("control_required"):
            if not changed and not spec.get("reason_no_control"):
                problems.append(
                    f"arm {name!r} has no control and no reason_no_control")
            continue
        for field in ("control_arm", "control_number_key"):
            if not spec.get(field):
                problems.append(f"arm {name!r} requires a control but has no {field}")
        key = spec.get("control_number_key")
        if key and key not in nums:
            problems.append(
                f"arm {name!r} names control_number_key {key!r}, which is not a "
                f"registered number")
        ctrl = spec.get("control_arm")
        if ctrl and ctrl not in arms:
            problems.append(f"arm {name!r} names control_arm {ctrl!r}, undeclared")

    print(f"=== arm controls ({len(arms)} declared, {len(used)} in use) ===")
    if problems:
        print(f"\nFAILED: {len(problems)} problem(s):\n")
        for p in problems:
            print("  " + p)
        print("\n  An arm that changes the feature count must be placed against a")
        print("  matched noise null. See docs/arm_protocol.md.")
        return 1

    controlled = [n for n, s in arms.items() if s.get("control_required")]
    retro = [n for n, s in arms.items() if s.get("status") == "RETROSPECTIVE"]
    print(f"\nOK — {len(controlled)} arm(s) require a control and all name a "
          f"registered one"
          + (f"; {len(retro)} retrospective ({', '.join(retro)})" if retro else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
