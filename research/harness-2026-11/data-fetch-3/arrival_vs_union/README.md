# Arrival-valid set vs final NIROPS union (S-D9 A1 §4.1 rule 5)

`arrival_vs_union.py` checks, cell by cell, whether the Choi et al. 2026 kriged arrival raster (`regions/<id>/arrival_time_hours.tif`, byte-identical to Zenodo 21788344 `rasters_us/<id>_pswt_ok_toa.tif`) is valid on exactly the final NIROPS perimeter union (the last cumulative state of the repo's `wildfire.survival.survey_states`, cell centres) for the 29 exposed US project events.

The script was run on 2026-11-12 on the inputs below:

| Input | sha256 |
|---|---|
| `forecast/data/environment/events.json` | `607f831e…ac8b` |
| `forecast/wildfire/survival.py` | `c70db8ad…bc5b` |
| `NIROPS_2020_2024_R1_R6.shp` | `a14f391a…f09b` |

The script itself is `c847e3df…de40` (`python -I arrival_vs_union.py EVENTS_JSON ENV_ROOT NIROPS_SHP ARCHIVE_EXTRACTED OUT_CSV`, with `forecast/wildfire` importable beside it as `repo_forecast/wildfire`).

**Result:** valid = union on 29 of 29 fires (`valid_not_union` = `union_not_valid` = 0, 159,522 cells in total). The regions, archive and events.json grids are identical on every fire. The NIROPS file was read per fire with an OGR where-filter, so only these exposed incidents were opened; none appears in the S-D9 cohort split.

**Note from S-D9 (Victor):** for RedRock the final union here is 2,285 cells. The union derived from the forecast-v2 held-out record R (the last scored interval's unscored complement plus its positives) has 2,283. The likely cause is that R's last scored interval ends before the final survey, for example where a gap over 48 h leaves no consecutive interval. The other five cohort-R fires agree exactly. This check (arrival-valid vs the union of all surveys) is unaffected.
