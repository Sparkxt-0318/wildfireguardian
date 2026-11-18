# Benchmark plan (frozen before the benchmark is run)

Frozen 19 Nov 2026, Shanghai morning, at the commit that adds this file and `bench.py`. Nothing below changes after
the first benchmark number exists. A mistake found later is corrected by a dated amendment at the bottom, never by
editing this text.

## What had been seen when this was written

Not blind. Before freezing I had run:
* a probe on 3 specs of one cache (`uiseong_andong_2025/20250324T090000Z`, cert rule): existing pass 0.13–0.26 s;
  margin pass 0.09–0.15 s at M = 0 and 0.10–0.20 s at M = 600;
* the exactness run on that same cache (cert rule, 31 specs, both acceptance variants): 0 mismatches; 11.6 s for the
  62 margin passes against 115.1 s for the 496 existing passes at 8 margins;
* the 12,000-graph property test: 0 mismatches; 0.51 s for the margin passes against 0.83 s for the existing pass run
  once per margin.

These are single runs with other work on the machine. They are why I expect the method to be faster. They are not
the benchmark.

## Machine and conditions

This Mac (arm64, 15 logical cores), macOS, Python 3.13 (`/Users/jp/miniforge3/bin/python3`), pure Python, standard
library only for both methods. One process, one thread. No other job of this study runs during the benchmark; the
machine is otherwise a normal desktop and is not isolated, which is why every timing is repeated. `gc.collect()` before
each timed call; the collector stays on during the call. Timer: `time.perf_counter`. Both methods get the same
`Instance` object.

## Inputs

**A. The six recorded caches**, cert contact rule (the rule used for certified leave-by times). From each cache,
`random.Random(20261119).sample(sorted specs, 6)` destination specs (all of them if fewer than 6): at most 36
specs. Acceptance variant: keep. M = 600 s.

**B. The 12,000 random graphs of the property test** (seeds `margin-{general,closure}-{0..5999}`, with the M and the
acceptance variant the test draws for each), timed as one batch.

## Tasks, and what counts as the same output

| task | existing method | new method | output compared |
|---|---|---|---|
| **T1** one field, margin 0 | `backward(inst)` | `margin_field(inst, 0)` | R and G of every edge state |
| **T2(K)**, K = 1, 2, 4, 8, 16 margins. K = 1: m = 60. K ≥ 2: m_i = round(600 i / (K − 1)), i = 0..K − 1 | `backward(widen(inst, m_i))` for each i | one `margin_field(inst, 600)`, then `level_set` of every μ_s and γ_s at each m_i | R and G of every edge state at each m_i |
| **T3** every margin 0..600 (601 margins), origin windows | `backward(widen(inst, m))` + `issue_set` for the spec's origins, for each m | one `margin_field(inst, 600)`, `issue_margin` per origin, `level_set` at each m | the issue set of every origin at every m |
| **B** | `backward(widen(inst, m))` for m = 0..M | `margin_field(inst, M)` | (equality is the property test) |

Timing rules:
* The existing method's time **excludes** building the widened instance (`widen`), which favours the existing
  method. The widening time is reported in a separate column.
* The new method's time **includes** building the tents and, in T2 and T3, the read-off of the compared output.
  The pass alone is also reported.
* T1, T2, B: 5 repeats, alternating which method runs first; the reported value is the median, with min and max.
* T3: the first sampled spec of each cache only (6 specs), 1 repeat (601 existing passes per spec).

## Memory

On the first sampled spec of each cache, in a separate run with `tracemalloc` (never while timing): the peak during
the call and the size retained by the result, for (i) one existing pass at margin 0, (ii) 16 existing passes with all
16 fields kept, (iii) one margin pass with M = 600 (tents included).

## Accuracy

Every output named above is compared for exact equality, outside the timed region. The number of mismatches is
reported per task. Exactness against the brute-force oracle is the property test (`tests/test_margin_field.py`), and
exactness on all specs of all six caches under both contact rules is `real_caches.py`; `BENCH.md` reports both.

## What will be claimed

Ratios are existing time / new time per spec; per cache the median over its sampled specs.

* **"Faster for one field"**: the T1 ratio is above 1 on every one of the six caches.
* **"Faster for K margins"**: the T2(K) ratio (new method with read-off, existing method without widening) is above 1
  on every one of the six caches.
* The Stage 5 verdict says FASTER only if there are **zero mismatches anywhere** and "faster for K margins" holds at
  **K = 2**, that is, as soon as more than one margin is wanted. The T1 and K = 1 results are stated next to the
  verdict whichever way they come out. If T2(2) fails on any cache the verdict is NOT FASTER.
* Memory is reported as measured, third in priority, with no pass or fail rule.
* No claim is made for any other machine, for compiled implementations of either method, or for instances unlike
  these (H = 3,600 s, one interval per state at margin 0).

## Amendments

(none)
