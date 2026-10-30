# Combined next-track readiness, interim HOLD

**No combined experiment has run. Track 1A reports 33 passing tests and 1,000 seeded enclosure regression cases, but its empirical physics gate is unresolved. Forecast fits are still in progress; an immutable interim 1C snapshot is audited below.** The original unsupported-case zero-enclosure defect has been repaired and independently rechecked; its failing record remains preserved. This document is a readiness record, not a claim that the requested scientific campaign is complete.

## Track evidence

| Track | Current evidence | Acceptance state |
|---|---|---|
| 1A radiation | 33 tests, 1,000 enclosure regression cases, seed 20261030; routing rejection and binding counts are null | HOLD_INCOMPLETE; physics unresolved; targeted refusal defect repaired |
| 1B forecast | Pending final owner evidence | Pending, no headline assigned |
| 1C members, SIPP and synthetic truth | 52/52 native contact pairs; 10,000/10,000 abstract comparisons; 15/15 export-array equality checks | HOLD_PARTIAL; owner continues; prior core defects repaired; reader admission findings open |

The [1A report at its audited source revision](https://github.com/Sparkxt-0318/wildfireguardian/blob/f9fa03290d57dc3d226543833f612640fd9f414a/research/flame-front-radiation/README.md) gives the detailed source and requirement ledger. `GATES.json` records the source hashes, exact test command, reported host and pending states. Results from the earlier remote Claude run are reference material and are not counted as executions in this run.

## Cross-track checks

| Requested check | Result | Reason |
|---|---|---|
| C1 and C4 with radiation v2 versus v1 | NOT_RUN_GATED | Empirical gate unresolved; complete v2 journey adapter unavailable |
| Binding on coherent members at K=4 and K=16 | NOT_RUN_GATED | 1A binding study and complete adapter unavailable |
| SIPP versus sweep on combined bridge-v2 packets | NOT_RUN_GATED | The orchestration Step 4 acceptance precondition is not met |

No track branch has been merged into this worktree. A pending or gated result has no numerical rate. It must not be replaced by zero, no-route, or a checked route.

## Independent targeted finding

At source revision `90b125a79d67301fac3058c97fe240b18cf8ae83`, a 2 by 2 simultaneous-ignition field with a 10 s residence time causes point evaluation at 1.5 s to raise `UnsupportedGeometry`. Enclosure evaluation over the interior interval [1,2] s instead returns [0,0]. An enclosure consumer could mistake that unsupported case for known zero flux. The failing fixture, source hashes and observations are retained in `audit/1a-simultaneous-initial.json`. This is a model-interface defect; it does not measure a physical fire. The defect was repaired at `f9fa03290d57dc3d226543833f612640fd9f414a`. The same fixture now raises consistently from both interfaces: `PASS_TARGETED_REFUSAL` in `audit/1a-simultaneous-repaired.json`. This is a bounded interface repair, not an empirical-physics pass.

## Commands and provenance

From this worktree, with the fresh pinned routing environment prepared by the orchestrator:

```sh
../venv-routing/bin/python research/next-combined/audit_1a_semantics.py --track-a ../audit-1a --out research/next-combined/audit/1a-simultaneous-initial.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../audit-1a --track-c ../audit-1c
```

The initial targeted audit exited 1; the repaired fixture exited 0, both retained separately. Report generation exits 0 and only summarizes evidence; it does not turn a failed gate into a pass. The track-owner test command and exit 0 are recorded verbatim in `GATES.json`. Owner test host: macOS-27.0.1-arm64-arm-64bit, Python 3.12.1, NumPy 1.26.4. The summary host and exact versions are also recorded there. No performance claim is derived from unit-test elapsed time. Hashes identify the exact artifact bytes reviewed, not a new field observation.

## What changed in the scientific claims

The optical prototype supports a narrower claim than the requested completed radiation study. It supplies a deterministic panel model with closed-form geometry checks and a finite, coarse model envelope on supported input geometry. Straight marching-square segments approximate a bilinear contour, and the leading/trailing panels are a declared representation of a flaming band. Regression samples test implementation behavior; they do not establish physical accuracy. The spatially constant coarse enclosure can remain too loose to decide a thermal route condition under refinement.

The empirical gate cannot be inferred from the supplied literature numbers alone. Vegetation height is not flame height, plot width is not instantaneous emitting width, and an in-flame sensor measurement does not uniquely identify a spatially uniform emitter power. A diagnostic model ratio under assumed geometry is not a measured validation error. Constants must not be fitted to the desired routing headline. There is consequently no new supported count of formerly accepted journeys rejected under radiation v2, and no supported peak or dose binding frequency.

Support must also be part of a mathematical contract. If a source array does not identify old-fire phases, or a simultaneous ignition does not identify a moving-front gradient, a checker must retain that uncertainty. The targeted zero-enclosure inconsistency illustrates why a successful scalar return is not enough to establish a usable certificate. The repaired domain guard adds consistent refusal evidence; a complete adapter, empirical case identification, and the requested journey-level studies remain open.

For coherent trajectory experiments, a change in missing-data policy would confound a comparison of dependence structures. Invalid trajectory states must remain unknown rather than become never-burned cells. A route whose needed support is unknown remains unresolved or unscorable under its declared contract. Earlier remote results that used a different policy cannot be relabeled as current evidence.

SIPP evidence, once finalized, concerns equivalence and computational cost for the declared contact relaxation. It cannot by itself establish a full thermal optimum, calibrated road-cut probabilities, universal runtime improvement or real evacuation effectiveness. Forecast fits and historical mapped perimeters, once finalized, likewise remain conditional retrospective evidence. They are not the blind future-fire test, and no new checkpoint becomes the integration default from a descriptive lead.

The current scientific conclusion is therefore an explicit hold with retained independent checks and open obligations. It adds no field-accuracy or operational-safety claim. Later evidence may fill pending rows only after its source, denominator, support policy, seeds, host and gate state are recorded.

## Scope and limits

This interim artifact audits one committed prototype and records unfinished work. It is not an integrated software build or a cross-track experiment. No field validation, operational deployment, full continuous-road checker, new default checkpoint, or GitHub merge has occurred. Timing from unit tests is not campaign performance. The source-level finding is bounded to its documented fixture and revision; repair verification is retained separately without overwriting the failing preimage.

## Recommended review and merge order

1C-1 export and members, 1A library, 1B forecast, 1C-2 SIPP, 1C-3 synthetic-truth harness, then integration. This is a logical future order conditional on acceptance, not a recommendation to merge the present held prototype.


## Immutable 1C snapshot audit

Snapshot `a2c6f8a69c46b5c678eea1d83bf9441f63a7e414` has 104 native contact-relaxation executions across 26 missions, with 52/52 paired status-and-arrival matches. SIPP was slower in 4/52 pairs. The raw CSV independently reproduces these counts. The custody ledger is internally consistent with its 156/156 reported original-job field matches. Original controller bytes remain retained; its final-after-exit guard was repaired after these executions, which were far below both limits. These are bounded contact-relaxation results, not full thermal-planner or universal runtime claims.

All 15 real exports pass the producing v2-array equality checks and full-N mean checks on known support. That script uses `array_equal`, including equal-NaN handling; this is not a general dtype or NaN-bit identity proof. A separate real KFS_11 cutoff establishes identical whole-NPZ hashes between the relocated wrapper and archived producer for that cutoff. The frozen exporter was restored; the default rollout diff adds only the optional observer and guarded call. The Boolean observer state is separately allocated. Block identity, offset and batch size are required for individual trajectory replay; seed alone is insufficient.

The copied full-journey checker explicitly checks a cell-centre surrogate. The wrapper preserves rejected candidates as unresolved, retains no-route only for uncut all-member relaxation exhaustion, and does not promote union exhaustion to k-of-m refusal. Its bounded lazy cuts remove whole departure singletons, so their exhaustion cannot prove global infeasibility or optimality. Whole-road validity, real scenario-reduction coverage, member-count scaling and scored risk campaigns remain open. Global-source completeness is a conservative admission policy, not proof that every local checker or pessimistic bound on unknown sources would fail.

The compressed campaign records were independently counted and checked for unresolved outcomes and null false-safe/false-refusal fields:

| Campaign | Admission records | Scored risk cases |
|---|---:|---:|
| C1 | 6,000 | 0 |
| C2 | 12,000 | 0 |
| C3 | 24,000 | 0 |
| C4 | 8 | 0 |

The total 42,008 records are unscorable admission records, not risk-validation samples. They identify no numerical false-safe/refusal rate. Brier diagnostics concern joint known cells only. The one-hour single-component case supplies no multi-step coherence contrast, and changing missing-data policy would confound the comparison. Shared truth draws and regional panels are clustered rather than independent fires.

The historical core snapshot `393f37748` pure-interface audit passed 5/9 fixtures, with four retained defensive failures: inconsistent evaluator flags can erase a known-contact violation; a supported passing journey can coexist with a no-route oracle without rejection; nonfinite oracle arrival can produce nonfinite regret; and overflowing finite weights can turn positive CVaR into zero. These defects concern admitted inconsistent or extreme inputs, not numerical errors asserted in the unscorable campaign. Exact fixtures and source hashes are retained in `audit/1c-core-393f37748.json`, produced by `audit_1c_semantics.py`, exit 1. The owner repaired those four core findings; the same fixtures now pass at the current snapshot, retained separately below. Unknown-mass decisions and all-member versus k-of-m no-route semantics passed their targeted fixtures. The scoring API also relies on caller-provided truth and oracle identities; the label `scope=full_policy` alone is not an independent proof or source binding.

This audit did not inspect 1B held-out scores. Its final fits, selection registry and reviewed blind protocol remain pending. The 1C owner has added independent adapters and features at this snapshot, with reader-boundary repairs pending, so this report does not finalize that track's gate. All cross-track scientific integration checks remain `NOT_RUN_GATED`.

To regenerate the interim summary and repeat targeted checks, use fresh output paths:

```sh
../venv-routing/bin/python research/next-combined/audit_1c_semantics.py --track-c ../audit-1c --out FRESH_C_AUDIT.json
../venv-routing/bin/python research/next-combined/audit_1a_semantics.py --track-a ../audit-1a --out FRESH_A_AUDIT.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../audit-1a --track-c ../audit-1c
```

The owner host is native macOS arm64 with Python 3.12.1 and NumPy 1.26.4; export seed 0, member/campaign seed 20261008. Exact commands, owner test receipts, hashes and audit scope are in `GATES.json`. No performance result is derived from these interface fixtures, and no branch was merged.


## Repaired core and new reader review

The current immutable 1C snapshot is `a2c6f8a69c46b5c678eea1d83bf9441f63a7e414`. The original core failure record at `393f37748` is unchanged. The independent post-repair core audit passes 9/9 fixtures, recorded separately in `audit/1c-core-a2c6f8a69.json`; it repairs the earlier known-contact, oracle-consistency, nonfinite-arrival and weight-normalization failures. It does not discharge physical, whole-road or risk-study gates.

The stronger export method is now separate from the historical value-equality method: 15/15 windows match dtype, shape, exact payload bytes including NaN bits, and 15/15 match the uncompressed NPY entries for every shared v2 array. The earlier `array_equal` limitation remains documented as history, not the final method. A regression verifies that different NaN payloads fail this stronger method even when value equality passes. This is shared-array identity; the separate one-cutoff whole-NPZ wrapper comparison has its narrower scope.

The post-repair receipt records 40 routing-environment tests passed with 4 dependency skips, and 20 selected forecast/GIS/export/features/scoring tests passed separately. These selectors overlap and must not be summed as independent tests. The source/artifact digests in the receipt match the archived files. The reported release verifier passes 367 copied hashes. A failed attempt to run the entire suite in the forecast environment is retained because that environment lacked Hypothesis; the successful split-environment receipts are stated explicitly.

The new reconstruction reader uses explicit seconds/minutes/hours and origin-to-cutoff conversion, exact grid alignment, nodata support and optional descriptive SD intervals. Nodata is not never-burned. The observed-perimeter reader keeps only arrival upper bounds, never exact ignition or survey-negative coverage; its actual CedarCreek collection is wholly unscorable after eight invalid source geometries, without silently repairing them. These are reader smoke results, not risk cases. The road-feature function reports unit-second unsafe departure times and metre chord weights, using the declared native-row mapping; no real road-reduction/K-scaling study is added by those fixtures, and caller data/grid admission remains a separate obligation.

The actual stored Wapiti metadata declares FARSITE, minutes, engine origin 1724048580 and a finite 1470 minute duration. It does not describe a new native simulation in this run. The smoke report has 11,655 covered cells, including 11,215 nonarrival sentinels. Those finite-run nonarrivals need a preserved query-time horizon or right-censoring interpretation; they do not establish global never-ignition after the simulation ends.

Five new reader boundary fixtures currently fail defensive admission or qualification, retained in `audit/1c-readers-a2c6f8a69.json`: a 1000 minute arrival is accepted despite a declared 10 minute simulation; nonarrival is exposed as a point-model infinity without a query-time validity bound; explicitly contradictory learned-probability metadata is still labeled FARSITE; an output lacking geometry is accepted against two reference grids shifted by 1000 m without an explicit unverified-alignment state; and a fractional UTC offset is silently truncated to a whole second. These are synthetic schema fixtures. They do not assert that the actual Wapiti file has wrong family, out-of-range arrivals or misaligned coordinates. Borrowed grid information must be qualified as a caller assertion unless verified from source coordinates or an independently bound alignment record. The owner has been notified for repair.

```sh
../venv-routing/bin/python research/next-combined/audit_1c_semantics.py --track-c ../audit-1c --out FRESH_REPAIRED_CORE.json
../venv-routing/bin/python research/next-combined/audit_1c_readers.py --track-c ../audit-1c --out FRESH_READER_AUDIT.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../audit-1a --track-c ../audit-1c
```

The current A evidence remains the immutable f9fa03290 radiation snapshot, not the later spatial-enclosure implementation being developed on its live branch. No claim about that later enclosure is made. All scientific integration experiments remain gated, and B final fits, geometry sensitivity, selection registry, protocol review and held-out results remain pending in this record.
