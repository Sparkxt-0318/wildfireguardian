# All saved members fail current contact-input admission

The separate full-N census checks every saved member, closing the alternative-selector question left open by the first-32 audit. It finds zero strictly supported members among all 1,024 original saved trajectories on each of 15 exact contact domains covering the 20 Korean missions: 15,360 domain-member checks. These are source-admission checks, not solver runs, independent fire observations or risk samples.

For each domain, every saved member contains at least one -2 unknown cell, and the unknown masks are byte-identical across all 1,024 members. The equality is checked directly on Boolean mask bytes, with hashes retained separately. The census therefore does not infer full-N missingness from a prefix or from the exporter implementation.

## Exact current-contract implication

The existing bridge_v2.to_contact_model predicate sets supported=False when any selected member contains any unknown cell on its declared contact domain. frontend.sipp_plan returns unresolved before graph preparation/search for that support state. Since every saved member on every audited domain is unsupported, any nonempty selection from each of these saved pools fails this same predicate. This includes first-K, forward selection, medoid selection and other selections at K = 4/8/16/32, regardless of weighting or later k_of_m acceptance. No subset is selected, replicated or executed in this census.

The current full-grid L1 and road-symmetric-difference distance constructors also reject -2 fields; positive-weight unknown road features are refused. No distance calculation, redistribution or exclusion of unknown empirical mass is performed here. The mandatory fig02_states_vs_members remains unproduced because no admitted measured multi-K search series exists. The fixed-four-member counter table remains separate historical evidence.

This is an exact admission result for the current strict whole-declared-domain support predicate and the saved inputs. It is not proof that a local checker or a checker with independently justified pessimistic bounds could not admit routes. The physics and full-policy truth-risk gates are separate; the result does not use them as blanket reasons against contact-only studies. No contact support policy, threshold, frozen input or scientific claim was changed.

## Source, grid and clock custody

The census streams the original first-burn NPY payload within each of the 15 NPZ exports, one export and one original member at a time. It checks the saved N = 1,024, int16 encoding, C-order layout, complete member indices 0 through 1,023, first-burn value range and payload exhaustion/ZIP integrity. It hashes the complete streamed first-burn payload and rechecks the original first-32 prefix against its immutable prior digest. Base seed and batch size are retained; no regeneration or new random draw occurs.

Each source NPZ and record digest is checked against the previous audit. Existing graph, request and native-metadata identities are rechecked, binding the prior exact grid/clock proof without loading large graph JSON objects again. Full source affine/EPSG/shape and every already-declared inclusive regional integer window are also checked directly. The regional views preserve values and unknown masks; there is no resampling, new region or frozen-input edit. Duplicate missions that use the same exact domain are explicitly mapped to that domain rather than counted as independent exported pools.

The largest raw member is 37,446 bytes. Processing retains one member view, its Boolean mask, bounded domain mask references and read/hash buffers. It never allocates a full-N trajectory tensor or invokes a solver, simulator, selector, resource benchmark or HEAVY job. These are construction bounds and process choices, not measured RSS or timing results.

## Reproduce and inspect

```sh
python research/sipp-routing/census_saved_member_support.py --out FRESH_CENSUS_DIRECTORY
```

Use the pinned routing Python 3.12.1 with NumPy 1.26.4. The output directory is write-once. `full-member-support-census-20261030/RESULTS.json` records all 15 domain/export/clock/grid bindings, source and payload hashes, seeds, support histograms, the host and exact producer hash. MEMBER_SUPPORT.csv contains every domain/index support check. RECEIPT.json verifies complete index coverage, post-stream input identities and the eight original first-32/initial-failure artifact hashes against immutable commit 6685a48c. Those prior artifacts are unchanged.
