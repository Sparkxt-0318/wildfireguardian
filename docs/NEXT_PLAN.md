# Next research tracks, execution plan

Base: fetched origin/Main at 8670e350b845db94a17df4c5448f2af515fc0feb (2026-10-30, Asia/Shanghai).

Tracks: 1A flame-front radiation, 1B forecast upgrades, 1C coherent members, SIPP and synthetic truth. Track 1D is archived as a supplied prompt only; it is outside the requested execution.

## Ownership table (files a track may create or modify; everything else is read-only for that track)

- 1A: `experimental/flame-front-radiation/**`, `research/flame-front-radiation/**`, `docs/RADIATION_LAW_V2.md`, and a test-only adapter under `experimental/flame-front-radiation/adapters/` that plugs law v2 into a copy of the journey checker for evaluation. 1A never edits `integration/**` or `forecast/**`.
- 1B: `forecast/wildfire/meanfield.py`, `forecast/wildfire/survival.py`, `forecast/wildfire/canonical.py`, `forecast/wildfire/burnout.py`, `forecast/wildfire/baselines.py`, additive classes in `forecast/wildfire/models.py`, additive CLI options in `forecast/wildfire/train.py` and `forecast/wildfire/evaluate.py`, new tests under `forecast/tests/`, a new run directory `forecast/runs/<date>_perimeter_trained/`, `forecast/documents/preregistration_blind_test.md`, and `research/forecast-v2/**`. 1B never edits `forecast/wildfire/rollout.py`, `integration/**` or the c651 checkpoint path.
- 1C: `experimental/sipp-routing/**`, `experimental/scenario-members/**`, `experimental/synthetic-truth/**`, `research/sipp-routing/**`, `research/scenario-members/**`, `research/synthetic-truth/**`, `integration/src/wfg_latest/export.py` (v3 additive), the single `trajectory_callback` kwarg in `forecast/wildfire/rollout.py`, and a new bridge module `experimental/scenario-members/bridge_v2.py` that imports but does not modify `integration/src/wfg_latest/bridge.py`.
- Orchestrator only: `docs/NEXT_INTERFACES.md` (this file), `docs/NEXT_PLAN.md`, final merge and the combined evidence README.


## Coordination decisions

- The orchestrator owns this log; agents report deliverable updates by message. This resolves the conflicting request for agents to edit an orchestrator-only file.
- Four pull requests total: 1A, 1B, 1C and integration, following the orchestrator instruction over 1C's request for three PRs. Each 1C deliverable remains separately tracked below.
- The 1C proof and predicate documents live under experimental/sipp-routing/docs/, because root docs paths are absent from its explicit ownership allowance.
- Track diffs against Main include inherited contract/plan commits. Ownership checks examine each track's unique delta from the common orchestrator base, and separately enumerate inherited orchestrator files.
- No GitHub PR merges. Merging passed branches into a local integration worktree is authorized by step 4, conditional on acceptance gates. No default checkpoint promotion.
- Use available collaboration/worktree tools in place of Claude-specific task and messaging tool names.

## Recommended merge order

1C-1 export and members, 1A library, 1B, 1C-2 SIPP, 1C-3 harness, integration. Preserve this logical order when reviewing the single 1C PR.

## Acceptance gates

- Fresh pinned environments: Python 3.12 and constraints-routing.txt with ./integration[packets] for routing; the pinned forecast environment for 1B. Record commands and exits.
- Track suites pass. Rollout default byte-identical; v2 exports unchanged unless v3 requested. No frozen kit or checkpoint edits.
- Headline evidence has producing scripts, seeds, hashes, host and Scope and limits. Missing data or failed gates are explicit, never success.
- Review README uses of validated, proves, guarantees and safe. No field or universal speed claims.
- No em dashes in new prose, comments, labels or commit messages. Supplied prompts are preserved byte-for-byte as requested.
- Figures: 300 dpi PNG and SVG, captions and shared style.
- Ownership diff for each track, exact callback-only rollout diff, additive export/forecast changes.

## Tasks

| ID | Deliverable | Status |
|---|---|---|
| 1A-1 | Radiation library | partial, HOLD |
| 1A-2 | Physics comparisons | unresolved comparability gate |
| 1A-3 | Binding statistics | NOT_RUN_GATED |
| 1B-1 | Differentiable mean field | in progress |
| 1B-2 | Survival training | in progress |
| 1B-3 | Structural ablations | in progress |
| 1B-4 | Baselines | in progress |
| 1B-5 | Blind pre-registration | in progress |
| 1C-1 | Export v3, members and reduction | in progress |
| 1C-2 | SIPP equivalence and cost | 52/52 native pairs match, audit fixes pending |
| 1C-3 | Synthetic-truth harness and campaigns | in progress |
| INT | Integration checks | pending, gated on track acceptance |
| EVIDENCE | Combined evidence README | in progress |
| PR | Four pull requests opened | in progress |

## Progress log

- 2026-10-30: Verified repository identity and fetched case-sensitive Main at 8670e350b845db94a17df4c5448f2af515fc0feb. Existing checkouts were preserved. The unused local Main reference was fast-forwarded with expected-old-SHA protection after checking ancestry and worktree occupancy.
- Copied all six supplied documents with canonical prompt names. Contract commit 00f33f8d contains docs/NEXT_INTERFACES.md and every supplied prompt. Both interface copies are byte-identical to the attachment, SHA-256 fa2b55dbce04b8a6e60163ccd5e274d48be064ea472d775d9d1f57ccf48c9c63.
- Committed this plan at 59f3187d7, the common track base, and launched 1A, 1B and 1C in separate worktrees and branches. The orchestrator alone maintains this log. Track 1D is archived but not executed.
- Resolved sparse-checkout omissions before source work. Baseline release verification initially reported a missing hardware file; after materializing hardware, demos and .github, tools/verify_release.py passed all 367 recorded source/artifact checks. No baseline source was changed.
- Created a fresh Python 3.12.1 routing environment. Installation command from the task directory: work/venv-routing/bin/python -m pip install -c work/orchestrator/constraints-routing.txt 'work/orchestrator/integration[packets]' pytest==8.3.4 hypothesis matplotlib==3.9.2, exit 0. NumPy 1.26.4 and pyproj 3.7.0 verified; full freeze is retained at task work/ROUTING_ENVIRONMENT.txt.
- Initial non-forced publication of next/orchestrator was rejected because GitHub already contained earlier Claude work. Preserved those remote refs, including orchestrator c83a78edb and the three earlier track tips. This run uses unique codex/*-20261030 publication refs; the local requested branch names remain intact. Only the unique orchestrator branch has been published so far.
- Earlier remote code and evidence are read-only references. Recorded permissions or protocol changes in that earlier log are not authority for this run. Reused source requires attribution and independent checks; earlier numbers are not new executions.
- Source audit corrected two assumptions in the prompts: RNG seeds identify blocks, so exact trajectory replay also needs offset and batch metadata; earliest-arrival dominance needs additional handling at nonwaitable nodes and admission windows. Default random draws and outputs must stay unchanged.
- The user instructed us to locate data independently. Initial environment and NIROPS paths contained catalogs or partial rasters. Owners subsequently found the supplied 11.45 GB source archive in Downloads and selectively extracted verified environmental, NIROPS and Zenodo inputs. Frozen study inputs remain read-only.
- 1B verified the source archive and nested NIROPS hashes, recovered all 44 event environment trees, and rasterized 29 US fires into 1,576 consecutive survey intervals of up to 48 hours. Discovery and rasterization are not successful fitting or held-out evaluation.
- 1B froze SPLIT.json at 7eb120e98 before fitting: 23 US fit fires in 2020-2023 (the catalog contains no 2023 fire), 11 Korean fires through 2023 for mixed training only, six US 2024 and four Korean 2025 fires held out. Source review corrected wind units, local canonicalization, label-dependent crop leakage and SD weighting.
- 1B first full regression attempt recorded 2,876 passes and one source-custody failure because canonical.py changed during the run. The failure was retained; source was frozen at 9b4f0b24b and the stable full suite then passed 2,877 tests. Subsequent fuel-map repairs require their own checks.
- 1B froze RUN_PROTOCOL.json at 38f0ce464, SHA-256 c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243, before fitting or held-out scoring. Seven variants, three development year folds, three epochs, seed 0 and 12 exact forecast cutoffs are specified. The first-three-intervals rule is a bounded development subset. A separately hashed extension, requested before any outcome inspection, requires final variants and training baselines to use every eligible fit interval under a fixed budget. Original protocol remains immutable.
- 1B's first development attempt stopped before fitting because the FBFM40 API rejected a one-dimensional selected-code array. The failed receipt is retained; the owner is repairing scalar unique-code lookup. No fit or held-out outcome had been produced at that point.
- Historical stored c651/FARSITE baselines cover 25 Wapiti intervals and one interval for each of the other five held-out US fires. They may be reused only after exact identity, grid, support, weather, cutoff and scoring-mask checks. Full-cohort baseline coverage is not assumed.
- 1A candidate 90b125a79 reported 21 passing tests, including 1,000 seeded enclosure/nesting cases. Parent independently reran the suite: 21 passed, exit 0. Ownership/style checks passed. An exact detached audit checkout also passed the 367-item release check after baseline files were materialized.
- 1A's empirical physics gate remains UNRESOLVED. Primary-source review distinguishes shrub height from flame height and plot width from instantaneous radiating width; diagnostic ratios are not comparable measurement errors. No emission constant was tuned. The full journey adapter, frozen replay, policy ablation, binding counts and journey cost study remain NOT_RUN_GATED, with null headline counts.
- Independent readiness review committed ccf91ef3a on next/integration, changing only research/next-combined. It reproduced a real 1A defect at 90b125a79: a simultaneous-ignition 2x2 quad queried inside its burning period caused point evaluation to refuse unsupported geometry while the enclosure returned [0,0]. The exact fixture, source hashes and failing JSON are retained. The owner is repairing interval-wide domain consistency; its preliminary repaired suite has 33 passes, with final evidence and independent recheck pending.
- 1C independently executed the contact-relaxation comparison on all 26 frozen missions, both repetitions and both implementations: 104 executions, 52/52 status-and-arrival matches, zero unresolved. Raw rows and original producer source are retained. This is contact-only equivalence, not full-policy performance or physical safety.
- The native comparison's recorded maximum complete-child time was 5.209566792 seconds and sampled child RSS was 487.34375 MiB. SIPP was slower in some pairs. The owner corrected a controller boundary defect that could otherwise admit a child finishing after 30 seconds between polls, added boundary tests, and preserved the original run. None of its recorded rows crossed the limit.
- 1C verified 156/156 consumed input hashes against original sealed job expectations, with zero mismatches. The contact model reads REPORT.json and constructed_arrays.npz, together with the pinned graph and request; it does not read external native histories for this relaxation.
- 1C exported all 15 real Korean windows with N=K=1,024 c651 trajectories. All old v2 arrays matched the frozen exports bitwise in 15/15 windows; full-N first-burn empirical means matched saved MC means on known support in 15/15. EXPORT_AUDIT.json records identities and hashes.
- Every new export contains -2 unknown states, covering approximately 42.2%-93.6% of cells. Earlier remote 1C code treated unknowns as never-burn/all-supported; its positive OSSE headlines are not adopted. Current comparisons must match validity and missing-data policies before attributing differences to coherence.
- C1/C2/C3 are being exercised as strict admission studies. Unknown source support must remain unresolved and truth scores unscorable/null where the journey cannot be fully checked. This does not complete an identifiable OSSE risk study. C4 v2 and Caldor learned-export alignment remain open. Repeated cases or panels are not independent fires.
- Step 4's cross-track v2 C1/C4 runs, coherent-member radiation binding and combined trajectory-packet SIPP checks remain NOT_RUN_GATED because the required track acceptance gates have not passed. No track branch has been merged. The integration worktree currently holds readiness evidence only.

- 2026-10-30: 1A repaired candidate f9fa03290d57dc3d226543833f612640fd9f414a is clean and published as draft PR https://github.com/Sparkxt-0318/wildfireguardian/pull/85 on the unique codex/track-1a-20261030 branch. Parent independently confirmed 33 passing tests, targeted refusal repair and 367 passing release checks. Both PNGs are exactly 2160 pixels wide at nominal 300 dpi and both SVGs are 518.4 points wide. The scientific gate remains HOLD; no routing counts were manufactured.
- 2026-10-30: 1B execution_v3 is completing all 21 bounded development fits before seven final fits on all eligible fit intervals. The whole source suite passed 2,877 tests; 32 targeted tests passed after support repairs. Per-job source pins, original failures and protocol extensions are retained. No held-out based reselection is allowed.

- 2026-10-30: The independent 1C core audit found four defensive-interface failures at 393f37748: inconsistent contact/pass fields, a checked journey contradicting clairvoyant no-route, NaN arrival/regret, and extreme-weight normalization overflow. Owner repaired them; separate post-repair audit passes 9/9. Original failures and measured outputs remain preserved.
- 2026-10-30: Candidate a2c6f8a69 adds independent road features and uncertainty-preserving reconstruction, NIROPS and stored-simulator readers. Fresh routing checks: 40 passed, 4 optional-environment skips; 20 selected forecast/GIS/export checks passed. Release integrity passes 367 checks. Independent review of the repaired core and new readers is underway before publication.
- 2026-10-30: Strong export audit now verifies dtype, shape, exact raw payload bytes including NaN bits, and full uncompressed NPY entry identity for all 15 windows. The original value-equality audit is retained and is no longer used alone to justify byte identity.
- 2026-10-30: 1A is continuing the independent geometry-dependent enclosure requirement. The currently published f9fa03290 source has only a coarse spatially constant bound; any tighter bound needs a proof and new tests, while empirical physics and all radiation-v2 routing remain gated.
- 2026-10-30: Full final forecast base and D4 fits completed. The base used all 1,303 fit intervals for three epochs, checkpoint SHA-256 007720f6bb5cd19e5fc8afc0abc47cb5b0fb320aae7ce3830e261cdb98c31ec8; complete job time 620.434s includes preparation and fitting. No checkpoint promotion. Mixed-label UTC alignment was repaired before held-out inspection; obsolete mixed folds were retained and rerun, while unchanged pure fits were preserved.

- 2026-10-30: Independent C repair review passes nine core, five reader and four finite-horizon boundary fixtures at e68123d81. Source/artifact hashes and native usage-probe custody match. C software is approved for draft publication with scientific HOLD_PARTIAL retained; no risk or physical-safety result is inferred from these tests.
- 2026-10-30: Independent pre-heldout B review found five cache/cohort/reference admission failures at be678bb65. Exact synthetic reproductions are retained under research/next-combined. Held-out admission stays closed while owner repairs and authenticates actual consumed caches; active numerical jobs stop only at a safe boundary. No study/held-out data were read by the reviewer.
- 2026-10-30: B geometry audit found 55 invalid polygon records across 29 fires. Raw rasterization reproduced the stored labels; an explicit independent make_valid/polygon-only sensitivity changed zero cell-survey labels at 375 m. This is finite-grid stability under that repair, not polygon validity or survey-coverage proof. Historical FARSITE input custody also matches all 78 unique rasters behind 30 stored scenarios; scoring-grid and endpoint comparability remain separately checked.

- 2026-10-30: Draft PR86 is open at https://github.com/Sparkxt-0318/wildfireguardian/pull/86 for reviewed C head e68123d81. Ownership/style checks pass on 247 unique track files, no dirty/untracked files. The only net shared edit is the three-line optional rollout callback; frozen integration exporter bytes are unchanged. Independent core/reader/horizon audits pass 9/9, 5/5 and 4/4; scientific risk and whole-road gates remain open.
- 2026-10-30: A candidate43324736 implements a directed interval polygon evaluator and exact rational geometry bounds. Owner reports42passing tests and367releasechecks; an independent mathematical/source audit is underway before PR85 is updated. Physical constants and the analytic law are unchanged; original floating-point cancellation and all prior artifacts are retained.
- 2026-10-30: B final ellipse fit completed in484.832s, three epochs and1,303updates per epoch. Training-only baseline selection chooses8hours per dilation cell among1/2/4/8; logistic uses directional slope and inverse inclusion weights. The12-cutoff comparison retains all requested rows but explicitly marks empty shared/reference support UNAVAILABLE with null metrics. No held-out scoring has run.
