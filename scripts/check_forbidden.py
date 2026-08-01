#!/usr/bin/env python
"""Scan tracked files for retired numbers and misleading terminology.

Round-3 PHASE 1-F.

TWO SEVERITIES
--------------
HARD    zero occurrences permitted. Retired values from the superseded Build A,
        or citations that misattribute the canonical model.
LABEL   permitted, but only near a qualifier. These are real numbers that belong
        to a superseded build or a different denominator, so a bare mention
        misleads even though the digits are correct.

NUMERIC BOUNDARY MATCHING
-------------------------
Every numeric pattern is wrapped as ``(?<![\\d.])VALUE(?![\\d])`` so it cannot
match inside a longer number. Without this, ``2731`` matches the coordinate
``36.500436273149326`` and ``0.874`` matches the IoU ``0.8741651819581638``,
burying real violations under noise.

LINE PRAGMAS
------------
A rule's own statement necessarily contains the thing it forbids. Suppress per
line, and only per line::

    <!-- forbidden-ok: 0.874 -->      markdown
    # forbidden-ok: 0.874            python / yaml / make
    // forbidden-ok: 0.874           js-ish

The pragma must sit on the offending line or the line directly above it, and it
suppresses ONLY the tokens it names. ``forbidden-ok: *`` is NOT supported and
there is deliberately no whole-file exemption: a file-level escape hatch becomes
a permanent one.

Run:  python scripts/check_forbidden.py
      python scripts/check_forbidden.py --list-rules
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# (token, kind, why) — kind: "num" gets boundary-wrapped, "word" gets \b...\b
HARD: list[tuple[str, str, str]] = [
    ("0.867",   "num",  "retired AUC (pre-correction Build A)"),
    ("0.8667",  "num",  "retired AUC (pre-correction Build A)"),
    ("0.8340",  "num",  "retired Build-A pooled AUC"),
    ("0.834",   "num",  "retired Build-A pooled AUC, 3-dp form"),
    ("0.8309",  "num",  "retired Build-A mean-of-folds AUC (lofo_metrics.json)"),
    ("0.8337",  "num",  "retired Build-A pooled AUC (lofo_metrics.json)"),
    ("0.8745",  "num",  "report-blocked footprint IoU"),
    ("0.874",   "num",  "report-blocked footprint IoU — measures next-overpass "
                        "GIVEN the burned area, not a from-scratch footprint"),
    ("138619",  "num",  "retired row count (canonical is 151,904)"),
    ("2731",    "num",  "retired positive count (canonical is 2,989)"),
    ("Chen",    "word", "XGBoost citation — the canonical model is sklearn "  # forbidden-ok: Chen, XGBoost
                        "HistGradientBoosting, not XGBoost"),
    ("Guestrin", "word", "XGBoost citation — see Chen"),  # forbidden-ok: Chen, Guestrin, XGBoost
    ("multi-scale", "word", "the model is single-scale (one 375 m / 500 m grid)"),  # forbidden-ok: multi-scale
    ("Multi-scale", "word", "see multi-scale"),  # forbidden-ok: multi-scale, Multi-scale
]

#: token -> regex that, if present on the line, counts as an adequate label.
LABEL: list[tuple[str, str, str, str]] = [
    ("XGBoost", "word",
     r"(?i)(superseded|legacy|build[ -]?a|abandoned|not\s+the\s+canonical|"
     r"deprecated|retired|previous|형|폐기|구|이전|레거시)",
     "must be marked as the superseded Build A"),
    ("452", "num",
     r"(?i)(superseded|legacy|build[ -]?a|retired|previous|폐기|이전|구)",
     "retired origin count — label the build it belongs to"),
    ("264", "num",
     r"(?i)(superseded|legacy|build[ -]?a|retired|previous|positives|"
     r"gangneung|폐기|이전|구)",
     "Build-A positive count for gangneung_donghae_2022"),
    ("154", "num",
     r"(?i)(superseded|legacy|build[ -]?a|retired|previous|폐기|이전|구)",
     "retired count — label the build it belongs to"),
    ("약 40%", "lit",
     r"(?i)(superseded|retired|previous|폐기|이전|구|잘못|오류|정정)",
     "retired walk-failure figure; the measured rate is 11.4 % "
     "(walk_failure_rate_pct)"),
]

#: ---------------------------------------------------------------------------
#: SCOPE: which rules apply where. Documented in docs/forbidden_check_scope.md.
#:
#: WORD rules (Chen, Guestrin, multi-scale, XGBoost) apply to EVERY tracked text  # forbidden-ok: Chen, Guestrin, multi-scale, XGBoost
#: file. A misattributed model name is wrong wherever it appears, including in
#: code comments — that is precisely where it gets copied from.
#:
#: RETIRED-NUMBER rules (452, 264, 0.834, 2731, ...) apply ONLY to authored
#: prose, i.e. `.md` files, wherever they live — including data/**/*.md, because
#: LEGACY_DO_NOT_CITE.md is an authored document that happens to sit next to the
#: artifacts it describes.
#:
#: They do NOT apply to code or artifacts:
#:   .py    `Sardoy (2008) Combust. Flame 154` is a citation; the XGBoost in
#:          spread_v2_xgb/model.py is the superseded build's own source.
#:   .json  `"n_origins": 452` is that run's own recorded value.
#:   .html/.txt/.toml/.yaml  generated payloads and machine config.
#:
#: A retired number is misleading exactly when it reads as a CURRENT CLAIM, and
#: claims live in prose. Records are evidence and must stay legible.
#:
#: Every skipped numeric match is counted and printed on every run, per file, so
#: the scope can never quietly hide anything.
def is_authored_prose(rel: str) -> bool:
    """True for files whose numbers are claims rather than records."""
    return rel.lower().endswith(".md")


SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
             "data/snapshots"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".npz", ".gz", ".tif",
                 ".nc", ".graphml", ".ipynb", ".zip", ".csv"}

# NB: the token list must allow hyphens ("multi-scale"), so it is matched  # forbidden-ok: multi-scale
# non-greedily up to a closing "-->" or end of line rather than with a
# negated class that would swallow the hyphen.
PRAGMA = re.compile(r"(?:#|//|<!--)\s*forbidden-ok:\s*(.*?)\s*(?:-->|$)")


def pattern_for(token: str, kind: str) -> re.Pattern:
    if kind == "num":
        # The lookbehind also excludes "," so a thousands separator cannot make
        # "1,264" match the token "264". A real prose mention is written ", 264"
        # (with a space), which is unaffected.
        return re.compile(r"(?<![\d.,])" + re.escape(token) + r"(?![\d])")
    if kind == "word":
        return re.compile(r"\b" + re.escape(token) + r"\b")
    return re.compile(re.escape(token))


def pragma_tokens(line: str) -> set[str]:
    out: set[str] = set()
    for m in PRAGMA.finditer(line):
        out |= {t.strip() for t in m.group(1).split(",") if t.strip()}
    return out


def tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=REPO).decode()
        files = [REPO / f for f in out.splitlines() if f]
    except Exception:  # noqa: BLE001
        files = [p for p in REPO.rglob("*") if p.is_file()]
    keep = []
    for p in files:
        rel = p.relative_to(REPO).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        keep.append(p)
    return keep


def scan(paths: list[Path]) -> tuple[list[dict], list[dict], int]:
    hard_rules = [(t, pattern_for(t, k), why, k) for t, k, why in HARD]
    label_rules = [(t, pattern_for(t, k), re.compile(lab), why, k)
                   for t, k, lab, why in LABEL]
    hard_hits: list[dict] = []
    label_hits: list[dict] = []
    n_suppressed = 0
    payload_skips: dict[str, int] = {}

    for p in paths:
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(REPO).as_posix()
        num_rules_apply = is_authored_prose(rel)
        for i, line in enumerate(lines, 1):
            allowed = pragma_tokens(line)
            if i >= 2:
                allowed |= pragma_tokens(lines[i - 2])

            for token, rx, why, kind in hard_rules:
                if not rx.search(line):
                    continue
                if kind != "word" and not num_rules_apply:
                    payload_skips[rel] = payload_skips.get(rel, 0) + 1
                    continue
                if token in allowed:
                    n_suppressed += 1
                    continue
                hard_hits.append({"file": rel, "line": i, "token": token,
                                  "why": why, "text": line.strip()[:150]})

            for token, rx, lab, why, kind in label_rules:
                if not rx.search(line):
                    continue
                if kind != "word" and not num_rules_apply:
                    payload_skips[rel] = payload_skips.get(rel, 0) + 1
                    continue
                if token in allowed:
                    n_suppressed += 1
                    continue
                if lab.search(line):
                    continue
                label_hits.append({"file": rel, "line": i, "token": token,
                                   "why": why, "text": line.strip()[:150]})
    return hard_hits, label_hits, n_suppressed, payload_skips


def report(hits: list[dict], title: str) -> None:
    if not hits:
        print(f"  {title}: none")
        return
    print(f"  {title}: {len(hits)}")
    for h in hits:
        print(f"    {h['file']}:{h['line']}  [{h['token']}]  {h['why']}")
        print(f"      | {h['text']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-rules", action="store_true")
    ap.add_argument("--label-is-error", action="store_true",
                    help="treat unlabelled LABEL hits as failures too")
    args = ap.parse_args()

    if args.list_rules:
        print("HARD (zero occurrences permitted):")
        for t, k, why in HARD:
            print(f"  {t:14s} [{k}]  {why}")
        print("\nLABEL (permitted only with a qualifier on the same line):")
        for t, k, _lab, why in LABEL:
            print(f"  {t:14s} [{k}]  {why}")
        print("\nPragma: '# forbidden-ok: TOKEN' on the line or the line above.")
        return 0

    paths = tracked_files()
    hard, label, suppressed, payload_skips = scan(paths)
    print(f"scanned {len(paths)} tracked text files "
          f"({suppressed} pragma-suppressed occurrence(s))")
    if payload_skips:
        tot = sum(payload_skips.values())
        print(f"  scope: {tot} retired-number match(es) skipped in "
              f"{len(payload_skips)} non-prose file(s) — records, not claims "
              "(docs/forbidden_check_scope.md). Word rules still applied:")
        for f, n in sorted(payload_skips.items(), key=lambda kv: -kv[1]):
            print(f"           {n:4d}  {f}")
    print()
    report(hard, "HARD violations")
    print()
    report(label, "UNLABELLED mentions")

    if hard:
        print(f"\nFAILED: {len(hard)} hard violation(s).")
        return 1
    if label and args.label_is_error:
        print(f"\nFAILED: {len(label)} unlabelled mention(s) (--label-is-error).")
        return 1
    if label:
        print(f"\nOK with warnings: {len(label)} unlabelled mention(s) — review, "
              "then either add a qualifier or a line pragma.")
        return 0
    print("\nOK — no forbidden strings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
