#!/usr/bin/env python
"""Claims-discipline and em-dash gate for the research program.

    python research/shared/check_research_claims.py            # scan research/**
    python research/shared/check_research_claims.py --self-test
    python research/shared/check_research_claims.py --list-rules

Two things are checked over tracked files under ``research/``:

1. **Em dashes.** The count must be zero. This is a program scope rule and it
   has no pragma and no exemption.
2. **Forbidden claim shapes.** The three research questions are hypotheses
   (``research/FORBIDDEN_CLAIMS.md``). Writing one as an established result is
   forbidden until the validation agent signs the direction off.

HOW A RULE DECIDES
------------------
A line fires a rule when it matches the rule's ASSERTIVE pattern and does NOT
match the shared :data:`HEDGE` pattern. The hedge guard is what keeps the
checker usable: the program wants agents writing "we test whether a 6 m road is
sufficient", and a detector that fires on that sentence is a detector agents
learn to route around.

⚠ WHAT THIS IS AND IS NOT. The hedge guard is also this checker's main
limitation, and it is deliberate. Any sentence carrying a hedge word escapes
every rule, so a determined overclaim dressed in "may" is not caught. This is a
**copy-paste ratchet, not a claim detector** (the same limit
``docs/withdrawn_claims.md`` records for the repository's own registry). It stops
the assertive spelling from spreading by copy and paste across the tree. It does
not replace A6's read.

PER-LINE PRAGMA
---------------
A rule's own statement necessarily contains the thing it forbids::

    <!-- research-claim-ok: RC-001 -->     markdown
    # research-claim-ok: RC-001            python / yaml

The pragma sits on the offending line or the line directly above it, and
suppresses ONLY the rule ids it names. ``research-claim-ok: *`` is not
supported and there is deliberately no whole-file exemption, because a
file-level escape hatch becomes a permanent one.

VALIDATED BOTH DIRECTIONS
-------------------------
Every rule carries a ``catches`` corpus of overclaim spellings it must fire on
and a ``spares`` corpus of legitimate hedged neighbours it must not fire on.
``--self-test`` runs both and is part of the gate. This is the bar
``docs/region_literals.md`` section 5 sets for this repository: a detector that
always fires is as useless as one that never does.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCOPE = "research/"

EM_DASH = "\u2014"          # written as an escape so this file has none

#: A line carrying any of these is treated as hedged and fires no claim rule.
#: Bilingual and deliberately generous. See the module docstring for why, and
#: for what that costs.
HEDGE = re.compile(
    r"(?:"
    r"hypothes|whether|we (?:test|ask|will|plan|aim|intend|expect)|"
    r"under test|claim under test|the question|not the (?:finding|answer|result)|"
    r"\bmay\b|\bmight\b|\bcould\b|\bwould\b|is expected|to be (?:fitted|estimated|tested)|"
    r"placeholder|illustrat|hypothetic|worked example|synthetic|"
    r"pre-?registrat|not yet|\bonce\b|\bplan\b|\bplanned\b|"
    r"(?<!no )prior (?:work|art|literature|study|studies)|literature reports|elsewhere|"
    r"to our knowledge|we are aware|unverified|not verified|pending|"
    r"E-?value|associat|confound|reverse causal|not causal|"
    r"held[- ]out|hold[- ]out|test year|\bfold\b|cross-?validat|block cv|"
    r"is not used|not used for fitting|not Korean|"
    r"operational barrier performance|width slope|association between|"
    r"가설|검증할|여부|예정|아직|선행\s*연구|예시"
    r")",
    re.IGNORECASE)

#: id -> (pattern, why, catches, spares). All patterns compile with IGNORECASE.
#:
#: Patterns target the ASSERTIVE spelling only. Where Korean puts the verb last
#: and English puts it in the middle, the pattern carries both orderings as
#: explicit alternatives rather than trying to be clever with one.
RULES: list[tuple[str, str, str, list[str], list[str]]] = [

    ("RC-001",
     # English: 6 m ... is/proves ... sufficient|effective
     # Korean:  6 m ... 충분|효과적 ... 확인|입증|이다  (verb final)
     r"(?:6\s*m|6\s*미터|육\s*미터|6\s*m\s*이상)[^\n]{0,70}"
     r"(?:"
     r"(?:is|are|was|were|proves?|proved|confirm\w*|demonstrat\w*|shown to be)"
     r"[^\n]{0,30}(?:sufficient|insufficient|enough|not enough|effective|ineffective)"
     r"|"
     r"(?:충분|불충분|효과적)[^\n]{0,30}(?:확인|입증|이다|였다|된다|한다)"
     r")",
     "H-ROADS is untested. The NIFoS 6 m claim is prior art to be tested, not a "
     "result to restate or to refute.",
     ["A 6 m forest road is sufficient to hold a front.",
      "Our work confirmed 6 m roads are effective firebreaks.",
      "6 m 임도는 충분하다는 것이 확인되었다.",
      "Roads 6 m or wider proved effective against the front."],
     ["We test whether a 6 m forest road is sufficient to hold a front.",
      "NIFoS states that forest roads 6 m or wider are the most effective "
      "firebreak; this is the claim under test.",
      "Whether 6 m is enough is the hypothesis, not the finding.",
      "6 m 이상 임도가 충분한지 여부를 검증할 예정이다."]),

    ("RC-002",
     r"(?:breach|crossing)\s+probabilit(?:y|ies)[^\n]{0,40}"
     r"(?:is|was|were|are|=|of)\s*(?<![\d.])\d+(?:\.\d+)?\s*(?:%|percent)?",
     "No breach dataset exists yet. Any breach number is a placeholder until "
     "A6 signs the pre-registration and the fit.",
     ["The breach probability is 0.42 for a 6 m road.",
      "Measured breach probability of 31 % at 8 m.",
      "Breach probabilities are 0.42 and 0.17 respectively."],
     ["The breach probability is 0.42 in this worked example, which uses "
      "synthetic inputs and is illustrative only.",
      "Breach probability will be estimated per segment once the labels exist.",
      "We will report a breach curve with uncertainty."]),

    ("RC-003",
     # English: burned slope ... recover ... N years
     # Korean:  산불 후 사면 ... N년 ... 회복  (verb final)
     r"(?:burn(?:ed|t)|post-?fire|화재\s*후|산불\s*후|산불\s*피해)[^\n]{0,60}"
     r"(?:slopes?|사면|비탈|산지)[^\n]{0,70}"
     r"(?:"
     r"(?:return|returns|returned|recover|recovers|recovered)[^\n]{0,50}"
     r"(?<![\d.])\d+(?:\.\d+)?\s*(?:years?|yrs?)"
     r"|"
     r"(?<![\d.])\d+(?:\.\d+)?\s*년[^\n]{0,30}(?:회복|복원|정상)"
     r")",
     "H-SLIDE is untested. A recovery window in years is a result, and there "
     "is no fit.",
     ["Burned slopes return to baseline after 6 years.",
      "Post-fire slopes recovered within 4 years in our model.",
      "산불 후 사면은 5년이면 회복된다."],
     ["We hypothesise that burned slopes return to baseline within some "
      "bounded number of years.",
      "Prior work elsewhere reports that burned slopes recover after 4 years; "
      "that figure is not Korean and is not ours.",
      "산불 후 사면이 5년이면 회복되는지 여부가 가설이다."]),

    ("RC-004",
     # Either order: pine ... differ ... oak, or pine ... oak ... differ.
     r"(?:"
     r"(?:pine|소나무)[^\n]{0,70}(?:oak|broadleaf|활엽|참나무)[^\n]{0,70}"
     r"(?:differ\w*|slow\w*|fast\w*|long\w*|short\w*|high\w*|low\w*|길다|짧다|높다|낮다)"
     r"|"
     r"(?:pine|소나무)[^\n]{0,40}"
     r"(?:differ\w*|slow\w*|fast\w*|long\w*|short\w*|high\w*|low\w*)[^\n]{0,50}"
     r"(?:oak|broadleaf|활엽|참나무)"
     r")",
     "H-SLIDE is untested and the species contrast is its weakest arm.",
     ["Pine stands differ from oak stands in recovery window.",
      "소나무 임분은 참나무 임분보다 회복 기간이 길다.",
      "Pine recovers more slowly than broadleaf."],
     ["We test whether pine and oak stands differ in recovery window.",
      "Whether pine differs from broadleaf is the question, not the answer.",
      "Pine may recover more slowly than oak; this is what the model is for."]),

    ("RC-005",
     r"(?:hazard ratio|critical rainfall)[^\n]{0,40}"
     r"(?:is|was|were|are|=|of)\s*(?<![\d.])\d+(?:\.\d+)?",
     "No landslide fit exists. A hazard ratio or a critical-rainfall shift is "
     "a result.",
     ["The hazard ratio is 2.3 in year one.",
      "Critical rainfall was 41 mm/h on burned units."],
     ["The hazard ratio is 2.3 in this illustrative worked example.",
      "We will report a hazard ratio by years since fire, with uncertainty.",
      "Prior literature reports a hazard ratio of 2.3; that study is not Korean."]),

    ("RC-006",
     r"(?:censoring|censored)[^\n]{0,60}"
     r"(?:has been|have been|is|was|were)\s+"
     r"(?:corrected|removed|accounted for|handled)"
     r"|(?:corrected|uncensored)\s+(?:fire[- ])?size distribution",
     "H-SUPP is untested. A corrected size distribution is a result.",
     ["Suppression censoring has been corrected in these figures.",
      "The censored sizes were corrected using the tail model.",
      "The corrected size distribution has a heavier tail."],
     ["Suppression censoring will be corrected once the containment model is "
      "fitted.",
      "We plan a design in which censoring is accounted for explicitly."]),

    ("RC-007",
     # Either order: night ... causes ... growth, or growth ... due to ... night.
     r"(?:"
     r"(?:night|nocturnal|야간)[^\n]{0,60}"
     r"(?:causes?|caused|causing|drives?|drove|leads? to|led to|유발|때문)"
     r"[^\n]{0,60}(?:growth|spread|escape|확산|성장)"
     r"|"
     r"(?:growth|spread|escape|확산|성장)[^\n]{0,60}"
     r"(?:is|was|are|were)\s+(?:due to|caused by|driven by)[^\n]{0,60}"
     r"(?:night|nocturnal|diurnal|야간)"
     r"|"
     r"(?:야간|심야)[^\n]{0,60}(?:확산|성장|번짐)[^\n]{0,30}(?:유발|때문|원인|초래)"
     r")",
     "The night comparison has reverse causality (dispatch responds to danger) "
     "and report-time bias. Causal wording needs the E-value first.",
     ["Night causes faster fire growth.",
      "Faster spread at night is due to the diurnal wind shift.",
      "야간 조건이 확산을 유발한다."],
     ["Night is associated with faster growth; the E-value for unmeasured "
      "confounding is reported alongside.",
      "We hypothesise that night drives growth, and treat reverse causality "
      "from dispatch as the main threat."]),

    ("RC-008",
     r"\b(?:PR-?AUC|ROC-?AUC|AUC|Brier|recall|precision)\b[^\n]{0,30}"
     r"(?:of|is|was|were|are|=|reaches|reached)\s*(?<![\d.])0?\.\d+",
     "A score quoted without the held-out years or fires it came from is not a "
     "result.",
     ["The escape score reaches PR-AUC of 0.61.",
      "Brier was 0.08 for the containment model."],
     ["The escape score reaches PR-AUC of 0.61 on held-out years 2023 to 2025.",
      "Brier was 0.08 under spatial block cross-validation.",
      "PR-AUC of 0.61 is reported in prior literature for a non-Korean record."]),

    ("RC-009",
     r"\b(?:the\s+)?first\b[^\n]{0,40}"
     r"(?:study|work|analysis|model|dataset|to\s+(?:measure|quantif\w*|test|map))"
     r"|\bno\s+prior\s+work\b"
     r"|(?:처음|최초)[^\n]{0,30}(?:연구|측정|분석)",
     "A7 has not finished the prior-art sweep. Novelty is a claim like any "
     "other and needs the same evidence.",
     ["This is the first study to measure barrier breaching in Korea.",
      "There is no prior work on the post-fire landslide clock.",
      "국내 최초로 측정한 연구이다."],
     ["To our knowledge this is the first study to measure barrier breaching "
      "in Korea, and that novelty claim is itself unverified pending the "
      "prior-art sweep.",
      "The prior art note records what is already done and what we do "
      "differently."]),

    ("RC-010",
     r"\b(?:US|American|Californian|Australian|Chinese|European|Spanish|"
     r"Portuguese|Canadian|Japanese)\b[^\n]{0,50}"
     r"(?:fires?|fire record|landslides?|roads?|inventor(?:y|ies)|data(?:set)?)"
     r"[^\n]{0,60}"
     r"(?:for (?:fitting|training)|as (?:fitting|training) data|"
     r"pooled|combined with (?:the )?Korean|added to the Korean)"
     r"|(?:pooled|combined)[^\n]{0,40}"
     r"\b(?:Californian|Australian|Chinese|American|European)\b",
     "Scope rule 1 is non-negotiable. Pooling foreign data into a Korean model "
     "is a human gate, not an agent decision.",
     ["We pooled Californian fire data with the Korean record.",
      "Australian landslide inventory used as training data."],
     ["Californian fire data is cited as prior art for the method only.",
      "The Australian study supplies the effective-width equation; its data is "
      "not used."]),

    ("RC-011",
     r"(?:barrier effectiveness|effectiveness of the barrier|\ubc29\ud654\uc120\s*\ud6a8\uacfc"
     r"|the effect of (?:road )?width|width effect on breach"
     r"|wider roads (?:hold|stop) (?:fires|the fire)"
     r"|\ub113\uc740\s*\uc784\ub3c4\uac00\s*\uc0b0\ubd88\uc744\s*\ub9c9\ub294\ub2e4)",
     "The roads estimand is an association under Korean suppression practice, "
     "not barrier physics and not the effect of widening a road. A wide Korean "
     "forest road is also the road the engines used and the line the crews "
     "held. Say 'operational barrier performance', 'the width slope', or "
     "'the association between width and'.",
     ["We report barrier effectiveness by width.",
      "This estimates the effect of road width on breaching.",
      "Wider roads hold fires.",
      "\ub113\uc740 \uc784\ub3c4\uac00 \uc0b0\ubd88\uc744 \ub9c9\ub294\ub2e4."],
     ["We report operational barrier performance by width.",
      "The width slope is reported with its interval.",
      "The association between width and lee-side burning is the estimand.",
      "Whether wider roads hold fires is the hypothesis, not the finding."]),
]

#: The one file the CLAIM rules do not scan, resolved from ``__file__`` so it
#: cannot be widened to a second file without editing this line.
#:
#: ⚠ This is a structural exemption, not an escape hatch. Every rule carries its
#: own ``catches`` corpus of overclaim spellings, so by construction this file
#: contains one assertive spelling of every claim the program forbids. A rule
#: file that cannot state its own rule is not writable. The EM-DASH check still
#: applies here, and so does every rule when the same text appears anywhere else.
RULE_SOURCE = Path(__file__).resolve()

#: Frozen superseded records, exempt from the CLAIM rules but NOT from the
#: em-dash check.
#:
#: A refused or superseded pre-registration is kept and never edited
#: (``research/eval/SIGNOFF.md``), because the point of keeping it is to show
#: what was proposed before it was corrected. It therefore contains, by
#: construction, the wording a later rule exists to stop recurring, and it
#: cannot be given a pragma without editing the thing that must not be edited.
#:
#: This mirrors the record class the repository already declares for the same
#: reason (``docs/auto/CHARTER.md`` section 3, rule 5c): pages that exist to
#: quote a withdrawn claim in order to record it are exempt by design, and the
#: registration is what makes the machine read everything else.
#:
#: ⚠ Narrow on purpose. It matches the superseded per-direction
#: ``PREREGISTRATION.md`` only. The live pre-registration of the day is a
#: versioned file (``PREREG_<direction>_<date>_v<n>.md``) and is NOT exempt.
RECORD_CLASS = ("research/roads/PREREGISTRATION.md",
                "research/landslides/PREREGISTRATION.md",
                "research/suppression/PREREGISTRATION.md")

PRAGMA = re.compile(r"research-claim-ok:\s*([A-Z]{2}-\d{3}(?:\s*,\s*[A-Z]{2}-\d{3})*)")
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".txt", ".json", ".bib", ".html", ".stan"}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", SCOPE], cwd=REPO,
                         capture_output=True, text=True).stdout.split()
    return [REPO / p for p in out if Path(p).suffix in TEXT_SUFFIXES]


def pragmas_for(lines: list[str], i: int) -> set[str]:
    """Rule ids licensed on line i: its own pragma, or the line directly above."""
    ids: set[str] = set()
    for j in (i, i - 1):
        if 0 <= j < len(lines):
            m = PRAGMA.search(lines[j])
            if m:
                ids.update(t.strip() for t in m.group(1).split(","))
    return ids


def fires(rx: re.Pattern, line: str) -> bool:
    """A rule fires on an assertive match that is not hedged."""
    return bool(rx.search(line)) and not HEDGE.search(line)


def scan(paths: list[Path]) -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    compiled = [(rid, re.compile(pat, re.IGNORECASE), why)
                for rid, pat, why, _, _ in RULES]
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(REPO))
        for i, line in enumerate(lines):
            if EM_DASH in line:
                findings.append((rel, i + 1, "EM-DASH",
                                 "em dash is forbidden program-wide, no pragma"))
            if path.resolve() == RULE_SOURCE or rel in RECORD_CLASS:
                continue          # claim rules only; the em-dash check above ran
            licensed = pragmas_for(lines, i)
            for rid, rx, why in compiled:
                if rid in licensed:
                    continue
                if fires(rx, line):
                    findings.append((rel, i + 1, rid, why))
    return findings


def self_test() -> int:
    """Every rule must fire on its catches and stay silent on its spares."""
    bad = 0
    for rid, pat, _why, catches, spares in RULES:
        rx = re.compile(pat, re.IGNORECASE)
        for s in catches:
            if not fires(rx, s):
                why = "hedge guard swallowed it" if rx.search(s) else "pattern missed it"
                print(f"[self-test] MISS  {rid}: should have fired ({why}) on {s!r}")
                bad += 1
        for s in spares:
            if fires(rx, s):
                print(f"[self-test] FALSE {rid}: fired on legitimate {s!r}")
                bad += 1
    n_c = sum(len(r[3]) for r in RULES)
    n_s = sum(len(r[4]) for r in RULES)
    if bad:
        print(f"[self-test] FAIL  {bad} problem(s) over {n_c} catches and {n_s} spares")
        return 1
    print(f"[self-test] OK    {len(RULES)} rules, {n_c}/{n_c} catches, {n_s}/{n_s} spares")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true",
                    help="run the catches and spares corpora, scan nothing")
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args()

    if args.list_rules:
        for rid, _pat, why, catches, spares in RULES:
            print(f"{rid}  ({len(catches)} catches, {len(spares)} spares)\n    {why}\n")
        return 0

    rc = self_test()
    if args.self_test:
        return rc
    if rc:
        print("[claims] refusing to scan with a broken rule set")
        return rc

    paths = tracked_files()
    findings = scan(paths)
    if not findings:
        print(f"[claims] OK    {len(paths)} tracked file(s) under {SCOPE}, 0 findings")
        return 0
    print(f"[claims] FAIL  {len(findings)} finding(s) under {SCOPE}:")
    for rel, ln, rid, why in findings:
        print(f"  {rel}:{ln}  {rid}  {why}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
