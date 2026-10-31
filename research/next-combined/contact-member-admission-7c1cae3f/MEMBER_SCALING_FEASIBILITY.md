# Member-count scaling: existing counters and presearch admission

The mandatory fig02_states_vs_members is not produced. Existing native evidence has only K = 4; there is no measured multi-K series. The read-only first-K feasibility check admits 0 of 80 candidate configurations under the current contact adapter contract. This is an input-admission count, not solver performance, a risk rate, or a physical impossibility result. No planner, forecast simulation, benchmark rerun or new panel was executed.

## Existing measured evidence

`member-scaling-closure-20261030-v2/NATIVE_FIXED_K_COUNTERS.csv` extracts the stored counters for all 52 native pairs: 26 missions, two repetitions, 104 child executions, each with four original members. SIPP interval pieces, piece expansions and successor runs are retained beside the sweep's reported states_reached counter. These are distinct internal work units; no ratio or common-state-count claim is made. Variation across missions at one K cannot identify fragmentation or a slope versus member count. Repetitions are not new missions or fires.

The existing C1-C4 admission records contain no solver counters. In particular, C3 has K = 4, 8, 16 and 32 labels, but every record stopped on UNKNOWN_GLOBAL_SOURCE_SUPPORT before graph preparation/search. Its 24,000 repeated case/truth records are not 24,000 measured searches. The 15 actual v3 exports contain original trajectory inputs, not routing state counts. No empty or fabricated metric image is drawn.

## Exact read-only admission scope

The audit reads the original first 32 trajectory fields from each of the 15 export files and evaluates only deterministic first-K controls, indices 0 through K-1, for K = 4, 8, 16 and 32 on the 20 original Korean missions. It verifies the NPZ producer digest, source record identity, graph/request/native-metadata pins, cutoff/as-of agreement, EPSG, affine and native shape. The export seed, trajectory batch size, original N, prefix hash and source hashes are retained. No trajectory is simulated, replicated, reordered or filled.

Eight Gyeongbuk missions already have recorded regional windows in NATIVE_METADATA.json. Their inclusive integer row/column bounds map the full event grid exactly onto the existing packet/graph grid. The audit uses those existing array views and verifies the resulting affine and shape, preserving every value and unknown mask. This is not interpolation, a new region or a frozen-input change. An initial full-grid-only audit stopped at those regional bindings; its source and partial fixed-K extraction remain in member-scaling-closure-20261030. The final audit is member-scaling-closure-20261030-v2.

Every inspected first-K field set still contains unknown cells on its declared contact domain, including after the recorded regional view. The exact current adapter predicate in bridge_v2.to_contact_model sets supported=False whenever any selected trajectory cell is unknown. frontend.sipp_plan then returns unresolved before graph preparation and solve. Consequently none of the 80 checked controls supplies an admitted search from which to measure a state count. KOREAN_PRESEARCH_ADMISSION.csv retains the per-mission/K decision, unknown-cell counts and grid/clock binding. Issue-cell trajectory uncertainty is a future-arrival-support diagnostic; it is not evidence of current flame contact. Cutoff state validity is separately retained.

This audit did not inspect all 1,024 trajectory masks, establish whether unknown masks are shared across full N, or evaluate alternative selectors. Its negative admission result applies only to the actually checked first-K candidates. It does not prove that every alternative scenario selection or a future local/pessimistically bounded contact checker would fail.

## Protocol decision

No solver campaign is queued under the current contract. This contact-only deliverable is separate from Track 1A physics and full-policy truth-risk gates: radiation-law validation is not a prerequisite to benchmarking a supported exact contact relaxation. The immediate obstacle for this audited control is the existing contact adapter's input-admission predicate, not an absent thermal theorem.

If admissible actual contact inputs or a separately justified spatial/temporal support contract become available, the intended bounded study remains the fixed 20 Korean missions with exact original grids/clocks, first-K original identities at K = 4/8/16/32, paired sweep/SIPP, two ABBA repetitions, the existing 30 s and 3,072 MiB limits, and an exclusive HEAVY lease after the forecasting boundary. Thresholds, mission histories and unknown support must remain explicit. This is a conditional protocol note, not authorization to change the support contract or launch that study. Native Caldor/Rim forecast alignment and all thermal/risk claims remain separate gates.

Reproduce only this read-only extraction/admission audit with the pinned routing Python 3.12.1 and NumPy 1.26.4:

```sh
python research/sipp-routing/audit_member_scaling.py --out FRESH_AUDIT_DIRECTORY
```

RESULTS.json records the host, exact producer hash, original measured-source manifest, input/output hashes, original export seeds and all scoped conclusions. The output directory is write-once. The script calls neither solver nor trajectory generator. Integrity validation checks the producer and output digests and the 52 stored pairs/80 presearch rows; it does not substitute a new benchmark for the missing fig02.
