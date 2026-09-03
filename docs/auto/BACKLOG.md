# Backlog — what the loop works on, in order

Conventions: `docs/auto/CHARTER.md` §5. **P0** ships before the 2026-10-10 freeze,
**P1** before the 2026-10-18 finals, **P2** after the finals (ISEF), **P3** for the
IEEE paper. Status: `todo | in-progress(<stamp>) | done(<commit>) | blocked(NH-###)
| dropped(why)`. The dev routine takes the first `todo` row that is agent-doable and
unblocked. Rows come from the 2026-09-03 research brief
(`docs/auto/research/RESEARCH_BRIEF_2026-09-03.md`), from `docs/BLOCKERS.md`,
from `docs/HANDOFF_ROUND3.md` §4, and from every critic lap.

| ID | P | goal | title | status | rubric rows | done when | constraints |
|---|---|---|---|---|---|---|---|
| WFG-001 | P0 | infra | Clean-Linux green: bootstrap + full gates pass in the sandbox and in `auto-gates.yml` | in-progress(20260903T0513Z) | 데이터 수집·분석·해석 (재현 가능성) | `.auto/gates.json` passed=true from a cloud lap and a green Actions run on `auto/dev` | no artifact changes; env fixes only |
| WFG-002 | P0 | KCF | Judge Q&A bank v2 (`docs/auto/JUDGE_QA.md`): the hardest hostile questions, each answered with the artifact that proves it or an honest "not measured" | todo | 연구 목적 · 설계와 방법론 · 데이터 해석 | ≥ 30 questions, every answer cites a file path or NUMBERS key; critic lap finds no unanswered P0 question | Korean; no new numbers |
| WFG-003 | P0 | KCF | Finals screen audit: every number, label and legend on `web/finals.html` traces to `docs/NUMBERS.json`; 5-minute demo script (`docs/auto/DEMO_SCRIPT_5MIN.md`) with per-act timings and the sentence to say when each judge type interrupts | todo | 제출 자료 · 구현 및 유용성 | script exists; `scripts/check_screen_assets.py web/finals.html` green; a table maps every on-screen figure to a registry key | do not rebuild screens from changed artifacts; `make finals` only if data unchanged |
| WFG-004 | P0 | KCF | SSOT sweep of judge-facing docs (README, MODEL_CARD, HANDOFF, session reports): one value per quantity, superseded values annotated, no contradiction a judge can find in a minute | todo | 제출 자료 | `check_number_collisions.py --report` shows 0 unmarked hits; `ssotize` audit report committed | annotate, never delete |
| WFG-005 | P0 | science | Decision-level uncertainty: how many Yeongdeok origins flip class under the forecast's own uncertainty (bootstrap over LOFO folds / calibration bands), reported as a stability count with CI, on the canonical field | todo | 데이터 수집·분석·해석 · 창의성 | new artifact `data/processed/decision_uncertainty/…json`, registered numbers, `docs/decision_uncertainty.md`, tests | new filenames only; 32.6 % coverage caveat on every absolute rate |
| WFG-006 | P0 | science | Wind-direction sensitivity done right: perturb `wind_alignment` inputs (±30°, ±60°) through the forward simulation and measure route-classification shifts, so the withdrawn severity-vs-direction claim is replaced by a measured statement | todo | 설계와 방법론 · 데이터 해석 | artifact + doc + registered deltas; states what ERA5's 28 km grid can and cannot resolve | never reinstate the withdrawn ratio |
| WFG-007 | P1 | KCF | Rehearsal aids: printable A4 evidence sheet (headline numbers with sources and caveats), booth checklist for 10.18 (offline files on two USBs, laptop settings, key bindings G/R/Esc), fallback if the laptop dies | todo | 제출 자료 | files under `docs/auto/finals/`; PDF built from Markdown by a script | no new numbers |
| WFG-008 | P1 | science | Ignition-likelihood layer from KFS statistics (BLOCKERS: ~1,711 usable cause labels, 454 free-text strings to normalise) as a pre-ignition prior for the operator console | todo | 창의성 · 데이터 수집 | normalised cause table artifact, a doc with the distribution, registered counts; console integration only if it stays offline and gated | CSV is in `data/raw/kfs_fire_statistics/`; no re-scraping |
| WFG-009 | P1 | infra | Playwright smoke of `web/finals.html` in CI (loads offline, four acts advance, no console errors, screenshot per act as an artifact) | todo | 구현 및 유용성 | `auto-gates.yml` job `finals-smoke` green with 4 screenshots | headless chromium only; no change to the screen |
| WFG-010 | P1 | KCF | Round-4 section of the README: what changed since Round 3, in the same honest register, with links; ISEF-facing English abstract (250 words) from registered numbers | todo | 제출 자료 · 연구 목적 | README §Round 4 exists; `docs/auto/ABSTRACT_EN.md`; forbidden scan green | keep Round-2/3 sections intact |
| WFG-011 | P2 | ISEF | ISEF category memo and 12-month-window plan (what counts as Jan–May 2027 work), forms list (1, 1A, 1B; Form 7 continuation), AI-use disclosure text | todo | — | `docs/auto/research/ISEF_PLAN.md` | rules verified against the current ISEF rulebook with URLs |
| WFG-012 | P2 | science | Cross-region generalisation: repeat WFG-005/006 on 의성·안동 and 울진·삼척 with the completeness covariates beside every number | todo | 데이터 해석 | artifacts for both regions; covariate table carried | §5.7, §5.12, §5.14 |
| WFG-013 | P2 | science | Open building footprints for Yeongdeok: check whether an open global dataset (e.g. Microsoft Global ML Building Footprints, Overture) covers the walk bbox; if yes, run the scripted real-footprint replacement and compare household counts to the 124-building OSM snapshot | todo | 데이터 수집 | coverage finding documented; if covered, new household artifact with the OSM comparison | licences cited; NH-005 stays open until decided |
| WFG-014 | P3 | IEEE | Paper skeleton in `paper/` (IEEEtran LaTeX, built by CI to PDF): sections, figure list mapped to artifacts, abstract from registered numbers, limitations first | todo | — | `paper/main.pdf` builds in Actions; every number in it is a registry key | submission timing per RUBRIC.md rules |
| WFG-015 | P3 | IEEE | Reproducibility package: `citation.cff`, Zenodo-ready release checklist, `docs/REPRODUCE.md` verified end to end by a fresh-clone run in CI | todo | 데이터 해석 (재현) | a fresh-clone CI job reproduces the headline within the documented tolerance | no keys in CI; use committed snapshots |

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

⚠ **Two things this lap did NOT establish.** (a) The CI half of "done when" is
unverified — `auto-gates` had never once concluded green before this lap (runs
1/2/3/5 cancelled by the concurrency rule as pushes stacked, run 4 `failure`).
(b) The sandbox collects **1116** tests against the laptop baseline's **1120**
(1116 passed / 3 skipped / 1 xpassed). Four tests are not collected here and the
cause is not diagnosed; `xgboost` is absent in the sandbox but reports as a
skip, not as an uncollected test, so it does not obviously account for them.

### WFG-002 — Judge Q&A bank v2
Start from `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md` §(c) and the author's
예상질의 notes (outside the repo; summarised in the brief). Each entry: the
question, a one-sentence answer, the artifact path or NUMBERS key, and the
expansion. Group by judge type. Mark "no evidence yet" honestly; those become
backlog rows.

### WFG-003 — Finals screen audit
`scripts/build_finals.py` reads artifacts at build time; do not rebuild unless
inputs changed. Produce a mapping table from each visible figure to its registry
key by reading the template and the payload builder; any figure with no key is a
finding. The demo script follows `docs/FINALS_DEMO.md`'s four acts.

### WFG-005 — Decision-level uncertainty
Method sketch: for each of the six LOFO folds the model already produces
out-of-fold probabilities (`data/processed/spread_v2_lofo_oof.csv.gz`); build B
bootstrap resamples of the training fires or use calibration bands from
`calibration_metrics.json`; propagate the P(ignite) surface through the existing
routing classification at the canonical cutoff; report, per origin, the fraction
of resamples in which its class changes. Headline is the count of stable vs
unstable origins with a CI. New script `scripts/decision_uncertainty.py`.

### WFG-006 — Wind-direction sensitivity
Do not retrain. Use the forward simulation (`spread_v2/forward_sim.py`) with the
wind direction feature rotated, keep everything else fixed, and measure the
envelope and the routing classification shift on Yeongdeok. State plainly that
ERA5's grid resolves synoptic, not local, wind.
