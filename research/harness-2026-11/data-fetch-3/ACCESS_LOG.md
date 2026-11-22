# NIROPS access log: Daniel (data fetcher), 12 Nov 2026

This log covers every command in this session that read the NIROPS 2020–2024 shapefile or its parts. It was reconstructed from the session transcript by searching all shell commands for `NIROPS` together with a read call (`read_dataframe`, `build_nirops_event`, `gridtest`, `unzip`). That search found 42 matching commands; the reads among them are listed below with their times (UTC). Commands that only mentioned the file name (documentation edits, `grep` of my own scripts, `sed -n` views, commits) are listed at the end. Wherever a command printed anything, the printed output was recovered from the transcript and is quoted here.

Source files (Mendeley 10.17632/95rj5d379g.1):
- `NIROPS_2020_2024_R1_R6.zip`: `b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615`
- `.shp`: `a14f391ae0e2f75a1d218aed91ad03eb35bfc311a4909021f9fe1f6310fdf09b`
- `.dbf`: `568c0412d6507adc2ce9013bd3d5aefbfa8ed24ca0a70c7b08ca17453f6d0eb7`
- `.shx`: `02f94a1415c9ad80072a24fe6198035e0b4f9b29bd0107a2bde66293b2b01b77`
- `.prj`: `a02a27b1d1982c8516d83398e85a3c8b1aef1713c13ef4d84d7bde17430c07c4`
- `.cpg`: `3ad3031f5503a4404af825262ee8232cc04d4ea6683d42c5dd0a2f2a27ac9824`

The S-D9 split (COHORT_SPLIT) did not exist before about 09:30 UTC. Part b/c/d below means the parts as later assigned.

## Reads

| Time (UTC) | Command / script | What was read | All records? | Written | Printed (verbatim summary) |
|---|---|---|---|---|---|
| 09:01:51, 09:02:06 | `unzip -l` on the Mendeley zips | zip directory listings only | n/a | the zips under scratchpad/dl/nirops | file counts and folder names per zip; the 50 shapefile sidecar names |
| 09:02:36 | `unzip -Z1` on `Area_Progression_TimeSeries.zip` and `Supplementary_Maps.zip`; first 20 markdown cells of `NIROPS.ipynb` | member names of the PNG zips (one PNG per incident; names were counted, not listed) | names only | nothing | "709 png" and per-region folder counts for each zip; notebook markdown headings |
| 09:04:23 | `dbf.py` (scratchpad) | **all attribute columns of all 12,706 records**, no geometry: `read_dataframe(dbf, read_geometry=False)` | **yes** | nothing | the column list; `df.head(4)`, which shows **4 rows of CA-AEU-017769_Electra (part a)** with UTC, Acres, IRWINID and names; UTC and DateUTC min/max over all records (2020-05-12 to 2024-12-17); distinct counts (737 Incident_C, 692 IRWINID) |
| 09:04:36 | `nirops_inc.py` (scratchpad) → `data-fetch/nirops_incidents.csv` | **all attribute columns of all records**, no geometry | **yes** | **`nirops_incidents.csv`: one row per incident for all 737 incidents, with surveys, first_utc, last_utc, max_acres, irwinid, days, project_status, year. Committed at 0cf39959; edited to `nirops_incidents_v2.csv` (max_acres dropped, shares_irwin added) at 259ef5b4 / 04fad9e1, which is now on Main** | counts by project_status and year (aggregates); "unused with ≥20 surveys: 180"; `wc -l`; the header and the first 2 rows (RedSalmonComplex and HermitsPeak, both project fit fires) |
| 09:17:09, 09:17:25 | `gridtest.py` (scratchpad) | geometry and attributes via `where="Incident_C = '<id>'"` for **Moose, GreenRidge, Dixie, AlderCreek and CameronPeak only** (exposed project fires) | no (where filter; the driver scans the Incident_C field of each record) | nothing | grid shape and transform per fire, compared with the Choi grids |
| 09:19:07, 09:19:16 | `data-fetch/build_nirops_event.py` (v1, where filter at L62) | **Blue2, OR-WIF-240214_MossMountain_Chalk, OR-UPF-240311_Homestead_Salmon33** (S-D9 pilot round 1, all on the then-current PART_A_ALLOWLIST) | no | `scratchpad/sd9pilot/data/environment/regions/<id>/`, `data/perimeters/<id>/` | one "BUILT …" line per fire (grid, survey times, interval count, window, mapped cells) |
| 09:21:39 | `build_nirops_event.py ID-BOF-000683_Wapiti_Wapiti --exposed-reference events.json` | Wapiti (exposed project fire) | no | `scratchpad/wapiti_ref/` | a BUILT line and a grid comparison with the Choi archive |
| 09:41:12, 09:41:25 | `build_nirops_event.py` | **Line and ThreeNine** (after item 9, MossMountain_Chalk and Homestead_Salmon33 were removed: their region and perimeter directories were deleted from sd9pilot at 09:41) | no | `scratchpad/sd9pilot/...` | BUILT lines |
| 09:47:45, 09:49:51 | `build_nirops_event.py` after the A1 time-rule change | Blue2, Line, ThreeNine (rebuild) | no | `scratchpad/sd9pilot/...`; committed `data-fetch/sd9_pilot/` | BUILT lines |
| 10:24:06 | `arrival_vs_union.py` (L36, where filter) | the **29 exposed US project events** in forecast/data/environment/events.json | no | `scratchpad/v_union/arrival_vs_union.csv` (committed f5342c29) | one summary line per project fire, plus KR raster counts |
| 13:20:37 | `parta_price.py`, committed as `nirops_access/parta_price_v1_AS_RUN.py` (sha256 `87aeeadb…`) | **columns `Incident_C` and `UTC` of all records, no geometry** (L8), filtered in memory to the 490-row allowlist (L9); then geometry by fid for allowlisted incidents only (L12) | **yes, for two columns** | `scratchpad/parta_price.csv`: 490 allowlisted rows (committed at ab065e85) | piped through `tail -12`; the visible lines are in `nirops_access/STDOUT_TAIL.txt` (allowlisted incidents and pool totals only). Lines 0–200 were discarded and never displayed |
| 13:23:55 to 13:53 | `run_parta.sh` → `build_nirops_event.py` v1, once per allowlist row | the **490 PART_A_ALLOWLIST_FINAL (7db3cc0e) incidents**, one where filter each | no | `scratchpad/parta/data/environment/regions/<id>/`, `data/perimeters/<id>/`, `events.json`, `PERIMETER_MANIFEST.json` | stdout of each build went to /dev/null; run.log holds only "BUILT n" counters |
| 14:01:01 | `build_nirops_event_v2.py` (by fid via `nirops_access.py`) | 3 allowlisted incidents: AZ-SCA-002036_Valley, CO-RTF-000363_MiddleFork, OR-781S-000115_7k | Incident_C column only, then by fid | `scratchpad/v2check/` | BUILT lines; byte comparison SAME for all outputs |
| 14:01:34 | `parta_price_v2.py` (by fid) | Incident_C column of all records; UTC and geometry by fid for the allowlist only | Incident_C only | `scratchpad/parta_price_v2.csv` (identical to v1: 490 rows) | totals and the top 5 (allowlisted) |

Since 14:00 UTC every NIROPS read goes through `nirops_access.py`: the Incident_C column alone, then everything else by fid for allowlisted records only.

## Other files with per-incident values that I produced

- `data-fetch/incident_metadata.csv` (Victor's request; on Main) has first_utc, last_utc, discovery_utc, origin lat/lon and WFIGS/ICS-209 names for all 733 cohort and project incidents, b/c/d included. It came from the pinned NIROPS table plus the public WFIGS and ICS-209-PLUS catalogues, by IRWIN ID.
- Column-trimmed copies with only the fields A1 §1.2 allows are in `allowed_fields/`.

## Commands that matched the search but did not read NIROPS data

08:55:31 (`grep` of the repo for file names), 08:58:08 (Zenodo search), 09:00:36, 09:06:06 and 09:06:34 (resources.json and MANIFEST.md edits), 09:24:48, 09:43:07 and 09:50:23 (README edits and copies), 09:47:15 and 09:47:38 (edits to build_nirops_event.py), 09:49:32 (commit), 10:30:47 and 10:31:34 (summaries of arrival_vs_union.csv and its commit), 13:59:39, 14:00:20, 14:00:41, 14:00:51, 14:01:26 and 14:01:46 (`grep`/`sed` of my scripts; writing nirops_access), 14:02:35 and 14:02:47 (this transcript search).
