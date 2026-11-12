# Custodian script: the exposed incidents' NIFC FTP IR folders (for Hannah to review and run once)

The orchestrator's ruling (12 Nov 2026, 15:25Z): Daniel does NOT fetch FTP directory pages. Hannah reviews this script, runs it once, and hands Daniel the folder URLs. Daniel opens only those folders.

## Files

- `find_exposed_ir_folders.py`: stdlib only.
- `test_find_exposed_ir_folders.py`: a fixture test with no network. `TEST_OUTPUT.txt` holds its output (PASS).
- `EXPOSED_29.csv`: the 29 exposed incidents (forecast-v2 fit and held-out), with their years. It was made from `allowed_fields/nirops_incidents_allowed.csv`.

## Version 3 (after Hannah's run of v2, 15:38:41Z: the server returned 404 for the incident_specific_data/ index, so the run aborted after 1 URL)

v3 fetches NO index page at all: no root page and no GACC page. Every URL is CONSTRUCTED from frozen lists.

- **ROOTS:**
  - `.../public/incident_specific_data/`: from Magstadt's NIROPS.ipynb cell 0 and the FRESH_HOLDOUT.md links W4, W5, W42 and W43. Its own index returns 404, but subpaths may exist.
  - `.../public/incident_specific_maps/`: the tree where Sofia's 12 Nov crawl started.
- **GACCS:** the seven areas in Magstadt's region list: calif_n, calif_s, great_basin, n_rockies, pacific_nw, rocky_mtn, southwest. The spellings come from NIROPS.ipynb and FRESH_HOLDOUT; calif_n and calif_s are conventional and not verified from a document.
- **TEMPLATES (per year):**
  - `{y}/`, `Z_{y}_HISTORIC/`, `GACC_Incidents/{y}/`, `Historic_archived NIROPS/{y}_fires/`, `pre2015-great_basin_w/{y}/`;
  - `{y}_Incidents_Oregon/`, `{y}_Incidents_Washington/`, `Z_{y}_HISTORIC/{y}_Incidents_Oregon/`, `Z_{y}_HISTORIC/{y}_Incidents_Washington/` (the W4 and W5 layouts).

  A 404 means absent. Any 2025–2029 URL is refused. Requests are spaced 0.3 s apart; a full run is about 504 URLs plus grouping pages.

Unchanged from v2:
- FOUND requires unit code + incident number + name.
- NAME_ONLY gives no URL.
- At most one grouping level ("incidents" in the name, no unit-number pattern).
- hrefs only.
- The stderr templates are now `R<r>/GACC[i]/T<k>/<year>[/GROUP[j]]`, with no names.
- The test asserts the exact fetched set (constructed URLs plus group pages), that no index page and no 2025/26 URL is fetched, and that no GACC name appears on stderr. It covers the W4 layout (Pioneer FOUND under incident_specific_maps) and a Z_HISTORIC state group (Jack FOUND).

## Run (custodian)

```
python3 -I find_exposed_ir_folders.py EXPOSED_29.csv --out exposed_ir_folders.tsv 2> pages.log
```

The default ROOTS are both trees above. `--root URL` (repeatable) overrides them.
