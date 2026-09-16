# Forbidden claims for the research program

The three research questions are **hypotheses**. None of them has a result yet.
This file holds them in hypothesis wording, and lists the sentence shapes that
state them as fact. Those shapes are forbidden in `research/**` until the
validation agent (A6) signs the direction off.

The check is `research/shared/check_research_claims.py`. It runs over tracked
files under `research/` and must exit 0 before any research commit. It also
enforces the zero-em-dash rule for the same tree.

Per-line pragma, same convention as `scripts/check_forbidden.py`:

    <!-- research-claim-ok: RC-001 -->      markdown
    # research-claim-ok: RC-001             python / yaml

The pragma sits on the offending line or the line directly above it and
suppresses only the rule it names. There is no whole-file exemption.

## Why these are not in scripts/check_forbidden.py yet

Adding them there is a change outside `research/`, which is a human gate
(program brief section 9). The patch is drafted and waiting as **WJ-002** on the
TASKBOARD. Until John approves it, the research-local checker is what holds the
line, and it covers exactly the tree where these claims would first be written.

---

## The three hypotheses, in the wording that is allowed

**H-ROADS.** *Hypothesis:* the probability that a Korean fire front breaches a
linear barrier falls with the barrier's effective width, and a forest road of
6 m or wider is not by itself sufficient to hold a front under the approach <!-- research-claim-ok: RC-001 -->
angles, slope directions and lee-side fuels observed in Korean fires.
*Status:* untested. No breach dataset exists yet.

**H-SLIDE.** *Hypothesis:* a burned Korean slope stays more landslide-prone for
a bounded number of years after fire, and that window differs between
pine-dominated and broadleaf-dominated stands.
*Status:* untested. No hazard model has been fitted.

**H-SUPP.** *Hypothesis:* the Korean recorded fire-size distribution is
right-censored by suppression, and the fires that would have grown large can be
separated from the rest using information available in the first hours.
*Status:* untested. No containment or tail model has been fitted.

## Rule table

| id | forbidden shape | why |
|---|---|---|
| RC-001 | a 6 m road stated as sufficient or insufficient as fact | H-ROADS is untested; the NIFoS 6 m claim is prior art to be tested, not a result to restate or to refute |
| RC-002 | a named breach probability, breach curve value or width threshold presented as measured | no breach dataset exists; any number is a placeholder until A6 signs the pre-registration and the fit |
| RC-003 | a recovery window in years stated as fact ("burned slopes return to baseline after N years") | H-SLIDE is untested |
| RC-004 | a pine-versus-oak difference stated as established | H-SLIDE is untested, and the species contrast is the weakest arm of it | <!-- research-claim-ok: RC-004 -->
| RC-005 | a hazard ratio or critical-rainfall shift presented as measured | no fit exists |
| RC-006 | censoring correction stated as done, or a corrected size distribution quoted | H-SUPP is untested | <!-- research-claim-ok: RC-006 -->
| RC-007 | the night-growth comparison stated causally | the design has reverse causality (dispatch responds to danger) and report-time bias; an E-value is required before any causal wording |
| RC-008 | an escape-risk score's discrimination quoted without the held-out year it came from | a score quoted without its evaluation frame is not a result |
| RC-009 | "first", "novel" or "no prior work" for any direction | A7 has not finished the prior-art sweep; novelty is a claim like any other | <!-- research-claim-ok: RC-009 -->
| RC-010 | a foreign dataset named as a fitting input for a Korean model | scope rule 1 is non-negotiable and a human gate |
| RC-011 | the roads estimand stated as barrier effectiveness or as the effect of width | the quantity is an association under Korean suppression practice. A wide Korean forest road is also the road the engines used and the line the crews held, so the width coefficient may be measuring access. Permitted vocabulary: operational barrier performance, the width slope, the association between width and | <!-- research-claim-ok: RC-011 -->

RC-011 was drafted by the roads modeller, which does not own this file, and added by the orchestrator after validating it both directions. The roads tree also carries its own local detector, `research/roads/check_vocabulary.py`, which covers the same ground inside that direction.

Each rule's regexes live in the checker with the same id, together with the
validation record: what the rule caught on a corpus of overclaim spellings, and
what it did NOT fire on for a corpus of legitimate neighbours. A rule that fires
on legitimate hedged wording is worse than no rule, because agents learn to
ignore the checker.

## How a claim graduates

1. The direction's pre-registration is signed by A6.
2. The model is fitted and the numbers are re-run independently by A6.
3. The number is registered in `docs/NUMBERS.json`.
4. A6 writes the kill-shot section and the result survives it.
5. A8 records the graduation in `research/DECISIONS.md`, and the rule moves from
   "forbidden" to "forbidden without its uncertainty interval and its
   evaluation frame".

Step 5 is the important one. A result never becomes free to state bare. It
becomes free to state **with** its interval and the fires or years it was held
out on.
