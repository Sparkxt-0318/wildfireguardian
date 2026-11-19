# kcf-idea-routing: the one-pass margin field

A research task in five stages. Stage reached: **5 (complete)**, 19 Nov 2026, after two rounds.

**Verdict: NEW, PROVED AND FASTER.**

Read the verdict with its limits:

1. *New* is narrow. Not found published after three searches: the one-pass algorithm on cyclic graphs (Theorems 4,
   5), Theorem 2 for closure timing (one route is valid for every timing error up to the margin), and Theorem 6
   for a routing model (the margin moves by at most d when closure times move by at most d). Known: Theorem 1 (an
   instance of Bruns and Godefroid 2004), the kind of quantity (a robustness radius), the mechanism of Theorem 2,
   every ingredient of Theorem 6, and Proposition 3 as a phenomenon. The three closest works are Donzé and Maler
   2010 with Rodionova et al. 2022, Bruns and Godefroid 2004, and Clement et al. 2020. Record: `METHOD.md` §6,
   `survey_notes/`.
2. *Proved*: complete proofs in `METHOD.md`; zero mismatches against the existing field and the brute-force oracle
   on 18,000 random graphs, and against the existing field on the six recorded caches.
3. *Faster*, pure Python against the existing pure Python, by rules frozen before each run (`BENCH_PLAN.md`,
   `BENCH_PLAN_V2.md`): on all six caches, 2.0× to 6.0× for a single field at margin 0, and 2.2× to 6.1× at two
   margins up to 4.0× to 16.4× at sixteen.
4. The single-field speed is the fast path's (round-2 engineering), not the margin idea's. Like for like (the
   compiled kernel at M = 600 against the same kernel at M = 0) the margin pass is **5% to 12% slower for one
   margin** and faster from two (1.6×) up. Round 1, before the fast path, was slower for a single field on three
   caches (0.55× to 0.61×); those numbers stay in `BENCH.md` §1.
5. The "margin of leaving now" comparison (18× to 47×) was against a bisection that did not test the end points
   first; on this data a better-ordered one would cut it to about 1.3× to 6×.

If "faster" must mean "the idea itself beats a single level pass with equal engineering", the result for one
margin is NEW AND PROVED, NOT FASTER; for two or more margins it is faster on every measure taken.

## Files

| file | what |
|---|---|
| `SUMMARY.md` | half-page plain-English summary |
| `SURVEY.md`, `survey_notes/` | stage 1: literature survey and the unedited search notes |
| `CANDIDATES.md` | stage 2: seven candidate directions and the choice |
| `METHOD.md` | stage 3: definitions, theorems, complete proofs, cost, prior-art search |
| `margin_field/` | the implementation (`pl.py` piecewise-linear functions, `field.py` the pass and its fast path, `nb.py` the compiled port) |
| `tests/test_margin_field.py` | 18,000 random graphs against the existing field and the brute-force oracle; fast path, compiled port, Theorem 6; planted bugs |
| `real_caches.py` | exactness on the six recorded caches |
| `BENCH_PLAN.md`, `bench.py`, `BENCH.md` §1 | round 1: frozen plan, benchmark, results |
| `BENCH_PLAN_V2.md`, `bench2.py`, `BENCH.md` §2 | round 2: frozen plan, benchmark, results |
| `figures/margin_field.png`, `make_figure.py` | the figure |
| `results/` | raw outputs |

No existing file outside this folder was changed. The existing pass is imported from
`research/harness-2026-11/F-3.1/deadline_field` and the oracle from `research/kcf-theorem`.

## Reproduce

From the repository root, Python 3.13. The tests, the cache check and round 1 need only the standard library
(matplotlib for the figure). Round 2 needs numba; it was run in a virtual environment that is not in git:

```bash
python3 -m venv --system-site-packages .venv-kcf && .venv-kcf/bin/pip install numba
```

The recorded-cache steps need the frozen routing inputs under `data/routing` (not in git).

```bash
python3 -m unittest research/kcf-idea-routing/tests/test_margin_field.py -v
```

```bash
python3 research/kcf-idea-routing/real_caches.py --data-root data/routing --out research/kcf-idea-routing/results/real_fast/all.json
```

```bash
python3 research/kcf-idea-routing/bench.py --data-root data/routing --out research/kcf-idea-routing/results/bench.json
```

```bash
.venv-kcf/bin/python research/kcf-idea-routing/bench2.py --data-root data/routing --out research/kcf-idea-routing/results/bench2.json
```

```bash
python3 research/kcf-idea-routing/make_figure.py
```

The tests take about three minutes, the cache check a few hours on one core, each benchmark two to three hours.
`bench.py` now times the fast path, since that is the default; the round-1 method is `fast=False`.
