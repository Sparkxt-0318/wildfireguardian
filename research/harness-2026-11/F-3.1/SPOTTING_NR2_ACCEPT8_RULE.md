# Acceptance 8, spotting-dilation half, on `no_reentry/2` (rule; committed before any build or run)

Parent rules:
- `NOREENTRY2_ACCEPTANCE_RULE.md` §8;
- MULTIHOUR_HEADLINE_RULE.md amendment 19:15 UTC;
- the clamp from ledger row 61 (spotting envelope notes).

Labels:
- SCENARIO, not what happened. Graphs are road-limited.
- Isotropic dilation with no wind field. Nothing is claimed about actual spotting distances in 2025.
- Research check of monotonicity, not a spotting result.

## Hazards (nested by construction)

- **Base.** kriged_mean arrival raster `KFS_01_pswt_ok_toa.tif` band 1 (hours since t0 = 2025-03-22T02:24:00Z).
  Call it a.
- **Per start s**, h = s − t0 in hours. For d ∈ {0, 500, 1000, 2000} m:
  - D_d = `fdyn.variants.dilate(a, d, lag_s=0)`, Leo's function at 819bcb91, unchanged.
  - a_d = a where a is finite and a ≤ h (burned at the start: unchanged).
  - a_d = max(D_d, h) where a is finite and a > h (the clamp: nothing not burned at the start may arrive before the start).
  - a_d = D_d where a is NaN and D_d is finite. This is the clamp as well: max(D_d, h).
  - a_d = NaN where D_d is NaN.
- **Nesting.** dilate is a min over a disc, so D_2000 ≤ D_1000 ≤ D_500 ≤ D_0 = a pointwise. The clamp is a monotone
  map. Hence a_2000 ≤ a_1000 ≤ a_500 ≤ a_0 = a on every cell, and the finite support is nested.
  - **Checked before any build:** written per start and d into the run output (counts of cells where the order fails;
    pass = 0), together with a_0 == a on every cell.
- **Effect of the clamp under `/2`.** Under `/2`, C0 uses an inclusive comparison (a ≤ h). A clamped cell (a_d = h)
  therefore enters C0 and is closed on [0, H). This is the same set membership an unclamped D_d < h would give.
  - So under `/2` the clamp changes arrival times and flux, but not C0 membership versus a raw dilation.
  - The row-61 artefact (pre-start cells opening) cannot occur under `/2` either way.
  - The count of clamped cells per start and d is reported.
- **Rasters.** Saved with Leo's `fdyn.variants.save` (same affine and t0), one per (start, d), into scratch. Their
  sha256 values are recorded.

## Packets and fields

- **Build.** Leo's builder at 819bcb91, using the v3.7 manifest command for (region, start, h5, kriged_mean) with:
  - `--arrival <a_d npz>` and `--arrival-variant spot_clamped_<d>m`;
  - `--out` a scratch path.
  - Built twice: once with `--no-reentry2` (`/2`, the tested packet) and once without (reopening, so the existing runner
    can be used unchanged; its rows are not tested).
- **Scope.** 6 recorded starts:
  - UA 23T01Z, 24T09Z, 25T17Z;
  - YD 25T19Z, 25T23Z, 26T08Z;
  - × 4 d, h5. That is 24 pairs.
- **Runner.** `deadline_field/headline.py`, unchanged. Places come from INSTANCE.json for the start. Witnesses:
  - every `/2` CERT leave-by witness is full-checked on its own packet;
  - pass = full policy OK and closed/router replay clear.

## Control (pass/fail)

- At d = 0, every place's CERT and ROUTER leave-by (and no-route status) must equal the committed HEADLINE `/2`
  kriged_mean h5 row (`results/HEADLINE_NR2_summary.json`).
- A mismatch is listed. Monotonicity is then reported as **not interpretable** for that start.

## What is checked (reported; every violation listed and explained, none suppressed)

- For each start, each place, CERT and ROUTER, and each consecutive pair d < d′ (0→500, 500→1000, 1000→2000), plus 0→2000:
  - **Violation:** leave-by under d′ later than under d, or a route under d′ where d has none.
  - **Not a violation:** a route lost under d′.
- **Counts reported:** equal / earlier / lost / none-on-both / violation.
- **Witness results.** All witnesses must pass. A failing witness is listed. Its place is excluded from the
  monotonicity count, with the exclusion stated.

## Expected (stated before running)

- 0 violations. Under nested closure sets every trip feasible under d′ is feasible under d, whatever the waiting rule.
  A violation would therefore indicate a construction or implementation fault, not a fire effect.
