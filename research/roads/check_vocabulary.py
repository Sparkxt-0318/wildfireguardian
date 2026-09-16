#!/usr/bin/env python
"""Vocabulary gate for the roads direction.

    python research/roads/check_vocabulary.py             # scan the roads tree
    python research/roads/check_vocabulary.py --self-test
    python research/roads/check_vocabulary.py --list-rules

WHY THIS FILE EXISTS
--------------------
Section 12.4.4 of the roads pre-registration scopes this direction's estimand to
**operational barrier performance**: an association between a barrier's measured
width and the absence of a lee-side burn, for barriers as they are actually used
in Korean wildfire operations, which includes their use as access routes and as
anchor lines. It forecloses the counterfactual reading a county planner would
otherwise take by default.

v0.1b said that distinction was "enforced in the same way as the claim rules: a
fixed vocabulary, used everywhere or nowhere". A6 refused that sentence, in one
line worth keeping: a fixed vocabulary that nothing checks lasts until the first
author who writes a figure caption in a hurry. This file is the check.

SCOPE
-----
`research/roads/**` and `research/reports/A3/**`, which is what A3 owns. The
program-wide version is drafted as RC-011 in section 12.4.6 of the
pre-registration and belongs in `research/FORBIDDEN_CLAIMS.md`, which A3 does not
own. Until RC-011 lands, this file holds the line inside the roads tree.

WHAT IT IS AND IS NOT
---------------------
A copy-paste ratchet, not a claim detector. It carries the same hedge guard as
`research/shared/check_research_claims.py`, so a determined overclaim dressed in
"may" escapes it. What it stops is the assertive spelling spreading by copy and
paste, which is the failure mode A6 named.

PER-LINE PRAGMA
---------------
    <!-- research-vocab-ok: RV-001 -->      markdown
    # research-vocab-ok: RV-001             python / yaml

On the offending line or the line directly above it, suppressing only the rule
ids it names. There is no whole-file exemption and no `*`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
SCOPES = ("research/roads/", "research/reports/A3/")

#: The permitted term. A line carrying it is making the scoped claim, not the
#: unscoped one, so it is spared on every rule.
PERMITTED = re.compile(r"operational barrier performance", re.IGNORECASE)

#: Same shape and same reasoning as the claims checker's hedge guard.
HEDGE = re.compile(
    r"(?:"
    r"hypothes|whether|we (?:test|ask|will|plan|aim|intend|expect)|"
    r"under test|claim under test|the question|"
    r"\bmay\b|\bmight\b|\bcould\b|\bwould\b|is expected|"
    r"cannot be read as|must never|never be written|forbidden|refus|"
    r"placeholder|illustrat|hypothetic|worked example|synthetic|"
    r"pre-?registrat|not yet|\bplan\b|\bplanned\b|"
    r"associat|confound|not causal|reverse causal|"
    r"가설|검증할|여부|예정|아직"
    r")",
    re.IGNORECASE)

#: id -> (pattern, why, catches, spares)
RULES: list[tuple[str, str, str, list[str], list[str]]] = [
    ("RV-001",
     r"(?:barrier\s+effectiveness"
     r"|effectiveness\s+of\s+(?:the\s+)?(?:barrier|road|firebreak)"
     r"|방화선\s*효과|임도\s*효과)",
     "the estimand is operational barrier performance, an association under "
     "Korean suppression practice. 'Barrier effectiveness' reads as a physical "  # research-claim-ok: RC-011
     "property of the barrier, which is the counterfactual reading section "
     "12.4.4 forecloses.",
     ["Barrier effectiveness rises with cleared width.",  # research-claim-ok: RC-011
      "We report the effectiveness of the barrier per segment.",  # research-claim-ok: RC-011
      "임도 효과가 폭에 따라 증가한다."],
     ["The estimated quantity is operational barrier performance.",
      "This cannot be read as barrier effectiveness in the physical sense.",  # research-claim-ok: RC-011
      "Whether barrier effectiveness is separable from suppression effort is "
      "the question, not the answer."]),

    ("RV-002",
     r"the\s+effect\s+of\s+(?:the\s+)?(?:road\s+)?width"
     r"|width(?:'s)?\s+effect\s+on\s+(?:breach|crossing|hold)"
     r"|(?:임도\s*)?폭(?:의|\s*)\s*효과",
     "the width coefficient is an association, not an effect. Section 1.4 "
     "states the estimand as associational and section 12.4.4 lists 'the effect "
     "of width' among the readings this direction does not support.",
     ["The effect of width is 0.3 on the logit scale.",  # research-claim-ok: RC-011
      "We estimate the effect of road width on breach.",  # research-claim-ok: RC-011
      "Width's effect on breach is reported per barrier type."],
     ["The width slope is reported with its interval.",
      "The association between width and the absence of a lee-side burn is "
      "what is estimated.",
      "The effect of width would require a counterfactual this record does not "
      "observe."]),

    ("RV-003",
     r"(?:wider|widening|\bwide\b)\s+(?:forest\s+)?roads?\s+"
     r"(?:hold|holds|held|stop|stops|stopped|prevent|prevents|block|blocks)"
     r"|넓은\s*임도(?:가|는)[^\n]{0,20}(?:막|저지|차단)",
     "H-ROADS is untested and the design is observational. A sentence of this "
     "shape is both a result claim and a counterfactual about construction "
     "policy, which section 12.4.4 refuses explicitly.",
     ["Wider roads hold fires.",  # research-claim-ok: RC-011
      "Widening roads stops the front at Korean approach angles.",
      "넓은 임도가 산불을 막는다."],  # research-claim-ok: RC-011
     ["Whether wider roads hold fires is the hypothesis, not the finding.",
      "The result cannot be read as grounds for a claim that wider roads hold "
      "fires.",
      "NIFoS states that forest roads of 6 m or wider show the most effective "
      "firebreak function; that is the claim under test."]),
]

_COMPILED = [(rid, re.compile(pat, re.IGNORECASE), why, c, s)
             for rid, pat, why, c, s in RULES]

_PRAGMA = re.compile(r"research-vocab-ok:")
#: Ids are matched by their own shape rather than by splitting on commas. A
#: markdown pragma ends in "-->", and a comma-split that swallows the arrow
#: produces "RV-002 -", which silently matches nothing and suppresses nothing.
_PRAGMA_ID = re.compile(r"RV-\d{3}")


def _pragma_ids(line: str) -> set[str]:
    m = _PRAGMA.search(line)
    if not m:
        return set()
    return {t.upper() for t in _PRAGMA_ID.findall(line[m.end():])}


def fires(line: str, rid: str, rx: re.Pattern) -> bool:
    """One line, one rule. The permitted term and the hedge guard both spare."""
    if PERMITTED.search(line):
        return False
    if HEDGE.search(line):
        return False
    return bool(rx.search(line))


def scan_text(text: str, path: str = "<text>") -> list[tuple[str, int, str, str]]:
    out = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        allowed = _pragma_ids(line) | (_pragma_ids(lines[i - 1]) if i else set())
        for rid, rx, why, _c, _s in _COMPILED:
            if rid in allowed:
                continue
            if fires(line, rid, rx):
                out.append((path, i + 1, rid, line.strip()))
    return out


#: Frozen superseded records. These cannot be edited without destroying the one
#: thing `SIGNOFF.md` section 4 says cannot be repaired afterwards, so they cannot
#: carry a per-line pragma either. Named one file at a time, never by pattern.
FROZEN = (
    "research/roads/PREREGISTRATION.md",   # pre-registration v0.1b, superseded
)


def _tracked_files() -> list[Path]:
    found: list[Path] = []
    for scope in SCOPES:
        root = REPO / scope
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix in (".md", ".py", ".yaml", ".yml", ".json"):
                if p.resolve() == HERE:
                    continue          # this file states what it forbids
                if str(p.relative_to(REPO)) in FROZEN:
                    continue          # see FROZEN
                found.append(p)
    return found


def self_test() -> int:
    bad = 0
    for rid, rx, _why, catches, spares in _COMPILED:
        for s in catches:
            if not fires(s, rid, rx):
                why = "hedge or permitted term swallowed it" if rx.search(s) \
                      else "pattern missed it"
                print("SELF-TEST FAIL %s did not catch: %r (%s)" % (rid, s, why))
                bad += 1
        for s in spares:
            if fires(s, rid, rx):
                print("SELF-TEST FAIL %s fired on a legitimate line: %r" % (rid, s))
                bad += 1
    if bad == 0:
        print("self-test ok: %d rules, both directions" % len(_COMPILED))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args()

    if args.list_rules:
        for rid, _rx, why, _c, _s in _COMPILED:
            print("%s  %s" % (rid, why))
        return 0
    if args.self_test:
        return self_test()

    rc = self_test()
    if rc:
        return rc

    hits = []
    for p in _tracked_files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits.extend(scan_text(text, str(p.relative_to(REPO))))

    if not hits:
        print("vocabulary ok: 0 violations over %s" % ", ".join(SCOPES))
        return 0
    print("VOCABULARY VIOLATIONS (%d):" % len(hits))
    for path, ln, rid, line in hits:
        print("  %s:%d  %s  %s" % (path, ln, rid, line[:110]))
    print("\nThe permitted term is 'operational barrier performance'. See section")
    print("12.4.4 and 12.4.6 of research/roads/PREREG_roads_2026-09-16_v0.2.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
