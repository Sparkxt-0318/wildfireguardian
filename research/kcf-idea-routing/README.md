# kcf-idea-routing: the one-pass margin field

A research task in five stages. Stage reached: **5 (complete)**, 19 Nov 2026.

**Verdict: NEW, PROVED AND FASTER.**

Read the verdict with its three limits:

1. *New* covers Theorem 2 (one route is valid for every closure-timing error up to the margin) and the one-pass
   algorithm (Theorems 4, 5). Theorem 1 is an instance of a published theorem (Bruns and Godefroid 2004) and
   Proposition 3 is a known phenomenon. The search record is `METHOD.md` §6 and `survey_notes/`.
2. *Faster* is by the rule frozen in `BENCH_PLAN.md`: zero mismatches, and faster than the existing backward pass on
   all six recorded caches as soon as two margins are wanted (1.5× to 4.7×).
3. For a single field at margin 0, which is what the existing pass computes today, it is faster on three caches and
   **slower on the other three (0.55× to 0.61×)**. For one non-zero margin it is slower on those same three
   (0.84× to 0.92×).

If "faster" is read as "faster at the existing pass's own single-field job on every cache", the result is
NEW AND PROVED, NOT FASTER.

## Files

| file | what |
|---|---|
| `SUMMARY.md` | half-page plain-English summary |
| `SURVEY.md`, `survey_notes/` | stage 1: literature survey and the unedited search notes |
| `CANDIDATES.md` | stage 2: seven candidate directions and the choice |
| `METHOD.md` | stage 3: definitions, theorems, complete proofs, cost, prior-art search |
| `margin_field/` | the implementation (`pl.py` piecewise-linear functions, `field.py` the pass) |
| `tests/test_margin_field.py` | 12,000 random graphs against the existing field and the brute-force oracle; planted bugs |
| `real_caches.py` | exactness on the six recorded caches |
| `BENCH_PLAN.md`, `bench.py`, `BENCH.md` | frozen plan, benchmark, results |
| `figures/margin_field.png`, `make_figure.py` | the figure |
| `results/` | raw outputs |

No existing file outside this folder was changed. The existing pass is imported from
`research/harness-2026-11/F-3.1/deadline_field` and the oracle from `research/kcf-theorem`.

## Reproduce

From the repository root, Python 3.13, standard library only (matplotlib for the figure). The recorded-cache steps
need the frozen routing inputs under `data/routing` (not in git).

```bash
python3 -m unittest research/kcf-idea-routing/tests/test_margin_field.py -v
```

```bash
python3 research/kcf-idea-routing/real_caches.py --data-root data/routing --out research/kcf-idea-routing/results/real/all.json
```

```bash
python3 research/kcf-idea-routing/bench.py --data-root data/routing --out research/kcf-idea-routing/results/bench.json
```

```bash
python3 research/kcf-idea-routing/make_figure.py
```

The tests take about half a minute, the cache check a few hours on one core, the benchmark about three hours.
