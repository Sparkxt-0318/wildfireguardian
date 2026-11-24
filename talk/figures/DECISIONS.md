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
