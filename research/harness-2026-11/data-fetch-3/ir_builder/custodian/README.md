# Custodian script: the exposed incidents' NIFC FTP IR folders (for Hannah to review and run once)

The orchestrator's ruling (12 Nov 2026, 15:25Z): Daniel does NOT fetch FTP directory pages. Hannah reviews this script, runs it once, and hands Daniel the folder URLs. Daniel opens only those folders.

## Files

- `find_exposed_ir_folders.py`: stdlib only.
- `test_find_exposed_ir_folders.py`: a fixture test with no network. `TEST_OUTPUT.txt` holds its output (PASS).
- `EXPOSED_29.csv`: the 29 exposed incidents (forecast-v2 fit and held-out), with their years. It was made from `allowed_fields/nirops_incidents_allowed.csv`.

## Version 2 (after Hannah's review FAIL of v1 at 85b246ab, 12 Nov 15:32Z)

v1's no-number fallback could return a homonym's folder URL. v1 also fetched GACC pages, which list 2025 and 2026 season folders.

## What the script guarantees (v2)

1. **Pages fetched.** The ROOT page only, which must list GACC directories and nothing else. If it lists anything else, the script aborts and prints nothing from it.
   - GACC pages are NEVER fetched.
   - Under each GACC, only CONSTRUCTED URLs are tried, from a frozen template list, for the 2020–24 years in EXPOSED.csv: `{y}/`, `Z_{y}_HISTORIC/`, `GACC_Incidents/{y}/`, `Historic_archived NIROPS/{y}_fires/`, `pre2015-great_basin_w/{y}/` (layouts from firecast-lab/docs/FRESH_HOLDOUT.md §2.1). A 404 means absent.
   - Any URL containing 2025–2029 is refused.
2. **Grouping folders.** At most one level deeper, into grouping folders only: the name contains "incidents" and has no unit-number pattern. A fire's own folder is never opened.
3. **Parsing.** `<a href>` values only, in memory. Link text, mtimes and sizes are never read.
4. **Output.** One line per exposed incident, then a TOTAL line:
   - `FOUND <url>` only when the unit code, incident number and fire name all match;
   - `AMBIGUOUS <n>`;
   - `NAME_ONLY <n>` for folders with no incident number whose name, minus a leading year, equals the FULL fire name (repeated tokens counted once). No URL is given, because the folder may be a homonym. The custodian resolves these by hand;
   - `NOT_FOUND 0`.
5. **stderr.** A template per URL tried (`GACC[i]/T<k>/<year>[/GROUP[j]]`), then ABSENT or the response sha256.
6. **Test** (`TEST_OUTPUT.txt`: PASS). It asserts:
   - the exact set of fetched URLs: ROOT, the constructed URLs and one group page;
   - that no GACC page and no 2025/2026 URL is fetched;
   - that no planted non-exposed name, time or size leaks;
   - Hannah's homonym case (`pacific_nw/Z_2021_HISTORIC/2021_RiverComplex/`) gives NAME_ONLY with no URL;
   - generic single tokens never match;
   - that a ROOT holding a year, an incident folder or a file aborts with nothing printed.

## Run (custodian)

```
python3 -I find_exposed_ir_folders.py EXPOSED_29.csv --out exposed_ir_folders.tsv 2> pages.log
```

The default root is `https://ftp.wildfire.gov/public/incident_specific_data/`. This is the path in Magstadt's NIROPS.ipynb; it was not checked from here.
