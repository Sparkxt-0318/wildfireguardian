# Critic #69 — 2026-09-11T1959Z, reviewed `8952a5b`

**The next dev lap reads this file first.** Window `de0bcd3..8952a5b`. `de0bcd3` is this
shallow clone's oldest resolvable commit (2026-09-11T00:23:02Z, 19 h 36 m back), so it is the
base rather than a chosen one; the clone is SHALLOW at **50** commits, measured here with
`git rev-parse --is-shallow-repository` and `git rev-list --count HEAD`, and was deliberately
NOT deepened. **No ancestry or reachability claim is written anywhere in this lap.** Counted
from the report files **added** in the range (`git diff --name-status`, status `A`): **twelve
finished dev laps**, six critic laps and three paper laps (filed `--kind manual`).

**Critic #68's `fix-before-next-row` item is CLOSED.** The clause 「부스에서 말해도 되는지를
저희가 아직 정하지 않아서」 is gone from both spoken sentences, and **NH-059** is gone from
both README lines. Re-measured here rather than read from a report: `grep -n` finds the
withheld-for-permission clause in **zero** spoken spans, and `NH-059` appears in
`docs/auto/JUDGE_QA.md` exactly **once**, inside the labelled student note where it belongs.
Two new gates hold it there. The reprint happened: `WFG_printables_20260911T1904Z.pdf`,
**59** pages, its seven `sources` hash **7 of 7** against the tree, and
`release/kcf-finals-2026/MANIFEST.json` hashes **19 of 19** and names that kit. All four
hash checks recomputed in this lap's own process.

**WFG-260 is `done` and its measurement is sound.** Re-derived here from
`data/processed/routing_demo_canonical.npz` before reading the lap's figures: `haz_times[0]`
is **0.0**; `haz_stack[0]` holds exactly `{0.0, 1.0}` while `haz_stack[1]` holds **3,961**
distinct values; `haz_stack[0] >= 0.5` and `obs_stack[0] > 0` are both **249** cells with
**XOR 0**; those cells fall into **226** 8-connected components (**236** at 4-connectivity),
the largest **3** cells. Every figure the lap published agrees with mine.

**And the repair carried a defect of its own onto the card it repaired.** That is this
lap's one item, and it is below.

---

## `fix-before-next-row`: ONE. The card now contradicts its own student note, and the two together decide NH-059

⚠⚠ **The card says, in its own student note, that it does not raise the count first. Eight
lines later the card raises it first.** Measured at `8952a5b` in this lap's own process:

| line | what it says now | why it is the finding |
|---|---|---|
| `docs/auto/JUDGE_QA.md:1013` | 「그 실행에서 나온 수치는 그 문서 **4절**에 적혀 있고, **이 카드에서는 먼저 꺼내지 않습니다**」 | a statement about the card, and it is no longer true of the card |
| `docs/auto/JUDGE_QA.md:1018` | the prescribed booth sentence, to all five judges: 「거기서 나온 수치는 그 문서 **4절**에 그대로 적혀 있습니다」 | the student volunteers the section, unprompted. That IS raising it first |
| `docs/auto/JUDGE_QA.md:955` | Q19's **draft answer**, the sentence spoken from memory, the same clause | said from memory, on page 25 of the kit |
| `docs/auto/JUDGE_QA.md:1019`, `:957` | 「숫자만 떼어 말씀드리기보다 **그 문서로 보여드리는 편이 정확합니다**」 | the offer the same lap's reviewer removed, returned in the indicative |
| `docs/auto/JUDGE_QA.md:1028`, `:1036` | the note instructs 「유보의 이유를 입으로 설명할 일이 아니라 **문서를 열어 보여 드리면 되는 일**」 | the card instructs the student to do what the spoken line was edited to stop doing |
| `tests/test_judge_qa_bank.py:1118`, `:1133-1134` | the new gate's own docstring prescribes 「... offer to open it」 | a rider, not the item: the gate teaches the next lap the behaviour this lap removed |

**Why this is a defect and not a nit.** The 1852Z lap's independent reviewer blocked on
exactly this and was right: `docs/present_perimeter_yeongdeok.md` §4 prints all three counts
in bold, so steering a judge into that section is **NH-059 option A reached through a side
door**, by the judge's request rather than the student's sentence, but reached. The lap
removed 「원하시면 지금 열어서 보여드리겠습니다」 from both spoken sentences and left three
other forms of the same act standing: the section pointer, the 「그 문서로 보여드리는 편이
정확합니다」 clause, and the note that tells the student opening the page is the right move.
The card and its note now say opposite things about the card, in one block, eight lines
apart. **That is CHARTER §5c's failure mode reproduced inside a single file for the second
consecutive lap, by the lap clearing a finding about it.** Critic #68's item listed five
lines; the reviewer found a sixth at `:1013`; the note AT `:1013` that the substitution
falsified was missed by both.

⚠ **Critic #68's prescription is the proximate cause and this lap says so.** 「Say where the
number is written」 is what put the section pointer in the student's mouth. The reason clause
had to go and that half was right. The pointer should not have replaced it.

**The fix, and it is minutes: answer the question, name the file, name nothing inside it.**
Nothing below needs NH-059 answered and nothing below closes it.

1. `docs/auto/JUDGE_QA.md:955-957` and `:1018-1019`, the same substitution in both. Drop
   「그 수치는 그 문서 **4절**에 그대로 적혀 있습니다」 and the 「숫자만 떼어 말씀드리기보다
   그 문서로 보여드리는 편이 정확합니다」 clause, and put:
   「영덕 쪽은 2026-09-11 에 돌렸고, 방법과 한계까지 `docs/present_perimeter_yeongdeok.md`
   에 그대로 공개되어 있습니다. 거기서 나오는 것은 여백 하나가 아니라 대상 지점 전체를 세
   갈래로 나눈 **분할**입니다.」
   (A draft like every answer in the bank. Keep the register, keep the length, **speak no
   count and name no section**. ⚠ Do not write 「44곳」: `test_no_ppy_count_reaches_a_spoken_draft`
   keys on `(?<![0-9])(?:26|16|44)\s*(?:곳|개)` at `tests/test_judge_qa_bank.py:990` and
   critic #68's own prescribed wording would have reddened it. 「대상 지점 전체」 is the
   spelling that works and the one already in the file.)
2. `docs/auto/JUDGE_QA.md:1028` and `:1036`: the note stops instructing 「문서를 열어 보여
   드리면 되는 일」. What it should say instead is the true rule and it is one sentence: the
   student answers the question and names the file, does not point at a section and does not
   say a count; if a judge asks to open it, it is opened, because refusing to open a
   committed public document in front of a judge is the concealment critic #68 was about.
   Whether the student may **offer** the counts is **NH-059** and stays the author's.
3. `docs/auto/JUDGE_QA.md:1013` then becomes true again as written, and is not edited.
4. Rider, same edit: `tests/test_judge_qa_bank.py:1118` and `:1133-1134` stop prescribing
   「offer to open it」 in the docstring of the gate that exists to stop it.
5. Then `make printables` at a new stamp and `release/kcf-finals-2026/MANIFEST.json`
   re-pointed (**NH-049**). `git add` the new PDF **before** the bundle rebuild (MEMO
   2026-09-10).

**Grade by mutation:** put 「그 문서 **4절**에 그대로 적혀 있습니다」 back into Q19's
prescribed sentence and a new assertion in `tests/test_judge_qa_bank.py` should go red naming
Q19. Key it on a spoken span that names a **section of** `present_perimeter_yeongdeok.md`,
not on the bare string 「4절」, which appears legitimately elsewhere in the bank.
`test_no_ppy_count_reaches_a_spoken_draft` and
`test_no_spoken_sentence_withholds_a_number_for_want_of_permission` must both stay green
throughout; the replacement speaks no count and gives no permission reason.

⚠ **Out of scope, deliberately, and recorded for the author instead:** `README.md:334-336`
names §4 the same way. A written pointer a reader follows at their own pace is a different
act from a student volunteering it aloud to five judges, the TL;DR already links the page,
and NH-054's narrowing licensed that clause one lap ago. It is written into NH-059 as part
of the 「option B is thinning」 reading, not fixed here. ⚠ **Put NO count on any surface in
this item**: not 26, not 16, not 2, not 44, not 226. ⚠ Do **not** touch `README.md`'s opening
paragraph about the 2025 fire (CHARTER §3.5b). ⚠ Do **not** weaken the fire-blind-control or
oracle-in-the-grading caveats, and do **not** touch the WC-019 correction block's substance.

---

## The root objection (`hate`)

**The page the README now sends a judge to contains, in prose, the sentence that ends this
project's headline, and it is the only sentence on that page nobody can re-derive.**

`docs/present_perimeter_yeongdeok.md:165` says, as fact, 「at 500 m, 15 of the 16 flip」. Read
with §4, that says a router which sees only where the fire is now, plus half a kilometre of
margin, reaches all but one of the origins the headline **42** credits to the forecast. The
whole booth narrative is 42. The sentence that reduces it is on the same page, two screens
below the result, one click from the front door, and `docs/NUMBERS.json` holds **seven**
`ppy_yeongdeok_` keys and not one of them is the 15 or either width. It came from a
reviewer's in-session probe that has ended. CHARTER §3.3: 「A number you cannot register, you
do not write.」

And this lap's own verification makes it sharper, because the two halves have never been put
in one sentence. WFG-260 established that the opponent's input is the **observation**, and
measured that the observation is **226** disconnected components with a largest piece of
**3** cells: a VIIRS detection scatter at 375 m rasterised onto a 500 m grid, not a fire
line. A sparser burning set removes fewer nodes, reroutes fewer walks, and saves fewer
origins. §5 item 5's own probe says which way that runs: dilating the set moves origins
**into** `saved`. **So the fair opponent is systematically weakened by the coarseness of this
project's own input, and the direction of that bias runs in this project's favour.** Neither
the page nor any other file says that sentence, and both halves of it are now in the same
document.

**The cheapest test, and it is one lap, not a row you can skip:** extend
`scripts/measure_present_perimeter_yeongdeok.py` with the two widths **already named in the
prose** (100 m and 500 m, so no width is chosen after the answer), write a
`buffer_sensitivity` block beside `outcomes`, register the keys additively, and re-point §5
item 5. Then read the number. If it holds, this project knows the honest size of its own
contribution before a judge computes it. If it does not, a false sentence comes off a page a
judge reaches in one click. **Either outcome is a good lap. Leaving it is not.** That is
**WFG-259**, `todo`, already the first `todo` row in table order.

---

## Findings, ranked

1. **The card contradicts its own student note and steers a judge into §4, above.** The one
   `fix-before-next-row` item. Six judge-facing lines plus one gate docstring, all named.
2. **WFG-259, re-confirmed open and now carrying a second half.** Re-measured here at
   `8952a5b`: `docs/NUMBERS.json` holds **seven** `ppy_yeongdeok_` keys
   (`target_origins`, `saved_by_present_perimeter`, `still_enter_forecast`,
   `not_reached_under_filter`, `filter_nodes_removed`, `filter_shelters_removed`, and
   WFG-260's new `slice0_components_8conn`) and **none** is the 15 or either width;
   `data/processed/present_perimeter_yeongdeok_2025.json` has no `buffer` or `dilat` key at
   any depth; `scripts/measure_present_perimeter_yeongdeok.py` still takes no buffer
   argument. **New this lap:** the row now also owns the bias-direction sentence the root
   objection names. The row is updated, not duplicated.
3. **The judge drill produced exactly one gap, and it is the same one.** Ten hard questions
   run against the tree. Nine have an answer that points at a file: the dispatch order has
   never been produced from a real fire and the surfaces say so (NH-057); how wrong the
   forecast can be is `docs/oracle_gap.md` with a §7 that states what it does not show; the
   reproduction is §3's gate table, which re-derives 458 / 414 / 42 / 2 before the script
   writes; six events (Q5); 「is the 26 a margin」 is §5 item 2; 「what did you build」 is
   Q29a; 「offline demo, so what is real-time」 is Q25. **The one with no licensed answer is
   「your present perimeter is 226 disconnected dots, largest 3 cells. Does that make your
   fair opponent artificially weak, and in whose favour?」** §2 states the object, §5 item 5
   forbids asserting a direction, and the numbers that would license one are unregistered.
   ⚠ It is filed as a backlog row and **not** as a JUDGE_QA card: **NH-049** is the entry
   that says a critic lap cannot add a card without a reprint it is not allowed to run, and
   it is now **past due**.
4. **WFG-261 (P1, NEW).** The two gates this window added read `docs/auto/JUDGE_QA.md` and
   nothing else. `docs/auto/DEMO_SCRIPT_5MIN.md`, `web/finals.html` and
   `docs/auto/finals/*.md` are spoken or shown surfaces with no gate for either class
   (a number withheld for want of permission; an `NH-###` in front of a judge). The 1852Z
   lap recorded this and correctly did not widen its row. It is P1 because it is protective
   rather than corrective, and it earns promotion the moment the P0 block clears.
5. **Zero KCF_READINESS lines ticked, for the twenty-sixth consecutive critic lap.** Verified
   by diffing the R-row status cells across the window: not one of the twelve changed. 8 of
   11. ⚠ **What is new is the arithmetic of the hold, and it is worth one sentence to the
   author:** CHARTER §14b releases the P1 hygiene block when **R1, R3, R4, R7, R8 and R9**
   tick. **Five of those six are ticked. R3 is the only one that is not**, R3 is
   `blocked(NH-046)`, NH-046 is a three-option question that came due 2026-09-10, and the
   sprint ends 2026-09-15. One unanswered email is holding both the ninth readiness tick and
   the whole P1 block. Reported, not re-filed: NH-046 is already open.
6. **The decision channel has now produced nothing for nine days.**
   `docs/auto/decisions_seen.json` records `"seen": []` and the newest applied decision is
   still NH-031 of **2026-09-06**. Confirmed at the Gmail connector in this lap: the **30**
   newest threads matching `from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop"
   newer_than:14d` each carry exactly one message and every one is the loop's own send;
   PR #31's comment list is empty. That is **WFG-211**, already `todo`. **26 decisions open,
   2 undated. NH-046, NH-049 and NH-051 are past due.**

**No finding #1 under CHARTER §4b, for the eighteenth consecutive lap.** Read through the
GitHub MCP (CHARTER §4 forbids `curl` against `api.github.com` here, WFG-119): runs **363 to
382** on `auto/dev`, **no run in the window concluded `failure`**; two `cancelled` (368 and
381, each superseded by the next push); run **382 is `success` at `8952a5b`**, this exact
head. **Every report in the window records `Reviewed by:`** (twenty-one checked, dev, critic
and paper alike). `gates.py --assert-reported` exits **0** at every push boundary since
critic #68 (`ca164c3`, `5949fe6`, `5d63b39`, `ae0323d`, `679c187`), so every push in the
window carried a report or touched only report machinery.

---

## What this lap verified rather than assumed

- `gates.py --mode full` exits **0** on its FIRST run in this sandbox at `8952a5b`:
  **2158 passed**, 65 skipped, 3 xfailed, pytest 413.6 s. `baseline-verify` is the known
  WARN (NH-029 / CHARTER §3d; the two MISSING contracts are under git-ignored
  `data/raw/firms_data/`, which never reaches a fresh clone).
- The slice-0 identity and the component count, recomputed from the committed npz in this
  lap's own process and compared with the lap's figures only afterwards: 249 / 249 / XOR 0,
  226 at 8-connectivity, 236 at 4-connectivity, largest 3, slice 1 at 3,961 distinct values.
  **Every figure agrees.**
- `grid_extent` in that npz ends **500.0**, so the page's 「500 m hazard grid」 is the array's
  own cell size and not a remembered constant. `factchk` on the one new claim about the
  world in this window: VIIRS active-fire detections carry a **375 m** nominal footprint,
  which is the I-band product's published resolution and is correctly stated at
  `docs/present_perimeter_yeongdeok.md:55`. No other new prose claim in the window is about
  the world rather than about this repository's own artifacts.
- The kit hashes **7 of 7** and the bundle **19 of 19**, both recomputed here from the
  `source` paths; the kit is `WFG_printables_20260911T1904Z.pdf`, 59 pages, and the bundle
  names it.
- The withheld-for-permission clause is in **zero** spoken spans and `NH-059` appears in
  `docs/auto/JUDGE_QA.md` exactly once, inside the labelled student note. Critic #68's item
  really is closed; what replaced it is finding 1.

## `Do NOT edit` notes carried, re-checked, and their expiry

Per CHARTER §14c every such note names lines and a measurement and expires at the next critic
lap unless re-stated. Re-checked here:

- **Do not unshallow the clone.** RE-STATED. `git rev-parse --is-shallow-repository` answers
  `true` at **50** commits in this clone and `gates.py --mode full` exits 0 on its first run
  without deepening. The stated cost holds: `tests/test_timeline_roles.py:234` **SKIPS**
  rather than runs in a shallow clone, so a green critic gate does not certify it; GitHub at
  `fetch-depth: 0` does, and run **382** is green at this head. Recorded on **WFG-217**.
  Expires at critic #70 unless re-measured.
- **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or
  `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a
  re-pointed MANIFEST** (NH-049). RE-STATED, re-measured here at `8952a5b`: kit 7 of 7,
  bundle 19 of 19, bundle names the newest kit. Expires at critic #70 unless re-measured.
- **Do not edit `README.md`'s TL;DR lead while NH-054 is open.** RE-STATED with critic #67's
  narrowing unchanged: the bar covers the bullet's **ordering and proportion**, which is what
  NH-054's 433-against-1,853 character count measured, and not the truth or the length of a
  parenthetical inside it. Nothing in this lap's item touches that bullet.
- Every other ⚠ line in `docs/auto/DIRECTION.md` is carried unchanged and is not re-derived
  here; this lap re-measured only the three above.

## Scorecard

**No row moves on either track. Track B holds at 95, Track A at 97.** A dated row is
appended to the series with all ten cells unchanged and the evidence beside them, because the
routine keeps the series; no per-track table gains a row, because the per-track tables are
the record of movements and nothing moved.

**제출 자료 is the row that had a case, and the case cancels.** The gain is real: the front
door stopped printing an internal entry id and the spoken card stopped explaining a
withholding, on the two surfaces five judges actually meet, with the kit reprinted and the
bundle re-pointed in the same window. Against it, exactly and measurably: the card shipped in
that kit now contradicts its own student note eight lines apart (finding 1, page 25 of
`WFG_printables_20260911T1904Z.pdf`), and `README.md:50`, `:265` and `:351` still print
**NH-053** in the identical defect class critic #68 named and put out of scope. **Gain and
deduction cancel at 19.** 20 needs both: the card consistent with itself, and the front door
free of entry ids.

**데이터 수집·분석·해석 holds at 19 and I am pre-registering what moves it**, so critic #70
can hold me to it: **WFG-259 closing by route (i)** — the dilation run as a committed
artifact with registered keys and §5 item 5 re-pointed — takes it to **20**, because the last
unre-derivable integer on the project's most exposed page becomes re-derivable and the row's
criterion is literally 「연구 재현 가능성」. WFG-260 was a real gain on this row and it is why
19 was already earned last lap; it does not buy the same point twice.

**설계와 방법론 20, 연구 목적 18, 창의성 19 hold**: no model, split, arm, coupling, region or
protocol changed in this window. Track A the same, for the same reasons; 구현 및 유용성 holds
at 20 with the screen still opening and the bundle verified 19 of 19 here.

## Next row for the dev lap

After the item above: **WFG-259**, alone and in full. It is the first `todo` row in table
order, it is the root objection, and critic #68 asked for it a lap ago and did not get it.
Then **WFG-256** (the rotation null, still the only thing that would license a sentence about
「모양」), then **WFG-255**.
