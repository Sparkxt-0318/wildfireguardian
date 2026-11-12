# Road-graph rebuild rule: Uiseong–Andong 2025 and Yeongdeok 2025 (DRAFT 1; extent to be filled in by Leo or Richard)

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

## Rule

1. **Source.** The ohsome API (api.ohsome.org, HeiGIT), endpoint `/v1/elements/geometry`:
   - `time=2025-03-21T23:59:59Z`;
   - `filter=type:way and highway in (<classes>)`;
   - `bbox=<extent>`;
   - `properties=tags,metadata`.

   Licence: OSM data under ODbL 1.0, "© OpenStreetMap contributors". The ohsome attribution and terms will be recorded from the API's own metadata response before use.
2. **Extent, per region: TBD.** It will be supplied by Leo or Richard, and must be wide enough that every exit road reaches outside the final burn set. It must also contain the current node bbox above.
3. **Highway classes kept.** Default, pending confirmation:
   - motorway, trunk, primary, secondary and tertiary, with their `_link` variants;
   - unclassified, residential, living_street and service.

   track and path are kept only if Leo or Richard say the owner's graph used them. The display roads include track, but that does not show that the graph uses it.
4. **Graph.** Built with osmnx (version pinned in the manifest), from the ohsome GeoJSON converted to nodes and edges with shared-vertex topology:
   - a vertex is a node if it is shared by two or more ways, or is a way endpoint;
   - edges are directed, following `oneway` tags;
   - `simplify=True`;
   - CRS EPSG:5179.
5. **375 m gridding: TBD.** The meaning of "G2window-grid375" is undocumented. My proposal is to record the 375 m grid of the region's fire window, aligned to the region's arrival raster from the archive's data/regions/<region>/, and to tag each node with its cell. Nodes are not snapped, because 23k and 56k nodes far exceed the number of 375 m cells in the window.
6. **Validation, inside the existing window (the node bbox above).**
   - node count against 23,158 and 56,369;
   - the share of "allowed" nodes;
   - road length by class against the display roads in `<region>.osm.js`.

   Pass criterion (proposed): node count within ±15%, and length per major class within ±10%. Byte identity is NOT claimed.
7. **Artefacts.**
   - the raw ohsome GeoJSON is uncommitted, or a release asset if large, with its sha256 in `roads/MANIFEST.json`;
   - the derived graph (GraphML or npz) is committed only if under about 5 MB;
   - the query, timestamp, ohsome metadata response and osmnx version all go in the manifest.
8. **Verification.** Hannah verifies.
