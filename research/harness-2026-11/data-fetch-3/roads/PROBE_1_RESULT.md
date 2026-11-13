# Roads probe 1 (13 Nov 2026, 00:26Z): BLOCKED

These were the only requests made: 2 to ohsome and 1 HEAD to Geofabrik. Nothing was retried, and nothing was worked around (no other method, header, host or mirror was tried).

| time (UTC) | request | result |
|---|---|---|
| 00:26:14 | `GET api.ohsome.org/v1/metadata` | 200, 532 B. apiVersion 1.10.4. Attribution "© OpenStreetMap contributors" (ohsome.org/copyrights). Temporal extent 2007-10-08 to 2026-07-27T09:00Z, so 2025-03-21 is covered. |
| 00:26:16 | `GET api.ohsome.org/v1/elements/geometry`, tiny bbox 128.700,36.350,128.705,36.355, time=2025-03-21T23:59:59Z, filter=`type:way and highway=*`, properties=tags,metadata | **403 Forbidden**, 280 B. Apache/2.4.58 page from the ohsome server itself, not the proxy. This matches the earlier geometry 403. |
| ~00:27 | `HEAD download.geofabrik.de/asia/south-korea-latest.osm.pbf` (the contingency) | **Connection reset by peer** after the proxy tunnel was established (proxy status: enabled, bundle covers every host). This matches the earlier reset. |

## Status

- Both the ohsome 2025-03-21 snapshot and the labelled Geofabrik current extract are unreachable from this environment.
- The node-id question (ROAD_RULE item 7) could not be tested.
- Step 1 (ACCEPTANCE_STEP1.md) and the export-grid + 5 km graph stay BLOCKED. The owner graphs remain the only road source, and their extent is the current windows.
- Unblocking needs an owner or orchestrator decision: for example, someone outside this environment supplies a pbf or ohsome GeoJSON for the bbox, by sha256, or another approved source is named.
