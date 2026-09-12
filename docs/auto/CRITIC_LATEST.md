# CRITIC_LATEST — critic #73, 2026-09-12T0822Z, reviewed `4bf34ab`

**The next dev lap reads this file before it claims a row** (CHARTER §4 step 3). Only the
most recent critic lap's file is kept; the full report is
`docs/auto/reports/2026-09-12T0822Z-critic.md`.

## `fix-before-next-row`

**ONE item. Repair `README.md:25` and `README.md:798`, then register the spelling. Then
claim WFG-267.**

Both lines read 「**2** have no safe walking route **at all**」. The code condition behind
that count is `nv.enters_hazard and not fa.reached`: the fire-blind route **did** reach a
refuge, through the predicted hazard, and the forecast-aware **search terminated without
reaching one**. Asserting that no such route is there is stronger than any search result
can support. This is the last live instance of a claim every other surface has already
narrowed — the Abstract at `63e9d20`, all three figure legends to 「found」, the booth script
(WFG-103) and the finals template (WFG-109) — and it is on the project's most-read page, in
its own voice, on the surface CHARTER §14b names first.

**(a)** Both lines report what the searches returned, in the register the Abstract and the
legends now use. Do **not** move the **2**: the count is registered and correct. Do not
re-order the TL;DR bullet or change its length materially (NH-054 freezes its ordering and
proportion, not the truth of a clause inside it). Do not touch the opening paragraph about
the 2025 fire (CHARTER §3.5b) or the Round-2 section (§3.12).

**(b) NARROWED, and the narrowing is the whole reason this is minutes.** Register
**exactly** 「no safe walking route at all」 as `WC-021` in `docs/auto/withdrawn_claims.json`,
with the probe sentence the README actually shipped. Do **not** register the class name
「no safe route」.

**Why this is minutes and WFG-270 said it was not.** The row defers on the ground that the
spelling is live in `docs/present_perimeter_yeongdeok.md`,
`docs/ROUTING_INTEGRATION_REPORT.md`, `docs/real_roads_real_hazard.md`,
`docs/slope_integration.md` and `docs/OVERNIGHT_REPORT_SESSION5.md`. Measured at `4bf34ab`
in this lap's own process: **`grep -n 'no safe walking route'` over all five returns zero
lines.** What they carry is the bucket's class name 「no safe route」 — a different string,
and a label rather than an assertion in most of those places. Measured against the
registry's own scope rule (every tracked `.md` and `.html`, **1192** files, minus the twelve
`record_prefixes` declared in `docs/auto/withdrawn_claims.json`), the exact string
「no safe walking route at all」 is in **exactly one gated file, `README.md`**, plus four
record-class files exempt by design. **So (a) plus the narrowed (b) is green across the
gated set with no per-line pragma anywhere.** Clauses (c) and (d) of WFG-270 stay on the
row, and so does the open question of which of the eight non-record 「no safe route」 lines
assert non-existence and which name a bucket.

**What this lap checked, so the next lap does not re-check it:**

- `gates.py --mode full` exits **0** on its FIRST run at `4bf34ab` (2221 passed, 65 skipped,
  3 xfailed, pytest 279.2 s). `baseline-verify` is the usual sandbox WARN for two absent
  `data/raw/` manifests (CHARTER §3d).
- `--assert-head` and `--assert-reported` both exit **0**.
- **No red GitHub run in the window.** `auto-gates` runs 392 to 402 on `auto/dev` all
  concluded `success`, and run **402** is green at `4bf34ab`. CHARTER §4b sets no finding #1.
  `curl` against `api.github.com` works here; WFG-268 confirmed a second time.
- All **35** reports dated 09-11 and 09-12 record `Reviewed by:`.
- Printed kit **7 of 7** (`WFG_printables_20260911T2137Z.pdf`, 60 pages,
  `manifest_20260911T2137Z.json`), release bundle **19 of 19** against its own `source`
  fields, `tests/test_printables.py` 24 of 24. All re-hashed here, not read off a report.
- Clone is SHALLOW at **50** commits and was **not** deepened. No ancestry claim anywhere
  in this lap.
- Nothing new on either decision channel: the newest 25 Gmail threads matching the report
  subject each carry exactly one message, every one the loop's own send; PR #31's comment
  list is empty. Six days on WFG-211.

## Findings, ranked

**F1 (root objection) — three pages in this window made a claim about the tree that was
true when it was written and false when it shipped, and the project's thesis is that its
pages are the contribution.**

`docs/auto/DIRECTION.md` says the defensible contribution is 「the **output object and its
measured limits**, a time-dependent decision per point with a page saying how wrong it can
be」. If the pages are the product, their accuracy is the product. Three instances, one
window:

1. `docs/figure_legend_claims.md` cites `paper/make_figures.py` at nine line numbers of
   which **seven are one too high** — F2 below.
2. `WFG-270` prices a README repair against five files that do not contain the string —
   the `fix-before-next-row` item above.
3. `docs/auto/JUDGE_QA_PENDING.md` was structurally broken by critic #72 and never read
   back — F3 below.

**None of the three is a hard mistake and all three are the same easy one.** A sentence of
the form 「X is at line N」 or 「X is live in these files」 is a command the lap already knows
how to run. **Run it last, against the tree you are about to commit.** DIRECTION has now
named this class four laps running, each time one abstraction too high (describing
sentences, defining sentences, the same string elsewhere in the file); this is the naming
that covers all three.

⚠ **The lap under review is not what is wrong here.** The WFG-266 lap pre-registered its
root objection in the claim commit `a9bc4ab` before editing anything, refused repair by
analogy until it had read the producer behind each artifact, took a **block** from its own
reviewer and repaired every finding rather than arguing, published its own three wrong
counts in order, rewrote WFG-271's done-when to forbid a gate built against today's
enumeration, and found the README over-claim by running DIRECTION's own instruction and
**filed it instead of quietly fixing it**. The defect below is in the fourth draft of the
document that narrates the first three.

**F2 — WFG-272, P1. The document written to prove this project stops over-claiming cites
the one file it was written about at line numbers that are all one off, including the
single pointer it calls its own finding.**

`docs/figure_legend_claims.md` §「Why a test and not the grep the row asked for」 says
「Nine, at lines 133, 146, **173, 252, 283, 574, 581, 586 and 755**」. Re-running that count
in the shipped tree returns nine hits at **133, 146, 172, 251, 282, 573, 580, 585, 754**:
the first two are right and the other **seven are each exactly one too high**. The same
offset runs through the prose. The seventh producer — the one the document marks
「⚠⚠ the finding of this lap」 — is cited as `paper/make_figures.py:649`, and `:649` is
`classes["no_safe_route"].append(n)`; the `elif` the table quotes is at **:648**. The legend
the narrative says `:755` labels is at **:754** (`:755` is the fire-blind route entry).

⚠ **Every line number the same document gives for a DIFFERENT file is exact** — all six
other producers and all three `fa_exceeds_budget` sites resolve on the line named. The
defect is confined to the one file the lap was editing, which is the same blind spot its own
reviewer already caught once. ⚠ **Credit first:** the document says in its own Method
section 「The command is the authority here, not this prose」 and ships the command with its
raw output, so a reader who runs it gets the right answer, and the counts **7**, **3**,
**9** and **19** are all correct. It is the pointers that rot.

**F3 — WFG-273, P1, and the defect is this routine's own. Critic #72 inserted two judge
cards into the middle of a sentence, breaking a document's headings, and every gate stayed
green. Repaired in this lap's commit.**

Commit `155aa07` added P-003 and P-004 to `docs/auto/JUDGE_QA_PENDING.md` by opening them
inside the inline code span of the sentence 「it moves the entry under `## Merged` with the
commit that merged it」. At `4bf34ab` the sentence read 「it moves the entry under
`### P-003 · ...」, both cards sat above the `## Pending` heading rather than in it, and the
file carried a bogus second 「## Merged` with the commit that merged it.」 line. The WFG-266
dev lap then edited P-003 inside the broken region without noticing. **Repaired here**: the
two cards moved verbatim under `## Pending`, the sentence restored, nothing deleted, line
count unchanged at 145, and a multiset diff of non-blank lines showing only the two broken
lines becoming their two correct forms. The row is the missing gate, not the repair.

**F4 — WFG-191, evidence added, still P1, and the cause is now measured.** Splitting every
row whose first cell is a `WFG-` id on pipes not preceded by a backslash, **12** rows yield
a cell count other than 10, so the rule reads their `status` cell as a fragment of their own
prose: WFG-271 (filed in this window), WFG-181, WFG-182, WFG-188, WFG-215, WFG-197, WFG-175,
WFG-168, WFG-115, WFG-243, WFG-107, WFG-112. Each pastes a shell command containing a
literal unescaped pipe. That is why the two board-counting rules disagree. ⚠ **This critic
wrote a thirteenth instance into its own note filing the row, and caught it only by
re-running its own count before committing.** Annotated, not re-filed; held behind R3.

**F5 — WFG-263, evidence added, still P1, fifth consecutive lap.** The 0710Z report's
header (`:6`) and its generated gate table (`:198`) both name `a9bc4ab`, that lap's claim
commit; the report ships in `4bf34ab`. Unlike critic #72's instance both commits resolve on
`origin/auto/dev`, the lap re-ran the gates at the pushed head and said so in prose, and run
**402** is green at `4bf34ab`, so no gate was in fact skipped. Annotated, not re-filed.

## What this lap did NOT find, stated so the next lap does not look again

- **Nothing wrong with the WFG-266 repair itself.** `F3b_regions.png` and
  `F8b_routing_map.png` are new files (`git diff --name-status a37cfb0..4bf34ab --
  paper/figures/` is three `A` lines, no `M`, no `D`, so all three predecessors are
  byte-unchanged); `paper/make_figures.py` asserts non-existence nowhere outside a
  supersession docstring; `paper/manuscript.md:394`, `:396` and `:428` point at `F5b_`,
  `F8b_` and `F3b_`; F8b's caption 「2 reaching no refuge」 and its legend 「no safe walking
  route found」 no longer disagree. CHARTER §3 rule 2 is intact.
- **No red gate and no red GitHub run anywhere in the window.** See the checklist above.
- **No new prose world-claim to check.** `factchk` over the window's added markdown found
  no assertion about anything outside this repository; every new claim is about this tree,
  and each was checked against the tree instead.
- **No leakage finding.** `mandela` had nothing to audit: the window re-ran no router,
  moved no count and registered no key. The lap says so in its own words — 「A rewording is
  not a measurement」 — and the committed partitions are untouched.
- **No Korean judge-facing surface carries the over-claim.** Grepped `docs/auto/JUDGE_QA.md`,
  `docs/auto/DEMO_SCRIPT_5MIN.md`, `web/finals.html`, `docs/auto/finals/` and
  `release/kcf-finals-2026/README_KO.md`. `README.md` is the only live surface.

## Scorecard

**Track B UP to 96, Track A HOLDS at 96 with two rows moving in opposite directions.**

제출 자료 **18 to 19 on both tracks**, firing critic #72's pre-registration exactly as
written. It stops at 19 because of F2, which sits on the same criterion's third clause
(「사용된 자료에 대한 출처 명기」). 구현 및 유용성 **20 to 19**, firing critic #72's other
pre-registration because WFG-267 (i) is still `todo` — **not the dev lap's doing**: critic
#72 put WFG-266 at position 1 and the lap correctly took it. 설계와 방법론 **20** and
데이터 수집·분석·해석 **20** HOLD, re-earned rather than inherited. 연구 목적 18, 개발 목적
19, 창의성 19 HOLD.

⚠ **Pre-registered for critic #74:** 제출 자료 rises to **20** when WFG-272 closes AND the
README spelling is repaired and registered; it falls to **18** if a third document in this
family ships with `file:line` citations that do not resolve in the tree it ships in.
구현 및 유용성 returns to **20** when WFG-267 (i) names the stale page in a committed file.

## Readiness

**8 of 11, unchanged, and ZERO lines ticked for the thirtieth consecutive critic lap.**
`git diff cd18782..4bf34ab -- docs/auto/KCF_READINESS.md` is empty; the file's newest commit
is `a37cfb0`. R3 is the only one of CHARTER §14b's six outstanding, it is `blocked(NH-046)`,
NH-046 came due **2026-09-10**, and the sprint ends **2026-09-15**. One unanswered question
holds the ninth tick and the whole P1 block. **118 rows are P1 `todo`**, and the leading
block that sits directly under the P0s is now **nine** deep: WFG-252, WFG-253, WFG-261,
WFG-263, WFG-268, WFG-269, WFG-271, WFG-272, WFG-273. Two of those nine were filed today.

⚠ **New state the author needs, recorded on NH-037 rather than as a new entry:**
`paper/STATE.json` `built_pages` is **`null`** at this head. The WFG-266 lap nulled it
rather than hand-writing a page count no run produced, which is the right call, and the
consequence is that the author's own **25-page limit (NH-028)** is verified by nothing,
three days before the sprint ends. Only a machine with LibreOffice Writer can change that
(`paper/measure_pages.py`, WFG-116).
