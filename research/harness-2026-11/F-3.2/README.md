# F-3.2 primal-dual certificates for the contact-relaxation router (work in progress)

- `CERTIFICATE_SPEC.md` — certificate definition, soundness argument, scope boundary (under review).
- `FORMAT.md` — `.wfgc` bundle format (integers and keywords only).
- `generate.py` — solver side: SIPP answer + exact truncated forward-reachable interval sets.
- `check_py.py` — checker 1 (Python, stdlib only, no solver imports).
- `checker_c/` — checker 2 (C99, integer only), written independently from the spec only.
- `cases.py`, `run_panel.py` — the 20 Korean native-panel missions on the frozen inputs (`tools/fetch_routing_inputs.py`).

Reproduce (from repository root, after `python3 tools/fetch_routing_inputs.py`; needs numpy):

```sh
export PYTHONPATH=experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src
python3 research/harness-2026-11/F-3.2/run_panel.py --out /tmp/f32-panel
```

Bundles (0.06–7 MB each) are written outside git; `results/` holds the summaries.

## Checkpoint 2 results (measured, this container, Python 3.13.18, gcc 13.3)

- 20/20 Korean missions: 15 `ROUTE` + 5 `NO_ROUTE` certificates; verdicts and arrivals equal the recorded SIPP rows.
  Both checkers accept all 20 (`results/panel_summary_run2.json`). C checker ≤ 0.08 s per bundle, Python ≤ 1.2 s.
  Re-generation is byte-identical (20/20 bundle sha256 equal across two runs).
- Mutation test (`mutate.py --per-class 10 --seed 20261112`): 1,526 checker runs, 0 failures — every corrupted bundle
  rejected by both checkers, every control accepted (`results/mutation_run3.json`). Run 1 (`..._buggy_mutator.json`)
  counted 8 no-op witness "mutations" (a WAIT leg rewritten as itself) as failures; the mutator now skips no-ops.
- Not covered by panel mutations: C4 is never the *first* failing condition (C2 fires first) and no wait-unblock
  candidate arose; both are covered by the C checker's hand-written unit tests (`checker_c/tests`).

```sh
make -C research/harness-2026-11/F-3.2/checker_c && bash research/harness-2026-11/F-3.2/checker_c/tests/run_tests.sh
python3 research/harness-2026-11/F-3.2/run_panel.py --out /tmp/f32 --c-checker research/harness-2026-11/F-3.2/checker_c/wfgc_check
python3 research/harness-2026-11/F-3.2/mutate.py --bundles /tmp/f32 --per-class 10 --c-checker research/harness-2026-11/F-3.2/checker_c/wfgc_check --out /tmp/f32-mut.json
```

## O2 instance faithfulness (measured)

`derive_instance.py` re-derives EB/WB/AC from the raw graph, request and `ContactModel.cell_intervals` with its own
exact-rational grid geometry, examining every edge (no bounding-box prefilter) and importing nothing from `wfg_sipp`.
`python3 check_instances.py` (PYTHONPATH as above): **0 differences on all 20 missions**; 0 geometry points outside the
grid (the frozen `row*width+col` cell formula would alias such points). Sensitivity: moving a single activity-interval
start by ±2 s on a road cell produced differences in 12/12 targeted trials (4 missions; only 2 had start-in-window
targets). Untargeted perturbations mostly show no difference because present-fire intervals ([0, ≈3967 s)) outlast
the 3600 s horizon and many cells carry no roads.

Still trusted: `ContactModel` (packet arrays → per-cell activity intervals), graph and request JSON, the cut rule
(interior grid lines only), and the integer-second clock.

Observation: the panel's time dependence is thin. 4/20 missions have no blocked edge; in 6 more every blocked edge is
blocked for the whole [dep, H] window; both Miryang NO_ROUTE claims are purely static cuts.

## Checkpoint 4 (measured)

- (d) Frozen full-policy journey checker (`witness_check.py`): 15/15 SIPP witnesses `CHECKED_ROUTE`, same arrival, max peak ≤ 0.003 vs budget 10 (`results/witness_check_py313.json`).
- Backward/complement certificates (`COCERT`, `sizes.py`): accepted by both checkers on all 20 (C ≤ 56 ms); forward and backward exact sets disjoint below T on all 20; certificate part 1.1–30× smaller than forward (largest NO_ROUTE 4.1 MB → 0.82 MB); gzip -9 of the instance alone is up to 0.85 MB and dominates (`results/sizes_py313.json`). In 5 route missions no state can complete before T (optimality forced by the destination opening).
- COCERT mutation test: 482 runs, 0 failures; C4 is the first failing condition in 31 (`results/mutation_cocert_run1.json`).
- C checker extended to COCERT from the spec only; 30 unit tests pass (normal + sanitizer); check_py agrees on all 30.
- Python 3.12.3 + numpy 1.26.4 (pinned): panel bundles byte-identical to 3.13 (20/20), both checkers accept 20/20, mutation 1,526 runs / 0 failures (`results/panel_summary_py312.json`, `results/mutation_py312.json`).

## Proof-carrying route slices (measured; `slices.py`, `results/slices.json`)

Bytes a verifier needs, in `.wfgc` record syntax, vs the full instance (34–2,858 KB):
- A, legality of the route only (corridor edges, their blocks, turns, waits, acceptance): **4.5–57 KB**.
- Optimality: in the 5 routes whose arrival is forced by the destination opening (no state can complete before T),
  the COCERT proof needs only the acceptance record (≈0.1 KB). Otherwise the best slice (forward or complement) plus
  certificate is ≈0.5–1.5× the full instance, before any completeness authentication: optimality genuinely depends on
  most of the reachable region. A per-node Merkle authentication estimate (32 B × ⌈log2 nV⌉ per node, no sharing) is
  a loose upper bound that alone exceeds the instance; a real multi-proof design is unmeasured.

## Departure-sweep cohort (reconstruction — NOT the November 106-request cohort or its 2 unproved claims)

`cohort.py`: the 20 frozen requests re-issued at departures 0, 300, …, 1800 s (`results/cohort_departure_sweep.json`).
140 distinct requests: 75 ROUTE + 65 NO_ROUTE; both checkers accept all 140 certificates; the independent copied
frozen sweep agrees on every verdict and every arrival (0 disagreements, 0 unresolved, 0 at-issue refusals). Max
certify 17.8 s, max C check 0.07 s, max bundle 7.1 MB. It reuses 5 graphs, 15 packets and 4 parent fires; departures
of one request are not independent tests.
