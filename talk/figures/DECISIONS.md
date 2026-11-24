# DECISIONS

Decisions taken without asking, with the reason for each. Numbered in the order they were made.

**D1. Where the work happens.** The repository checkout at `/Users/jp/wildfireguardian-forecast` was on another branch with other work in progress, so the figures were built in a separate git worktree (`.claude/worktrees/talk-figures`) on a new branch `talk/figures`, cut from `origin/Main` at `5ff9aa90`. Nothing was committed to `Main`, and nothing was written inside `/Users/jp/Desktop/wildfire`, the preprint folder or `wildfireguardiandata`.

**D2. Font.** Inter is not installed on this machine. Helvetica Neue is installed, so every figure and the PowerPoint file use Helvetica Neue. Korean text falls back to NanumGothic, a TrueType font that embeds cleanly in PDF. Fonts are embedded in the PDFs as TrueType (Type 42). Text in the SVGs stays real text.

**D3. Canvas and placement.** Every figure is drawn on the full 13.333 × 7.5 in slide canvas. A figure meant for the right two thirds of a slide keeps its content inside x ≥ 4.45 in, so the PNG can be dropped on the slide at full size and the left third stays free for text. The top 0.9 in stays clear for the slide title.

**D4. Collision check.** `src/figkit.py` collects, after layout, the box of every text and the geometry of every data mark: lines, bars, markers, polygons, images and axis spines, clipped to the axes they are drawn in. A figure fails if any of these happen:
- two text boxes come within 8 pt of each other (half a line at 16 pt);
- a text comes within 4 pt of a mark;
- a text comes within 4 pt of the figure edge.

Map context such as roads and tints is tagged `bg` and is not counted. A box that is meant to hold text is tagged `box`, and the text may not cross its outline. Every figure script fails if the check fails, and the result is written to `check/<name>_overlap.json`.

**D5. Native charts.** F09 and F09b use log time axes with tick labels in mixed units (1 min, 1 h, 100 h) and a separate column of ratios. A native PowerPoint chart cannot label a log axis in mixed units, so these two use the picture-plus-text-box rule, as the prompt allows.

**D6. F09b.** The scalar fast path was timed on an Apple M5 Pro laptop under load (`runs/HOST.json` on `research/kcf-fastpath`). F09 was timed on an Intel Xeon server pinned to one core (`kcf-bench` host B). The two sets of seconds cannot share an axis, so F09b is a full-slide figure with two panels. Panel a repeats F09. Panel b plots, for each of the six cases, the field time of the deadline field and of the fast path from the same laptop, with its own log axis and its own ratio column. Panel b also has no cold and warm split, because the fast-path study did not record one.

**D7. F07 network.** The real Uiseong–Andong graph (`data/routing/graphs/uiseong_andong_2025/graph.json`, not committed) has 23,158 nodes and 43,826 edges. Even cut down to a handful of villages, its short OSM segments become unreadable at slide scale. F07 therefore uses a clean synthetic network of 25 junctions, the same layout in both panels, as the prompt allows. The time bars are illustrative shapes and carry no numbers.

**D8. F08 certificate count.** The number "174 village certificates pass" exists only as a sentence in `product/wfg-roadlayer/README.md`. The two golden `MANIFEST.json` files list 84 and 90 certificates, and the script checks that they add up to the README's number. The committed test asserts all 84 Uiseong–Andong passes but samples only every 15th Yeongdeok certificate. This is recorded in SOURCES.md.

**D9. F08 colour of the closure.** The prompt asks for vermilion for "closed: fire on the road". The fixed palette's colour for fire and closed is brick red `#B5483A`, so that colour is used.

**D10. F06 axis.** F06 uses a linear axis from 0 to 54 km, without a break or a log scale:
- The median 5-hour reach of the 20,161 California hours is 0 km. A log axis cannot show zero, and those hours would disappear.
- A broken axis would hide the empty space between the calibration maximum (17.3 km) and the Gyeongbuk hours (up to 40.1 km), and that empty space is the message.

On the linear axis the 3.75 km line still sits clearly above zero. The printed safety distance is the file value, 3.75 km, not the rounded 3.8.

**D11. F06 Korean hours.** All 23 complete 25 March issue hours are plotted. The 11 run hours (10–20 KST), whose answer was withheld, are filled. The other 12 hours are hollow. The hatched band marks the column of withheld answers. Over the whole day, 22 of 24 hours were withheld, and SOURCES.md records this.

**D12. F10 has no road lines.** The Paradise road graph was never committed; only the checksums of the four OSM tiles are (`research/kcf-camp/data/osm_tiles_sha256.txt`). No copy was found on this machine. Downloading OpenStreetMap data again was not done in this run. The map therefore shows only the 195 report locations, with a scale bar and a north arrow. If `PARADISE_GRAPH=/path/to/graph.json` is set (the file made by `research/kcf-camp/build_graph_osm.py`), the script notes the path so the roads can be added; the drawing code for them is still to be written.

**D13. F10 median.** The prompt expects "median 119 minutes" for the caught reports. In the files, 119 min (`numbers.json` → `tests12.test1.strict.MR.time_error_min_closed_rows.median = -118.8`) is the median time error over **all 195** closed reports, caught and missed together. The figure plots the 170 caught reports, as the prompt asks, so it marks their own median, **153 min** (from `test1_road_state.csv`). Both values are in SOURCES.md. A report counts as caught when the road was closed no later than 15 min after the report time (`TOL_MIN`). Five of the 170 were closed up to 13.7 min after the report, so they appear just below zero.

**D14. F02 village.** The village is 삼의리 Samui-ri (영양군 Yeongyang), at the 18:00 KST issue on 25 March 2025. It has the largest gap (159.6 min) among the 97 place-hours where a road ends the window. It is also easy to explain: there is one departure window, from 18:00 to 20:39, and it ends when a road cell closes, so the time axis needs only three marks. The histogram covers those 97 place-hours. The printed "68 of 174 places" is the wider count A in the files (154 place-hours: 103 where a road ends the window, plus 51 with no departure window at all). The figure labels the two counts separately so that they are not read as the same set.

**D15. F01 issue hour and extent.** Only two issue hours have a committed forecast raster: 12:00 and 18:00 KST (`product/wfg-roadlayer/examples/fire_arrival_*.tif`). The map uses 12:00 KST because it is the more varied of the two. At 12:00 all four departure states occur (124 places with no road cut within 8 h, 24 inside the fire, 16 with a latest safe departure, 10 with no safe departure). At 18:00 only three occur. At 12:00 the fire affects only Uiseong–Andong, and the two regions are about 50 km apart, so the map shows the Uiseong–Andong region box from `scene.js`. Roads and water come from the committed OSM basemap (`planner/public/kcf-scene/data/basemap.js`).

**D16. F01 colour and numbers.** The prompt names two colour scales for "time left": "bluish green to orange" in the F01 description, and "time left: the cividis colormap" in the style rules. The style rule names this exact quantity, so F01 uses cividis, reversed so that less time is yellow and more time is dark. Places with no road cut within 8 h get the "more" end of the scale. The key uses the words "less" and "more" instead of numbers. The only number on the map is the "5 km" of the scale bar, which a map needs. The forecast fire is drawn as a pale tint of the fire colour, so the roads and village dots stay readable on top of it.

**D17. Paper style (revision of 24 Nov).** All figures were redrawn in the research-paper style:
- framed axes, light grey gridlines, and one text size (16 pt) for labels, tick labels, legends and captions, with 18 pt for axis titles;
- boxed legends, and whiskers or error bars wherever the source has an interval;
- (a)/(b) panel letters, and a numbered caption under every figure;
- schematics with square-cornered boxes and thin 0.75 pt outlines.

Headline numbers moved from the plots into the captions. Each figure is exported with its caption (`Fxx_name.*`), without it (`Fxx_name_nocaption.*`), and text-free (`Fxx_name_notext.*`). Figures finished before the style change were redrawn too, so that the set stays consistent.

**D18. F03 cell values.** No market-research summary is committed. A search of every local and remote ref for "technosylva", "genasys" and "watch duty" found only passing mentions in `research/harness-2026-11/research-scout/`, none of which compares the products. The cells are therefore the values given in the brief: Korea yes, yes, no, no; Technosylva yes, no, no, no; Genasys no, yes, no, no; Watch Duty yes, yes, no, no; WildfireGuardian no, no, yes, yes.

**D19. F14 intervals.** The preprint applies no interval to the reliability bins; its caption says so. The figure adds Wilson 95% intervals, computed from each bin's entry and new-burn counts in `wapiti_calibration_table.tex`, and the caption says they were computed for this figure. A label for the lowest bin could not be placed in the enlarged panel without crossing the diagonal or an error bar, so its three values (93.91% of entries, 0.0131% predicted, 0.3642% observed) are in the caption.

**D20. F05 panel (b).** The per-fire 5-minute satellite signal is inside `release/live-v0.1/live_export_v0.1.tar.gz` (18.8 MB of per-frame arrays). Two downloads were cut off by the network, at 8 MB and on a stream reset. A signal would also have to be computed from the raw frames, which no committed file gives as a series. Panel (b) therefore plots what the committed label file does give: the lead `lead_vs_T0_min` for each of the 45 of 240 fires whose first label moved earlier, with the median and bootstrap interval stated in `HEADLINE_NUMBERS.md` (42 min, 22–84). One fire's signal curve is left to a later run that can read the archive.

**D21. F05 data access.** The data repository is read only and was not cloned into this one. A full clone stalled, so the files F05 needs were fetched one at a time with `gh api` into `talk/figures/.cache/wgd/` (ignored by git), together with the last commit hash of each file, which SOURCES.md lists. `make_all.sh` repeats the fetch. The record in panel (c) is `fod:1389433`, the first record in `patches_us.jsonl.gz` with three patches, one of which is a placeholder repair. Trailing spaces are written as ␣×k. The panel labels its data scope "United States data, 2018 to 2020", which applies to panel (a). Panel (b) covers 2023–2025 fires, and panel (c) the 1992–2024 FPA FOD national run; the caption states both.

**D22. F16.** The receiver is drawn at exactly d = 4H. The histogram uses the baseline fuel level for all 13,125 burned cells of the four reconstructed fires (column `dstar_7` of `cells_KFS_*.csv.gz`), with a log count axis because most cells lie near zero. The prompt expects "largest 320 m", which is also the wording of `RESULTS.md` ("max 320 m, Uiseong, high fuel"). `fires_summary.json`, however, gives 323.45 m for Uljin 2022 at high fuel, which is larger than Uiseong's 319.85 m. The figure prints the file value, 323 m, and SOURCES.md records the difference. The equations use matplotlib's STIX math font. In PowerPoint they become text with italic symbols.

**D23. F15 source.** The saved exposure arrays are not in `/Users/jp/Desktop/wildfire`, because the `demonstration/flame_danger/physical_exposure/` folder is missing (NEEDS.md). The only sources are the two session images in `Oral Presentation Figure/Heat Physics/`. They show the four exposure panels as screenshots with non-linear colour bars. See the README for the status of F15.
