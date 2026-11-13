# Acceptance test for the Magstadt-equivalent IR perimeter-series builder (written before any run)

Written 2026-11-12, about 15:35 UTC, before the builder had been run on anything. Any later change goes in a new file; this file is never edited.

## Scope

- **Input:** raw NIFC IR products for EXPOSED incidents only, meaning the 29 forecast-v2 project fires (23 fit and 6 held-out) found in NIROPS 2020–24 (`project_status` in `nirops_incidents_v2.csv` is `forecast_v2_fit` or `forecast_v2_heldout`).
- **Not in scope:** no part a/b/c/d incident, no H-test fire, and nothing from 2025 or later.
- **Reference:** the Magstadt archive (NIROPS_2020_2024_R1_R6.shp, sha256 a14f391a…f09b), read only through `nirops_access.py` with the exposed set as the allowlist.

## Output schema

The builder's output must use the archive's schema, so that the frozen `rebuild_env.sh` runs unchanged:
- `Incident_C`, `UTC`, `DateUTC`, `Acres`, `IRWINID`, `Inc Name`, `Inc Number`;
- geometry in EPSG:4326, one feature per survey.

## Matching rule

A built survey matches an archive survey of the same incident if their UTC times are equal. The comparison is to the minute, after both are floored to the minute.

## Pass criteria (per incident, then over the set)

1. **Timestamps.** The set of survey UTC times is IDENTICAL to the archive's: no missing surveys, no extra surveys.
2. **Area.** For each matched survey, |Acres_built − Acres_archive| / Acres_archive ≤ 0.5%.
3. **Shape.** For each matched survey, IoU(built, archive) ≥ 0.99. IoU is computed in EPSG:5070.
4. The run, the comparison and the reported numbers are deterministic: two runs give byte-identical output.

The builder PASSES on the rehearsal set if criteria 1–4 hold for every incident in the set. The report also gives:
- per incident: n_archive, n_built, n_matched, the median and minimum IoU, and the median and maximum relative area error;
- every failing survey, with its reason.

A partial pass is reported as such and is not re-labelled as a pass.

## Known risks, recorded in advance

- The archive's per-incident shapefiles were produced by human interpreters, and their QA notebook is in NIROPS.ipynb. Their DateFlown, TimeFlown and TimeZone come from the interpreter shapefiles. KMZ-derived layers carry no flight time, so criterion 1 cannot pass from KMZ-only inputs.
- Several raw layers per night (heat perimeter, intense heat, scattered heat, and "_rev" or "_copyDissolved" variants) mean the builder needs a layer-selection rule. That rule is part of the frozen builder.
