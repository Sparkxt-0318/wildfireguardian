# CRITIC_LATEST — critic #41, 2026-09-08T0819Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`9329400`. Window: the 24 h to 2026-09-08T08:10Z. ⚠ **This clone is shallow:**
`git rev-parse --is-shallow-repository` = **true** and `git rev-list --count HEAD` = **50**, so I
make no claim about anything older than that boundary and no ancestry or reachability claim at all
(DIRECTION's standing rule). Full report: `docs/auto/reports/2026-09-08T0819Z-critic.md`.*

## `fix-before-next-row` — ONE item: **WFG-185**. Clear it, then take the table (WFG-182).

**`docs/auto/JUDGE_QA.md:715` tells the student a count about this repository that describes one
directory out of three, and the gate written to stop exactly that passes on a coincidence.**

The spoken draft of **Q16b (T0)** reads 「... `FOOTER_LINES` 가 모든 시트에 찍는 것이라, **커밋된
33장 전부**에 있습니다」. Measured here at `9329400`:

- `git ls-files '*dispatch_a4.html'` answers **642** tracked sheets: **33** under
  `outputs/dispatch`, **113** under `outputs/dispatch_full`, **496** under `outputs/live`.
- 「커밋된」 makes the claim about the repository. 33 is true of one run directory.
- The 0655Z lap's own independent reviewer raised this, and the lap's report says the card
  「must name the run directory its count describes」. **The fix commit `4679285` never touched
  `docs/auto/JUDGE_QA.md`** (`git show --stat 4679285` lists `tests/`, `MEMO`, `BACKLOG`, `STATE`,
  `dashboard`, images and the report). The scope fix reached the test file and the report's prose.
- The gate's scope assertion is `assert COUNTED_RUN in _card("16b")`
  (`tests/test_responsibility_and_privacy_cards.py:225`). It passes because
  `outputs/dispatch/20260801T163042Z/MANIFEST.json` sits at `JUDGE_QA.md:733` **in the 근거 block,
  under the `nothing_was_sent` claim**, not under the sheet count. The count could be wholly
  unscoped and the gate would stay green.

⚠ **The substantive claim is TRUE and understates.** The reviewer measured **0 of 642** sheets
missing the footer. This is a scope defect on the sentence the student says out loud, not a false
claim about the world, and it is live on `WFG_printables_20260908T0633Z.pdf` (40 pages).

**Why this qualifies under §14b as amended by NH-038 B.** One line of Korean on one card, a
tightened assertion, and the kit rebuild every `SOURCES` edit already requires. That is the same
shape and cost as critic #39's WFG-178, which the loop cleared inside one lap. **It does not
displace WFG-182**, which stays position 1.

**Done when:** the spoken sentence names the run directory its count describes, or drops the count
and points at the manifest (Q30/WFG-117's register); the assertion binds the scope token to the
**sentence carrying the count** rather than to anywhere in the card; the lap records the mutation
that proves it (move the run-directory string out of that sentence: green today, must be red
after); and the kit is rebuilt and `release/kcf-finals-2026/MANIFEST.json` re-pointed in the same
lap (WFG-152).

---

## The baseline, re-derived rather than read

✅ **ALL GREEN on the routine's DEFAULT clone, measured before any deepening, read unpiped.**
`gates.py --mode full` exits **0** at `9329400`: `1735 passed, 63 skipped, 2 xfailed`, pytest
**466.2 s**. `verify`, `snapshot-verify`, `env-check` PASS; the `baseline-verify` WARN is the
documented CHARTER §3d sandbox state. **The run downloaded nothing:** `du -sb data/raw` answers
**201,187** bytes before and after, and `data/raw/dem/srtm/` is empty afterwards. **Cold on the
tile, which was never present; WARM on `data/cache`**, said rather than implied. `--assert-head`
exits 0.

✅ **GitHub's own runs (CHARTER §4b): no finding.** Through the GitHub MCP. ⚠ `curl` against
`api.github.com` returns 「GitHub access is not enabled for this session」 here, which is WFG-119's
403 in its current wording; the routine prompt's `curl` line does not work and the MCP is the
channel. `auto-gates` runs **216 to 236** on `auto/dev`: **15 `success`, 5 `cancelled` (218, 226,
229, 232, 235), ZERO `failure`**. Run **236** at this exact head is `success`. No red run sits
behind a green report.

✅ **Report certification.** Every dev and critic report in the window carries `Reviewed by:`.

---

## The root objection

**This loop reports the completeness of its own gates as a fraction whose denominator it chooses,
and a fresh reader has broken that fraction three laps running.**

The 0655Z lap graded `tests/test_responsibility_and_privacy_cards.py` **5 for 5** by mutation and
shipped it as trustworthy. Its own independent reviewer reproduced all five, invented **three more**,
and **M7 found 609 of 642 tracked sheets unguarded**. The widened gate was graded again and again
called trustworthy. I then found its scope assertion is satisfied by a string sitting in a different
claim's 근거 block (WFG-185, above). One lap earlier, `82ec346`/`4f887c7` ran the same shape: nine
tests, graded, and the reviewer still had to rewrite the line the student speaks (WFG-178).

The defect is in the **reporting**, not the testing. 「5 for 5」 reads to the author as coverage. It
means 「every mutation I thought of」, which is 100 % by construction and cannot fall.

**The cheapest test, and it costs one sentence:** a lap that reports a mutation score also writes
down **one mutation it could not make the gate catch**. If it cannot name one, the grading is
unfinished, not perfect. That is **WFG-186** for the class and **WFG-185** for today's instance.

---

## Findings, ranked

**F1 · WFG-185 · `fix-before-next-row`.** Q16b's spoken count is unscoped and its gate passes on a
coincidence. Stated in full above. `docs/auto/JUDGE_QA.md:715`, `:733`;
`tests/test_responsibility_and_privacy_cards.py:225`.

**F2 · WFG-186 · P1 infra (behind R3, R8).** Mutation scores are published without a denominator
the loop controls. The root objection made mechanical.

**F3 · WFG-010 promoted P1 to P0.** ⚠ **This corrects the record rather than changing a mind, and it
is a step-5 update to an existing row, not a §3b reorder.** Critic #39 recorded WFG-010 as
「sitting inside the very block R8 helps hold shut」 and filed it no further. That is a misreading:
CHARTER §14b holds **loop hygiene** behind the readiness lines, this row's goal column is **KCF**,
and §14b's own sentence names 「README opening」 first among judge-facing surfaces. For two laps the
one row that ticks R8 sat unpicked as P1 under a reason that did not apply to it. Measured here:
`grep -nE '^## Round' README.md` returns `:59` Round 2, `:75` Round 3, no Round 4.

**F4 · KCF_READINESS: 7 of 11, ZERO lines ticked for the SECOND consecutive critic lap.** The
routine prompt makes that a finding about the loop's **direction**, not about the product, and I am
filing it as one rather than softening it. Both windows went to the Q&A bank. That is real
judge-facing work and it closed two P0 rows, and the checklist that defines 「the product is done」
has not moved since 2026-09-07T2020Z. R3 and R8 are the two unticked lines; R8's blocker is F3 and
is now P0, R3 needs NH-046 and NH-014 from the author.

**F5 · NH-041, second instance, recorded not filed.** The `2026-09-08T0407Z-dev` report email
(Gmail `1a07f4d490be13ab`) went out with a **corrupted Subject header** carrying the entire HTML
body and raw tool-call scaffolding; `sizeEstimate` **52,396** bytes against about 26,000 for every
other report this week. The plain-text body arrived intact. Second failure of the author's only
report channel in two days, and both were invisible to every gate for the same structural reason:
the send happens after the push and leaves no artifact in the tree. Recorded in NH-041 with the
habit that follows and an explicit note that the habit has **no gate behind it** (WFG-175's
complaint), rather than a duplicate row.

**F6 · Protocol, already self-reported, recorded not re-filed.** WFG-181 was built without a pushed
`in-progress` claim (CHARTER §4 step 3). The 0655Z lap's reviewer caught it and the lap wrote it
into the row. Nothing collided. No new row.

---

## What I checked and did NOT find

Said explicitly, because a critic that only publishes hits is not measuring anything.

- **The two new cards' load-bearing claims all hold**, re-derived by channels the lap did not use:
  `sms.send` is called nowhere in `src/` or `scripts/`; `email_sent.json` appears **0** times in the
  tree; **28** JSON run records carry `nothing_was_sent: true` and the 29th grep match is
  `outputs/dispatch/README.md`, which is prose, so the card's 28 is right and I nearly published a
  false finding on it; `immobile_fraction` is **0.3** in `data/processed/rescue_routing.json`;
  `vulnerability.py`'s module docstring does declare its county scores placeholders 「NOT yet
  anchored to authoritative data sources」.
- **The bank's own counts are consistent:** `grep -cE '^\*\*Q[0-9]+[a-z]? · T[0-9]'` returns **44**,
  and the header's 44 / T0 18 / T1 19 / T2 7 sums correctly.
- **The paper lap's prose changes at `24f914f` all narrow rather than widen** (「reports」 to
  「finds」, 「standard since Dozier」 to 「after Dozier」, 「established predictor」 to 「predicts」,
  「the Korean local area」 to 「its sectored regions」). No new world claim needed a `factchk`
  reversal, and I am not filing the one wording tension I noticed because I could not settle it
  from a source in this sandbox.
- **No ancestry or reachability claim is made anywhere in this lap** (`is-shallow-repository` =
  `true`).

---

## Direction

**No reorder spent.** Positions 1 and 2 (WFG-167, WFG-181) both closed inside this window at
`c2a7980`. **WFG-182 falls through to position 1** and is the right row: critic #40 measured the
scorecard side (41 consecutive 15/15 on a row worth **20 points on both tables**); this lap measured
the product side, which is the half that matters at a booth. `grep -ncE '창의|독창'` returns **0** on
`docs/auto/JUDGE_QA.md`, **0** on `web/finals.html` and **0** on `docs/auto/DEMO_SCRIPT_5MIN.md`.
The same grep for 책임 and 개인정보 now returns **6** and **5** where critic #40 measured zero, so the
method that found those rows works and 창의성 is what it points at next.

Order for the next lap: **WFG-185** (the item, minutes), then **WFG-182**, then **WFG-010**, then
WFG-128.

---

## Scorecard

Appended at `9329400` to **all three** tables (WFG-184's requirement; existing rows untouched).
**Track B 87, unchanged: 17 / 18 / 19 / 15 / 18.** **Track A 87, +1: 개발 목적 16 to 17**, the only
rubric row whose text names 「작품 작동을 위한 제약에 대한 이해」, which is exactly what the two new
cards' eight 없는 것 clauses are. 제출 자료 holds on both tracks: two T0 cards and a 40-page kit
against F1 live on those printed pages, and I would rather hold than ratchet. **창의성 15 and 15,
the 41st consecutive pair.**

---

## `Do NOT edit` notes

**None written this lap** (CHARTER §14c, NH-036 A). WFG-185 must edit `docs/auto/JUDGE_QA.md` and
rebuild the kit in the same lap, and WFG-182 must add to it; freezing either would block the work
this file is asking for. Critic #40 wrote none either, and no note from an earlier lap is re-stated
here, so none carries forward.
