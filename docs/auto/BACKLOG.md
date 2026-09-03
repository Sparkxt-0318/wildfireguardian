# Backlog — what the loop works on, in order

Conventions: `docs/auto/CHARTER.md` §5. **P0** ships before the freeze (2026-10-10, or
10-16 if the fair is 10.24; NH-006), **P1** before the finals, **P2** after the finals
(ISEF), **P3** for the IEEE paper. Status: `todo | in-progress(<stamp>) | done(<commit>)
| blocked(<why>) | parked(<why>)`. The dev routine takes the first `todo` row in table
order that is agent-doable and unblocked; `blocked(human)` rows are the author's and are
mirrored in `docs/auto/NEEDS_HUMAN.md`. This table was re-keyed on 2026-09-03 from the
research brief (`docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`) and its backlog
proposal (`BACKLOG_PROPOSAL_2026-09-03.md`), which explain every priority change; the
eight sweeps behind them are under `docs/auto/research/sweeps_2026-09-03/`. Rows the
proposal demoted keep their IDs so earlier reports still resolve.

| ID | P | goal | title | status | agent-doable | effort | rubric rows |
|---|---|---|---|---|---|---|---|
| WFG-022 | P0 | KCF | Five questions to the KCF 운영사무국 (date, track, 기여 ② restatement, AI disclosure, 제출 자료 scope) | blocked(human) | **false** | hours | Pass/Fail · all rows |
| WFG-023 | P0 | infra | Protect `Main`; ratify `auto/dev`; decide the two HANDOFF §4 items; approve/veto decimation; close NH-001/002/006 | blocked(human) | **false** | hours | — |
| WFG-018 | P0 | KCF | 제출본 대비 정본 reconciliation sheet as NEAR-labelled prose (Korean, one page) | in-progress(20260903T0624Z) | true | hours | 제출 자료 · 데이터 해석 |
| WFG-019 | P0 | science | Operating-point evidence package: per-fire recall/FNR at 0.3, PR curve, nested LOFO threshold calibration as a negative result, MODEL_CARD appendix | todo | true | one lap | 데이터 수집·분석·해석 · 설계와 방법론 |
| WFG-002 | P0 | KCF | Judge Q&A bank v2 (**revise**: corrected numbers, four new questions, deprecated phrasings purged) | todo | true | one lap | 연구 목적 · 설계와 방법론 · 데이터 해석 |
| WFG-004 | P0 | KCF | SSOT sweep (**revise**: fix README:731, reconcile `fold_sizes.md` vs `NUMBERS.json` on the primary AUC, annotate superseded values) | todo | true | one lap | 제출 자료 |
| WFG-020 | P0 | KCF | Greenpeace 2026 survivor survey registered as evidence + the "85% drove" answer | todo | true (fallback NH) | hours | 연구 목적 · 데이터 수집 |
| WFG-021 | P0 | KCF | Detection-floor panel (Session 19 as recorded) + tests for `src/wildfireguardian/detection/gk2a.py` | todo | true | one lap | 데이터 수집·분석·해석 · 설계와 방법론 |
| WFG-017 | P0 | KCF | `web/finals.html` refresh v2: evidence cards for operating point, detection floor, horizon grounding, refuge placement, reconciliation; rebuilt with `--verify` | todo | true (fallback: student runs `make finals`) | one lap | 제출 자료 · 구현 및 유용성 |
| WFG-003 | P0 | KCF | Finals screen audit + 5-minute demo script (keep) | todo | true | one lap | 제출 자료 · 구현 및 유용성 |
| WFG-016 | P0 | ISEF | AI ledger current (**revise**: add IEEE acknowledgment draft; hand-written-only list) | in-progress(kickoff seed) | true | hours | 제출 자료 · ISEF independence |
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
| WFG-011 | P2 | ISEF | ISEF plan memo (**revise**: route-existence questions, SFTD base rate, age rule, hand-written documents) | todo | true | one lap | — |
| WFG-032 | P2 | science | Leak-free 영덕 fold + hindsight-oracle routing arm (agent writes the script; student runs on the Mac) | todo | partial | one lap + one Mac day | 데이터 해석 · IEEE Table V |
| WFG-033 | P2 | science | Coupling-ablation routing-only arms on committed hazard fields (fire-blind / static perimeter + buffer / spread_v2), three regions (absorbs WFG-012) | todo | true | two laps | 설계와 방법론 · 데이터 해석 |
| WFG-034 | P2 | science | Refuge-density decimation (100/75/50/25%, 20 seeds, 3 regions) — only after written approval in WFG-023 | blocked(approval in WFG-023) | true, blocked(approval) | two laps | 데이터 해석 · 창의성 |
| WFG-013 | P2 | science | Open building-footprint coverage check for 영덕 (keep) | todo | true | one lap | 데이터 수집 |
| WFG-014 | P3 | IEEE | Paper skeleton in `paper/` (**revise**: vocabulary, caveats, AI acknowledgment, no preprint before December) | todo | true | weeks | — |
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

### WFG-019 · P0 · science · Operating-point evidence package (incl. the threshold-guarantee negative result)
- **What:** new script `scripts/operating_point_evidence.py` reading `data/processed/spread_v2_lofo_oof_cells.csv.gz` (151,904 rows, 2,989 positives; per-fire positives 8/24/34/652/769/1,502) and `data/processed/oof_classification_metrics.json` (51-point PR curve). Compute and write `data/processed/operating_point/per_fire_recall.json`: per fire, `n_positive`, recall/FNR at the committed 0.3 (expected 1.000/1.000/1.000/0.977/0.959/0.544 for gangneung/hongseong/miryang/uiseong/uljin/yeongdeok — recompute, do not copy), max OOF probability per fire (expected 0.024/0.296/0.369 on the three small fires), pooled recall 0.138 and mean-of-folds 0.0867 cross-checked against the existing keys `oof_pooled_recall_at_operating_threshold` / `oof_mean_of_folds_recall_at_operating_threshold`. Then the nested leave-one-fire-out threshold-calibration table: for each held-out fire, λ chosen so the other five fires' OOF FNR ≤ 0.2 (a) without and (b) with the conformal finite-sample correction 1/(n+1) with n = 5 (Angelopoulos et al. 2024, https://proceedings.iclr.cc/paper_files/paper/2024/file/f3549ef9b5ff520a7e41ff3cc306ab2b-Paper-Conference.pdf), reporting held-out FNR and the fraction of all cells flagged (prevalence 1.97%). State the leakage caveat (OOF probabilities for fire g come from models that saw fire f). Write `docs/operating_point.md`: "AUC ranks, recall counts"; the per-step `advance_threshold` (forward simulation) vs cumulative-field `p_cut` (router) distinction so recall is not misread as the routing field's miss rate; and the conclusion as a negative result: no finite-sample FNR guarantee is possible at n = 6 and any bound-satisfying λ turns the hazard field into a near-blanket mask; the operating point stays a ranking-driven forward simulation and 0.3 stays unchanged. Append the same section to `docs/MODEL_CARD.md` (append only; no committed value edited). Draw the PR-curve figure with the 0.3 point and the F1-optimal 0.14 point to a NEW path (e.g. `docs/figures/auto/pr_curve_operating_point.png`; §5.3 forbids regenerating existing figures, not adding). One test with a synthetic OOF frame.
- **Rubric rows:** 데이터 수집·분석·해석 (수학·통계의 적절한 적용, 논리적 해석), 설계와 방법론.
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** new filenames only; register every number; the two R3 verdicts disagree on the exact λ and held-out FNR values (different calibration conventions) — state the convention used and let the artifact be the source; never adopt any λ.
- **Done when:** artifact + registered keys + doc + MODEL_CARD appendix + figure + test; `make verify` green; JUDGE_QA question 1 cites the new keys.

### WFG-002 · P0 · KCF · Judge Q&A bank v2 — revise
<!-- forbidden-ok: 44× -->
- **What:** `docs/auto/JUDGE_QA.md` grows to ≥ 30 questions grouped by judge type (software professor, disaster-response official, fire scientist, ML reviewer, statistician). Add the ten answers in `RESEARCH_BRIEF.md` §(c) plus: the 서식1 44× contradiction; the 기여 ② restatement (with the sentence to use only after WFG-022 is answered); "why walking routes when 84.5% drove" (from WFG-020); "what did you build yourself" (from `docs/auto/AI_DISCLOSURE.md`); "is LOFO honest when 영덕 trains on 의성·안동's same-week rows"; "are any refuges designated 대피소" (OSM POIs; national shelter file not yet cross-checked — NH item). Purge: "10–14 s" (say about 25 s, HANDOFF §9), "five fabricated citations" (§4-B is five instructions carrying non-existent findings), "seven times 영덕's" (24.73/9.17 = 2.7×), "every fire we could test" (3 of 6; 영덕 excluded), the "40 minutes 안동→영덕" factoid, "Li et al. 2019", "Ronchi et al. 2021", "Lee et al. KJRS 2025" (Sung et al.). Each answer: one sentence, artifact path or registry key, "what does not exist" line, and a DRAFT label (the student rewrites in their own words).
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** no number not in `NUMBERS.json` or a committed artifact; `check_number_collisions.py --report` clean (the 24.73% share must stay marked as its own quantity, commit 953eb6c); Korean.
- **Done when:** ≥ 30 questions; a grep for the purged strings returns nothing; the critic lap's drill finds no P0 question without a file; the student has been told which answers are drafts.

### WFG-004 · P0 · KCF · SSOT sweep — revise
- **What:** as written, plus: fix `README.md:731` "6 → 34" to the [6, 11, 24, 51, 66] row from `rescue_verify.json` (registered `rescue_unreachable_count` covers 24; register the delay row if not already); reconcile `docs/fold_sizes.md` ("pooled AUC is the primary indicator") with `docs/NUMBERS.json`'s note ("MEAN-OF-FOLDS, not pooled … never present one as the other") — one statement of which is primary, annotated in both; confirm README lines 197/494 say SFTD (done at 30ed00a); annotate the two HGB means (0.890 ± 0.107 in `spread_v2_lofo.json` vs 0.894 ± 0.092 in `ml_baselines.json`) with why they differ.
- **Effort:** one lap. **agent_doable:** true.
- **Constraints:** annotate, never delete; README Round-2 section untouched; `make verify` after every prose edit.
- **Done when:** `check_number_collisions.py --report` shows 0 unmarked hits; an `ssotize` audit report is committed listing every quantity with its single home.

### WFG-020 · P0 · KCF · Greenpeace 2026 survivor survey as evidence + the "85% drove" answer
- **What:** fetch the Greenpeace Korea 2025 영남 초대형 산불 피해 실태조사 최종보고서 (2026-03) PDF (URL in `RESEARCH_BRIEF.md` §(c) Q5); record its sha256 and the quoted figures with table/page references in `docs/evidence/greenpeace_2026_survey.md`: n = 300 (296–299 answering), 63.9% aged 60–79 and 17.9% ≥ 80, 90.0% evacuated (영덕 98.0%), car 84.5% (246/291), foot 3.1% (9), boat 2.7% (8), own car 60.1% of 278 car users, neighbour ~17%, relatives 15.1%, 재난문자 received 62.3% (영덕 48.0%), 마을방송+주민 237 vs 문자 112 mentions, 87% felt life threatened, 영덕 36% living alone, 영덕 foot 1.0% / boat 8.2%, 영덕 deaths 10 (mean age 84). If `scripts/build_numbers.py` supports literal/evidence entries, register them as such; otherwise keep them as documented literals with the sha256. Write the one-paragraph answer: the walking layer is a classifier for who cannot self-evacuate feeding the rescue layer and the 이장/마을방송 channel the survey shows worked; consistent with 서식1 §1's own question. Explicitly do NOT present "40% no own car" as a bracket on the 0.30 immobility rate (car-less ≠ immobile; 60.1% is a share of car users); the immobility answer remains 서식1 §4's f = 0.15/0.30/0.45 sensitivity. State survivor bias.
- **Effort:** hours. **agent_doable:** true if the PDF is reachable through the sandbox proxy (greenpeace.org is not on the trusted allowlist — UNVERIFIED); fallback: NEEDS_HUMAN asking the student to drop the PDF under `data/raw/evidence/` (the scratchpad copy `research/greenpeace_2025.txt` is a text extraction, not the PDF).
- **Constraints:** no number derived beyond the quoted ones; the KCF purpose is unchanged.
- **Done when:** evidence doc with sha256 exists; JUDGE_QA carries the answer with the 영덕-specific figures; `make verify` green.

### WFG-021 · P0 · KCF · Detection-floor panel + tests for the GK2A detector
- **What:** (a) a finals card / Q&A block that states Session 19 exactly as recorded in `docs/detection_floor.md` §4, §9–10: reference = report time; 의성·안동 +22 min (FIRMS +117), 강릉 2023 +34 (FIRMS +151), 홍성 2023 +64 (FIRMS +17); 영덕 2025 excluded as confounded by the 의성 fire's background ring; 2022 fires predate the archive; false-alarm control 0/709 steps; conclusion: 사람 신고 > GK2A > FIRMS, the `manual` trigger is primary, "GK2A buys time" is not claimed. Registry keys: `det_gk2a_delay_uiseong_andong_min`, `det_gk2a_delay_gangneung_2023_min`, `det_gk2a_delay_hongseong_2023_min`, `det_gk2a_yeongdeok_best_delta_k`. (b) Unit tests for `src/wildfireguardian/detection/gk2a.py` (SESSION19 item 11: "새 코드에 테스트가 하나도 없습니다") using a tiny synthetic granule fixture: bit-width/units checks, the K = 4 contextual rule, the 15 km target / 30–80 km ring geometry, and a regression pin on `data/processed/detection/gk2a_detection_floor.json` values. (c) SESSION19 items 10 (FD-vs-LA cadence check) and 12 (cross-fire background contamination for 강릉/홍성) only if the needed intermediates are committed under `data/processed/detection/`; otherwise file a NEEDS_HUMAN (NOAA S3 is not reachable from the sandbox proxy).
- **Effort:** one lap. **agent_doable:** true for (a)(b); (c) conditional.
- **Constraints:** never say "every fire" (3 of 6); never rewrite the KMA-key direction experiment (`docs/gk2a_direction_experiment.md`) as a trigger item; the confabulated "1.28 ± 0.79 km" figure must not appear.
- **Done when:** tests exist and pass in the sandbox; the card text is in `docs/auto/finals/` and JUDGE_QA; registry keys cited.

### WFG-017 · P0 · KCF · `web/finals.html` refresh v2
- **What:** the committed screen was built 2026-08-15 at `c22ee5d9` and carries no Session 19/20/22 content. Add EVIDENCE/RELIABILITY cards, each with a 「근거」 pointer: operating point (WFG-019: PR curve, recall 0.138/0.0867, three folds at TP = 0 with `n_positive` shown so it reads as prevalence); detection floor (WFG-021); horizon grounding (Session 20: 79.23% of 2,008 fires contained ≤ 240 min; ≥ 100 ha median 4,025 min; `docs/horizon_grounding.md`); refuge placement (Session 22: one refuge covers 20/24 failing OSM-building "households", two cover 24/24 — with all three red caveats: OSM 124-building proxy, reachability-not-safety objective, 0/120 survival-filter events, counts 잠정 pending footprints); the reconciliation sheet as a RELIABILITY card only in the NEAR-labelled prose form permitted by WFG-018's constraints. Rebuild with `scripts/build_finals.py --verify` so the SYSTEM INTEGRITY panel records the gates; run `scripts/check_screen_assets.py web/finals.html` and the 17 tests in `tests/test_finals_screen.py`. No em-dashes (font subset). Region literals forbidden in the template.
- **Effort:** one lap. **agent_doable:** true — the sandbox has the geospatial stack via pip; if `build_finals.py` fails on a missing git-ignored input, emit the card payload as JSON under `docs/auto/finals/` with instructions and file a NEEDS_HUMAN for the student to run `make finals` locally.
- **Constraints:** `docs/finals_demo_plan.md` §1 (offline gate strict; no `fetch(`, no external URL); §5.19 caveat on every 영덕 absolute; never put reverted-field numbers on the screen; `web/finals.html` references `web/assets/fonts/` — do not inline fonts (size) and do not break the paths.
- **Done when:** rebuilt file with `built_at_commit` on `auto/dev`, gate panel showing the gates ran, `check_screen_assets` and the 17 tests green, a screenshot per act attached to the report.

### WFG-003 · P0 · KCF · Finals screen audit + 5-minute demo script — keep
- As in `docs/auto/BACKLOG.md`, run **after** WFG-017 so the mapping table covers the new cards. The script follows `docs/FINALS_DEMO.md`'s four acts and adds one interruption sentence per judge type; it says "about 25 seconds" for trigger→dispatch.
- **Done when:** `docs/auto/DEMO_SCRIPT_5MIN.md` exists; every on-screen figure maps to a registry key; `check_screen_assets` green.

### WFG-016 · P0 · ISEF · AI ledger current — revise
- **What:** as written, plus: (a) `docs/auto/FORM_2A_DRAFT.md` lists AI-generated code by directory and commit range and where the prompt log is; (b) an IEEE-style acknowledgment draft naming the AI system and identifying the AI-generated code and sections (IEEE requires this — https://journals.ieeeauthorcenter.ieee.org/become-an-ieee-journal-author/publishing-ethics/guidelines-and-policies/submission-and-peer-review-policies/); (c) a "hand-written only" list in `AI_DISCLOSURE.md`: ISEF research plan, abstract, poster, citations (rule #8) — the loop never drafts these for submission; (d) note pending WFG-022's answer on KCF disclosure.
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

