# Road-graph rebuild rule: Uiseong–Andong 2025 and Yeongdeok 2025 (DRAFT 2, 15:35Z: updated in place from Leo's and Richard's answers; draft 1 is commit 584ccfab)

Written 2026-11-12 before any OSM request. Execution waits until the 00:12 UTC weather launch on 13 Nov (orchestrator).

**Status of the result: an EQUIVALENT graph, NOT byte-identical to the owner's graph.** The owner's graph builder and raw road extract are absent from GitHub, Drive and the owner archive (checked 12 Nov).

## What exists (the reference)

| region | graph_revision (planner/data/osm/SOURCES.json) | nodes (fixtures/nodes) | allowed | node bbox (lon, lat) |
|---|---|---|---|---|
| uiseong_andong_2025 | uiseong-andong-osm-20250321-provisional-G2window-grid375-dt1-a30e1f054a5e-8b859334ebe8 | 23,158 | 23,128 | 128.5463–128.8547, 36.3316–36.5539 |
| yeongdeok_2025 | yeongdeok-osm-20250321-provisional-G2window-grid375-dt1-8a804b26a635-8b859334ebe8 | 56,369 | 56,363 | 129.1441–129.4445, 36.3251–36.5541 |

- graph_snapshot is 2025-03-21T23:59:59Z for both. Node CRS source is EPSG:5179.
- "allowed" means the node has at least one incoming and one outgoing road edge (api/regions.py GraphIndex.load).
- Display roads are in planner/research-map/site/regions/<region>.osm.js, classified as major_road / minor_road / highway / path (track) / rail.

## Facts from Leo (measured from data/routing/graphs/*/graph.json, which is in Leo's container and not in git) and Richard

- **Export grid.** Both regions sit on the KFS_01 export grid: EPSG:5179, x 1,085,250–1,174,125, y 1,815,750–1,845,375, 237 × 79 cells of 375 m.
  - The final burn set has 16,176 cells and touches all four edges of the grid.
  - The writer requires graph grid == forecast grid.
  - So "every exit road reaches outside the burn set" is IMPOSSIBLE on the current hazard grid. It needs a padded hazard grid, which is a contract change and the orchestrator's decision (Leo has flagged it).
- **Current windows.**
  - UA: x 1,093,875–1,121,250, y 1,815,750–1,840,125.
  - YD: x 1,147,500–1,174,125, y 1,815,750–1,840,875.
- **Recipe found in the files.**
  - Nodes are OSM nodes at projected coordinates, NOT snapped.
  - There is one edge per consecutive node pair of a way, in both directions, with ids w<way>:s<k>:f/r.
  - travel_ticks = ceil(chord / 40 km/h), with dt = 1 s.
  - segments = the chord split at 375 m cell boundaries, as {cell, start, end}, with a row-major cell index and row 0 at the south edge.
  - Excluded: private and no-access ways, and unsupported conditional or restriction ways.
  - A missing oneway tag is treated as two-way.
  - U-turns are allowed only at dead ends.
  - The forbidden_turns, waitable and mid_edge_reversal rules are not yet documented.
- **Counts.**
  - UA a30e1f05…: 23,158 nodes, 43,826 edges, 2,065 distinct source_way.
  - YD 8a804b26…: 56,369 nodes, 111,924 edges, 3,849 distinct source_way.
- **Schema needed by Richard's F-3.1:** revision, crs, grid, nodes, edges (travel_ticks, segments with a per-cell index), forbidden_turns, mid_edge_reversal and provenance, on the same grid metadata.

## Rule

1. **Source.** The ohsome API (api.ohsome.org), `/v1/elements/geometry` with `time=2025-03-21T23:59:59Z`, `filter=type:way and highway=*`, the bbox below and `properties=tags,metadata`. Ways only; node IDs come from the geometry vertices via `/elements/geometry` with node references if available, otherwise see step 7.
   - Licence: ODbL 1.0, "© OpenStreetMap contributors". The ohsome metadata and attribution are recorded before use.
2. **Extent.** The export grid plus a margin of N km, for both regions, in one extract.
   - N = 5 is suggested by Leo and still to be fixed by the orchestrator with the padding decision.
   - With N = 5, the WGS84 bbox is about lon 128.3937–129.5035, lat 36.2774–36.6479. Without the margin it is lon 128.4499–129.4465, lat 36.3234–36.6024.
3. **Highway classes.** Taken EMPIRICALLY: the highway tags of the owner's 2,065 + 3,849 source_way ids, looked up in the same snapshot.
   - This needs Leo to commit or share the distinct source_way id lists.
   - The class set found is then applied to the wider extent, with the same exclusions as in the owner's provenance.
4. **Graph.** The owner's recipe as above, written to the same JSON schema and grid metadata as graph.json.
5. **Acceptance, step 1 (before widening).** Rebuild the two CURRENT windows and compare with the owner's graphs:
   - node id set equal;
   - edge id set equal;
   - travel_ticks equal.

   Any difference is stated, not hidden. This needs the owner graph.json files or their id lists; the planner fixtures already give the node ids and lon/lat.
6. **Acceptance, step 2 (widened).** Inside each current window the widened graph equals the step-1 graph. Outside it, I report counts only.
7. **Risk.** ohsome geometry output may not carry OSM node ids per vertex. If it does not, node identity has to come from the ohsome `/contributions` or `/elements` endpoints, or by matching the planner fixture lon/lat to 1e-6. This is tested in the tiny-bbox probe first.
8. **Artefacts.**
   - Raw extract: uncommitted (or a release asset), with its sha256 in `roads/MANIFEST.json`.
   - Derived graphs: committed only if under about 5 MB, otherwise a release asset.
   - Query, timestamp, ohsome metadata and code version go in the manifest.
   - Status: EQUIVALENT, not byte-identical.
   - Hannah verifies.
9. **Timing.** Nothing is fetched before the 00:12 UTC weather launch on 13 Nov.

## Contingency (orchestrator, 12 Nov 16:10Z; added before any OSM request)

The full-export-grid graph gates every multi-hour count, so the routing reviewer has raised its priority. The plan is unchanged: probe right after the 00:12 UTC weather launch, then step 1.

If ohsome cannot deliver the 2025-03-21T23:59:59Z snapshot with usable topology, the fallback is a CURRENT public extract: Geofabrik South Korea (`download.geofabrik.de`, ODbL). Both of these count as "cannot deliver":
- way node ids are unrecoverable, so step-1 criteria 1–2 cannot be met even by coordinate matching;
- the API refuses or truncates the export-grid + 5 km bbox.

Every result built from the fallback carries an explicit label in its provenance, its file names and every report:

`OSM CURRENT EXTRACT <Geofabrik file date>, NOT the 2025-03-21 snapshot: roads built or changed after the fire may be present`

It is never presented as the historical graph, and step 1 is then reported as "not comparable (date mismatch)".
