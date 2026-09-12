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
| 1 | the **output object** is the contribution — a rescue order and a walking route **per point** (지점 단위), with the forecast grid as an intermediate input rather than the deliverable. ⚠ In the run that produced the committed instances the **hazard surface and the terrain are synthetic** and the **origins are sampled coordinates**: dispatch sheets on the real spread surface were made on 2026-09-12 (`outputs/dispatch_real_hazard/20260912T153043Z/`; origins still sampled, walking time flat; NH-057), and a point is not a real household address (§9) | `outputs/dispatch/README.md` and the committed sheets beside it, e.g. `outputs/dispatch/20260801T163042Z/01-거무역리공원-북쪽/dispatch_a4.html` (an instance of the object); `data/processed/rescue_routing.json` → `provenance.sources` (what was real and what was synthetic in that run); `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §3 (why the choice is not to compete on accuracy) |
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

---

## 7. The front door (WFG-207, 2026-09-09)

*Method proposed by the loop, not by the student (CHARTER §9). Like §6 this is an
**assembly** of the three claims already in §2 onto a surface that already
existed: no experiment, no model, no arm, no region (CHARTER §3.4).*

### What was silent, and how it was missed

WFG-194 named three surfaces — `web/finals.html`, `docs/auto/DEMO_SCRIPT_5MIN.md`
and, on the way, the printed kit — and delivered all three. Critic #48 then
measured the fourth, which no row had named: a raw count of 창의 or 독창 answered
**0 on `README.md`**. That is the page a judge opens before the booth, and it is
the page this loop had spent a whole window writing a Round-4 section into while
the word it is scored on did not occur once.

The useful part is *how* it stayed at zero. WFG-182's scope was a card, WFG-194's
scope was the two surfaces the student stands in front of, and both closed
correctly on their own scope. **A surface that is in nobody's scope is not
caught by any lap doing its row properly**; it is caught by someone re-measuring
the whole set. That is what the critic lap is for, and it took four of them.

### What shipped

`README.md` gains **§5 창의성 — 이 작품이 직접 만든 것** inside Round 4, below §4
and above the abstract pointer. The same three items, in the same descriptive
register, each on its own line with its own repository path as a link, plus the
없는 것 limit for item ③, the closing line that the verdict is the judge's, and a
pointer to this page and to Q29a. The README's opening paragraph and its Round-2
section are untouched (CHARTER §3.12), and no margin value was written anywhere
in the Round-4 fair-opponent block while NH-032 and NH-034 are open.

### The row's own 「done when」 could not be met as written, and this is what replaced it

The row asks for a gate that reads **「the rendered README and not a source
file」**. There is no rendered README: nothing in this tree builds it, so
`README.md` is at once the source and the artifact a judge opens, unlike
`web/finals.html`, which `make finals` builds from `scripts/finals.template.html`
and which is why WFG-194's gates could read the wrong file.

⚠ **The sentence that first stood here as the evidence for that was false, and
the independent reviewer measured it.** It said the only `README.md` string in
`scripts/` was inside a printables body paragraph. `grep -rn 'README\.md'
scripts/` returns **seven** text hits: `check_readme_figures.py` (which *reads*
the file, as a gate), `auto/render_images.py`, `auto/dashboard.py`,
`auto/gates.py`, `check_finals_acts.py`,
`investigate_routing_demo_divergence.py`, and the printables one. **The
conclusion survives** — every one of those reads or names the file and none
writes it, and neither the `Makefile` nor `.github/workflows/` generates it —
but the measurement offered for it did not, and this page is printed in the
booth kit. It is corrected here rather than deleted, because a false measurement
under a true conclusion is exactly the shape this file exists to refuse.

So the property a source-reading gate genuinely misses here is not a build step.
It is **the link**. What a judge does on the front door is press on a path, and
the only thing that makes the claim real to them is that the file opens.
`test_every_link_in_the_readme_block_opens` resolves every link target in the
block against the tree, which is as close to reading what the judge is handed as
a filesystem gets.

**And the pairing is bound item by item, which is WFG-206's hole closed on this
one surface.** WFG-206 exists because the screen block passes every assertion
with two anchors transposed: the checks ask whether the paths appear *somewhere*.
Here the block is cut at its ①②③ markers and each chunk must name its own
anchors and none of another item's, so a transposition is red. ⚠ **WFG-206 stays
open**: the screen and the Q29a card are unchanged, and this closes the hole on
the newest surface only.

### Mutations

Ten were run by the lap against its five new gates, and eight more by the
independent reviewer, which is the two-source rule §6 stated and this lap had
not followed until the review. **Nine of the lap's ten are red, and the
reviewer's set added a sixth gate — see the review section below:**

| mutation | red |
|---|---|
| delete the block heading | ✅ |
| transpose items ① and ② anchors (the WFG-206 shape) | ✅ |
| point item ② at a path that is not in the tree | ✅ |
| a bare novelty claim (「국내에서 이런 접근은 이번이 처음입니다」) | ✅ |
| a sentence about another operational system | ✅ |
| a digit count of this repository's own state (「12건」) | ✅ |
| the Korean-numeral form of the same (「여섯 건」) | ✅ |
| delete the reworded-claim limit | ✅ |
| delete the 「심사위원의 판단입니다」 line | ✅ |
| **(reviewer, D)** rewrite an item's backticked LABEL, leave the link target correct | ✅ *after the gate this review forced* |

**The tenth stays green, and it is M8 again**: rewriting the opening from the
descriptive register into the evaluative one, keeping all three items, all their
anchors, no other system, no count and both limit sentences. Nothing here reads
tone, on this surface any more than on the other three.

⚠ **One thing the mutation run itself taught, and it is why M8 was re-run.** The
first attempt at the M8 mutation went **red** — and for the wrong reason. It
opened with 「아래 세 항목은」, and 항목 is on this file's own counter list, so the
count gate fired on structural prose about the block's own shape. A mutation that
goes red for a reason other than the one it tests reports coverage the gate does
not have; it was rewritten without a counter word and then stayed green, which is
the honest result. Two of §5's mutations were originally green for the mirror-image
reason, so this is the same lesson from the other side.

### One measured false positive, excluded rather than papered over

The block sends a reader to Q&A card **Q29a**, and the card's count gate reads a
multi-digit run as a count — 29 is a card ID. The card-ID shape is removed before
the scan rather than dropping the multi-digit half (which is what the screen's
version of this check does), because the front door is the one page where a stale
headline number would be read first.

### What this does NOT show

- **The word is now reachable on four surfaces; that is not a mark.** A keyword
  count is satisfied by typing the word. What the gates hold is the anchor
  pairing, the register and the limits, and none of them can tell whether these
  are the right three items or whether a judge finds them creative.
- **It says nothing about whether a judge scrolls that far.** §5 sits below four
  other Round-4 sections on a long page. The finals screen and the spoken
  script are the surfaces that do not depend on scrolling, and they carry the
  same three items (§6). ⚠ The line count that stood here — a figure for the
  README's length — was removed by the reviewer's third nail: it was an
  unregistered count of this repository's own state, in a printed document, one
  section below a gate that forbids exactly that on the surface next door.
- **The evaluative-register rewrite is still uncaught here**, as it is
  everywhere else in this file.

### What the independent reviewer blocked, and what it changed (WFG-207)

`LOOP_CONFIG.json` sets `review: subagent`, and this lap's reviewer returned
**block** with four nails, each proved by a command. Two are corrected above.
The other two changed the gates and the claims:

**The label a judge reads was not bound to the link it opens (mutation D).** The
reviewer wrote its own eight mutations without seeing the lap's ten — which is
the two-source rule §6 stated and this lap had not followed — and D is what the
lap's set could not have found: rewriting item ①'s backticked **label** to
another real repository path while leaving the **target** correct left all
eighteen assertions green. On a rendered README the label is the whole of what a
reader sees; they read one path and land on another. So the claim 「a
transposition of two items' paths turns the suite red」 was true of *hrefs* and
false of *labels*. `test_the_label_a_judge_reads_is_the_path_the_link_opens`
now requires the two strings to be equal, and D is red.

**The count exclusion let something through, and the page did not say what.**
§7 above says `Q\d+[a-z]?` is stripped before the count scan so 「Q29a」 is not
read as 29. The reviewer planted 「근거 문서 Q33종」 and it passes: a count written
*adjacent to a Q* escapes. It is narrow, and it is now written down rather than
implied by the word 「excluded」.

The reviewer also confirmed, independently: the four link targets resolve; the
README diff is one hunk, with the opening paragraph, the Round-2 section and the
Round-4 fair-opponent block untouched and no margin value added; and the
malformed-row histogram of `docs/auto/BACKLOG.md` is identical before and after.
And one disclosed limit it re-found rather than a finding: an explicit
superiority claim over an *unnamed* class (「국내 어떤 시스템보다 앞서 있는」) trips
neither the novelty pattern nor the other-system list, because nothing here
reads tone — which is M8 again, from a third direction.

---

## 8. The anchor (WFG-210, 2026-09-09)

*Method proposed by the loop (critic #49), not by the student (CHARTER §9).*

### What was wrong

<!-- forbidden-ok: wc013-output-object-is-per-household-en -->
Item 1 claims the contribution is the **output object** — a per-household
walk-or-be-rescued verdict, the walking route that goes with it, and the village
dispatch list. ⚠ **2026-09-10 (WFG-222, WC-013): 「per-household」 is quoted here
as the wording item 1 carried in September 2026 and is now withdrawn** — the unit
word is **point-level (지점 단위)**; §9 below is the withdrawal. ⚠⚠ And the
registry did **not** find this line: the phrase wraps across two source lines and
`scripts/check_withdrawn_claims.py` scans one line at a time, so the pragma above
was placed by hand by the WFG-222 lap rather than because a gate asked for it
(§9's 「What this does NOT show」). On every surface that answers it, its only anchor was
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`, a landscape note whose
subject is the other systems. Two things follow, and the second is the one a
judge feels:

1. `tests/test_creativity_card.py` spends four graded mutations keeping those
   names out of what the student **says**, in either direction, because this
   card carries no source line and a sentence about another system here would be
   unsourced by construction (`WC-007`, `WC-008`, `WC-009`). The anchor then
   handed the judge a document full of them. A principle cited, and its opposite
   implemented one line below.
2. A judge who reads item 1 and says 「그 산출물을 하나 보여 주십시오」 had no
   path from any surface — while `outputs/dispatch/` has carried committed
   instances of exactly that object the whole time: the A4 dispatch sheet for
   each village cluster, the 마을방송 script, the SMS drafts, none of them ever
   sent.

It was **inherited, not chosen four times**: written in §2's table (WFG-182),
taken by the finals screen (WFG-194), by the README's front door (WFG-207), and
standing unchanged in Q29a's own 근거 line. Each of those laps did its own row
correctly. That is why the fix is a gate and not four edits — the next surface
would have inherited it a fifth time.

### What changed

Every surface that answers item 1 now names a path to an instance of the object
**first**, and keeps the landscape note beside it with its role stated: it is
the anchor for the *choice* not to compete on accuracy, which is what it has
always honestly been. Nothing was deleted and no comparison sentence was added.

One asymmetry, and the version below is the **second** one written here, because
the first was false and the independent reviewer caught it on this page.

`README.md`'s block is the **only** surface carrying a `\d{2,}` count assertion
(`test_the_readme_block_holds_the_same_register_as_the_card`; the screen's
register check drops that half deliberately), and every committed instance lives
under a run stamp — `outputs/dispatch/{stamp}/…` — which that assertion reads as
a count. So the front door names the committed **index**,
`outputs/dispatch/README.md`: one click above the sheets, and the page that
states the clusters are not 행정리, that nothing was transmitted, and which of
the run's points the sheets cover. The other three surfaces name a sheet **and**
the index. Weakening the count assertion to fit a path in was the alternative and
was declined: it is the assertion that caught WFG-117 and WFG-178, and it guards
the page a judge reads first.

⚠ **What the first version of that paragraph said, and why it is recorded rather
than quietly replaced.** It read 「The surfaces with no count assertion name a
sheet directly」 — and at the time it was written the finals screen named the
index, exactly as the README did, with no count assertion anywhere near it. The
reviewer proved it in one command rather than arguing: putting a stamped sheet
path into `CREATIVE[0].doc` and running the eight suites that read the screen
gave **262 passed** and `check_forbidden.py` exit 0, so nothing had constrained
that surface and the reason given for it was invented after the fact. The
sentence generalised one real constraint into an account of a choice nobody had
made, in the *measured* register, on a page that is a hashed `SOURCES` entry of
the printed booth kit — which is the defect class this whole card exists to
prevent, one level up from the anchor it was fixing. The screen now names a
sheet, so the claim above is true; the sentence it replaces is kept here because
that is what §3.7 asks and because the mechanism that spread it — a sentence
inherited verbatim from this card into `tests/test_creativity_card.py`'s own
header comment — is the same mechanism that carried the original anchor onto
four surfaces.

### The gate, and the mutation that graded the gate rather than the surface

Four new assertions: an instance exists in the tree at all; every surface hands
a judge one; item 1's anchors are never *all* documents about the other systems,
decided by reading the anchors' contents rather than by matching their names;
and the classifier that decides that still separates the two anchors.

Nine mutations, re-runnable by a stranger with
`python scripts/mutate_creativity_gates.py` rather than by a recipe this lap kept
to itself. Seven are on the surfaces — reverting each of the four anchors, naming
the directory as prose with no resolvable file, swapping in a second document
about the other systems, and pointing the premise check at a directory holding no
sheets — and two move the classifier's threshold in opposite directions. **All
nine are red against the shipped tree**, each on the assertion it was aimed at,
and the script prints which test failed for each so the grading can be read
rather than trusted.

**The eighth was GREEN when it was first run, and that is the useful part of this
section.** It is red now only because the assertion it exposed was then written;
the numbering here is the final set, not the order of discovery. Raising the classifier's
threshold to a number no document reaches makes it answer False for everything,
which turns 「item 1's anchors are not all documents about other systems」 into
「they are not all members of the empty set」 — true of any surface, on any tree.
The whole suite stayed green. That is the **third** time this one file has
shipped a check that could not fail: the count assertion that was digit-only
and could not see 「여섯 개」, the Korean-numeral half written with a trailing
`\b` that after a Hangul syllable can never match, and now a free constant.
**The shape is the same each time — a check whose failing case is unreachable —
and the only thing that has ever found it is mutating the gate itself rather
than the document it reads.** The floor is now asserted in both directions, so
raising the threshold past the note's own content is red and lowering it until
every file classifies is red too.

### What this does not show

The classifier reads a named list of systems, so a document about a system this
repository has never named is not classified and could still stand as item 1's
only anchor. That is the same residual limit §2 records for the spoken draft,
one level up, and the cold read is still what catches it. The assertions bind
the **anchor**, not the wording: a surface may describe the object however it
likes, and nothing here reads whether the description is true of the sheet.

---

## 9. The wording (WFG-222, 2026-09-10)

*Method proposed by the loop (critic #54), not by the student (CHARTER §9).*

**§8 ends with a sentence that predicts this section:** 「The assertions bind the
**anchor**, not the wording: a surface may describe the object however it likes,
and nothing here reads whether the description is true of the sheet.」 It was
written on 2026-09-09 as a residual limit. It was already a live defect on five
surfaces when it was written.

### What was wrong

On 2026-09-09 at 2206Z the independent reviewer of WFG-212 broke the Round-4 lead
block of `README.md` on a **conjunction**: two artifacts named side by side assert
their conjunction, and the conjunction was false. The committed dispatch documents
come from the rescue-routing pipeline, whose `provenance.sources` reads
`walk_network: osm`, `drive_network: osm`, `shelters: osm`, `depots: osm`, but
**`hazard: synthetic`**, **`terrain: synthetic`**, **`origins: sampled candidates`**.
The run where the walking graph and the spread surface are *both* real is a different
execution and it produces four-way verdicts, not dispatch documents. That lap fixed
`README.md:212-251` and shipped.

It fixed **one** surface. Measured by critic #54 at `3eec471` and re-measured by this
lap at `49ac16e`, the identical claim in the identical words stood on five more:

⚠ **The withdrawn wordings are described here and not transcribed.** This file is one of
the seven sources of the printed booth kit, and the WC-005 / WC-007 precedent
(`docs/withdrawn_claims.md` §5f) is that a correction note on a printed page explains the
sentence rather than reprinting it — otherwise the kit carries the withdrawn sentence in
the same weight of type as the correction. The exact spellings are in
`docs/auto/withdrawn_claims.json` under `WC-013`, where a machine reads them.

| surface | what it carried | bound |
|---|---|---|
| `README.md` §5 item ① | the household register, plus 「그 산출물의 실물이 저장소에 커밋돼 있습니다」 | none, 180 lines below the block that denies it, **in the same file** |
| `web/finals.html` + `scripts/finals.template.html` | the same, in Korean **and** English | none |
| `docs/auto/JUDGE_QA.md` Q29a (**T0**, spoken from memory) | the same, as the rescue ordering that follows the forecast grid | 행정리 only |
| `docs/auto/DEMO_SCRIPT_5MIN.md` 도입 | the same, in the sentence the student speaks to open the demo | none |
| `docs/creativity_card.md` §2 table row 1 | the same, in English, printed in the booth kit | none |

Two things are wrong and they are not the same size. The **register**: the committed
instances do not start from households, and `docs/auto/JUDGE_QA.md` Q20a's honest
definition of 「가구」 as one node of the OSM walking graph sits two hundred lines from
every surface that used the word. The **conjunction**, which is the larger half: on
three of the five, item ① sits immediately beside item ② 「두 축이 동시에 실제인 실행」,
so a judge reading them in order reads 「real roads + real fire → these committed
sheets」.

### What shipped

Every block that asserts the committed instances exist now carries, **in that same
block**, what was synthetic in the run that produced them and that the origins were
sampled — 지점 단위 rather than 가구 단위, and 「실제 확산면으로 만든 출동 지시서는
아직 없습니다」.

⚠ **2026-09-12 (NH-057):** that last sentence is no longer true. The author ran the rescue pipeline on the real 영덕 spread surface on the laptop and committed the sheets at `outputs/dispatch_real_hazard/20260912T153043Z/`; every one of the surfaces above now names that path in the same block, with the run's own bound (origins still sampled, walking time flat). The record above is kept as written.

⚠ **The row named five surfaces. Eleven were corrected, and the row's list found the
fewest of them.** The lap's own sweep added a sixth, `docs/auto/finals/RELATED_WORK_PANEL.md`,
a *printed* panel carrying the same sentence about this project's own output.
**Registering `WC-013` then found three more** in files nobody had reason to open —
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` (which instructs the student what to
say at the booth), `docs/auto/knowledge/PYROGEOGRAPHY.md` and
`docs/auto/research/WEEKLY_2026-W36.md`. **And the independent reviewer found two the
registry's first pattern still missed** — `docs/evidence/greenpeace_2026_survey.md` and
`docs/firefighter_consultation.md`, whose wordings (「출동 순서」, 「인명」) were outside the
anchor list; the pattern was widened in the same lap, after measuring that the two new
alternatives hit nothing else in the tree. That ratio is the section's real finding: a
hand list found five, a machine found three, and a hostile reader found two more.

Two things were **added** rather than swapped, because a word swap alone would have
left the conjunction standing:

* `docs/auto/JUDGE_QA.md` Q29a gains a 없는 것 item, placed **first**, that tells the
  student not to read items ① and ② as one sentence and gives the answer to the
  question critic #54's judge drill found unanswerable anywhere but the README —
  「이 출동 지시서, 진짜 불로 만든 겁니까?」 The answer is 「아직 아닙니다」.
* `docs/auto/DEMO_SCRIPT_5MIN.md` takes the bound in a ⚠ block rather than in the
  spoken line, and that is deliberate: §1's syllable budget is measured
  (`tests/test_demo_script_pace.py`), one added sentence moves the segment off the
  document's single rate, and 가구 → 지점 is the same two syllables. The student says
  the corrected word inside the same spoken segment and answers the rest if asked.

### The gate, and what makes it different from the one it replaces

`tests/test_output_object_claim_bounds.py` holds a **structural** property over seven
declared blocks (the six sources plus the built screen): a block that says committed instances exist must carry the
synthetic-hazard and sampled-origin bounds itself. It is not a wording gate.

* It cannot be satisfied by deleting the claim — one assertion fails if a surface
  goes quiet, because a silent screen is the state WFG-194 found.
* Its families are not strings this lap invented: 합성 / synthetic and 표본 / sampled
  are the words `provenance.sources` uses about itself.
* It is **graded against text this lap did not write.** ⚠ Its first version was not:
  it built a mutation by deleting whatever matched its own two patterns and then
  asserted those same two patterns reported them missing, which cannot fail. The
  lap's independent reviewer blocked the lap on it — `mandela` pattern #4, a scorer
  grading buckets it drew itself — and the repair is a corpus of the **six blocks
  the repository actually shipped at `3eec471`**, written by five earlier laps over
  six days, none of which had seen these patterns. Every one of them is refused, and
  a second test re-derives the corpus from git and refuses a copy that has drifted.
* It reads **polarity**, not only tokens, and that assertion is also the reviewer's.
  Its first version returned green on a block carrying 합성, 표본 좌표 and the
  existence claim while asserting the **opposite** of all three. So a block must now
  also say the thing they add up to — that no dispatch document has yet been made on
  a real spread surface — and a block that asserts the run *was* real is refused
  outright. The reviewer's sentence is kept verbatim as a regression.

`tests/test_readme_round4_lead.py` now runs its bound assertion over the whole Round-4
**section** rather than over its `lead` fixture. That fixture boundary is what let one
file answer its own headline claim two ways, and it was written by the lap that made
the claim. Both new assertions there were graded against the pre-fix text and both go
red on it.

The spelling half is `WC-013` in `docs/auto/withdrawn_claims.json`. Registration is
what makes the machine read every gated file rather than the five a critic listed —
and it earned its keep immediately: it found **three** copies no list named, in
`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`, `docs/auto/knowledge/PYROGEOGRAPHY.md`
and `docs/auto/research/WEEKLY_2026-W36.md`.

### What this does NOT show

**It does not show the claim is now true everywhere, and one measurement says so.**
`scripts/check_withdrawn_claims.py` scans **one line at a time**, so a registered
spelling that wraps across a source line break is invisible to it. This section's own
§8 is the proof: 「a per-household / walk-or-be-rescued verdict」 straddles two lines
there and the registry did not report it. The pragma on that line is there because a
human put it there. The same limit is recorded for `WC-012` in
`tests/test_withdrawn_claims_registry.py`, where two halves of one sentence had to be
registered as two patterns for exactly this reason, and it is now the third measured
limit of the registry beside the two in `docs/withdrawn_claims.md` §4 — a reworded
claim escapes, and a claim in a `.py` or `.bib` file is out of scope.

**It does not show the register is corrected everywhere it appears.** 「가구 단위」 is
still the right phrase in three places in the same Q&A bank, deliberately: Q20a
*defines* it, Q16 names the quantity `ingress_survival_time_min`, and Q16a says what
other systems' published material does not show. The patterns are anchored on the
output-object phrases so that none of the three trips, which also means a fourth,
differently-worded copy of the same claim escapes both gates.

**And it does not make the object better.** Nothing measured here changed. The
committed dispatch documents are the same documents; what changed is that every page
that offers them now says, in the same breath, what fire they were made on.
