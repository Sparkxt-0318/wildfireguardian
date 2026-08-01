# w(t): evacuation failure as the walking budget tightens

**Artifact:** `data/processed/budget_sweep_experiment.json`
**Script:** `scripts/run_budget_sweep_experiment.py`
**Measured:** 2026-08-01 · PHASE 2-C-2

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
* **Time-aware routing is NOT hazard-aware.** A gentler detour is chosen for
  speed alone, and 3 more origins' detours cross the predicted fire. This cost is
  **constant at +3 across every budget**, because it has nothing to do with time.

At tight budgets the timing gain outweighs the safety cost (net +1 to +4). At
600 minutes the timing gain is exactly zero — nobody is over budget — so only the
safety cost remains, and the time objective is **worse by 3**.

**This is the operational value of terrain-aware routing, and its price.** The
brief expected the difference column to grow as budgets tighten; it does, but the
gain is bounded by a hazard-blindness cost that a status-quo router cannot avoid.
The obvious fix — rank by time *and* respect the hazard — is precisely what
`future_aware_route` already does, and is not a status-quo policy.

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

## The 6-bucket partition degrades under a binding budget

Applying the budget to `future_aware_route` as well:

| 예산 | both_safe | FA_only | no_safe_route | **unclassified** |
|---|---:|---:|---:|---:|
| 600분 | 440 | 17 | **3** | **0** |
| 120분 | 371 | 2 | **18** | **69** |
| 90분 | 342 | 2 | **18** | **98** |
| 60분 | 285 | 2 | **18** | **155** |
| 30분 | 205 | 2 | **18** | **235** |

Two things to state plainly:

1. **`no_safe_route` does move — 3 → 18, a 6× rise** — and saturates there,
   because it requires the naive route to enter the hazard (20 origins,
   budget-independent) *and* the future-aware route to fail. So the PHASE-2 null
   result was a budget artifact after all, for this bucket.
2. **`unclassified` explodes to 235.** This is a **partition defect exposed by
   the experiment, not a result.** The 6-bucket rule has no branch for "the naive
   route is safe but the future-aware route cannot finish within budget" — the
   commonest state once the budget binds — so those origins fall through to
   `unclassified`. The partition was designed when the budget never bound.

**Do not report the tight-budget bucket counts as if the partition were
meaningful there.** The `w(t)` table above is the sound measurement; the bucket
table is included because hiding it would be worse.

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

The `unclassified` blow-up says the classification needs a sixth honest category
before tight-budget bucket counts can be reported. And cause 3 — the hazard's
180-minute time resolution — is still untested; PHASE 2-C-3 addresses it.
