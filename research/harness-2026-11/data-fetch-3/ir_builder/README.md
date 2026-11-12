# Magstadt-equivalent IR perimeter-series builder (CR1 job 2): status, 12 Nov 2026

- `ACCEPTANCE_TEST.md` was pre-registered at commit d7f8bc96 and is never edited.
  **Erratum:** its text says it was written "about 15:35 UTC". The true commit time is 2026-11-12T15:22:53Z, still before any builder or probe run.
- `custodian/`: the folder-finder script for Hannah (see its README). Daniel does not fetch FTP directory pages.
- `probe_dixie_kmz.py` and `PROBE_DIXIE_OUTPUT.txt`: a feasibility probe. This is NOT the acceptance run.

## Probe: Dixie 2021 (exposed fit fire), from KMZ-derived raw IR

**Input:** Hatchett 2025 (Zenodo 10.5281/zenodo.15492982), DixieFire_2021_perimeters.zip, sha256 84afb947…06db. It holds 41 shapefiles; 37 nights remain after dropping the IntenseHeat and ScatteredHeat layers.

**Archive:** CA-BTU-009205_Dixie, read through `nirops_access.read_incident` with allowlist {CA-BTU-009205_Dixie}; it has 75 surveys.

**Rule:**
- per night, keep the features named "*Perimeter*" (or the whole layer), apply buffer(0) and dissolve, then reproject to EPSG:5070;
- compare with the archive surveys within ±1 local day.

**Result:**
- the best IoU per night has median 0.9993 and minimum 0.9608;
- 25 of 37 nights are ≥ 0.99 and 34 of 37 are ≥ 0.98;
- the weakest nights are 6–10 August.

The file date equals the UTC date of the matching archive survey.

**Why the acceptance test cannot pass from this input:**
- the KMZ-derived layers carry no flight time (timestamp, begin and end are empty), so criterion 1 cannot be met;
- the set covers 37 of the 75 archive surveys.

The archive's DateFlown, TimeFlown and TimeZone come from the interpreters' IR shapefiles on the NIFC FTP (NIROPS.ipynb cells 1, 3 and 5; UTC = local + fixed offset, PDT +7, MDT +6). The rehearsal therefore needs those shapefiles, through the custodian route.

## Finding (12 Nov 2026, Hannah's custodian runs, ledger rows 47, 49 and 51)

The NIFC FTP does not serve any 2015–2024 season folder at any documented path today.

- **v2 run:** `.../public/incident_specific_data/` returned 404 at server level.
- **v3 run:** 504 constructed URLs, covering 2 roots × 7 GACCs × 2020–24 × 9 documented layouts, were all 404. All 29 exposed fires came back NOT_FOUND.
- **v3.1 `--years` run:** 980 constructed year-folder URLs, covering 2015–2024, were all 404.
- The client identity was `wfg-custodian/1` throughout. Changing it was refused by policy, so it was not tested.

Possible causes, documented in FRESH_HOLDOUT §3.6 but unverified: the 2022 purge notice, or a move to /protected (login; not tested). Sofia reports that only a 2026 season exists, and 2026 is off limits.

Consequence: the full acceptance test (`ACCEPTANCE_TEST.md`) cannot be run on the 29 exposed fires. The builder can only be rehearsed on IR already held. The geometry-only Dixie rehearsal (`ACCEPTANCE_TEST_GEOMETRY_DIXIE.md`, `RESULT_GEOMETRY_DIXIE.txt`) came out PARTIAL: 24 of 37 nights pass both criteria, and times were not tested.

## The 13 failing Dixie nights (31 Jul to 30 Aug 2021): explanation, recorded rather than fitted

`diag_dixie_holes.py` and `DIAG_DIXIE_HOLES.txt` are a diagnosis run after acceptance test 2; they are not part of the test.

- **What differs.** On every failing night, the built perimeter is LARGER than the archive's. The area found only in the built perimeter is 3.6–70.9 km²; the area found only in the archive is ≤ 1.5 km².
  - Correction to my 15:47Z message: there I wrote that "the built perimeter is consistently the smaller one". That was wrong.
- **Where it differs.** The extra area sits inside the archive's interior holes, i.e. unburned islands. On these nights the KMZ-derived "HeatPerimeterDissolved" layers have 1–5 interior rings, while the archive has 5–14.
- **Test.** With interior rings removed from both sides, IoU is ≥ 0.9994 on every one of the 37 nights.
- **Conclusion.** The cause is the input product: the dissolve step in these August KMZ layers filled in the unburned islands. It is not a builder error. A builder cannot restore holes that are absent from its input.
- **Status.** Acceptance test 2 stays PARTIAL (24/37); no criterion or rule was changed after the run. On interpreter shapefiles, which carry the islands, the same builder is expected to pass. That expectation is untested, because none are available (see Finding).

## CR1 harvest-route items (draft 13, section 2, requirements 2 and 4), from documentation and repository code only

**WFIGS Incident Locations fields** (NIFC ArcGIS feature service `WFIGS_Incident_Locations/FeatureServer/0`, as queried by `data-fetch/incident_metadata_join.py`):

| Content | Field |
|---|---|
| IRWIN ID | `IrwinID`, a braced GUID |
| Discovery date-time | `FireDiscoveryDateTime`, epoch milliseconds, UTC |
| Point of origin | the feature's point geometry, requested with `outSR=4326` (x = lon, y = lat) |
| Initially reported location | `InitialLatitude` / `InitialLongitude` (separate from the point of origin) |
| Also used | `IncidentName`, `UniqueFireIdentifier`, `POOState` |

**IRWIN ID in the IR delivery attribute tables: NOT carried.**
- Magstadt's NIROPS.ipynb cell 4 adds an `IRWINID` field by joining an IROC export, keyed on the incident number, to every shapefile, and cell 5 creates the column empty when it is absent.
- The KMZ-derived Dixie layers have no IRWIN field either.
- A harvest therefore needs the incident-number key, or the no-IRWIN fallback: a unique match within 4 km and ≤ 3 days before the first perimeter, otherwise E8.

**Builder acceptance criteria, for the in-season builder:**
- **Geometry:** IoU ≥ 0.99 and |area error| ≤ 0.5% against an interpreter-shapefile reference, per survey.
- **Time:** where testable, the parsed survey time equals the reference to the minute. This applies under the fixed flight-time rule:
  - free-text parse with a per-region time-zone table;
  - a local time at or after 12:00 is assigned to the day before the folder date;
  - a missing or unparseable time becomes the folder date at 00:00 local, flagged ESTIMATED.
- ESTIMATED surveys are reported separately and are excluded from the time criterion.
