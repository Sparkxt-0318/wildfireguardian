# CRITIC_LATEST — critic #9, 2026-09-04T0950Z

Window `12bf2d9..ce31b91` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `ce31b91` in a
fresh cloud sandbox. `1312 passed, 62 skipped` in 206 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). Against critic #8's cold reading at
`12bf2d9` (`1273 passed, 62 skipped`) that is **+39 passed, skips unchanged** — like for
like, both cold, third window running. `verify`, `snapshot-verify`, `env-check` PASS;
`baseline-verify` WARN, expected off-laptop, `hard: false`, ninth window and still not a
finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. **Green at HEAD for a
sixth consecutive critic lap.**

**The window's headline: the bank stopped contradicting itself, and it cost five files.**
Critic #8's F42 was one document holding two opposite **T0** answers to one question. It is
closed. One sentence — 「이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, 어떤
소스가 일차여야 하는지는 재지 않았습니다」 — now stands in `JUDGE_QA.md` Q10 and Q10d, in
`detection_floor.md` §10 (whose 우선순위표 is gone, replaced by a 「이 측정이 말하는 것」
table where the 사람 신고 row reads 「재지 않았습니다」), on the booth card's front and in
its trigger table, and in `docs/SESSION19_REPORT.md` Phase 3, which was **annotated rather
than edited** because it is a record. Grepped every `.md` and `.html` in the tree this lap:
the only surviving affirmative-primacy strings are that dated withdrawal block and §10's own
paragraph explaining what its table used to be. Track B 제출 자료 takes the point critic #8
named and withheld: 16 → 17.

**And the window's own gate is 2-for-20 against a reader who did not write it.** That is
this lap's finding and its root objection.

---

## fix-before-next-row

**One item, and it is one sentence.**

1. **WFG-069 (F48)** — `docs/detection_floor.md:13`, the first sentence of the file that
   Q10 and Q10d both name as their 근거, reads 「한국의 산불 탐지는 사실상 전부
   사람입니다」 and rests it on the 99 % statistic that §10 of the same file forbids, in
   bold, from carrying a conclusion in a judge-facing document. The window's claim is that
   no judge-facing document now elects the human channel. That claim is false at line 13 of
   the document the fix cites. Narrowing it is one sentence and one scope label; no number
   moves and no artifact is touched.

Otherwise **the table order stands and this lap does not reorder it**. The next `todo` row
in table order is **WFG-003** (finals screen audit + the 5-minute demo script), which the
0855Z lap deferred for a stated reason that is now spent, and **WFG-067** after it. The one
ordering question this lap will not settle by itself — whether WFG-062 jumps ahead of the
booth rows — is **NH-021**, with options, for the author.

---

## fix-this-sprint

### F47 — The gate written to stop a claim is 2-for-20 against sentences its author did not write

**Where:** `tests/test_detection_ordering_is_not_claimed.py` — `BANNED_PRIMACY` /
`primacy_violations` (`:371-403`) and `PRIORITY_WORDS` / `SOURCE_NOUNS` /
`NEGATION_MORPHEMES` / `priority_violations` (`:541-641`). **Row: WFG-062, raised P1 → P0.**

The 0855Z lap's own reviewer wrote twenty primacy sentences and **nineteen escaped** the
first draft. The lap then added the structural rule, folded the reviewer's seven escapes in
as cases, and shipped. This lap ran the same experiment again with a set written from the
withdrawn **claim** rather than from the deleted **sentences**, by a reader who had not seen
the patterns. Twenty sentences, each an affirmative assertion that some human channel is the
primary trigger source:

| detector | caught |
|---|---:|
| `primacy_violations` (the spelling family) | **0 / 20** |
| `priority_violations` (the structural rule) | **2 / 20** |
| invisible to **both** | **18 / 20** |

Three escape classes, and none of them is a spelling:

1. **A source noun outside `SOURCE_NOUNS`.** 「119 상황실이 일차 트리거입니다」,
   「지자체 상황실 접수가 1순위 트리거입니다」. The list is
   `신고 · 위성 · GK2A · FIRMS · 감시카메라 · 무전`; 119, 상황실, 목격, 주민, 이장, 전화
   are not in it. The reviewer's own cut sentence — 「실무상 119·마을 무전이 그 자리에
   오겠습니다만」 — was caught only because 무전 happened to be listed.
2. **A priority word outside `PRIORITY_WORDS`.** 「사람 신고가 트리거의 출발점입니다」,
   「탐지 체계의 머리에는 사람 신고가 옵니다」. 출발점, 기점, 머리, 맨 앞 are all ordinary
   Korean for the same claim.
3. **A negation morpheme anywhere else in the sentence — and this is the one that matters.**
   `priority_violations` exempts a whole sentence if any of `않 · 없 · 아니 · 못 · 말하지`
   appears in it. 「위성이 1 ha 아래를 보지 **못**하므로 최초 인지는 사람 신고입니다」 is
   an affirmative primacy claim wearing a negation, and it is exempt. So is 「GK2A는 발화를
   잡지 **못**하고, 따라서 신고가 앞선 채널입니다」, and 「위성이 **아니**라 사람 신고가
   주된 트리거입니다」.

Class 3 is not a corner case. It is the sentence shape **this repository's own honest prose
already uses everywhere**: 「위성은 …하지 못합니다, 그래서 …」. The rule is therefore weakest
exactly where the next author is most likely to write, and it gets weaker the more the
author sounds like this project.

**What this is not.** It is not a claim that the lap overstated its gate to the student: it
did the opposite, and that is the best thing in the window. Q10d, a **T0** answer, now says
in the student's own drill material that this is 「문자열·구조 검사이지 뜻을 읽는 검사가
아닙니다」, that 「같은 주장을 다른 말로 쓰면 지나갈 수 있다」, and — the load-bearing line —
**「부스에서 이 검사를 근거로 들지 마십시오」**. NH-019's note was rewritten the same way.
A loop that measures its own instrument, finds it weak, and writes the weakness into the
sentence the student recites is doing the thing this project is selling. The finding is
about what to build next, not about what was said.

**Nor is it a claim that a document is currently wrong because of it.** Grepped this lap:
every guarded surface is clean in **meaning**, not merely in spelling. The gate did what it
was written for.

**What it decides.** WFG-062 asks for a general registry of withdrawn claims. Critic #8's
cheapest test for it was 「does one sentence in three files plus one gate close WFG-063」; the
0855Z lap answered honestly that it took **five** files and a **second** hand-rolled claim
family. This lap adds the other half of the answer: the second family, measured from
outside, catches 2 of 20. Two windows have now each spent a lap hand-rolling regexes, and
the third one is already visible.

### F48 — The document that spent this window forbidding a conclusion opens by stating it

**Where:** `docs/detection_floor.md:13-15` (§0, sentences one and two) against `:310-320`
(§10's 99 % ban). **Row: WFG-069 (P0), new, and the one `fix-before-next-row` item.**

§0 opens: 「한국의 산불 탐지는 사실상 전부 사람입니다. 보도된 해에 산림청·119 가 접수한
산불 신고의 **99 %가 목격 신고**였고 …(경향신문, 2023-04-28)」.

Two defects in two sentences.

1. **The claim.** 「탐지는 사실상 전부 사람입니다」 is a stronger human-primacy assertion
   than anything deleted this window — the deleted ones at least hedged as 「설계 함의」 or
   「가정」. Its only ground is the clause after it, and §10 of the same file says in bold
   that this value 「이 표의 근거로 쓰지 않습니다 … 판정단이 보는 문서에서 이 값이 결론을
   떠받치게 두지 않습니다」. §0 lets it hold up a conclusion in sentence one of a 판정단이
   보는 문서, and `JUDGE_QA.md` Q10 and Q10d both send the judge to this file.
2. **The scope.** §0 writes 「보도된 해에」. The article is dated 2023-04-28 and says
   「올해」, so the figure is roughly four months of accumulation — which §10 itself spells
   out as 「연중 누계, 즉 잠정치」. CHARTER §3 rule 5b: an interim tally is never presented
   as a final one. §0 presents it as an annual fact and the correction sits 300 lines below.

**Why both new gates are blind to it, and why that is instructive rather than sloppy.**
`priority_violations` needs a token from `PRIORITY_WORDS` and the sentence has none, so the
rule never looks. `primacy_violations` would fire on the 99 % clause, and the 0855Z lap
pragma-licensed that exact line, deliberately and in writing: 「§0 은 배경 설명으로 출처와
함께 그대로 둡니다」. Both decisions are defensible alone. Together they leave the strongest
surviving primacy sentence in the repository inside the guarded file, unflagged and
licensed — which is F47 in one concrete instance.

**The fix is small.** The same 경향신문 article carries a figure that is a count rather than
a share and needs no interim label: 경북 152 cameras, 최초 발견 **0건** over two years. §0
can open on that.

### F49 — The Q&A bank now miscounts itself by eight, and the report that named it miscounted it too

**Where:** `docs/auto/JUDGE_QA.md:17-23`; `tests/test_judge_qa_bank.py` `QUESTION_RE`.
**Row: WFG-057 (P0), fourth window, and it moved the wrong way.**

Counted at `ce31b91` with `grep -cE '^\*\*Q[0-9]+[a-z]? · T[012]'` and per tier:

| | header says | file holds | |
|---|---:|---:|---|
| total | 33 | **41** | +8 |
| T0 | 14 | **15** | +1 |
| T1 | 13 | **19** | +6 |
| T2 | 6 | **7** | +1 |

Last window critic #8 could say one tier count was wrong. Now **all three** are, and the
total is out by eight. The header is the file's own drill plan and it tells the student
「T0 … 이것만 완전히 자기 말로 만드십시오」, so the student who obeys it memorises fourteen
of fifteen and the one they skip is **Q10d**, the guard.

**And the defect has started infecting the reports.** Critic #8 wrote 「the file now holds
**38 questions and 15 T0s**」. At its own window head `12bf2d9` the file held **40**; 38 was
the count at `8e0a6ad`, the head of the window before. It carried the previous window's
total beside the current window's tier count, which is exactly what a document that cannot
count itself does to the people reading it. This lap says so about its own series first.

**This lap deliberately added no question to the bank.** The drill turned up two it could
have added; adding a 42nd header to a file that says 33 would make this finding worse by the
hand of the lap reporting it. They are filed as WFG-069 and inside WFG-062 instead. CHARTER
§7: a lap that verifies and finds nothing it should change reports exactly that.

### F50 — The daily check this routine is asked to perform still cannot answer its question

**Where:** `scripts/auto/gates.py` `assert_reported`. **Row: WFG-056, second window,
reproduced on a window that removes the last excuse.**

Critic #8 ran eight bases across 24 hours and got eight zeros naming one report. This lap
ran the four commits of its own window — `12bf2d9`, `d8aec94`, `0965b15`, `ec2e813` — where
the push boundaries are known and only one report exists. All four exit 0 and all four name
`docs/auto/reports/2026-09-04T0855Z-dev.md`, **including `--base d8aec94`**, which is the
commit that carried critic #8's own report: the check answers 「a report travelled」 for a
range whose report is behind the base. On a window with one report it is uninformative for
every base, not merely weak. Two critic laps in a row have now been unable to perform the
verification their prompt asks for, and both have said so rather than reporting a pass.

**What this lap *can* verify from the report files themselves:** every dev report in the
24-hour window carries a `Reviewed by:` line except `docs/auto/reports/2026-09-04T0401Z-dev.md`
(critic #7's F40, unchanged, a record) and `docs/auto/reports/2026-09-03T1300Z-dev.md`, which
predates the independent-review rule's introduction at `a131daf` and is therefore not a
defect.

### F51 — Carried, verified unchanged, with the checks that were run

- **WFG-067 (F41)**, P0, second window, and it sits on a ☑ line. `git cat-file -t a562045`
  in this fresh clone still answers `fatal: Not a valid object name`; `web/finals.html`
  still carries `"git":"a562045"`. Nothing in this window touched `web/`. `JUDGE_QA.md` Q35
  answers it honestly at the booth, which is why this is a row and not a `fix-before-next-row`.
- **WFG-051 (F46)**, P0, **fifth window**. `docs/NUMBERS.json` → `fire2025_chain_deaths`
  still records `agency: 중앙재난안전대책본부 … source: newsis`, and `README.md:198` and
  `:510` still assert 「경상북도 최종 집계·중앙재난안전대책본부 확인」 with nothing in this
  repository supporting the confirmation. Critic #8 opened the 대구MBC page and it names
  경상북도 재난안전대책본부 and no 중대본 at all. This is the oldest live defect in the tree
  and the only P0 that has survived five critic laps untouched.
- **WFG-065 (F38)**, third window. 8.2 km h⁻¹ is still only in
  `docs/auto/knowledge/PYROGEOGRAPHY.md`, the backlog and three critic reports — nothing a
  judge is handed. Checked by `git grep` over `docs/*.md`, `paper/`, `web/` and `README.md`.
- **WFG-054 (F28)**, fourth window. Still unbitten for the same reason: there has still not
  been a first author reply.
- **WFG-055, WFG-061 / NH-019, WFG-050, WFG-048, WFG-044, WFG-038 / WFG-039, WFG-068** —
  unchanged; nothing in this window touched them.

---

## note

- **N52 · The best line in the window is a line that weakens the window's own deliverable.**
  Q10d is a **T0** answer, memorised word for word, and it now contains
  「부스에서 이 검사를 근거로 들지 마십시오」 about the gate the same lap had just built.
  The lap's reviewer put it there after breaking the gate 19 times in 20. Most projects
  would have shipped the gate and the sentence 「다섯 표면이 어긋나면 실패합니다」, which is
  what the draft said. This one measured, lost, and wrote the loss into the student's script.
- **N53 · A record was annotated instead of edited, and it is the right instinct.**
  `docs/SESSION19_REPORT.md` Phase 3 keeps its 우선순위표 with 사람 신고 at rank 1 and puts a
  dated withdrawal block above it saying which two grounds vanished and where the current
  wording lives. CHARTER §3 rule 7 in practice. It also means the record is now inside a live
  content gate and needs pragmas to stay there, which is a cost worth noticing but not
  paying differently.
- **N54 · The census is comparable for a third window and the habit is now the instrument.**
  `1273 → 1312` cold to cold, `+39`, skips unchanged at 62. The 0855Z lap quoted both its
  own readings with their temperature (`1293` cold, `1318` warm) rather than picking the
  bigger one. WFG-039 has now reproduced in four consecutive laps; it is still `todo` and
  still P1, and the reason it has not hurt anyone is that three laps in a row have been
  careful by hand.
- **N55 · Nothing new about the world was asserted this window, and that is the honest
  `factchk` result.** The diff's new prose is about this repository: a withdrawn claim, a
  gate, a dead commit id. The one external-world claim it added is Q35's assertion that
  `a562045` does not resolve, and this lap ran that command itself and got the stated answer.
  The 99 % statistic and the 2 km / 1 ha size floor are both carried over, and the first of
  them is F48. No new citation was added, so nothing needed opening.
- **N56 · The author has replied to nothing, for a sixth lap.** Searched the mailbox this
  lap: **27** threads match `subject:"WildfireGuardian autoloop"` in 14 days, and every
  thread holds exactly one message, the loop's own report — confirmed by fetching the newest
  thread rather than trusting the preview. PR #31 has zero comments.
  `docs/auto/decisions_seen.json` still does not exist. Sixteen entries are now open,
  **NH-016's date is today**, and NH-021 is added by this lap. The loop is now writing
  decisions faster than it is receiving them, which is a failure mode of the loop's design
  rather than of the author.

---

## The judge drill

Ten questions, answered using only files in the repository.

| # | question | can a file answer it? |
|---|---|---|
| 1 | 「부스에서 무엇을 보여 주십니까?」 | **Yes.** `web/finals.html`, four tabs, five evidence cards; nine committed screenshots at `docs/auto/finals/screens_20260904T0630Z/`; `docs/finals_screen_v2.md`. R2 ticked, unchanged |
| 2 | 「그러면 왜 사람 신고를 일차 소스로 둡니까?」 | **Yes, and it could not last window.** The premise is refused in one sentence that is now identical in Q10, Q10d, `detection_floor.md` §10, the booth card and the screen. WFG-063 closed |
| 3 | 「그 문장이 다른 말로 되살아나면 무엇이 잡습니까?」 | **Partly, and the bank says so first.** Measured 2 of 20 against an outside mutation set (F47). Q10d already tells the student not to cite the check at the booth. WFG-062, now P0 |
| 4 | 「그런데 이 문서 첫 줄은 탐지가 사실상 전부 사람이라고 쓰여 있습니다」 | **No.** `docs/detection_floor.md:13`, on the statistic §10 forbids. F48, WFG-069, the one `fix-before-next-row` item |
| 5 | 「화면 아래 「commit a562045」 로 이 화면을 다시 만들 수 있습니까?」 | **No**, and the bank says 「아니오」 honestly at Q35 with what *is* reproducible. WFG-067, second window |
| 6 | 「사망 26명은 어느 기관 집계입니까?」 | **Half**, fifth window. Manuscript and `data_sources.md` say 경상북도; the registry and `README.md:198` say 중앙재난안전대책본부. WFG-051 |
| 7 | 「Q&A 카드는 몇 문항이고 그중 몇 개를 외워야 합니까?」 | **No.** Header says 33 / 14 / 13 / 6; the file holds 41 / 15 / 19 / 7. F49, WFG-057 |
| 8 | 「이 산불의 확산 속도는 시간당 얼마였습니까?」 | **No file a judge can be shown.** Q34 answers honestly (「저희가 측정한 값이 아닙니다」). WFG-065, third window |
| 9 | 「5분 시연 대본이 있습니까? 부스 노트북에서는 어떻게 띄웁니까?」 | **No, twice.** `docs/auto/DEMO_SCRIPT_5MIN.md` and `docs/auto/finals/BOOTH_SETUP.md` do not exist (R4 ☐, R3 half ☐). WFG-003 is the next row; WFG-037 follows |
| 10 | 「제출용 번들을 하나로 받을 수 있습니까?」 | **No.** `release/` does not exist (R9 ☐, WFG-036, plan date 09-10). Three of eleven `KCF_READINESS.md` lines are ticked |

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass**, and stronger than last window | Green at HEAD for a sixth window, `1312 / 62` cold, and this window the machine did the thing I actually look for: it built a check, tested it, could not defend it, and wrote the failure into the student's own script instead of into a footnote. Show me `test_detection_ordering_is_not_claimed.py`'s docstring beside Q10d and that is a better ninety seconds than the screen |
| KCF judge · 재난 대응 공무원 | **pass**, held | The answer I get when I ask about the telephone is now the same answer wherever I ask it, and it ends in 「재지 않았습니다」. Good. But your own design document still opens by telling me detection in Korea is essentially all human, and I am the person who would know whether that is true. Fix the first sentence before you show me the file |
| fire-behaviour scientist | **pass**, unchanged and still short of strong | Nothing about fire behaviour moved this window. 8.2 km h⁻¹ is still the number that characterises 의성 and it is still in a note I would not be handed (WFG-065, third window). The size floor is still given as an order of magnitude, which is still the right instinct |
| ML reviewer (leakage, baselines) | **pass**, and this is the window it had something to say | No model, split, metric, arm or eval moved, so `mandela` fires on nothing in the science. It fires hard on the **gate**: `test_each_withdrawn_primacy_spelling_is_caught` is parametrised over sentences the pattern's author wrote in the same session as the patterns — pattern #4, a scorer grading its own buckets. The 0855Z lap named this itself, from its reviewer. An outside set breaks it 18 in 20 (F47). External ground truth is a mutation set the author did not write, and it should be **reported as a number** in every report that ships a claim gate |
| statistician | **pass**, and one complaint is now two windows old | Third comparable cold census in a row, `+39`, temperature stated: that is a habit and I credit it. Against it: a file that miscounts itself by eight is not a file I can audit (F49), and the report that named the miscount miscounted it (38 against a head holding 40). And `--assert-reported` gave me four zeros for four different bases naming one report. Three of your instruments this window returned a value that does not depend on the thing being measured |

**Where they agree:** the window's honesty about its own weakest artifact. Four of five named
Q10d's 「부스에서 이 검사를 근거로 들지 마십시오」 unprompted.

**Where they split:** the professor and the ML reviewer are looking at how the loop treated
its gate and are satisfied; the 공무원 and the statistician are looking at the two documents
in front of them — §0's first sentence and the bank's header — and both are wrong in a way
a judge finds in the first thirty seconds of reading.

---

## The root objection, and its cheapest test

Critic #4 asked which numbers can be wrong without a gate noticing. #5 asked which sentences.
#6 asked which sentences the repository already knows are wrong. #7 asked why eight windows
had never touched what judges look at. #8 asked why every gate points away from the screen.
This one is about the instrument the last two windows reached for:

> **The loop's answer to 「a gate cannot read meaning」 has twice been a bigger string gate,
> and it has twice graded that gate with mutations it wrote itself.** Measured from outside
> this window, the new gate catches **2 of 20**, and the class it is blindest to is the
> sentence shape this repository's own honest prose already uses: a negation anywhere in the
> sentence exempts the whole sentence, so 「위성이 보지 **못**하므로 최초 인지는 사람
> 신고입니다」 is invisible. The gate is strongest against sentences already deleted and
> weakest against sentences not yet written. Meanwhile the single strongest surviving
> primacy claim in the tree sits at line 13 of the guarded file, licensed by a pragma the
> same lap wrote. Two laps have now been spent this way and the third is already visible in
> WFG-062's own row text: two claim families, six regex rules, two pragma vocabularies, two
> guard lists, one file named for one of the claims.

**The cheapest test, and it is one lap:** take WFG-062 and build the withdrawn-claims
registry, but **have the reviewer subagent write the mutation set before the rules exist**,
and print the catch rate against it as a number in the report — the way this repository
prints pass/skip counts with their temperature. If an outside set is caught above about half,
the registry is the right instrument and it should absorb both hand-rolled families. If it is
not, that is the more valuable answer: string matching is the wrong instrument for claims,
and the right one is the rule that every judge-facing claim sentence cites a registry key or
an artifact — which is WFG-030's shape, already in the backlog, and a different lap.

**And it is not this lap's call which comes first.** Doing WFG-062 next costs a booth row in
a twelve-day sprint whose readiness checklist is 3 of 11. That trade is **NH-021**, with
three options, for the author.
