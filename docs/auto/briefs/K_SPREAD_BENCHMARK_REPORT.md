# K-SPREAD-2025 benchmark — Stage 1 build report

**Written 2026-09-14 by a laptop session on `auto/dev`, in a worktree at `../wfg-benchmark`;
the main checkout was not written to. Brief: `docs/auto/briefs/K_SPREAD_BENCHMARK.md`.
Protocol: `docs/benchmark/K_SPREAD_2025.md` v0.1, frozen, unchanged by this session.
Full leaderboard and every caveat: `docs/benchmark/results_v0.1.md`.**

Stage 1 is complete. Stages 2, 3 and 4 did not start, because the brief's Stage 0 files are
not in `data/raw/` and there is no `MANIFEST.json` there — §5 names exactly what is missing.

## 1. What ran

| new file | what it is |
|---|---|
| `scripts/benchmark/kspread_truth.py` | truth under `docs/regrade_three_way.md` §2 (A1–A6); a transcription of `scripts/regrade_three_way.py`'s `first_seen_grid` / `earliest`, with the horizon classes derived from them |
| `scripts/benchmark/kspread_metrics.py` | the four protocol §5 metrics, and the six scorer conventions C1–C6 declared in its docstring |
| `scripts/benchmark/build_entrants_v0_1.py` | writes the E0 and E3 entrant bundles from committed artifacts, with source sha256 |
| `scripts/benchmark/score_kspread.py` | the scorer; writes `data/processed/benchmark/<entrant>/<event>.json` and `leaderboard.json` |
| `scripts/benchmark/render_results_v0_1.py` | appends §8 of the results page from those artifacts, so no number is transcribed by hand |
| `tests/test_kspread_scorer.py` | 16 tests: the reference-implementation equivalence, the indeterminate exclusion, the complex rule, the track separation, the 100 m upsampling identity <!-- collision-ok: 100 --> |
| `docs/benchmark/results_v0.1.md` | the leaderboard page: what ran, the conventions, what it cannot say |
| `data/processed/benchmark/**` | entrant bundles, per-event scores, `leaderboard.json` |

Commands, all on `.auto/venv/bin/python` (3.11.15, `pins_ok: true`, `stack_ok: true`):

```
python scripts/benchmark/build_entrants_v0_1.py
python scripts/benchmark/score_kspread.py --with-decision-shift
python scripts/benchmark/render_results_v0_1.py
python -m pytest tests/test_kspread_scorer.py -q
python scripts/auto/gates.py --mode full          # exit code 0 (§2)
```

Two things were verified against something other than the scorer, because a scorer that
grades itself has measured nothing. The canonical 458-origin scan re-derives in this worktree
before any entrant is scored, and the run stops if it does not. And every AUC and IoU in the
table below was re-derived by hand — the AUC through a Mann-Whitney U rank sum with no
`sklearn` in the path, the IoU as a ratio of two counts — and all twelve values agree to six
decimal places with what the scorer wrote.

## 2. Gates, and the red baseline that resolved itself while this ran

`--mode quick` was green at the start of this session. `--mode full` was not:
`tests/test_finals_payload_rederives.py::test_every_value_the_screen_displays_is_what_the_builder_derives_today`
failed, and it failed identically in a **pristine detached worktree of `origin/auto/dev` at
`37a441a` with nothing of this session in it** — three embedded base64 hill-shade PNGs on the
judged finals screen did not match what the builder derives today.

**This session's first reading of that was wrong, and the wrong reading is recorded here
rather than quietly dropped.** It inferred that the screen had been built before the F12–F16
figure set landed and never rebuilt, drafted an NH-061 BLOCKER saying so, and prepared to park
this work on an `auto/red/...` branch. While the decision-shift sweep was still running, the
author's HQ session pushed `abe5512`, which names the actual cause: `7750d8f` rebuilt
`web/finals.html` with one machine's PNG encoder, and a different encoder writes different
bytes for pixel-identical hill-shades. The gate was comparing encoder bytes. It now decodes the
data-URIs and compares RGBA arrays. Nothing was stale. The NH-061 draft was deleted unpushed —
a ledger entry carrying the wrong root cause is worse than no entry — and this work was rebased
onto `abe5512` and pushed to `auto/dev` as the brief asked.

Gate results at the pushed commit:

| gate | result on the rebased commit |
|---|---|
| `make verify` — numbers, forbidden strings, withdrawn claims, region literals, arm isolation, gate invocations, arm controls, declared deps, artifact manifest, number collisions, README figures | PASSED, 38.6 s |
| `snapshot-verify` | PASSED |
| `env-check` | PASSED |
| `baseline-verify` | WARN, soft here (see below) |
| `pytest-full` | 2,320 passed, 65 skipped, 3 xfailed — no failures |
| of which `tests/test_kspread_scorer.py` | 16 passed |
| **`gates.py --mode full`** | **ALL GREEN, exit code 0** |

Those are the results on this work rebased onto `abe5512`, before the amendment that added this
table. The gates were re-run on the amended commit too, and `scripts/auto/gates.py --assert-head`
was run immediately before the push, so the commit on `origin/auto/dev` is the commit the gates
read.

`baseline-verify` is soft by design here: it digests two manifests under
`data/raw/firms_data/` that exist only on the author's laptop and are absent from any fresh
checkout. `--assert-reported` was not run — it requires a new file under `docs/auto/reports/`,
and the harness that writes those is paused; the brief put this lap's report here instead.

## 3. The leaderboard

One event (영덕 2025), two entrants, and they are **in different tracks and are not
comparable** (§4 below). Metric 3 is the one the protocol says matters.

**Metrics 1 and 2, truth at *m* = 0, indeterminate cells excluded from both.**

| track | entrant | ROC-AUC 3 h / 5 h / 8 h | IoU at p ≥ 0.5, 3 h / 5 h / 8 h |
|---|---|---|---|
| forecast | E0 persistence | 1.0000 / 1.0000 / 0.6329 | 1.0000 / 1.0000 / 0.2657 |
| hindcast | E3 WFG canonical (leave-one-complex-out) | 0.9990 / 0.9990 / 0.9791 | 0.8272 / 0.6368 / 0.3606 |

**Metric 3 — arrival-time error at the 8,443 nodes of the canonical walk network**, cell
membership, window = the entrant's own last surface (720 min). The observation burns 1,772 of
those nodes inside the window. Signed error is model minus observation, so positive is late.

| track | entrant | nodes it burns | median abs error | false-safe | false-safe rate | false alarms |
|---|---|---:|---:|---|---:|---:|
| forecast | E0 persistence | 275 | 0.0 min | 1,497 of 8,168 | 0.1833 | 0 |
| hindcast | E3 WFG canonical | 281 | 0.0 min | 1,494 of 8,162 | 0.1830 | 3 |

**Metric 4 — decision shift**, 19,250 도로명주소 주건물 on 4,970 walk nodes, the committed
time-aware policy with only the hazard field changed.

| track | entrant | buildings whose LSD class changes | of which entrant is more optimistic |
|---|---|---:|---:|
| forecast | E0 persistence | 3,906 | 3,906 |
| hindcast | E3 WFG canonical | 3,898 | 3,879 |

The observation-graded field says 3,906 of the 19,250 buildings have an evacuation window that
closes inside 600 minutes — 2,645 before the 5-hour mark and 1,261 after it. **Persistence flags
none of them**: it puts every reachable building in the censored class. **E3 flags 34**, of
which 27 do close (15 in exactly the right class, 12 that close after 5 h which E3 places
before it) and 7 do not. So E3 finds 27 of the 3,906 closing windows and is more optimistic
than the observation for the other 3,879. Both fields agree with the observation on the 190
buildings that are never safe, at any departure.

## 4. Three things the build measured that no one asked it to

**(a) The committed WFG field is a hindcast, by the project's own protocol.**
`forward_simulate` advances each step 「with the next step's real weather」 — ERA5 reanalysis at
times *after* T0 (`src/wildfireguardian/spread_v2/forward_sim.py`, steps 2 and 5). Protocol §3
puts any entrant that reads an observation after T0 in the hindcast track, reported separately
and never beside a forecast-track score. So E3 sits in the second table, and every claim of the
form 「our forecast beats X」 that rests on the committed 영덕 field is unsupported until a
forecast-track entrant exists. The same model on a KMA 초단기예보 issued before T0 would be
one; it is not committed, so it was not scored. This is the finding that most changes what the
project may say out loud, and it was produced by applying the project's own rules to itself.

**(b) The 영덕 observation cannot grade a 3-hour or a 5-hour forecast at all.** The overpasses
are at 0, 333, 1005, 1480, 1812 and 2403 minutes after T0. Nothing observes the fire between T0
and 333 minutes, so the 3 h and 5 h horizons have **identical truth**, and all 688 cells first
seen at 333 minutes are indeterminate at both. That is why E0 persistence scores a perfect
1.0000 AUC and IoU at 3 h and 5 h: it reproduces the T0 footprint exactly, and the T0 footprint
is the whole of what the observation can confirm by then. A perfect score there is an artifact
of the overpass schedule, not skill, and reading it as skill is the mistake this page exists to
prevent. Under the honest floor of *m* = ∞, 774 of the 1,023 ever-detected cells are
indeterminate at 3 h.

**(c) At the road nodes, the WFG field differs from 「nothing spreads」 by three nodes.** E3
calls 291 cells burned that E0 does not, and 142 of those the observation confirms. But only
**3** of the 291 contain a road node at all, holding **6** nodes between them. The canonical
walk network touches 1,009 of the canvas's 28,236 cells: the model's advance is onto forested
slope the road network does not cross. So the false-safe rate moves from 0.1833 to 0.1830, and
the median absolute arrival error is 0.0 min for both entrants because the nodes they both call
burned are the T0 nodes, where the observation also says zero. On the metric the protocol calls
the one that matters, the committed field's advantage over persistence is three nodes — while
on the ranking metrics (AUC at 8 h: 0.9791 against 0.6329) it is large. Both readings are true
and they are about different questions: E3 ranks cells far better, and it does not cross p ≥ 0.5
anywhere that changes a road node's verdict. 4,176 of the nodes E3 calls safe still carry a
non-zero probability at its last surface, so C1's clamp may be hiding later crossings for them;
that is counted in the artifact, not corrected.

## 5. What could not run, and why

| blocked | why |
|---|---|
| Stage 2 (E1 wind-cone, E2 Rothermel-class) | Stage 0 items 1–2 absent. `data/raw/` holds only `kfs_fire_statistics/` and `README.md`; no `MANIFEST.json`, no 임상도, no KMA AWS/ASOS files. The brief's own gate says stop. |
| Stage 3 (E4 gust-aware WFG at 100 m) | Stage 0 items 1–3 absent, same evidence. <!-- collision-ok: 100 --> |
| Stage 4 (E5 NIFoS issued maps) | the 정보공개청구 has not returned. |
| 5 of the 6 protocol §2 events | scoring needs a committed per-cell observed detection stack. Only 영덕 has one (`routing_demo_canonical.npz` → `obs_stack`). 의성·안동 2025 and 울진·삼척 2022 have committed model fields and no observation; 강릉 2023, 홍성 2023 and 밀양 2022 have neither. Rebuilding any of them needs the git-ignored raw FIRMS/ERA5/DEM bundle, which a fresh checkout does not carry. |
| protocol §5's mean-over-events and worst-event | one event scored. A mean over one event is that event, so neither is reported rather than reported misleadingly. |
| a forecast-track WFG entrant | needs a KMA forecast issued before T0; see §4(a). It is the single highest-value next row. |

Nothing was regenerated: no figure under `docs/figures/` was rebuilt, no number was added to
`docs/NUMBERS.json`, and no new pip dependency was introduced (`check-declared-deps` green).
Three committed files changed, all additively: `.gitignore` gained a whitelist block for
`data/processed/benchmark/**` (the artifacts are small and a test reads them, so an untracked
one would fail a fresh clone); `docs/auto/NEEDS_HUMAN.md` gained NH-061; and
`docs/artifact_manifest.json` was rebuilt as the brief asked, which moved exactly one line —
its `generated_at_git_commit` stamp — because the benchmark's artifacts are cited by no
`NUMBERS.json` entry and so do not enter the manifest yet. The benchmark's numbers are deliberately unregistered
and none is on a judge-facing surface, which is the standing `docs/regrade_three_way.md` took;
`docs/benchmark/results_v0.1.md` §5 says why, and says that a number quoted at the booth gets
registered first.

## 6. Where a reviewer should attack this

1. **One convention changed after the first run.** C5 first read 「every walk-network node the
   canonical routing scans」 as the canonical scan's 458 origins. On that set the metric is
   degenerate by construction — `candidate_origins` refuses an origin already in the fire, so
   almost no origin node is one an entrant can burn, and on the first run every entrant burned
   2 of the 458 and the median was over those 2. The primary set is now every node of the
   canonical walk network and the origin subset is reported unchanged beside every row. The
   argument is structural and applies identically to both entrants, but it is still a
   convention that moved after a number was seen, and it is recorded as such here and in
   `results_v0.1.md` §3 rather than quietly.
2. **Metric 3's window is a choice the protocol does not state.** Scored against the whole
   observation record, an entrant is charged for road nodes the fire reached after its horizon.
   The headline uses the entrant's own last surface; `whole_observation_record` in every
   artifact repeats all counts against the full record (E0's false-safe becomes 1,514 of 8,168).
3. **Metric 4 reads its field through the router's bilinear sampler**, which on a binary
   footprint is the softer reading (`docs/regrade_three_way.md` §A5, §6). Metrics 1–3 use cell
   membership. The two are not interchangeable and the artifact says which is which.
4. **A5 and A4 are assumptions, not measurements.** A cell nobody detected is treated as
   unburned, at FIRMS's 375–500 m detection floor. The whole leaderboard inherits that.
5. **The track is a claim, not a check.** No gate can verify that an entrant's author declared
   the right track; `results_v0.1.md` §7 says so in the instructions for adding one.

## 7. The sentence the finals can defend

**We wrote the first public, pre-registered protocol for scoring Korean wildfire spread
prediction against observed footprints, ran our own model under it before anyone else's, and
the first thing it found was a limit in our own evidence: our committed 영덕 field is a
hindcast, and at the road nodes an evacuation decision actually depends on it differs from
「nothing spreads」 by three nodes — so the next thing we build is the forecast-track entrant,
not a bigger claim.**

## 8. The rows this opens

1. **E3f — a forecast-track WFG entrant.** Same model, weather from a KMA 초단기예보 issued
   before T0 instead of ERA5 after it. Blocked on Stage 0 item 2 (KMA API Hub key + the March
   2025 bulk files). Until it exists the project has no forecast-track score of its own.
2. **An observation between T0 and 333 minutes.** GK2A (`docs/detection_floor.md`) is the only
   candidate in reach. Without it, no 3 h or 5 h horizon in 영덕 is gradeable, for any entrant.
3. **A committed observed footprint for 의성·안동 2025 and 울진·삼척 2022.** Both already have
   committed model fields; an `obs_stack` on the same canvas would take the benchmark from one
   event to three and make protocol §5's mean and worst-event figures meaningful.
4. **Metric 3 at 100 m.** Both v0.1 entrants are 500 m and the only committed truth is 500 m,
   so the protocol's 100 m grid is presently a no-op. <!-- collision-ok: 100 -->
