# E3: scenario robustness and the default safety margin (SYNTHETIC dev set)

**Type:** measurement and recommendation (Phase 1 batch 1, Track C). No new planner and no change to the problem
definition: the margin is reported, not enforced (`program/DECISIONS.md` 2026-11-01, item 5). **Decision:** KEEP /
KILL / ITERATE (below). **Data:** the frozen dev split only. **Label:** every number and figure here is SYNTHETIC.

## Pre-registration (written and committed 2026-11-01 before the main run; nothing under "Results" existed then)

### Questions

1. A plan whose trips are checked in all K members: how often does it fail in **fresh** members drawn from the same
   SYNTHETIC hazard distribution? How does that compare with the scenario approach (Campi & Garatti 2008; the
   a-posteriori wait-and-judge bound with the number of support members, Campi & Garatti 2018)?
2. How does that depend on K (plan with K' members, check on disjoint fresh members)?
3. Siyeong (item 5): relate a delivered resident's in-sample safety slack (ASSUMPTIONS #91, the prefix rule of
   `evacplan.harness.delivered_by_margin`) to its out-of-sample violation, and recommend the default margin.

### Hypotheses (predictions, stated before any out-of-sample check ran)

- **P1.** B1's plans with the instance's 8 members fail out of sample often: at least one delivered resident fails in
  ≥ 10 % of fresh members on at least half of the instances. B1 runs some trips at near-zero slack (min slack 1.9 s on
  L-grid at 60 s).
- **P2.** Out-of-sample violation falls with K' roughly like s*/(K'+1), with a support count s* that grows slowly in K'.
- **P3.** Violation falls monotonically with in-sample slack, and at slack ≥ 30 min the per-resident rate is below 5 %.
- **P4.** The measured plan-level violation lies below the a-posteriori scenario bound ε(s*) at β = 0.05 for at least
  95 % of the plans with a support set (the bound is valid), and the bound is loose (≥ 2× the measured rate at K' = 8).

### Why it might work (the math)

**Scenario approach.** A decision computed to satisfy K i.i.d. scenarios violates a fresh scenario with probability
V. For convex programs with d decision variables, P{V > ε} ≤ Σ_{i<d} C(K,i) ε^i (1−ε)^{K−i} and E[V] ≤ d/(K+1)
(Campi & Garatti 2008). A dispatch plan is combinatorial (routes, orders, departure seconds), so d is not defined and
the a-priori bound is vacuous. The a-posteriori ("wait-and-judge") view uses the plan's **support members**: a subset
of the planning members from which the planner returns the same plan. For any decision rule with a support (compression)
set of s* out of K i.i.d. members, P{V > ε(s*)} ≤ β with ε(k) = 1 − (β / (K·C(K,k)))^{1/(K−k)} (Campi, Garatti & Ramponi
2018, the non-convex form); the convex wait-and-judge form of Campi & Garatti (2018) (ε(k) = 1 − t(k), t(k) the root in
(0,1) of β/(K+1) Σ_{i=k}^{K} C(i,k) t^{i−k} = C(K,k) t^{K−k}) is tighter but needs convexity and non-degeneracy; it is
shown for scale only. With K = 8 these bounds are weak: ε(1) = 0.64 and ε(2) = 0.75 at β = 0.05 (`e3_stats.py`), and
E[V] ≈ s*/(K+1) ≈ 11 % per support member. A 5 % guarantee with s* = 5 needs K of several hundred members. So with
K = 8, protection must come mostly from a margin, which is what question 3 measures.

**Slack as a time buffer.** A checked leg's slack (ASSUMPTIONS #27) is min over touched cells and planning members of
(ignition − the leg's last touch), capped at horizon − leg end. A fresh member can break the leg by contact only if, in
some touched cell, it ignites before the vehicle leaves, i.e. earlier than the planning members' earliest ignition there
by more than the leg's slack s. In this hazard model a cell's ignition time varies between members through the rate
(log-normal, CV 0.25), the direction (SD 15°) and smooth noise (log SD 0.2): roughly a log-normal spread with σ ≈ 0.3. If
T is a cell's typical arrival time, the minimum of K members sits about z_K σ T earlier (z_8 ≈ 1.4), and a fresh member
beats it with probability ≈ 1/(K+1) at s = 0, falling as s grows relative to σT (tens of minutes for arrivals 1-4 h
after issue). So margins of the order of 15-30 min should cut contact violations substantially. Slack does not measure
dose (cumulative exposure) failures, and the horizon cap shrinks slack for late deliveries that no fresh member can
break by contact (a conservative bias of the margin).

### Setup

- **Instances.** The 10 dev instances (4 S, 4 M, 2 L), regenerated through `evacplan.instances` (fingerprints verified).
  Refused when `EVACPLAN_MILESTONE` is set; no test instance is ever generated or loaded (rule 5).
- **Fresh members.** For each instance, its own hazard model is drawn again with 8 + 32 + 256 = 296 members:
  `hazard_contract.synthetic` with the instance's seed, ignition point, rate of spread, spread direction, grid and horizon
  (all from the instance's hazard provenance and `evacplan.generators.synthetic._Fire`), then the generator's own
  post-processing (ignitions floored to whole seconds, persistent burning). `hazard_contract.synthetic` draws members
  one after another from one generator, so members 0-7 must reproduce the instance's members bit for bit; this is
  checked per instance (and held on S-grid-t25-s101 in a probe), and an instance that fails is refused. Members 8-39 are
  fresh **planning** members, 40-295 fresh **check** members ("check member c" = index 40 + c). The generator and the
  frozen instances are untouched.
- **Conditional i.i.d.** Given the ignition point, all 296 members are i.i.d. draws of the same model. The ignition
  point itself was placed by bisection so that the earliest arrival at any facility over members 0-7 equals the lead, so
  the instance's members are conditioned on that statistic; fresh members are not. Arm B (fresh planning members) is
  exactly exchangeable with the check members; arm A (the instance's members) only approximately. Comparing arms at
  K' = 8 measures the difference. Fresh members share the instance's ignition, rate, direction and grid: they represent
  the model's member spread, not structural error (another ignition, a wind shift outside the model).
- **Plans** (B1 = `b1_greedy`, deterministic, 60 s budget, seed 0; a plan that stops at its budget is flagged).
  - Arm A: B1 on disjoint consecutive blocks of the instance's members, K' ∈ {1, 2, 4, 8} (`A1-g0` … `A1-g7`, `A2-g0` …
    `A2-g3`, `A4-g0`, `A4-g1`, `A8-g0`). `A8-g0` uses the instance's own scenario set, i.e. it is the harness's B1 plan
    (checked against the committed B1 rows before the main run).
  - Arm B: B1 on disjoint consecutive blocks of the 32 fresh planning members, K' ∈ {8, 16, 32} (`B8-g0` … `B8-g3`,
    `B16-g0`, `B16-g1`, `B32-g0`).
  - B2 (`b2_vrptw`, 60 s, the instance's 8 members) on S and M, run in the main process while the workers plan B1; B2 is
    load-sensitive, so its plans are treated as given (search depth recorded in each record).
  - L: only the core plans (`A1-g0`, `A2-g0`, `A4-g0`, `A8-g0`, `B8-g0`, `B16-g0`, `B32-g0`).
- **In-sample check.** Each plan is checked by the oracle against its planning members: delivered residents, per-trip
  state, and each delivered resident's safety slack by the prefix rule (cross-checked against
  `evacplan.harness.delivered_slacks`).
- **Out-of-sample check (rule 3).** Each plan is checked against each fresh check member **alone**: `Oracle.check_plan`
  with a one-member scenario set built from that member. A resident delivered in-sample **violates** in member c if its
  trip is not `checked` there (`model_no_route` or `unresolved`, whatever the cause; rule 4: unresolved is never
  delivered). Causes are recorded.
- **Support sets.** Greedy removal in member order: drop a planning member if B1 without it returns the identical plan
  (same itineraries); what is left is a compression set of size s*. For `A8-g0` (all instances) and `B8-g0`, `B16-g0`,
  `B32-g0` (S and M).
- **Compute and subsampling.** One check costs about 0.7 s for a 4-trip S plan (measured on S-grid-t25-s101 with one
  member), more on M and L, so not every plan can be checked against all 256 members. The checks run in pre-registered
  tiers (`config.yaml`), S → M → L and members in order inside a tier, with 4 worker processes inside one bench-lock hold,
  until the compute budget (75 min wall clock for the whole compute step) is used: T1 `A8-g0` and B2 on S, M with check
  members 0-63; T1L `A8-g0` on L, 0-31; T2 the core K curve on S, M, 0-31; T3 `A8-g0` and B2 on S, M, 64-127; T3L L,
  32-63; T4 core S, M, 32-63; T5 `A8-g0` and B2 on S, M, 128-255; T5L L, 64-127; T6 core on L, 0-15; T7/T8 the other blocks
  (replicates) on S/M, 0-31; T9 L, 128-255. Whatever is not reached is not run, and the results say what was. A smoke run
  (`config_smoke.yaml`, one S instance) and `e3_compute.py selftest` run first in the same hold; the main run starts only
  if both pass.
- **Host.** All of it in this container session (`vm boot ff671362`; the script refuses another boot session).

### Metrics

- **Per-resident violation rate**: the average over in-sample delivered residents of the share of their plan's
  checked fresh members in which they are not delivered (each resident counts once, whatever the number of members its
  plan was checked against; it equals violating (resident, member) pairs / all pairs when every plan has the same number
  of members). Residents of one vehicle fail together, so pairs are clustered by (instance, fresh member). Intervals:
  two-sided 95 % Clopper-Pearson (CP) with three sample sizes: naive (pairs independent; too narrow, reference only),
  Korn-Graubard (effective n = n / design effect from the cluster-robust variance), and Kish (effective n = (Σ n_c)² /
  Σ n_c², i.e. each cluster counts once, weighted by its residents: perfect correlation inside a cluster, the most
  conservative under this clustering). Per instance, the clusters are its members.
- **Plan-level violation rate**: share of fresh members in which at least one in-sample delivered resident fails;
  exact CP over the members (i.i.d. given the instance's ignition).
- **vs K**: arm A K' ∈ {1, 2, 4, 8}, arm B K' ∈ {8, 16, 32}. Primary curve: the core plans on check members 0-31 of the
  instances where every core plan was checked there. Replicate blocks: secondary.
- **vs slack**: the cumulative rate over residents with in-sample slack ≥ m for the harness grid m ∈ {0, 1, 2, 5, 10,
  15, 20, 30, 45, 60} min plus 90 and 120, a 1-min curve from 0 to 120 min, and slack bins.
- **Cost of a margin**: the share of in-sample delivered residents with slack ≥ m (E3's plans), and the leaderboard's
  margin columns for the baselines (`delivered_by_margin_min` in the result rows; the 5-seed rows if merged).
- **Scenario bounds** per plan with a support set: s*, ε(s*) (Campi, Garatti & Ramponi 2018, β = 0.05), the convex
  wait-and-judge value for scale, s*/(K'+1); against the measured plan-level rate and its CP interval.

### Recommendation rule (the margin)

Primary set: B1 `A8-g0` plans (the harness's B1 plans; slack measured on the instance's 8 members), pooled over every
instance checked. For α = 5 % and α = 1 %: the **smallest m in the harness grid** {0, 1, 2, 5, 10, 15, 20, 30, 45, 60}
min whose upper bound U(m) = max(Korn-Graubard, Kish) upper end of the two-sided 95 % CP interval is ≤ α. Its cost: the
share of delivered residents with slack ≥ m (E3's B1 and B2 plans, and the leaderboard baselines). If no m ≤ 60 min
qualifies: "none ≤ 60 min". Secondary sets (robustness): B2, arm B `B8-*`, all K' = 8 plans. Sensitivity (reported,
not the rule): the same with the Korn-Graubard bound alone.

### Decision rule

- **KEEP** (propose the α = 5 % margin as the default, the α = 1 % margin as the strict option, plus the K guidance) if
  the primary set has an α = 5 % margin and the B2 set's point estimate at that margin is ≤ 5 %.
- **ITERATE** if no m ≤ 60 min qualifies for α = 5 %, or B2 contradicts (point estimate > 5 % at that margin), or more
  than half of the violations at that margin have causes the slack does not measure (dose, unresolved).
- **KILL** (the margin as a robustness tool) if violation does not fall with slack: the rate at slack ≥ 30 min is not
  below half the rate at slack ≥ 0.

**Baseline** for the comparison: K = 8 with margin 0 (today's definition of delivered).

### Budget

About 4 hours of work; at most 1.5 hours of bench-lock time (smoke + compute ≤ 80 min, analysis a few minutes).

### Known biases (stated before the results)

- **SYNTHETIC hazards.** H0 found them much hotter than the Korean dev packets, and the member spread (rate CV 0.25,
  direction SD 15°, noise SD 0.2) is a modelling assumption. The margin is conditional on this model and must be
  re-validated on real members (Track A) before it means anything for real fires.
- **Conditioning** of the instance members through the ignition bisection (above).
- **Two planners.** B1 and B2 only; other planners (E1) may place trips differently relative to the fire.
- **Slack is contact-only and capped at the horizon** (above).
- **Few instances.** 10 instances; L instances hold most residents, so pooled rates lean on them. Members are i.i.d.
  only within an instance.

### Outputs

- `e3_compute.py` (compute and selftest), `e3_analyze.py` (analysis), `e3_stats.py` (Clopper-Pearson, effective
  sample sizes, scenario bounds), `e3_pilot.py` (an earlier cost probe, superseded by the tiers; not used for results).
- Raw records in `evacplan/runs/E3-scenario-robustness/` (git-ignored, regenerable).
- `results.csv` (per plan), `by_K.csv`, `by_margin.csv`, `by_slack_bin.csv`, `recommendation.csv`, `figures/`; every row
  records the commits, seed (none), config and host.

Reproduce from the worktree root:

```sh
.venv/bin/python program/benchlock.py --label E3-compute -- bash -c '
  set -e; P=evacplan/experiments/E3-scenario-robustness
  .venv/bin/python $P/e3_compute.py compute --config $P/config_smoke.yaml \
      --runs-dir evacplan/runs/E3-scenario-robustness/smoke --instances SYNTHETIC-S-grid-t25-s101
  .venv/bin/python $P/e3_compute.py selftest --config $P/config_smoke.yaml --runs-dir evacplan/runs/E3-scenario-robustness/smoke
  .venv/bin/python $P/e3_compute.py compute'
.venv/bin/python program/benchlock.py --label E3-analyze -- \
    .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_analyze.py
```

## Results

(Pending: filled in after the main run.)
