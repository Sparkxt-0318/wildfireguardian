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
- **The other two judge-facing surfaces are still silent on 창의성.** Measured
  after this lap: `grep -cE '창의|독창'` returns 0 on `web/finals.html` and 0 on
  `docs/auto/DEMO_SCRIPT_5MIN.md`. The row asked for one surface and a T0 card
  and that is what shipped; the screen and the spoken script were deliberately
  not widened (CHARTER §3.4, and the demo script's segment times are a
  registered allocation that a new sentence would move — the WFG-121 (c)
  problem).
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
