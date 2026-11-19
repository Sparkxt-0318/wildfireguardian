# Benchmark and exactness results

Two rounds. **§1 (round 1)** is below, unchanged since it was written. **§2 (round 2)**, at the end, measures the
method after the fast path and the compiled port were added; it has its own frozen plan, `BENCH_PLAN_V2.md`.
Where the two disagree about speed, round 2 describes the code as it is now.

# §1 Round 1

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

# §2 Round 2

Plan: `BENCH_PLAN_V2.md`, frozen at commit `b8494a7c` before numba was installed and before any compiled timing
existed. Raw numbers: `results/bench2.json`, `results/bench2.log`, `results/real_fast/*.json`. Run on 19 Nov 2026,
12:13–14:32 UTC, same machine, `.venv-kcf/bin/python` (Python 3.13.13, numba 0.68.1, numpy 2.5.0), one process,
nothing else of this study running.

Methods: EXISTING = `deadline_field.core.backward`, unchanged; NEW = `margin_field` with the fast path
(`METHOD.md` §4.6); V1 = the round-1 method (`fast=False`); NB = the compiled port (`margin_field/nb.py`); NB0 = the
same compiled kernel run at M = 0, once per margin.

## Result in six lines

* **Accuracy.** Zero mismatches everywhere, again: 18,000 random graphs, the six caches re-run with the fast path,
  and every output of this benchmark (36 shelters, all tasks, all methods).
* **One field at margin 0.** NEW is now faster than EXISTING on **all six caches**: 2.0× to 6.0× (median of 6
  shelters), and on all 36 shelters (lowest 1.41×). The round-1 failure on Yeongdeok (0.55× to 0.61×) is gone.
* **K margins.** Faster on all six caches at every K: 1.3× to 3.9× at K = 1, 2.2× to 6.1× at K = 2, 4.0× to 16.4×
  at K = 16.
* **Where the single-field speed comes from.** From the fast path, which is engineering, not from the margin idea.
  With the same engineering on both sides (NB against NB0 at K = 1) the margin pass is **slower** than a pass for
  one margin: 0.88× to 0.95×. The idea pays from the second margin on: 1.6× at K = 2, 3.9× to 7.0× at K = 16.
* **Margin of leaving now.** 18× to 47× faster than the bisection in the plan. That bisection is a weak baseline on
  this data; see T4.
* **Memory.** NEW now peaks below one existing pass on every cache (0.64× to 0.86×).

## Accuracy, round 2

| check | compared | mismatches |
|---|---|---|
| 18,000 random graphs (general with reopening, closure-only, sparse; 6,000 each), every margin: against the existing field and the brute-force oracle | as `results/property_tests.json` | 0 |
| same graphs: fast path against the general path, every state | 99,176 states | 0 |
| same graphs: compiled port against the reference pass (run compiled and as plain Python) | 99,176 states | 0 |
| same graphs: Theorem 6 (stability under shifted closures) | 838,729 pairs | 0 violations |
| six caches re-run with the fast path, router and cert rule, both acceptance variants: R and G of every state | 3,537,210,368 sets | 0 |
| six caches, same: origin issue sets | 50,368 sets | 0 |
| six caches: witness routes checked by the independent checker | 8,892 routes | 0 invalid |
| this benchmark: T1 (NEW, V1: R and G; NB: R), T2 (NEW at every K; NB against EXISTING at 0, 60, 600; NB against NB0 at every margin), T4 margins | 36 shelters | 0 |

Eight planted bugs, three of them in the fast path, were each caught (`results/mutation_tests.json`). The two
rarest are caught on few graphs: `fast_skip_too_eager` on 2 of 9,000, `fast_wait_not_closed` on 34 of 9,000. The
compiled port never fell back to Python and never needed more than its first buffer size.

## T1: one field, margin 0

Median over 6 sampled shelters of the median of 5 repeats. Ratios are EXISTING / method.

| cache | existing s | NEW s | V1 s | NB s | **EXISTING / NEW** | per-shelter range | EXISTING / V1 | EXISTING / NB |
|---|---|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 0.148 | 0.049 | 0.091 | 0.021 | **3.04** | 2.46–8.68 | 1.65 | 7.4 |
| uiseong_andong_2025/20250324T090000Z | 0.281 | 0.048 | 0.089 | 0.020 | **5.98** | 1.93–10.49 | 3.21 | 13.2 |
| uiseong_andong_2025/20250325T170000Z | 0.131 | 0.035 | 0.071 | 0.021 | **3.99** | 2.23–8.86 | 1.91 | 6.3 |
| yeongdeok_2025/20250325T190000Z | 0.259 | 0.124 | 0.233 | 0.061 | **2.32** | 1.79–3.09 | 1.02 | 4.4 |
| yeongdeok_2025/20250325T230000Z | 0.291 | 0.136 | 0.363 | 0.066 | **2.28** | 1.63–3.94 | 0.79 | 4.5 |
| yeongdeok_2025/20250326T080000Z | 0.328 | 0.192 | 0.631 | 0.075 | **1.99** | 1.41–2.99 | 0.60 | 4.2 |

**"Faster for one field": met** on all six caches. V1 reproduces round 1 (slower on Yeongdeok), so the change is
the fast path and not the day or the interpreter. NB's time here includes packing the graph into arrays, which is
most of it (the compiled pass alone takes 0.007 to 0.03 s).

**What this does and does not show.** The fast path skips work the existing pass does (it builds nothing for edges
it never reaches, and crosses a closure-free edge with one constant piece). The existing pass could be given the
same treatment. So T1 shows that this implementation is faster than the existing implementation at the existing
job; it does not show that computing margins is cheaper than computing one level. The like-for-like comparison is
the NB0 / NB column of T2 at K = 1, and it goes the other way.

## T2: K margins

Median of 6 shelters. Top number EXISTING / NEW (pure Python, the claim); below it NB0 / NB (compiled against
compiled, the same kernel, one pass per margin against one margin pass).

| cache | | K=1 | K=2 | K=4 | K=8 | K=16 | lowest single shelter, K=1 / K=2 |
|---|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | EXISTING / NEW | 2.36 | 3.99 | 6.02 | 8.19 | 10.00 | 1.69 / 3.02 |
| | NB0 / NB | 0.89 | 1.57 | 2.64 | 4.06 | 5.82 | |
| uiseong_andong_2025/20250324T090000Z | EXISTING / NEW | 3.94 | 6.07 | 10.29 | 13.93 | 16.37 | 1.05 / 1.81 |
| | NB0 / NB | 0.88 | 1.61 | 2.76 | 4.10 | 6.13 | |
| uiseong_andong_2025/20250325T170000Z | EXISTING / NEW | 2.86 | 4.91 | 7.33 | 9.55 | 10.94 | 1.57 / 2.58 |
| | NB0 / NB | 0.90 | 1.61 | 2.92 | 4.45 | 6.98 | |
| yeongdeok_2025/20250325T190000Z | EXISTING / NEW | 1.62 | 2.55 | 3.50 | 4.49 | 5.39 | 1.27 / 2.04 |
| | NB0 / NB | 0.90 | 1.65 | 2.58 | 3.29 | 4.70 | |
| yeongdeok_2025/20250325T230000Z | EXISTING / NEW | 1.57 | 2.49 | 3.60 | 4.40 | 4.92 | 0.92 / 1.59 |
| | NB0 / NB | 0.95 | 1.69 | 2.90 | 3.90 | 5.17 | |
| yeongdeok_2025/20250326T080000Z | EXISTING / NEW | 1.30 | 2.21 | 3.02 | 3.63 | 4.03 | 1.00 / 1.57 |
| | NB0 / NB | 0.88 | 1.58 | 2.53 | 3.26 | 3.90 | |

**"Faster for K margins": met at every K on all six caches** by the frozen rule (median of the cache's 6
shelters). At K = 1 one shelter of 36 is below 1 (0.92) and one is at 1.00; from K = 2 all 36 are above 1.5.

**NB against NB0.** At K = 1 the margin pass is 5% to 12% slower than a compiled pass for that one margin, on every
cache. That is the honest price of the idea: carrying piecewise-linear functions instead of level sets costs a
little, and one margin gives nothing back. At K = 2 it is 1.6× faster on every cache and the ratio grows with K.
Both sides are my code, so this says nothing about the existing code.

EXISTING / NB (interpreted against compiled, **not like for like**, not a claim): 10× to 31× at K = 1, 45× to 182×
at K = 16.

## T4: the margin of leaving now

For every recorded origin of the shelter, the largest margin up to 600 s at which leaving at second 0 still works.

| cache | origins (6 shelters) | EXISTING bisection s | passes | NEW s | ratio (median of 6) | range | mismatches |
|---|---|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 23 | 1.57 | 10 | 0.055 | **29.3** | 21.9–70.3 | 0 |
| uiseong_andong_2025/20250324T090000Z | 16 | 2.84 | 10 | 0.060 | **47.4** | 12.9–98.1 | 0 |
| uiseong_andong_2025/20250325T170000Z | 16 | 1.40 | 10 (one shelter 18) | 0.036 | **38.7** | 26.7–85.8 | 0 |
| yeongdeok_2025/20250325T190000Z | 7 | 2.57 | 10 | 0.136 | **23.1** | 16.1–31.4 | 0 |
| yeongdeok_2025/20250325T230000Z | 9 | 2.97 | 10 | 0.156 | **22.9** | 13.9–35.1 | 0 |
| yeongdeok_2025/20250326T080000Z | 8 | 3.46 | 10 | 0.189 | **17.8** | 14.8–28.0 | 0 |

**"Faster than bisection": met as frozen, but the baseline is weaker than it should have been.** Of the 79
origins, 74 have margin 600 (the cap) and 5 cannot leave at second 0 at all. The bisection in the plan does not
test the two ends first, so it spent about 10 passes to find an answer that one pass at m = 600 (or at m = 0)
would have settled. A bisection that tests the ends first would need 1 or 2 existing passes on every one of these
shelters, and the fair ratio is then about the T2 figure at K = 1 or K = 2: 1.3× to 6×, not 18× to 47×. I saw this
only in the results; the plan is not changed and the numbers above are what it measured. The large ratios would
apply to data where margins fall strictly between 0 and the cap, which these six hours do not contain.

## B: the 18,000 random graphs

90,172 existing passes 0.759 s (0.749–0.769); 18,000 margin passes 0.480 s (0.474–0.490); ratio **1.58**. Tiny
graphs; mostly fixed overhead.

## Memory, round 2 (MB, `tracemalloc`, first sampled shelter of each cache)

| cache | EXISTING one field: peak / kept | NEW, M=600: peak / kept | NEW, M=0: peak / kept | NB result arrays |
|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 18.0 / 13.8 | 15.3 / 10.5 | 15.2 / 10.3 | 22.8 |
| uiseong_andong_2025/20250324T090000Z | 17.8 / 13.5 | 15.2 / 10.5 | 14.9 / 10.2 | 22.8 |
| uiseong_andong_2025/20250325T170000Z | 15.5 / 11.2 | 12.8 / 9.0 | 12.7 / 9.0 | 22.8 |
| yeongdeok_2025/20250325T190000Z | 26.6 / 15.9 | 17.0 / 16.1 | 17.0 / 16.1 | 58.2 |
| yeongdeok_2025/20250325T230000Z | 35.2 / 24.3 | 27.5 / 20.4 | 27.5 / 20.4 | 58.2 |
| yeongdeok_2025/20250326T080000Z | 38.9 / 28.1 | 31.1 / 22.4 | 31.1 / 22.4 | 58.2 |

With lazy tents the pure-Python margin pass peaks at 0.64× to 0.86× of one existing pass (round 1: 1.5× to 2×).
The compiled port's result arrays are fixed-size (16 piece slots per state) and larger than either; no peak is
claimed for it.

## What round 2 decides

The frozen rule: the single-field caveat leaves the verdict only if T1 and T2 at K = 1 hold on all six caches,
round 2 has zero mismatches, and the six-cache run with the fast path has zero mismatches. All four hold. **The
caveat "slower for a single field on three caches" is removed.** It is replaced by a different and smaller one,
which the plan required to be stated either way: the single-field speed is the fast path's, and like for like the
margin pass costs 5% to 12% more than a pass for one margin.

## Deviations from the round-2 plan

* None in tasks, inputs, repeats or rules. Nothing was re-run and no code changed after the first round-2 number.
* The compiled port compiled as frozen; no change was needed.
* The T4 baseline weakness above was found in the results and is reported, not repaired. Recorded as an amendment
  in `BENCH_PLAN_V2.md`.

## Not claimed (round 2)

Other machines; a compiled or fast-path form of the existing pass (none exists; NB0 is my stand-in, not the
existing code); any speed advantage of the margin idea itself for a single margin; the T4 ratios as typical of a
well-ordered bisection; instances unlike these.
