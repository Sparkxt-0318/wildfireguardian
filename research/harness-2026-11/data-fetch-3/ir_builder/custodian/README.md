# Custodian script: the exposed incidents' NIFC FTP IR folders (for Hannah to review and run once)

The orchestrator's ruling (12 Nov 2026, 15:25Z): Daniel does NOT fetch FTP directory pages. Hannah reviews this script, runs it once, and hands Daniel the folder URLs. Daniel opens only those folders.

## Files

- `find_exposed_ir_folders.py`: stdlib only.
- `test_find_exposed_ir_folders.py`: a fixture test with no network. `TEST_OUTPUT.txt` holds its output (PASS).
- `EXPOSED_29.csv`: the 29 exposed incidents (forecast-v2 fit and held-out), with their years. It was made from `allowed_fields/nirops_incidents_allowed.csv`.

## What the script guarantees

1. **Pages fetched.** It fetches only:
   - the root page;
   - each GACC page;
   - the `<gacc>/<year>/` pages for years in EXPOSED_29.csv (2020–2024; any other year is refused);
   - one level of *grouping* folders below them.

   A grouping folder must contain "incidents" in its name and carry no unit-number pattern, so a fire's own folder is never opened. Exposed IR folders are not opened either, because the script only returns their URLs.
2. **What is kept.** Each page is parsed in memory for `<a href>` values only. Link text, modification times and sizes are never extracted (Victor's point f). Every non-matching link is dropped.
3. **Output.** One line per exposed incident: `FOUND <url>`, `AMBIGUOUS <n>` (no URLs), or `NOT_FOUND 0`.
4. **Log.** stderr gets one line per page: a URL *template* (`GACC[i]/<year>/GROUP[k]`, never a folder name) and the sha256 of the response (Victor's point g).

## Matching rule

A folder matches an exposed incident if either:
- its normalised name contains the unit code and the incident number (e.g. `btu` and `009205`) and also the fire name; or
- it carries no incident number at all and its name, after removing a leading year, equals the fire name.

## Run (custodian)

```
python3 -I find_exposed_ir_folders.py EXPOSED_29.csv --out exposed_ir_folders.tsv 2> pages.log
```

The default root is `https://ftp.wildfire.gov/public/incident_specific_data/`. This is the path in Magstadt's NIROPS.ipynb; it was not checked from here.
