# Critic #68 — 2026-09-11T1724Z, reviewed `b6778e7`

**The next dev lap reads this file first.** Window `196ea42..b6778e7`. `196ea42` is this
shallow clone's oldest resolvable commit (2026-09-10T22:15:06Z, 18 h 22 m back), so it is the
base rather than a chosen one; the clone is SHALLOW at **50** commits, measured here with
`git rev-parse --is-shallow-repository` and `git rev-list --count HEAD`, and was deliberately
NOT deepened. **No ancestry or reachability claim is written anywhere in this lap.** Counted
from the report files **added** in the range (`git diff --name-status`, status `A`): **ten
finished dev laps**, six critic laps and three paper laps (filed `--kind manual`).

**Critic #67's `fix-before-next-row` item is CLOSED, in full, including the part that
normally slips.** WFG-258 (a), (b) and (c) are all done. Re-measured in this lap's own
process rather than read from a report: the four judge-facing lines now say the fair
opponent **has** been run on 영덕 and name the file; `release/kcf-finals-2026/MANIFEST.json`
hashes **19 of 19** against its sources and names `WFG_printables_20260911T1627Z.pdf`, whose
seven `SOURCES` documents hash **7 of 7** against the tree, 59 pages, 25 of them the Q&A
bank. That is the condition critic #68 was pre-registered on, and it fires: **제출 자료
returns 18 to 19 on both tracks.**

**And the same edit shipped the loop's own governance onto the surfaces a judge meets.**
That is this lap's one item, and it is below.

---

## `fix-before-next-row`: ONE, and it is one clause on five lines plus the reprint

⚠⚠ **The sentence the student is told to say to all five judges, beside the headline 42,
now tells them the project measured something and has not decided whether it is allowed to
say it.** Measured at `b6778e7` in this lap's own process:

| line | what it says now | why it is the finding |
|---|---|---|
| `docs/auto/JUDGE_QA.md:1017` | inside 「**그러니 42 를 말할 때 붙일 문장**」: 「...거기서 나온 수치를 부스에서 말해도 되는지는 저희가 아직 정하지 않아서 오늘은 말씀드리지 않겠습니다」 | **prescribed**, beside the headline number, to every judge |
| `docs/auto/JUDGE_QA.md:956` | Q19's **draft answer**, the sentence the student speaks from memory, same clause | said from memory, on page 25 of the kit |
| `README.md:37` | 「neither count is licensed for the booth (**NH-059**)」 | the English TL;DR prints an internal entry id |
| `README.md:335-336` | 「수치는 아직 부스에서 말하지 않습니다, 말해도 되는지는 저자에게 **NH-059** 로 열려 있습니다」 | the Korean front door prints the same id and calls its own author a third party |
| `docs/auto/JUDGE_QA.md:1022` | tells the student 「말하지 않는 진짜 이유는 **NH-059**」 | a student note, correct as a note, but it never says it is not for the judge |

**Why this is a defect and not a caveat.** Every other withheld thing in this repository is
withheld because the measurement does not exist or does not support the sentence, and the
surface says exactly that. This one exists, is committed, is registered, and is reachable:
`README.md`'s TL;DR now links `docs/present_perimeter_yeongdeok.md`, whose §4 prints the
26 and the 16 in bold. So the surface is not protecting a judge from an unlicensed number;
it is announcing that a number is being withheld, and giving as the reason an internal
ticket. A judge hears concealment. This project's whole credibility rests on the opposite
move, and its own charter says it: **「When a result is weak, say so in the artifact」**
(CHARTER §3.5).

**The fix, and it is minutes: replace the reason, speak no count.** Nothing below needs
NH-059 answered, and nothing below closes it.

1. `docs/auto/JUDGE_QA.md:956` and `:1017`, the same substitution in both. Drop the clause
   「부스에서 말해도 되는지를 저희가 아직 정하지 않아서 ... 말씀드리지 않겠습니다」 and put:
   「그 수치는 `docs/present_perimeter_yeongdeok.md` **4절**에 그대로 적혀 있습니다. 원하시면
   지금 열어서 보여드리겠습니다. 다만 그건 여백이 아니라 44곳을 세 갈래로 나눈 **분할**이라,
   숫자만 떼어 말씀드리기보다 그 문서로 보여드리는 편이 정확합니다.」
   (Wording is a draft like every answer in the bank; keep the register, keep the length,
   and **speak no count**.)
2. `README.md:37`: 「neither count is licensed for the booth (**NH-059**)」 becomes 「neither
   count is restated here; both pages carry their own」. No id on the front door.
3. `README.md:335-336`: the clause becomes 「거기서 나온 수치는 그 문서 **4절**에 그대로 적혀
   있고, 이 README 에는 옮겨 적지 않습니다. 여백이 아니라 44곳을 세 갈래로 나눈 분할이고,
   그렇게 읽어야 하는 이유는 같은 문서 **5절**의 여덟 항목입니다.」
4. `docs/auto/JUDGE_QA.md:1022` keeps its reasoning, which is correct, and gains one clause:
   this is why the student does not say the number, and **the reason itself is not said to a
   judge**.
5. Then `make printables` at a new stamp and `release/kcf-finals-2026/MANIFEST.json`
   re-pointed (**NH-049**).

**Grade by mutation:** put 「말해도 되는지를 저희가 아직 정하지 않아서」 back into Q19 and a
new assertion in `tests/test_judge_qa_bank.py` should go red naming Q19. The existing
`test_no_ppy_count_reaches_a_spoken_draft` must stay green throughout; the replacement
speaks no count.

⚠ **NH-054 does not hold item 2**, on critic #67's narrowing re-stated below: NH-054 is open
on the TL;DR bullet's **ordering and proportion** (433 result characters against 1,853 of
qualification), and this shortens one parenthetical by a few characters, deletes no caveat,
reorders nothing. ⚠ **Do not touch `README.md`'s opening paragraph about the 2025 fire**
(CHARTER §3.5b). ⚠ **Do not weaken** the fire-blind-control or oracle-in-the-grading caveats.
⚠ **Put NO count on any surface in this item**: not 26, not 16, not 2, not 44. NH-059 stays
open and every one of its four options stays reachable after this edit.

⚠ Out of scope for this item, recorded for the author instead: `README.md:50`, `:265` and
`:351` print **NH-053** the same way, and they predate this window.

---

## The root objection (`hate`)

**The loop has started shipping its own governance onto the judged surfaces.** The
machinery that makes this project trustworthy, the NEEDS_HUMAN ledger, 「the repository has
not decided」, 「not licensed for the booth」, was built to stop the loop from overclaiming
to its author. It is internal by construction: it names entries by id, it addresses the
student in the third person as 「저자」, and it treats a booth sentence as something pending
authorisation. In this window it crossed onto the README and into a sentence prescribed for
five judges. The lap that did it reasoned carefully about **which word** to use inside that
sentence (`docs/auto/JUDGE_QA.md:1018-1022` argues 「정하지 않았다」 over 「확정 전」 and is
right on its own terms) and never asked whether a judge should hear the sentence at all.
That is the same shape as critic #67's objection one level up: the loop checks its wording
faster than it checks who the wording is for.

**The cheapest test, and it is not a row:** read `README.md:33-37` and
`docs/auto/JUDGE_QA.md:1013-1017` to one person who has not read the charter, and ask them
in one sentence what the project is not telling them and why. If the answer is 「a number
that makes them look bad」, the sentence has failed, whatever it literally says.

---

## Findings, ranked

1. **The withheld-reason clause, five lines, above.** The one `fix-before-next-row` item.
2. **WFG-260 (P0, NEW, filed at table position 1).** `paper/manuscript.md`'s Abstract and
   §4.5 claim the fair opponent 「needs no model at all」, and
   `docs/present_perimeter_yeongdeok.md` §5 item 6 words its own input so that a reviewer
   would conclude the opposite: the arm is 「filtered from `haz_stack` slice 0 ... which is
   the same leave-one-fire-out forward simulation the forecast-aware arm plans on」. **The
   claim is true and this lap proved it from the committed array**: `haz_times[0]` is 0.0;
   `haz_stack[0]` is strictly binary `{0.0, 1.0}` while `haz_stack[1]` holds 3,961 distinct
   values; `haz_stack[0] >= 0.5` and `obs_stack[0] > 0` are both **249** cells and the two
   sets are **identical cell for cell**; `scripts/build_canonical_hazard.py:88` seeds the
   simulation from `snaps[0].cumulative_mask`; and at `t_min = 0.0`
   `src/wildfireguardian/routing/hazard.py:97-100` collapses the bracket to `i0 == i1 == 0`,
   so no slice is mixed in. So slice 0 is the **observation**, the planning side is
   model-free, and the strongest new claim in the paper is sound and unstated. ⚠ The same
   measurement says the object called a 「present perimeter」 is **226 connected components,
   largest 3 cells** at 8-connectivity, which is a detection scatter and not a perimeter;
   that is the honest version and it is nowhere. **Ride it with WFG-259 in one lap.**
3. **WFG-259 (P0, position 2), re-confirmed open and unchanged.** `docs/NUMBERS.json` holds
   exactly six `ppy_yeongdeok_` keys and none is the 15 or either buffer width; the artifact
   has no `buffer` or `dilat` key at any depth; the script takes no buffer argument. So
   `docs/present_perimeter_yeongdeok.md:134`'s 「at 500 m, 15 of the 16 flip」 is still the
   one number on that page nobody can re-derive from this tree, **and the page is now linked
   from `README.md`'s TL;DR**, so a judge reaches it in one click. CHARTER §3.3.
4. **Zero KCF_READINESS lines ticked, for the twenty-fifth consecutive critic lap.**
   Verified by diffing the R-row status cells across the window: not one changed. 8 of 11.
   Reported and not re-filed, because critic #52's measurement of the cause still holds and
   no lap can change it: R12 is the author's (NH-014), R3 is `blocked(NH-046)`, R11's
   WFG-024 is held by §14b until R3 ticks. **There is no path from any amount of loop work
   to a ninth tick, and the sprint ends in four days.**
5. **The decision channel has now produced nothing for seven days.**
   `docs/auto/decisions_seen.json` records `"seen": []` and the newest applied decision is
   NH-031 of **2026-09-06**. Confirmed at the Gmail connector in this lap: the **30** newest
   threads matching `from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop"
   newer_than:14d` each carry exactly one message and every one is the loop's own send;
   PR #31's comment list is empty. That is **WFG-211**, already `todo`. **26 decisions open,
   2 undated.**
6. **WFG-257 gains one clause rather than a new row.** `tests/test_demo_script_pace.py` pins
   the **spread** (`implied_rate_spread <= 1.10`, `:120`) and refuses the comfort claim
   (`:143`), and **nothing pins the absolute rate**. The script could reach 7.0 syllables per
   second with every gate green; that is the mechanism behind this row's own 5.61 to 6.00
   drift. The ceiling belongs in the row's done-when.

**No finding #1 under CHARTER §4b, for the seventeenth consecutive lap.** Read through the
GitHub MCP (CHARTER §4 forbids `curl` against `api.github.com` here, WFG-119): runs **359 to
378** on `auto/dev`, **no run in the window concluded `failure`**; one `cancelled` (368,
superseded by the next push); run **378 is `success` at `b6778e7`**, this exact head. Every
dev report in the window records `Reviewed by:` (**fourteen** checked, all `subagent`, nine
of them `block` and five `pass`), and every push in the window carried a report file with
it: the only commits in the range with no report beside them are bare backlog claims and
work commits pushed together with the report commit that closed their lap, which is what
`--assert-reported` allows.

---

## What this lap verified rather than assumed

- `gates.py --mode full` exits **0** on its FIRST run in this sandbox at `b6778e7`:
  **2149 passed**, 65 skipped, 3 xfailed, pytest 501.4 s. `baseline-verify` is the known
  WARN (NH-029 / CHARTER §3d; the two MISSING contracts are under git-ignored
  `data/raw/firms_data/`, which never reaches a fresh clone).
- The kit hashes **7 of 7** and the bundle **19 of 19**, both recomputed here from the
  `source` paths, and the bundle names `WFG_printables_20260911T1627Z.pdf`, 59 pages.
- `docs/auto/DEMO_SCRIPT_5MIN.md` and `docs/demo_script_pace.md` have **not** changed since
  `dec00f4`, so critic #67's pre-registered DOWNWARD condition on Track A 구현 및 유용성
  (「the script grows again without the trade recorded」) does **not** fire.
- WFG-258 half (c) was checked in the file, not in the report:
  `tests/test_future_aware_attribution.py:16-18` now reads 「has been run on 의성·안동 ...
  and, since 2026-09-11, on 영덕 too」 with the WC-019 record note beneath it at `:20`.

## `Do NOT edit` notes carried, re-checked, and their expiry

Per CHARTER §14c every such note names lines and a measurement and expires at the next
critic lap unless re-stated. Re-checked here:

- **Do not unshallow the clone.** RE-STATED. `git rev-parse --is-shallow-repository` answers
  `true` at **50** commits in this clone and `gates.py --mode full` exits 0 on its first run
  without deepening. The stated cost holds: `tests/test_timeline_roles.py:234` **SKIPS**
  rather than runs in a shallow clone, so a green critic gate does not certify it; GitHub at
  `fetch-depth: 0` does, and run 378 is green at this head. Recorded on **WFG-217**.
  Expires at critic #69 unless re-measured.
- **Do not edit `README.md`'s TL;DR lead while NH-054 is open.** RE-STATED with critic #67's
  narrowing unchanged: the bar covers the bullet's **ordering and proportion**, which is what
  NH-054 measured, and not the truth or the length of a parenthetical inside it. Item 2 of
  the `fix-before-next-row` above is licensed by that narrowing and nothing else in the
  bullet is.
- **Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or
  `docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a
  re-pointed MANIFEST** (NH-049). RE-STATED, re-measured here at `b6778e7`: kit 7 of 7,
  bundle 19 of 19, bundle names the newest kit.
- Every other ⚠ line in `docs/auto/DIRECTION.md` is carried unchanged and is not re-derived
  here; this lap re-measured only the three above.

## Scorecard

**Track B 94 to 95, Track A 96 to 97.** One row moves on each and it is the same row:
**제출 자료 18 to 19**, on critic #68's own pre-registration, because WFG-258 (a) closed
**with the kit reprinted and the bundle re-pointed** and this lap re-hashed both rather than
reading a report. **19 and not 20** because of finding 1. Every other row HELD, evidence in
`docs/auto/SCORECARD.md` at this date.

## Next row for the dev lap

After the item above: **WFG-260 and WFG-259 together, in one lap** (same page, same script,
same registration pass). Then **WFG-256** (the rotation null, still `todo` and still the only
thing that would license a sentence about 「모양」), then **WFG-255**.
