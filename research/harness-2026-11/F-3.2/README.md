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

Still trusted (Nora C5 note): O2 checks geometry and the integer translation only, NOT contact semantics —
`ContactModel` (packet arrays → per-cell activity intervals) is shared by both derivations, graph and request JSON, the cut rule
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
  the COCERT proof needs only the acceptance record (≈0.1 KB). For the other 15 (10 routes, 5 no-route) the best slice
  (forward or complement) plus certificate is 0.82–3.08× the full instance (median 1.42×; 6 of 15 above 1.5×), before
  any completeness authentication: on this panel an optimality or no-route proof is often LARGER than the instance
  itself, because it depends on most of the reachable region. A per-node Merkle authentication estimate
  (32 B × ⌈log2 nV⌉ per node, no sharing) is a loose upper bound that alone exceeds the instance; a real multi-proof
  design is unmeasured.
- **Consequence: a device can verify route legality only** (4.5–57 KB per route). Optimality and no-route proofs are
  not smaller than the instance on this panel, so a device cannot check them more cheaply than by holding the whole
  instance.
- Erratum (2026-11-12): the corrected range above was verified by Mira and committed in ae5351a. The #141 routing cut
  (0685e03) carried an older README and silently restored the earlier, wrong draft figure "≈0.5–1.5×". Recomputed from
  the unchanged `results/slices.json` (same sha256 at ae5351a, 0685e03 and Main): ratio = min over forward/complement of
  (slice instance bytes + certificate bytes) / full instance bytes, over the 15 rows not forced by the destination
  opening. The file's `best_optimality_total` field also adds the Merkle upper bound and is not this ratio.

## Departure-sweep cohort (reconstruction — NOT the November 106-request cohort or its 2 unproved claims)

`cohort.py`: the 20 frozen requests re-issued at departures 0, 300, …, 1800 s (`results/cohort_departure_sweep.json`).
140 distinct requests: 75 ROUTE + 65 NO_ROUTE; both checkers accept all 140 certificates; the independent copied
frozen sweep agrees on every verdict and every arrival (0 disagreements, 0 unresolved, 0 at-issue refusals). Max
certify 17.8 s, max C check 0.07 s, max bundle 7.1 MB. It reuses 5 graphs, 15 packets and 4 parent fires; departures
of one request are not independent tests.

Binding (Mira, claim 9 PASS WITH NOTES): the checkers certify the instance EMBEDDED in the bundle; nothing in a bundle
binds it to the request (a bit flip in an EDGES line can yield another valid instance). Faithfulness is O2's job:
`cohort.py` now runs `derive_instance.compare` per request (`o2_diffs`); Mira ran it on the 120 non-frozen departures,
0 differences. `sweep_plan` and `build_instance` both live in `wfg_sipp`: the independent sweep is a separate search,
not a separate package.

## P1 / contact semantics re-derived (measured; `p1_check.py`, `results/p1_flame_sets.json`)

Per graph cell, the union flame-activity set on [0, H) from (i) HAZARD.json member flame rows (what the frozen full
checker samples), (ii) an own re-derivation from `constructed_arrays.npz` + REPORT assumptions (no `ContactModel`),
and (iii) `ContactModel.cell_intervals`: **identical on all 15 frozen packets** (1–483 active cells each), exact
rationals. Sensitivity: of 40 all-member HAZARD flag flips, the 10 that change the union are all detected (the other
30 leave the union unchanged because another member row covers the same time); a 1 s shift of one raw interval is
detected. This closes the O2 gap Nora noted (contact semantics now independently re-derived for the frozen panel).

## Tier R, all events (measured; `tier_r.py`, `results/tier_r.json`; verified: Mira W4 @ b2d9eba, guard W5 @ c11eccd0 / d4564b38)

`unknown_support.py` is included only as a library for `tier_r.py` (`Augmented`, `certify_and_check`). Its own
`main` (the earlier Tier B experiment) is superseded by Tier R, and its results are not part of this tree.

Tier R(v) (Iris): U_state is not present fire; an unknown cell is blocked from d/v, with d measured from present fire
∪ positive-probability cells; U_state cells with a FIRMS detection are blocked on [0, H]. FIRMS and TOA for all four
events (KFS_01/02/05/11; Daniel's files, hashes matched). Every certificate (20 optimistic + 60 pessimistic) is accepted
by both checkers.

| Tier | checked | no_route | unresolved |
|---|---:|---:|---:|
| A | 5 | 5 | 10 |
| R, v = 1.5 km/h | 12 | 5 | 3 |
| R, v = 8.2 km/h | 10 | 5 | 5 |

- **Change from the first run (2025 FIRMS only: R1.5 14/5/1, R8.2 11/5/4).** Three labels went from checked to
  unresolved: Uljin 20220304T060000Z_FL1 (R1.5), and Hongseong 20230402T230000Z_FD1 (R1.5 and R8.2). In each case
  U_state cells with FIRMS detections (17 at Uljin, 13 at Hongseong) are now blocked on [0, H]. The first run had no
  FIRMS for those events, so its three checked labels there were not justified.
- **U_state.** In every packet, 100% of U_state is outside the footprint, and no positive-probability cell is in U_state.
- **Unresolved causes.** Tier A: U_state+U_q 6, U_state 2, U_q 2. R1.5: U_state 2, U_q 1. R8.2: U_state+U_q 4, U_state 1.
- Contact relaxation only; the radiation precondition with U_state cells as sources is not computed.
- **Coverage guard** (`tier_r.firms_coverage`, `tier_label`; tests `test_tier_r_guard.py`, 12/12). A Tier R
  mission is labelled only if ONE supplied FIRMS file both spans the event window (the dates of its detections) and has
  at least one detection, at any date, inside the event's own packet-grid bounds (`packet_bbox`). A file for another
  area, even one inside the coarse `KOREA_BBOX` default such as Fukuoka, does not count. Otherwise the mission is
  `not_labelled_no_firms`, never checked or unresolved; a no_route from the optimistic instance still stands, and Tier A
  needs no FIRMS. Coverage is judged from detection dates, not the export's nominal period, so an export whose first or
  last detection falls inside a quiet window is refused (conservative). The FIRMS step depends only on FIRMS and the
  footprint step only on the TOA raster. With the all-events FIRMS every event is covered, so the table above is
  unchanged (Mira enumerated all 24 covered input combinations: identical labels). With the first run's 2025-only files,
  KFS_02, KFS_05 and KFS_11 would now be refused rather than mislabelled.

## F-DYN certificates (measured; `fdyn_certs.py`, `results/fdyn_certs.json`; verified: Mira W4 @ b2d9eba, v3.1 firms_early W7 @ f5aef10)

The run covers 10 v3 packets: 5 kriged_mean and 5 firms_early, 5 h, central member, at Uiseong and Yeongdeok. It
certifies every origin at departures 0 and 7,200 s, for 1,728 requests in all (1,680 ROUTE, 48 NO_ROUTE).
- **Checkers.** The C checker accepts 1,728/1,728. The Python checker accepted 1,659 in the batch. For the other 69 it
  printed nothing: the checker failed to run, and the batch did not record its exit status or stderr. Each of the 69 was
  regenerated and re-checked, and both checkers accept with the same claim and T (`results/fdyn_recheck69.txt`).
  `fdyn_certs.run` now retries once and records `NORUN exit=…` instead of an empty string.
- **Sizes.** Instance plus certificate has a median of ≈ 1.25 MB, about the 1-hour panel's median bundle (1.21 MB).
  Forward certificates: median 27–28 kB, p90 272 kB, max 3.2 MB. COCERT: median 63–65 kB, max 3.5 MB. The COCERT
  bundles in this batch were built with `legs=[]` and only SIZED, never checked: a checker rejects a ROUTE cocert
  without a witness. Checked COCERTs are those of the 20-mission panel (claim 8).
- **Times.** Median certify time is 0.21 s, max 29 s on one request. Checks: C median 0.014 s (max 0.19 s), Python
  median 0.34 s (max 1.6 s). The 1-hour panel: C 0.015 s, Python 0.24 s (max 1.9 s).
- **Soundness labels (manifest).** kriged_mean is "kriged mean (not a bound)". firms_early is "BRACKET-START, NOT A
  LOWER BOUND". So these certificates prove routes and no-routes in those hazards only, not against the real fire.
- **firms_early on v3.1** (`results/fdyn_certs_v31_firms_early.json`). The five packets were rebuilt from
  MANIFEST_v3_1.json (sha 1c2e73db…) argv lists at Leo f40e2af and certified at departures 0 and 7,200 s.
  - All 864 requests are accepted by both checkers (841 ROUTE, 23 NO_ROUTE), with no empty outputs, and O2
    first-origin diffs are 0.
  - Claim and T are identical to the v3 rows for all 864. That is expected: per-cell flame starts are identical to v3
    in all five packets (HAZARD differs only in identity digests, as in Leo's PACKET_DIFF_v3_v31.json). The +300 s
    birth shifts of v3.1 fall at other starts, such as acceptance sample (b).
  - kriged_mean is unchanged by v3.1 according to Leo's diff.

## Envelope O2 and the v3.1 acceptance check (measured; `envelope_o2.py`; verified: Mira W2 @ 07d4a58, W3 @ 45a8975, exact-mode sign-off @ d4564b38)

`envelope_o2.py` was written from Leo's rule text, without reading `fdyn/ignitions.py` or `_packet_child.py`.

> **Erratum (2026-11-12; Nora ledger row 34; measured by this author on all three packets below, and confirmed
> independently by Mira on the v3 Yeongdeok packet).** Everything in this section
> compares the rule against **HAZARD.json**: the per-cell intervals derived from the variant arrival files
> (`variants/firms_early.npz`, `firms_constrained.npz`), and integer instances built from HAZARD.json intervals. It
> never reads a packet's `constructed_arrays.npz` and never uses `ContactModel`. In the `envelope` packets (v3 and
> v3.1) those two representations DISAGREE. ContactModel, which the router and the certificate pipeline use, reads
> the raw arrays: birth + the raw burning duration T + Q (≈ 4,270 s). HAZARD.json ends a cell at hi_rel + T + Q,
> often clipped at H. Cells differing beyond 1 µs: 794 / 198 / 794 on the v3 Yeongdeok, v3.1 (a) and v3.1 (c)
> packets; for example cell 1040 is [5100, 18000) in HAZARD.json and [5100, ≈ 9370.6) in ContactModel.
> So the results below show that **HAZARD.json implements the stated envelope rule** (v3 in binary64, v3.1 in integer
> ms). They do **not** show that the hazard a router or certificate sees on an envelope packet is that rule: it is
> not. No envelope packet was certified here. Sample (b), firms_early (scalar law), passes the same consistency check
> (139 identical, 108 ends within 1 µs, 0 other), as do the certified kriged_mean and firms_early packets.
> "The packets" below means their HAZARD.json.

- **v3, Yeongdeok 20250325T110000Z h5 envelope.**
  - Rule evaluated in binary64 (`--mode float`): 820 cells differ from HAZARD.json. Every one has the same start and
    an end within 1.4e-12 s (97 HAZARD later, 723 earlier). There are 0 other differences, and 10/10 integer
    instances are equal.
  - Exact rationals (`--mode exact`), a NEGATIVE result: 791 cells differ by a whole 300 s quantum (482 births, 309
    ends), plus 502 sub-µs end differences, and 0/10 integer instances are equal. So the v3 HAZARD.json does NOT
    implement the exact-rational law. This finding led to v3.1, whose integer-ms law HAZARD.json matches (below).
  - Float vs exact, no contradiction: the v3 writer evaluates the rule in binary64, so the float-mode derivation reproduces
    its integer instances (10/10), while the exact-rational reading of the SAME stated rule differs by a 300 s quantum at
    791 minute-boundary cells (0/10). That is, v3 implemented its rule in float, not as stated; v3.1 removes the gap.
  - An earlier version of the classifier counted only HAZARD-later ends and so reported "0 differences" for the float
    mode. Corrected.
- **v3.1 (`--mode v31`, QUANT_v3_1_RULE.md @ f40e2af).** Packets were built with Leo's manifest commands at f40e2af,
  after re-running `variants.py` there to get the `timestamp_exact` mask.

  | sample | active cells | single-interval cells: start equal / hi_rel equal | merged or clipped equal | boundary cells (birth / end) | integer instances equal |
  |---|---:|---:|---:|---:|---:|
  | (a) Uiseong 20250324T020000Z h5 envelope | 275 | 142 / 142 | 133 | 102 / 17 | 10 / 10 |
  | (b) Uiseong 20250324T020000Z h5 firms_early (scalar law) | 247 | 216 / 216 | 31 | 102 / — | 10 / 10 |
  | (c) Yeongdeok 20250325T110000Z h5 envelope | 1,752 | 820 / 820 | 932 | 482 / 309 | 10 / 10 |

  - There are 0 mismatches.
  - The largest end residue is 1.4e-12 s, the binary64 form of the same integer end.
  - Timestamp-exact cells were recovered to within 2.4e-8 ms of an integer.
  - A "boundary" cell is one whose rel_ms is an exact positive multiple of 300,000. At (c), these are exactly the
    cells v3 got wrong under the exact rule.
  - (b) uses Leo's scalar-law text (2026-11-12): central member, p/q = 1/1, shift 0; birth t = floor_div(max(rel, 0),
    300000)·300 s; kept iff finite, not export-burned, rel > −T·1000 and t < H; interval [t, t + T + Q). That is the
    envelope law with hi = lo (`--law scalar`). Its 102 boundary births match the 102 births Leo's v3→v3.1 diff moves
    by +300 s at that start.
  - The export's `contract__cell_duration_s` is asserted equal to T in every sample.
  - Command: `envelope_o2.py --leo <f40e2af worktree> --packet <packets_v31/...> --start <tag> --mode v31 --law
    envelope|scalar --tag a|b|c` (results `results/envelope_o2_v31_{a,b,c}.json`).
