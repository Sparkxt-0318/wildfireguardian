# K-SPREAD-2025 Stage 2 — the E1 and E2 proxy entrants, declared before they run

**Status: rule pre-registered 2026-09-14, before any E1 or E2 field was built or scored.**
Brief: `docs/auto/briefs/K_SPREAD_STAGE2.md`. Protocol: `docs/benchmark/K_SPREAD_2025.md`
v0.1, frozen and unchanged by this page. Stage 1: `docs/auto/briefs/K_SPREAD_BENCHMARK_REPORT.md`.

This page exists because the numbers on it did not exist when it was written. §2 fixes the
construction, §3 the sweep, §4 the selection criterion and §5 the reading of either outcome.
`docs/benchmark/results_v0.2.md` is filled only by a run that obeys this page.

## 1. What the brief asked for, and the one substitution this page makes

The brief asks for two proxies: **E1 wind-cone** (the G-DAPS class) and **E2
Rothermel-family** (the NIFoS class), each advanced from the T0 detection footprint with
**the wind observed at T0**. Protocol §3 would then put both in the **forecast track**.

**The wind at T0 is not reachable on this machine, and no substitute for it was invented.**
Measured here rather than assumed (`docs/auto/briefs/K_SPREAD_STAGE2_REPORT.md` §2): no
ERA5 `.nc` for any fire, no `data/raw/mountain_weather/`, no `data/raw/kma_forecast/`, and
no API key anywhere on the filesystem. `docs/mountain_weather_yeongdeok.md` prints hourly
and minute extrema over the fire window, but an extremum at one station in one hour is not
the wind field over the 영덕 canvas at T0, and transcribing it as though it were would be
exactly the fabrication CHARTER §3 rule 5 forbids.

So this page builds the **ceiling** instead of the point estimate:

> **E1 and E2 are built with their wind swept over a declared grid, and the entrant that is
> scored is the grid point that scores best against the observation.**

That entrant is an **oracle**. It is declared **hindcast track** — it chose its wind knowing
what the fire did, which is an observation after T0 — and it is never reported beside a
forecast-track score. What it measures is **an upper bound**: the best a method of that
class could have done on this fire under any wind. It is **not** the E1 or E2 the brief
asked for, those remain **not run**, and no number here may be quoted as 「what a wind-cone
scores」 — only as 「the most a wind-cone could have scored」.

⚠ **Why a ceiling is worth building at all.** A point-estimate proxy invites the objection
「you gave it the wrong wind」, and that objection is unanswerable. A ceiling is immune to it:
if the committed model beats the best wind-cone on this fire, no choice of wind would have
changed the comparison. If the ceiling beats the committed model, the project has to say so.

## 2. Construction (fixed; both entrants, 영덕 2025 only)

**Canvas, seed footprint and clock, all committed.** The canonical 500 m canvas of
`data/processed/routing_demo_canonical.npz` (181 × 156 cells, EPSG:5179); the seed is
`obs_stack[0]`, the **249** cells detected at T0, which is the same set E0 persistence uses;
output surfaces at **0, 30, 60, … 720 min**, the protocol §6 「per 30 min」 step, with the
last surface at 720 min so metric 3's window matches E0 and E3.

**E1 — wind-cone.** Let θ be the wind-**toward** bearing and *r* the head spread rate in
metres per 30 min. For travel in a direction making angle Δ with θ, the rate is

    R(Δ) = r · max(b, cos Δ),        b = 0.15

— full head rate downwind, a cosine falloff to the flanks, and a floor of **0.15** for the
backing fire, which is the standard rule-of-thumb backing fraction. The footprint *F(t)* is
every cell whose **least-time path** from the T0 set, over the 8-connected grid at rate
*R(Δ)* per edge, takes at most *t* (a Dijkstra from a virtual source joined to all 249 T0
cells).

**읍면동-scale smoothing**, which protocol §6 names: a Gaussian of **σ = 2,000 m** (4 cells)
over the binary footprint, and

    p(c, t) = max( 1{c ∈ F(t)},  Gaussian_σ(1_F(t))(c) )

so the footprint stays certain and the smoothing only adds a halo outside it, which is what
a 읍면동-scale product does to an alert. σ = 2 km is declared here as the 읍면동 scale; it
is **not** swept and no result below chooses it.

**E2 — Rothermel-family.** The same cone, multiplied by **Rothermel's slope factor** applied
to the slope in the direction of travel:

    R(Δ, s) = r · max(b, cos Δ) · (1 + φ_s),   φ_s = 5.275 · β^(−0.3) · (tan s)²,  β = 0.05

β = 0.05 is a forest-litter packing ratio, so the coefficient is **12.96**. *s* is the slope
**in the direction of travel**, and φ_s is an **upslope** term: travel that descends gets
φ_s = 0, which is Rothermel's own convention and not a choice made here. The propagation is
**the same Dijkstra E1 uses**, on the same graph, with the same seeds and the same smoothing;
E1 is this construction with φ_s = 0 everywhere. Slope comes from the **committed** DEM snapshot
`data/snapshots/srtm-dem_yeongdeok-2025_20260723_66988bf5.tif`, reprojected to the 500 m
canvas by area average, so *s* is a 500 m slope and not a 30 m one.

⚠ **Two declared limits of E2, both measured in the report rather than argued away.**
(1) **Fuel is uniform.** 임상도 1:5000 is not on this machine, so E2 carries no fuel-class
term. This is less of a departure than it sounds — the committed model's own land cover is
`_synthetic_landcover`, 「all forest (code 3) for the Pinus belt」
(`src/wildfireguardian/data_io/raster.py:230`) — but it means E2 is a **slope-and-wind**
proxy, not a fuel-aware one, and it is labelled that way everywhere.
(2) **The DEM covers 51.2 % of the canvas** (14,462 of 28,236 cells) — but it covers all
**249** T0 cells and all **1,023** ever-detected cells, so the half it misses is the half no
fire reached. Cells outside it are given slope 0.
The report states how many cells the entrant puts above p ≥ 0.5 outside DEM coverage; if
that count is 0 the partial DEM did not touch the result, and if it is not 0 the number is
printed rather than the limitation waved off.

**So E1 and E2 differ by exactly one term: Rothermel's slope factor.** That is the
comparison this pair can actually support, and it is the one the report reads.
`tests/test_kspread_stage2_proxies.py` asserts it the only way that means anything: on flat
ground the two constructions must agree **cell for cell**.

⚠ **The 8-connected grid is generous crosswind, for both entrants equally.** A front limited
to eight headings can zigzag between two well-aligned ones and so reach a crosswind cell
sooner than a strict straight-line cone would. Measured on a flat test canvas the shortfall
against a straight ray reaches **23 %** due crosswind. It is an artefact of the
discretisation, not of either method; it **raises** both ceilings, which is the harmless
direction for an upper bound, and it cancels in the E1–E2 comparison because both walk the
same graph.

### 2a. Amendment, recorded rather than quietly applied

**This section was changed after it was first written and before any result was reported.**
The first implementation built E1 as a **straight ray** from the nearest T0 cell and E2 as
the least-time walk above. A test written to assert 「on flat ground the pair agrees」 failed:
the walk beat the ray by up to 23 % crosswind, because of the zigzag just described. So the
pair did **not** differ by one term — it differed by the slope factor **and** by how the
front propagated, and the sentence above would have been false of the code.

E1 was changed to the shared walk and the sweep was re-run from scratch. **No score from the
first implementation is reported anywhere**, in this page or the results page or the Stage 2
report; the only number carried over from it is the 23 % that names the artefact. The
selection criterion, the grid, β, b and σ are untouched.

## 3. The sweep (declared; 720 grid points each)

| parameter | grid |
|---|---|
| wind-toward bearing θ | 0°, 10°, … 350° — **36** values |
| head rate *r* | 100, 200, … 2000 m per 30 min — **20** values |

Nothing else varies. β, b and σ are fixed above and are not swept.

## 4. Selection (declared before any score exists)

The **primary oracle** for each proxy is the grid point with the **greatest mean ROC-AUC
over the three protocol horizons** (3 h, 5 h, 8 h) at truth *m* = 0. ROC-AUC and not IoU,
because it ranks every cell and does not turn on a single threshold.

The grid point with the greatest **mean IoU at p ≥ 0.5** is reported **beside** it as a
secondary row, labelled, so a reader can see whether the two criteria pick the same field.
No third criterion is introduced after the run, and neither row is re-cut once seen.

Both selected entrants are then scored by **`scripts/benchmark/score_kspread.py`, unchanged**,
with `--with-decision-shift`, so metrics 1–4 come from the same scorer that produced E0 and E3.

## 5. The reading rule, fixed now

**Whatever the sweep says is the result.**

- If **E3 beats both ceilings** on metric 3, the finding is that the committed model's
  advantage over the proxy classes on this fire does not depend on which wind the proxies
  were given — the strongest form that comparison can take.
- If a **ceiling beats E3**, the finding is that a wind-cone with the right wind would have
  done better than the committed model, and the project says so.
- If **E1 and E2 tie**, the finding is that Rothermel's slope factor buys nothing on this
  fire at 500 m, which is a statement about the resolution and the terrain, not about
  Rothermel.

**A ceiling is never reported as a score.** Every row carries the word oracle, the hindcast
track, and the sentence that the forecast-track E1 and E2 are not run.

⚠ **One fire, one ignition, one start time.** Everything here is 영덕 2025, at 500 m, against
FIRMS truth with a 375–500 m detection floor. Nothing on this page is evidence about another
fire, another region, or another country.

## 6. What this page does not do

Nothing here is registered in `docs/NUMBERS.json`, nothing reaches a judge-facing surface,
no committed artifact is modified, and the protocol is not amended — v0.1 is frozen and
these are entrants under it, not a new version of it.
