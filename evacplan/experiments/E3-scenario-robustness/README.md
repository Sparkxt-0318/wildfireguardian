# E3: scenario robustness and the default safety margin (SYNTHETIC dev set)

**Type:** measurement and recommendation (Phase 1 batch 1, Track C). No new planner and no change to the problem
definition: the margin is reported, not enforced (`program/DECISIONS.md` 2026-11-01, item 5). **Decision:** KEEP /
KILL / ITERATE (below). **Data:** the frozen dev split only. **Label:** every number and figure here is SYNTHETIC.

## Pre-registration (written and committed 2026-11-01 before the main run; nothing under "Results" existed then)

**Amendment, disclosed only in the batch-1 review (note dated 2026-11-01).** The pre-registration was committed and
pushed at `71a694de` (05:25 UTC). At `758b1d55` (05:30 UTC), before any E3 data existed, the per-resident metric under
Metrics changed from violating (resident, member) pairs / all pairs to the resident-weighted average below (so that
plans checked against different numbers of members do not reweight instances), and the Korn-Graubard-only sensitivity
was added. Every E3 record carries compute commit `11817858`, a descendant of `758b1d55`, so the effective
pre-registration is `758b1d55`. But `758b1d55` reached `origin` only at 07:48 UTC, with the results: the
pre-registration visible before the run had the pairs-weighted metric. Under that metric (recomputed from the raw
records in the review), B1's pooled rate is 4.18 %, U(0) 5.53 % and U(1 min) 3.03 %; the α = 5 % margin is still
1 min, but the α = 1 % margin is 45 min (U 0.98 %) instead of none ≤ 60 min. In the secondary sets, B2 gives 5 min
instead of 0 at α = 5 %, and all K = 8 plans give 1 and 45 min instead of 0 and 60 min. KEEP holds under both
metrics. The margin rule, the decision rule and P1-P4 were not changed.

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

*Premises of the bound (stated in the batch-1 review, 2026-11-01).* The non-convex bound needs three things: a
deterministic decision rule (the same members always give the same plan), a decision consistent with all K members
(here: every trip with residents checked in each of them), and K i.i.d. members. It holds for any fixed compression
rule, such as the greedy removal below. B1 meets the first two: it is deterministic (Setup) and no plan stopped at its
budget, and every plan is consistent (both in Results, Run). The members are exactly i.i.d. in arm B and only
approximately in arm A (Setup, "Conditional i.i.d.").

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

*Name of the Korn-Graubard interval (batch-1 review, 2026-11-01).* The interval computed here, as pre-registered, is
the Korn-Graubard effective-n interval without the degrees-of-freedom factor: CP with effective n = p(1−p)/v (v the
cluster-robust variance), capped at the number of pairs. Korn & Graubard (1998) also multiply the effective n by
(t_{n−1, 0.975} / t_{df, 0.975})², with n the number of pairs and df = clusters − 1. With that factor, the numbers
pooled over all checked members (Q1's pooled line, Q3, the recommendation) do not change at the reported precision
(B1's KG upper end at 30 min goes from 0.9899 to 0.9903 %, so the KG-only α = 1 % pick stays 30 min). Without it the
intervals are slightly too narrow: 11 of the 18 Q1 rows widen in the displayed decimals, by at most 0.1 points
(largest: L-geo-t50-s110, [2.44, 8.85] → [2.40, 8.94]), and the 7 Q2 rows by 0.01-0.02 points. No margin pick and no
decision changes.

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
- Raw records in `evacplan/runs/E3-scenario-robustness/` (git-ignored, regenerable). Correction (batch-1 review,
  2026-11-01): not fully regenerable. B2's plans depend on machine load (Results, Run), and how far the checks get
  depends on when the 75 min budget runs out. Copies of the main run's records are committed in `raw/`
  (`raw/README.md`).
- `results.csv` (per plan), `by_K.csv`, `by_margin.csv`, `by_slack_bin.csv`, `recommendation.csv`, `figures/`; every row
  records the commits, seed (none), config and host. Added after the run (descriptive): `scenario_summary.csv`,
  `by_instance_margin.csv`, `diagnostic_arrivals.csv`, `margin_cost_baselines.csv`.

Reproduce from the worktree root:

```sh
.venv/bin/python program/benchlock.py --label E3-compute -- bash -c '
  set -e; P=evacplan/experiments/E3-scenario-robustness
  .venv/bin/python $P/e3_compute.py compute --config $P/config_smoke.yaml \
      --runs-dir evacplan/runs/E3-scenario-robustness/smoke --instances SYNTHETIC-S-grid-t25-s101
  .venv/bin/python $P/e3_compute.py selftest --config $P/config_smoke.yaml --runs-dir evacplan/runs/E3-scenario-robustness/smoke
  .venv/bin/python $P/e3_compute.py compute'
.venv/bin/python program/benchlock.py --label E3-analyze -- \
    .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_analyze.py --diagnostics
```

The final analysis ran with `--diagnostics` (the arrival diagnostic); without it `diagnostic_arrivals.csv` is not
rewritten (flag added to this command in the batch-1 review, 2026-11-01). To re-run only the analysis on the committed
records, see `raw/README.md`.

## Results (computed 2026-11-01; nothing below this heading existed at pre-registration)

**Decision: KEEP** (pre-registered rule). The primary set has an α = 5 % margin (**1 min**), B2 agrees at that
margin (3.7 % ≤ 5 %), every violation is flame contact (which the slack measures), and violation falls with slack
(0.56 % at ≥ 30 min against 3.89 % at ≥ 0). At α = 1 % no margin ≤ 60 min is certified by the pre-registered
(conservative) bound; the Korn-Graubard bound alone gives 30 min. Everything here is conditional on the SYNTHETIC
hazard model (below).

**Scope (batch-1 review, 2026-11-01).** The 1 min certificate covers the residents of these 10 dev instances: the
clusters are (instance, fresh member) and the instances are fixed. With the instance as the sampling unit (post hoc),
the α = 5 % margin is 20 min under Korn-Graubard, 1 min under an instance bootstrap and none ≤ 60 min under
max(KG, Kish) (Q3, instance-level sensitivity). The post-hoc recommendation for Siyeong is a provisional default of
30 min: the smallest margin that passes both post-hoc readings, 20 min by the cumulative rule with the instance as the
sampling unit and about 30 min so that every slack bin above it stays ≤ 5 % (Q3). The experiment's pre-registered
result stays 1 min.

**Predictions.** P1 falsified (plan-level violation ≥ 10 % on 3 of 10 instances, not half). P2 holds only in the
pooled point estimates for fresh planning members (2.74 → 1.62 → 0.97 % at K' = 8 / 16 / 32), and that fall comes
from one instance, M-grid-t75-s107; the other 7 S and M instances are about flat (Q2). It does not hold for the
instance's own members. P3 holds on the harness grid for B1 (the cumulative curve never rises there; 0.56 % at
≥ 30 min), but not strictly: the 1-min curve and the slack bins rise in places (Q3). P4 holds (34 of 34 plans below
their a-posteriori bound, which is 8-23× loose); the bound is exact for the 24 arm-B plans, whose members are i.i.d.,
and only approximate for the 10 arm-A plans, whose members are conditioned (scenario-bound section). P2, P3 and P4
were qualified in the batch-1 review (2026-11-01).

### Run

- One bench-lock hold, 05:54:50-07:10:37 UTC (75.8 min): smoke run (one S instance, 17 s), selftest, main compute
  (4523 s, stopped by its 75 min budget), in-chain analysis (6 s). Host `vm (Linux x86_64, Intel(R) Xeon(R) Processor
  @ 2.80GHz, 4 cpu, python 3.12.3, vm boot ff671362)`; boot id checked at start. Compute at commit `11817858` (clean;
  the compute code is unchanged since `95e28374`), 4 worker processes.
- Members 0-7 regenerated **bit-identically on all 10 dev instances** (`members.json`); the selftest's B1 plan with
  S-grid-t25-s101's own 8 members reproduced the committed harness row (23 delivered, min slack 3839.2 s).
- 198 plans: 190 B1 (no plan stopped at its budget; longest 9.8 s), 8 B2 (52.8-56.1 s of search each, 335-44 090
  solutions; recorded in `plans.jsonl` and `results.csv`). **Every trip with residents of every plan was checked
  in-sample**, so every plan is consistent with its planning members. 34 support sets.
- E3's B2 plans cannot be regenerated (batch-1 review, 2026-11-01). B2's search depth depends on machine speed and
  load, and E3 ran it in the main process beside 4 B1 workers. Its plans differed from the leaderboard's B2 rows of the
  morning hold (5 seeds, rows at `18841678`) on 2 of the 8 instances: M-grid-t25-s105 (E3: min slack 56.8 s, 154
  residents at slack ≥ 1 min, 550 solutions found; each of those seeds: 766.8 s, 163 residents, 826-864 solutions) and
  M-geo-t25-s106 (min slack 1808 s against 1814 s); the other 6 had the same objective and min slack. B2's quiet
  re-run (14:56-15:49 UTC; the VM was slower than in the morning, 636-725 and 423-554 solutions there) found exactly
  E3's plans on both (objective 15677, min slack 56.8 s, 154 at ≥ 1 min; min slack 1808 s) in all 5 seeds. The plans
  are kept in `raw/`.
- Rule 6 (batch-1 review): the E4 agent ran about 27 s of work outside the lock during this hold (05:59:40-06:07:19
  UTC), while E3 was computing, B2 runs included. E3's own 4 workers already loaded the machine (by design), so E3's
  B2 plans carry that load either way.
- 7 112 out-of-sample oracle checks (one plan against one fresh member). Median cost per check: 0.57 s (S), 3.1 s (M),
  18 s (L). Tiers reached: T1, T1L, T2, T3, T3L, T4 complete; T5 169/192 tasks (M-geo-t75-s108 stopped at 164 members);
  T5L-T9 not reached. Coverage: `A8-g0` and B2 on S and M against 256 fresh members (M-geo-t75-s108: 164), `A8-g0` on L
  against 64; the core K curve (`A1-g0`, `A2-g0`, `A4-g0`, `B8-g0`, `B16-g0`, `B32-g0`) on S and M against 64; the
  replicate blocks and the L K curve were not checked.
- Deviations from the plan: the per-resident metric was amended at `758b1d55`, 5 min after the pre-registration and
  before any data existed, and that commit was pushed only with the results (note under the Pre-registration heading;
  disclosed in the batch-1 review, 2026-11-01). The pilot (`e3_pilot.py`) never ran (stopped in the lock queue; the
  tiers made it unnecessary). After the main run started, descriptive outputs were added to the analysis (claimed
  residents per plan, expected safe deliveries, a scenario-bound summary, a per-instance margin table, the arrival
  diagnostic run) and the rate accumulation was vectorized (identical outputs on test data). A snapshot of the records
  was analysed once during the run. The margin rule and the decision rule were not changed. The final analysis (with
  the arrival diagnostic) ran in a second, 10 s bench-lock hold at 08:15 UTC; its stamp is `6bc77714+dirty` (only this
  README was uncommitted), and its numbers equal the in-chain analysis (`6500ee03`) apart from that stamp.

### Q1. Plans checked in all 8 members, in fresh members

Per instance, B1 with the instance's own 8 members (`A8-g0`, the harness's B1 plan) and B2 (`B2-A8`). Plan-level =
share of fresh members in which at least one delivered resident is not delivered (exact 95 % CP); per resident =
average share of fresh members in which a delivered resident is not delivered (95 % Korn-Graubard effective-n CP
without the degrees-of-freedom factor, as pre-registered: see the note under Metrics; Kish upper bound in the next
column). Every violation is `FLAME_CONTACT` (`model_no_route`); no dose or unresolved violation occurred.

| instance | plan | delivered (in-sample) | min slack (s) | fresh members | plan-level [95 % CP] | per resident [KG 95 % CP] | Kish upper | s* | ε(s*) |
|---|---|---|---|---|---|---|---|---|---|
| S-grid-t25-s101 | A8 | 23 | 3839.2 | 256 | 2.7 % [1.1, 5.6] | 1.43 % [0.58, 2.91] | 3.76 % | 1 | 64 % |
| S-geo-t25-s102 | A8 | 37 | 686.0 | 256 | 2.7 % [1.1, 5.6] | 0.78 % [0.31, 1.60] | 2.79 % | 1 | 64 % |
| S-grid-t75-s103 | A8 | 20 | 1374.7 | 256 | 0.4 % [0.0, 2.2] | 0.04 % [0.00, 0.22] | 1.51 % | 1 | 64 % |
| S-geo-t75-s104 | A8 | 24 | 36.3 | 256 | 3.9 % [1.9, 7.1] | 1.68 % [0.67, 3.45] | 4.11 % | 1 | 64 % |
| M-grid-t25-s105 | A8 | 163 | 2032.0 | 256 | 0.4 % [0.0, 2.2] | 0.16 % [0.00, 0.89] | 1.75 % | 1 | 64 % |
| M-geo-t25-s106 | A8 | 155 | 1836.0 | 256 | 0.0 % [0.0, 1.4] | 0.00 % [0.00, 1.43] | 1.43 % | 1 | 64 % |
| M-grid-t75-s107 | A8 | 100 | 59.7 | 256 | **37.1 %** [31.2, 43.3] | **22.6 %** [18.6, 27.0] | 28.25 % | 2 | 75 % |
| M-geo-t75-s108 | A8 | 101 | 2342.7 | 164 | 9.8 % [5.7, 15.4] | 2.63 % [1.16, 5.04] | 6.39 % | 3 | 84 % |
| L-grid-t50-s109 | A8 | 335 | 1.9 | 64 | 12.5 % [5.6, 23.2] | 1.91 % [0.78, 3.88] | 8.97 % | 2 | 75 % |
| L-geo-t50-s110 | A8 | 395 | 545.9 | 64 | 20.3 % [11.3, 32.2] | 4.96 % [2.44, 8.85] | 13.48 % | 4 | 90 % |
| S-grid-t25-s101 | B2 | 23 | 4135.6 | 256 | 2.3 % [0.9, 5.0] | 1.43 % [0.53, 3.07] | 3.76 % | – | – |
| S-geo-t25-s102 | B2 | 36 | 1430.0 | 256 | 1.6 % [0.4, 4.0] | 0.81 % [0.21, 2.12] | 2.84 % | – | – |
| S-grid-t75-s103 | B2 | 23 | 16.7 | 256 | 0.8 % [0.1, 2.8] | 0.41 % [0.04, 1.52] | 2.19 % | – | – |
| S-geo-t75-s104 | B2 | 26 | 118.3 | 256 | 3.9 % [1.9, 7.1] | 2.03 % [0.94, 3.80] | 4.60 % | – | – |
| M-grid-t25-s105 | B2 | 163 | 56.8 | 256 | 6.6 % [3.9, 10.4] | 0.67 % [0.22, 1.53] | 2.62 % | – | – |
| M-geo-t25-s106 | B2 | 155 | 1808.0 | 256 | 0.8 % [0.1, 2.8] | 0.05 % [0.01, 0.18] | 1.53 % | – | – |
| M-grid-t75-s107 | B2 | 140 | 129.6 | 256 | **39.1 %** [33.1, 45.3] | **15.9 %** [12.9, 19.2] | 20.94 % | – | – |
| M-geo-t75-s108 | B2 | 139 | 1476.7 | 164 | 7.9 % [4.3, 13.2] | 0.73 % [0.24, 1.67] | 3.55 % | – | – |

Pooled over the 10 instances, B1 (`A8-g0`): **3.89 % of delivered residents** [KG 2.94, 5.03 %; Kish upper 6.25 %]
fail in a fresh member, and **7.6 %** of (plan, fresh member) pairs break at least one delivered trip [6.5, 8.8 %].
B2 (8 S/M instances): 3.64 % per resident [KG upper 4.43 %, Kish 4.84 %], 7.9 % per plan. The failures concentrate on
the tight instances: M-grid-t75-s107 fails in 37-39 % of fresh members with both planners, while the six S and M
instances other than the two tight M ones stay at or below 4 % with B1 (B2: up to 6.6 %, on M-grid-t25-s105, where
E3's B2 plan differs from the leaderboard's; see Run). Prediction **P1 is falsified** (≥ 10 % plan-level on 3 of 10
instances, not half).

### Scenario bound vs measured violation

Support sets are tiny: greedy removal leaves a single member for 12 of the 18 K = 8 plans and 1-4 members for every
plan, including K = 32 (`results.csv`, `support_members`). Greedy removal drops members in index order, so s* and the
support members can depend on that order: they need not be the only or the smallest set of members that reproduces the
plan (batch-1 review, 2026-11-01, from a B1 re-run under the bench lock that is not in the committed records). The
re-run shows this on 3 of the 10 A8 plans: on S-grid-t25-s101 and M-grid-t25-s105 each of the 8 members alone
reproduces the plan (the reported support is member 7), and on M-geo-t75-s108 member 0 alone reproduces it, while
greedy removal reports members 1, 5, 6 (s* = 3, ε = 84 %; with member 0: s* = 1, ε = 64 %, and the arm-A mean s* would
be 1.50, not 1.70). On 4 other A8 plans the reported member is the only single member that reproduces the plan; on the
last 3 no single member does. Per (arm, K'), plans with a support set (all consistent with their members):

| arm | K' | plans | mean s* | mean s*/(K'+1) | median ε(s*), non-convex (CGR 2018) | median ε, wait-and-judge (convex, scale only) | measured plan-level [95 % CP] | plans above ε(s*) | plans above s*/(K'+1) |
|---|---|---|---|---|---|---|---|---|---|
| A (instance members) | 8 | 10 | 1.70 | 18.9 % | 64 % | 59 % | 7.6 % [6.5, 8.8] | 0 | 1 |
| B (fresh members) | 8 | 8 | 1.25 | 13.9 % | 64 % | 59 % | 5.7 % | 0 | 1 |
| B | 16 | 8 | 1.50 | 8.8 % | 48 % | 40 % | 3.9 % | 0 | 1 |
| B | 32 | 8 | 1.50 | 4.5 % | 27 % | 19 % | 1.2 % | 0 | 0 |

- The a-posteriori bound holds for every plan (34 of 34 below ε(s*) at β = 0.05) and is loose: 8-11× the pooled rate
  at K = 8, 23× at K = 32 (**P4 holds**). Its premises (stated with the bound above; batch-1 review, 2026-11-01) are
  met exactly in arm B: B1 is deterministic, every plan is consistent and the fresh planning members are i.i.d. In
  arm A the i.i.d. premise holds only approximately, because the instance's members are conditioned by the ignition
  bisection. So the bound is exact for the 24 arm-B plans (24 of 24 below it) and approximate for the 10 arm-A plans
  (10 of 10 below it; also with M-geo-t75-s108 at s* = 1: 9.8 % < 64 %). The order dependence above does not
  invalidate it: it holds for any fixed compression rule. The a-priori bound of Campi & Garatti (2008) needs a number
  of decision variables, which a dispatch plan does not have; it is vacuous here.
- s*/(K'+1), the expected violation of a fully supported convex program with s* support constraints, has the right
  order and the right slope in K (13.9 → 8.8 → 4.5 % vs measured 5.7 → 3.9 → 1.2 %, 2.3-3.8× above the measured
  rates), but it is not a bound: on M-grid-t75-s107 the measured rate (37 % with the instance's members; 30 % and 22 %
  with fresh K = 8 and K = 16) exceeds s*/(K'+1) (22 %, 22 % and 12 %).
- With K = 8 the scenario approach cannot certify much: ε(1) = 64 %. A 5 % guarantee at β = 0.05 needs about 280
  i.i.d. members with s* = 1 and 400 with s* = 2 (non-convex bound; 134 and 174 with the convex wait-and-judge form).

### Q2. Dependence on K

Primary scope (pre-registered): the core plans against fresh check members 0-31 on the 8 S and M instances (where all
core plans were checked). Claimed = residents delivered in-sample; expected safe = claimed × (1 − per-resident rate).

| arm | K' | claimed per plan | per resident [KG 95 % CP] | plan-level [95 % CP] | expected safe per plan |
|---|---|---|---|---|---|
| A: instance members | 1 | 79.0 | 4.72 % [2.69, 7.62] | 9.0 % [5.8, 13.2] | 75.3 |
| A | 2 | 76.9 | 4.70 % [2.63, 7.67] | 8.2 % [5.2, 12.3] | 73.3 |
| A | 4 | 77.9 | 4.74 % [2.64, 7.78] | 7.8 % [4.8, 11.8] | 74.2 |
| A | 8 | 77.9 | 4.73 % [2.63, 7.77] | 7.4 % [4.5, 11.4] | 74.2 |
| B: fresh members | 8 | 76.4 | 2.74 % [1.14, 5.46] | 4.7 % [2.5, 8.0] | 74.3 |
| B | 16 | 75.4 | 1.62 % [0.54, 3.69] | 3.9 % [1.9, 7.1] | 74.2 |
| B | 32 | 73.9 | 0.97 % [0.23, 2.63] | 2.0 % [0.6, 4.5] | 73.2 |

With all checked members (scope "all" in `by_K.csv`; arm B: 0-63) the arm-B rates are 2.41 / 1.32 / 0.52 % per
resident and 5.7 / 3.9 / 1.2 % per plan at K' = 8 / 16 / 32.

- **More i.i.d. members help in the pooled numbers, but only one instance shows it** (arm B): per-resident violation
  2.7 → 1.6 → 1.0 % from K = 8 to 32, roughly like 1/K. The fall comes from M-grid-t75-s107
  (13.57 → 5.50 → 1.93 %); the other 7 S and M instances pooled are about flat (0.99 → 1.03 → 0.81 %; on members
  0-63: 0.67 → 0.62 → 0.44 %). Each K is one nested block (`B8-g0` ⊂ `B16-g0` ⊂ `B32-g0`; the replicate blocks were
  not checked), and on 7 of the 8 instances at least two of the three arm-B plans are identical. A paired cluster test
  of K = 8 against K = 32 gives z = 2.5 with all 8 instances and 0.8 without M-grid-t75-s107 (check members 0-31; on
  0-63: 3.6 and 1.7; batch-1 review, 2026-11-01). So **P2 holds only in the pooled point estimates**; the 1/K shape is
  not established. The plans claim 3 % fewer residents at K = 32 (S-grid-t25-s101: 23 → 7), so the expected number
  delivered safely in a fresh member does not change (about 74 per plan): K buys robustness by claiming less, not by
  delivering more.
- **More of the instance's own members do not help** (arm A is flat in K' = 1-8 per resident, 9.0 → 7.4 % per plan),
  partly because the plans are often the same: all four arm-A plans are identical on 3 of the 8 instances, and
  A2 = A4 = A8 or A4 = A8 on 4 more (batch-1 review, 2026-11-01). In this scope 76-77 % of arm-A violations come from
  M-grid-t75-s107, where A1, A2 and A4 = A8 are different plans with similar rates (22-24 %). At K' = 8 the instance's
  members give higher violation than fresh ones (4.7 vs 2.7 % per resident). The arrival diagnostic below shows why.
  It is not a systematic bias of the generator: on average 10.3 % of fresh members reach a facility before the lead
  (11.1 % if members were exchangeable). But the share ranges from 0.8 to 29 % between instances, and where the
  violations are, the instance's 8 members happen to be cool (M-grid-t75-s107: 27 %,
  L-geo-t50-s110: 18 %). Every subset of them shares that luck, so plans made from 1, 2, 4 or 8 of them are about
  equally exposed; fresh planning members redraw it, hence the decrease in arm B on M-grid-t75-s107.
- Cost of members: B1's runtime hardly depends on K (about 2 s on S, 4 s on M, 9 s on L), the in-sample oracle check
  grows with K (M: 8 s at K = 8, 21 s at K = 32).

### Q3. Slack vs out-of-sample violation, and the default margin

Cumulative (residents counted with in-sample slack ≥ m; U = max(Korn-Graubard, Kish), the pre-registered bound):

| m (min) | B1 kept (share) | B1 violation | B1 U | B2 kept (share) | B2 violation | B2 U |
|---|---|---|---|---|---|---|
| 0 | 1353 (100 %) | 3.89 % | 6.25 % | 705 (100 %) | 3.64 % | 4.84 % |
| 1 | 1231 (91.0 %) | 2.46 % | **4.55 %** | 681 (96.6 %) | 3.67 % | 4.90 % |
| 5 | 1231 (91.0 %) | 2.46 % | 4.55 % | 564 (80.0 %) | 0.53 % | 1.20 % |
| 15 | 1189 (87.9 %) | 2.13 % | 4.15 % | 564 (80.0 %) | 0.53 % | 1.20 % |
| 20 | 1090 (80.6 %) | 1.41 % | 3.04 % | 564 (80.0 %) | 0.53 % | 1.20 % |
| 30 | 956 (70.7 %) | 0.56 % | 1.82 % (KG 0.99 %) | 498 (70.6 %) | 0.47 % | 1.16 % |
| 45 | 839 (62.0 %) | 0.37 % | 1.71 % | 379 (53.8 %) | 0.28 % | **0.92 %** |
| 60 | 807 (59.6 %) | 0.33 % | 1.62 % | 351 (49.8 %) | 0.16 % | 0.72 % |
| 90 | 510 (37.7 %) | 0.05 % | 1.74 % | 158 (22.4 %) | 0.00 % | 0.68 % |
| 120 | 346 (25.6 %) | 0.00 % | 2.43 % | 69 (9.8 %) | 0.00 % | 0.57 % |

Per slack bin (the risk of a resident whose slack is in the bin, not the cumulative average), B1: 0-1 min 18.3 %
(122 residents), 5-10 min 15.4 % (29), 10-15 min 3.5 % (13), 15-20 min 10.1 % (99), 20-30 min 7.5 % (134), 30-45 min
2.0 % (117), 45-60 min 1.3 % (32), 60-90 min 0.8 % (297), 90-120 min 0.14 % (164), ≥ 120 min 0 % (346). B2: 2-5 min
21.7 % (99), every other bin ≤ 3 %.

Neither the bins nor the 1-min cumulative curve (`figures/violation_vs_margin.png`) fall strictly monotonically
(batch-1 review, 2026-11-01). The B1 bins dip at 10-15 min (3.5 %, 13 residents). The B1 1-min curve rises at 24 of its
120 steps, by small amounts (e.g. 22 → 23 min: 1.14 → 1.16 %), and the B2 curve at 13, including 0 → 1 → 2 min
(3.64 → 3.67 → 3.69 %). On the harness grid the B1 curve never rises.

**Scope of the certificate and instance-level sensitivity (post hoc, batch-1 review, 2026-11-01; not the rule).** The
pre-registered intervals cluster by (instance, fresh member) and treat the 10 dev instances as fixed. So the α = 5 %
certificate below (1 min) covers the residents of these 10 instances, not a new instance. With the instance as the
sampling unit, for the pooled B1 `A8-g0` rate (recomputed from the raw records in the review; its scripts are not
committed):

| bound | U(1 min) | smallest margin with U ≤ 5 % |
|---|---|---|
| pre-registered: max(KG, Kish), clusters = (instance, member), instances fixed | 4.55 % | **1 min** |
| KG, the 10 instances as clusters, with the df factor (df 9) | 6.63 % | 20 min (U(15 min) 5.80 %, U(20 min) 3.77 %) |
| KG, the 10 instances as clusters, without the df factor | 5.88 % | 20 min |
| KG, instances as clusters, stratified by size (S/M/L) | 7.05 % (8.49 % with the df factor, df 7) | 20 min |
| instance bootstrap (resampling the 10 instances), 97.5 % quantile | 4.5 % | 1 min |
| max(KG, Kish), the 10 instances as clusters (effective n about 5) | about 55 % | none ≤ 60 min (U 52-56 % at every margin) |

Leaving one instance out pushes the pre-registered U(1 min) above 5 % in 3 of 10 cases: without L-grid-t50-s109
(5.50 %), M-geo-t25-s106 (5.38 %) or M-grid-t25-s105 (5.39 %), the three largest low-violation instances, whose
removal raises the pooled rate most. Per-instance rates at 1 min run from 0 % (M-geo-t25-s106) to 12.35 %
(M-grid-t75-s107; per-instance table below). None of this changes the experiment's outcome: the pre-registered rule
gives 1 min, and the decision is KEEP.

**Recommendation (pre-registered rule; primary set B1 `A8-g0`):**

| α | margin | pooled violation of counted residents | upper bound U | cost: B1 (dev, deterministic) | cost: B2 (5 seeds, this host) |
|---|---|---|---|---|---|
| 5 % | **1 min** | 2.46 % | 4.55 % | keeps 1231 of 1353 (91.0 %) | keeps 1698 of 1749 (97.1 %) |
| 1 % | **none ≤ 60 min** (U at 60 min: 1.62 %) | – | – | – | – |
| 1 %, KG bound only (sensitivity) | 30 min | 0.56 % | 0.99 % | keeps 956 of 1353 (70.7 %) | keeps 1284 of 1749 (73.4 %) |

- Secondary sets: B2 alone gives 0 min (α = 5 %) and 45 min (α = 1 %; KG only: 5 min); all K = 8 plans together give
  0 min and 60 min (KG only: 30 min).
- The 1 min margin removes the near-zero-slack trips (B1: 122 residents at < 1 min, 18 % of whom fail): it gives up 122
  claimed residents to avoid about 22 expected failures. 30 min gives up 397 to avoid about 47.
- The rule controls the **average** over counted residents. A resident whose slack is just above the margin is riskier
  than the average: 3.5-15 % per bin for B1 residents with 1-30 min of slack, 9.05 % pooled over those 275 residents
  (range corrected in the batch-1 review, 2026-11-01; it read 7-15 %). A margin that keeps every bin above it at ≤ 5 %
  would be about 30 min, at ≤ 1 % about 60 min (point estimates; post hoc reading of the bins, not the pre-registered
  rule).
- Leaderboard margin columns (`delivered_slack_ge_Xm`, the same prefix rule). B1 is deterministic and `A8-g0` is the
  harness's B1 plan, so B1's columns equal E3's numbers: slack ≥ 5 / 15 / 30 min keeps 1231 / 1189 / 956 of 1353. B2,
  5 seeds on this host (commit `c888a87b` on `evacplan/phase0`, read, not merged): 1523 / 1463 / 1284 of 1749 (87.1 /
  83.6 / 73.4 %; at 1 min 1698, 97.1 %; at 60 min 976, 55.8 %). B0 and B3 had no 5-seed rows on this host when this
  ran, so `margin_cost_baselines.csv` is empty; the leaderboard's margin columns show them. *Batch-1 review:* those
  B2 rows were replaced by B2's quiet re-run (one bench-lock hold, 14:56-15:49 UTC; the VM was slower than in the
  morning): 1499 / 1442 / 1263 of 1737 (medians; at 1 min 1677, at 60 min 1001).

**Post-hoc recommendation (orchestrator, batch-1 review; Siyeong decides).** As of 2026-11-01: provisional default
margin **30 min**, the smallest margin that passes both post-hoc readings at α = 5 %:
- the pre-registered cumulative rule with the instance as the sampling unit, because a default is meant for new
  instances (Korn-Graubard with the df factor, the standard interval for few clusters; a 10-cluster bootstrap tends to
  under-cover): 20 min (sensitivity table above);
- every slack bin above the margin at ≤ 5 %, because the rule controls only the average over counted residents and B1
  residents with 20-30 min of slack still fail at 7.5 % (bins above): about 30 min.
It is also a leaderboard column already. Cost at 30 min, from the leaderboard rows of this VM session (medians over
5 seeds): B2 1263 of 1737 (72.7 %, B2's quiet re-run), B1 956 of 1353 (70.7 %), E1 992 of 1444 (68.7 %), B0 1042 of
1157 (90.1 %); at 20 min 1394, 1090, 1110 and 1080 (80.3, 80.6, 76.9 and 93.3 %). Re-estimate on more instances and on
real hazards: H0 found the SYNTHETIC dev hazards much hotter than the Korean panel, and every E3 violation is flame
contact. The experiment's outcome is unchanged: KEEP, with 1 min from the pre-registered rule.

Post hoc (descriptive; `by_instance_margin.csv`): per instance, residents kept and their violation at m = 0 / 1 / 5 /
30 / 60 min. The pooled rule averages over very different instances:

| instance | plan | fresh members | m = 0 | m = 1 | m = 5 | m = 30 | m = 60 |
|---|---|---|---|---|---|---|---|
| S-grid-t25-s101 | A8 | 256 | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % |
| S-geo-t25-s102 | A8 | 256 | 37: 0.78 % | 37: 0.78 % | 37: 0.78 % | 27: 0.09 % | 20: 0.00 % |
| S-grid-t75-s103 | A8 | 256 | 20: 0.04 % | 20: 0.04 % | 20: 0.04 % | 0: – | 0: – |
| S-geo-t75-s104 | A8 | 256 | 24: 1.68 % | 10: 0.39 % | 10: 0.39 % | 0: – | 0: – |
| M-grid-t25-s105 | A8 | 256 | 163: 0.16 % | 163: 0.16 % | 163: 0.16 % | 163: 0.16 % | 135: 0.16 % |
| M-geo-t25-s106 | A8 | 256 | 155: 0.00 % | 155: 0.00 % | 155: 0.00 % | 155: 0.00 % | 129: 0.00 % |
| M-grid-t75-s107 | A8 | 256 | 100: 22.62 % | 46: 12.35 % | 46: 12.35 % | 1: 0.00 % | 1: 0.00 % |
| M-geo-t75-s108 | A8 | 164 | 101: 2.63 % | 101: 2.63 % | 101: 2.63 % | 101: 2.63 % | 41: 1.22 % |
| L-grid-t50-s109 | A8 | 64 | 335: 1.91 % | 281: 0.50 % | 281: 0.50 % | 225: 0.06 % | 208: 0.06 % |
| L-geo-t50-s110 | A8 | 64 | 395: 4.96 % | 395: 4.96 % | 395: 4.96 % | 261: 0.77 % | 250: 0.60 % |
| S-grid-t25-s101 | B2 | 256 | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % | 23: 1.43 % |
| S-geo-t25-s102 | B2 | 256 | 36: 0.81 % | 36: 0.81 % | 36: 0.81 % | 14: 0.00 % | 5: 0.00 % |
| S-grid-t75-s103 | B2 | 256 | 23: 0.41 % | 8: 0.00 % | 8: 0.00 % | 0: – | 0: – |
| S-geo-t75-s104 | B2 | 256 | 26: 2.03 % | 26: 2.03 % | 8: 0.00 % | 0: – | 0: – |
| M-grid-t25-s105 | B2 | 256 | 163: 0.67 % | 154: 0.32 % | 154: 0.32 % | 154: 0.32 % | 106: 0.21 % |
| M-geo-t25-s106 | B2 | 256 | 155: 0.05 % | 155: 0.05 % | 155: 0.05 % | 155: 0.05 % | 111: 0.00 % |
| M-grid-t75-s107 | B2 | 256 | 140: 15.88 % | 140: 15.88 % | 41: 1.87 % | 41: 1.87 % | 16: 0.00 % |
| M-geo-t75-s108 | B2 | 164 | 139: 0.73 % | 139: 0.73 % | 139: 0.73 % | 111: 0.60 % | 90: 0.00 % |

A margin removes the near-misses (M-grid-t75-s107, the L instances) but not the tail: on S-grid-t25-s101 every
delivered resident has at least 64 min of slack, yet 1.43 % fail, because a few fresh members burn the route more than
an hour before any of the instance's 8 members (and M-geo-t75-s108 keeps 2.6 % at 30 min). Those failures need more
members (or real-member validation), not a larger margin.

### Arrival diagnostic (conditioning of the instance members)

The lead is the earliest fire arrival at any facility over the instance's 8 members (fixed by the ignition bisection).
Share of fresh members whose earliest facility arrival is earlier (`diagnostic_arrivals.csv`; 1/9 = 11.1 % on average if
the members were exchangeable):

| instance | lead (min) | fresh planning members (32) earlier | fresh check members (256) earlier |
|---|---|---|---|
| S-grid-t25-s101 | 120 | 12.5 % | 29.3 % |
| S-geo-t25-s102 | 120 | 3.1 % | 3.5 % |
| S-grid-t75-s103 | 60 | 3.1 % | 0.8 % |
| S-geo-t75-s104 | 60 | 9.4 % | 2.3 % |
| M-grid-t25-s105 | 120 | 15.6 % | 7.0 % |
| M-geo-t25-s106 | 120 | 6.3 % | 4.7 % |
| M-grid-t75-s107 | 60 | 37.5 % | 27.0 % |
| M-geo-t75-s108 | 60 | 15.6 % | 5.9 % |
| L-grid-t50-s109 | 90 | 6.3 % | 4.7 % |
| L-geo-t50-s110 | 90 | 28.1 % | 18.0 % |

Mean over instances: 10.3 % of the check members. The bisection does not bias the instance's members on average, but 8
members are a small sample: the share of the distribution beyond their envelope is itself random. For one binding
statistic it is Beta(1, 8): mean 11 %, above 18 % for 20 % of instances and above 27 % for 8 %. That matches
M-grid-t75-s107 (27 %) and L-geo-t50-s110 (18 %), which carry 80 % of B1's violations (43 % and 37 % of the expected
violating residents), and S-grid-t25-s101 (29 %), the most extreme share. S-grid-t25-s101 is not a carrier (corrected
in the batch-1 review, 2026-11-01): its plan keeps at least 64 min of slack, which absorbs 68 of the 75 check members
that beat the lead; its per-resident rate is 1.43 %, 0.6 % of B1's violations. This is the scenario approach's
point: with K = 8 a plan's violation probability is a random variable with a wide spread, and a margin offsets only
part of it.

### Caveats

- **SYNTHETIC hazard model.** Every number is conditional on `hazard_contract.synthetic` with the generator's settings
  (rate CV 0.25, direction SD 15°, noise SD 0.2 over about 8 cells, persistent burning). H0 found these hazards much
  hotter than the Korean dev packets, and the member spread is a modelling assumption: the margin must be re-validated
  on real members (Track A) before it is used for real fires.
- **Fresh members share the instance's ignition, rate and direction**; they measure the model's member spread only, not
  structural error (another ignition, a wind shift outside the model), which would need a wider margin.
- **Few instances, one dominates.** 10 instances; M-grid-t75-s107 carries the largest share of the violations (B1: 43 %,
  with L-geo-t50-s110 37 %; B2: 87 %) and the L instances carry half the residents but were checked against 64 members
  only. The α = 5 % certificate covers these 10 instances only; with the instance as the sampling unit, Korn-Graubard
  moves the margin to 20 min (Q3; batch-1 review, 2026-11-01). The Kish bound is what makes α = 1 % uncertifiable: with
  zero violations it still needs about 370 effective (instance, member) clusters.
- **Two planners.** B1 and B2 run close to the fire on tight instances; E1 or other planners may distribute slack
  differently. The margin is a property of the plans, so it should be re-checked for each new method.
- **Slack is contact-only and capped at the horizon.** Here all violations were contact, so it measured the right
  thing; dose-driven failures would not show in the slack.
- **Conditioning.** The instance's members are conditioned through the ignition bisection. On average this does not
  bias them (10.3 % of fresh members beat the lead, 11.1 % expected), but per instance they can be unrepresentative
  (0.8-29 %); arm B is exactly exchangeable, arm A only on average.

### Next step

Propose to Siyeong, who decides the default robust count (updated in the batch-1 review, 2026-11-01): either the
pre-registered result, "delivered with slack ≥ 1 min" (α = 5 %, SYNTHETIC; it covers these 10 instances), or the
post-hoc recommendation, "≥ 30 min" as a provisional default (it passes both post-hoc readings: 20 min with the
instance as the sampling unit, about 30 min per slack bin; Q3). The strict view is ≥ 60 min (every bin ≤ 1 %, point
estimates); plan with K = 8 and use the margin rather than more members for robustness. Re-validate on real members from Track A, add more instances (the instance-level bound
depends on them; the L K curve and the replicate blocks, tiers T5L-T9, would also test the 1/K shape), and re-check the
margin for E1's plans.
