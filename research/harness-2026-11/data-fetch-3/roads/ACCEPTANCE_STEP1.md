# Road rebuild acceptance, step 1: the CURRENT windows (pass rule, written before any OSM request)

Written 2026-11-12, about 15:45Z. No ohsome or other OSM request has been made. Any later change goes in a new file; this one is never edited. The orchestrator approved the plan at 15:32Z: rebuild the current windows and compare first, then the export grid + 5 km.

## Reference (owner graphs)

They come from the repo's pinned release `research-final-20261015` (archive sha256 d7e0a5fc…2882202), fetched with `tools/fetch_routing_inputs.py`, which verified all 132 files.

| region | graph.json sha256 | grid (EPSG:5179) | nodes | edges | distinct source_way | forbidden_turns |
|---|---|---|---|---|---|---|
| uiseong_andong_2025 | 8c37e5b6440608bc07de71be89dd02fb4d75f7176b4aed9c54df80ecd3de1afc | x0 1093875, y0 1815750, 73 × 65 | 23,158 | 43,826 | 2,065 | 39,502 |
| yeongdeok_2025 | f097e6c8d8bb4454696b23a5d5cf1483ec29ba33dea5c9877e7100c4933b14a9 | x0 1147500, y0 1815750, 71 × 67 | 56,369 | 111,924 | 3,849 | 106,973 |

Facts measured from these files (and by Leo):
- Node ids are `osm:<node id>`, and every node lies inside the window.
- Edge ids are `w<way>:s<k>:f|r`. Here k is the index of the node pair along the FULL way: 40 UA ways and 34 YD ways start at k > 0, where they enter the window.
- travel_ticks = ceil(chord / (40 km/h)) with dt = 1 s.
- segments are split at 375 m cell boundaries, using the cell index of each grid.
- forbidden_turns = U-turns at non-dead-end heads, plus 30 (UA) and 9 (YD) other pairs, which are presumably OSM turn restrictions.

## Rebuild recipe under test

From the 2025-03-21T23:59:59Z OSM snapshot:
- take every highway way with at least one node inside the window;
- keep its nodes inside the window;
- make one edge per consecutive pair of kept nodes, using the full-way index k;
- set direction from `oneway`, treating a missing tag as two-way;
- apply the owner's exclusions (private, no-access, and unsupported conditional or restriction ways).

**The highway class set is NOT chosen in advance.** It is read from the tags of the owner's own source_way ids in the same snapshot, and then applied unchanged.

## Pass rule (per region)

1. The node id sets are equal.
2. The edge id sets are equal, and each edge has the same u and v.
3. travel_ticks are equal on every edge.
4. segments are equal on every edge: the same cell sequence, with fractions within 1e-9.
5. Node x and y agree within 0.01 m. The projection is EPSG:4326 → 5179 with pyproj (version recorded).
6. forbidden_turns: the U-turn subset is equal to what the dead-end rule predicts. The other pairs (30 UA, 9 YD) are compared with the snapshot's turn-restriction relations and reported as matched or unmatched.
7. `waitable` is INHERITED by node id from the owner graph and is NOT re-derived, because its rule is unknown (Leo). It is reported as such.

The region PASSES if 1–6 hold exactly. Otherwise every difference is listed by category, with counts and example ids, and the result is reported as a partial pass. Widening to the export grid + 5 km happens only after this report is out. The widened graph must then reproduce the step-1 graph inside each window.

## Known risk, recorded in advance

ohsome `/elements/geometry` returns way geometries without OSM node ids. Node identity then has to come from coordinate matching against the snapshot's nodes, at 1e-7° (about 1 cm), or from another ohsome endpoint. If identity cannot be established exactly, criteria 1–2 are reported as "matched by coordinate", not as id equality.
