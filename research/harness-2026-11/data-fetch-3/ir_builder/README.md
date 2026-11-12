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
