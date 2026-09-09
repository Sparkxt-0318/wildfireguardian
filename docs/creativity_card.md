# The 창의성 card, and why it is written in the descriptive register (WFG-182)

*Method proposed by the loop (dev lap 2026-09-08T0920Z), not by the student
(CHARTER §9). The booth consequence is one sentence: **the card says what was
built, not how good it is, because the second kind of sentence is the judge's
to write and not ours.***

## The defect this closes

창의성 is **20 points on both KCF scoring tables** (`docs/auto/RUBRIC.md`, the
「연구목적, 설계와 방법론, 데이터 수집·분석·해석 등의 프로젝트 진행에 있어 뛰어난
창의성」 row on each), and the 심사기준 names it first: 「단순 암기 발표 지양;
창의성, 과학적 원리, 과학적 사고 중점」.

Critic #40 measured, on 2026-09-08, that the 창의성 column of
`docs/auto/SCORECARD.md`'s combined series had returned the same value in every
row of the series since the first critic lap, while the total moved on the other
four columns; critic #41 measured that `grep -ncE '창의|독창'` returned **0** on
each of the three surfaces a judge actually meets — `docs/auto/JUDGE_QA.md`,
`web/finals.html` and `docs/auto/DEMO_SCRIPT_5MIN.md`. The project had been
graded on honesty for six days and had never assembled its creative claim
anywhere a judge could meet it.

This row is **not** a research row and did not become one (CHARTER §3.4: extend,
never pivot). No experiment, model, split, arm or region was added. The card is
an assembly of three things already committed in this tree.

## Method

`docs/auto/JUDGE_QA.md` gains **Q29a · T0**, placed after Q29 (「무엇을 직접
만들었습니까?」), because the natural follow-up to *what did you make* is *what
is new about it*. It answers in three items, each pointing at a committed file:

| item | the claim | the artifact |
|---|---|---|
| 1 | the **output object** is the contribution — a rescue order and a walking route per household, with the forecast grid as an intermediate input rather than the deliverable | `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 |
| 2 | the run where **both axes are real** at once — real OpenStreetMap walk graph *and* real forward-simulated spread — closing the project's own largest stated limitation | `docs/real_roads_real_hazard.md`, first table, third row |
| 3 | withdrawn claims are **registered for a machine to read**, not deleted; the check runs inside `make verify` on every lap and every push | `docs/auto/withdrawn_claims.json`, `scripts/check_withdrawn_claims.py`, `docs/withdrawn_claims.md` |

The **register** is the whole design of the card, and it is the part a gate can
hold. The card describes *what was built*. It does not rate it, it does not
compare, and it states no quantity. `tests/test_creativity_card.py` binds those
three properties:

- the three anchors exist and are named in the card, and the spoken draft still
  makes all three items;
- the spoken draft names **none of a listed set of other systems**, in either
  direction — this card carries no source line, so a sentence about NIFoS or
  G-DAPS here would be unsourced by construction, and the register rule
  (`WC-009`, critics #34 and #37) binds the positive form as tightly as the
  negative one. The card sends that question to Q16a and the related-work
  panel, where the provenance is;
- the spoken draft holds **no count** — any multi-digit run, and any digit or
  Korean numeral used with a counter of repository objects;
- the spoken draft makes **no novelty claim** (처음 · 최초 · 유일한 · 전례 없);
- the 없는 것 block still carries the limit that makes item 3 honest.

## Result

Seven mutations were run by the lap, and six more by its independent reviewer
(recorded in the section after next, because five of those six were **green**
when the reviewer ran them and are red only because it blocked the lap).

Of the lap's seven, six turn the gate red: deleting the card; a positive
assertion about another system (「NIFoS 의 콘솔은 진압 지휘용입니다」); three count
shapes — 「12건」, 「아홉 건」 and 「여섯 개」, the last being the exact spelling of
the WFG-178 defect; and deleting the reworded-claim limit.

**Two of those six were green when the gate was first written, and that is the
useful part of this section.** The count assertion began as `\d{2,}` only, and
「여섯 개」 — the defect this project actually shipped onto three judge-facing
surfaces — contains no digit, so the check could not see the failure it existed
for. The Korean-numeral half was then written with a trailing `\b`, which after
a Hangul syllable can never match, because Korean particles attach directly to
the counter (「여섯 개는」, 「아홉 건이」) and Hangul syllables are word
characters; two more mutations stayed green until that was removed. A gate that
cannot fail reports coverage it does not have.

One measured false positive forced one exclusion: 「한」 is idiomatic rather than
enumerative in Korean prose — this card's own 「이유를 한 줄씩 적게」 tripped it —
so the numeral list starts at 「두」. Every count this repository has actually
shipped wrong was two or more (33장, 여섯 개, 41문항).

The cold read of the card also caught an overclaim written by this lap: item 3
first said the checker reads 「추적되는 문서 전부」. It does not — it reads
tracked `.md` and `.html` only, minus the loop's own record class. Both limits
are now on the card, in the 없는 것 block, with `references.bib` named as the
copy a human found and the machine structurally could not (WFG-155, WFG-168).

## What this does NOT show

- **It cannot tell whether the three items are the right three**, or whether a
  judge will find them creative. That is the judge's call, and the card's own
  first 없는 것 line says so.
- **The mutation it could not catch** (WFG-186's rule, stated rather than
  omitted): rewriting the draft from the descriptive register into the
  evaluative one — 「이 접근은 매우 독창적입니다」 — while keeping all three
  anchors, no other system, no count and the limit clause. Every assertion
  passes and the card has become the self-assessment its design exists to
  avoid. Nothing here reads tone. A keyword list for 「독창」-type words would be
  a spelling ratchet with exactly the limit `docs/withdrawn_claims.md` §4
  measures for the registry, so it was not written; the cold read is what
  catches this one, and it is recorded so the next reader looks for it.
- **[철회 · 2026-09-09 · WFG-194] The paragraph in quotation marks below is a
  RETRACTED claim, kept as the record and no longer true.** It is quoted rather
  than struck through with markup, because `scripts/build_printables.py` renders
  one weight of body text on paper and this file is now printed in the booth kit:
  a retraction that depends on a line being drawn through it is a retraction that
  vanishes at the printer. WFG-194's independent reviewer found exactly that, in
  this bullet, in the lap that added this file to the kit.
  「**The other two judge-facing surfaces are still silent on 창의성.** Measured
  after this lap: `grep -cE '창의|독창'` returns 0 on `web/finals.html` and 0 on
  `docs/auto/DEMO_SCRIPT_5MIN.md`. The row asked for one surface and a T0 card
  and that is what shipped; the screen and the spoken script were deliberately
  not widened (CHARTER §3.4, and the demo script's segment times are a
  registered allocation that a new sentence would move — the WFG-121 (c)
  problem).」
  It is kept because the four days it was true are the reason WFG-194 existed
  (critics #41, #45 and #47 each re-measured the same zero). §6 below is what
  replaced it, including what the registered allocation actually cost.
- It says nothing about whether the three items are novel **against the
  literature**. The card refuses novelty claims outright, and since the review
  below, `tests/test_creativity_card.py` enforces that refusal. ⚠ **It is the
  only thing that does.** An earlier draft of this section said the
  repository's forbidden-string check was an independent backstop for the
  novelty shapes; that was false. `scripts/check_forbidden.py` has no novelty
  *word* ban at all. Its one rule naming those words is a claim **shape** taken
  from `docs/decision_shift.md` §6, and that shape only fires when one of them
  sits within forty characters of the word for a direct measurement. A bare
  「국내에서 이런 접근은 이번이 처음입니다」 passes it, exit 0, over every gated
  file — which the reviewer demonstrated rather than asserted.
- **The list of other systems is a named list, so it is a partial one.** The
  first version held only the five systems this repository had already written
  about, which is a population drawn to fit the claim — the exact shape WFG-185
  and WFG-186 are about, recurring inside the gate written to answer them. It
  is wider now, and a system this repository has never named still escapes it.
- **The anchor check is card-level, not item-level.** Replacing an item's path
  with a nonexistent one inside the spoken draft stays green while the 근거
  block still lists the real path. The three-item structure is bound; the
  pairing of each item to its own file, as the method table above draws it, is
  not.

## How this section came to be accurate

Everything in the two bullets above, and the novelty gate, exists because the
lap's own independent reviewer returned **block** and proved each point with a
command rather than an argument (CHARTER §4 step 5). It planted a bare novelty
claim on the T0 card and watched both this gate and `check_forbidden.py` stay
green; it planted 「FARSITE 는 …」 and 「소방청 시스템에는 …」 and watched the
other-system check stay green; and it planted 「철회 주장은 9건입니다」, a
single-digit count of this repository's own state, one digit under a `\d{2,}`
threshold. All five now turn the gate red, and so does deleting an item from the
draft.

It also found the same class one card over: Q16b's spoken scope-denial
(「33은 그 한 실행분의 수이지 저장소 전체의 수가 아닙니다」) could be deleted with
the gate green, because the assertion bound the run-directory token and not the
denial. Naming the directory scopes the count for someone reading the path; the
denial is what scopes it for a judge who is only listening. Both are bound now.

---

## 6. The two surfaces a judge stands in front of (WFG-194, 2026-09-09)

*Method proposed by the loop, not by the student (CHARTER §9). This section is
an **assembly** of the three claims already in §2 onto two surfaces that already
existed: no experiment, no model, no arm, no region (CHARTER §3.4).*

### What was silent, and for how long

WFG-182 closed correctly on its own scope — a T0 card — and said so in the
bullet struck through in §5. What it left is that the Q&A bank is a reference
the student reads from, while the surfaces a judge is actually in front of are
`web/finals.html` and the five minutes the student speaks. A count of 창의 or
독창 answered **0** on both, and critics #41, #45 and #47 each re-measured the
same zero on four consecutive days. Meanwhile this page existed and was in
**none** of the printed kit's source documents, so the project's written answer
to a row worth **20 points on both KCF scoring tables**, named **first** in the
심사기준, reached a judge only if that judge opened the bank at the right card.

### What shipped

| surface | what it now carries | bound by |
|---|---|---|
| `web/finals.html` | a 「창의성 · 이 작품이 직접 만든 것」 block at the foot of the 시스템 구조 tab: the three items as three cards, each with the repository path behind it, and a closing line saying the verdict is the judge's | `tests/test_creativity_card.py` — anchors resolve, register held, built page not stale against the template |
| `docs/auto/DEMO_SCRIPT_5MIN.md` | **one spoken sentence** in 도입 naming 창의성 and saying what the output object is, plus two ⚠ blocks (Q&A prose, outside the 300 s) pointing at the screen block, Q29a and this page | the same file, plus `tests/test_demo_script_pace.py` |
| the printed kit | this page is now the sixth of seven `SOURCES` in `scripts/build_printables.py`, printing immediately before the related-work panel | `tests/test_printables.py` |

### What it cost, stated because it is a real cost

300 seconds is fixed by the 운영요강, so the spoken sentence is paid for by the
other five segments. The re-measure
(`data/processed/demo_script_pace/pace_20260909T0321Z.json`) moved the six
segment budgets from 28 / 44 / 50 / 61 / 59 / 58 to **37 / 42 / 48 / 60 / 57 /
56**: 도입 gains nine seconds, **1막, 2막, 4막 and 마무리 each give back two** and 3막
gives back one — the least, because 3막 is the segment this script calls 「이 작품의
전부」 and it is trimmed last.
The single rate the budget exists to hold is intact — the spread is **1.02x**,
tighter than the 1.03x it replaced, and 마무리 · 한계 is not the fastest segment.
`docs/demo_script_pace.md` carries the arithmetic and the fixed-point check.

**Whether those nine seconds are worth the 창의성 row is not something this
repository can answer.** It is the judge's arithmetic, and this page says so
rather than defending the trade.

### What this does NOT show

- **A keyword count is not a mark, and the row's own 「done when」 is a keyword
  count.** Naming 창의성 on two more surfaces makes the word reachable; it does
  not make the work more creative, and no gate here can tell the difference.
  What the gates do instead is bind the **anchor paths and the register**, so a
  surface that says the word without the claim, or with the claim rewritten as
  self-praise, goes red. That was checked rather than asserted: of eight
  mutations run against the new gates, the one that keeps 창의성 in the spoken
  line and replaces the claim with 「저희 프로젝트는 매우 독창적입니다」 turns the
  suite red on two counts at once.
- **The screen block is still card-level, not item-level**, exactly as §5 says
  of the Q&A card: swapping one item's path for another real path inside the
  block stays green while all four anchors are named somewhere in it.
- **The evaluative-register mutation (M8) is still uncaught by any assertion.**
  Nothing here reads tone. What changed is that the prohibition is now written
  on the page the student reads immediately before speaking, and a test asserts
  that sentence is still there — a control on the human, not on the prose.
- **It says nothing about whether a judge will look at the 시스템 구조 tab.**
  The booth script tells the student to open it when asked 「무엇이
  새롭습니까」; whether that happens in a five-minute visit is not measured, and
  R12 (`NH-014`, the booth rehearsal on the real laptop) is the only thing that
  would find out.

### One thing this lap found on the way

`scripts/check_region_literals.py` refused the screen block, correctly by its
own rule and wrongly in fact: it tests region names by substring, and **의성**
(Uiseong) is the tail of **창의성**. So the gate that stops a per-region value
being typed into a shared screen read the card title as a claim about a region.
The fix narrows the region-name branch to names that **start** a word, and
`tests/test_check_region_literals.py` grades all four cases including the one
the narrowing deliberately cannot see (`경북의성군`). A gate whose false
positive is the word 「창의성」 would have been paid for by the next four laps
that tried to write it.

### What the independent reviewer blocked, and what it changed (2026-09-09)

The lap's reviewer returned **block** and proved each point with a command
(CHARTER §4 step 5). Its root objection is worth keeping verbatim in shape:
**every gate the lap wrote reads a source file, and nothing read what a judge is
actually handed or shown.** Three defects lived in that gap, all of them in the
finals kit:

1. **A number in prose that did not re-derive.** The lap wrote 「가장 많이 낸
   구간은 2막」 into the booth script and 「2막 most」 into this page. The deltas
   from its own artifact are +9 / -2 / -2 / -1 / -2 / -2: **four segments tie at
   two seconds and 3막 gave the least.** Both wrong sentences print in the kit.
   `test_the_doc_that_explains_the_budget_prints_the_budget_that_shipped` read
   the syllable and seconds columns and could not see a claim about their
   differences. Fixed in both documents, and
   `test_the_deltas_the_pages_claim_are_the_deltas_the_artifacts_show` now
   asserts the property from the artifacts rather than matching a string, so the
   next re-measure re-runs it instead of rewriting it.
2. **The print renderer had no strikethrough rule.** The lap struck the §5 bullet
   through with markdown strikethrough and added this file to the printables
   `SOURCES` in the same commit. `strip_inline()` knew images, links, code, bold
   and italic, and not that one. On paper the retraction markup vanished and a
   judge would have read
   「그 두 화면은 창의성에 대해 아직 침묵합니다」 as a live claim, contradicted by
   the screen in front of them. The renderer now prints a struck span as
   **「[철회] …」**; the §5 bullet is a quoted retraction in words, because this
   parser works a line at a time and a span that wraps is not matched at all;
   and `test_no_residual_inline_markup_prints_in_the_real_kit` scans the seven
   real `SOURCES` instead of a two-line literal the author typed.
3. **The screen dropped the limit that makes its third claim honest.** The
   register gates were ported to the screen and
   `test_the_card_keeps_the_limit_that_makes_its_third_item_honest` was not, on
   the one item whose content is 「we are honest about being wrong」. The screen
   said the checker reads the registry back across 「추적 문서 전체」, full stop.
   It now names the file types, the exempt record class and the reworded-claim
   escape, and a screen-side gate binds all three.

The reviewer also **corrected the lap in the project's favour twice**, which is
recorded because a review that only subtracts is not being read properly. The
mutation that keeps 창의성 and swaps the claim for a self-assessment goes red on
**seven** tests, not the two the lap claimed. And it re-derived the pace
measurement independently — 1,744 syllables, spread 1.02, the same six segment
rates — and checked the fixed-point argument by reading the numerals itself
(오십팔 and 오십육 are three syllables; 육십 is two, so 60 s genuinely would have
moved it).

**One thing it found that no source file could show.** Driving the built page
with the repository's own CDP driver: after one visit to 시스템 구조 the DOM holds
one `#syscreative`, after one language toggle **two**, after two toggles
**three**, with duplicate element ids. `renderSystem()` appends into the page and
`setLang()` resets `sysBuilt`, and nothing ever cleared it. **The class is
pre-existing** — `#syssrc` and the operator note duplicate identically — but this
lap added the largest element yet to that block and, in the same lap, told the
student to open that exact tab when a judge asks 「무엇이 새롭습니까」. Fixed by
removing the three nodes by id before rebuilding, and
`scripts/check_finals_acts.py` now opens the tab, toggles the language twice and
counts; removing the fix turns it red.

**And one objection about the review itself, which the reviewer raised against
its own method** (`mandela` leakage #5): the lap wrote both the gates and the
mutations that grade them, in one session — verifier equals designer. That is
why the mutation set here has two sources, and why the reviewer's eight were
written without seeing the lap's eight. The item-level anchor hole is what
survived both sets: it is **WFG-206**.
