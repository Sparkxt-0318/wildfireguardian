# Talk figures (Korea Code Fair, 10-minute talk)

Branch `talk/figures` (not merged). Every figure is made by one script in `src/`, reads its numbers from committed
result files through `src/prov.py`, and writes a ledger used for `SOURCES.md`. Decisions are in `DECISIONS.md`; missing
inputs in `NEEDS.md`.

| file | what |
|---|---|
| `Fxx_name.svg/.pdf/.png` | complete figure with its numbered caption (PNG 3840 px wide; PDF fonts embedded) |
| `Fxx_name_nocaption.*` | the same without the caption |
| `Fxx_name_notext.png/.svg` | the same graphic with every word and number removed (same size and position) |
| `kcf_talk_figures.pptx` | one figure per slide, editable: schematics as native shapes, F02 as a native chart, every label and caption a text box; last slide = palette |
| `contact_sheet.png` | every figure with its code |
| `kcf_talk_figures.zip` | the pptx plus all PNG, SVG and PDF files |
| `check/` | greyscale versions and the collision-check result of each figure |

## Figures

| code | slide | files | what it shows | status |
|---|---|---|---|---|
| F01 | 1 (right half) | `F01_title_map.{svg,pdf,png}`, `F01_title_map_nocaption.*`, `F01_title_map_notext.{png,svg}` | Uiseong–Andong replay area at 12:00 KST, 25 Mar 2025: roads, forecast fire, villages by time left | done |
| F02 | 2 (right two thirds) | `F02_road_cut.{svg,pdf,png}`, `F02_road_cut_nocaption.*`, `F02_road_cut_notext.{png,svg}` | Samui-ri time axis (road cut 159.6 min before the fire) and the gap histogram (n = 97) | done (native histogram in pptx) |
| F03 | 3 (full) | `F03_comparison_grid.{svg,pdf,png}`, `F03_comparison_grid_nocaption.*`, `F03_comparison_grid_notext.{png,svg}` | Three-rule comparison table: Korea, Technosylva, Genasys, Watch Duty, WildfireGuardian | done with a note: cells from the brief (D18) |
| F04 | 4 (full) | `F04_overview.{svg,pdf,png}`, `F04_overview_nocaption.*`, `F04_overview_notext.{png,svg}` | Method overview, one case left to right (Uiseong–Andong, 18:00 KST): inputs, forecast model and kernels, heat zoomed to the fire on log scales with the burned outline, margin and gate (Within the calibration range?), leave-by times in four classes on main roads, village card and checker | done with notes: (c) shows Fish Creek, no Korean fuel maps (D30); (d)–(f) come from the replay, not from (b) (D31, D39); five-colour palette and F04 revision (D42, D43); 17 in canvas, PNG 300 dpi transparent (D33) |
| F05 | 5 (full) | `F05_data_foundation.{svg,pdf,png}`, `F05_data_foundation_nocaption.*`, `F05_data_foundation_notext.{png,svg}` | Data foundation, each panel headed by its result: records with no satellite label by tier on one axis (207,508; verified 2.1%, false-label rate not measured), first label earlier for 45 of 240 fires (median 42 min), one record cleaned reversibly with hidden spaces drawn | done with a note: panel (b) shows the leads, not one fire's signal (D20); reworked (D40) |
| F06 | 6 (full) | `F06_safety_distance.{svg,pdf,png}`, `F06_safety_distance_nocaption.*`, `F06_safety_distance_notext.{png,svg}` | 5-hour spread of 28 California fires with the 3.75 km safety distance and its held-out miss rate; Gyeongbuk 25 March 2025 by issue hour, each hour marked withheld or given | done (D38) |
| F12 | 7 (full width) | `F12_forecast_example.{svg,pdf,png}`, `F12_forecast_example_nocaption.*`, `F12_forecast_example_notext.{png,svg}` | Wapiti 2024: forecast chance of burning beside the mapped burns 36 h later, marked as the most favourable interval chosen after results; average precision and Brier score of three rules over all 25 intervals on full scales | done (D41) |
| F07 | 7 (full) | `F07_forward_backward.{svg,pdf,png}`, `F07_forward_backward_nocaption.*`, `F07_forward_backward_notext.{png,svg}` | Forward search from one village against one backward pass from the shelters (schematic) | done (native shapes in pptx; five colours, D42) |
| F07m | 7 (map version) | `F07_map.{svg,pdf,png}`, `F07_map_nocaption.*`, `F07_map_notext.{png,svg}` | The same comparison on the real map (Wondang-ri, 18:00 KST, OSM basemap): a forward search from one village leaving 18:00 (661 road pieces) against one backward pass from every shelter (leave-by classes; both villages outside the fire area) | done (D44) |
| F15 | 7 (full width) | `F15_exposure.{svg,pdf,png}`, `F15_exposure_nocaption.*`, `F15_exposure_notext.{png,svg}` | Fish Creek exposure maps across the slide: chance you cannot see 10 m, fine smoke, CO; burned area, north arrow, scale bar, labels at the highest values (D35) | done with a note: rebuilt from screenshots, colour-bar ticks typed in by eye (D26); redo from the arrays when they arrive |
| F16 | 7 (right half) | `F16_safety_zones.{svg,pdf,png}`, `F16_safety_zones_nocaption.*`, `F16_safety_zones_notext.{png,svg}` | d = 4H geometry and the distribution of d* (13,125 cells below 375 m) | done with a note: largest d* 323 m in the file, 320 m expected (D22) |
| F17 | backup | none | Heat on terrain (3D) | not done: terrain and thermal arrays not on this machine (NEEDS.md) |
| F08 | 8 (full) | `F08_backward_step_checker.{svg,pdf,png}`, `F08_backward_step_checker_nocaption.*`, `F08_backward_step_checker_notext.{png,svg}` | One backward step on a time axis; solver, certificate and independent checker | done (native shapes in pptx; five colours, blocked wording, D42) |
| F08m | 8 (map version) | `F08_map.{svg,pdf,png}`, `F08_map_nocaption.*`, `F08_map_notext.{png,svg}` | One backward step on the first real road of Wondang-ri's route (315 m): safe arrival at the far end, drive time, fire reaching the road, resulting leave-by time 18:15:21 | done (D45) |
| F09 | 9 (full width) | `F09_speed.{svg,pdf,png}`, `F09_speed_nocaption.*`, `F09_speed_notext.{png,svg}` | Search per village (earlier) against one backward pass (ours): six forecast hours in KST with place and check counts, total (129×), line at the hourly update (D36) | done |
| F09b | 9 (variant, full) | `F09b_speed_fastpath.{svg,pdf,png}`, `F09b_speed_fastpath_nocaption.*`, `F09b_speed_fastpath_notext.{png,svg}` | F09 plus the scalar fast path as its own panel (other machine); rows and names as F09 (D36) | done |
| F10 | 10 (full) | `F10_camp_fire.{svg,pdf,png}`, `F10_camp_fire_nocaption.*`, `F10_camp_fire_notext.{png,svg}` | Camp Fire: 170 of 195 blocked-road reports flagged before the crew report (map with Paradise), hours earlier (half ≥ 2.5 h), hits and false alarms (22 of 23 passable roads also flagged) | done with a note: no road lines or fire area, none committed (D12, D37) |
| F11a | 11 | `F11a_village_card.png` | One real village card (삼의리 Samui-ri), exported at 300 dpi as printed | done |
| F13 | backup | `F13_kernels.{svg,pdf,png}`, `F13_kernels_nocaption.*`, `F13_kernels_notext.{png,svg}` | Four mean effective kernels and their embedded sum (h⁻¹) | done with a note: rebuilt from the preprint's vector PDF, calibrated to its table (D24) |
| F14 | backup | `F14_reliability.{svg,pdf,png}`, `F14_reliability_nocaption.*`, `F14_reliability_notext.{png,svg}` | Reliability of the reported model, low-probability region enlarged | done |

## Rebuild

```
bash talk/figures/make_all.sh
```

needs Python 3 with matplotlib, numpy, pandas, pillow, python-pptx, pyproj, tifffile (the script creates `.venv-fig`),
`pdftoppm`/`pdftotext` (poppler), `gh` (for the read-only wildfireguardiandata files, cached in `.cache/`, not
committed), and LibreOffice for the render check (`tools/check_pptx.sh`, which points LibreOffice at the macOS system
fonts with `tools/fonts.conf.template`; without it LibreOffice's headless mode falls back to its own serif fonts).

## Style

Research-paper style (revision of 24 Nov): framed axes with light gridlines, one text size (16 pt) and 18 pt axis
titles, boxed legends, whiskers wherever the source has an interval, (a)/(b) panel letters, numbered captions carrying
the headline numbers and caveats, square-cornered schematic boxes with 0.75 pt outlines. Palette and fonts in
`src/style.py` (Helvetica Neue; Inter is not installed; Apple SD Gothic Neo for Korean, D46). Each script fails if any text comes
within 4 pt of another text, a data mark, an axis or the canvas edge (`src/figkit.py`).
F04, F07 map and F08 map also run `src/labelcheck.py`: Korean place names are in Hangul from the planner data
(`src/placenames.py`), every character has a glyph, and no label touches a village, shelter or route mark.
