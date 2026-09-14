# Report — K-SPREAD-2025 Stage 2 (the forecast-track field and the proxy ceilings)

**Brief:** `docs/auto/briefs/K_SPREAD_STAGE2.md` (HQ, 2026-09-14).
**Protocol:** `docs/benchmark/K_SPREAD_2025.md` v0.1, frozen and **unchanged** by this lap.
**Stage 1:** `docs/auto/briefs/K_SPREAD_BENCHMARK_REPORT.md`.
**Rule declared before anything ran:** `docs/benchmark/stage2_proxy_rules.md`.
**Leaderboard page:** `docs/benchmark/results_v0.2.md`, rendered from artifacts.

---

## 0. The one sentence this lap can defend

> **On the metric the protocol says matters for evacuation, the committed model finds 27 of
> the 3,906 buildings whose evacuation window actually closes; the best a crude wind-cone
> could have done finds 3,001 of them at the same precision — so what the committed field
> lacks at the road network is not forecast quality, it is reach.**

The wind that drove the fire is not on this machine, so no forecast-track entrant was run and
none was faked. What was run is a **ceiling**, and §3 says exactly what that is and is not.

## 1. Every row of the brief, and what happened to it

**Ownership.** `K_SPREAD_STAGE2.md`'s 「Ownership split (HQ, 2026-09-15)」 landed on `auto/dev`
**while this lap was running** (`d8dba6c`, read at `origin/auto/dev` before this report was
written; this branch is a PR *into* that base and does not carry it — see §9b). This session
is **Session B**, which owns **F2, the E1/E2 proxies and F3**; **F1 is Session A's row**, and
the line below reports only what this machine measured about it, not a claim on it. The
split's collision rule was honoured and checked: `data/processed/benchmark/` on `auto/dev`
holds **only E0 and E3**, so the four `e1_*` / `e2_*` bundles here are first writes and
overwrite nothing.

| brief's row | status |
|---|---|
| **F1 frozen weather** *(Session A's)* | **NOT RUN on this machine** — no ERA5 `.nc` for any fire (§2). Not this lap's row to deliver |
| **F2 산악기상 gust-aware** | **NOT RUN** — no `data/raw/mountain_weather/`, and the station coordinates its interpolation needs are not served by the API at all (§2) |
| **F3 KMA forecast at T0** | **NOT RUN: input missing** — precisely the outcome the brief names for it |
| **E1 wind-cone proxy** | **BUILT AND SCORED as a ceiling.** The forecast-track E1 is not run |
| **E2 Rothermel-family proxy** | **BUILT AND SCORED as a ceiling.** Same caveat |
| leaderboard beside E0 and E3, rendered from artifacts | **done** — `docs/benchmark/results_v0.2.md` §6 |
| decision shift on the 19,250 주건물 | **done, for all six entrants** (§5) |
| gates exit 0, read directly | **done** (§9) |
| GitHub's `auto-gates` checked after pushing | ⚠ **could not run — and this lap does NOT report green** (§9a) |

## 2. Why the three F-rows could not run, measured rather than assumed

This session is a **cloud container**, not the author's laptop. Measured here:

- a filesystem-wide search for `*era5*`, `*.nc`, `*forest_type*`, `*mountain_weather*` and
  `*kma_forecast*` outside the venv returns **only source files** — `scripts/get_era5.py`,
  `scripts/fetch_mountain_weather.py`, `docs/mountain_weather_yeongdeok.md`. No data.
- `~/.config/wildfireguardian/` does not exist and no `KMA`/`FIRMS`/`CDS`/`DATA_GO` variable
  is set, so nothing could be fetched either.
- the F1 script and the KMA script were **run**, not merely inspected. Both refuse, name the
  missing files, and exit 0 — the behaviour the previous lap built them to have. ⚠ **The KMA
  script was renamed mid-lap.** It is `scripts/run_forecast_track_f2_kma.py` on this branch
  and `scripts/run_forecast_track_f3_kma.py` on `auto/dev` after `7f2c4bd` adopted the F3
  naming. **Both were run, and the refusal is identical** — only the label in the message
  differs. This report uses the adopted naming (F3 = KMA) throughout.

⚠ **An empty `data/raw` in a fresh checkout is not evidence that the author has no data**
(commit `4994f99`). The claim is the narrow one: **this machine cannot reach the bundle.**

**F2 has a second blocker the brief did not anticipate, and it is on the laptop too.** The
brief says F2 interpolates the 산악기상관측망 record 「to the grid with terrain-aware inverse
distance」. `docs/mountain_weather_yeongdeok.md` §4 records that the API returns `obsid`,
`obsname` and `localarea` and **not station coordinates**. Inverse-distance weighting with no
distances cannot be written. F2 needs a station-coordinate table before it needs anything else.

### 2a. One thing the previous lap looked for and missed

F1's refusal lists `MISSING data/raw/firms_data/yeongdeok_2025_dem.tif`. **A 영덕 DEM is in
this repository and always was**: `data/snapshots/srtm-dem_yeongdeok-2025_20260723_66988bf5.tif`,
tracked, 5.9 MB, and the canonical routing scene loads it here without complaint. The
2026-09-14 search that concluded otherwise globbed `*_dem.tif`, which that filename does not
match. **This does not unblock F1** — the ERA5 file is the binding constraint and no DEM
substitutes for it — but it does mean `data/snapshots/` holds more of the pipeline's inputs
than the last two reports assumed, and that is why Stage 2 could score anything at all.

## 3. ⚠ What a ceiling is, and what no one may read it as

The wind at T0 is unreachable. `docs/mountain_weather_yeongdeok.md` prints extrema over the
fire window, but an extremum at one station in one hour is not the wind field over the canvas
at T0, and writing it in as though it were is the fabrication CHARTER §3 rule 5 forbids.

So each proxy was built at **720 declared wind settings** (36 bearings × 20 head rates,
`stage2_proxy_rules.md` §3) and the best-scoring one written as the entrant. That makes both
**oracles**, filed **hindcast track**, because choosing a wind by how well it matches the
outcome uses an observation after T0.

- What a row **does** say: *no wind would have let this method class do better on this fire.*
- What it **does not** say: what the method scores. **The forecast-track E1 and E2 are not run.**

A ceiling is the one form of this comparison immune to 「you gave it the wrong wind」, and it
is generous to the proxies and to nobody else — E0 and E3 were not tuned against anything.

## 4. Metrics 1–3 (full tables: `results_v0.2.md` §6.1–6.2)

**Ranking (ROC-AUC, 3 h / 5 h / 8 h):** E3 WFG canonical 0.9990 / 0.9990 / 0.9791; the E1
ceiling 0.9975 / 0.9952 / 0.9802. **The committed model out-ranks the best possible wind-cone
at 3 h and 5 h and they tie at 8 h.** On IoU at 8 h the ceiling is ahead (0.4286 vs 0.3606),
because E3 predicts 536 positive cells where the observation detects 937 and the cone predicts
1,257 — E3 under-reaches, the cone over-reaches.

**Metric 3, and the finding that it cannot be read as a headline.** The E1 ceiling's
false-safe rate is **0.0423** against E3's **0.1830**, and across the **whole** grid — not
just at the oracle — **every one of the 684 grid points with a defined rate beats E3**
(`stage2_wind_sensitivity.json`, a sweep this lap added precisely to stop that number being
over-read).

⚠ **That is an artefact of the operating point, not a win.** The **most conservative** of the
720 points burns **1,284** of the 8,443 road nodes and raises **303** false alarms; the median
point burns 6,101 and raises 4,329. **E3 burns 281 and raises 3.** Not one of the 720 points operates within an
order of magnitude of E3's alarm budget, so the two are at opposite ends of one trade-off and
the false-safe rate rewards the burn-everything end: a field covering the whole canvas scores
**0.0000** and is worthless. Stage 1 could compare E0 and E3 on this metric fairly only
because both burn about 280 nodes. **Pairing protocol §5.3's rate with the false-alarm count
is the author's call; v0.1 is frozen and this lap applied it as written.**

## 5. Metric 4 — the decision-shift numbers the brief asked for

19,250 주건물 on 4,970 walk nodes, the committed time-aware policy with only the hazard
changed. The observation says **3,906** buildings have a window that closes inside 600 min
(2,645 before the 5-hour mark, 1,261 after) and **190** are never safe.

| entrant | track | changing class | more optimistic | closing windows found (of 3,906) | flagged where truth is censored | precision | recall |
|---|---|---:|---:|---:|---:|---:|---:|
| E0 persistence | forecast | 3,906 | 3,906 | 0 | 0 | — | 0.000 |
| E1 wind-cone oracle | hindcast | 3,062 | 1,235 | **3,001** | 1,078 | **0.736** | **0.768** |
| E2 Rothermel oracle | hindcast | 3,110 | 1,231 | 3,008 | 1,115 | 0.730 | 0.770 |
| E3 WFG canonical | hindcast | 3,898 | 3,879 | **27** | 7 | **0.794** | **0.007** |

**This row is the one that is not an operating-point artefact, and it is the lap's result.**
Precision — the share of flagged buildings whose window really does close — is **0.736 for
the ceiling against 0.794 for the committed field**, near enough that the two are warning
about real closures at a similar hit rate. Recall is **0.768 against 0.007**: a hundredfold
gap. E3 is not wrong about the buildings it flags; it flags 34 of them.

**What that means, stated no more strongly than it can be.** E3's field crosses p ≥ 0.5 over
536 cells at 8 h where the observation detects 937, and the canonical walk network is sparse,
so the field is very nearly **decision-inert** at the road nodes — Stage 1 measured it
differing from 「nothing spreads」 by three nodes. Stage 2 adds that this is **not** because
the fire was unpredictable: a cone with a well-chosen wind recovers 3,001 of the closing
windows at comparable precision. The gap is reach, not skill. ⚠ And the cone had its wind
chosen with hindsight, so **how much of this a forecast-track entrant keeps is exactly what
F3 would measure and F3 did not run.**

## 6. E1 against E2 — what Rothermel's slope factor buys at 500 m

**Nothing measurable, and slightly less than nothing.** Both ceilings select the same wind
(bearing 100°, 100 m/30 min). Mean ROC-AUC: E1 **0.9910**, E2 **0.9904** — the slope term
costs 0.0005. Metric 3: false-safe 271 of 6,401 against 266 of 6,389. Metric 4: recall 0.768
against 0.770, precision 0.736 against 0.730.

That is a statement about **500 m cells on this fire**, not about Rothermel: a slope factor
computed on 500 m-averaged terrain has had the slopes that drive a fire averaged out of it.
The pair can support this comparison at all only because they share every other line —
asserted by a test that requires them to agree **cell for cell** on flat ground.

## 7. The defect a test caught before any number was reported

**E1 and E2 did not differ by one term, and the page claiming they did was written first.**
The first implementation built E1 as a **straight ray** from the nearest T0 cell and E2 as a
least-time walk over the 8-connected grid. A test written to assert 「on flat ground the pair
agrees」 failed: the walk beat the ray by up to **23 %** due crosswind, because eight headings
can zigzag between two well-aligned ones and beat a straight line. The pair therefore differed
by the slope factor **and** by how the front propagated, and every E1-vs-E2 sentence would
have been false of the code.

E1 was changed to the shared walk, the sweep re-run from scratch, and **no score from the
first implementation appears anywhere** — the only figure carried across is the 23 % that
names the artefact. The amendment is recorded in `stage2_proxy_rules.md` §2a rather than
applied quietly. A second, smaller error the same test caught: the rule page's slope
coefficient was hand-computed as 12.34 and is **12.96**; the code was right and the page was
wrong, and the page now asserts the code's value.

## 8. Two things this lap measured that nobody asked it to

**(a) Stage 1 reproduces exactly, on a different machine.** E0 and E3 were re-scored here and
their per-event artifacts are **identical to the committed ones**, key for key, apart from the
timestamp and commit stamp — a cloud container against a laptop worktree, 2.9 hours of
routing and re-planning, no drift. Stage 1's committed `leaderboard.json` was then **restored
byte-for-byte** and Stage 2's own leaderboard written to a new filename (CHARTER §3 rule 2).

**(b) The oracle's bearing agrees with the observed wind, having never seen a wind.** T0 is
2025-03-25 12:25 UTC = **21:25 KST**. The sweep selected a wind-**toward** bearing of **100°**
for both proxies. `docs/mountain_weather_yeongdeok.md` records that the network measured
**westerly** winds at exactly that hour — 25.1 m/s W at 21:11 at 울진 가재미재, 19.4 m/s W at
22:08 at 영덕 독경산. W-toward is 90° and WNW-toward is 112.5°; the selection sits between
them, one grid step from due east.

⚠ **This is a sanity check on the construction, not a discovery.** The oracle was selected to
match the burned footprint, and a fire's footprint is of course aligned with the wind that
drove it; the agreement says the cone is pointing the way the fire went, which is what it was
fitted to do. It is worth recording because it would be **alarming if it disagreed**, and it
does mean an operator with that night's 산악기상 readings would have pointed the cone within
one grid step of the oracle — which is an argument for F2 and F3, not a substitute for them.

## 9. Discipline

New filenames only; **no committed artifact modified** — verified by sha256 before and after
the scoring run, which does overwrite `leaderboard.json` and the E0/E3 per-event files and
was reverted with `git checkout` once its output was copied to `leaderboard_v0_2.json`.
Nothing registered in `docs/NUMBERS.json`; **no judge-facing surface touched**;
`scripts/benchmark/score_kspread.py` **unchanged**, as the brief required; the protocol
unchanged; no new pip dependency. 26 tests pass (`test_kspread_scorer.py` 16,
`test_kspread_stage2_proxies.py` 10). Every artifact staged by explicit path **before** the
gate, which is commit `cb41adf`'s lesson.

### 9b. Merging the base into this branch turns a gate red, and the reason is worth keeping

Before writing §1's ownership note this lap **did** merge `origin/auto/dev` in, ran the full
gates, and got **RED**: `tests/test_finals_screen.py::test_the_staleness_threshold_and_its_helper_are_both_graded`
failed with `['29 commits behind', '31 commits behind']`.

The cause is topology, not content. The test pins `_stamp_commits_behind` against
`HEAD~29` and `HEAD~31`, and the helper counts **every** commit in `stamp..HEAD`. On a linear
branch that is 29 and 31; **with a merge commit it became 34 and 36**, because the merge adds
the base's own commits to the count. Measured both ways on this branch.

So the merge was **dropped** — it was local and unpushed, `origin` never saw it, nothing was
force-pushed and the commit survives in the reflog — and the report's three corrections were
made against `origin/auto/dev` by reading it instead. **This branch is linear, its gates are
green, and GitHub reports the PR `mergeable_state: clean` against the moved base**, so the
base's commits arrive the normal way, through the merge of this PR.

⚠ **This makes the repository's 「rebase-then-merge」 convention (`d8dba6c`) load-bearing
rather than stylistic**, and that does not appear to be written down anywhere: a contributor
who merges `auto/dev` into a feature branch gets a red gate with a message about commit
counts that says nothing about merges. Worth a line in the CHARTER — **the author's call.**

### 9a. ⚠ GitHub has NOT verified this commit, and that is stated rather than glossed

The brief's rule is 「check GitHub's `auto-gates` run after pushing (a laptop green is not the
gate)」, and commit `cb41adf` exists because a local gate once went green on a file it had
never read. **So this is the one row of the brief this lap could not satisfy, and it is not
being reported as satisfied.**

`.github/workflows/auto-gates.yml` triggers on `push` to `auto/**` and `Main`, plus
`workflow_dispatch`. This session's harness pins development to
`claude/loving-fermi-2sjs7n`, which matches no trigger, so **no run fired**; a
`workflow_dispatch` on the ref was attempted and refused **403 Resource not accessible by
integration**. Measured, not assumed: the PR's combined status on `19ee42d` is
`total_count: 0` — **zero checks**.

**What this lap can say:** `scripts/auto/gates.py --mode full` is ALL GREEN on this exact
commit, exit code read directly and never piped, and `--assert-head` confirms the recorded
run is the pushed tree. **What it cannot say:** that a machine sharing nothing with this one
agrees. Two things settle it, both needing a permission this session lacks — merging or
pushing the branch to `auto/dev`, which matches the `auto/**` trigger; or dispatching
`auto-gates.yml` on this ref.

The partial-DEM worry in the rule page closed with a measurement: the committed snapshot
covers 51.2 % of the canvas but **all 249 T0 cells and all 1,023 ever-detected cells**, and
**0** cells above p ≥ 0.5 outside its coverage, for every entrant. The half it misses is the
half no fire reached.

## 10. Where a reviewer should attack this

1. **The rate optimum sits on the grid boundary.** Both ceilings select the slowest declared
   head rate, 100 m/30 min. The true ceiling may be at a slower rate still, where the cone
   degenerates toward persistence — and persistence already scores 1.0000 AUC at 3 h and 5 h
   for the overpass-schedule reason Stage 1 established. The grid was declared before the run
   and was **not** extended after seeing that, which is the right call and also a limitation.
2. **σ = 2 km smoothing is declared, not swept**, so it is a free parameter no result chose.
   It is also not what drives the proxies' reach: the halo adds 0 / 87 / 63 cells at
   3 h / 5 h / 8 h against deterministic footprints of 491 / 730 / 1,194.
3. **Metric 4 reads its field through the router's bilinear sampler** (Stage 1's point 3),
   while metrics 1–3 use cell membership. The precision/recall pair inherits that.
4. **Uniform fuel.** E2 carries no 임상도 term. Less of a departure than it sounds — the
   committed model's own land cover is `_synthetic_landcover`, 「all forest」 — but E2 is a
   slope-and-wind proxy and is labelled so everywhere.
5. **One fire, one ignition, one start time**, at 500 m, against FIRMS truth with a
   375–500 m detection floor. Five of the six protocol §2 events still have no committed
   observed detection stack, so §5's mean-over-events and worst-event remain unreportable.
6. **A ceiling is not a score**, and the forecast-track proxies remain not run. Every table,
   every `entrant.json`'s `track_reason`, and a test that fails if the wording is removed say so.

## 11. Open for the author

1. **F3 is the row that would settle §5's caveat** — the only true forecast-track entrant, and
   it needs the 초단기/단기예보 archive under `data/raw/kma_forecast/`. Nothing else this lap
   found changes that it is the highest-value next input.
2. **F2 needs a 산악기상 station-coordinate table** before it needs the wind record (§2). Worth
   knowing before the laptop schedules the run.
3. **Protocol §5.3.** Should the false-safe rate be reported only beside the false-alarm count,
   or as a curve? §4 is this lap's evidence that the rate alone is not comparable across
   operating points. **v0.1 was applied as written and not amended.**
4. **E3's reach at p ≥ 0.5** is the finding with the most consequence for the project (§5), and
   it is a question about the committed field's calibration, not about this benchmark.
5. ~~**NH-062**~~ — **closed while this lap ran** (`4b23b3c` on `auto/dev`). The author ran
   `scripts/nh062_check.py` against the real bundle: the ERA5 index is `datetime64[ns, UTC]`
   and `at()` resolves correctly, so the second post-T0 leak the previous lap feared **never
   existed**. Nothing in Stage 2 depended on it either way — the proxies compare `Timestamp`s
   and never call `at()` — but the previous report's open item is now answered, and this one
   would have left a stale escalation standing if the base had not been merged before writing.
6. **This commit has no GitHub verdict** (§9a). It needs a push or merge to `auto/dev`, or a
   `workflow_dispatch` of `auto-gates.yml` on the branch. Until one happens, the only green
   on this work is this machine's, which is exactly the situation `cb41adf` warns about.
7. **Should the CHARTER say that a feature branch must be rebased onto `auto/dev` and never
   merged from it?** §9b is the measured reason: the merge turns a gate red for a topological
   reason its failure message does not mention.
