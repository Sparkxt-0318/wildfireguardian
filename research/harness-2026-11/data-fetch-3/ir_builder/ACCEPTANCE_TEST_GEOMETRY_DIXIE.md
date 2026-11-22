# Acceptance test 2: geometry-only rehearsal on Dixie 2021 (PARTIAL; written before the builder run)

Orchestrator decision, 12 Nov 15:47Z, option (b). This file is new. `ACCEPTANCE_TEST.md` (d7f8bc96) is unchanged and remains the full test; this rehearsal does not pass it.

**This is not a blind test.** The feasibility probe (`probe_dixie_kmz.py`, commit 85b246ab) already compared these same inputs with the archive. It gave a median best IoU of 0.9993, and 25/37 nights ≥ 0.99. What this test adds is a frozen builder and a frozen matching rule, both stated before the run.

## Inputs

- Raw IR: Hatchett 2025, Zenodo 10.5281/zenodo.15492982, `DixieFire_2021_perimeters.zip`, sha256 84afb947…06db. It holds 41 KMZ-derived shapefiles.
- Archive: CA-BTU-009205_Dixie in NIROPS_2020_2024_R1_R6.shp (a14f391a…f09b), read through `nirops_access.read_incident` with allowlist {CA-BTU-009205_Dixie}.

## Builder rule (frozen in `build_ir_series.py`)

1. One input file is one night. The night's date D is the first 8 characters of the file name (YYYYMMDD).
2. Files whose name contains `IntenseHeat` or `ScatteredHeat` are dropped.
3. Inside a file, if any feature's `Name` contains "Heat", only features whose `Name` contains "Perimeter" are kept. Otherwise all features are kept.
4. Geometry: buffer(0), then a union of all kept features, in EPSG:4326.
5. Output uses the archive schema: `Incident_C`, `UTC` (left EMPTY, because the input has no flight time), `DateUTC` = D, `Acres` (geodesic area via EPSG:5070), and geometry. An extra column `time_source = "none (KMZ-derived; date from file name)"` is added.

## Matching rule

A built night with date D matches the archive surveys whose UTC calendar date is D. If several archive surveys share D, the one with the highest IoU is taken, and the multiplicity is reported.

## Criteria (per matched night)

- G1: IoU ≥ 0.99, in EPSG:5070.
- G2: |Acres_built − Acres_archive| / Acres_archive ≤ 0.5%.

## What is reported

- Nights built, nights matched, archive surveys with no built night, and built nights with no archive survey.
- Per night: IoU and relative area error, and whether G1 and G2 hold.
- The overall result: PASS(geometry) only if G1 and G2 hold on every matched night. Otherwise it is PARTIAL, with the failing nights listed.

Criterion 1 of the full test (identical survey times) is NOT TESTED: the input has no times. Coverage is also NOT tested: the input has 37 nights, against 75 archive surveys.
