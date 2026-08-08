# w(t): evacuation failure as the walking budget tightens

**Artifacts:** `data/processed/objective_budget_canonical.json` (current) ·
`budget_sweep_experiment.json` (earlier reading)
**Scripts:** `scripts/run_canonical_objective_and_budget.py` (current) ·
`scripts/run_budget_sweep_experiment.py` (earlier)
**Measured:** 2026-08-01, **re-measured 2026-08-02 on the canonical hazard field**

## The canonical-field re-run (2026-08-02)

The earlier sweep consumed `routing_demo.npz`, the near-static field of the run
reverted on 2026-07-21 ([`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json)).
The canonical field's ≥ 0.5 core is four times larger. Same network, same DEM,
same definitions — `w`, `route_hilliness` and the origin rule are **imported**
from the committed scripts, not restated.

| 예산 | 거리 기반 w (폐기 장) | **거리 기반 w (정본)** | 시간 기반 w (정본) | 차이 | FA 예산 초과 |
|---|---:|---:|---:|---:|---:|
| 30분 | 55.00 % | **56.55 %** (259) | 56.33 % (258) | **+1** | 216 |
| 60분 | 38.26 % | **40.17 %** (184) | 39.30 % (180) | **+4** | 139 |
| 90분 | 26.09 % | **28.38 %** (130) | 27.95 % (128) | **+2** | 85 |
| 120분 | 19.78 % | **22.27 %** (102) | 21.62 % (99) | **+3** | 56 |
| 600분 | 4.35 % | **9.61 %** (44) | 9.83 % (45) | **−1** | **0** |

Denominator **458** origins (460 on the earlier field; the t0 core grew, so two
more nodes start at or above `p_cut`).

> ⚠ **영덕 절대 비율에 대한 단서** — 영덕 수치는 정본 화재 핵심의 **32.6 %만
> 덮는** 보행망에서 산출되었습니다. 나머지 3분의 2에 있는 출발지들의 거동은
> 측정되지 않았으며, 편향의 방향도 알려져 있지 않습니다. 지역 간 비교에서 영덕
> 행을 인용할 때는 이 열을 반드시 함께 제시하십시오.
> ([`walk_bbox_coverage.md`](walk_bbox_coverage.md) · 재취득하지 않기로 2026-08-02
> 확정) **짝지어진 대비는 영향받지 않습니다** — 두 arm이 같은 출발지를 쓰므로
> 표본 프레임이 상쇄됩니다.

### The 600-minute budget still does not bind

`fa_exceeds_budget` is **0 at 600 minutes on the canonical field too**, and the
"차이" column is unchanged at +1 / +4 / +2 / +3. That is not a coincidence: a
budget failure is a **walk-time** failure, and walk time is a property of the
graph and the DEM, neither of which moved. What moved is the **hazard**, and it
shows up in the other failure cause.

### Failure ratio 12.6× → 5.9×, and the reason is a raised floor

| | 폐기 장 | 정본 |
|---|---:|---:|
| w(30분) | 55.00 % | 56.55 % |
| w(600분) | 4.35 % | 9.61 % |
| 비율 | **12.65×** | **5.89×** |

The tight-budget end barely moved (+1.55 pp) because it is dominated by walking
time. The loose-budget end more than doubled (4.35 → 9.61 %) because at 600
minutes nothing fails on time and **everything that fails, fails by entering the
fire**. A bigger fire raises the floor; it does not change the ceiling.

### ⚠ Hazard entry doubled — and it is still the baseline's, not the system's

| | 폐기 장 | 정본 |
|---|---:|---:|
| 거리 기반 `enters_hazard` | 20 | **44** |
| 시간 기반 `enters_hazard` | 23 | **45** |
| `both_enter` (제안 시스템) | **0** at every budget | **0** at every budget |

These are failures of the **fire-blind status-quo route**. `future_aware_route`
never enters the hazard — `both_enter` is 0 at every budget on both fields.
**Never restate a rising `enters_hazard` as a cost of the proposed system.** The
number doubled because the fire is four times larger, so a fire-blind walk is
more likely to walk into it. That is the argument *for* the system.

The 44 is the same 44 as the routing run's `FA_only + no_safe_route` = 42 + 2.
It is budget-independent by construction: hazard entry is tested before the
budget is.

---

# ── EARLIER READING (reverted hazard field) ──────────────────────

Everything from here on was measured on `routing_demo.npz`. Retained because the
contrast — a raised floor with an unchanged ceiling — is only legible against it.

## What this closes

Round-2 **Ⅴ-2** listed the 30 / 60 / 90-minute `w(t)` sweep as future work, and
the Round-2 documents recorded as a stated limitation that **600 minutes is an
algorithmic ceiling, not an operational evacuation window**. This experiment
closes that item and turns the caveat into numbers.

## ⚠ This does not replace the committed w ≈ 11.4 %

> 600분 기준 w ≈ 11.4%는 커밋된 값이며 유효합니다. 본 실험의 단축 예산 w(t)는
> 운영 조건에서의 추가 측정이며 대체값이 아닙니다.

The committed figure is a **600-minute** result from the **439-origin rescue
pipeline** over **n_mobile = 307**. It stands. Everything below is a *different
denominator* (460 scanned origins on the 2026-07-24 snapshot network) under
*operational* budgets. The two are complementary, not competing.

**Never quote a short-budget w without its budget.** The 30-minute figure is
55 %; stated bare it is simply wrong.

## Definitions — read before quoting

An origin is **evacuable within budget t** under objective *O* if its status-quo
route (nearest shelter, ranked by *O*) **reaches** a shelter, **does not enter**
the predicted hazard, **and** takes **≤ t minutes**.

    w(t, O) = 1 − evacuable / 460

`naive_route` carries no budget of its own, so the budget is applied explicitly
to its traversal time. That is the operational question: *can this resident, who
walks to the nearest shelter, actually get there in time?*

## Main result

| 예산 | 거리 기반 도달 불가 | 시간 기반 도달 불가 | 차이 |
|---|---:|---:|---:|
| 30분 | **55.00 %** (253) | **54.78 %** (252) | **+1** |
| 60분 | **38.26 %** (176) | **37.39 %** (172) | **+4** |
| 90분 | **26.09 %** (120) | **25.65 %** (118) | **+2** |
| 120분 | **19.78 %** (91) | **19.13 %** (88) | **+3** |
| 600분 (대조) | **4.35 %** (20) | **5.00 %** (23) | **−3** |

**The dominant finding is the vertical axis, not the horizontal one.** Failure
rises from **4.35 % at 600 minutes to 55.00 % at 30 minutes — a 12.6× increase.**
At a realistic warning time, **more than half** of the scanned origins cannot
walk to a safe refuge. The 600-minute ceiling was concealing that, exactly as the
Round-2 limitation warned.

## Why the difference column is small — and negative at 600 minutes

Decomposing each failure by cause makes the trade-off explicit:

| 예산 | over-budget (거리 → 시간) | enters-hazard (거리 → 시간) |
|---|---|---|
| 30분 | 233 → 229 (**−4**) | 20 → 23 (**+3**) |
| 60분 | 156 → 149 (**−7**) | 20 → 23 (**+3**) |
| 90분 | 100 → 95 (**−5**) | 20 → 23 (**+3**) |
| 120분 | 71 → 65 (**−6**) | 20 → 23 (**+3**) |
| 600분 | 0 → 0 (**0**) | 20 → 23 (**+3**) |

Two opposing effects:

* **Time-aware routing consistently beats the clock**, saving 4–7 origins from
  the budget constraint at every binding budget.
* **The fire-blind baseline puts 3 more origins into the hazard.** Constant at
  +3 across every budget, because it has nothing to do with time.

### ⚠ Where the +3 belongs

**Both of these numbers are `naive_route` numbers, and `naive_route` is the
fire-blind BASELINE.** It is the status quo — "walk to the nearest shelter" — and
its path never sees the fire under *either* objective; the hazard is only used to
*score* it afterwards. Telling that baseline about terrain makes it faster. It
does not, and cannot, make it safer.

**This is not a cost of the proposed system.** `future_aware_route` minimises
cumulative exposure on a time-expanded graph and refuses any node at or above
`p_cut`, so it cannot enter the hazard at all. Measured across every budget in
this sweep, `both_enter` — the only bucket in which the future-aware route enters
the hazard — is **0**. Asserted in
`tests/test_partition_categories.py::test_hazard_entry_is_a_baseline_property_not_a_system_cost`.

So the +3 is **direct evidence for the rescue-aware routing layer, not against
it**: it shows that giving a fire-blind router better terrain information does
not produce safety, and that hazard-awareness has to be a separate capability.
A reader who attributes the +3 to the proposed system has inverted the finding.

At tight budgets the baseline's timing gain outweighs its hazard cost (net +1 to
+4). At 600 minutes the timing gain is exactly zero — nobody is over budget — so
only the baseline's hazard-blindness remains, and the time-ranked baseline is
**worse by 3**.

## Who gets rescued: steep-terrain residents

Route "hilliness" = (slope traversal time / flat traversal time − 1) along an
origin's route.

| 예산 | 구제된 출발지 | 그 경로의 평균 급경사도 | 전체 평균 | 배율 |
|---|---:|---:|---:|---:|
| 30분 | 1 | **+52.1 %** | +18.4 % | **×2.84** |
| 60분 | 4 | **+30.8 %** | +18.4 % | ×1.68 |
| 90분 | 2 | **+28.7 %** | +18.4 % | ×1.56 |
| 120분 | 3 | **+45.0 %** | +18.4 % | **×2.45** |
| 600분 | 2 | +28.4 % | +18.4 % | ×1.55 |

The origins the time objective rescues sit on routes **1.6–2.8× hillier than
average**, and the effect is strongest at the tightest budget. They are
concentrated in steep terrain, exactly as the mechanism predicts. The counts are
small (1–4), so this is directional evidence about *who* benefits, not a
population estimate.

## The partition, with its sixth category

Applying the budget to `future_aware_route` as well:

| 예산 | both_safe | FA_only | no_safe_route | **fa_exceeds_budget** | unclassified | 합계 |
|---|---:|---:|---:|---:|---:|---:|
| 600분 | 440 | 17 | **3** | **0** | 0 | 460 |
| 120분 | 371 | 2 | **18** | **69** | 0 | 460 |
| 90분 | 342 | 2 | **18** | **98** | 0 | 460 |
| 60분 | 285 | 2 | **18** | **155** | 0 | 460 |
| 30분 | 205 | 2 | **18** | **235** | 0 | 460 |

(`both_enter` and `naive_unreachable` are 0 at every budget and omitted for
width; the six categories sum to 460 throughout — partition completeness is
asserted in the test suite.)

Two things to state plainly:

1. **`no_safe_route` does move — 3 → 18, a 6× rise** — and saturates there,
   because it requires the naive route to enter the hazard (20 origins,
   budget-independent) *and* the future-aware route to fail. So the PHASE-2 null
   result was a budget artifact after all, for this bucket.
2. **`fa_exceeds_budget` carries the load**, rising monotonically to 235 of 460
   as the budget tightens. **`unclassified` is 0 at every budget.**

Before PHASE 2-C-2 those 235 origins fell through every branch into
`unclassified`, because the original five-category rule was written when the
budget never bound and had no branch for "the naive route is safe but the
future-aware router cannot finish in time" — the commonest state once it does.
That state has a meaning, so it now has a name.

**The addition is strictly additive.** The five original categories keep their
definitions and their evaluation order. At a 600-minute budget the new category
is empty and the counts are exactly 440 / 17 / 3 / 0 / 0, so the committed
459-origin reading is untouched.

> ⚠ **제출 시점 기록입니다.** 440 / 17 / 3 / 0 / 0 은 되돌려진 실행의 위험면 위
> 값이며, 정본 재산출값은 **414 / 42 / 2 / 0 / 0** 입니다
> ([`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §2-A). ⚠ **위 문단의 주장 자체는
> 영향받지 않습니다** — 요점은 「600분 예산에서 새 범주가 비어 있어 기존 판독이
> 그대로 유지된다」는 *가산성*이고, 그것은 두 위험면 모두에서 성립합니다. Regression-tested in
`tests/test_partition_categories.py`.

These bucket counts are now reportable results rather than an artifact.

## Reporting rules

* Always pair a `w` with its budget. `w = 55 %` alone is meaningless.
* These are snapshot-network (2026-07-24) values on 460 origins. They do not
  supersede the committed 459-origin figures, whose network is unrecoverable
  ([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md)).
* The committed `w ≈ 11.4 %` (600 min, n_mobile = 307, rescue pipeline) is
  unchanged and remains the citable figure for that quantity.
* The time objective is **opt-in**; `length_m` remains the default
  ([`slope_integration.md`](slope_integration.md)).
* Registered in [`NUMBERS.json`](NUMBERS.json) as `budget_*`.

## What this does not settle

Cause 3 — the hazard's 180-minute time resolution — is still untested. Its
priority has fallen: `no_safe_route` moving 3 → 18 shows the budget was the
main blocker, so the remaining resolution effect is a refinement rather than
an explanation.
