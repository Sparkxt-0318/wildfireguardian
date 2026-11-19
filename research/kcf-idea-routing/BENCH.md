# Benchmark and exactness results

Plan: `BENCH_PLAN.md`, frozen at commit `7f274a63` before any number below existed. Raw numbers:
`results/bench.json`, `results/bench.log`, `results/real/*.json`, `results/property_tests.json`,
`results/mutation_tests.json`. Run on 19 Nov 2026, 01:10–03:54 UTC, on the machine named in the plan (macOS arm64,
Python 3.13.13, pure Python for both methods, one process, nothing else of this study running).

"Existing" is `deadline_field.core.backward`, imported unchanged. "New" is `margin_field.field.margin_field`.
Every ratio is existing time / new time, so above 1 means the new method is faster.

## Result in four lines

* **Accuracy.** Zero mismatches everywhere: 12,000 random graphs against the existing field and the brute-force
  oracle, and all six recorded caches against the existing field.
* **Several margins (the task the method is built for).** Faster on every cache from K = 2 margins up: 1.5× to 4.7×
  at K = 2, 4.8× to 15.7× at K = 16, 150× to 1,500× for all 601 margins.
* **One field at margin 0 (the task the existing pass does today).** Faster on the three Uiseong–Andong caches
  (1.7× to 3.2×), **slower on the three Yeongdeok caches (0.55× to 0.61×)**. The claim "faster for one field" fails.
* **Memory.** One margin pass peaks at 1.5 to 2 times one existing pass, and at about one eighth of 16 existing
  fields kept side by side.

## Accuracy

| check | compared | mismatches |
|---|---|---|
| 12,000 random graphs (6,000 general with reopening, 6,000 closure-only), every margin 0..M: origin sets against the existing field | 240,820 sets | 0 |
| same graphs: origin sets against the brute-force oracle (`kcf-theorem/checker.py`), 3,151,772 departure seconds | 240,820 sets | 0 |
| same graphs: R and G of every state against the existing field | 662,174 sets | 0 |
| same graphs: one route followed under a random perturbation inside the margin (Theorem 2) | 320,589 routes | 0 invalid |
| six caches, router and cert rule, keep and erode variant, 551 shelter specs per rule, 8 margins: R and G of every state | 3,537,210,368 sets | 0 |
| six caches, same: issue set of every recorded origin | 50,368 sets | 0 |
| six caches: margin fixed-point certificate (equation E_μ) | 2,204 fields | 0 failures |
| six caches: witness routes at margins 0, 60, 600 checked by the independent checker | 8,892 routes | 0 invalid |
| benchmark T1, T2, T3 outputs (below) | all | 0 |

The random general family is a real test of reopening: 3,871 of its 8,214 non-empty margin-0 sets are not prefixes.
Five deliberate bugs planted in the new code were each caught by the same tests (`results/mutation_tests.json`).

On the six caches every recorded origin's issue set is a prefix `[0, L]` at every margin tested. So on this data the
margin field never needed its reopening machinery for the origins; that part is exercised by the random graphs.

## T1: one field, margin 0

Median over 6 sampled shelters of the median of 5 repeats.

| cache | edges | existing s | new s | ratio (median of 6) | per-shelter range | mismatches |
|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 43,826 | 0.151 | 0.089 | **1.68** | 1.35–4.85 | 0 |
| uiseong_andong_2025/20250324T090000Z | 43,826 | 0.274 | 0.084 | **3.25** | 1.05–6.11 | 0 |
| uiseong_andong_2025/20250325T170000Z | 43,826 | 0.124 | 0.068 | **1.88** | 0.92–4.43 | 0 |
| yeongdeok_2025/20250325T190000Z | 111,924 | 0.212 | 0.371 | **0.57** | 0.23–1.08 | 0 |
| yeongdeok_2025/20250325T230000Z | 111,924 | 0.233 | 0.382 | **0.61** | 0.29–0.92 | 0 |
| yeongdeok_2025/20250326T080000Z | 111,924 | 0.218 | 0.380 | **0.55** | 0.31–0.83 | 0 |

**"Faster for one field": not met** (3 of 6 caches). On Yeongdeok the new pass costs about 0.37 s whatever the
shelter, because it builds a tent for every one of the 111,924 edges before it starts; the existing pass only
touches the edges that can reach the shelter. I did not investigate further and did not tune after seeing this.

## T2: K margins

Ratio per cache (median of 6 shelters). New time includes the read-off of every state's R and G at each margin;
existing time excludes building the widened instances.

| cache | K=1 | K=2 | K=4 | K=8 | K=16 | lowest single shelter at K=2 | mismatches |
|---|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 1.41 | 2.47 | 4.10 | 6.19 | 8.28 | 1.95 | 0 |
| uiseong_andong_2025/20250324T090000Z | 2.77 | 4.70 | 7.88 | 11.71 | 15.67 | 1.44 | 0 |
| uiseong_andong_2025/20250325T170000Z | 1.63 | 2.91 | 4.85 | 7.26 | 9.65 | 1.46 | 0 |
| yeongdeok_2025/20250325T190000Z | 0.92 | 1.63 | 2.71 | 4.05 | 5.30 | 1.06 | 0 |
| yeongdeok_2025/20250325T230000Z | 0.86 | 1.55 | 2.37 | 3.52 | 4.97 | 1.06 | 0 |
| yeongdeok_2025/20250326T080000Z | 0.84 | 1.50 | 2.49 | 3.67 | 4.83 | 1.10 | 0 |

**"Faster for K margins": met for K = 2, 4, 8, 16 on all six caches; not met for K = 1** (Yeongdeok 0.84–0.92).
At K = 2 all 36 shelters are above 1; the closest is 1.06.

Where the time goes (seconds, median of 6 shelters):

| cache | K | existing s | widening s (not counted) | new pass s | new read-off s | new total s |
|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 2 | 0.299 | 0.171 | 0.091 | 0.025 | 0.120 |
| uiseong_andong_2025/20250323T010000Z | 16 | 2.363 | 0.822 | 0.091 | 0.190 | 0.289 |
| uiseong_andong_2025/20250324T090000Z | 2 | 0.542 | 0.185 | 0.092 | 0.026 | 0.118 |
| uiseong_andong_2025/20250324T090000Z | 16 | 4.406 | 0.832 | 0.092 | 0.200 | 0.291 |
| uiseong_andong_2025/20250325T170000Z | 2 | 0.247 | 0.263 | 0.070 | 0.018 | 0.088 |
| uiseong_andong_2025/20250325T170000Z | 16 | 1.980 | 0.912 | 0.070 | 0.141 | 0.211 |
| yeongdeok_2025/20250325T190000Z | 2 | 0.426 | 0.611 | 0.196 | 0.056 | 0.252 |
| yeongdeok_2025/20250325T190000Z | 16 | 3.394 | 2.239 | 0.196 | 0.420 | 0.615 |
| yeongdeok_2025/20250325T230000Z | 2 | 0.471 | 0.636 | 0.222 | 0.065 | 0.288 |
| yeongdeok_2025/20250325T230000Z | 16 | 3.928 | 2.295 | 0.222 | 0.518 | 0.735 |
| yeongdeok_2025/20250326T080000Z | 2 | 0.436 | 0.614 | 0.211 | 0.062 | 0.273 |
| yeongdeok_2025/20250326T080000Z | 16 | 3.535 | 2.206 | 0.211 | 0.468 | 0.678 |

At K = 16 most of the new method's time is the read-off of all states at 16 margins, not the pass.

## T3: every margin 0..600, origin windows

First sampled shelter of each cache, one repeat.

| cache | origins | existing s (601 passes) | widening s (not counted) | new s | ratio | margins with a mismatch |
|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 7 | 73.39 | 69.95 | 0.15 | 474 | 0 |
| uiseong_andong_2025/20250324T090000Z | 1 | 245.98 | 76.72 | 0.16 | 1519 | 0 |
| uiseong_andong_2025/20250325T170000Z | 1 | 91.09 | 73.89 | 0.14 | 630 | 0 |
| yeongdeok_2025/20250325T190000Z | 2 | 41.15 | 170.42 | 0.27 | 152 | 0 |
| yeongdeok_2025/20250325T230000Z | 2 | 178.83 | 179.28 | 0.33 | 550 | 0 |
| yeongdeok_2025/20250326T080000Z | 2 | 189.53 | 175.38 | 0.34 | 557 | 0 |

One repeat, so read these as orders of magnitude. The comparison is against running the existing pass once per
margin, which is the only way the existing code can produce this output; nobody had written a smarter baseline
(for instance a bisection over the margin, which would need about 10 passes per origin when only the largest margin
of one departure second is wanted).

## B: the 12,000 random graphs

60,078 existing passes (one per margin) 0.428 s (0.422–0.469); 12,000 margin passes 0.342 s (0.326–0.413);
ratio **1.25**. These graphs are tiny, so this mostly measures fixed overhead.

## Memory (MB, `tracemalloc`, first sampled shelter of each cache)

| cache | existing, one field: peak / kept | existing, 16 fields kept: peak / kept | new, M=600: peak / kept (μ, γ) / kept with tents |
|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 18 / 14 | 225 / 221 | 27 / 10 / 23 |
| uiseong_andong_2025/20250324T090000Z | 18 / 13 | 220 / 215 | 27 / 10 / 23 |
| uiseong_andong_2025/20250325T170000Z | 15 / 11 | 184 / 180 | 25 / 8 / 21 |
| yeongdeok_2025/20250325T190000Z | 27 / 16 | 265 / 254 | 53 / 9 / 42 |
| yeongdeok_2025/20250325T230000Z | 35 / 24 | 400 / 389 | 60 / 16 / 49 |
| yeongdeok_2025/20250326T080000Z | 39 / 28 | 460 / 449 | 63 / 19 / 52 |

Against one existing field the new method uses more memory at peak (1.5× to 2×), because of the tents. Against
16 fields kept it uses about one eighth. The largest number of pieces any state needed on the caches was 5.

## What the caches say about the margin itself

Of 1,482 place–shelter pairs with a leave-by time (cert rule), 1,457 keep the same leave-by time when every closure
is moved 600 s either way, 16 lose exactly 600 s, 9 lose part of it, none loses its window (figure, panel b).
On these six recorded hours the leave-by times are therefore mostly insensitive to closure timing; the margin field
is what shows that, and it is also a reason not to expect it to change many answers on this data.

## Deviations from the plan

* Memory: two rows were measured in addition to the three planned (new method keeping only μ and γ; new method with
  M = 0). Nothing planned was dropped. Recorded as an amendment in `BENCH_PLAN.md`.
* No other deviation. Nothing was re-run and no code was changed after the first benchmark number.

## Not claimed

Other machines; compiled implementations of either method (`kcf-defend/fastfield.py` is a compiled existing pass
and was not benchmarked, numba is not installed here); instances unlike these (H = 3,600 s, nearly one interval per
state); any speed advantage for a single field.
