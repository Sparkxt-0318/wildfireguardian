# kcf-theorem: the F-3.1 deadline field as a checkable result

Start with [THEOREM.md](THEOREM.md). It covers the model, the exactness theorem, the prefix theorem and its
hypotheses, the smallest counterexample, the running time, the evidence and the assumption table.

| file | what | imports from the repository |
|---|---|---|
| `THEOREM.md` | statements and proofs; measured results | – |
| `checker.py` | independent checker: `check_route` (valid or invalid, and why), `find_route` / `confirm_deadline` / `feasible_set` (brute force on small graphs). Standard library only, under 200 lines | **nothing** |
| `test_theorem.py` | toy, counterexamples, exhaustive minimality, 12,000-case property test against brute force, mutation tests | `deadline_field.core` (the code under test) |
| `randgraphs.py` | random instances in both formats; the no-re-entry hull of Corollary 3 | `deadline_field.core.Instance` |
| `mutants.py` | copy of `backward` / `issue_core` with five switchable bugs, and a route extractor that shares each bug | `deadline_field.intervals`, `core.Field` |
| `differential_witnesses.py` | checker over every recorded checked route of the six caches, plus deadline witnesses and L + 1 | `real.PacketModel`, `core`, `tools/explain_deadlines/plans.reconstruct_legs` |
| `measure_assumptions.py` | hypotheses M1–M4 and the prefix property on the six caches | `real.PacketModel`, `core` |
| `bench.py` | backward pass vs one departure at a time | `core` |
| `make_figure.py` | `figures/toy_backward_pass.svg`, traced from the unchanged `backward` | `core` |
| `results/` | JSON written by the scripts above | – |

## Reproduce

From the repository root, Python 3.12+ (measured with 3.13.18). The tests need no third-party packages. The
real-data scripts need numpy (for `real.py`) and the frozen inputs.

```bash
python3 -m unittest research/kcf-theorem/test_theorem.py -v
```

```bash
python3 research/kcf-theorem/bench.py
```

```bash
python3 research/kcf-theorem/make_figure.py
```

```bash
python3 tools/fetch_routing_inputs.py --out /tmp/wfg_routing
```

```bash
python3 research/kcf-theorem/measure_assumptions.py --data-root /tmp/wfg_routing --out research/kcf-theorem/results/assumptions_real.json
```

```bash
python3 research/kcf-theorem/differential_witnesses.py --data-root /tmp/wfg_routing --out research/kcf-theorem/results/differential_real.json
```

`KCF_CASES` and `KCF_MUTANT_CASES` change the number of random cases per family (defaults 6,000 and 3,000).
