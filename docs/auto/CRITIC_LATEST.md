# CRITIC_LATEST — critic #14, 2026-09-04

Window `baf6962..ed35f0d` on `auto/dev` (7 commits; the 24 h window `ca366bf..ed35f0d` is 93).
Written by the `wfg-autoloop-critic` routine. The next dev lap clears every
`fix-before-next-row` item here before claiming a row.

## fix-before-next-row

**One item, WFG-087, and it is fifteen minutes of work on the Q&A bank.**

`docs/auto/JUDGE_QA.md:585-603` is **Q18, a T0 question** — one of the fifteen the student is
told to make fully their own — and it is the question a disaster-response judge is most likely
to ask: 「여기서 말하는 대피 지점이 무엇입니까? 그중 지정 대피소가 있습니까?」 Its 「없는 것」
paragraph says the comparison against the agency-designated list was not made because
「포털 다운로드가 로그인·CAPTCHA로 막혀 있고 NH-012에 학생 작업으로 올라가 있습니다」.

Both halves of that sentence are stale at HEAD, and the tree contradicts it in three places:

- `docs/juso_yeongdeok.md:1` — the 영덕 designated-site subset was **re-cut on 시군구 47770
  and verified from the data itself** on 2026-09-04 (NH-022 closed at `6f33eca`). The
  repository holds 지진해일긴급대피장소, 무더위쉼터 and six more layers for 영덕 today.
- `paper/manuscript.md:656-671` — 「Every refuge in this paper is an OpenStreetMap point, and
  **a designated list now exists that no result here uses**」, and it names the clip-to-walk-box
  comparison as **runnable now**.
- `docs/auto/NEEDS_HUMAN.md` — **NH-012 is closed**, deferred post-finals by the author, so it
  is not pending student work; and its WFG-075 amendment still reads 「the repository holds
  **no** agency-designated 대피장소 list for 영덕」, which the re-cut it was waiting on has
  since falsified.

So the drilled T0 answer understates what the project holds and explains the gap with a
blocker the project removed the same day. The 지정 *산불* 대피소 question is still genuinely
open (the designated categories in hand are earthquake, tsunami and heat), and that is the
honest sentence — it is not the sentence the bank teaches. `WFG-073` and `WFG-074`, both
`todo (unblocked 2026-09-04)`, are the rows that would close the rest.

This qualifies under CHARTER §14b as a judge-facing surface (the Q&A bank is named there), and
it is the only item this lap sets.

## Verified independently this lap

`gates.py --mode full` exits **0** at `ed35f0d` in a fresh cloud sandbox: `1453 passed,
62 skipped` in 208.9 s, **COLD** (first full run here, so the six SRTM-gated tests skip;
WFG-039). Against critic #13's cold `1377 / 62` at `baf6962` that is **+76 passed, skips
unchanged**, like for like, eighth comparable window and the largest single-window gain the
suite has recorded. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN,
expected off-laptop, `hard: false`, fourteenth window and still not a finding. Green at HEAD
for an **eleventh** consecutive critic lap. `--assert-head` exits 0.

**GitHub's own runs (CHARTER §4b), read through the MCP because the sandbox proxy answers
nothing to unauthenticated `api.github.com` calls.** Runs 92, 93, 95, 96, 97, 98 and **99 (this
head) are `success`**; run 94 was cancelled by a superseding push. The six red runs 86–91 sit
in the 24 h window but were diagnosed, fixed at `21b8740` and verified closed by critic #13.
**No red run behind a green report in this window, so there is no finding #1 of that kind and
the fix-before-next-row item goes to the product surface instead.**

**Report certification.** Every push in the window carried a report (45 new report files).
**Every dev report of the last 24 h carries a `Reviewed by:` line** — critic #13's F63 named
`0401Z-dev.md` as the exception and that file has now fallen out of the 24 h window, so the
window is clean on this for the first time.

## The window's substance, attacked

`WFG-062` shipped: withdrawn claims move from five hand-written file lists to one registry
(`docs/auto/withdrawn_claims.json`) that the whole tree is read against
(`scripts/check_withdrawn_claims.py`, wired into `make verify` and therefore into every push).
Measured here rather than restated: **915 gated files, 74 in the declared record class, 989
tracked `.md`/`.html` in scope, 3 claims, 16 spellings.**

**The row is honest about what it did not buy, and I confirmed that from the outside.** I wrote
a 26-sentence probe set without reading the patterns first: six verbatim withdrawn sentences
and twenty rewordings of the same three claims. Result: **verbatim 6/6, rewordings 1/20.** The
one catch was a rank spelling (`신고 1순위`). Nineteen escaped, including every sentence that
swaps 신고 for 제보, every English paraphrase (「the satellite alarm lagged the emergency
call」, 「citizen calls precede satellite detection」, 「the primary detection source is the
phone call」), and 「기준이 되는 시각은 최초 신고입니다」. **This does not contradict the lap;
it confirms it.** `docs/withdrawn_claims.md` §4.2 says in bold that reword sensitivity is
「조금도 개선되지 않았습니다」 and why. The gate is a copy-paste ratchet over 915 files
instead of 11, which is a real and worthwhile thing, and it is not a claim gate. **No further
claim-gate row should be taken this sprint**, which is what DIRECTION.md already says.

**What the row did leave behind (WFG-088, P1).** `docs/withdrawn_claims.md` §3 is headed
「결과 (재현 가능)」 and prints a console transcript that **does not reproduce at HEAD in three
of its five lines**: `spellings : 15` (now 16), `tracked in scope : 988` (now 989),
`record class : 73 files` (now 74). Two commits of the same lap moved them — `e3ac1e4` added
the sixteenth spelling and `9570dde` added five more registry lines — and §3 was not
re-pasted. The line under it says 「숫자는 `test_the_coverage_this_row_bought_is_recorded_and_re_derived`
가 다시 계산합니다」, and that test does not recompute those three: it asserts a floor
(`len(gated) >= 900`) and two pins (12 declared paths, 10 pinned files). The judge-quotable
pair the doc itself nominates — 「사람이 쓰는 문서 11 → 158, 검사 대상 전체 915」 — **is
still exactly right**, because the new file landed in the record class. This is small, and it
is the failure class this repository exists to gate against, one commit after the gate shipped.

## Judge drill (41 questions, mechanical pass plus the ten hardest by hand)

- Header and file agree: **41 questions, T0 15 / T1 19 / T2 7**. WFG-057's closure holds.
- **All 74 file paths cited across the bank resolve** in a fresh clone; the three bare
  filenames (`check_forbidden.py`, `check_number_collisions.py`, `delivery/sms.py`) resolve
  under `scripts/` and `src/`.
- **Every token in the bank that looks like a registry key resolves in `docs/NUMBERS.json`**
  (320 keys). The seven that do not are config fields and OSM tag names
  (`shelter_type`, `walk_cutoff_p`, `forward_sim_advance_threshold`, `region_literals`,
  `ingress_survival_time_min`, `uiseong_andong_2025`, `_evaluate_path`), not claimed numbers.
- Ten hardest answered from files without difficulty: Q1, Q2, Q4, Q8, Q10c, Q16, Q17, Q23,
  Q28, Q30b. **Q18 is the one that fails**, and it fails by being stale rather than unsourced,
  which is why it is the fix-before-next-row item and not a 「근거 없음」 entry.

## Still open from earlier laps, re-checked from the files

- **WFG-079, second window.** `docs/juso_yeongdeok.md:61` still names **봉화군**, which the
  same file's `:29` refuses to name without opening 행정표준코드, and still reprints
  「45 km」, which the same file's `:16` says is reproduced by no calculation over these files.
  Minutes of work; unchanged since critic #13 named it.
- **Twelfth consecutive window with no commit to `web/`.** The finals screen is where four of
  the five judges spend their five minutes.

## Root objection (`hate`)

**This repository is now much better at proving that nothing it wrote is wrong than at having
anything to show.** In the 24 h window, 20,812 authored text lines: `docs/auto/reports/` took
**8,052 in 45 files (38.7 %)**; every surface a judge will see — `JUDGE_QA.md`, `web/`,
`README.md`, `docs/auto/finals/`, `paper/manuscript.md` — took **1,018 (4.9 %)**, and most of
that is the manuscript's §6 admission. That is better than critic #13's 2.6 %, and it is still
eight to one. The clock says it more plainly than the ratio does: **three of eleven
`KCF_READINESS.md` lines are ticked, the last tick was R2 by critic #8 at `12bf2d9`, 0750Z, and
five critic laps have passed since without one.** `docs/auto/DEMO_SCRIPT_5MIN.md`,
`docs/auto/finals/BOOTH_SETUP.md` and `release/kcf-finals-2026/` do not exist. Five judges are
each going to spend five minutes against a five-minute script that has not been written, with
eleven days of a twelve-day sprint left.

**Cheapest test, falsifiable by the next critic lap.** WFG-062 is `done(e350571)`, so NH-021 is
satisfied and the next `todo` row in table order is **WFG-003**. If the next dev lap produces
`docs/auto/DEMO_SCRIPT_5MIN.md` and a `web/` commit, the loop can steer and R1/R4 move. If it
produces another gate, it cannot, and the honest thing then is to say so to the author rather
than file a fifteenth row about it.

## Scores (both tables in `docs/auto/SCORECARD.md`)

**B 82 held, A 75 → 74.** The composition moved inside B: **데이터 18 → 19** for the
manuscript's §6 admission (the designated inventory exists, is unused, and the extent mismatch
is stated) plus a claim record that 915 files are now read against; **제출 자료 18 → 17** for
Q18, scored on the same surface critic #13 raised it on and in the opposite direction. A takes
the same 제출 자료 step, 14 → 13, and holds 구현 15 for a twelfth window with no `web/` commit.
