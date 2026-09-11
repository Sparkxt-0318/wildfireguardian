# Critic #64 — 2026-09-11T0520Z, reviewed `5482ba8`

**The next dev lap reads this file first.** Window `0796336..5482ba8`: one dev lap that closed
WFG-247 and WFG-248 and was BLOCKED once by its own reviewer, one paper lap trimming under
NH-037, two board rebuilds after rebases and one report-header fix. No data, no figure, no
model. `docs/NUMBERS.json` gained four keys additively.

---

## `fix-before-next-row`: ZERO, and this lap measured the reason instead of repeating it

No gate is red on the pushed head. **GitHub `auto-gates` run 361 is `success` at exactly
`5482ba8`**, at `fetch-depth: 0`; no run in the window has conclusion `failure`. All three
judge-facing findings below sit on hashed kit sources, so CHARTER §14b plus NH-049 make each
of them a P0 row at position 1 and none of them a preemption. **Take the top row directly.**

⭕ **THE PREMISE UNDER THAT RULING NOW HAS A NUMBER. A full booth-kit rebuild is 17 seconds.**
Measured in this lap without touching the tree: `build_printables.py --stamp <new>
--out-dir <scratch>` produced the whole 58-page kit and its manifest in 17 s, `git status
--short` stayed empty. The chain a critic would need is: edit `docs/auto/JUDGE_QA.md` (under
`docs/auto/`, permitted), `make printables` (writes under `docs/auto/finals/printables/`,
permitted, 17 s), then re-point **`release/kcf-finals-2026/MANIFEST.json`**, which is the one
file outside `docs/auto/` and is three JSON fields. The two gates that enforce it are
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` and
`tests/test_finals_bundle.py::test_the_bundle_carries_the_newest_booth_kit_and_not_an_older_stamp`.
**This is not a lap reversing its predecessors' ruling on its own authority** — #62 and #63
both ruled the rebuild is not minutes and this lap keeps ZERO preemptions to stay consistent
with them. It is the measurement NH-049 has been open for, appended there.

⚠ **DO NOT `git fetch --unshallow`, AND CHARTER §4 DOES NOT ASK YOU TO.** §4 forbids writing
an ancestry or reachability claim from a shallow clone; it nowhere requires deepening.
Critic #63 recorded 「CHARTER §4 mandates `--unshallow`」 and then recorded a cure for the
damage deepening does (delete eleven remote-tracking refs, expire the reflog, `gc
--prune=now`, 16,420 objects down to 13,011). **Critic #64 did not deepen and `gates.py
--mode full` went green on its FIRST run:** 2092 passed, 65 skipped, 3 xfailed, 531 s.
⚠ And the honest cost of not deepening, which is why this is a note and not a victory: in a
shallow clone `tests/test_timeline_roles.py:234` **SKIPS**, printing 「shallow clone: the
2026-05-27 first commit is not present」, and `build_timeline_roles.py --check` declines
rather than passing. So a green critic gate does not certify that check; GitHub at
`fetch-depth: 0` does, and run 361 is green. Recorded on **WFG-217**, which is the row.

---

## Finding 1 — WFG-249 (P0, KCF, filed at position 1)

**A T0 card the student answers from memory tells a judge that a 가구 in this repository is
not a building. The closing sentence the same window wrote tells the same judge that the 가구
it counts are OSM buildings. Both are on paper in the box.**

`docs/auto/JUDGE_QA.md` Q20a, the privacy card, unqualified:

> 「이 저장소에서 「가구」는 사람도 주소도 건물도 아니라 **OSM 보행 도로망의 노드 하나**입니다.」

`docs/auto/DEMO_SCRIPT_5MIN.md`, the spoken 마무리, added by WFG-247 in this window:

> 「여기서 세는 **가구**는 판정 단위인 **지점**이 아니라 **OSM 건물**입니다」 (with the count).

Q20a says 건물도 아니라. The closing says 건물입니다. ⚠⚠ **And the fix cites the card it
breaks:** 금지 item 6, rewritten in the same commit, now reads 「`docs/auto/JUDGE_QA.md`
Q20a 가 「가구」를 보행망 노드 하나로 정의하고」, so the surface that contradicts the definition
points the student at the card that states it.

⭕ **WFG-247's sentence is NOT the error and must not be reverted.** The refuge arm genuinely
counts buildings; `docs/NUMBERS.json :: l0i_household_population` says so in its own `caveat`,
and this lap re-read `data/processed/vulnerability/refuge_placement.json ::
optimum_h240.baseline` in its own process to confirm it. What is false is Q20a's **scope**,
written before the refuge arm had a population sentence anywhere in the kit.

**Both documents are in the printed kit and the kit is in the bundle**, re-measured here
rather than read: `manifest_20260911T0412Z.json` hashes **7 of 7** sources against the tree,
`release/kcf-finals-2026/MANIFEST.json` **19 of 19**, and it names that newest kit. The kit is
58 pages, of which `JUDGE_QA.md` is 25 and `DEMO_SCRIPT_5MIN.md` is 7.

**Why it is finding 1.** Q20a is on the first drill round (`docs/auto/JUDGE_QA.md` §6), so it
is spoken from memory; the 마무리 is the last thing each of the five judges hears. One visit
contains both. 「자료의 논리적 구성」 is the first named sub-item of a 20-point row on **both**
rubric tables.

⚠ **Scope the definition, do not soften the privacy answer** — that answer is correct about
the routing output and is the reason the card exists.

---

## Finding 2 — WFG-250 (P0, KCF, filed at position 1)

**The closing now names a population for its three counts and it is the arm's denominator, not
the claim's, so a judge doing the arithmetic in their head gets a number several times worse
than the truth.**

`data/processed/vulnerability/refuge_placement.json :: optimum_h240.baseline`, re-read in this
lap's own process, holds `n_households` and `n_failing` side by side. The refuge result is a
count of the households that **fail** the horizon and are recovered, so the claim's
denominator is `n_failing`, not `n_households`.

**The screen says this correctly and the script does not.** `scripts/finals.template.html:1981`
renders 「분 지평에서 도달에 실패하는 」 + `R.failing_before` + 「가구 가운데, 대피 지점 한 곳을
더 두면 」. The spoken 마무리 names only the building population. And the §3 화면/구두 table at
`docs/auto/DEMO_SCRIPT_5MIN.md` disagrees with itself: the pair row was labelled 「도달 실패
… 전부」 in this window while the single-refuge row was labelled with the building population
only.

⚠ **The defect cuts AGAINST this project, which is exactly why nothing caught it.** Under the
building denominator the result sounds like a small slice of the village; under the failing set
it is most of the households that could not get out. Both readings are available to a judge from
the sentence as spoken and the repository supports one.

⚠ **This is not WFG-247 re-opened.** That row asked that the population be named where the
number is said, and it is. This is which population.

---

## Finding 3 — WFG-251 (P0, KCF, filed at position 1)

**The card that sends a judge to another team's DOI asserts a negative about the whole
deposited record, and its own limits list, forty lines below, says the file inside that record
was never opened.**

Q16d's **draft answer**, the text the student speaks: 「기록에는 **성능 수치가 하나도
없습니다** — 확산 쪽도, 경로 쪽도 없습니다」. The same card's 없는 것 item 1: 「초록과 기록만
읽었고 본문 PDF 는 열지 못했습니다」, prescribing ⭕ 「**공개된 기록과 초록에는** 경로 성능
수치가 없습니다」. The deposited record contains that PDF: the Zenodo API, read in this lap,
returns exactly one attached file, `IEEE_Conference_Template.pdf`. So the spoken sentence
asserts over a document nobody here has read, and widens the prescribed claim from the routing
arm to both arms. Three paragraphs below it the card says 「이 DOI 를 그 자리에서 열어
보이십시오」.

⭕ **Everything else on Q16d survived independent re-verification at the API, not at the report
that wrote the card:** `conceptdoi` `10.5281/zenodo.22668357` resolving to record `22668358` as
a version relation; the title verbatim; `publication_date` **2026-09-09**; `resource_type`
**publication / preprint**; the five authors in the card's order; one attached file. And the
card's hardest claim is **exact**: a digit regex over the full abstract text returns the empty
list. **WFG-248's repair is also verbatim correct** against the abstract, which reads 「The
system orchestrates OpenRouteService vector routing … During API constraints or in wilderness
scenarios, the system delegates to an internal D\* Lite heuristic grid fallback」. **Do not
weaken any of those while fixing the one clause.**

---

## Finding 4 — WFG-252, and this lap repaired the gap it found

`docs/auto/SCORECARD.md`'s **combined series table**, the one whose shape the critic routine
prompt specifies by name, ended at critic #62's head `f93af93`. Critic #63 appended to the
Track B table and the Track A table at `0796336` and not to the combined one, so the series a
reader follows skips a lap while the record tables do not. **Transcribed here** as critic #63's
own values, labelled as a transcription and not a re-score, with this lap's row beneath it. The
gate is the row.

## Finding 5 — WFG-253, two rows closed on a commit id that does not exist

`WFG-247` and `WFG-248` both read `done(cd97bc2)`, and `docs/auto/STATE.json` names the same
id. Measured in a fresh clone at this head, with the depth recorded because CHARTER §4 requires
it (`--is-shallow-repository` answers `true`, `git rev-list --count HEAD` answers **54**):
`git cat-file -t cd97bc222878534c1927aee16ba182c13b786dca` fails with 「could not get object
info」 and `git log --oneline --all` matches nothing. ⚠ **This is an object-existence
measurement and NOT an ancestry claim** — the distinction CHARTER §4 draws and that five critic
laps once got wrong (`WC-004`). The cause is benign and the lap's own report states it:
`report.py` stamped the id before the push, the push rebased onto the paper routine's commit,
the work shipped as `c75cb08`. It is the **third recurrence in four days** of one defect class,
after `f93af93` and `71e95ee`, both of which are commits titled 「the row names a commit that
exists」. The repair belongs to a lap, not to this critic: rewriting another lap's closure note
is not this lap's to do.

---

## What the window got right, measured rather than read

- **WFG-247's repair did the hard thing.** It did not swap 가구 for 지점, which would have made
  a true sentence false; it registered the two missing populations from the artifact the
  numerators come from, and it refused to cite the coincidentally-equal count in a different
  file, naming that refusal as WFG-244's mistake.
- **The independent reviewer BLOCKED the lap and was right twice**, on the same failure class the
  lap was writing a correction about. Both corrections were about the lap's own arithmetic, and
  both were registered as withdrawals (`WC-015`, `WC-016`) in the same lap, which is CHARTER
  §3.5c paid on time rather than a window late.
- **`WC-015` is the first withdrawal in this registry of the project's own arithmetic about its
  own machinery**, and its blast radius was measured on flattened text before registering, which
  is the limit `docs/withdrawn_claims.md` §4 records.
- **The pace cost was paid, not absorbed.** The added sentence moved the 마무리, a new pace
  artifact was registered under a new tag, and the demo script says which segments paid and that
  the judgement is the judges' rather than the repository's.
- **Q16d's D\* Lite clause is now verbatim correct** against the abstract, re-checked at the API.
- **The kit and the bundle are on paper as claimed**: 7 of 7 and 19 of 19, recomputed here, and
  the bundle names the newest stamp.
- **All dev reports in the window record `Reviewed by:`**, and `--assert-reported` exits 0 both
  over the window (`--base 0796336`, 32 substantive paths) and over the full 24 h
  (`--base 3601c5e`, 66 paths).

---

## Root objection (`hate`) on the current headline narrative

**The loop has been measuring its own prose and calling it measurement, and the row that would
measure the world has been sitting `todo` at table position 3 the whole time.**

What this window produced: two withdrawn claims about this project's own syllable counting and
its own noun for a candidate count, one registered building population, two kit rebuilds, a new
structural gate, and about 2,600 lines of diff. All of it honest, some of it genuinely good
discipline. **None of it is a measurement of anything outside this repository.** The last
window that measured the world was WFG-228's disc null, and critic #63's own objection was that
the project's exhibits are synthetic; it then routed that objection to the author's decision
queue (NH-057) and named a prose repair as the next row. So did #62, #61, #60 and #59.

**The judge question that lands is not the one #63 named.** 「그 판정을 실제 불로 한 번이라도
내보셨습니까」 has an honest 「no」 with a documented reason and the panel says so in bold. The one
that lands is: 「이 42는 불을 전혀 보지 않는 지도와 비교한 값이라고 하셨는데, 지금 불난 자리만
피하는 지도와는 비교해 보셨습니까?」 Today the answer is 「on another region only; on this one we
specified the test and did not run it」, and the specification is in this repository, in
`paper/GAPS.md` G7, in the project's own words: 「That is minutes of work … **A dev lap should
run this before the finals whatever the author decides on NH-027.**」

**Cheapest test: run WFG-129.** Committed inputs only, no refit, no re-acquisition, no
credential, **no author decision** (its own cell records why NH-027 and NH-032 do not bar it).
Unlike every other standing objection this one does **not** land on the decision queue. It lands
on this page, which is mine, and `docs/auto/DIRECTION.md` now names WFG-129 as the row after the
kit bundle, with the skip list counted rather than asserted. **Pre-registered for critic #65: if
a dev lap ran in the next window and WFG-129 is still `todo`, that is finding #1.**

## Scorecard

**Both tracks HELD: Track B 96, Track A 97.** Critic #63 pre-registered 제출 자료 reaching **20
on both tracks** when WFG-247 and WFG-248 closed with the kit rebuilt and the manifest
re-pointed. **That condition is MET and I verified the object rather than the report** (kit 7 of
7, bundle 19 of 19, bundle names `WFG_printables_20260911T0412Z.pdf`, all recomputed here).
**The rise is declined**, and not by moving the goalposts: the same repair introduced **WFG-249**
on the same two printed documents, and **WFG-251** stands on one of them. A 20 on this row is a
claim that nothing was found on the submitted material, and three things were.
**No fall either**, which the same pre-registration allowed for: nothing drifted against a hash,
and the false noun that cost this row a point two laps ago is gone and registered.
**Pre-registered for critic #65:** 제출 자료 reaches 20 on both tracks when WFG-249, WFG-250 and
WFG-251 all close with the kit rebuilt and the manifest re-pointed; it falls to 18 on either
track if a kit source drifts against its manifest hash.

## Readiness

**8 of 11**, unchanged. ⚠⚠ **ZERO lines ticked for the TWENTY-FIRST consecutive critic lap.**
R3 is `blocked(NH-046)`, R11's WFG-024 is held by §14b until R3 ticks, R12 is the author's
(NH-014). Appended to **NH-038** and **NH-049** with measurements rather than restated as a
finding: the cause has been the same single point of failure for twelve laps and the author's
reply is the only thing that moves it.

⚠ **One channel fact, re-measured at the GitHub MCP rather than inherited, and NOT re-filed.**
PR #31 is `state: closed`, `merged: true` since 2026-09-05T14:25Z, merged by
`github-actions[bot]`, with **zero** comments ever, while CHARTER §6 and every report email
still name a PR comment as the author's second channel. That is **WFG-211**, already `todo`
with `agent-doable: yes`, and its own cell is right that where the author is told to reply is a
**question** and not a lap's choice. Gmail search over the report subject for the last fourteen
days returned only the loop's own sends, no reply in any thread, which matches
`decisions_seen.json` reading `"seen": []`.
