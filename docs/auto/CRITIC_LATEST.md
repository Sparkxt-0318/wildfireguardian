# CRITIC_LATEST — critic #8, 2026-09-04T0750Z

Window `8e0a6ad..12bf2d9` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `12bf2d9` in a
fresh cloud sandbox. `1273 passed, 62 skipped` in 204 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). Against critic #7's cold reading at
`8e0a6ad` (`1261 passed, 62 skipped`) that is **+12 passed, skips unchanged** — like for
like, both cold, second window running. `verify`, `snapshot-verify`, `env-check` PASS;
`baseline-verify` WARN, expected off-laptop, `hard: false`, eighth window and still not a
finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. Green at HEAD for the
fifth consecutive critic lap.

**The window's headline: the screen exists.** `web/finals.html` had not been opened by this
loop since 2026-09-02. It now carries the five evidence cards, 26 tests binding them to the
artifacts, nine committed screenshots and a 219-line document saying what each card does
**not** say. `KCF_READINESS.md` R2 ticks today, the first tick since 2026-09-03, and Track A
구현 및 유용성 moves 11 → 14 after nine windows at 11. Critic #7's cheapest test was "take
WFG-017 and find out what it costs". It cost one lap and three review blocks. The risk was
real and it is now retired.

---

## fix-before-next-row

**None, again, and for the same reason critic #7 gave: the table order is already right.**

The two rows below are the top two `todo` rows in `docs/auto/BACKLOG.md` and both are P0.
They are one lap together and the next dev lap should take them in this order.

1. **WFG-063** — the T0 answer the student recites contradicts, inside one file, the T0
   answer that forbids it, and now contradicts the screen behind them as well (F42).
2. **WFG-067** — the screen prints a build commit that does not exist (F41). Two lines of
   fix, and it sits on the surface the loop just spent a lap earning.

Naming them as rows rather than as `fix-before-next-row` items is deliberate: nothing in
this window needs undoing, and a lap that starts by re-reading a report writes less code.

---

## fix-this-sprint

### F41 — The panel that exists to prove the build prints a commit that does not exist

**Where:** `web/finals.html` (`"git":"a562045"`), rendered on the RELIABILITY tab as
「SYSTEM INTEGRITY · build 2026-09-04 07:11 UTC · commit a562045」 and visible in the
committed screenshot `docs/auto/finals/screens_20260904T0630Z/4_reliability.png`. Also
`docs/auto/finals/screens_20260904T0630Z/README.md:3`, `docs/auto/BACKLOG.md` WFG-017's
`done(a562045)`, and the 0714Z / 0719Z / 0725Z reports. **Row: WFG-067 (P0).**

In a fresh clone of `auto/dev`, `git cat-file -t a562045` answers
`fatal: Not a valid object name a562045`. The id is a pre-rebase hash:
`scripts/build_finals.py:815`'s `git_head()` reads `git rev-parse --short HEAD` at build
time, the lap then ran `git pull --rebase origin auto/dev`, and the rebase discarded the
object the stamp names. Nothing re-reads it and no test in `tests/test_finals_screen.py`
touches that line.

This is not cosmetic and it is not a number. It is the **one line on the screen whose only
purpose is to let someone check the rest**, and it is the first string an ISEF or IEEE
reproducibility reviewer would paste into a terminal. Everything around it is honest: the
three gate lines really ran and really passed at build time, and the three `DATA` rows carry
live sha256 prefixes of the committed snapshots. The screen invites the check and then
fails it.

**The fix has a trap.** Do not gate the stamp against `HEAD`. The commit that carries a
build is always one later than the commit the build was made at, so an equality gate is
unsatisfiable and the next lap would weaken or delete it. Gate that the stamp **resolves**:
`git cat-file -e <stamp>`, one line, and rebuild before pushing when a rebase moved the
branch. `JUDGE_QA.md` Q35 is added this lap so the booth is safe before the row lands.

### F42 — The Q&A bank tells the student to say, at T0, a sentence it forbids at T0

**Where:** `docs/auto/JUDGE_QA.md:240` (Q10, tier **T0**) against `:353` (Q10d, tier
**T0**). **Row: WFG-063 (P0), open a second window, now sharper.**

Critic #7 filed F35 as a stale sentence: Q10 still named 「신고의 99 %가 목격 신고」 as a
ground after the 99 % had been struck from the booth card and forbidden 60 lines away in the
file Q10 cites as its 근거. The fix did not land in this window. What landed instead was
critic #7's own guard, Q10d, which lists that exact sentence among 「❌ 말하면 안 되는 것」.

So the bank now holds two T0 answers to the same question, one instructing the student to
say what the other forbids, and `JUDGE_QA.md:17-23` tells the student to memorise all T0
answers word for word. This is no longer a stale sentence a careful judge might catch; it is
a document giving two opposite recitation orders and no way to tell which is current.

**And the split now includes the screen.** `scripts/finals.template.html:1858` and the built
`web/finals.html` say 「이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, 어떤
소스가 일차여야 하는지는 재지 않았습니다」 — exactly what the row asks for.
`docs/finals_screen_v2.md:81-83` records that the lap wrote the screen in the corrected form
deliberately, before the correction reached anywhere else, and says why. That was the right
call. Its consequence is that the student reciting Q10 would now contradict the screen
behind them, in front of the judge, on the sentence the fire-behaviour and 재난 공무원 lenses
both probe.

The fix has not changed and no number moves: `JUDGE_QA.md:240`,
`docs/detection_floor.md:319`, `docs/auto/finals/DETECTION_FLOOR_CARD.md:28` and `:78`, and
the screen is already the model sentence to copy.

### F43 — Six questions are invisible to every gate, and one of them is the guard

**Where:** `tests/test_judge_qa_bank.py:45`, `docs/auto/JUDGE_QA.md:17-23`.
**Row: WFG-057, raised P1 → P0 and its stated fix corrected.**

`QUESTION_RE = re.compile(r"^\*\*Q(\d+) · (T[012])\.", re.MULTILINE)`. The escaping headers
are `**Q10a · T1 (WFG-021 a).`, `**Q10b · T1 (WFG-021 a).`, `**Q10c · T1 (크리틱 #6).`,
`**Q10d · T0 (크리틱 #7).`, `**Q34 · T2 (크리틱 #7).` and now `**Q35 · T1 (크리틱 #8).`.

Critic #6 diagnosed this as the letter suffix. **That diagnosis is incomplete and the row's
「done when」 would not fix it.** The parenthetical between the tier tag and the period
defeats the pattern on its own — which is why `Q34`, which carries no letter at all, escapes
too. Widening the pattern for `Q(\d+)[a-z]?` and stopping there leaves Q34 and Q35 invisible
and the row would close while the defect stands.

**Why this is P0 and not a tidy-up.** The header at `:17-23` says 「33개」 and
「T0 (14개) · T1 (13개) · T2 (6개)」 and tells the student
「T0 … 이것만 완전히 외우십시오」. The file now holds **38 questions and 15 T0s**. The
fifteenth T0 is **Q10d** — the entry whose entire job is to stop the student saying a
sentence this repository cannot support. A student who obeys the bank's own drill plan
memorises the fourteen and never reaches the guard, while Q10, which carries the forbidden
sentence, **is** one of the fourteen. F42 and F43 are the same failure seen from two sides:
the gate cannot see the guard, and neither can the reader.

### F44 — A routine that can do a row's work but cannot mark it done

**Where:** `docs/auto/BACKLOG.md` WFG-064; CHARTER §12. **Row: WFG-068 (P1). WFG-064 closed
by this lap.**

CHARTER §12 confines the paper routine to `paper/` plus its own report, which is the right
isolation. Its unwritten consequence is that a backlog row the paper lap completes stays
`todo`, because `BACKLOG.md` is out of reach.

WFG-064 is the first instance and it is fully done. This lap opened both PNGs at `12bf2d9`:

- **F2** writes every value inside its bar in white and names the two reference rules in a
  boxed legend in the lower right, a corner the shortest bars leave provably empty. The
  `0.878` label is clear of the `0.890` rule and nothing sits on the tick labels.
- **F7** reads vermilion = deadline-first and teal = nearest-first in **both** panels, and
  panel b says 「ahead」 rather than 「wins/loses」 so colour and word agree.

The paper lap also found and fixed two defects nobody had named (F1's arrow landing on a box
**corner**, so it read as pointing between boxes; F5's last value label touching the panel
frame) and wrote both rules into `paper/README.md` so the next figure inherits them. It then
wrote 「CHARTER §12 stops this routine editing `BACKLOG.md`」 and left the row `todo`. Had no
critic run, the next dev lap would have claimed a finished row.

### F45 — The daily check this routine is asked to perform cannot answer the question it is asked

**Where:** `scripts/auto/gates.py --assert-reported`. **Row: WFG-056 (F32), open, second
window; verified this lap.**

The critic prompt asks that every push in the window be confirmed to have carried a report
(`gates.py --assert-reported --base <previous push>`). Ran it against eight bases spanning
the whole 24 hours: `3156459`, `1113388`, `0ff1b36`, `8d1decf`, `12b8ac7`, `5a0466e`,
`b855943`, `8e0a6ad`. **All eight exit 0, and all eight name the same report**,
`docs/auto/reports/2026-09-04T0725Z-dev.md`, because the check is satisfied by any one new
report anywhere in the range. A window of ten pushes and one report passes exactly like a
window of one and one.

So the daily verification is **not performed today and has never been performed**, and this
lap says so rather than reporting a pass it did not earn. The push ledger WFG-056 asks for
is what would make it real. What this lap *can* say, from the report files themselves: every
dev report in the window carries a `Reviewed by:` line except
`docs/auto/reports/2026-09-04T0401Z-dev.md`, which is critic #7's F40 unchanged and is a
record, not a new defect.

### F46 — One death toll, two spellings, and the wrong one is the registry

**Where:** `docs/NUMBERS.json` → `fire2025_chain_deaths`; `README.md:198` and `:510`.
**Row: WFG-051 (P0), fourth window, narrowed.**

Progress: the paper lap corrected `paper/manuscript.md` this window and registered
`dgmbc2025toll` for it. **This lap opened that page independently**
(<https://dgmbc.com/article/bLdh4s3M4pgcSdYI0MZPc>, 2026-09-04) and it reads verbatim
「경상북도 재난안전대책본부가 3월 30일 오전 8시 30분을 기준으로 발표한 자료에 따르면 산불로
인한 경북 지역 사망자는 영덕군 9명, 영양군 7명, 안동시와 청송군 각각 4명, 의성군 2명 등
26명입니다」, and **neither 「중앙재난안전대책본부」 nor 「중대본」 appears on the page.**

Three spellings are now two, and `docs/data_sources.md:190` and the manuscript are both
right. What is left is worse for being smaller:

- `fire2025_chain_deaths`'s `derivation` says `agency: 중앙재난안전대책본부 … source: newsis`,
  a breaking-news stub that names no agency at all. The registry is the SSOT and it is the
  one that is wrong, against a page this repository already cites.
- `README.md:198` asserts 「경상북도 최종 집계·**중앙재난안전대책본부 확인**」 and `:510`
  repeats it in English. No source in this repository supports that confirmation, and the
  link a judge would click carries no death figure at all.

### Carried, unchanged, from earlier windows

- **WFG-054 (F28)** — third window open. `decisions.py apply` marks a message read even when
  it recorded nothing, so the **first** author reply is the one at risk. See NH-020: there
  has still not been one, which is why this has not bitten yet and why it will.
- **WFG-055 (F29)** — `check_paper` now reports `body_words: 7408` against the 7,500 hard
  fail (was 7,479). 92 words of headroom instead of 21, still measuring a proxy for a page
  limit nobody has calibrated. The paper lap corrected the earlier account of why: LibreOffice
  fails on **any** `.docx` in this environment, not on ours.
- **WFG-061 / NH-019, WFG-062, WFG-065, WFG-066, WFG-038/039, WFG-050, WFG-048, WFG-044** —
  all unchanged.

---

## note

- **N47 · The window's best act is a document nobody asked for.**
  `docs/finals_screen_v2.md` is 219 lines whose organising rule is 「무엇을 말하지 않는가」,
  written per card, with the reviewer's three blocks quoted **inside** the entries they
  changed: the refuge card's 「전 계층 재계산으로 확인한 것은 지점 한 곳뿐입니다」 is item
  **zero** of what that card does not say, and it is there because the draft closed a
  paragraph with a verb the artifact did not support (「일치했습니다」) over three numbers
  that were correct. Three numbers right, one verb wrong, caught, and then made the first
  thing the student reads. That is the discipline this project is actually selling.
- **N48 · The screen is the first artifact in this repository a judge can hold, and it is
  honest.** Checked the four tabs against their sources. The EVIDENCE grid leads with
  `0.89 ± 0.09 AUC` and immediately says pooled 0.905 is a different metric; the operating
  point card prints 0.138 with the three folds that have no true positive **and** their
  positive-cell counts, so 「참양성 0」 cannot be read as 「모델이 부서졌다」; the RELIABILITY
  tab's cards are titled 「운영용 소프트웨어가 아닙니다」, 「기상 입력의 한계」,
  「부정 결과도 결과입니다」. A screen whose reliability tab leads with what it cannot do is
  a rarer thing at a booth than a screen that works.
- **N49 · The detection card ships the fix its own backlog row is still waiting for.** Verified
  by grep: `web/finals.html` contains 「위성을 일차로 둘 수 없다는 것까지이며, 어떤 소스가
  일차여야 하는지는 재지 않았습니다」 and contains no sentence promoting 사람 신고. The
  screen is right and three markdown documents are wrong. That is the inverse of every
  previous window in this series, where prose was fixed and the screen was untouched.
- **N50 · The author has replied to nothing, and the decision machinery has never run once.**
  Searched the mailbox this lap: 25 threads match `subject:"WildfireGuardian autoloop"` in 14
  days, and **every thread holds exactly one message**, the loop's own report. PR #31 has zero
  comments. `docs/auto/decisions_seen.json` does not exist because `decisions.py apply` has
  never recorded anything. Twelve entries are open and NH-016's date is **tomorrow**. Filed as
  **NH-020** with three one-line reply options, because the loop cannot distinguish "read and
  not answered" from "never arrived", and those need opposite responses.
- **N51 · WFG-038/039 reproduced a third time, and the comparison is clean again.** One cold
  full-suite pass, quoted as cold: `1273 passed, 62 skipped` against critic #7's cold
  `1261 / 62`. Every census in this series should carry the word until WFG-039 makes the SRTM
  download opt-in.

---

## The judge drill

Ten questions, answered using only files in the repository.

| # | question | can a file answer it? |
|---|---|---|
| 1 | 「부스에서 무엇을 보여 주십니까?」 | **Yes, and it could not last window.** `web/finals.html`, four tabs, five evidence cards; nine committed screenshots at `docs/auto/finals/screens_20260904T0630Z/`; `docs/finals_screen_v2.md` explains each card. R2 ticked |
| 2 | 「그러면 왜 **사람 신고**를 일차 소스로 둡니까?」 | **No, and the repository now answers it two opposite ways at the same tier.** F42. The screen is right, Q10 is wrong, Q10d forbids Q10. WFG-063 |
| 3 | 「화면 아래 「commit a562045」 로 이 화면을 다시 만들 수 있습니까?」 | **No.** That object does not exist (F41). Added this lap as **Q35 (T1)**; the honest answer is 「그 줄은 지금 틀렸습니다」 and it names what *is* reproducible |
| 4 | 「사망 26명은 어느 기관 집계입니까?」 | **Half.** The manuscript and `data_sources.md` say 경상북도 and cite the page that says it; the registry and README still say 중앙재난안전대책본부. Fourth window (WFG-051) |
| 5 | 「화면의 숫자가 산출물과 어긋나면 무엇이 잡습니까?」 | **Yes, and this is new.** `tests/test_finals_screen.py`, 26 tests, each named for the claim it guards, comparing the built HTML to the committed artifact |
| 6 | 「대피 지점 두 곳·세 곳도 전 계층 재계산으로 확인했습니까?」 | **Yes, and the answer is no, and the card says so first.** `docs/finals_screen_v2.md` §2.4 item 0; one node at k=1, and even that node differs from `marginal_curve.k1_nodes` |
| 7 | 「출동 순서 정렬이 실제로 효과가 있습니까?」 | Yes, and the answer is **no, and we report it** — §4.6, the abstract, F7 panel b (now legible), `JUDGE_QA.md:416`. Still the strongest answer in the bank |
| 8 | 「이 산불의 확산 속도는 시간당 얼마였습니까?」 | **No file a judge can be shown.** Q34 answers it honestly (「저희가 측정한 값이 아닙니다」). WFG-065, unchanged |
| 9 | 「5분 시연 대본이 있습니까?」 | **No.** R4 ☐, WFG-003. The screen exists and the script for walking a judge through it in five minutes does not. This is the next screen-shaped gap |
| 10 | 「논문은 20쪽 제한 안에 들어갑니까?」 | **No.** 7,408 words against a word gate standing in for a page limit; the converter cannot open any `.docx` in this environment, so nobody has counted the pages (WFG-055) |

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass**, and the first one I would call strong | Green at HEAD for a fifth window, 1,273 tests, and this window the machine finally produced something I can look at rather than read about. Twenty-six tests that compare a **built HTML file** to the artifacts it was built from is not a thing student projects have. Show me `test_finals_screen.py` and the screen side by side and that is your ninety seconds |
| KCF judge · 재난 대응 공무원 | **pass**, first time in this series | Last window I refused the card because it told me to build my trigger around the telephone and could not tell me why. The screen does not do that. It says the satellite cannot be primary and that it did not measure who should be. I can work with a system that knows the edge of its own evidence. What I will still ask at the booth is what your alert desk does with three false alarms a day, and 「상한」 is not an answer to that |
| fire-behaviour scientist | **pass**, unchanged and still short of strong | The size floor is given as an order of magnitude because the flame-temperature assumption moves it eightfold, and the screen prints the range rather than the point estimate. Correct instinct twice. Still: 8.2 km h⁻¹ is the number that characterises this fire and I cannot find it in anything you would hand me (WFG-065, second window) |
| ML reviewer (leakage, baselines) | **pass** | Ran `mandela` over the window. No model, split, metric, arm or eval moved, so it fires on nothing new. One thing it *did* fire on and the lap had already caught: a draft test would have permanently banned the **artifact's own wording** from the screen, which is a presentation layer beating its source through a gate. It now tests that the disagreement is disclosed instead. That is the correct fix and it is written down at `docs/finals_screen_v2.md:105-107` |
| statistician | **pass**, held | 「+12 passed, both readings cold」 is the second comparable census in a row, which is a habit now. Against that: the 26명 attribution is four windows old and the registry is the wrong one, and F43 means the document I would audit does not know how many questions it holds. A file that miscounts itself is not a file I trust to be complete |

**Where they agree:** the screen, and specifically that it states its own limits per card.
Four of five named it unprompted.

**Where they split:** the professor and the 공무원 are looking at the screen and are
satisfied; the statistician is looking at the documents behind it and is not. That is
exactly the shape of F42 and F43 — the surface got better than the record it is drawn from.

---

## The root objection, and its cheapest test

Critic #4 asked which numbers can be wrong without a gate noticing. #5 asked which
sentences. #6 asked which sentences the repository already knows are wrong. #7 asked why
eight windows of evidence had never touched the thing judges look at. That one is answered.
This lap's is the inverse of #7's:

> **The screen is now the most correct document in this repository, and every gate this
> project owns points the other way.** `web/finals.html` states the withdrawn claim
> correctly while `JUDGE_QA.md`, `detection_floor.md` and the booth card do not. It carries
> a build stamp no gate checks and that no longer resolves. The Q&A bank cannot count its
> own questions, so the entry that stops the student saying a forbidden sentence is
> invisible to both the test suite and the drill plan. The loop has spent eight windows
> building gates that read **values**, and every defect in this window is a defect of
> **agreement between surfaces** — which no gate here can see.

**The cheapest test, and it is one lap:** take WFG-063 and WFG-067 together, then look at
what the fix actually required. If narrowing one sentence in three files and adding one
`git cat-file -e` closes both, then WFG-062 (a registry of withdrawn claims that any
document can be checked against) is the right generalisation and should be promoted from P1
to the front of the P0 block, because it is the only row in this backlog that would have
caught F42 on its own. If the fix instead needs a fourth and fifth document nobody listed,
that is the answer too, and it is worth more than the fix.
