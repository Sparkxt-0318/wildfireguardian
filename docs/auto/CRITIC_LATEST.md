# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-04T0349Z (critic #6).** Scope: `5a0466e..b855943`, the ten commits since
critic #5's report landed. That is the two manual paper laps critic #5 explicitly left
unreviewed (`b621441`, `2a02477` — a 938-line rewrite of `paper/manuscript.md`, five new
`references.bib` entries, `make_figures.py`, `F1_system.png`, the `.docx`, `GAPS.md` and
NH-019), critic #5's own report (`5f39452`, `ed2b267`, `f6f34ae`), the F26 repair
(`130bab7`), the decisions machinery (`5ffacd0`), and the 0255Z dev lap that cleared F21,
F22 and F24 (`e5aaaa7`, `28b4c38`, `b855943`). `paper/` changed, so `check_paper.py` ran.

**Gates, re-run independently at `b855943`: `gates.py --mode full` exits 0. `auto/dev` is
GREEN at HEAD.** `1240 passed, 62 skipped` in 205 s; verify PASS, snapshot-verify PASS,
env-check PASS, `baseline-verify` WARN as expected off-laptop (soft step, `hard: false`,
sixth lap running). Third consecutive critic lap opening on a green branch, and the first
that stayed green for the whole run. `check_paper.py` exits 0.

**The loop's own claims, checked.** Every dev and manual report in the last 24 h records a
`Reviewed by:` line; two say `self` (`2026-09-04T0134Z`, `2026-09-04T0214Z`) and both give a
reason, but `LOOP_CONFIG.json` → `review` is `subagent`, so a lap choosing `self` is
deviating from the switch the author owns rather than obeying it. Not a finding this lap
because both were author-directed laptop laps and both said so; recorded so it does not
become the habit. **Critic #5's F21, F22, F24 and F26 are all closed and were verified in
place, not taken on the report's word.** F23 is open and has spread (F30). F11, F12 are
open and unchanged (`report.py:227` still has no `paper` kind).

**No author decisions have arrived.** The Gmail search
`from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d` returns 19
threads, all of them the loop's own outgoing reports, each a single message with no reply.
PR #31 has no comments. `docs/auto/decisions_seen.json` does not exist yet, so nothing has
been applied. Eleven entries are waiting.

**Root objection.** Critic #5 said the failure class had moved: numbers are bound, and the
reasoning *about* the numbers is not. The loop fixed that instance well — better than the
critic asked, because the lap checked the critic's argument and found one premise wrong. And
in the same twenty-four hours it shipped the identical class on a bigger surface. The
sentence 「위성은 사람보다 느렸습니다」 is the front of the one finished evidence card, the
verdict of the design document, the basis of its trigger-priority table, and the body of a
**T0** answer the student is told to know by heart. No committed artifact supports it. The
project's own paper, written the same night by the same loop after its reviewer blocked it,
says the measurement cannot say it. `check_readme_figures.py`, `check_number_collisions.py`,
`check_forbidden.py` and 17 card-binding tests all pass on the card, because every one of
them reads a *value*. Every gate in this repository reads values. Not one reads what the
sentence around the value asserts, which is now the second consecutive window in which the
one wrong thing a judge would catch is a sentence rather than a number.

**The cheapest test, and it costs ten seconds:**

    grep -n "신고" docs/auto/finals/DETECTION_FLOOR_CARD.md docs/auto/JUDGE_QA.md docs/detection_floor.md
    grep -n "recorded occurrence" paper/manuscript.md

Two files, one question, two answers, no gate between them.

---

## fix-before-next-row

### F27 — The booth card, a T0 answer and the design doc's 평결 say the satellite rang after the telephone; this project's paper says the measurement cannot say that, and the manifest calls the reference clock the ignition

**Where the ordering is asserted, all of it judge-facing:**

- `docs/auto/finals/DETECTION_FLOOR_CARD.md:17-19` — the card's front, in bold:
  「**위성은 사람보다 느렸습니다.** … 위성 트리거는 신고보다 각각 **+22분 · +34분 · +64분**
  뒤에 울렸을 것입니다」; and `:11-13`, the caveat that the clock is the 신고 시각 so the
  delays are written 「실제보다 위성에 유리하게」.
- `docs/detection_floor.md:29-38` (§1, 「가장 중요한 단서 — 기준 시각은 신고 시각입니다」),
  `:240-252` (§9 평결, 「어느 쪽으로 읽어도 위성이 사람보다 앞서지 않습니다」),
  `:262-275` (§10, the trigger-priority table that ranks 사람 신고 first *because of* it).
- `docs/auto/JUDGE_QA.md:234`, inside **Q10 — a T0 question, one of the fourteen the drill
  table tells the student to make their own without paper.**

**Where it is withdrawn, in the same repository, from the same window:**

- `paper/manuscript.md:492-497` — 「no artifact supports that and this paper does not claim
  it」 — and `:533` — 「Whether that is ahead of or behind the emergency call, this
  measurement cannot say」. Table 3's caption states the clock's provenance in full.
- `paper/GAPS.md` G5; `docs/auto/NEEDS_HUMAN.md` NH-019.

**Why the paper is right, from artifacts alone — this needs no external source and no author
reply.** Checked this lap in `docs/data_provenance/fire_manifest.json`. All four detection
fires carry `start/end/reported_ha are provenance only`, and every one of their notes
describes the event start as the **ignition** (`first hit … may lag ignition`). Not one entry
contains the word 신고 or any report-time language. For `yeongdeok_2025` it is not even
ambiguous: `start` is `2025-03-22T12:15:00+09:00` and the same note reads `first hit
(2025-03-25) lags the 2025-03-22 ignition by days` — the manifest names that date the
ignition, in the field the delays are measured from.

So §1's reading is not merely unsourced, as NH-019 put it; the one artifact it cites labels
the field the other way. **And the caveat inherits the error.** The card tells a judge the
figures flatter the satellite *because* the clock is a report time. Under the manifest's own
reading there is nothing to flatter, and 「어느 쪽으로 읽어도 위성이 사람보다 앞서지
않습니다」 has no measurement behind it at all, because the human's time was never measured.
Both the claim and the safeguard that was supposed to make it conservative rest on the same
sentence.

**Smallest fix. It is a narrowing, and the paper has already written the words.**

1. `docs/detection_floor.md` §1: state the delays against the **기록된 발생일시**, quote the
   manifest's own `provenance only` sentence and its ignition note, and say the relation to
   both the true ignition and the emergency call is unestablished. Annotate the superseded
   신고 reading under CHARTER §3 rule 3; do not delete it.
2. `docs/detection_floor.md` §9: the 평결 becomes the size floor, which holds under either
   reading — a 2 km pixel does not resolve a fire below roughly a hectare, so a geostationary
   sensor cannot be an ignition-scale alarm. §10's table keeps 사람 신고 first, on the
   99 %-목격신고 statistic it already cites rather than on the ordering.
3. `docs/auto/finals/DETECTION_FLOOR_CARD.md:11-13` and `:17-19`: the same two changes. The
   card's 「+22 · +34 · +64분」 figures stay and keep their keys — no number moves here, so
   `tests/test_detection_floor_card.py`'s 17 bindings must still pass untouched. Only the
   label on the clock and the sentence in front of it change.
4. `docs/auto/JUDGE_QA.md` Q10: rewrite the ordering sentence to match, then delete the
   「근거 없음」 banner from **Q10c**, which this lap added beside it with the narrow answer
   already written.
5. Leave NH-019 **open**. Its author-facing half — one 신고접수시각 from a 산림청 / 119 /
   중대본 record — is what would let the ordering be stated again. Do not wait for it: the
   paper did not.

Filed as **WFG-053, P0**. Do this before claiming any other row: `DETECTION_FLOOR_CARD.md`
is the one evidence card the loop has finished, WFG-017 is about to put it on the finals
screen, and putting it there first would print the wrong sentence on the panel five judges
read for five minutes.

### F28 — `decisions.py` marks an author's reply read even when it recorded nothing, so a line it cannot map is lost with no trace

**Where:** `scripts/auto/decisions.py:100-104` — `cmd_apply` appends `key` to
`seen["applied"]` unconditionally, outside any check that `apply_one` changed anything;
`:69-71` — `apply_one` returns the text unchanged with the message
`no such entry; recorded nowhere`; `:115-119` — `cmd_seen` reports `seen` when **any** key
starts with the message ref.

**Reproduced this lap**, in process, against the live `NEEDS_HUMAN.md` without writing it:

    apply_one(text, "NH-020", "yes, do it", "email reply", "2026-09-05", "abc123")
      -> "NH-020: no such entry; recorded nowhere"
      -> text changed?  False        the author's words appear anywhere?  No

`cmd_apply` records `abc123:NH-020` as applied regardless, and CHARTER §6 tells the next lap
to skip any message `decisions.py seen` reports as seen. So a reply naming an id with a typo,
or an entry a later lap has not written yet, is discarded and never read again — and a reply
carrying one good line and one bad one marks the whole message read after applying only the
good one. The module's own docstring at `:15-16` promises the opposite: `A decision the loop
does not understand is still recorded, as` noted `, never guessed at`.

Nothing has been lost yet, because no reply has arrived. That is the only reason this is a
`fix-before-next-row` rather than an incident: the first author reply is the one that finds
out. This is NH-017's failure class rebuilt in code — the machinery added this window to make
the author's decisions verifiable can silently drop one — which is why it belongs above every
other infrastructure item.

**Smallest fix.** Record the seen key only when `apply_one` reports a change; append anything
else verbatim, with its message id and date, to an `## Unmapped replies` section at the foot
of `NEEDS_HUMAN.md`; exit non-zero when anything went unmapped so a lap cannot miss it; and
add one test per direction to `tests/test_decisions.py`. Filed as **WFG-054, P0**.

---

## fix-this-sprint

### F29 — The paper's page limit is enforced by a word proxy nobody has calibrated, and the loop's own recount says the limit is already breached

**Where:** `paper/check_paper.py:26` (`LIMIT = 7500`) and its docstring's
「the 20-page budget incl. refs + title」; `docs/auto/CHARTER.md` §12 (「under 20 pages
including title page and references」); `paper/GAPS.md`, ⚠ Length pressure.

Measured this lap: `check_paper` reports `body_words: 7479` — **21 words of headroom**, so the
next lap that adds a sentence fails the gate. The paper lap declared that itself and it is
honest. The finding is the layer under it. CHARTER §12 states the constraint in **pages**; the
gate measures **words**; the conversion has never been checked. The paper lap's own recount of
the built `.docx` (8,909 words including captions, tables and 25 references, plus seven
full-width figures) lands nearer **21 pages**, so on the loop's own estimate the invariant is
already broken and no gate can see it. LibreOffice is present in the sandbox but will not open
the built document, so no lap has produced a real count.

`check_paper.py` also checks no section against §12's list, which is F11 / WFG-045's
substance. Both are now **WFG-055**: get one real page count, re-derive `LIMIT` from it or
correct CHARTER §12 to whatever the measurement says, and add a section gate.

### F30 — F23 is unfixed in its second window and has propagated into the paper: one figure, three agencies

**Where:** `docs/NUMBERS.json` / `data/processed/external/fire_2025_scale.json`
(`fire2025_chain_deaths`, agency 중앙재난안전대책본부); `docs/data_sources.md:190`
(경상북도 재난안전대책본부); **new this window** `paper/manuscript.md:36-38`
(「the provincial disaster headquarters' count of 30 March 2025」); `README.md:193-199` and
`:505-513`, which still put 사망 26명 under the 아시아경제 link critic #5 opened and found
carries no death figure at all.

Critic #5 filed the gate half as WFG-051 at P1. It is now a value with three attributions
across three judge-facing documents, in the exact figure a judge is most likely to check, so
this lap **raises WFG-051 to P0**. The fix is unchanged and small: one agency spelling in the
artifact, an inline citation of its own for 26명, and a gate that compares the prose's link
and the sources table's 출처 column against the registry's `agency` and `source_url` rather
than only asserting those fields are non-empty.

### F31 — `KCF_READINESS.md` mis-stated the tree, in the file that is the final product's definition of done

R8's status named the 「about 43 %」 sentence as one of two reasons the line could not be
ticked, eight commits after that sentence was deleted. The readiness checklist is what
CHARTER §11 makes the definition of done for WFG-036, and a critic lap is what keeps it true;
critic #5 wrote that line and the two dev laps that fixed the defect did not come back to it.
**Fixed in this lap's own commit**: R8 now records (b) closed and verified at `b855943` with
(a) — no Round-4 section, no abstract draft — as the only remaining reason, and R2 carries
F27. Recorded as a finding rather than a silent edit because the same lapse can hide the
opposite state: a line that still reads ☐ for a reason that has gone is indistinguishable
from one that is genuinely blocked.

**And the number that matters more than the correction: 2 of 11 lines are ticked** (R5, R6),
with eleven days of sprint left. R1, R2, R4, R7, R9 and R11 are ☐, R12 is the author's.

### F32 — The push check that guards every push leaves no record of any push

**Where:** `scripts/auto/gates.py:103-149` (`assert_reported`).

The check itself is now correct — critic #5's F22 is properly fixed, `--diff-filter=A` is
load-bearing, and the docstring explains why. But it takes `--base` from the caller
(`origin/auto/dev` at push time) and writes nothing, so once the branch moves the push
boundaries are unrecoverable. This lap tried to verify the critic prompt's own step 2,
「every push in the window carried a report」, and **could not** — the one check whose purpose
is to make pushes auditable is the only thing here that cannot be audited after the fact.
Filed as **WFG-056**: append `{utc, mode, base, head, verdict}` to a committed ledger under
`docs/auto/`, inside `REPORT_ONLY` so it does not itself demand a report.

### F33 — Critic #5's two recommended Q&A questions were not added

`docs/auto/JUDGE_QA.md` has not changed since `fbe71de`, so the two questions critic #5's
drill declared newly answerable — 「의성 산불 피해면적이 얼마입니까?」 and 「영덕에서 몇 분이
돌아가셨습니까?」 — were not added by either dev lap since. **Added by this lap** as Q30a and
Q30b, with 근거, keys and 없는 것, since the prompt makes JUDGE_QA additions the critic's own
to write. Recorded so the general habit is visible: a critic recommendation that names no
backlog row is a recommendation the next lap does not see.

### F34 — A lettered question is invisible to every test that guards the Q&A bank

`tests/test_judge_qa_bank.py`'s `QUESTION_RE` matches `Q(\d+)`, so `Q10a`, `Q10b` and the
three questions this lap added are seen by none of the tier-count anti-padding guard, the
contiguity check, the 근거/없는 것 requirement or the T0 evidence check. Filed as
**WFG-057**: widen the pattern, restate the three header counts in the same commit, and name
the lettered questions in the §6 drill table.

### F12, F11 — open, unchanged

`scripts/auto/report.py:227` still reads
`choices=["dev","critic","research","kickoff","red","manual"]`, so the paper routine still
files as `manual` and overwrites `STATE.json` → `last_report_kind` (WFG-044). F11 is absorbed
into F29 / WFG-055.

---

## note

- **N32 · The best thing in this window is a lap correcting its own reviewer, and it should
  be kept as precedent.** Critic #5's F21 gave three reasons to delete the 「43 %」 sentence.
  The 0255Z dev lap deleted it and then checked the reasons, and found the first one wrong:
  산림청 told 경향신문 that 산불영향구역 and 피해면적 「개념이 달라서 단순 비교할 수 없고」
  and that 「실제 피해면적은 줄어들 수도 있고 늘어날 수도 있다」 — two concepts for two
  purposes, not two sizes of one thing. So `docs/data_sources.md` 함정 1 and 함정 6 now carry
  the agency's wording under its own two sources rather than the critic's directional claim.
  **The critic was wrong about that premise and this lap confirms the correction.** A loop
  whose reviewer can be wrong and whose lap checks it is worth more than a loop that obeys.
- **N33 · The same lap's own reviewer then caught it putting two quotes under one link, and
  blocked the push.** `28b4c38` is titled 「the correction gets the newspaper that actually
  printed it」. A lap whose whole subject was a sentence that shipped with a source that did
  not carry it does not get to ship one of its own, and it did not.
- **N34 · The WWA reference note is the sourcing standard the rest of the repository should
  copy.** `references.bib` re-opened its own URL and corrected the paraphrase the previous
  lap's note carried: 「Uiseong was hardest hit, with 26 deaths, while four occurred in
  Sancheong」 had been rendered as "26 of them in Uiseong-gun", which converts a fire
  attribution into a county one and drops the four deaths that reconcile 26 with 32. Nothing
  asked it to check. Five entries were added this window and all five carry a verbatim quote
  or a Crossref record.
- **N35 · Suite census, cold, in a fresh sandbox.** `1240 passed, 62 skipped` at `b855943`
  against `1229 passed, 62 skipped` at `5a0466e`: **+11 passed**, which is
  `tests/test_decisions.py` plus the `assert_reported` and paragraph-scope additions. Skips
  unchanged at 62 (the SRTM-gated six and the rest, WFG-039). Critic #2's N7 recommendation,
  gate on `collected`, is still unimplemented (WFG-038).
- **N40 · WFG-038/039 reproduced inside this lap, which is the cleanest demonstration yet.**
  This critic ran `gates.py --mode full` twice in one sandbox. Cold, at `b855943`:
  **1240 passed, 62 skipped**. Warm, at `18870d4` minutes later: **1246 passed, 56 skipped**.
  Same machine, same session, same code under test, and the difference is exactly the six
  SRTM-gated tests, which ran the second time because the first run had already downloaded
  the tile. That is WFG-039's mechanism producing WFG-038's symptom, observed by the lap whose
  job is to verify the loop's own claims — and both readings pass the gate, so a census
  recorded without saying whether it was cold or warm is not a measurement. Any lap quoting a
  pass/skip count must say which it was until WFG-039 makes the download opt-in.
- **N36 · `baseline-verify` WARN is unchanged and is not a finding.** Sixth lap running,
  `hard: false` for the git-ignored raw manifests.
- **N37 · The abstract drops a qualifier the rest of the repository insists on.**
  `paper/manuscript.md:6` calls the March 2025 fires 「the largest on the country's record by
  burned area」; §1 at `:33` correctly says 「the largest in the Korean series since it began
  in 1986」, which is what the 경상북도 release actually claims. Not filed as a row — one
  word — but it is the same shape as everything else in this report: the figure is bound and
  the sentence around it is a little freer than the source.
- **N38 · §4.7's negative control was checked with `mandela` and does not leak.** The 709
  control steps take their label from construction (same sites, same clock times, fourteen
  days earlier) rather than from a fire record, which is a designer-supplied ground truth —
  but the paper and the card both report `0 of 709` as an **upper bound** rather than a rate,
  name the scope (four sites, one season) and give the 95 % bound. That is the correct
  handling and no finding is filed. No model, split, metric or eval otherwise moved in this
  window, so `mandela` fires on nothing else.
- **N39 · Two laps used `review: self` while `LOOP_CONFIG.json` says `subagent`.** Both
  (`0134Z`, `0214Z`) ran on the author's laptop outside the routine and both said so in their
  reports. Not a finding; recorded because the switch is the author's layer under CHARTER
  §10, and "I ran outside the routine" should not become a standing exemption from it.

---

## The judge drill

Ten questions, answered using only files in the repository. Seven are answered well, one is
answered by two files that disagree, and two are answered by files that disagree with each
other on an attribution.

| # | question | can a file answer it? |
|---|---|---|
| 1 | 「그 22분·34분·64분은 신고 기준입니까, 발화 기준입니까?」 | **No, and two files claim it can.** F27. Added as **Q10c**, marked 「근거 없음」 |
| 2 | 「의성 산불 피해면적이 얼마입니까?」 | Yes, well — 99,289 ha with the basis, the superseded 45,157 ha estimate and why no ratio is printed. **Added as Q30a** |
| 3 | 「영덕에서 몇 분이 돌아가셨습니까?」 | Yes — 10명, named as a 재인용값, with the 9명 interim beside it and neither collapsed. **Added as Q30b**, with F30's warning attached |
| 4 | 「사망 26명은 어느 기관 집계입니까?」 | **No.** Three answers in three documents, and the README's own link carries no death figure (F30). Carried inside Q30b's 없는 것 rather than as a fourth question |
| 5 | 「이 화재군이 전국 산불의 몇 %입니까?」 | Yes, and the answer is that the repository refuses to divide them, with three reasons and the agency's own wording. This was the last window's failure and it is now the bank's best answer |
| 6 | 「오경보율은 몇 %입니까?」 | Yes — Q10b, `0 of 709` as an upper bound with its scope. Unaffected by F27 |
| 7 | 「임계값에서 실제 발화의 몇 %를 잡습니까?」 | Yes — Q1, pooled 0.138, three folds with no true positive, in the model card above the AUC |
| 8 | 「낯선 사람이 이걸 다시 돌릴 수 있습니까?」 | Yes — Q28, and this lap is a data point: a fresh sandbox bootstrapped in about a minute and ran 1,240 tests green |
| 9 | 「AI 사용을 어디에 정리해 두셨습니까?」 | Yes again, and it was `No` last lap. F24's archived copy at `docs/auto/archive/AI_DISCLOSURE_retired_2026-09-04.md` restores the single document Q29 needs to hand a judge |
| 10 | 「부스에서 무엇을 보여 주십니까?」 | **Not from a file.** `web/finals.html` has not been touched since 09-03, `KCF_READINESS` R1/R2/R4/R7/R9 are ☐, and there is no 5-minute script. Already WFG-017 / WFG-003 / WFG-036; no new row |

**Where the bank is silent and should stay silent.** Nothing in it claims a share of the
national total, and Q30a now explains why. Nothing should claim the detection ordering until
F27 is fixed; until then the answer is the size floor, which is true either way.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass** | Green at HEAD for a third window, 1,240 tests, a check that refuses a push whose gates read another commit and now refuses one that edits an old report instead of writing a new one. And a lap that fact-checked its own reviewer and corrected the record rather than obeying. If the student can explain that machine in ninety seconds it is the strongest part of the entry. |
| KCF judge · 재난 대응 공무원 | **fail**, on the card I would be handed | I would read the panel: 「위성은 사람보다 느렸습니다, 신고보다 +22분」. My next question is which 신고 — whose record, what time. There is no record. In dispatch a claim about who knew first, without the log, is the claim you do not make. Everything else on this card is careful, which is why the front of it costs so much. |
| fire-behaviour scientist | **pass** | Last window's inverted 영향구역 relation is gone, and the fix is better than what I asked for: the agency's own wording, that the two statistics cannot be simply compared, under both of its sources. §4.7's size floor is stated as an order of magnitude because the flame-temperature assumption moves it eightfold, and Yeongdeok is set aside as confounded rather than explained. That is how you write a detection result on n = 3. |
| ML reviewer (leakage, baselines) | **pass** | Ran `mandela`. No model, split, metric or arm moved. The one new eval, §4.7's 709-step control, takes its label from construction and reports zero as an upper bound with its scope, which is the honest handling. WFG-050's prose-test leakage is open and correctly named. The reviewer that blocked the ordering claim is doing the work I would do. |
| statistician | **fail**, same shape as last time | Last window you printed 43 in the README and 94.8 in the registry. You fixed it. This window one fire's death toll is attributed to three different agencies in three documents, and one document says the satellite was late while another says you cannot know. A repository whose entire thesis is one fact one home cannot hold two answers to one question, twice running, in the artifacts a judge reads first. |

**Where they agree:** the window's work is good and the process is visibly getting stronger —
a reviewer that blocks, a lap that checks the reviewer, a gate that got tighter. Four of five
lenses would let the paper and the README go to a booth today.

**Where they split, and it is the same split as last window with the roles swapped:** the two
failures are not about the paper, which is careful. They are about the two Korean documents a
judge physically holds. The paper says less than it could; the card says more than it can.

**The question that resolves the split.** Critic #4 asked which *numbers* here can be wrong
without a gate noticing. Critic #5 asked which *sentences* can. This lap's version is narrower
and worse: **which of the sentences a judge actually reads out loud does the repository
already know are wrong?** Today the answer is two — the detection verdict and the 26명
attribution — and in both cases the loop wrote the correction down somewhere else and left the
judge-facing copy standing.
