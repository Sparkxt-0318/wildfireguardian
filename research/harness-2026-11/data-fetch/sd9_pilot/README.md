# S-D9 pilot inputs (part a only): Blue2, Line, ThreeNine

These were built on 2026-11-12 with `build_nirops_event.py`. The allowlist is S-D9 `cohort/PART_A_ALLOWLIST_FINAL.csv` @ ff38bdcd
(sha256 `801acdd8…391e`, 489 incidents). Only these incidents' NIROPS features were read, through an OGR attribute filter. No part b, c or d fire was opened.

| Fire | Grid (EPSG:5070, 375 m) | Survey times | Intervals 0 < dt ≤ 48 h | Mapped cells at last survey | Window (UTC) |
|---|---|---|---|---|---|
| NM-LNF-000227_Blue2 | 29×35 | 20 | 17 | 211 | 2024-05-18 00:00 to 06-16 07:00 |
| CA-BDF-012520_Line | 50×72 | 40 | 35 | 1,275 | 2024-09-07 00:00 to 11-13 08:00 |
| CA-SHF-001004_ThreeNine | 37×24 | 20 | 9 | 88 | 2023-08-19 00:00 to 11-09 05:00 |

**Replacements.** The S-D9 filters (`cohort/RUN_FILTERS.md` @ f91cf824) removed two of the original pilot fires:
- MossMountain_Chalk (leakage filter);
- Homestead_Salmon33 (duplicate of part-b ReynoldsButte).

Their outputs were deleted from this folder and must not be used. The replacements are the next eligible, kept part-a incidents in `u` order: Line and ThreeNine.
The builder now refuses Chalk against the final allowlist.

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
