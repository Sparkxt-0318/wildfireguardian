# Backlog — what the loop works on, in order

Conventions: `docs/auto/CHARTER.md` §5 and §11. **P0** ships inside the sprint (by
2026-09-15), **P1** before the freeze (2026-10-16), **P2** after the finals (2026-10-24;
ISEF), **P3** for the IEEE paper. Status: `todo | in-progress(<stamp>) | done(<commit>)
| blocked(<why>) | parked(<why>)`. The dev routine takes the first `todo` row in table
order that is agent-doable and unblocked; `blocked(human)` rows are the author's and are
mirrored in `docs/auto/NEEDS_HUMAN.md`. This table was re-keyed on 2026-09-03 from the
research brief (`docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`) and its backlog
proposal (`BACKLOG_PROPOSAL_2026-09-03.md`), which explain every priority change; the
eight sweeps behind them are under `docs/auto/research/sweeps_2026-09-03/`. Rows the
proposal demoted keep their IDs so earlier reports still resolve.

## Sprint plan, 2026-09-04 to 09-15 (CHARTER §11)

Table order below is the order of work. Target days are for the critic to
measure slippage against, not deadlines a lap may skip past.

| by | rows | what the author sees at the end of that day |
|---|---|---|
| 09-04 | WFG-002, WFG-004 | Q&A bank v2 done; one value per quantity across judge-facing docs |
| 09-05 | WFG-020, WFG-021 | survivor-survey evidence registered; detection-floor panel + GK2A tests |
| 09-07 | WFG-017, WFG-003 | finals screen v2 with the evidence cards; 5-minute script and screen audit |
| 09-08 | WFG-024 | dates and branch re-keyed everywhere (R11); WFG-016 withdrawn 09-04 |
| 09-10 | WFG-036 | **final product bundle v1** (`release/kcf-finals-2026/`, R9) |
| 09-11 | WFG-007, WFG-030, WFG-031 | booth checklist + printables as PDF; report-number gate; CITATION.cff |
| 09-12 | WFG-026, WFG-027, WFG-010 | related-work + SFTD059T panel; schedule/roles timeline; README Round-4 + abstract |
| 09-13 | WFG-025, WFG-009 | the two clean single-variable sweeps; Playwright smoke of the screen |
| 09-14 | WFG-036 v2 | bundle rebuilt with everything above; every KCF_READINESS line ticked except R12 |
| 09-15 | buffer | slippage, critic findings, MEMO; the 09-16 handover writes the post-sprint list |

Left for after the sprint by design: P2 and P3 rows, anything needing the
laptop's raw bundle (WFG-005/006/032/034), and the author-only rows.

| ID | P | goal | title | status | agent-doable | effort | rubric rows |
|---|---|---|---|---|---|---|---|
| WFG-022 | P0 | KCF | Five questions to the KCF 운영사무국 (date, track, 기여 ② restatement, AI disclosure, 제출 자료 scope) | blocked(human) | **false** | hours | Pass/Fail · all rows |
| WFG-023 | P0 | infra | Protect `Main`; ratify `auto/dev`; decide the two HANDOFF §4 items; approve/veto decimation; close NH-001/002/006 | blocked(human) | **false** | hours | — |
| WFG-018 | P0 | KCF | 제출본 대비 정본 reconciliation sheet as NEAR-labelled prose (Korean, one page) | done(20260903T0653Z) | true | hours | 제출 자료 · 데이터 해석 |
| WFG-019 | P0 | science | Operating-point evidence package: per-fire recall/FNR at 0.3, PR curve, nested LOFO threshold calibration as a negative result, MODEL_CARD appendix | done(20260903T1224Z) | true | one lap | 데이터 수집·분석·해석 · 설계와 방법론 |
| WFG-002 | P0 | KCF | Judge Q&A bank v2 (**revise**: corrected numbers, four new questions, deprecated phrasings purged) | done(20260903T1536Z) | true | one lap | 연구 목적 · 설계와 방법론 · 데이터 해석 |
| WFG-004 | P0 | KCF | SSOT sweep (**revise**: fix README:731, reconcile `fold_sizes.md` vs `NUMBERS.json` on the primary AUC, annotate superseded values) | done(20260903T1622Z) | true | one lap | 제출 자료 |
| WFG-020 | P0 | KCF | Greenpeace 2026 survivor survey registered as evidence + the "85% drove" answer | done(20260903T1821Z) | true (fallback NH) | hours | 연구 목적 · 데이터 수집 |
| WFG-021 | P0 | KCF | Detection-floor panel (Session 19 as recorded) + tests for `src/wildfireguardian/detection/gk2a.py` | **done for the sprint** — **(a) done(b557e9d)**, **(b) done(f5f8498)**, **(c) parked(needs the NOAA archive at run time; not runnable in the cloud sandbox — parked by critic #6 so this row stops sitting above WFG-017 as a `todo` a lap must first read and reject)** | true | one lap | 데이터 수집·분석·해석 · 설계와 방법론 |
| WFG-017 | P0 | KCF | `web/finals.html` refresh v2: evidence cards for operating point, detection floor, horizon grounding, refuge placement, reconciliation; rebuilt with `--verify` | done(a562045) | true (fallback: student runs `make finals`) | one lap | 제출 자료 · 구현 및 유용성 |
| WFG-003 | P0 | KCF | Finals screen audit + 5-minute demo script (keep) | todo | true | one lap | 제출 자료 · 구현 및 유용성 |
| WFG-063 | P0 | KCF | **The trigger recommendation lost its evidence and the T0 answer kept it.** `docs/detection_floor.md` §10 now says in bold that 「신고의 99 %가 목격 신고」 may not carry a conclusion (unregistered, interim), and the booth card dropped it — but `docs/auto/JUDGE_QA.md:240`, a **T0** answer, still names it as one of the two grounds for 신고 우선. And with it gone, nothing left in any judge-facing document supports 「사람 신고를 일차로」: the size floor rules the **satellite out**, it does not rule the **human in**. Restate the claim as the one the measurement carries (「위성을 일차 트리거로 둘 수 없습니다」) in `JUDGE_QA.md` Q10, `detection_floor.md` §10 row 1 and `DETECTION_FLOOR_CARD.md:28,78`, and delete the 99 % clause from Q10 (critic #7, F35) | **done(20260904T0820Z)** — narrowed in five surfaces (JUDGE_QA Q10 · Q10d, detection_floor §10 with its 우선순위표 replaced, DETECTION_FLOOR_CARD front + 트리거 표, SESSION19_REPORT Phase 3 annotated as a record) and gated: `tests/test_detection_ordering_is_not_claimed.py` gains a second claim family that scans five judge-facing surfaces **including the built `web/finals.html`** for the banned spellings AND requires all five to carry the permitted clause verbatim | true | hours | 데이터 해석 · 제출 자료 · 구현 및 유용성 |
| WFG-067 | P0 | KCF | **The finals screen's integrity panel prints a commit id that does not exist in this repository.** `web/finals.html` carries `"git":"a562045"` and the RELIABILITY tab renders it as 「SYSTEM INTEGRITY · build 2026-09-04 07:11 UTC · commit a562045」 — the first line of the panel whose entire job is to let a judge verify the build. `git cat-file -t a562045` answers `fatal: Not a valid object name`. `scripts/build_finals.py:815` `git_head()` stamps `git rev-parse --short HEAD` at build time and the lap then rebased, so the hash died between the build and the push; no test in `tests/test_finals_screen.py` asserts the stamp resolves. The same dead id is quoted in `docs/auto/finals/screens_20260904T0630Z/README.md:3` (the provenance line of the nine committed screenshots), in `docs/auto/BACKLOG.md` WFG-017's `done(a562045)` and in three reports. Rebuild after the rebase so the stamp names a real commit, and add the one-line gate that makes it structural: the stamp in the built `web/finals.html` must satisfy `git cat-file -e`. Do **not** try to make the stamp equal `HEAD` — the commit that carries the build is always one later; the requirement is that it resolve (critic #8, F41) | todo | true | hours | 데이터 해석 (재현) · 제출 자료 (출처) |
| WFG-064 | P1 | paper | **Two of the seven restyled figures have colliding labels, and the lap that shipped them said all seven were looked at.** `paper/figures/F2_lofo_auc.png`: the `0.878` bar label is struck through by the red 「mean of folds 0.89」 rule, and 「pooled 0.905」 sits on the x-axis over the tick labels. `F7_dispatch_ordering.png`: panel b's 「deadline first wins」 teal is the same teal as panel a's 「nearest first」, two meanings on one colour inside one figure. Nudge the labels (offset a value label that falls within ~1 % of a reference rule; place the pooled label inside the axes) and give panel b its own hue. Rubric row is literally 「그래픽 및 범례의 명확성」 (critic #7, F36) | **done(e28377c)** — closed by critic #8, which opened both PNGs at `12bf2d9` and looked: F2 writes every value inside its bar in white with the two reference lines named in a boxed legend in the lower right, and F7 reads vermilion = deadline-first / teal = nearest-first in **both** panels with panel b saying 「ahead」 rather than 「wins/loses」. The paper lap also found and fixed two defects nobody had named (F1's arrow landing on a box corner, F5's last label touching the frame) and wrote both rules into `paper/README.md`. The row could not close itself: CHARTER §12 forbids the paper routine touching `BACKLOG.md` — that mechanism is WFG-068 | true | hours | 제출 자료 |
| WFG-065 | P1 | KCF | **The most quotable fire-behaviour figure about the motivating event is in no judge-facing document.** 8.2 km h⁻¹ forward spread (국가산림위성정보활용센터, from S-NPP/VIIRS thermal detections, 2025-03-22 onward; a Korean record) lives only in `docs/auto/knowledge/PYROGEOGRAPHY.md:45`. It is the first thing a fire-behaviour judge asks about 의성. Register it under CHARTER §3.5b with agency + as-of + scope + the URL a lap opened, add it to `docs/data_sources.md` table A and answer it in `JUDGE_QA.md`, or write down in one line why it stays out (critic #7, F38; the 1.5× / 고성 2019 5.2 km h⁻¹ comparison did **not** verify in this lap's search and must not travel with it) | todo | true | hours | 연구 목적 · 제출 자료 (출처) |
| WFG-066 | P1 | infra | **A bibliographic record was written from memory in a repository whose rule 5 is 「no fabricated citations」.** `docs/auto/knowledge/PYROGEOGRAPHY.md:169` carries `[UNVERIFIED — not opened; author list from memory]`. Critic #7 checked it: Sullivan, Sharples, Matthews & Plucinski (2014), *Environ. Model. Softw.* **62**: 153–163 is **correct in every field**, confirmed against the FRAMES catalog record (frames.gov/catalog/53980) and the ScienceDirect listing. So replace the tag with `[verified 2026-09-04 · FRAMES catalog + ScienceDirect listing]` and delete the phrase. The row is the rule, not the entry: add to CHARTER §13 that a note may carry `[UNVERIFIED]` for a *claim* it could not open, and may never carry an author list, year, volume or page range that was not read off a record (critic #7, F37) | todo | true | minutes | 제출 자료 (출처) |
| WFG-068 | P1 | infra | **The paper routine can do a backlog row's work but cannot mark it done, so a row it finishes stays `todo` and the next dev lap rediscovers it.** CHARTER §12 says the paper lap 「touches nothing outside `paper/` (plus its own report)」, which is the right isolation and also means `BACKLOG.md` is out of reach. WFG-064 is the first instance: the paper lap fixed both halves at `e28377c`, wrote it up under the row's own name, and left the row reading `todo`; critic #8 closed it by opening the two PNGs. Give the routine a write it can make — the cheapest is a committed `paper/BACKLOG_CLAIMS.md` the paper lap appends `{row, commit, what}` to and the next dev or critic lap drains — or state in CHARTER §12 that the paper lap names its completed rows in its report and the daily critic closes them. Either way the rule must be written down, because the failure mode is silent: a `todo` row that is already done costs a whole lap to rediscover (critic #8, F44) | todo | true | minutes | 데이터 해석 (재현) |
| WFG-016 | — | — | ~~AI ledger current~~ | **withdrawn(2026-09-04)** — author's instruction; organisers require no disclosure artifact (NH-008). Never started, nothing produced | false | — | — |
| WFG-036 | P0 | KCF | **Final product bundle** `release/kcf-finals-2026/`: `web/` whole (finals + console + field view), printables PDF, `README_KO.md` 10-line run recipe, `CITATION.cff`, `make finals-bundle` byte-identical rebuild; definition of done = `docs/auto/KCF_READINESS.md` R1–R11 | todo | true | two laps (v1 by 09-10, v2 by 09-14) | 구현 및 유용성 · 제출 자료 |
| WFG-037 | P0 | KCF | Booth recipe `docs/auto/finals/BOOTH_SETUP.md`: exact steps for the judged laptop (env, `make all-checks`, open `file://` with Wi-Fi off, key bindings, two USB copies, fallback if the laptop dies), plus NH-014 asking the author to run it once | todo | true | hours | 구현 및 유용성 |
| WFG-024 | P0 | infra | Re-key branch name and dates after WFG-023/022 (HANDOFF §5.1 → `auto/dev`; STATE/CHARTER dates; BACKLOG brief path) | blocked(WFG-022, WFG-023) | true, blocked(WFG-023) | hours | — |
| WFG-005 | P2 | science | Decision-level uncertainty (**revise**: demote to P2, blocked — needs the raw bundle and forward simulation; Mac-only; human-approved) | blocked(raw bundle, Mac-only; P2) | false in sandbox | — | — |
| WFG-006 | P2 | science | Wind-direction sensitivity (**revise**: demote to P2, blocked — forward simulation needs the raw bundle; Mac-only) | blocked(raw bundle, Mac-only; P2) | false in sandbox | — | — |
| WFG-008 | P3 | science | Ignition-likelihood layer (**revise**: park to P3 — pre-ignition risk forecasting is what 서식1 says the project is not; theme-drift risk) | parked(theme-drift risk; P3) | — | — | — |
| WFG-007 | P1 | KCF | Rehearsal aids + booth checklist (**revise**: `web/` is a directory, two USBs, affine drift on the booth laptop) | todo | true (print/laptop: human) | hours | 제출 자료 |
| WFG-009 | P1 | infra | Playwright smoke of `web/finals.html` (**revise**: `document.fonts.check` per family; package `web/` whole) | todo | true | one lap | 구현 및 유용성 |
| WFG-025 | P1 | science | Two clean single-variable sweeps: pre-movement delay (routing axis, 3 regions) and walking speed (vulnerability layer, 영덕) | todo | true (verify dry run first) | one to two laps | 설계와 방법론 (변수 통제) · 데이터 해석 |
| WFG-026 | P1 | KCF | Related-work table with Crossref-resolved DOIs only + one-panel differentiation from ISEF 2026 SFTD059T | todo | true | one lap | 설계와 방법론 (기존 연구와의 차별점) |
| WFG-027 | P1 | KCF | Schedule & roles timeline from `git log` (Korean; AI-assisted sessions disclosed pending WFG-022) | todo | true | hours | 설계와 방법론 (일정·역할) |
| WFG-010 | P1 | KCF | README Round-4 section + English abstract draft (**revise**: vocabulary and caveat rules) | todo | true | hours | 제출 자료 · 연구 목적 |
| WFG-028 | P1 | KCF | Two or three structured expert consultations (이장, 119 상황실, 사회복지사) + close firefighter §8 blanks | blocked(human) | **false** (agent drafts protocol) | hours each | 개발/연구 목적 · Q&A |
| WFG-029 | P1 | KCF | One recorded email send from a Shanghai-workable path (agent builds Gmail-API/OAuth adapter; student authorises once) | todo | partial | hours | 구현 및 유용성 · 제출 자료 |
| WFG-030 | P1 | infra | Report-number check: every number in `docs/auto/reports/*.md` and `JUDGE_QA.md` must grep to a registry key or artifact | todo | true | hours | 데이터 해석 (재현) |
| WFG-031 | P1 | infra | `CITATION.cff` with true fields (no fabricated dates) | todo | true | minutes | 제출 자료 (출처) |
| WFG-040 | P1 | infra | `scripts/build_numbers.py` overwrites the registry with 65 of its 278 entries — make it refuse, or make it merge (**renumbered** from a duplicate `WFG-036`, critic 20260903T1748Z) | todo | true | hours | 데이터 해석 (재현) |
| WFG-041 | P1 | infra | The lineage gate's ±2-line label window is satisfied by an unrelated keyword, so `JUDGE_QA.md:46` passes it | todo | true | hours | 데이터 해석 (재현) |
| WFG-042 | P1 | IEEE | A `verified` citation in `references.bib` can disagree with the paper at its URL, and `check_paper.py` cannot tell | todo | true | hours | 제출 자료 (출처) |
| WFG-043 | P0 | KCF | Source and register the 2025 fire's scale figures (deaths, burned area, homes) that open the README. **Rewritten by critic 20260903T2347Z (F16/F17/F18): the paragraph was rewritten at `12b8ac7` and is now wrong in the other direction — 45,157 ha stated for a chain that burned 99,289 ha, 영덕 8명 against this repository's own correction to 10, and eleven figures with no URL** | done(fbe71de) | true (author granted standing permission to source public data, NH-015 closure) | hours | 연구 목적 · 제출 자료 (출처) |
| WFG-038 | P1 | infra | The full suite reports two different skip counts on one commit and the gate is green for both — make the (collected, passed, skipped) triple a gate | todo | true | hours | 데이터 해석 (재현) |
| WFG-039 | P1 | infra | The test suite downloads an 8.4 MB (gzipped; 25.9 MB on disk) SRTM tile mid-run, so first-run and re-run pass/skip counts differ by six — make the download opt-in (**this is the cause of WFG-038's symptom**) | todo | true | hours | 데이터 해석 (재현) |
| WFG-044 | P1 | infra | `scripts/auto/report.py` has no `paper` kind, so the paper routine files its report as `manual` and overwrites `STATE.json` → `last_report_kind` with it (critic 20260903T1947Z) | todo | true | minutes | 데이터 해석 (재현) |
| WFG-045 | P1 | IEEE | `paper/manuscript.md` cites 21 works and has no `## References` section, and `check_paper.py` checks no section at all against CHARTER §12 (critic 20260903T1947Z) | todo | true | hours | 제출 자료 (출처) |
| WFG-046 | P0 | infra | Every lap pushes commits no gate has read: `gates.py` runs at step 5 and everything after it (the report, and any post-review fix) is unchecked, so `auto/dev` has gone red twice this way (`24751fa`, `8d1decf`). **Widened by critic 20260903T2147Z (F14):** not just the report. Make `report.py` gate its own prose AND add a `--assert-head` check that refuses a push when `.auto/gates.json` → `git_head` is not `HEAD` | done(509819d) | true | hours | 데이터 해석 (재현) |
| WFG-047 | P0 | infra | `in-progress` is written as a lock with no release, so a row a lap left unfinished is invisible to every later lap: WFG-021 (a)+(c) and WFG-016 are stranded, and `KCF_READINESS` R2 depends on WFG-021 (a) (critic 20260903T2147Z) | done(509819d) | true | minutes | 데이터 해석 (재현) |
| WFG-049 | P0 | infra | A commit that carries only unregistered prose is invisible to every gate this repository owns: `12b8ac7` rewrote the judge-facing README in two languages and closed three NEEDS_HUMAN entries with no report, no reviewer and no `STATE.json` update, and `--assert-head`, `report.py`'s prose gate and `make verify` all passed on it (critic 20260903T2347Z, F19) | done(2026-09-04 laptop lap: registry keys fire2025_*, check-readme-figures, --assert-reported) | true | hours | 데이터 해석 (재현) |
| WFG-048 | P1 | infra | The three FIRMS first-detection delays that `docs/detection_floor.md` §4 and §8 put beside the GK2A delays (+117 / +151 / +17 min, from `data/processed/detection/firms_first_detection.json` → `delay_h` 1.95 / 2.52 / 0.28) have no registry key, so the one comparison a judge is most likely to ask about is the one number on that page that `make verify` cannot re-derive (dev lap 20260903T2217Z, while writing WFG-021 a) | todo | true | hours | 데이터 해석 (재현) |
| WFG-050 | P1 | infra | The motivating-event figures are pinned by `tests/test_motivating_event_figures.py` against `docs/data_sources.md`, a sibling document the same lap wrote in the same commit — leakage patterns #3/#4/#5, named by the 2026-09-04T0017Z dev lap's own reviewer. Table A's rows carry bare news URLs whose content can change or vanish. Snapshot each cited page (sha256 + retrieval date, the way `docs/evidence/greenpeace_2026_survey.md` already does) and assert README <-> snapshot instead of README <-> sibling doc | todo | true | hours | 데이터 해석 (재현) · 제출 자료 (출처) |
| WFG-051 | **P0** | infra | The `fire2025_*` apparatus binds a figure's **value** to the registry and leaves its **attribution** free: `check_readme_figures.py` only asserts that `agency` / `as_of` / `scope` / `source_url` are non-empty, never that they agree with what the prose says. Three live disagreements: the registry calls 45,157 ha a 중앙재난안전대책본부 figure while `README.md:204-205` and `docs/data_sources.md:194` call it 산림청 (the cited 경향신문 article says 산림청, so the registry is the wrong one); the registry calls 사망 26명 a 중앙재난안전대책본부 count while `docs/data_sources.md:190` calls it 경상북도 재난안전대책본부; and `README.md:193-199` puts 사망 26명 under an 아시아경제 link that carries no death figure at all. Fix the artifact, give 26명 its own citation, and extend the gate to compare the README's inline link and the sources table's 출처 column against the registry's `agency` and `source_url` (critic #5, F23). **Raised P1 → P0 by critic #6 (F30): the disagreement has now propagated into `paper/manuscript.md:36-38`, which calls 26명 "the provincial disaster headquarters' count" — a third spelling — so the same figure now carries three different agencies across three judge-facing documents, and the README link a judge would click still carries no death figure** | todo | true | hours | 제출 자료 (출처) · 데이터 해석 (재현) |
| WFG-052 | P1 | infra | No gate reads judge-facing prose for *structural* damage, only for numbers: `d2f314d` left BOTH opening stanzas duplicated verbatim on consecutive lines (`**보호 대상**` and `**Motivating event**`), and they survived the eight commits since, a critic run that read that exact diff, `make verify`, `check_readme_figures.py` and 36 paragraph tests, because every one of them flattens or greps the paragraph and none looks at it as text. The 2026-09-04T0400Z dev lap removed the Korean twin, missed the English one, and its own reviewer found it — which is the row's point twice over. Both removed; that test now asserts each anchor appears exactly once. The general gate is still the row. Cheapest form: fail on two consecutive identical non-empty lines in `README.md` and `docs/*.md` | todo | true | minutes | 제출 자료 |
| WFG-053 | P0 | KCF | **The booth card, the T0 Q&A answer and the design doc's 평결 all say the satellite rang after the human call; this project's own paper says the measurement cannot say that.** Narrow every judge-facing document to the paper's wording (delays behind the *recorded occurrence time*, no ordering claim), keep the size floor, which is true either way. Agent-doable and needs nothing from the author: the paper already did it (critic #6, F27) | done(2026-09-04T0419Z) | true | one lap | 데이터 해석 · 제출 자료 (출처) · 구현 및 유용성 |
| WFG-054 | P0 | infra | `scripts/auto/decisions.py apply` appends the Gmail message id to `decisions_seen.json` even when `apply_one` recorded nothing, so an author reply naming an id the file does not carry is written nowhere and the message is never read again. Its own docstring promises the opposite (`recorded, as noted, never guessed at`). Record `seen` only on a real change, write unmapped lines to a committed place, and test both directions (critic #6, F28) | todo | true | hours | 데이터 해석 (재현) |
| WFG-055 | P1 | IEEE | `paper/check_paper.py` enforces a word proxy (7,479 of 7,500 used) for a constraint CHARTER §12 states in **pages**, measures no section against the §12 list, and the loop's own recount puts the built `.docx` nearer 21 pages than 20. Get one real page count out of the built document, re-derive the words-per-page constant from it, and add a section gate. Absorbs WFG-045 (critic #6, F29) | todo | true | one lap | 제출 자료 |
| WFG-056 | P1 | infra | `gates.py --assert-reported` reads `origin/auto/dev` at push time and writes nothing, so no later lap can audit whether a given push actually carried a report — which is the check the critic prompt asks be verified every day and the one thing in this repository that cannot be. Append `{utc, base, head, verdict}` to a committed ledger under `docs/auto/` on every run (critic #6, F32) | todo | true | hours | 데이터 해석 (재현) |
| WFG-057 | **P0** | infra | A question numbered `Q10a` is invisible to every test in `tests/test_judge_qa_bank.py`: `QUESTION_RE` matches `Q(\d+)`, so a lettered question escapes the tier-count anti-padding guard, the contiguity check and the 근거/없는 것 requirement. Four such questions now exist (Q10a, Q10b, and the three this lap added). Widen the pattern to accept a letter suffix and restate the three header counts in the same commit (critic #6, F34). **Raised P1 → P0 and the stated fix corrected by critic #8 (F43): widening the pattern for the letter suffix is not enough.** `QUESTION_RE` is `^\*\*Q(\d+) · (T[012])\.` and the escaping headers are `**Q10c · T1 (크리틱 #6).`, `**Q10d · T0 (크리틱 #7).` and `**Q34 · T2 (크리틱 #7).` — the **parenthetical between the tier and the period** defeats the pattern on its own, so `Q34`, which carries no letter at all, escapes too. Six questions are now invisible, not four. The reason this is P0: `JUDGE_QA.md:17-23` tells the student 「T0 (14개) — 이것만 완전히 외우십시오」, the file actually holds **38 questions and 15 T0s**, and the fifteenth T0 is **Q10d**, the entry whose whole job is to stop the student saying a sentence this repository cannot support. The student who obeys the bank's own drill plan memorises the fourteen and never reaches the guard | todo | true | minutes | 제출 자료 |
| WFG-058 | P1 | paper | Manuscript figures restyled to the look of Moreno et al. (2025), which the author chose on 2026-09-04: framed panels, panel letters, hairline bar edges, framed legends, a warm red / blue / grey palette. `paper/style.py` rewritten, `paper/make_figures.py` labels every multi-panel figure; rules in `docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md` | done (2026-09-04 laptop lap) | true | one lap | 제출 자료 |
| WFG-059 | P3 | science | Buildings as exposure, not fuel — a Korean BFM-lite **after the finals**: 건축물대장 (needs the author's API key) joined to 도로명주소 건물DB footprints → footprint fraction, structure-separation distance, construction era and structure type per cell; then an ablation in the leave-one-fire-out protocol. The FireDX pipeline the author supplied was read and deliberately not adopted before the freeze; the decision and the four reasons are in `docs/auto/knowledge/WUI_BUILDINGS_AS_FUEL.md` | todo (post-finals) | partly | days | 데이터 수집 · 연구 기여 |
| WFG-060 | P2 | paper | Study-area map of the six fires in the Moreno Fig. 1 style: DEM hillshade from data already in the repo, one graded circle per fire (size and colour by burned area, five-step legend), lat/lon graticule, scale bar, boxed legend. Offline build only, every burned-area figure from the registry | todo | true | one lap | 제출 자료 |
| WFG-061 | P1 | science | `docs/horizon_grounding.md` reads the KFS 산불통계 CSV's `발생일시` column as a 신고 시각 and cites no source for that reading, exactly as `docs/detection_floor.md` §1 did before WFG-053. The two are **different datasets** (public-portal CSV vs `fire_manifest.json`), so the claim that they "share the same weakness in the same data" was wrong and was withdrawn by the WFG-053 lap; the column's own provenance is still unchecked. Find what 산림청 says `발생일시` means in the 산불통계데이터 spec, or state that it is unknown. The 79.23 %/240-min horizon numbers do not move either way (dev lap 20260904T0419Z). **Widened by the WFG-017 lap's reviewer (2026-09-04): this is not doc-vs-nothing, it is doc-vs-artifact.** `data/processed/detection/kfs_containment_duration.json`'s own header `⚠_reference_time` states flatly 「`발생일시` is a REPORTED start time, not observed ignition. Every duration is report-to-containment」, and all four registry entries the finals screen reads (`kfs_cum_le_240_pct`, `kfs_n_usable_events`, `kfs_containment_median_min`, `kfs_area_ge100ha_median_min`) carry that caveat, as do `det_gk2a_delay_*_min`. So the artifact asserts what §2 says it could not confirm. The artifact is a committed record and is not edited (§3 rule 2); what this row must produce is either the upstream source (then annotate the entries) or a written statement that the assertion is unsourced. Until then judge-facing prose states BOTH and reads the distribution as 기록 → 진화 only | todo | true | hours | 데이터 해석 (재현) · 데이터 수집 |
| WFG-062 | P1 | infra | `tests/test_detection_ordering_is_not_claimed.py` gates ONE withdrawn sentence shape over FOUR named documents, and `scripts/check_forbidden.py`'s five `claim` rules are the only other sentence-level gate in the tree. Every other gate reads a value, which is critic #5's and critic #6's shared root objection two windows running. Generalise: a registry of withdrawn CLAIMS (id, banned spellings, the artifact that withdrew it, the pragma token) that any document can be checked against, so a fifth document asserting the ordering tomorrow is caught. Absorbs the per-row hand-rolled gates (dev lap 20260904T0419Z). **Critic #8 named the cheapest test of this row and the WFG-063 lap ran it (20260904T0820Z): 「if narrowing one sentence in three files and adding one gate closes WFG-063 and WFG-067, WFG-062 is the right generalisation」. The answer is stronger than that. WFG-063 alone took FIVE files — the fourth was `docs/SESSION19_REPORT.md`, a session report nobody had listed, which still carried the rank table and the primacy sentence unannotated — and it needed a SECOND hand-rolled claim family in the same test file, whose first draft caught six of nine mutations. There are now two claim families, six regex rules, two pragma-token vocabularies and two guard lists in one file named for only one of the claims. The next withdrawn claim makes it three.** | todo | true | one lap | 데이터 해석 (재현) · 제출 자료 |
| WFG-011 | P2 | ISEF | ISEF plan memo (**revise**: route-existence questions, SFTD base rate, age rule, hand-written documents) | todo | true | one lap | — |
| WFG-032 | P2 | science | Leak-free 영덕 fold + hindsight-oracle routing arm (agent writes the script; student runs on the Mac) | todo | partial | one lap + one Mac day | 데이터 해석 · IEEE Table V |
| WFG-033 | P2 | science | Coupling-ablation routing-only arms on committed hazard fields (fire-blind / static perimeter + buffer / spread_v2), three regions (absorbs WFG-012) | todo | true | two laps | 설계와 방법론 · 데이터 해석 |
| WFG-034 | P2 | science | Refuge-density decimation (100/75/50/25%, 20 seeds, 3 regions) — only after written approval in WFG-023 | blocked(approval in WFG-023) | true, blocked(approval) | two laps | 데이터 해석 · 창의성 |
| WFG-013 | P2 | science | Open building-footprint coverage check for 영덕 (keep) | todo | true | one lap | 데이터 수집 |
| WFG-014 | P3 | IEEE | Paper skeleton in `paper/` (**revise**: vocabulary, caveats, AI acknowledgment, no preprint before December) | done(0ff1b36) | true | weeks | — |
| WFG-035 | P3 | IEEE | Register every number the manuscript will cite; reconcile the two HGB means; per-fire/spatial-block CIs; new-ring IoU beside cumulative | todo | true | one lap | 데이터 해석 |
| WFG-015 | P3 | IEEE | Reproducibility package + Zenodo release checklist (keep; DOI minted by the student) | todo | true (release: human) | one lap | 데이터 해석 (재현) |

## Details

### WFG-001 — Clean-Linux green
Run `bash scripts/auto/bootstrap.sh` then `python scripts/auto/gates.py --mode full`
in the sandbox. Record skips with reasons (`--rs`). If a test needs a git-ignored
input, mark it `skipif` with the reason, never delete it. Compare the pass/skip
counts to the laptop baseline recorded in the kickoff report.

**Lap 20260903T0513Z (first cloud dev lap).** The sandbox half is green:
`1062 passed, 54 skipped, 0 failed, 0 errors` at `017c9ec`. It took two rounds.

The first full run was RED with 17 items, which resolved to exactly two causes,
neither of them a defect in the project's own code and neither touching an
artifact:

1. **`brotli` was declared nowhere.** `fonttools==4.63.0` is pinned, but its
   WOFF2 decoder needs the Brotli extension to open the vendored `.woff2`
   faces. Fixed upstream in `e1588b4` (`bootstrap.sh` installs it); that alone
   cleared all five `test_screen_checks` failures, 17 red → 12.
2. **Git-ignored inputs absent from a fresh clone, with guards that did not
   fire.** All 12 survivors. `data/raw/**` is ignored at `.gitignore:60`, so
   `firms_data/` never reaches a clone at all.
   - `test_photo_exif` (7, reported as ERRORS): the module-scoped `client`
     fixture builds a runner that opens `yeongdeok_2025_dem.tif`. No guard.
   - `test_osm_cache_isolation` (2): the guard read `if not d.exists(): skip`,
     but `data/cache/osm/yeongdeok_2025/` is **tracked** (it holds
     `vegetation.geojson`) while the four graphs in it are ignored — so the
     directory always exists and the skip never fired.
   - `test_baseline_freeze` (2) and `test_live_pipeline` (1): need the
     laptop-only acquisition manifests / detections CSV.

   All 12 now skip with a stated reason. Two deliberate scoping choices:
   `test_the_migrated_yeongdeok_cache_is_where_the_loader_looks` keeps its
   old-flat-path assertion running everywhere (it needs no ignored input), and
   `test_a_moved_artifact_is_actually_detected` runs its tampering assertions
   in every clone and skips only the final two, so the guard is still exercised
   in CI rather than blanket-skipped.

**Both halves of "done when" are now satisfied.** The CI half settled after the
push: `auto-gates` **run 8** on `c42287e` concluded `success` at 2026-09-03
05:17:52Z — the first green run this workflow has ever had. Before it, runs
1/2/3/5 were cancelled by the concurrency rule as pushes stacked, and runs 4 and
7 concluded `failure`; run 7 on `017c9ec` is the clean-machine confirmation that
the twelve guards were the remaining blocker.

**The count gap is explained, and it is benign.** The sandbox reports **1116**
test outcomes against the laptop baseline's **1120**
(1116 passed / 3 skipped / 1 xpassed). Cause:
`tests/test_empirical_interaction.py` calls `pytest.importorskip("xgboost")` at
**module level**, so without the optional `legacy` extra its **five** tests are
never collected and the module contributes one skip instead — 1115 collected + 1
module skip = 1116, and the shortfall of 4 is exactly those 5 tests minus the 1
skip. `xgboost` is deliberately not a core pin (`requirements.txt` keeps
`xgboost==3.2.0` commented; it lives in the `legacy` extra), so the sandbox is
behaving as designed and no test is silently lost.

While confirming that, a stale note in `requirements.txt` was corrected: it
warned that `test_lofo_holds_out_whole_fire` imports xgboost *without* a guard
and therefore ERRORS on a clean clone. The guard was added at
`tests/test_spread_v2_xgb.py:222` and it skips. The note now says so, and records
the module-level collection effect above.

**Lap 20260903T0534Z — the same two findings, reached independently, plus one
change.** This lap read `auto-gates` run
[33718108879](https://github.com/Sparkxt-0318/wildfireguardian/actions/runs/33718108879)
directly and diagnosed the count gap the same way, before seeing that the lap
above had already written both up; nothing above is superseded. What it adds:

- [`docs/clean_clone_gates.md`](../clean_clone_gates.md) — the standing artifact
  for this row: method, gate table, the 54 skips grouped by cause, the
  1,115 + 1 = 1,116 vs 1,120 arithmetic, and a caveats section saying what a
  green clean clone does NOT show (the 37 data-gated skips are exactly the tests
  that re-derive numbers from raw inputs, so it proves consistency, not
  reproduction).
- One test split. `test_weather_basis_is_derived_from_committed_data_not_a_literal`
  asserted both that the basis is *derived* from the git-ignored archive and that
  it is *never typed into the source*; a single `skipif` took the second out of
  every clean clone, which is exactly where hard-coding the date is the tempting
  fix. Now two tests, and the guard runs everywhere (+1 collected).
- `scripts/auto/report.py`'s backlog counter matched only a bare status word, so
  every row the loop had started or finished vanished from the counts in its own
  report.

⚠ **This lap and the one above overlapped almost entirely.** Both fetched
`auto/dev` at `017c9ec` and both fixed the same five tests. This one discarded
its duplicate (preserved at `auto/lap-b1989d5-superseded`, nothing deleted)
because the landed fixes are better: they keep the old-flat-path and tamper
assertions running in CI rather than blanket-skipping. Filed as **NH-007** —
the charter's "the later lap takes the next row" cannot work while a row is
claimed only by the commit a lap pushes at the end.


### WFG-022 · P0 · KCF · Five questions to the KCF 운영사무국 — human
- **What:** one call (070-5066-1963) or email (koreacodefair@gmail.com): (1) finals date — the student's notice says 10.18 with 10:30 judging start; https://www.kcf.or.kr/84/?bmode=view&idx=171991931 (2026-06-24) says 본선 10.24 (토) 김대중컨벤션센터, 결과 10.30; (2) the 참가부문 (애플리케이션/실생활 도구 vs SW 연구) this entry is registered under; (3) whether restating 기여 ② from "위험 시한 순 트리아지 목록" (서식1 line 13) to the per-home closure time `ingress_survival_time_min` is within 운영요강 p.9 (첫 제출 당시의 작품 목적·주제에 반하지 않는 범위); (4) how AI-assisted / autonomous-agent development must be disclosed given 심사개요 "대리(표절)작 판정 시 심사 제외 가능" and p.18 "허가받지 않은 제3자의 참여나 개입"; (5) what 제출 자료 is scored at the finals (기제출 서식2 only, poster, handouts) and the poster specification.
- **Rubric rows:** Pass/Fail (서류 구비, 대리작) and every scored row indirectly.
- **Effort:** hours. **agent_doable:** false (external contact).
- **Constraints:** CHARTER §6 (contacting anyone is human-only).
- **Done when:** NH-006 closed with the confirmed date; a new closed NH entry records the four other answers verbatim; `docs/auto/RUBRIC.md` "Which track applies" updated by the loop (WFG-024).

### WFG-023 · P0 · infra · Protect `Main`, ratify the branch, take the open decisions — human
- **What:** (a) GitHub → Settings → Branches: protect `Main` (require PR, require `auto-gates` status, block force-push); routines can push to any unprotected branch that carries only the owner's commits (https://code.claude.com/docs/en/routines), so this is the only real guard; (b) write one line ratifying `auto/dev` as the working branch (replaces `round3-dev` in HANDOFF §5.1); (c) decide in writing: which routing field the finals says — recommendation: canonical 414/42/2 (n = 458) with the reconciliation sheet — and whether the corrected-DEM LOFO (`spread_v2_lofo_dem_corrected.json`) ever replaces `spread_v2_lofo.json` — recommendation: not before the finals, keep as a separate lineage; (d) approve or veto the refuge-density decimation experiment (HANDOFF §4 says the user confirms before it starts); (e) close NH-001 (report-email secrets) and NH-002 (`@claude` app) either way.
- **Effort:** under an hour. **agent_doable:** false.
- **Done when:** `gh api repos/Sparkxt-0318/wildfireguardian/branches/Main/protection` returns 200; NH entries closed with the decisions; WFG-024 unblocked.

### WFG-018 · P0 · KCF · 제출본 대비 정본 reconciliation sheet as NEAR-labelled prose
<!-- forbidden-ok: 44× -->
- **What:** `docs/submission_reconciliation.md` (Korean, one printable page): for every number in the submitted 서식1/서식2 that the repo has since superseded, one row: submitted value (with its lineage and denominator) → current canonical value (with its artifact and commit) → why it moved → what did not change. Rows: 438/18/3 of 459 (`routing_demo.npz`, reverted-run field) → 414/42/2 of 458 (`routing_demo_canonical.npz`), and separately 440/17/3 of 460 (PHASE-2 flat/slope re-run) — never combined, no "N reclassified" (§5.24), 18/459 = 3.92% not 3.70%; 핵심 영역 241→244 (reverted field) vs core growth 249→1,036 cells on the canonical field; "DEM 경사 미적용" → applied at 60 m sampling (+26.6% traversal time, null on buckets); RF 0.920 ± 0.036 → 0.914 ± 0.044, GBM 0.889 ± 0.107 → 0.894 ± 0.092 (`ml_baselines.json`; note the committed headline 0.890 ± 0.107 is `spread_v2_lofo.json`, a different artifact); far-band 0.925 → 0.904 ± 0.100 (n = 3 t-CI 0.66–1.15) and corrected-DEM pooled far-band 0.8408 vs 0.877; PR-AUC/Brier "미산출" → AP 0.169 vs 0.0197, Brier 0.0183, ECE 0.0086; 6→24→66 (서식2 Fig. 3) is correct, README:731's "6 → 34" is a typo (`rescue_verify.json` `unreachable_delay_row_cutoff_0p7` = [6, 11, 24, 51, 66]); headline AUC lineage trained on the −497 m sea-filled DEM, corrected re-run +0.0048 not adopted; contribution ② restated 2026-08-10; the 44× severity-vs-direction ratio withdrawn (README/MODEL_CARD) — explain the reason in two sentences (six-feature sum vs single variable; ERA5 28 km). Add a 30-second spoken version of each row for the student.
- **Rubric rows:** 제출 자료 (논리적 구성), 데이터 해석.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** every retired literal must carry a `scripts/check_forbidden.py` NEAR label or the file fails `make check-forbidden`; do NOT register retired values in `NUMBERS.json` (§5.5, §5.20; `check_number_collisions.py` has no "submitted lineage" class); do NOT put reverted-field figures on `web/finals.html` unless the student changes gate policy in writing; do not edit the 서식 files (outside the repo). Every 영덕 rate carries the 32.6% caveat.
- **Done when:** the file exists in Korean, `make verify` and `make check-forbidden` pass, every current value in it greps to a `NUMBERS.json` key, and `docs/auto/JUDGE_QA.md` §0 links to it instead of duplicating the table.

**Lap 20260903T0653Z — done.** `docs/submission_reconciliation.md` (Korean, printable as
one double-sided sheet: eleven-row table on the front, 30-second spoken lines on the back),
`tests/test_submission_reconciliation.py` (4 tests), JUDGE_QA §0 repointed, `gates.py
--mode full` exit 0. Four things worth carrying forward:

1. **18 values registered** to make the done-when's "every current value greps to a key"
   true: `mlbase_*` ×6, `farband_*` ×4, `calib_*` ×4, `canonhaz_core_growth_pct`,
   `demcorr_mean_of_folds_delta` / `_pooled_delta`,
   `rescue_unreachable_delay_row_cutoff_0p7`. Registry 260 → 278. Retired values are NOT
   registered, per the constraint.
2. **A new arm, `A_reconciliation`**, declared in `docs/arm_protocol.json`. Registering
   already-computed values still needs an arm, and it cannot be `A` — that one is frozen
   and `check_arm_isolation` stops a new key claiming it.
3. **249 → 1,036 core cells cannot be registered.** Their key is `cells_ge_0.5_per_slice`
   and the registry's path resolver splits on `.`. The growth percentage registers; the
   counts are cited to the artifact and the limitation is stated in the sheet.
4. **A key name is part of the collision gate.** `farband_pooled_auc_committed` turned
   three unrelated lines red on the anchor words "committed / pooled / auc"; renaming it
   `farband_pooled_auc_precorrection` cleared them without editing a document.

### WFG-019 · P0 · science · Operating-point evidence package (incl. the threshold-guarantee negative result)
- **What:** new script `scripts/operating_point_evidence.py` reading `data/processed/spread_v2_lofo_oof_cells.csv.gz` (151,904 rows, 2,989 positives; per-fire positives 8/24/34/652/769/1,502) and `data/processed/oof_classification_metrics.json` (51-point PR curve). Compute and write `data/processed/operating_point/per_fire_recall.json`: per fire, `n_positive`, recall/FNR at the committed 0.3 (expected 1.000/1.000/1.000/0.977/0.959/0.544 for gangneung/hongseong/miryang/uiseong/uljin/yeongdeok — recompute, do not copy), max OOF probability per fire (expected 0.024/0.296/0.369 on the three small fires), pooled recall 0.138 and mean-of-folds 0.0867 cross-checked against the existing keys `oof_pooled_recall_at_operating_threshold` / `oof_mean_of_folds_recall_at_operating_threshold`. Then the nested leave-one-fire-out threshold-calibration table: for each held-out fire, λ chosen so the other five fires' OOF FNR ≤ 0.2 (a) without and (b) with the conformal finite-sample correction 1/(n+1) with n = 5 (Angelopoulos et al. 2024, https://proceedings.iclr.cc/paper_files/paper/2024/file/f3549ef9b5ff520a7e41ff3cc306ab2b-Paper-Conference.pdf), reporting held-out FNR and the fraction of all cells flagged (prevalence 1.97%). State the leakage caveat (OOF probabilities for fire g come from models that saw fire f). Write `docs/operating_point.md`: "AUC ranks, recall counts"; the per-step `advance_threshold` (forward simulation) vs cumulative-field `p_cut` (router) distinction so recall is not misread as the routing field's miss rate; and the conclusion as a negative result: no finite-sample FNR guarantee is possible at n = 6 and any bound-satisfying λ turns the hazard field into a near-blanket mask; the operating point stays a ranking-driven forward simulation and 0.3 stays unchanged. Append the same section to `docs/MODEL_CARD.md` (append only; no committed value edited). Draw the PR-curve figure with the 0.3 point and the F1-optimal 0.14 point to a NEW path (e.g. `docs/figures/auto/pr_curve_operating_point.png`; §5.3 forbids regenerating existing figures, not adding). One test with a synthetic OOF frame.
- **Rubric rows:** 데이터 수집·분석·해석 (수학·통계의 적절한 적용, 논리적 해석), 설계와 방법론.
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** new filenames only; register every number; the two R3 verdicts disagree on the exact λ and held-out FNR values (different calibration conventions) — state the convention used and let the artifact be the source; never adopt any λ.
- **Done when:** artifact + registered keys + doc + MODEL_CARD appendix + figure + test; `make verify` green; JUDGE_QA question 1 cites the new keys.

**Lap 20260903T1224Z — done.** Everything the row asked for exists and the whole
done-when clause holds. New: `scripts/operating_point_evidence.py`,
`data/processed/operating_point/per_fire_recall.json` (git-tracked; `.gitignore`
carries an explicit negation), `docs/operating_point.md` (Korean),
`docs/figures/auto/pr_curve_operating_point.png`, a `MODEL_CARD.md` appendix
(append-only, nothing above the rule edited), 17 registry entries on a new arm
`A_operating_point`, and `tests/test_operating_point_evidence.py` (10 tests, a
synthetic three-fire frame pinning the lambda convention).

Every expected value reproduced exactly from the committed OOF file: per-fire
FNR at 0.3 of 1.000/1.000/1.000/0.977/0.959/0.544 and ceiling probabilities
0.0241/0.296/0.369 on the three small fires. The script refuses to write if its
recomputed pooled and mean-of-folds recall disagree with Session 18's
`oof_classification_metrics.json`.

**The calibration result came out sharper than the row expected, and in a
different shape.** The row (and the brief) anticipated "any bound-satisfying
lambda turns the field into a near-blanket mask". That is true of the corrected
column only. The pair is the result: *without* the finite-sample term the bound
is met on the five calibration fires and then **broken on 3 of 6 held-out
fires** (worst 0.750), so naive calibration does not deliver what it claims;
*with* `1/(n+1)` = 0.167 — which at n = 5 calibration fires eats **83 % of a
0.20 budget** — the bound holds 6 of 6 and a feasible lambda flags **26–46 % of
all cells** against a 1.97 % prevalence. So: the guarantee or a usable field,
not both, at n = 6. Neither column is a valid guarantee (exchangeability breaks
twice; stated in the artifact, the doc and the MODEL_CARD appendix), which makes
the corrected column an optimistic bound — and even the optimistic version is
unusable, which is why the conclusion stands.

Convention stated as the row required (the two R3 verdicts differed here):
strict comparison, largest feasible lambda. No lambda was adopted; no default
moved. This lap's numbers therefore differ from both verdicts' lambda figures
and the artifact is the source.

Two gate lessons went to `docs/auto/MEMO.md`: a `pytest.skip` guard on a
git-TRACKED artifact hides a defect in a green summary line (one full-suite run
read 1,071/60 against three neighbours at 1,077/54, delta exactly the six tests
behind the guarded fixture; the fixture now asserts), and sibling registry keys
collide with each other when a 출처 table lists key and value on one line.

### WFG-002 · P0 · KCF · Judge Q&A bank v2 — revise
<!-- forbidden-ok: 44× -->
- **What:** `docs/auto/JUDGE_QA.md` grows to ≥ 30 questions grouped by judge type (software professor, disaster-response official, fire scientist, ML reviewer, statistician). Add the ten answers in `RESEARCH_BRIEF.md` §(c) plus: the 서식1 44× contradiction; the 기여 ② restatement (with the sentence to use only after WFG-022 is answered); "why walking routes when 84.5% drove" (from WFG-020); "what did you build yourself" (from `docs/auto/CHARTER.md` §9 and `ROUTINE_PROMPTS.md`); "is LOFO honest when 영덕 trains on 의성·안동's same-week rows"; "are any refuges designated 대피소" (OSM POIs; national shelter file not yet cross-checked — NH item). Purge: "10–14 s" (say about 25 s, HANDOFF §9), "five fabricated citations" (§4-B is five instructions carrying non-existent findings), "seven times 영덕's" (24.73/9.17 = 2.7×), "every fire we could test" (3 of 6; 영덕 excluded), the "40 minutes 안동→영덕" factoid, "Li et al. 2019", "Ronchi et al. 2021", "Lee et al. KJRS 2025" (Sung et al.). Each answer: one sentence, artifact path or registry key, "what does not exist" line, and a DRAFT label (the student rewrites in their own words).
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** no number not in `NUMBERS.json` or a committed artifact; `check_number_collisions.py --report` clean (the 24.73% share must stay marked as its own quantity, commit 953eb6c); Korean.
- **Done when:** ≥ 30 questions; a grep for the purged strings returns nothing; the critic lap's drill finds no P0 question without a file; the student has been told which answers are drafts.

**Lap 20260903T1536Z — done.** `docs/auto/JUDGE_QA.md` is now a **33-question Korean
bank** grouped by judge type (ML·통계 8, 산불 과학자 7, 재난대응 실무자 7, 소프트웨어 교수 6,
출처·규정·AI 5) and **tiered** T0 ×14 / T1 ×13 / T2 ×6 with a drill table in §6. Every
answer carries a `근거:` line (path or registry key) and a `없는 것:` line.
`tests/test_judge_qa_bank.py` (18 tests) gates it; `gates.py --mode full` exit 0
(1,106 passed / 54 skipped). Four things worth carrying forward:

1. **The count was the wrong done-when, and the fix was tiers plus tests.** A 30-answer
   document is more for the student to explain, not less — the opposite of CHARTER §9.
   Two of the three done-when clauses are now mechanical rather than the critic's
   opinion: `test_every_t0_question_points_at_something_that_exists` ("no P0 question
   without a file") and `test_the_stated_tier_counts_match_the_tags` (the anti-padding
   guard — adding a question forces the header's numbers to move).
2. **`test_every_registry_key_named_in_the_bank_exists`** is the strongest one: all 66
   backticked key-candidates on 근거 lines resolve in `docs/NUMBERS.json`. A key that
   reads plausibly and does not exist is HANDOFF §4-B's class and nothing else catches it.
3. **A number inherited from v1 had no source.** "46 snapped to the network" (beside the
   real `mr_yeongdeok_shelter_pois` = 50) appears nowhere in the tree; the only "46개" in
   the docs is `global_portability.md`'s *missed*-POI count. Replaced with
   `docs/multi_region.md`'s committed tag breakdown, which answers the judge's question
   better: 33 `leisure=park` + 17 `amenity=shelter` of which 16 are `shelter_type=gazebo`,
   and `amenity=community_centre` = 0 in two of three regions.
4. **The purge list must be derived, not retyped.** The independent reviewer blocked: the
   hand-copied `PURGED` dict had dropped the 40-minute 안동→영덕 factoid — the one item on
   the list the research brief marks "(no source)", i.e. the fabricated event rather than
   a superseded number — while the report claimed it was gated. Fixed with regexes (the
   literal "40분" is a substring of the legitimate "240분") plus
   `test_the_purge_list_covers_what_the_row_actually_ordered`, which parses the quoted
   phrases out of `RESEARCH_BRIEF_2026-09-03.md` and `BACKLOG_PROPOSAL_2026-09-03.md` and
   asserts each is covered. Both new gates confirmed by mutation.

Left for WFG-020: the Greenpeace survey figures in Q17 are labelled 「미등록」 in the
document itself, with the instruction to cite the report by name at the booth rather than
present them as repository-derived, until that row registers them with a sha256.

### WFG-004 · P0 · KCF · SSOT sweep — revise
- **What:** as written, plus: fix `README.md:731` "6 → 34" to the [6, 11, 24, 51, 66] row from `rescue_verify.json` (registered `rescue_unreachable_count` covers 24; register the delay row if not already); reconcile `docs/fold_sizes.md` ("pooled AUC is the primary indicator") with `docs/NUMBERS.json`'s note ("MEAN-OF-FOLDS, not pooled … never present one as the other") — one statement of which is primary, annotated in both; confirm README lines 197/494 say SFTD (done at 30ed00a); annotate the two HGB means (0.890 ± 0.107 in `spread_v2_lofo.json` vs 0.894 ± 0.092 in `ml_baselines.json`) with why they differ — **answered by WFG-018**: `ml_baselines.json`'s `hist_gbm` row IS the corrected-DEM lineage (it equals that file's own `dem_corrected_reference.mean_of_folds`), so they are two lineages, not two readings of one; both are now registered (`mlbase_hgb_mean_of_folds_auc`, `lofo_mean_of_folds_auc`) and `docs/submission_reconciliation.md` §"헷갈리기 쉬운 세 지점" states it. **Found by the WFG-018 lap, still open, not fixed there:** `docs/HANDOFF_ROUND3.md` §1.3 says the 의성·안동 time-aware-only share is "nearly **seven times** Yeongdeok's" — that ratio is 24.73/3.70 = 6.7 on the RETIRED share; against the canonical 9.17 % it is 2.7×. The same deprecated phrasing sits in `docs/auto/JUDGE_QA.md` Q7 (already on WFG-002's purge list). HANDOFF is not, so fix it here.
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** annotate, never delete; README Round-2 section untouched; `make verify` after every prose edit.
- **Done when:** `check_number_collisions.py --report` shows 0 unmarked hits; an `ssotize` audit report is committed listing every quantity with its single home.

**Lap 20260903T1622Z — done.** `docs/ssot_audit_2026-09-03.md` is the audit report;
`make verify` exit 0 (collisions 0 unmarked); `tests/test_rescue_lineage_ssot.py`
(6 tests) is the new gate. Registry 295 → 296. Four things worth carrying forward,
two of which contradict this row as written:

1. **"README:731 is a typo" was false, and the row inherited the error.** `6 → 34`
   is the real bracket of the superseded pre-flip **452-series** baseline
   (`data/processed/rescue_baseline_synthetic/rescue_verify.json` →
   `[6, 15, 20, 25, 34]`, superseded N = 452). The defect was a **lineage mix**: that value
   sat in a paragraph whose other figures (143 origins, 6.12 → 1.71) are
   439-series. `docs/rescue_routing.md` (do-not-cite banner, superseded N = 452) and
   `docs/REPORT_ROUND2_P1.md` ("synthetic lattice" vs "real roads") were **right
   all along** — exactly two documents broke the rule, and one of them was
   WFG-018's own reconciliation sheet, which had hardened the typo theory into
   「34는 어느 산출물에도 없습니다」 plus a spoken booth line. Corrected in all four
   places, including the two research files that carried the misdiagnosis.
2. **The row's second premise was also wrong, and the real conflict is sharper.**
   `docs/fold_sizes.md` and `docs/NUMBERS.json` do **not** disagree — both say
   pooled AUC is primary. The contradiction is `docs/MODEL_CARD.md`, which calls
   pooling "**not** the generalization estimate". Both are right about different
   questions (discrimination over the evidence vs generalization to an unseen
   fire); §3 of the audit is now the single home for that, and both files point at
   it. Found while fixing it: **the metric three documents call primary had no
   registry key at all** — pooled 0.905 lived only in prose and inside other
   entries' caveat strings, while the non-primary mean-of-folds was the registered
   headline. Now `lofo_rowweighted_pooled_auc` on new arm `A_ssot`. **No headline
   moved**; which metric leads is the author's call (CHARTER §6).
3. **HANDOFF's "nearly seven times" was self-contradicting.** Both occurrences sat
   two lines below the canonical shares they contradicted: 24.73 / 9.17 = **2.7×**,
   while 6.7× is 24.73 / **3.70** on the retired share. Direction unchanged.
4. **The collision gate structurally cannot see this failure class** and was green
   over README:731 at this lap's baseline. Hence the lineage test, which found two
   more instances the moment it was switched on — and two further ones
   (`BACKLOG_PROPOSAL_2026-09-03.md`, `results_rescue_draft.md`) after the
   independent reviewer showed the first version was far weaker than described:
   its banner exemption let 15 files through on an incidental word, and its label
   list accepted bare 이전/정본. Now a named 2-file ratchet with reasons.
   Generalising it beyond this one quantity is WFG-030's job, not done here.

### WFG-039 · P1 · infra · The suite's own counts depend on whether it has run before
> **This answers the open question in WFG-038.** That row recorded the same
> six-test signature (1,158 outcomes both times, six moving between passed and
> skipped, ALL GREEN printed for both) and said plainly: "The identity of the
> six is open." They are `test_srtm_dem.py` ×4 plus
> `test_validation_robustness.py:57` and `test_validation_session3.py:171`, all
> guarded on `data/raw/dem/srtm/N36E129.hgt`. WFG-038's ruled-out hypothesis
> (`data/cache/*.nc`) was the wrong cache. Both rows should be worked together:
> WFG-038 makes the drift visible, WFG-039 removes its cause.
- **What:** `tests/test_srtm_dem.py` documents that if `data/raw/dem/srtm/N36E129.hgt`
  is absent "the network-download step in `data_io.raster._download_srtm_tile` will
  fetch" it — and something in the suite does, from
  `elevation-tiles-prod.s3.amazonaws.com`, 8,473,868 bytes gzipped and 25,934,402 on disk, during the run. The path is
  git-ignored, so in a fresh clone six tests skip on the first run
  (`test_srtm_dem.py` ×4, `test_validation_robustness.py:57`,
  `test_validation_session3.py:171`) and pass on every run after it. Measured this
  lap: 1,088 passed / 60 skipped on the first `gates.py --mode full`, then
  1,094 / 54 on three consecutive full runs, with total outcomes 1,148 in all four.
- **Why it matters:** (a) every suite count this project has recorded is an
  unlabelled mixture of first-run and re-run readings, so cross-lap count
  comparisons — the check the loop uses to prove no test was lost — have been
  comparing different quantities; (b) an unattended loop and the `auto-gates` runner
  make a live network fetch nobody declared, which contradicts NH-004's "the loop
  works from committed snapshots"; (c) on the booth laptop with Wi-Fi off (the
  finals condition, R3) those six will skip, and nobody has recorded that as
  expected.
- **Options:** make the download explicit — an opt-in marker or env flag, default
  off, so a clean run skips deterministically and states why; or vendor the tile as
  a snapshot if its licence allows. Do **not** delete the tests.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** no committed artifact regenerated; `data/raw/**` stays
  git-ignored; the six tests keep their assertions (CHARTER §3.7, never delete).
- **Done when:** two consecutive full runs in a fresh clone report identical
  pass/skip counts; the expected clean-clone count is written down with the word
  FIRST-RUN or RE-RUN beside it; `docs/clean_clone_gates.md` updated.

### WFG-020 · P0 · KCF · Greenpeace 2026 survivor survey as evidence + the "85% drove" answer
- **What:** fetch the Greenpeace Korea 2025 영남 초대형 산불 피해 실태조사 최종보고서 (2026-03) PDF (URL in `RESEARCH_BRIEF.md` §(c) Q5); record its sha256 and the quoted figures with table/page references in `docs/evidence/greenpeace_2026_survey.md`: n = 300 (296–299 answering), 63.9% aged 60–79 and 17.9% ≥ 80, 90.0% evacuated (영덕 98.0%), car 84.5% (246/291), foot 3.1% (9), boat 2.7% (8), own car 60.1% of 278 car users, neighbour ~17%, relatives 15.1%, 재난문자 received 62.3% (영덕 48.0%), 마을방송+주민 237 vs 문자 112 mentions, 87% felt life threatened, 영덕 36% living alone, 영덕 foot 1.0% / boat 8.2%, 영덕 deaths 10 (mean age 84). If `scripts/build_numbers.py` supports literal/evidence entries, register them as such; otherwise keep them as documented literals with the sha256. Write the one-paragraph answer: the walking layer is a classifier for who cannot self-evacuate feeding the rescue layer and the 이장/마을방송 channel the survey shows worked; consistent with 서식1 §1's own question. Explicitly do NOT present "40% no own car" as a bracket on the 0.30 immobility rate (car-less ≠ immobile; 60.1% is a share of car users); the immobility answer remains 서식1 §4's f = 0.15/0.30/0.45 sensitivity. State survivor bias.
- **Effort:** hours. **agent_doable:** true if the PDF is reachable through the sandbox proxy (greenpeace.org is not on the trusted allowlist — UNVERIFIED); fallback: NEEDS_HUMAN asking the student to drop the PDF under `data/raw/evidence/` (the scratchpad copy `research/greenpeace_2025.txt` is a text extraction, not the PDF).
- **Constraints:** no number derived beyond the quoted ones; the KCF purpose is unchanged.
- **Done when:** evidence doc with sha256 exists; JUDGE_QA carries the answer with the 영덕-specific figures; `make verify` green.

**Lap 20260903T1821Z — done.** The PDF was reachable from the sandbox (HTTP 200,
3,406,169 bytes), so the row's NEEDS_HUMAN fallback was not used. Everything the
done-when asked for exists: `docs/evidence/greenpeace_2026_survey.md` (Korean, with
the sha256), JUDGE_QA Q17 carrying the 영덕-specific figures, and `make verify` green.
`gates.py --mode full` exit 0 (1,128 passed / 54 skipped, RE-RUN). Five things worth
carrying forward.

1. **The row's own figures had never been checked against the report.** They reached
   the repository through a scratchpad text extraction that no longer exists in the
   tree. Writing them down beside the PDF's sha256 would have produced a number that
   reads as sourced while the checksum authenticates the PDF and not the
   transcription — HANDOFF §4-B's class wearing the costume of provenance. So
   `scripts/extract_survey_evidence.py` does the transcription: digest first, then
   parse the report's own answer tables, then refuse to write unless the parse agrees
   with both the claimed value and the table's internal arithmetic. Both refusals
   confirmed by mutation.
2. **Reading the source changed three claims, none of them in the row.** The sample is
   임의·유의·눈덩이표집, so no interval belongs on any of these figures and the report
   asks to be read as 탐색적 자료; 「전체」 is a 100/100/100 equal allocation, not a
   영남-wide rate; and the 영덕 death toll (10, mean age 84) is the report re-citing
   영덕군's notice (p.9 fn.2), not a survey finding — it lives under
   `secondary_citation` so it cannot be read as one.
3. **Two things the repository had already written about this survey were wrong**, both
   in `research/sweeps_2026-09-03/R3_science_gaps.md`: "the 8 Yeongdeok dead" (it is
   10), and "≈40 % had no own car" offered as an empirical bracket on the 0.30
   immobility rate — the exact misreading this row was written to forbid. 60.1 % is a
   share of the 278 who evacuated *by vehicle*. Both annotated in place, not deleted.
   Also: neighbour's car is 16.5 %, not the "~17 %" the row carried.
4. **The figures are deliberately NOT in `docs/NUMBERS.json`.** No literal/evidence
   check kind exists (`json_path` / `expression` / `file_sha256`), so the row's own
   fallback applies. Registering someone else's measurement under a schema meaning
   "this project derived this from its own artifact" would buy the appearance of
   verification and lose the provenance. `test_the_survey_figures_did_not_leak_into
   _the_registry` pins the decision so a reversal must be deliberate.
5. **The anti-drift test is weaker than its name, and says so.** It checks a prose
   figure against the set of ALL table cells, not the table it cites: mutating 영덕's
   48.0 % to 47.0 % does not fail it, because 47.0 is a real cell elsewhere (표 1-5
   전체 '1명'). It does fire on a value in no table. The limitation is written into the
   docstring with the mutation that demonstrates it rather than left implied.

### WFG-021 · P0 · KCF · Detection-floor panel + tests for the GK2A detector
- **What:** (a) a finals card / Q&A block that states Session 19 exactly as recorded in `docs/detection_floor.md` §4, §9–10: reference = report time; 의성·안동 +22 min (FIRMS +117), 강릉 2023 +34 (FIRMS +151), 홍성 2023 +64 (FIRMS +17); 영덕 2025 excluded as confounded by the 의성 fire's background ring; 2022 fires predate the archive; false-alarm control 0/709 steps; conclusion: 사람 신고 > GK2A > FIRMS, the `manual` trigger is primary, "GK2A buys time" is not claimed. Registry keys: `det_gk2a_delay_uiseong_andong_min`, `det_gk2a_delay_gangneung_2023_min`, `det_gk2a_delay_hongseong_2023_min`, `det_gk2a_yeongdeok_best_delta_k`. (b) Unit tests for `src/wildfireguardian/detection/gk2a.py` (SESSION19 item 11: "새 코드에 테스트가 하나도 없습니다") using a tiny synthetic granule fixture: bit-width/units checks, the K = 4 contextual rule, the 15 km target / 30–80 km ring geometry, and a regression pin on `data/processed/detection/gk2a_detection_floor.json` values. (c) SESSION19 items 10 (FD-vs-LA cadence check) and 12 (cross-fire background contamination for 강릉/홍성) only if the needed intermediates are committed under `data/processed/detection/`; otherwise file a NEEDS_HUMAN (NOAA S3 is not reachable from the sandbox proxy).
- **Effort:** one lap. **agent_doable:** true for (a)(b); (c) conditional.
- **2026-09-03T2017Z, and it changes (c).** (b) is `done(f5f8498)`; (a) is not started.
  The independent reviewer of this lap disproved the row's own premise that
  "NOAA S3 is not reachable from the sandbox proxy": an anonymous HTTPS GET of
  `AMI/L1B/LA/202503/22/02/gk2a_ami_le1b_sw038_la020ge_202503220224.nc` returns
  200 and 458,172 bytes, and `read_granule` decodes it (14 valid bits, gain
  -0.00108296517282724, BT median 286.69 K). **(c) is therefore agent-doable**,
  and so is any future arm that needs the archive. It stays out of the default
  test run for WFG-039's reason, not for a reachability reason: the opt-in
  switch is `WFG_GK2A_NETWORK_TESTS=1`.
- **Constraints:** never say "every fire" (3 of 6); never rewrite the KMA-key direction experiment (`docs/gk2a_direction_experiment.md`) as a trigger item; the confabulated "1.28 ± 0.79 km" figure must not appear.
- **Done when:** tests exist and pass in the sandbox; the card text is in `docs/auto/finals/` and JUDGE_QA; registry keys cited.
- **2026-09-03T2217Z dev lap — (a) is done, and the row goes back to `todo` for (c).**
  `docs/auto/finals/DETECTION_FLOOR_CARD.md` states Session 19 as recorded: the three
  GK2A delays, the 영덕 교란 classification with the four numbers that justify it, the
  0-of-709 false-alarm **bound**, the 0.1939 ha size floor, the 신고 > GK2A > FIRMS
  priority, and an explicit "not claimed: GK2A buys time". `JUDGE_QA.md` gains Q10a
  (why 영덕 is excluded rather than counted as a miss) and Q10b (the false alarm rate is
  a bound, not 0 %). `tests/test_detection_floor_card.py` (17 tests) reads every figure
  on the card back out of `docs/NUMBERS.json`, binds each fire's delay inside its own
  table row so a swapped attribution fails, and keeps a tripwire over any new bare digit
  (a hand-maintained escape list, which the file itself says enforces nothing about the
  numbers already on it). **The FIRMS values named in this row's `What` were deliberately
  NOT copied onto the card: they are unregistered** (WFG-048), and CHARTER §3 rule 3
  says a number you cannot register you do not write. The card points at
  `docs/detection_floor.md` §8 instead.
- **(c) is still not attempted, and the reason is time, not reachability.** SESSION19
  items 10 and 12 need granules fetched from the NOAA GK2A archive at run time; the
  needed intermediates are not committed under `data/processed/detection/`. The 2017Z
  reviewer established the archive IS reachable anonymously, so this is agent-doable in
  a lap that budgets the download. It stays out of the default suite for WFG-039's
  reason (`WFG_GK2A_NETWORK_TESTS=1`).

### WFG-017 · P0 · KCF · `web/finals.html` refresh v2
- **What:** the committed screen was built 2026-08-15 at `c22ee5d9` and carries no Session 19/20/22 content. Add EVIDENCE/RELIABILITY cards, each with a 「근거」 pointer: operating point (WFG-019: PR curve, recall 0.138/0.0867, three folds at TP = 0 with `n_positive` shown so it reads as prevalence); detection floor (WFG-021); horizon grounding (Session 20: 79.23% of 2,008 fires contained ≤ 240 min; ≥ 100 ha median 4,025 min; `docs/horizon_grounding.md`); refuge placement (Session 22: one refuge covers 20/24 failing OSM-building "households", two cover 24/24 — with all three red caveats: OSM 124-building proxy, reachability-not-safety objective, 0/120 survival-filter events, counts 잠정 pending footprints); the reconciliation sheet as a RELIABILITY card only in the NEAR-labelled prose form permitted by WFG-018's constraints. Rebuild with `scripts/build_finals.py --verify` so the SYSTEM INTEGRITY panel records the gates; run `scripts/check_screen_assets.py web/finals.html` and the 17 tests in `tests/test_finals_screen.py`. No em-dashes (font subset). Region literals forbidden in the template.
- **Effort:** one lap. **agent_doable:** true — the sandbox has the geospatial stack via pip; if `build_finals.py` fails on a missing git-ignored input, emit the card payload as JSON under `docs/auto/finals/` with instructions and file a NEEDS_HUMAN for the student to run `make finals` locally.
- **Constraints:** `docs/finals_demo_plan.md` §1 (offline gate strict; no `fetch(`, no external URL); §5.19 caveat on every 영덕 absolute; never put reverted-field numbers on the screen; `web/finals.html` references `web/assets/fonts/` — do not inline fonts (size) and do not break the paths.
- **Done when:** rebuilt file with `built_at_commit` on `auto/dev`, gate panel showing the gates ran, `check_screen_assets` and the 17 tests green, a screenshot per act attached to the report.

**Lap 20260904T0630Z — done(a562045).** Every clause of the done-when holds, and the
row's own headline finding is that **the screen rebuilds in this sandbox in 10
seconds** — critic #7's root objection was that the cost of the first attempt was
unknown, and it is now known and small. The fallback the row provided (emit card
payloads as JSON, file a NEEDS_HUMAN, ask the student to run `make finals`) was not
needed: `build_finals.py` needs nothing git-ignored.

Shipped: four EVIDENCE cards (운영점 · 탐지 바닥 · 240분 지평 · 대피 지점 배치) and one
RELIABILITY card (제출본과 정본), each with a 근거 provenance block and its own caveat
line; 23 registry keys added to `REGISTRY_KEYS` (18 → 41); a new `evidence_v2()` payload for the
four structural facts a single key cannot hold; `docs/finals_screen_v2.md`;
`tests/test_finals_screen.py` 17 → 26. Four things worth carrying forward:

1. **Two claim defects were caught by rendering the page, not by the suite.** The
   operating-point card said 「나머지 폴드의 미검출률은 0.544~1.000」 while 1.000 is the
   value of the three folds that clause had just excluded. Every binding under it was
   green. The other is preventive: the detection card is written in **WFG-063's
   post-fix form ahead of that row** — the size floor rules the satellite OUT and the
   card says so, and says that which source should be primary was not measured.
2. **A second, spelling-free claim gate exists for this file.**
   `test_every_trigger_priority_sentence_on_the_screen_is_a_negation` requires any line
   naming both a priority word and a trigger source to carry a negation. Mutation-tested
   against three phrasings absent from the tree; the spelling gate missed all three and
   this one caught all three. It reads one file, which is why **WFG-062** stays open.
3. **Two documents called the KFS CSV's reference time a report time**
   (`horizon_grounding.md:106`, `JUDGE_QA.md:242`), contradicting `horizon_grounding.md`
   §2's own warning box thirty lines above. Corrected with a dated note; no number
   moved; the column's provenance is still **WFG-061**. `SESSION20_REPORT.md` keeps the
   old clause as a record.
4. **`JUDGE_QA.md:240` was deliberately not touched.** It is WFG-063's row across four
   documents, and fixing one clause of a two-clause sentence is the failure critic #6
   and #7 both named. It is the next row.

### WFG-003 · P0 · KCF · Finals screen audit + 5-minute demo script — keep
- As in `docs/auto/BACKLOG.md`, run **after** WFG-017 so the mapping table covers the new cards. The script follows `docs/FINALS_DEMO.md`'s four acts and adds one interruption sentence per judge type; it says "about 25 seconds" for trigger→dispatch.
- **Done when:** `docs/auto/DEMO_SCRIPT_5MIN.md` exists; every on-screen figure maps to a registry key; `check_screen_assets` green.

### WFG-016 · WITHDRAWN 2026-09-04 · ~~ISEF · AI ledger current~~
- **Withdrawn at the author's instruction (2026-09-04).** The organisers confirmed no AI-disclosure artifact is required for this entry (NH-008), and the author directed that `docs/auto/AI_DISCLOSURE.md` be deleted rather than re-scoped to ISEF/IEEE. The row is withdrawn, not done: nothing was produced. If an ISEF Form 2A or an IEEE acknowledgment is needed later, the underlying record still exists in git — `git log --grep='Co-Authored-By: Claude'`, `docs/auto/ROUTINE_PROMPTS.md` and `docs/auto/reports/` — and CHARTER §9 keeps the practices that make it reconstructible.
- **Effort:** hours. **agent_doable:** true. **Done when:** the three files agree with `git log`; the critic lap finds no undisclosed agent-authored file.

### WFG-024 · P0 · infra · Re-key branch and dates after the human answers — blocked(WFG-022, WFG-023)
- **What:** `ssotize` HANDOFF §5.1 from `round3-dev` to `auto/dev` (annotate, do not delete the history); update `docs/auto/STATE.json`, `CHARTER.md` §1 and `BACKLOG.md` priorities to the confirmed finals date (freeze 10-10 for 10.18, 10-16 for 10.24); update `RUBRIC.md` "Which track applies" with the registered 참가부문; fix the dangling reference `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md` by placing this brief there.
- **Effort:** hours. **agent_doable:** true once unblocked. **Done when:** no file on `auto/dev` names `round3-dev` as the working branch; STATE/CHARTER/BACKLOG dates agree; the brief path resolves.

### WFG-005 / WFG-006 · revise → P2, blocked(NH: raw bundle)
- **Why:** both require `spread_v2/forward_sim.py` on perturbed inputs; `scripts/run_forward_sim_region.py` rebuilds features from `data/raw/firms_data/` (git-ignored, absent in every clone). They are Mac-only. Also: an unattended loop registering new headline-adjacent numbers is the HANDOFF §4-B failure mode; per the R8 verdict these stay human-approved. Re-scope after the finals: the agent writes the scripts and tests against synthetic fields; the student runs them on the Mac; results are new arms with the 32.6% caveat. WFG-006 must state what ERA5's 28 km grid cannot resolve and never reinstate the withdrawn ratio.

### WFG-008 · revise → P3, parked
- **Why:** the ignition-likelihood (pre-ignition risk) layer contradicts 서식1's framing ("확산 예측 자체가 아니라 그 위에 세운 두 계층"; the existing system answers 「이 행정구역에 산불이 날 위험이 높은가」) — a theme-drift risk under 운영요강 p.9. Keep off every finals artifact. Revisit only after the ISEF selection with a written purpose check.

### WFG-007 · P1 · KCF · Rehearsal aids + booth checklist — revise
- **What:** `docs/auto/finals/`: printable A4 evidence sheet (headline numbers with sources and caveats), the reconciliation sheet (WFG-018), related-work table (WFG-026), Q&A cards (WFG-002), the 29 dispatch A4 sheets and 마을방송 script from `outputs/dispatch*`; booth checklist: copy `web/` **whole** (finals.html references `web/assets/fonts/*.woff2`; there are no data-URI fonts) to two USBs, open via `file://` with Wi-Fi off, key bindings G/R/Esc, HDMI/USB-C adapter, power strip, fallback laptop; fix the booth laptop's `wfg311` env (affine 2.4.0 → 3.0.1) so `make all-checks` is green on the judged machine; poster to the 사무국 spec (no asset in the repo).
- **Effort:** hours. **agent_doable:** true for the files; printing, laptop and poster are the student's.
- **Done when:** the files exist and a PDF is built by a script; the checklist has been ticked by the student once with the screen opened offline.

### WFG-009 · P1 · infra · Playwright smoke — revise
- **What:** `tests/e2e/finals.spec.ts` (Node, outside pytest): open `file://…/web/finals.html`, abort every non-`file://` request, assert no `pageerror`/console error, assert each `@font-face` family loaded with `document.fonts.check('12px "IBM Plex Sans KR"')` etc. (not `document.fonts.status`, which reports 'loaded' even when every face errored), advance the four acts, screenshot each; CI job installs `fonts-nanum fonts-noto-cjk` so screenshots have no tofu; upload screenshots as artifacts. Package check: the job copies only `web/` to a temp dir and runs from there, proving the directory is self-contained.
- **Effort:** one lap. **agent_doable:** true. **Constraints:** headless chromium; no change to the screen or to `check_screen_assets.py`. **Done when:** `auto-gates.yml` job `finals-smoke` green with 4 screenshots.

### WFG-025 · P1 · science · Two clean single-variable sweeps
- **What:** (a) pre-movement delay 0/5/10/20/30 min added to the walking departure on the 459-series routing axis for 의성·안동 and 울진·삼척 via `scripts/run_multi_region_routing.py` (new `--pre_movement_min` flag, new output filenames `real_roads_real_hazard_premove_<region>.json`), and for 영덕 via a new runner or an explicit new `--out` on `scripts/run_yeongdeok_canonical_routing.py` (its default writes only the protected canonical file; `run_multi_region_routing.py` refuses `yeongdeok_2025`, §5.18); report how `no_safe_route` and FA-only move, with OSM-completeness covariates beside every cross-region number (§5.7/§5.12) and the 32.6% caveat on 영덕. (b) walking speed 0.5–1.2 m/s (default 0.7) on the vulnerability layer at 영덕 (`scripts/vulnerability_layer.py` code path — not `verify_rescue_routing.py --sweep fc`, which is the 439-series rescue artifact), reporting the failing-household set size and Jaccard vs the committed 24; cite Studenski 2011 (0.92 ± 0.27 m/s, https://pubmed.ncbi.nlm.nih.gov/21205966/) and Peel 2013 (0.58 m/s) as the bracket. Step 0: a dry run proving the routing axis runs on `data/snapshots/` + committed npz in the sandbox (believed yes since Session 18; UNVERIFIED).
- **Effort:** one to two laps. **agent_doable:** true. **Constraints:** new arms, new filenames, defaults untouched; never quote a short-budget rate without its budget (§5.10); no ranking of regions (§5.14). **Done when:** artifacts + registered numbers + `docs/premovement_sensitivity.md` and `docs/walking_speed_sensitivity.md` stating method, result, caveats and what they do not show; tests.

### WFG-026 · P1 · KCF · Related-work table (Crossref-resolved only) + SFTD059T differentiation panel
- **What:** `docs/related_work.md` + a one-page Korean booth table. Entries restricted to citations already resolved: Cova & Johnson 2003 (10.1016/s0965-8564(03)00007-7); Cova et al. 2005 trigger buffers (10.1111/j.1467-9671.2005.00237.x); Li, Cova & Dennison 2017 (10.1016/j.apgeog.2017.05.008) and 2018 (10.1007/s10694-018-0771-6); Wahlqvist et al. 2021 WUI-NITY (10.1016/j.ssci.2020.105145); Finney 2002 FlamMap MTT (10.1139/x02-068); Borgwardt et al. time-expanded max-flow (https://arxiv.org/abs/2410.14500); RESCUE, Tammali et al., ICDCN 2026 (10.1145/3772290.3772301); Dayan 2026 CRC (https://arxiv.org/abs/2603.22331); Lahrichi et al. WSTS+ (https://arxiv.org/abs/2502.12003); Sung et al. KJRS 2025 GK2A detection (https://www.kjrs.org/journal/view.html?pn=mostdownload&uid=1117&vmd=Full); Kwon/Kim/Han Uiryeong MIP (10.3390/systems13121125); ISEF 2026 SFTD059T (https://abstracts.societyforscience.org/Home/FullAbstract?projectId=27978) and FireChain EAEV039 (…projectId=28121). For each: what it computes, what it does not (sampled-origin pedestrian routing on a learned held-out hazard, rescuer ingress survival, non-smartphone delivery), positioned as "not found in the surveyed work" — never 최초/처음 (`check_forbidden.py` claim rules). One panel: SFTD059T (FDS indoor gas/fire, building egress, time-varying-risk A*, Raspberry Pi) vs WildfireGuardian (wildfire-ML hazard on a time-expanded graph, rural household-level walk-out, rescue dispatch triage, live FIRMS trigger with offline replay). Any DOI the agent cannot re-resolve from the sandbox is kept with the note "resolved 2026-09-03 outside the sandbox".
- **Effort:** one lap. **agent_doable:** true (web access from the sandbox UNVERIFIED; the list above needs no new lookups). **Done when:** file + table exist; zero unresolved citations; `check_forbidden` green.

### WFG-027 · P1 · KCF · Schedule & roles timeline
- **What:** `docs/auto/finals/TIMELINE_ROLES.md` (Korean): a dated table reconstructed from `git log` (first commit 2026-05-27; tag `round2-submitted`; `docs/SESSION*_REPORT.md` dates; Round 3; 2026-09-03 loop start) plus a roles statement (student / 지도교사 / AI-assisted sessions disclosed as tooling in the wording WFG-022 returns). Verbal and poster use only; the submitted 서식2 Ⅱ-5 cannot be edited.
- **Effort:** hours. **agent_doable:** true. **Constraints:** truthful attribution only; label as DRAFT until the student confirms. **Done when:** the file exists and every date greps to a commit or report.

### WFG-028 · P1 · KCF · Expert consultations ×2–3 + firefighter §8 — human
- **What:** the agent drafts `docs/auto/finals/CONSULTATION_PROTOCOL.md` in the `docs/firefighter_consultation.md` §0 discipline (statements only, N-labelled, no numbers derived, anonymity default, design feedback not data). The student conducts 2–3 phone/video consultations (이장, 119 상황실 dispatcher, 사회복지사) and records them as `docs/consultation_<role>.md`; closes the firefighter §8 blanks (affiliation/rank, date, written consent for anonymous vs named attribution); asks the three academic advisers whether a one-line quoted judgment may be shown.
- **Effort:** hours each. **agent_doable:** false (protocol drafting: true). **Constraints:** no human-subject data (서식2 §3); ISEF exemption text reads "prior to experimentation", so present these as feedback shaping future design; never "현장에서 검증". **Done when:** N = 3–4 consultation docs with §8-style metadata complete.

### WFG-029 · P1 · KCF · One recorded email send from a Shanghai-workable path — partial
- **What:** `docs/delivery_channels.md` §3-B records SMTP 465/587/25 timeouts on the working network; from Shanghai a Gmail SMTP path is likely blocked without a VPN (UNVERIFIED). Agent: build `delivery/email_oauth.py` — Gmail API over HTTPS 443 with the same three locks and `approval_token` gate as `delivery/email.py`, DEMO_RECIPIENT-only, dry-run in the sandbox, tests with a mocked API. Student: authorise once and run `scripts/send_dispatch_email.py --confirm-send` (or the OAuth variant), commit `email_sent.json` with the network path stated (VPN or API). Keep 서식2's "SMS 전달은 모사" sentence until this exists; no Twilio, no SOLAPI, never "재난문자 연동".
- **Effort:** hours. **agent_doable:** adapter true; send false. **Done when:** `email_sent.json` committed with the path recorded; RELIABILITY tab wording updated.

### WFG-030 · P1 · infra · Report-number check (HANDOFF §4-B as a gate)
- **What:** `scripts/auto/check_report_numbers.py`: extract every numeric literal (with %, ×, ±) from `docs/auto/reports/*.md`, `docs/auto/JUDGE_QA.md` and any `docs/*.md` touched in the last lap; match each against `docs/NUMBERS.json` values/keys or a committed artifact path cited on the same line; print unmatched numbers with file:line; soft gate in `gates.py --mode quick`, hard in the critic lap. Allow-list dates, commit hashes, rule numbers.
- **Effort:** hours. **agent_doable:** true. **Done when:** the script runs in `gates.py`, the current tree's unmatched list is committed as the baseline, and the critic prompt cites it.

### WFG-031 · P1 · infra · `CITATION.cff`
- **What:** cff-version 1.2.0; title, `type: software`, author Park, Siyeong (Shanghai American School Puxi), repository-code URL, license as in `LICENSE`, keywords; `version`/`date-released` set only at the freeze tag (no invented date); `doi` added after the student mints it (WFG-015).
- **Effort:** minutes. **agent_doable:** true. **Done when:** file validates (`cffconvert --validate` or the GitHub citation widget renders).

### WFG-040 · P1 · infra · `build_numbers.py` would destroy the registry it claims to build

> ⚠ **Renumbered from `WFG-036` by the critic lap 20260903T1748Z.** Two live rows carried
> the ID `WFG-036`: this one (added by the research re-key `d88c85b`) and the P0 final
> product bundle (added by the sprint commit `42818ec`). `WFG-036` stays with the final
> product because `CHARTER.md` §11, `KCF_READINESS.md` R5/R9 and the sprint plan table all
> hard-reference it there. `docs/auto/reports/2026-09-03T0653Z-dev.md` still calls this row
> `WFG-036`; reports are records and are not edited.

- **What:** `scripts/build_numbers.py` defines **65** entries and ends with an
  unconditional `OUT.write_text(...)` over `docs/NUMBERS.json`, which currently holds
  **278**. Every entry added since roughly Session 12 went into the JSON directly and is
  gated by `verify_numbers.py`'s per-entry `check` block, not by the builder. So the one
  command CHARTER §3 names as the registration path silently deletes ~77 % of the
  registry, and `make verify` would then pass on the survivors. Found by the WFG-018 lap,
  which needed to register 18 values and had to establish the real path first.
- **Options (pick one, in writing):** (a) make it **refuse** — read the existing file, and
  exit non-zero if it would drop any key, so it becomes a checker rather than a builder;
  (b) make it **merge** — keep hand-added entries and rebuild only the keys it owns,
  which needs a marker on the entries it owns; (c) **retire** it to `scripts/legacy/` with
  a header saying what replaced it, and correct CHARTER §3 to describe the real path.
  (a) is the cheapest and loses nothing: the builder's value now is as a second derivation
  of the 65 oldest numbers.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** never run it as-is; do not delete it (CHARTER §3 rule 7 — archive);
  whichever option is taken, CHARTER §3's sentence must be corrected in the same commit.
- **Done when:** running the script on a clean tree cannot reduce the entry count; a test
  asserts that; `make verify` green; CHARTER §3 says what the registration path actually is.

### WFG-041 · P1 · infra · The lineage gate's label window admits an unrelated keyword
- **What:** `tests/test_rescue_lineage_ssot.py::test_every_prose_mention_of_the_synthetic_bracket_names_its_lineage`
  finds a `6 → 34` mention, then searches a **±2-line window** for `LINEAGE_LABEL`. At
  `docs/auto/JUDGE_QA.md:46` the label that satisfies it is the word 폐기 on line 45, which
  belongs to a different bullet about a different quantity (the 459-series 438/18/3 split).
  So the gate is green on the single most judge-facing occurrence of the exact sentence it
  was written to catch. Reproduced by the critic lap 20260903T1748Z: replace 폐기된 with
  버려진 on line 45, touch nothing else, and the gate fails naming line 46.
  This is the reviewer's 1724Z block ("a judge-facing file exempted by an incidental
  keyword") recurring at a finer granularity.
- **Do:** require the label on the mention's **own line**, or on an adjacent line that also
  carries the bracket; keep the ratchet in `WHOLLY_SUPERSEDED_LINEAGE` for whole-file
  exemptions, which is the reviewable mechanism. Add `JUDGE_QA.md:46` as a seeded
  regression case so the narrowing is proved, not asserted.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** do not widen `WHOLLY_SUPERSEDED_LINEAGE` to make the failure go away —
  `JUDGE_QA.md` is exactly the file the gate must see. Fix the F1 content defect first or in
  the same commit, or the tightened gate is red on landing.
- **Done when:** the window is narrowed, a seeded mutation of `JUDGE_QA.md:46` fails the
  gate, an unrelated keyword two lines away does not rescue it, and `gates.py --mode full`
  is green.

### WFG-042 · P1 · IEEE · A `verified` citation can disagree with the paper at its URL
- **What:** `paper/references.bib` requires a `note` containing "verified" and
  `check_paper.py` checks only that the word is present. The entry `wildfirespreadts2025`
  carries that note while its title and authors ("WildfireSpreadTS…", Gerard/Zhao/Sullivan)
  belong to arXiv:2406.04759, not to its own `url` arXiv:2502.12003, which is "Improved
  Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark" by Lahrichi,
  Bova, Johnson and Malof (WACV 2026). Opened and confirmed by the critic lap 20260903T1748Z.
  CHARTER §5 forbids fabricated citations; the gate that is supposed to enforce it cannot.
- **Do:** (a) correct the entry to whichever paper `manuscript.md:13` actually means, with
  the metadata as fetched; (b) make the `note` carry the **fetched title** and the fetch
  date, and have `check_paper.py` assert the note's title matches the entry's `title` field,
  so a mismatch is a gate failure rather than a reading exercise; (c) sweep the other three
  entries the same way. A network fetch inside the gate is not required and should not be
  added — the assertion is between two fields the lap that cited the paper had to fill in.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** never delete a citation to make the gate pass; correct it. Do not add a
  network call to `check_paper.py` (it runs on a clean machine in CI).
- **Done when:** every entry's `note` names the title as fetched, `check_paper.py` fails on
  a seeded mismatch, and the four current entries pass.

### WFG-043 · P0 · KCF · The 2025 fire's scale figures have no source and no key
- **What:** `README.md:193` (Korean) and `README.md:488` (English) open the project with
  27 deaths, **~116,000 ha** burned and 4,000+ homes destroyed for the
  의성→안동→청송→영양→영덕 chain, sourced to "한겨레·세계일보·서울환경연합" with no URL. None
  of the three has a `docs/NUMBERS.json` key. The hectare figure is the exposed one: public
  reporting puts the **nationwide** March–May 2025 total (347 fires) near 104,788 ha, and
  the WWA attribution report gives ~48,000 ha for the fires it analysed — so the sub-scope
  figure exceeds every national figure available. The same paragraph already carries a
  scope footnote for 27 vs "30명 이상" and none for the area. `paper/manuscript.md:9` then
  attributes 27 to `[@wwa2025korea]`, which reports 32 casualties (26 in 의성).
- **Do:** open the three named sources (NH-015 asks the author for the URLs; if they do not
  arrive, use 산림청 / 행정안전부 published figures and say which), record for each figure
  its value **and its scope** (this fire chain / 경북 / nationwide / date range), register
  them, add the scope footnote the death toll already has, fix `manuscript.md:9` to cite a
  source that carries its number, and add the drill question recorded in `CRITIC_LATEST.md`
  to `JUDGE_QA.md` with its 근거 line — updating the tier counts and the §6 drill table in
  the same commit, because `tests/test_judge_qa_bank.py` pins all of them.
- **Effort:** hours. **agent_doable:** true; the author's own sources are NH-015.
- **Constraints:** annotate, never delete, if a figure moves (CHARTER §3). Do not quietly
  swap 116,000 for another number without stating the scope both belong to — the scope is
  the finding, not the digit. `README.md`'s Round-2 section stays untouched; both lines are
  in Round 3.
- **Done when:** each of the three figures has a registered key with its scope in the
  caveat, both README lines and `manuscript.md:9` cite a source that carries the value they
  state, and `make verify` plus `check_number_collisions.py` are green.
- **2026-09-03T2347Z critic (F16, F17, F18) — the row did not close at `12b8ac7`, it changed
  sign.** That commit removed 116,000 ha and put **45,157 ha** in its place, attributed to
  중대본 as of 2025-03-27, plus a 범위 주의 note saying 104,788 ha belongs to a different
  event. Verified this lap against ko.wikipedia (2025년 의성-안동 산불), en.wikipedia
  (2025 South Korea wildfires) and Korean coverage of the 경상북도 recovery plan: the
  의성발 경북 chain's **final** area is **99,289 ha** (largest since 1986 statistics began;
  주불 진화 149시간; 2,246세대 3,587명 이재민; 주택 **3,819동**; 총 1조 505억 원), so the
  chain is about 95 % of the 104,788 ha nationwide total and the scope note points the wrong
  way. 45,157 ha is the 경북 provincial interim on 03-27, the day before 주불 진화 on 03-28
  17:15. The WWA "48,000 ha 이상" is WWA's figure for **southeastern Korea**, not this
  complex, so it cannot serve as the upper end of a range for it.
- **Also fix in the same commit:** (1) `README.md:194` and `:489` still say 영덕 **8명** /
  8 in 영덕, which `docs/evidence/greenpeace_2026_survey.md` §7 item 1 corrected to **10**
  (영덕군 공지 2025-04-29 quoted at report p.9, a 재인용값 not a survey result) on
  2026-09-03T1821Z; grep `영덕 8` so the third copy does not survive. (2) The 알려진 함정
  bullet at `docs/data_sources.md:201` is backwards: 3,819동 is the **chain's** 주택 전소,
  and 150동 is the 산림청 03-26 interim. (3) Every row of both tables in
  `docs/data_sources.md` § 동기 사건의 피해 규모 gains a URL, and any row whose URL the lap
  cannot open is removed rather than kept unsourced — the same rule CHARTER §12 applies to
  `references.bib`. The nationwide 주택 3,848동 is the row to check first; it is suspiciously
  close to the chain's 3,819동 and public reporting gives around 4,015 houses nationwide.
- **Then, and only then**, add the two drill questions `CRITIC_LATEST.md` withheld
  (의성 산불 피해면적; 영덕 사망자 수) to `JUDGE_QA.md` with their 근거 lines, updating the
  tier counts and the §6 drill table in the same commit.

### WFG-044 · P1 · infra · The paper routine has no report kind
- **What:** `scripts/auto/report.py:123` takes
  `choices=["dev","critic","research","kickoff","red","manual"]`. CHARTER §2 and §12 define
  a fourth routine, `wfg-autoloop-paper`, that is not in the list, so its first real lap
  filed `docs/auto/reports/2026-09-03T1928Z-manual.md` with a title line reading `· paper ·`
  and set `docs/auto/STATE.json` → `"last_report_kind": "manual"`. Three consequences, all
  live: a lap that resolves its predecessor by kind (this critic prompt's own
  `git log --grep='critic' -- docs/auto/reports` pattern) cannot find paper laps; the
  dashboard timeline labels a paper lap "manual"; and that report carries three different
  timestamps for one lap (title `1955Z`, `when` row 19:28 UTC, filename `1928Z`).
- **Do:** add `"paper"` to the `--kind` choices; derive the default title from the same
  stamp the filename uses so a hand-passed `--title` cannot disagree with it; leave the
  already-committed `*-manual.md` report where it is (CHARTER §3: reports are records).
- **Effort:** minutes. **agent_doable:** true.
- **Constraints:** `tests/` already covers the reporting scripts (`a131daf`); extend that
  test rather than adding a second one.
- **Done when:** `report.py --kind paper` writes `<stamp>-paper.md`, the title stamp equals
  the filename stamp, and a seeded `--title` with a different stamp fails a test.

### WFG-045 · P1 · IEEE · The manuscript has 21 citations and no bibliography
- **What:** `paper/manuscript.md` runs Abstract, 1 Introduction, 2 Related work, 3 Data and
  methods, 4 Results, 5 Discussion, 6 Limitations, 7 Conclusion, Data and code availability,
  and stops. CHARTER §12's required section list ends with "References"; there is none.
  `paper/check_paper.py` counts words, figures, tables, references and gaps and asserts
  nothing about sections, so the gate written to hold §12 true has never looked at the one
  structural requirement §12 states. 출처 명기 is a scored row in both rubric tracks and a
  reader of the markdown cannot resolve a single `[@key]`.
- **Do:** render `## References` into the manuscript from `references.bib` (the same path
  `build_docx.py` already uses for the `.docx`, so the two cannot disagree), and add one
  assertion to `check_paper.py` that every CHARTER §12 section heading is present, proven by
  a seeded deletion that fails it.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** the word budget is body text (7,000 target / 7,500 hard fail); confirm
  `check_paper.py` does not count the new section into it, or the paper fails its own gate.
- **Done when:** `check_paper.py` exits 0 with the section assertion in place, removing any
  required heading fails it, and the rendered bibliography lists all 21 entries.

### WFG-046 · P0 · infra · The commit you push is not the commit the gates read
- **What:** CHARTER §4 runs `gates.py` at step 5 and `report.py` at step 7, so every lap's
  report is tracked prose no gate has read. That is how critic #2 pushed `24751fa` red.
  **The 2053Z lap then showed the diagnosis was one step too narrow.** Its gate run was at
  `f5f8498` 20:39:36Z and it pushed `8d1decf` 20:57:29Z, and in between `e431696` rewrote
  162 lines of `tests/test_gk2a_detector.py` and 41 lines of `docs/detection_floor.md` (the
  reviewer-block fixes) as well as adding the report. `auto/dev` was red again. So the
  unchecked file is not "the report", it is **everything committed after the gate run**,
  and a report-only gate would not have caught the larger half.
- **Do:** two things, the second of which subsumes the first.
  (a) `report.py`, after writing, runs `make check-forbidden` and
  `pytest tests/test_rescue_lineage_ssot.py` over what it wrote and exits non-zero on
  failure, so the lap cannot commit an unreadable report.
  (b) `gates.py --assert-head` (or `scripts/auto/check_gates_current.py`, five lines):
  read `.auto/gates.json`, and exit non-zero unless `git_head` equals
  `git rev-parse --short HEAD`, `git status --porcelain` is empty, and `passed` is true.
  CHARTER §4 step 8 then becomes one command instead of a list a tired lap can skip.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** `.auto/` is git-ignored, so `--assert-head` must fail loudly when
  `.auto/gates.json` is absent rather than passing vacuously. Do not make `report.py`
  run the full suite; the prose gates are seconds, the suite is three minutes, and a
  report step that costs three minutes will be worked around.
- **Done when:** deleting the lineage label from a report makes `report.py` exit non-zero;
  committing anything after a green `gates.py` and running `--assert-head` exits non-zero;
  CHARTER §4 step 8 names the one command.

### WFG-047 · P0 · infra · `in-progress` has no release, so an unfinished row is stranded
- **What:** CHARTER §4 step 3 tells a lap to take the highest-priority row that is `todo`
  and **not `in-progress` by another lap**. Nothing tells a lap what to do with its row
  when it ends without finishing it. The 2053Z lap left `docs/auto/BACKLOG.md:44` reading
  `in-progress(20260903T2050Z) — (b) done(f5f8498), (a) card + JUDGE_QA block outstanding,
  (c) not attempted`, which is exactly the right residue note and exactly the wrong status
  word: no lap holds that claim any more, and no future lap may take the row. `WFG-016`
  has been `in-progress(kickoff seed)` since the kickoff for the same reason. Both are P0.
  `KCF_READINESS` R2 names WFG-021 (a), the detection-floor evidence card on the finals
  screen, so a readiness line is blocked by a status word inside a twelve-day sprint whose
  plan dated WFG-021 to 09-05.
- **Do:** add one sentence to CHARTER §5: *a lap that ends without finishing its row sets
  the row back to `todo` and appends what it did as a residue note; `in-progress` is only
  ever held by a lap that is still running.* Then set WFG-021 and WFG-016 to `todo`,
  keeping their residue text verbatim.
- **Effort:** minutes. **agent_doable:** true.
- **Constraints:** do not delete or reword the residue notes; they are what makes the rows
  restartable by a fresh agent (CHARTER §5). Do not mark WFG-021 `done`: only part (b) is.
- **Done when:** no row in the table is `in-progress` without a lap running, CHARTER §5
  states the release rule, and WFG-021's remaining (a) and (c) are pickable.

### WFG-038 · P1 · infra · The suite's own count is not gated
- **What:** `scripts/auto/gates.py` runs the full suite and writes the summary line
  into `.auto/gates.json`, but nothing reads the numbers in it. On 2026-09-03 one lap
  read **1,098 passed / 60 skipped** and then **1,104 / 54** from the same commit
  (`682aeb3`), same flags, minutes apart — 1,158 outcomes both times, six tests moving
  between passed and skipped, `ALL GREEN` printed for both. The previous lap saw the
  same six-test signature (1,071/60 vs 1,077/54) and could not reproduce it. So six
  tests in this suite have a result that no gate can distinguish from a regression,
  and the only place it is visible is a summary line nobody compares.
- **What was already ruled out:** the six git-ignored `data/cache/*.nc` files are
  written during the first full run of a fresh container, but moving them aside and
  re-running still gives 1,104/54 — they are regenerated before the guarded tests
  run. The identity of the six is open.
- **Do:** (a) parse `collected / passed / skipped / xfailed` out of the pytest summary
  in `gates.py` and store them as fields, not just the raw line; (b) commit a baseline
  (`docs/auto/suite_baseline.json`) holding the triple and the sorted list of skip
  reasons with counts, produced with `-rs`; (c) WARN in `--mode quick` and fail in the
  critic lap when the skip count or the reason multiset moves without the baseline
  being updated in the same commit; (d) with (b) in hand, run the suite once in a cold
  container and once warm, diff the two reason lists, and name the six in the MEMO.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** never fix a drift by widening a `skipif`; the point of the gate is
  to make the six findable. A skip on a git-TRACKED path is a defect, not a guard
  (MEMO 2026-09-03).
- **Done when:** the baseline file exists, `gates.py` compares against it, a test
  asserts the comparison fires on a seeded mismatch, and the six drifting tests are
  either named or the gate proves the drift no longer occurs.

### WFG-011 · P2 · ISEF · ISEF plan memo — revise
- **What:** `docs/auto/research/ISEF_PLAN.md`: route-existence questions and their answers (KCF 은상/동상 → delegation; interview date; eligibility of a student enrolled outside Korea — all UNVERIFIED until the 사무국 answers); category recommendation SFTD (Algorithms/HMC) with the base rate stated (applied decision-support pipelines in SOFT/SFTD 2023–2026: 8 of 10 unplaced; SFTD059T unplaced) and EAEV as non-target (FireChain unplaced); 12-month window (start 2026-05-27; freeze ~2027-05-01; ISEF 2027 LA 8–14 May); Form 2A; Display & Safety (no internet, no URLs/QR, ≤ 100 Wh, frozen digital demo, attribution lines for OSM/ERA5/FIRMS/SRTM/WorldCover, "created by Finalist using …"); human-participants position (no study this cycle; consultations as expert feedback); age rule 만 15세 이상 19세 미만 (namu wiki; UNVERIFIED against the affiliate); the "hand-written only" list; what the loop may and may not do after the affiliate selection (no new variables or procedures).
- **Effort:** one lap. **agent_doable:** true. **Done when:** the memo exists with URLs for every rule; every UNVERIFIED item has a NEEDS_HUMAN ask.

### WFG-032 · P2 · science · Leak-free 영덕 fold + hindsight-oracle routing arm — partial (Mac-only run)
<!-- collision-ok: 129.1 -->
- **What:** agent writes `scripts/leakfree_yeongdeok_fold.py` and `scripts/hindsight_oracle_routing.py` with tests on synthetic inputs: (1) count `uiseong_andong_2025` dataset rows whose cell lies inside the 영덕 bbox with overpasses 2025-03-25→27 (the manifests' bboxes overlap 128.95–129.1 E); (2) refit the 영덕 LOFO fold with `uiseong_andong_2025` excluded from training; re-simulate the canonical 영덕 field with `run_forward_sim_region.py` into a new npz; (3) build a hindsight field from the actual later FIRMS cumulative masks; (4) route the same 458 origins on the original, leak-free and hindsight fields; write three new artifacts and register 414/42/2-style partitions per arm. Student runs it on the Mac (raw bundle). Interpretation: if the FA-only count moves by more than network-drift noise (a 0.047% node change moved 33% of binary verdicts on the 439 series), the coupling claim is not paper-ready; if it survives, it is IEEE Table V and the strongest booth answer to "how do you know the 42 are real".
- **Effort:** one lap (agent) + one day (Mac). **agent_doable:** scripts true; run false. **Constraints:** never overwrite `spread_v2_lofo.json` or the canonical npz; new filenames; `fire_manifest.json` untouched (§5.9); label the six fires as five independent events plus one co-located pair in the doc. **Done when:** scripts + tests committed; NEEDS_HUMAN with the exact command; after the run, `docs/leakfree_fold.md` with the three partitions.

### WFG-033 · P2 · science · Coupling-ablation routing-only arms (absorbs WFG-012)
- **What:** on the committed hazard fields (`routing_demo_canonical.npz`, `hazard_uiseong_andong_2025.npz`, `hazard_uljin_samcheok_2022.npz`) and `data/snapshots/`, run the identical scan under: (a) fire-blind; (b) static current perimeter (slice 0, p ≥ p_cut) + fixed buffer 0.5/1/2 km; (c) `spread_v2` canonical (the committed arm, re-read not re-run); (d) the Rothermel surface field only if a committed field exists (do not regenerate). Report FA-only / no-safe counts and paired exposure per arm per region with covariates; the persistence and hindsight arms belong to WFG-032 (raw bundle). This is R5's E1 restricted to what the sandbox can run.
- **Effort:** two laps. **agent_doable:** true after the WFG-025 dry run proves the axis runs. **Constraints:** §5.7/§5.12/§5.14/§5.18/§5.19; new filenames. **Done when:** `data/processed/coupling_ablation/*.json`, registered numbers, `docs/coupling_ablation.md` that says plainly whether the learned field beats "current perimeter + buffer" on routing decisions.

### WFG-034 · P2 · science · Refuge-density decimation — blocked(approval in WFG-023)
- **What:** hold network and terrain; remove refuges at 100/75/50/25% with 20 seeds; measure FA-only and `no_safe_route` per region on the 459 axis → the condition under which the rescue-aware constraint binds (answers the "why does the rescue constraint change 0 assignments" question with a measurement). Requested 2026-08-02, sequenced, never started (HANDOFF §4: the user confirms before it starts).
- **Effort:** two laps. **agent_doable:** true once approved. **Constraints:** new arm; covariates; caveat. **Done when:** artifact + doc + registered numbers.

### WFG-013 · P2 · science · Open building footprints for 영덕 — keep
- As written; add: licences cited; if covered, the real-footprint replacement runs and every household count in Session 22 is re-stated with the OSM comparison; NH-005 closes either way.

### WFG-014 · P3 · IEEE · Paper skeleton — revise
- **What:** `paper/` IEEEtran built by CI (`xu-cheng/latex-action@v4`), using R5 §4's outline with these corrections baked in: "sampled walk-network origins", not "households"; 32.6% caveat in the abstract; never a 439-series number beside 458-series counts without lineage; six fires = five independent events + one co-located pair; cumulative IoU ≈ 0.40 with new-ring ~0.07 beside it; contribution ② in HANDOFF's conditional wording; Session-22 shelter finding out of Results; every number a registry key (WFG-035); acknowledgment naming the AI system and AI-generated sections/code; limitations first. Venue: IEEE Access at full US$2,160 + tax (no student discount), OJ-ITS if WFG-033 plus an external routing comparison exist; IGARSS 2027 4-pager by 10 Jan 2027 only if WFG-032 survived. No preprint/submission before the December ceremony; TechRxiv the week after.
- **Effort:** weeks. **agent_doable:** drafting true; submission false. **Done when:** `paper/main.pdf` builds in Actions; every number in it greps to a registry key; the student has rewritten the abstract by hand.

### WFG-035 · P3 · IEEE · Register the manuscript's numbers
- **What:** add `NUMBERS.json` entries (new keys, derived from committed artifacts) for: RF/LR/HGB baselines (`ml_baselines.json`), DEM-corrected deltas (+0.0048 / −0.0017), pooled CI with a per-fire or spatial-block method beside the DeLong cell-level CI (cells are autocorrelated; ±0.004 overstates precision), Brier/ECE per model, cumulative and new-ring IoU, envelope-bias ratios, timings (HANDOFF §9: ~25 s), and the two HGB means with the reconciling note. R5 claimed all were registered; a scan found most are not.
- **Effort:** one lap. **agent_doable:** true. **Done when:** `make verify` green with the new keys and `paper/` cites only keys.

### WFG-015 · P3 · IEEE · Reproducibility package — keep
- As written; the Zenodo DOI is minted by the student from a GitHub Release after the finals (needs a Zenodo login); `docs/REPRODUCE.md` verified by a fresh-clone CI run on committed snapshots; the 16 verified-but-unreproducible values stated as such with the 2026-07-24 graph-loss reason.

### WFG-048 · P1 · infra · The FIRMS half of the detection-floor comparison is unregistered
- **What:** `docs/detection_floor.md` §4 prints `+117분`, `+151분`, `+17분` for FIRMS beside
  the three registered GK2A delays, and §8 repeats them as the headline trade-off line
  (`+22 / +34 / +64분` vs `+117 / +151 / **+17**분`) together with a derived "95분·117분
  앞섬" and "47분 빨랐습니다". None of those has a `docs/NUMBERS.json` key. The values are
  read from a committed artifact — `data/processed/detection/firms_first_detection.json`
  → `<fire>.delay_h` = 1.95 / 2.52 / 0.28 h — so they are traceable by hand and NOT
  re-derivable by `make verify`, which is the gap CHARTER §3 rule 3 exists to close.
- **Do:** register three `json_path` entries in hours (the artifact's own unit) plus, if the
  minute form is wanted on judge-facing prose, three `expression` entries with
  `expr = "a * 60"`; then cite them from §4, §8 and the finals card. Check first whether
  `scripts/build_numbers.py` would drop them on its next run (WFG-040) — the existing
  `det_*` keys are not produced by it either, which is the same latent problem.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** never edit a registered value (§3 rule 2); the derived "95분·117분
  앞섬"/"47분" sentences in §8 must either become registered expressions or be rewritten to
  read off the registered pairs. Do not restate the FIRMS numbers anywhere new until they
  are registered.
- **Done when:** `make verify` re-derives every FIRMS figure that appears in prose, and
  `docs/auto/finals/DETECTION_FLOOR_CARD.md` can state the comparison instead of pointing
  at §8.

### WFG-049 · P0 · infra · A prose-only commit is invisible to every gate
- **What:** `12b8ac7` (2026-09-03T2330Z) rewrote `README.md`'s opening paragraph in Korean
  and English, added a new section to `docs/data_sources.md`, closed NH-008, NH-009 and
  NH-015, and edited `docs/auto/LOOP_CONFIG.json`. It has **no report**, so no
  `Reviewed by:` line, no gate table, no root objection and no plain-terms section;
  `docs/auto/STATE.json` still names the 2239Z dev report at `c7b8a66` as the last report,
  so the loop's own state file does not know the commit exists. Every gate passed on it, and
  the numbers it introduced were wrong (WFG-043, critic F16/F17/F18). The three checks the
  loop added this week are all aimed elsewhere: `--assert-head` asks whether the gates read
  the pushed commit (they did), `report.py`'s prose gate runs only when a report is written
  (none was), and `make verify` re-derives only numbers that have registry keys (these have
  none). The class is the finding: **prose with no key and no URL can change under every
  gate this repository owns.**
- **Do:** `report.py` already computes "commits since the previous report". Put the same
  computation in front of the push. `gates.py --assert-head`, or a short check beside it,
  exits non-zero when `HEAD` is not the commit the last report names **and** the intervening
  commits touch anything outside `docs/auto/reports/`, `docs/auto/images/` and
  `docs/auto/STATE.json`. Message names the offending paths so the fix is obvious. Pin it
  with a test in the style of `tests/test_gates_assert_head.py`, seeded with this exact
  `c7b8a66`/`12b8ac7` pair.
- **Effort:** hours. **agent_doable:** true.
- **Constraints:** must not block the report commit itself, which is by construction after
  the gate run (that is what `--assert-head` already handles); must not require network.
  Do not weaken `--assert-head`'s existing mode clause while extending it.
- **Done when:** a commit pushed without a report covering it fails the pre-push check, the
  seeded test reproduces the `c7b8a66`/`12b8ac7` case, and CHARTER §4 step 8 names the
  command.


### WFG-051 · P1 · infra · A bound value with a free attribution

Opened by critic #5 (2026-09-04T0147Z, F23). WFG-049 made every figure in the README's
opening paragraph traceable to a value in `docs/NUMBERS.json`, re-derived from
`data/processed/external/fire_2025_scale.json`. It did not make the *attribution*
traceable, and `scripts/check_readme_figures.py:88-92` is where that stops: the provenance
loop asserts only that `agency`, `as_of`, `scope`, `source_url` and `figure_status` are
present and non-empty.

Three disagreements exist today, all of them inside the apparatus:

| figure | registry says | `docs/data_sources.md` says | `README.md` says | the source says |
|---|---|---|---|---|
| 45,157 ha (interim) | 중앙재난안전대책본부, khan 2025-03-28 | 산림청, khan 2025-04-17 (`:194`) | 산림청 (`:204-205`) | **산림청** (khan 2025-04-17) |
| 사망 26명 | 중앙재난안전대책본부 (경북 5개 시군 합계), 뉴시스 + 서울신문 | 경상북도 재난안전대책본부, 대구MBC (`:190`) | no link of its own (`:193-199`) | not in the linked page |

The second matters most. `README.md:193-199` and its English twin at `:505-513` put the
whole chain parenthetical, 사망 26명 included, under one citation to
[아시아경제 2025-05-06](https://view.asiae.co.kr/article/2025050610030818823). That article
was opened by critic #5: it carries 99,289 ha, 149시간, 3,819동, 2,246세대 / 3,587명 and
1조 505억 원, and no death figure. The figure a judge is most likely to check is the one
whose link does not contain it.

**Done when:** (a) `interim_chain_area_ha_20250327` in the artifact reads agency 산림청 with
the khan 2025-04-17 URL (the page that carries both the figure and its 「산불영향구역」 label),
and `chain_deaths` uses one agency spelling that `docs/data_sources.md` also uses;
`register_fire2025_figures.py` re-run and `docs/NUMBERS.json` updated additively.
(b) 사망 26명 carries its own inline citation in both paragraphs, from the registry's URL.
(c) `check_readme_figures.py` compares each figure's registry `agency` and `source_url`
against the sources-table row and against the README's nearest inline link, and fails on a
mismatch; a test proves it fires by flipping one agency.

**Constraints:** additive registry writes only (CHARTER §3 rule 3); no figure value changes,
this row is about attributions; the artifact is under `data/processed/` so a new value needs
a new file, but correcting a provenance field on a figure the same sprint registered is a
correction of the record, not a regenerated result. If that reading is disputed, write the
corrected rows to a new `fire_2025_scale_v2.json` and point the registrar at it.

**Related:** WFG-049 (the value half, done), WFG-050 (the URLs themselves are unpinned;
snapshot them with sha256), critic #5 F23.

**Critic #8 addendum, 2026-09-04T0750Z — the disagreement narrowed to two spellings, and the
wrong one is the registry.** The paper lap corrected `paper/manuscript.md` this window and
registered `dgmbc2025toll` in `paper/references.bib` for it. Critic #8 opened that page
independently (<https://dgmbc.com/article/bLdh4s3M4pgcSdYI0MZPc>, 2026-09-04) and confirms
it verbatim: 「경상북도 재난안전대책본부가 3월 30일 오전 8시 30분을 기준으로 발표한 자료에
따르면 산불로 인한 경북 지역 사망자는 영덕군 9명, 영양군 7명, 안동시와 청송군 각각 4명,
의성군 2명 등 26명입니다」, and **neither 「중앙재난안전대책본부」 nor 「중대본」 appears
anywhere on the page.** So the only openable source that carries the 26 together with its
district split attributes it to the **province**, and the two documents still saying
otherwise are:

- `docs/NUMBERS.json` → `fire2025_chain_deaths`, whose `derivation` reads
  `agency: 중앙재난안전대책본부 (경북 5개 시군 합계) … source: newsis` — a breaking-news
  stub that names no agency at all;
- `README.md:198` 「경상북도 최종 집계·**중앙재난안전대책본부 확인**」 and its English twin
  at `:510` 「Gyeongsangbuk-do final tally confirmed by 중앙재난안전대책본부」, which assert a
  confirmation no source in this repository supports, under a link
  ([아시아경제 2025-05-06](https://view.asiae.co.kr/article/2025050610030818823)) that
  carries no death figure.

`docs/data_sources.md:190` and `paper/manuscript.md` are now both correct. The row is
therefore smaller than it was and more embarrassing: the SSOT is the one that is wrong, and
it is wrong against a page this repository already cites.

### WFG-053 · P0 · KCF · The booth card says the satellite was slower than the telephone; the paper says we cannot know

**Where the two answers are.** Judge-facing, asserting the ordering:

- `docs/auto/finals/DETECTION_FLOOR_CARD.md:17-19` — the card's front, in bold:
  「**위성은 사람보다 느렸습니다.** … 위성 트리거는 신고보다 각각 **+22분 · +34분 · +64분**
  뒤에 울렸을 것입니다」, and `:11-13`, the caveat that the clock is the 신고 시각 and that
  the delays are therefore written 「실제보다 위성에 유리하게」.
- `docs/detection_floor.md:29-38` (§1, 「가장 중요한 단서 — 기준 시각은 신고 시각입니다」),
  `:240-252` (§9 평결), `:262-275` (§10, the trigger-priority table that ranks 사람 신고
  first *because of* the ordering).
- `docs/auto/JUDGE_QA.md:234` — inside **Q10, a T0 question the student is told to memorise**:
  「위성 트리거는 사람 신고보다 각각 22분, 34분, 64분 **뒤에** 울렸을 것입니다」.

Withdrawing it, in the same repository, written the same night:

- `paper/manuscript.md:492-497` and `:533` — 「no artifact supports that and this paper does
  not claim it」 … 「Whether that is ahead of or behind the emergency call, this measurement
  cannot say」; Table 3's caption states the clock's provenance in full.
- `paper/GAPS.md` G5, and `docs/auto/NEEDS_HUMAN.md` NH-019.

**Why the paper is right and the card is wrong, from artifacts only.** No committed artifact
records a 신고접수시각 for any of these fires. `docs/data_provenance/fire_manifest.json` says
of the field the delays are measured from, for every one of the four detection fires,
`start/end/reported_ha are provenance only`, and each entry's own note describes the event
start as the **ignition** (`first hit … may lag ignition`). For `yeongdeok_2025` it is not
even ambiguous: `start` is `2025-03-22T12:15:00+09:00` and the same note reads `first hit
(2025-03-25) lags the 2025-03-22 ignition by days` — the manifest names that date the
ignition. So the design note's reading is not merely unsourced; the one artifact it cites
labels the field the other way.

The caveat inherits the error. The card tells a judge the figures flatter the satellite
*because* the clock is a report time. If the clock is the ignition, there is nothing to
flatter, and the 평결's 「어느 쪽으로 읽어도 위성이 사람보다 앞서지 않습니다」 has no
measurement behind it at all, because the human's time was never measured.

**Done when:** every document in the first list states the delays against the **recorded
occurrence time**, with the manifest's own provenance sentence beside them, and makes no
claim about whether the satellite preceded the call; the size floor (0.1–1 ha, and 「2 km
화소는 1 ha 규모 이하의 불을 분해하지 못한다」) carries the booth answer instead, because it
is true under either reading; §10's trigger-priority table keeps 사람 신고 first but on the
99 %-목격신고 statistic it already cites, not on the ordering; Q10's T0 answer is rewritten to
match, and the new Q10c stops being marked 「근거 없음」; NH-019 stays **open** for the
stronger claim, which still needs one 신고접수시각 from the author.

**Constraints:** this is a narrowing, not a new claim, so no number moves and no registry key
changes — `tests/test_detection_floor_card.py`'s 17 bindings must still pass untouched. Do
not delete the 평결 section; rewrite it under CHARTER §3 rule 3 with the superseded reading
annotated, the way NH-015 was handled. Do not wait on NH-019: the paper did not.

**Why it is P0.** `DETECTION_FLOOR_CARD.md` is the one evidence card the loop has finished,
it is meant for the booth panel, and Q10 is one of the fourteen answers the student is told
to know by heart. This is the same failure class as F21 — a value bound to a registry with a
free sentence around it — moved from a README paragraph to the three artifacts a judge
actually meets.

**Lap 20260904T0419Z — done.** The whole done-when clause holds and no number moved.

- `docs/detection_floor.md` §1 is retitled 「기준 시각이 무엇인지 우리는 모릅니다」 and quotes
  the manifest's own `start/end/reported_ha are provenance only` plus its ignition note
  (`first hit … may lag ignition`), with the withdrawn 신고 reading annotated below it rather
  than deleted (CHARTER §3 rule 3). §4's table label and §4's counterfactual sentence follow.
- §9's 평결 is now the **size floor** — 「2 km 화소는 대략 1 ha 아래의 불을 분해하지 못한다」 —
  which is true under either reading of the clock, with the old ordering verdict annotated.
  §10 keeps 사람 신고 first on §0's 99 %-목격신고 statistic instead of on the ordering.
- `docs/auto/finals/DETECTION_FLOOR_CARD.md`: caveat block, front sentence, table header,
  trigger table and the 「보여주지 않는 것」 list. The front sentence is now the size floor.
- `docs/auto/JUDGE_QA.md`: Q10 (T0) rewritten, Q10a's closing line narrowed, Q10c's
  「근거 없음」 banner replaced by a ✅ note making it the repository's standard answer.
- `docs/SESSION19_REPORT.md` keeps its body verbatim as a record and gains a dated 🛑
  annotation naming the current version; `docs/horizon_grounding.md` loses its false
  「same weakness in the same data」 cross-reference (filed as WFG-061).

**The row's constraint was almost right, and the exception is the finding.** It said the 17
tests in `tests/test_detection_floor_card.py` must pass untouched. Fifteen did. Two did not,
and both are worth recording:

1. `test_the_card_states_the_reference_time_caveat_first` asserted `"신고 시각" in text` — the
   one test guarding the card's most important sentence was **pinning the withdrawn reading**,
   so it would have failed the correct card and passed the wrong one. It now asserts
   「기록된 발생일시」 and `provenance only`. Every one of the 17 *number* bindings passed
   untouched, which is what the constraint was protecting.
2. The bare-digit tripwire fired on `2026-09-04`, `WFG-053`, `NH-019` and the `99 %`
   statistic. Its escape list is hand-maintained by design; all five are added with reasons.

**⚠ The gate was oversold by this row's first draft, and its own reviewer proved it twice.**
`tests/test_detection_ordering_is_not_claimed.py` (21 tests) bans the spellings this repository
actually shipped, and **that is all it does** — the reviewer escaped it with 「늦었」 for 「느렸」,
then with 「사람보다 22분 늦었」 against the fix, then reported that most of twelve further
rewordings (a line-wrap split, 인간/목격자 for 사람, reversed subjects, any English) still pass.
Both named escapes are closed and are permanent cases; the rest are listed as verified-uncaught
in the test's own docstring. **Read it as a ratchet against regression-by-copying, not as a
guarantee**, and note that the load-bearing protection for this claim is still a human reading
the card. The general fix is WFG-062. The row's own done-when — the documents themselves — is met
and was verified line by line. Historical note, the gate as first written bans five spellings
across the three Korean documents
**and `paper/manuscript.md`**, which is in the list as a regression anchor — it is the half of
the repository that got this right first, and a later lap "harmonising" it back to the card's
old wording is the failure this row exists to stop. Withdrawal prose is licensed per line by
the repository's own `<!-- forbidden-ok: -->` pragma, so there is no whole-file escape. Six
mutation cases put the exact shipped sentences back and require a failure; three neighbour
cases (「기록된 발생일시로부터 +22분」, the 99 % statistic, 「사람 신고를 일차 소스로」) require
a pass. `test_the_manifest_still_says_what_this_gate_rests_on` re-derives the premise from the
artifact, so if a real report time ever lands the gate fails and the narrowing is revisited on
evidence — which is what NH-019 asks the author for.

### WFG-054 · P0 · infra · A reply the loop cannot map is discarded, and the message is marked read

**Where:** `scripts/auto/decisions.py:100-104` (`cmd_apply` appends `key` to
`seen["applied"]` unconditionally), `:69-71` (`apply_one` returns the text unchanged and the
message `no such entry; recorded nowhere`), `:115-119` (`cmd_seen` reports `seen` when any
key starts with the message ref).

**Reproduced this lap**, in process, against the live `NEEDS_HUMAN.md` without writing it:

    apply_one(text, "NH-020", "yes, do it", …)
      -> "NH-020: no such entry; recorded nowhere"
      -> text changed?  False        the author's words appear nowhere?  True

`cmd_apply` then records `<message id>:NH-020` as applied anyway, and CHARTER §6 tells the
next lap to skip any message `decisions.py seen` reports as seen. So a reply that names an
id with a typo, or an entry a later lap has not written yet, is lost with no trace — and a
reply carrying one good line and one bad line marks the whole message read after applying
only the good one. The module's own docstring at `:15-16` promises `A decision the loop does
not understand is still recorded, as` noted `, never guessed at`.

This is NH-017's failure class rebuilt in code: the machinery added this window to make the
author's decisions verifiable can silently drop one.

**Done when:** `cmd_apply` records the seen key only when `apply_one` reports a change;
everything else is appended verbatim, with its message id and date, to a committed place a
later lap will read (an `## Unmapped replies` section at the foot of `NEEDS_HUMAN.md` is
enough and needs no new file); the run's exit code is non-zero when anything went unmapped,
so a lap cannot miss it; and `tests/test_decisions.py` gains one case per direction —
an unknown id leaves `decisions_seen.json` untouched and lands in the unmapped section, a
known id still closes and still records.

**Constraints:** never guess which entry an unmappable line meant (CHARTER §6). The report
must still quote the line, as this lap's prompt requires; the file record is in addition to
that, not instead of it.

### WFG-055 · P1 · IEEE · The paper's page limit is enforced by a proxy nobody has calibrated

**Where:** `paper/check_paper.py:26` (`LIMIT = 7500`) and its docstring's
「the 20-page budget incl. refs + title」; `docs/auto/CHARTER.md` §12 (「under 20 pages
including title page and references」); `paper/GAPS.md`, the ⚠ Length pressure section the
paper lap wrote itself.

**What is wrong.** Measured this lap: `check_paper.py` reports `body_words: 7479` against a
7,500 hard fail — **21 words of headroom**, so the next lap that adds a sentence fails the
gate. That is the paper lap's own declared state and it is honest. The finding is the layer
under it: the constraint CHARTER §12 states is *pages*, the gate measures *words*, and the
conversion has never been checked against the built document. The paper lap's own crude
recount over the `.docx` (8,909 words including captions, tables and 25 references, plus
seven full-width figures) lands nearer **21 pages**, so on the loop's own estimate the
invariant is already breached and no gate can see it. LibreOffice is present in the sandbox
but refuses to open the built document, so no lap has produced a page count.

`check_paper.py` also checks no section at all against §12's list (Abstract, Introduction,
Related work, Data and methods, Results, Discussion, Limitations, Conclusion, Data and code
availability, References) — which is WFG-045's substance, so that row is absorbed here.

**Done when:** one real page count exists for `paper/WildfireGuardian_Park_2026.docx`
(any route that works in the sandbox: a different converter, a docx page-break count, or a
PDF); `LIMIT` is re-derived from it or CHARTER §12 is corrected to the true budget, whichever
the measurement says; `check_paper.py` fails when a §12 section is missing from
`manuscript.md` or from the built document; and `GAPS.md`'s ⚠ section is replaced by the
measurement.

**Constraints:** do not cut a number or a caveat to make room (the paper lap's own rule).
Captions are free space because `build_docx.py` does not count them, which is also why the
word proxy drifts from the page count — say so in whatever replaces it.

### WFG-056 · P1 · infra · The push check that guards every push leaves no record of any push

**Critic #8, 2026-09-04T0750Z — verified, and it is worse than 「leaves no record」.** The
critic prompt asks this lap to confirm every day that each push in the window carried a
report, using `gates.py --assert-reported --base <previous push>`. Ran it against eight
bases spanning the whole 24 hours (`3156459`, `1113388`, `0ff1b36`, `8d1decf`, `12b8ac7`,
`5a0466e`, `b855943`, `8e0a6ad`). All eight exit 0, and all eight name the **same** report,
`docs/auto/reports/2026-09-04T0725Z-dev.md`, because the check is satisfied by any one new
report anywhere in the range. So it cannot answer the question it is asked: a window
containing ten pushes and one report passes exactly like a window containing one of each.
The ledger this row asks for is what would make the daily check real; until it exists, that
line of the critic prompt is unverifiable and this lap says so rather than reporting a pass.


**Where:** `scripts/auto/gates.py:103-149` (`assert_reported`).

**What is wrong.** The check is correct now — critic #5's F22 is properly fixed, and
`--diff-filter=A` is load-bearing and documented in the docstring. But it takes `--base` from
whatever the caller passes, normally `origin/auto/dev` at push time, and writes nothing.
After the fact the push boundaries are unrecoverable: this lap tried to verify the critic
prompt's step 2 (「every push in the window carried a report」) and could not, because
`<base>..HEAD` cannot be reconstructed from the repository once the branch has moved. The one
check whose whole purpose is to make pushes auditable is the one thing here that cannot be
audited.

**Done when:** every `--assert-reported` and `--assert-head` run appends one line
(`{utc, mode, base, head, verdict}`) to a committed ledger under `docs/auto/`, the ledger is
in `REPORT_ONLY` so it does not itself demand a report, and a critic lap can read a window's
push history out of it. A test asserts the line is written on both verdicts.

**Constraints:** append only, never rewrite (CHARTER §3 rule 7). The ledger is a record of
what a lap ran, not a claim that it was right.

### WFG-057 · **P0** · infra · Six questions are invisible to every test that guards the Q&A bank, and one of them is the guard

**Where:** `tests/test_judge_qa_bank.py` `QUESTION_RE` matches `Q(\d+)`, so `Q10a` and `Q10b`
— and the three questions critic #6 added this lap — are seen by none of
`test_the_stated_tier_counts_match_the_tags` (the stated anti-padding guard),
`test_question_numbers_are_unique_and_contiguous`,
`test_every_question_states_its_evidence_and_its_gap` or
`test_every_t0_question_points_at_something_that_exists`.

**Done when:** the pattern accepts an optional letter suffix, the three header counts are
restated in the same commit so the tier test passes, and the drill table at §6 names the
lettered questions in their tiers. Verify it fires by deleting one 없는 것 line before fixing
it.

**Constraints:** the five lettered questions are good questions; this row widens the guard,
it does not remove them.

### WFG-058 · P1 · paper · Figures in the Moreno look — done

Opened and closed by the 2026-09-04 laptop lap. The author supplied Moreno et al. (2025),
*Space-time modelling of wildfire initiation* (Trentino–South Tyrol), and asked that the
manuscript's figures look like its ten. The lap read every figure page, wrote the rules down
in `docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md`, and rewrote `paper/style.py` to them:
all four spines as a thin black frame, `a)` `b)` panel letters (`style.label_panels`),
bars with a hairline edge and in-bar values, framed legends inside the panel, YlOrRd for
probability fields, and a palette of fire red / steel blue / neutral grey with teal, brown
and slate for extra categories. The legacy `OKABE[...]` names still resolve, so no figure
function needed a colour edit; F4–F7 gained panel letters. Figures were regenerated and
looked at once; `check_paper.py` is green.

**Not done, deliberately:** the manuscript captions and the study-area map (WFG-060).

### WFG-059 · P3 · science · Buildings as exposure, not fuel (post-finals)

The author supplied Theodori et al. (FireDX, 2026 preprint) and asked whether its
buildings-as-fuel pipeline should inform our forecasting, with the instruction not to
implement it if it should not. Verdict, recorded in
`docs/auto/knowledge/WUI_BUILDINGS_AS_FUEL.md`: **not before the finals.** FireDX feeds a
physics spread solver we do not have and may not add before the freeze; its Building Fuel
Model needs construction year, stories, occupancy and a hazard-zone overlay that no open
Korean layer we hold provides; and the authors themselves call the product uncalibrated
against observed loss.

**Done when (after 2026-10-24):** (a) the author obtains a 공공데이터포털 key for the
건축물대장 API (NEEDS_HUMAN, author-only); (b) 건물DB footprints for the six study fires are
downloaded and per-cell footprint fraction, minimum structure-separation distance,
construction era and structure type (목구조 / 철근콘크리트) are computed as a new
`data/processed/exposure/` artifact with its own registrar; (c) a leave-one-fire-out ablation
says whether either descriptor improves held-out discrimination or only in the two fires
that entered settlements; (d) the descriptors feed the routing objective as a *demand* layer
(where people are), not as fuel. **Constraints:** a retrain — post-finals only; additive
registry writes; every attribute from a named agency with a date.

**Related:** WFG-013 (footprints for 영덕 — report footprint fraction and separation
distance the FireDX way so this row can compare later), the vulnerability layer, IEEE plan.

### WFG-060 · P2 · paper · Study-area map in the Moreno Fig. 1 style

Moreno et al. open with a hillshaded map of the study area, wildfire centroids as circles
graded by burned area, a graticule with lat/lon labels, a scale bar and a boxed legend. The
manuscript has no map. **Done when:** `paper/make_figures.py` gains `F0_study_area` (or the
next free number) drawn offline from the DEM already under `data/` and the six fires'
registered burned areas, in `paper/style.py` (`EXCEEDANCE` ramp for classes, `PALETTE["fire"]`
for events), cited from the Data section, and looked at once. **Constraints:** no tile or
basemap fetch at build time; every number a registry key.

---

### WFG-063 · P0 · KCF · The trigger recommendation lost its evidence and the T0 answer kept it

**Where.** `docs/auto/JUDGE_QA.md:240` (Q10, **T0** — one of the fourteen the student is
told to recite); `docs/detection_floor.md:310` (the ban) and `:319` (§10 row 1);
`docs/auto/finals/DETECTION_FLOOR_CARD.md:28` (front sentence) and `:78` (trigger table).

**What happened, in order, inside one lap.** WFG-053 narrowed every judge-facing document
off the detection-ordering claim, which was right. The narrowing removed the ordering as the
ground for 「사람 신고 일차」, so §10 needed a different ground and reached for 「신고의 99 %가
목격 신고」. That lap's own reviewer then showed the 99 % is an unregistered year-to-date
interim (경향신문 2023-04-28) and had it struck from the booth card, and §10 gained a bold
paragraph at `:310` forbidding its use as support. Two things were left behind:

1. **Q10 was not re-read.** Line 240 still says the ground is 「크기 바닥과 「신고의 99 %가
   목격 신고」라는 통계」 — the exact statistic banned 60 lines away in the file Q10 cites as
   its 근거. The card and the design doc refuse it; the sentence the student says out loud
   rests on it.
2. **The remaining ground does not carry the claim.** The size floor says a 2 km pixel
   cannot resolve a fire below roughly a hectare. That rules the **satellite out** as an
   ignition-scale trigger. It says nothing about whether the human channel is fast, complete
   or primary — that was the 99 %'s entire job. So `detection_floor.md:319`'s
   「일차 소스로 설계해야 합니다」 and the card's 「사람 신고가 일차」 are now inferences with
   no support in any judge-facing document in this repository.

This is F27's shape one window later: one question, two documents, and the loop already
wrote the correction down in one of them.

**Done when:** every judge-facing document states only what the measurement carries —
「정지궤도 위성을 일차 트리거로 둘 수 없습니다」 — and none asserts 사람 신고 primacy without a
registered source; the 99 % clause is gone from Q10; `docs/detection_floor.md` §0 may keep
the statistic as background with its source, as `:310` already provides.
**Constraints:** no number moves; this is a claim-shape change, exactly like WFG-053.
`tests/test_detection_ordering_is_not_claimed.py` guards the *ordering* sentence and does
not see this one, which is WFG-062's case for the general registry.

**Critic #8 addendum, 2026-09-04T0750Z — the row got worse in two ways in one window, and neither is a new sentence.**

1. **The bank now instructs the student to say, at T0, a sentence the same bank forbids at
   T0.** `JUDGE_QA.md:240` (Q10, tier **T0**) still reads 「그래서 트리거 설계가 신고 우선,
   위성 확인입니다 — 근거는 순서가 아니라 크기 바닥과 「신고의 99 %가 목격 신고」라는 통계」.
   `JUDGE_QA.md:353` (Q10d, tier **T0**, added by critic #7 as the guard) lists that exact
   sentence among 「❌ 말하면 안 되는 것」: 「신고의 99 %가 목격 신고이므로」,
   「사람 신고를 일차로 두어야 합니다」. Both are in the fourteen the student is told to
   memorise word for word. This is no longer a stale sentence in a document; it is one
   document giving two opposite recitation instructions at the same tier, and the student
   has no way to tell which one is current.
2. **The finals screen shipped with the fix and the three documents did not, so the student
   would now contradict the screen behind them.** `scripts/finals.template.html:1858` and the
   built `web/finals.html` say 「이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며,
   어떤 소스가 일차여야 하는지는 재지 않았습니다」, which is exactly what this row asks for.
   `docs/finals_screen_v2.md:81-83` records that the lap wrote the screen in the fixed form
   deliberately, before the fix reached anywhere else. So the four surfaces are now split
   three against one, and the one that is right is the one a judge is looking at while the
   student speaks.

Nothing about the **fix** changes: it is still the same claim-shape edit at
`JUDGE_QA.md:240`, `docs/detection_floor.md:319` and
`docs/auto/finals/DETECTION_FLOOR_CARD.md:28,78`, and the screen is already the model
sentence to copy. What changes is that the cost of not doing it is now a contradiction the
student carries to the booth rather than a sentence a careful judge might catch.

### WFG-064 · P1 · paper · Two restyled figures have colliding labels

**Where.** `paper/figures/F2_lofo_auc.png`, `paper/figures/F7_dispatch_ordering.png`,
`paper/style.py`, `paper/make_figures.py`.

The Moreno restyle (WFG-058) is a real improvement and F7 panel a is the best figure in the
paper. Two defects survived the 「all seven regenerated and looked at」 claim in
`docs/auto/reports/2026-09-04T0401Z-dev.md`:

- **F2.** Uiseong-Andong's value label `0.878` sits at x ≈ 0.878 and the
  「mean of folds 0.89」 reference rule at x = 0.89, so the red dashed line runs through the
  label's last digit. The 「pooled 0.905」 annotation is drawn at the bottom of the axes and
  overlaps the x-axis line and its tick labels.
- **F7.** Panel b's 「deadline first wins」 uses the same teal as panel a's
  「nearest first」. Inside one figure, one colour, two meanings.

**Done when:** a value label whose x falls within about 1 % of a reference rule is offset
away from it (or the rule label is moved), the pooled annotation is inside the axes, panel b
has a hue no panel-a series uses, and all seven figures are opened and looked at once after
the rebuild. **Constraints:** `paper/style.py` only; no figure data changes; the docx is
rebuilt in the same commit.

### WFG-065 · P1 · KCF · The spread-rate figure is in a knowledge note and nowhere a judge reads

`docs/auto/knowledge/PYROGEOGRAPHY.md:45` carries 8.2 km h⁻¹ forward spread for the 의성 fire
(국가산림위성정보활용센터, thermal detections from 2025-03-22, described as the highest rate
reported for a Korean wildfire). It is the first question a fire-behaviour judge asks, and it
appears in no README paragraph, no `docs/data_sources.md` row, no registry key and no Q&A
answer. CHARTER §13 is why it has not migrated, and that rule is correct — the fix is to put
it through the registry, not to quote it from the note.

**Done when:** either 8.2 km h⁻¹ is registered with agency, as-of date, scope, status and the
URL a lap opened, added to `docs/data_sources.md` table A and answerable from `JUDGE_QA.md`;
or `docs/data_sources.md` records in one line why it stays out. **Constraints:** critic #7's
search confirmed the 8.2 km h⁻¹ figure and its 「국내 최고」 framing but did **not** confirm
the 「1.5× / 고성 2019 의 5.2 km h⁻¹」 comparison the note carries beside it; that half is not
registrable until a lap opens a page that states it.

### WFG-066 · P1 · infra · No bibliographic record is written from memory

`docs/auto/knowledge/PYROGEOGRAPHY.md:169` tags a reference
`[UNVERIFIED — not opened; author list from memory]`. Critic #7 verified it and every field is
right (Sullivan, A. L., Sharples, J. J., Matthews, S., Plucinski, M. P. (2014). *Environ.
Model. Softw.* 62: 153–163), confirmed against the FRAMES catalog entry
<https://www.frames.gov/catalog/53980> and the ScienceDirect listing, both opened
2026-09-04. So nothing is wrong today. It is filed because CHARTER §3 rule 5 is
「no fabricated citations」 and a remembered author list is a bibliographic record produced
without a source; the next one may not be right, and the tag would not distinguish the cases.

**Done when:** that entry reads `[verified 2026-09-04 · FRAMES catalog + ScienceDirect
listing]` with the phrase removed, and CHARTER §13 states the rule: a note may mark a
**claim** `[UNVERIFIED]`, and may never state an author list, year, volume or page range that
was not read off a record. **Constraints:** the other nineteen `[UNVERIFIED]` tags in the two
notes are honest and stay; this row is about one phrase and one rule.

### WFG-067 · P0 · KCF · The finals screen prints a commit id that does not exist

**Where.** `web/finals.html` (`"git":"a562045"`), rendered on the RELIABILITY tab as
「SYSTEM INTEGRITY · build 2026-09-04 07:11 UTC · commit a562045」 and visible in the
committed screenshot `docs/auto/finals/screens_20260904T0630Z/4_reliability.png`. Also
quoted at `docs/auto/finals/screens_20260904T0630Z/README.md:3`, in this file's WFG-017
row (`done(a562045)`), and in the three dev reports of 2026-09-04 (0714Z, 0719Z, 0725Z).

**What is wrong.** `git cat-file -t a562045` in a fresh clone of `auto/dev` answers
`fatal: Not a valid object name a562045`. The id is a pre-rebase hash: the WFG-017 lap
built the screen, committed, then `git pull --rebase origin auto/dev` rewrote its commits
(`d0d64fb`, `dc63a06`) and the stamp inside the built HTML kept pointing at the object the
rebase discarded. `scripts/build_finals.py:815`'s `git_head()` reads
`git rev-parse --short HEAD` at build time, and nothing afterwards re-reads it.

**Why it is P0 and not cosmetic.** This is the panel a judge is pointed at to check that
the numbers on the screen came from somewhere. It is also the first thing an ISEF or IEEE
reproducibility reviewer would type. The screen invites the check and then fails it, in the
one place the project stakes its credibility. Nothing else on the screen is wrong: the
three gate lines (`verify-numbers`, `check-forbidden`, `check-region-literals`) really ran
and really passed, and the three `DATA` rows carry live sha256 prefixes.

**Done when:** `web/finals.html` on `origin/auto/dev` carries a stamp that resolves, and a
test in `tests/test_finals_screen.py` fails when it does not — `git cat-file -e <stamp>`,
one line. **Constraints:** the gate must assert that the stamp **resolves**, not that it
equals `HEAD`; the commit that carries a build is always one later than the commit the
build was made at, so an equality gate would be unsatisfiable and the next lap would
weaken it. A lap that rebases after building rebuilds before it pushes.

### WFG-068 · P1 · infra · A routine that can do a row's work but cannot close it

CHARTER §12 confines the paper routine to `paper/` plus its own report. That isolation is
correct and should stay. Its consequence, unwritten until now, is that a backlog row the
paper lap completes stays `todo`: the row is in `docs/auto/BACKLOG.md`, which the routine
may not touch.

WFG-064 is the first case. The paper lap fixed both figures at `e28377c`, wrote the fix up
under the row's own number, listed two further defects it found and fixed, and left the row
reading `todo` with the note 「CHARTER §12 stops this routine editing `BACKLOG.md`」. Critic
#8 closed it by opening the two PNGs. Had no critic run, the next dev lap would have
claimed a done row and spent a lap discovering that.

**Done when:** the loop has one written mechanism for this and it is in CHARTER §12 —
either a committed `paper/BACKLOG_CLAIMS.md` the paper lap appends `{row, commit, what}`
to and the next dev or critic lap drains, or an explicit sentence that the paper lap names
its completed rows in its report and the daily critic closes them. **Constraints:** do not
widen the paper routine's write scope to `docs/auto/`; the isolation is the point.
