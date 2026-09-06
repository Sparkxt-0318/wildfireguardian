# CRITIC_LATEST — critic #30, 2026-09-06T2317Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `524f13c`. Window: `1b26c3a..524f13c`, plus the
24 h to 2026-09-05T23:38Z for the gate, CI and report checks.*

**Critic #29's two falsifiable tests, answered first, because both were about the dev lap and not
about the row.**

1. **「If `README.md:22-26` still says 「only when the router accounts for where the fire will be」 with
   no fire-blind caveat at the next critic head, the finding is about the dev lap's step 3.」** It does
   not. `README.md:22-33` at `524f13c` carries the caveat inside the same bullet, and
   `docs/auto/JUDGE_QA.md` Q19's spoken draft carries it in the sentence itself. The 20:17Z slot ran,
   claimed **WFG-138** at `8cc1e89` and closed **both halves** at `0ed15aa`/`20b0b7e`. No finding.
2. **「If that lap clears WFG-138's README half and leaves Q19's 42 standing, then a widened row does
   not travel and the correct unit is one row per surface.」** It did not leave it standing.
   **A widened row travels when both halves are one clause long**, and the record now says so rather
   than the hypothesis. The unit stays the claim, not the surface.

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-148 — the README's headline bullet gained the first of the manuscript's two binding caveats and
not the second, and the gate the same lap shipped certifies the bullet as caveated.**

`paper/manuscript.md:506`, this loop's own sentence:

> Two caveats bind the whole comparison. The forecast-aware arm plans on the same hazard field it is
> graded against, so whatever it is worth against a present-perimeter policy is what a *noiseless*
> forecast is worth; this project's own model is worth less, by an amount no run here measures.

WFG-138 put caveat one into `README.md:22-33`. Caveat two is not in the README at all:
`grep -niE "perfect|oracle|upper bound|상한|noiseless" README.md` returns nothing at `524f13c`.

**It binds the 42 for the same reason it binds the 91.** `docs/present_perimeter_arm.md` §5 states it
and calls it 「a property the 91 has always had, inherited not introduced」. The 42 is the 영덕 sibling
of the identical design: `docs/real_roads_real_hazard.md` hands both arms the same `HazardSequence`,
and `src/wildfireguardian/routing/evacuation.py:270` says the fire-blind arm is 「then scored against
the hazard」. So on 영덕 too the forecast-aware arm plans on the field it is graded against, and the 42
is an upper bound on what a **noiseless** forecast buys, not a measurement of this project's model.

**The gate makes it harder to notice, not easier.** `tests/test_future_aware_attribution.py:135`,
`_is_caveated(block)`, returns True on any one spelling of the CONTROL family and asks nothing else.
The README bullet is therefore green under the gate built for it while half of what the manuscript
calls binding is missing. A gate that certifies 「this sentence is caveated」 is only as wide as its
list of caveats, and this list was written from the one defect in front of the lap.

**The judge already has the question and the bank already has the answer.** `docs/auto/JUDGE_QA.md`
**Q36** (「비교하신 예보 경로는 정답을 미리 본 예보 아닙니까?」, critic #23) sits in the 근거 없음 table
and tells the student to say 「맞습니다. 그건 완벽한 예보가 사는 값의 상한이고, 저희 모델이 실제로 사는
값은 아직 재지 않았습니다」 **before the judge digs**. The README is the surface that invites that
question and does not answer it.

⚠ **Do not touch `docs/auto/JUDGE_QA.md` for this item.** Q36 already carries the sentence, and the
printables manifest is stale against that file for a **fourth** time (WFG-134 below). A fifth drift
buys nothing.

⚠ **Budget: twenty minutes and one clause.** Extend the module WFG-138 shipped; do not write a new
one. The full done-when, including the two mutations that grade it (a restore and a **move**), is the
`WFG-148` row in `docs/auto/BACKLOG.md`.

**Then claim WFG-134 with WFG-140 and WFG-130 in the same lap and do not idle** (CHARTER §11). R7 and
R9 wait on nothing else, and the 2154Z lap's own report already names that trio as its next row with a
written reason why WFG-140 cannot be separated from the rebuild.

## What I verified rather than read

- `gates.py --mode full` **ALL GREEN** at `524f13c`, exit 0: `1616 passed, 62 skipped, 1 xfailed`,
  **cold**, 350.4 s. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN is
  CHARTER §3d information. The 2154Z lap's **warm** `1622 / 56` and this **cold** `1616 / 62` differ by
  exactly the six terrain tests of **WFG-139**, in both directions, which is the cleanest demonstration
  of that row anyone has produced: same tree, one sandbox apart.
- **CI (CHARTER §4b), read through the GitHub MCP** because `curl` is 403 through this proxy
  (WFG-119): `auto-gates` runs **165 to 184** on `auto/dev` are **18 `success` and 2 `cancelled`**
  (`dfdf480`, `8cc1e89`, each superseded by a green push) with **no `failure` at all**. Run **184** at
  `524f13c`, this head, is `success`. **No red run behind a green report, so no finding #1 of that
  kind and no `fix-before-next-row` item spent on a gate.**
- **Every push in the window carried a report**, checked pair by pair with
  `gates.py --assert-reported --base <previous push>`; the only non-zero exit is the range that spans
  the concurrent paper lap and the WFG-138 claim commit, where the paper work is covered by
  `docs/auto/reports/2026-09-06T2119Z-manual.md` in the neighbouring range. Every **dev** report in the
  window carries `Reviewed by:`. The research report still does not (**WFG-147**, already filed).
- **The booth kit drifted a fourth time and this drift is the worst of the four.** Re-hashed in one
  process: manifest `2c8451211e5f97…`, tree **`5ac45ea8103f11…`**; the other three sources MATCH. The
  series is `af955a30fa…` (#27) → `7d5ac4c9c5…` (#28) → `175da9e50c…` (#29) → **`5ac45ea810…`** (here).
  Critic #29's reading was that all three earlier drifts were correction notes rather than
  improvements. This one is an improvement, and that is why it is worse: the printed 17 pages now hold
  Q19 **without** the caveat the repository has since made mandatory and gated twice. The paper in the
  student's hand and the files the gates read now disagree about what the student may say.
- The clone was unshallowed before any measurement: `git rev-parse --is-shallow-repository` answers
  **`false`**, 508 commits.
- **No author decision is waiting on either channel.** The Gmail search
  `from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d` returns 30 threads,
  every one a single message this loop sent, all labelled `SENT`; no thread carries a reply. PR #31 has
  no comments at all. `docs/auto/decisions_seen.json` is unchanged and `decisions.py` was not run.

## Direction (CHARTER §14, five minutes)

**No row moved and the reorder budget is unspent.** WFG-138 closed, so the first `todo` row in table
order is **WFG-134**, which is also `DIRECTION.md`'s row 2 and the 2154Z lap's stated next row. The
page and the table already agree; a reorder would be motion without a reason. `WFG-148` enters at
position 1 as this lap's one item, which is not a reorder of an existing row.

**KCF_READINESS: zero lines ticked in the last 24 h, 4 of 11, a SEVENTH consecutive critic lap, and
this time the rule fires.** Critic #29 recorded the zero without firing it, correctly, because that
window contained no dev lap. This one did. The seventh data point is in **NH-038**, which asks the
author this exact question and is the only place it can be answered, because the rule that produces it
is theirs.
