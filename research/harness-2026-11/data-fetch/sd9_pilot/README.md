# S-D9 pilot inputs (part a only): Blue2, MossMountain_Chalk, Homestead_Salmon33

These were built on 2026-11-12 with `build_nirops_event.py` and `rebuild_env.sh`. The allowlist was S-D9 `cohort/PART_A_ALLOWLIST.csv` @ bba8d00d (sha256 `956dfa09…5926`).
Only these three incidents' NIROPS features were read, using an OGR attribute filter. No part b, c or d fire was opened.

| Fire | Grid (EPSG:5070, 375 m) | Survey times | Intervals 0 < dt ≤ 48 h | Mapped cells at last survey | Window (UTC) |
|---|---|---|---|---|---|
| NM-LNF-000227_Blue2 | 29×35 | 20 | 17 | 211 | 2024-05-18 00:00 to 06-16 07:00 |
| OR-WIF-240214_MossMountain_Chalk | 31×37 | 65 | 57 | 181 | 2024-07-23 00:00 to 10-15 04:00 |
| OR-UPF-240311_Homestead_Salmon33 | 15×15 | 69 | 61 | 7 | 2024-07-22 00:00 to 10-20 04:00 |

Per fire, `regions/<id>/` contains:
- `labels/cumulative_masks.npz`: cumulative survey unions at cell centres.
- `labels/intervals.csv`: consecutive survey pairs with 0 < dt ≤ 48 h.
- `arrival_time_hours.tif`: the stepwise first-mapped survey time; it is also the grid template.
- `grid.json`
- `terrain/`, including slope.
- `vegetation/`, including tree cover.
- `biome/`

**Missing channels:** temperature and east/north wind. The `weather` stage fails with Open-Meteo HTTP 429 "Daily API request limit" on this egress IP. The repo code refuses to bypass it, and so do I.
**Not run for this pilot:** canopy (GLAD TLS root not trusted); gridmet, landfire and enrich ran in the `rebuild_env.sh` test but were not part of the six requested channels.

Checks:
- The grid rule reproduces the archived Choi grids of Moose, GreenRidge, Dixie and CameronPeak exactly.
- The label pipeline, rerun on the exposed Wapiti fire, reproduces all 52 committed held-out cases exactly (`forecast/runs/20261030_perimeter_trained/execution_v3/heldout/cases`): the same grid, `reference_cells`, `positives` and the identical `y` vector at every scored cell.
- Two independent runs produced byte-identical outputs (27 of 27 files for Blue2).
- Covariate values for Wapiti cannot be compared. The repo keeps only snapshot SHA-256s, and no covariate rasters or values exist for it.
