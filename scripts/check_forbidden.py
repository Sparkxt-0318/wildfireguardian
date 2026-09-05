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
    # ------------------------------------------------------------------
    # CLAIM FORMS — PHASE 25 STEP 0 (2026-08-13). Not retired NUMBERS but
    # retired SENTENCE SHAPES. The decision-shift measurement was scoped down
    # after a census: the defect COUNT, the region COUNT and the novelty claim
    # were each checked and none is supported. docs/decision_shift.md §1.
    #
    # ⚠ These are `kind="claim"`: the token IS the regex, and like every
    # non-word rule they apply to authored prose (.md) only.
    #
    # ⚠ VALIDATED BEFORE ADDING, both directions — the bar this repository
    # sets in docs/region_literals.md §5 ("a detector that always fires is as
    # useless as one that never does"). Against the tracked .md tree: 0
    # matches for all five. Against the six overclaim spellings they exist to
    # stop: 6/6 caught. Against five legitimate neighbours — "두 건의 …
    # 결함", "세 지역의 커버리지 공변량", "처음 보는 사람도", "the first
    # slice of the hazard field", "n = 3" — 0/5 fired.
    (r"(?<![\d.,])(?:30|29|31)\s*건[^\n]{0,25}결함", "claim",
     "the defect COUNT as a headline. 156 census records collapse to 2 events "
     "with a measured decision shift — docs/decision_shift.md §1"),
    (r"(?i)\bN\s*=\s*30\b", "claim", "see the 30건 rule"),
    (r"세\s*지역[^\n]{0,40}(?:판정|이동)[^\n]{0,20}(?:실측|측정)", "claim",
     "NO defect moved all three regions. Event 1 moved two, event 2 moved one "
     "— docs/decision_shift.md §3"),
    (r"(?:처음|최초)[^\n]{0,40}(?:체계적으로\s*)?실측", "claim",
     "novelty is UNVERIFIED. Li et al. 2025 supports that the gap exists, not "
     "that this is the first work in it — docs/decision_shift.md §6"),
    (r"(?i)\bfirst\b[^\n]{0,40}\bsystematic(?:ally)?\b[^\n]{0,30}\bmeasur",
     "claim", "see the 처음/최초 rule"),
]

#: token -> regex that, if present on the line, counts as an adequate label.
LABEL: list[tuple[str, str, str, str]] = [
    # forbidden-ok: XGBoost
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

#: How many lines either side of a hit count as "near" for LABEL_NEAR.
#: ⚠ MEASURED, NOT CHOSEN. Against the tree before and after the 2026-08-08
#: caveat pass, on the six LABEL_NEAR tokens:
#:
#:     window   false positives (corrected tree)   detections (pre-fix tree)
#:     same line              37                            42
#:     ±3                     14                            31
#:     ±10                     6                            23      <- adopted
#:     ±25                     5                            17
#:
#: **The same-line rule that LABEL uses cannot work here.** The natural way to
#: caveat a TABLE is a block quote above it, not a suffix on every row, so 88 %
#: of same-line "findings" landed on content that was already correctly marked.
#: LABEL's five tokens are single prose mentions, which is why same-line suits
#: them. Widening past ±10 buys one fewer false positive and loses six
#: detections.
NEAR_WINDOW: int = 10

#: A label that makes a retired value legible as history rather than as a claim.
#: Deliberately generous and bilingual: the cost of accepting a weak marker is
#: one missed finding, and the cost of rejecting a real one is a checker people
#: start ignoring.
NEAR_LABEL: str = (
    r"(?i)(미확립|철회|withdraw|not\s+establ|제출\s*시점|정본|폐기|이전|구\s|"
    r"superseded|legacy|retired|previous|reverted|되돌려|historical|"
    r"earlier\s+reading|no\s+longer|was\s+headed|used\s+to\s+read|"
    # ⚠ "a single point estimate whose spread was never measured" IS the caveat.
    # auc_intervals.md states exactly that and was being reported as unlabelled.
    r"single\s+point\s+estimate|deferred|future\s+work|unmeasured|"
    # ⚠ English docs draw the contrast with "canonical", Korean ones with 정본.
    # multi_region.md §5 says "the question has lost its premise ... on the
    # canonical field Yeongdeok's core advances fastest" — that IS the caveat,
    # and omitting the English word reported it as bare.
    #
    # ⚠ NOT bare "canonical". This repository calls its current model the
    # "canonical reference", and a baseline table row saying exactly that, eight
    # lines above a retired ratio, masked a real finding in docs/baselines.md.
    # Only the CONTRASTIVE usage counts: the canonical FIELD or RE-RUN, i.e. the
    # corrected lineage a retired value is being set against.
    r"canonical\s+(field|장|re-?run|reconstruction|recomputation|value)|"
    r"lost\s+its\s+premise)")

#: token -> (kind, why). Checked with NEAR_LABEL over ±NEAR_WINDOW lines.
#:
#: ⚠ THIS LIST IS THE CHECK'S ENTIRE SCOPE — see the limitation in
#: docs/forbidden_check_scope.md §"What LABEL_NEAR cannot do".
LABEL_NEAR: list[tuple[str, str, str]] = [
    ("440 / 17 / 3", "lit",
     "retired 459-series counts (reverted-run hazard field); canonical is "
     "414 / 42 / 2"),
    ("440/17/3", "lit", "see '440 / 17 / 3'"),
    ("438 / 18 / 3", "lit",
     "submission-time 459-series counts; canonical is 458 — 414 / 42 / 2"),
    # ⚠ The boundary matters: docs/OVERNIGHT_REPORT_SESSION4.md carries 1.44×
    # and 18.3× for the physics model's LFMC x wind decomposition, which is a
    # different quantity entirely. `(?<![\d.])` keeps those out.
    ("44×", "ratio",
     "withdrawn severity-vs-direction ratio — six-feature sum vs one variable, "
     "on a 0.25° grid that cannot resolve local wind"),
    ("severity ≫ direction", "sevdir", "withdrawn conclusion — see 44×"),
    ("3.70 %", "lit",
     "retired future-aware-only share (reverted field); canonical is 9.17 %"),
    ("+1.2 %", "lit",
     "retired Yeongdeok core growth (reverted field); canonical is +316.1 %"),
]

#: ⚠ THE RATCHET, AND EVERY ENTRY CARRIES ITS REASON.
#: Same idea as KNOWN_DASHES and KNOWN_REGION_LITERALS: the floor is where the
#: tree stands today and may only go down. An entry here has been LOOKED AT.
KNOWN_NEAR_UNLABELLED: dict[str, int] = {
    # Describes what a SCRIPT prints ("...and severity ≫ wind direction
    # (skipped if the dataset is absent)"), not a claim the document makes. The
    # withdrawal is stated twice elsewhere in the same file.
    "docs/ROUTING_INTEGRATION_REPORT.md": 1,
    # The body of a submission-time report, left verbatim ON PURPOSE: its header
    # carries the marker and the instruction was to preserve the body as written.
    "docs/REPORT_ROUND2_P2.md": 1,
    # 439-series five-category context ("the five originals are still
    # 440/17/3/0/0"), a different lineage and denominator from the 459 series.
    "docs/HANDOFF_ROUND3.md": 1,
}

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
# forbidden-ok: XGBoost
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
             "data/snapshots",
             # ⚠ Agent/IDE tooling, not project prose. The first tracked
             # skill bundle (c881714) tripped the scanner with oklch colour
             # components reading "264" and a slide-template author's
             # name  # forbidden-ok: Chen
             # — none of them claims anything about this project's
             # numbers. Nothing under .claude/ is a document a judge reads.
             ".claude"}
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".npz", ".gz", ".tif",
                 ".nc", ".graphml", ".ipynb", ".zip", ".csv"}

# NB: the token list must allow hyphens ("multi-scale"), so it is matched  # forbidden-ok: multi-scale
# non-greedily up to a closing "-->" or end of line rather than with a
# negated class that would swallow the hyphen.
PRAGMA = re.compile(r"(?:#|//|<!--)\s*forbidden-ok:\s*(.*?)\s*(?:-->|$)")


def pattern_for(token: str, kind: str) -> re.Pattern:
    if kind == "claim":
        # ⚠ The token IS the pattern. Claim rules match a SENTENCE SHAPE, not a
        # value, so there is nothing to escape and nothing to boundary-wrap.
        # They are deliberately narrow: each was measured against the tracked
        # tree (0 hits) and against its own overclaim spellings (all caught)
        # before being added. A claim rule that fires on ordinary prose would
        # be retired within a week and take the real ones with it.
        return re.compile(token)
    if kind == "ratio":
        # ⚠ "44×" must not match "1.44×" or "18.3×". The lookbehind rejects a
        # preceding digit or decimal point, which is what separates the withdrawn
        # severity ratio from the physics model's LFMC x wind decomposition in
        # docs/OVERNIGHT_REPORT_SESSION4.md. Both × and x are accepted because
        # both are written in this repository.
        #
        # ⚠ NO TRAILING \\b. The first version had one and matched NOTHING
        # for the "44×" form: × is not a word character, so \\b between × and
        # the following "*" (in "**44×**") can never hold. It silently passed
        # the MODEL_CARD line it was written for, and only the ASCII "44x"
        # spelling ever matched.
        #
        # ⚠ DIGIT VARIANTS ARE THE SAME RATIO. The measured value is 43.69,
        # so "43.69×", "43.7×" and "44×" are one claim in three roundings —
        # and the 44-only pattern let `43.69×` sit uncaveated in
        # docs/REPRODUCE.md's expected-results table for months (Round-4
        # A4-3). `4[34](?:\.\d+)?` covers the roundings; the trailing
        # `(?!\s*\d)` keeps out DIMENSIONS, where × separates two numbers —
        # walk_bbox_coverage.md's "43.5 × 22.5 km" grid is not a ratio.
        return re.compile(r"(?<![\d.])4[34](?:\.\d+)?\s*[×x](?!\s*\d)")
    if kind == "sevdir":
        # Both orderings and both languages, with any of the comparison glyphs.
        return re.compile(
            r"(?i)(severity\s*[≫>]{1,2}\s*(wind\s*)?direction|"
            r"세기\s*[≫>]{1,2}\s*풍향)")
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
    """Tracked files, PLUS files staged for the commit about to be made.

    ⚠ SESSION 19 FIX FOR A VACUOUS GATE. This used ``git ls-files`` alone, which
    lists only ALREADY-tracked files. A brand-new document was therefore
    invisible to this gate until the commit that added it had already been
    made — so the habit of running the gates and then ``git add -A && git
    commit`` checked everything EXCEPT the files the commit was introducing.
    Every Session 18 commit's "all gates green" line was, for its new files,
    true of nothing. The gate was not wrong about what it saw; it simply could
    not see the thing most likely to be wrong.

    Adding ``git diff --cached --name-only`` makes the gate correct under BOTH
    orderings — stage-then-gate and gate-then-stage — instead of relying on the
    author remembering which one is safe.
    """
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=REPO).decode()
        names = {f for f in out.splitlines() if f}
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=d"],
            cwd=REPO).decode()
        names |= {f for f in staged.splitlines() if f}
        files = [REPO / f for f in sorted(names) if (REPO / f).is_file()]
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
    near_rules = [(t, pattern_for(t, k), why) for t, k, why in LABEL_NEAR]
    near_label = re.compile(NEAR_LABEL)
    hard_hits: list[dict] = []
    label_hits: list[dict] = []
    near_hits: list[dict] = []
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

            # ⚠ LABEL_NEAR: the label may be anywhere within ±NEAR_WINDOW lines,
            # because a table is caveated by a block quote above it rather than
            # by a suffix on every row. `i` is 1-based, so the slice is i-1
            # centred.
            if not num_rules_apply:
                continue
            lo = max(0, i - 1 - NEAR_WINDOW)
            window = "\n".join(lines[lo:i + NEAR_WINDOW])
            for token, rx, why in near_rules:
                if not rx.search(line):
                    continue
                if token in allowed:
                    n_suppressed += 1
                    continue
                if near_label.search(window):
                    continue
                near_hits.append({"file": rel, "line": i, "token": token,
                                  "why": why, "text": line.strip()[:150]})
    return hard_hits, label_hits, near_hits, n_suppressed, payload_skips


def over_near_ratchet(hits: list[dict]) -> list[dict]:
    """Findings above the recorded floor, per file. The floor may only go DOWN."""
    by_file: dict[str, list[dict]] = {}
    for h in hits:
        by_file.setdefault(h["file"], []).append(h)
    out: list[dict] = []
    for rel, items in by_file.items():
        allowed = KNOWN_NEAR_UNLABELLED.get(rel, 0)
        if len(items) > allowed:
            out += items[allowed:]
    return out


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
    # Unlabelled mentions are ERRORS by default as of 2026-08-01, the day the
    # count first reached zero. A checker that always reports 89 findings is a
    # checker nobody reads; at zero, the next finding is a real signal.
    ap.add_argument("--allow-unlabelled", action="store_true",
                    help="downgrade unlabelled LABEL hits to warnings (default: "
                         "they are failures)")
    args = ap.parse_args()

    if args.list_rules:
        print("HARD (zero occurrences permitted):")
        for t, k, why in HARD:
            print(f"  {t:14s} [{k}]  {why}")
        print("\nLABEL (permitted only with a qualifier on the same line):")
        for t, k, _lab, why in LABEL:
            print(f"  {t:14s} [{k}]  {why}")
        print(f"\nLABEL_NEAR (caveat required within ±{NEAR_WINDOW} lines):")
        for t, k, why in LABEL_NEAR:
            print(f"  {t:22s} [{k}]  {why}")
        print("\nPragma: '# forbidden-ok: TOKEN' on the line or the line above.")
        return 0

    paths = tracked_files()
    hard, label, near, suppressed, payload_skips = scan(paths)
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
    print()
    near_over = over_near_ratchet(near)
    allowed_near = sum(KNOWN_NEAR_UNLABELLED.values())
    report(near_over, f"RETIRED CLAIMS without a nearby caveat (±{NEAR_WINDOW} lines)")
    if not near_over and allowed_near:
        print(f"    ({allowed_near} known and recorded in KNOWN_NEAR_UNLABELLED)")

    if hard:
        print(f"\nFAILED: {len(hard)} hard violation(s).")
        return 1
    if label and not args.allow_unlabelled:
        print(f"\nFAILED: {len(label)} unlabelled mention(s). Add a qualifier on "
              "the line, or a line pragma if the line's job is to name the value. "
              "The count has been zero since 2026-08-01 — this is a real finding.")
        return 1
    if near_over and not args.allow_unlabelled:
        print(f"\nFAILED: {len(near_over)} retired claim(s) stated with no "
              f"caveat within {NEAR_WINDOW} lines. Add the marker beside it — "
              "the value itself must NOT be deleted, it is the record of that "
              "run. If the mention is legitimately bare, add a line pragma or an "
              "entry to KNOWN_NEAR_UNLABELLED with its reason.")
        return 1
    if label or near_over:
        print(f"\nOK with warnings: {len(label)} unlabelled mention(s), "
              f"{len(near_over)} uncaveated retired claim(s) (--allow-unlabelled).")
        return 0
    print("\nOK — no forbidden strings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
