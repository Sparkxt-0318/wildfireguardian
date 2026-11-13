# ROAD_RULE addendum 2: owner-supplied OSM extract; step-1 rule for this source

Written 2026-11-13 at about 02:35Z, after the file was downloaded and hashed, and BEFORE any graph was built from it. It adds to ROAD_RULE.md (ff7b93af, contingency 64404d63), ACCEPTANCE_STEP1.md (d5ec4886) and addendum 1 (94920e4d). None of those files is edited. Any later change goes in a new file.

Label for every result built from this source:

> **roads as of 2025-01-01 (before the March 2025 fires)**

## 1. Source and provenance

The orchestrator unblocked roads at 02:19Z on 13 Nov. ohsome geometry had returned 403 and Geofabrik had reset the connection (PROBE_1_RESULT.md). The owner then supplied a Geofabrik extract on a private Drive link. The link and its id are not recorded in any repository file. The download passed the id to curl through an environment variable.

| item | value |
|---|---|
| file | `south-korea-250101.osm.pbf` (owner-supplied copy) |
| size | 233,753,476 bytes, equal to the size the orchestrator stated |
| sha256 | `9b67fc951d535639b2a12e96a0ff069943d6da4d75883e42d377e6f76c7483ab` |
| downloaded | 2026-11-13T02:19:38Z–02:19:44Z, HTTP 200, into its own new empty directory outside the repository |
| `file(1)` | OpenStreetMap Protocolbuffer Binary Format |
| header `generator` | osmium/1.14.0 |
| header `osmosis_replication_timestamp` | 2025-01-01T21:21:00Z |
| header `osmosis_replication_sequence_number` | 3813 |
| header `osmosis_replication_base_url` | https://download.geofabrik.de/asia/south-korea-updates |
| header bbox | lon 124.31880–132.33860, lat 32.36076–38.64966 |

The header was read with pyosmium (`osmium.io.Reader`, header only, no entities) under `python -I` from a separate scripts directory.

**Integrity limit, stated plainly.** This is the owner's copy. We could NOT compare it with Geofabrik's published checksum, because download.geofabrik.de is unreachable from this container (probe 1). The header is consistent with a Geofabrik daily extract of 1 Jan 2025. That consistency is not proof of byte identity with Geofabrik's file. Hannah verifies provenance.

Licence: ODbL 1.0, "© OpenStreetMap contributors". The pbf is not committed.

## 2. What changes against the original rule

- **Source.** This file replaces the ohsome 2025-03-21T23:59:59Z snapshot. Node and way ids are native to the pbf, so the coordinate-matching risk in ACCEPTANCE_STEP1.md does not arise.
- **Snapshot date.** The source is dated 2025-01-01T21:21:00Z. The owner graphs are dated 2025-03-21T23:59:59Z, 79 days later. OSM edits in that gap appear as differences that are not recipe errors. The label in the contingency of ROAD_RULE.md ("OSM CURRENT EXTRACT …") does NOT apply, because this is a historical extract from before the fires. The label above applies.

## 3. Step 1 (the CURRENT windows) for this source

The reference, recipe and pass criteria 1–6 of ACCEPTANCE_STEP1.md apply UNCHANGED. Addendum 1 replaces criterion 7: waitable is re-derived as "exactly 1 distinct neighbour" and must equal the shipped set. The highway class set is still read empirically, from the pbf tags of the owner's own source_way ids. Exclusions are applied as in the owner's provenance.

Because of the date gap, a strict pass is not expected. The report therefore has three parts. They are fixed now, before any build.

**A. Strict result.** Criteria 1–6 and the waitable check, per region, exactly as written: PASS or the list of differences.

**B. Recipe-exactness test on unchanged ways.** This is the test that decides whether the recipe is reproduced. A way is UNCHANGED if both of these hold:
- it is a source_way of the owner graph and is present in the pbf;
- the owner graph's node sequence for that way (from u/v of its edges in k order) equals the pbf way's node subsequence inside the window.

For every unchanged way, its edges must match exactly on:
- id, u and v;
- travel_ticks;
- segments (fractions within 1e-9);
- direction_evidence;
- node x/y within 0.01 m.

**Pass rule B:** 100% of edges on unchanged ways match. Any mismatch is a recipe error and is reported with its ids.

**C. Attribution of the remaining differences.** Every difference not covered by B is counted in exactly one category, with example ids:
- **C1, created after the snapshot:** an owner node or way id greater than the largest node or way id in the pbf. The cause is date, not recipe.
- **C2, changed between the dates:** a way present in both, whose node sequence differs. The cause is not verifiable here.
- **C3, in the rebuild only:** an id that the rebuild emits and the owner graph lacks. Possible causes: deletion or retagging after 1 Jan 2025, or an exclusion I do not reproduce. The tags of each such way are listed.
- **C4, unexplained:** anything else. Each C4 item is listed individually.

**forbidden_turns.** The U-turn subset is checked inside B for unchanged dead ends. The other pairs (30 UA, 9 YD) are compared with the pbf's turn-restriction relations and reported as matched, unmatched, or absent from the pbf.

**Summary line per region:** "strict: PASS/FAIL; recipe on unchanged ways: PASS/FAIL (n ways, m edges); date-attributed C1/C2: …; C3: …; C4: …".

The widened build does not start until this report is out.

## 4. Then: export grid + 5 km

The step-2 extent is the KFS_01 export grid (EPSG:5179, x 1,085,250–1,174,125, y 1,815,750–1,845,375) plus a 5 km margin. The graph uses the same recipe and the same class set. Its acceptance is criterion 6 of ROAD_RULE.md: inside each current window, the widened graph equals the step-1 graph. Outside the windows, counts only are reported.

The padding/contract question raised by Leo is NOT decided here. The 5 km graph is built as an input; how it is used is the orchestrator's call.

## 5. Artefacts and verification

- The pbf and any extract of it stay uncommitted, in scratch. Their sha256 values go in `roads/MANIFEST.json`.
- Derived graphs are committed only if under about 5 MB. Otherwise they stay in scratch, with their sha256 recorded.
- Before extracting anything, I check disk space. The part-a environment and the day-2 inputs must not be put at risk (7.1 GB free at 02:19Z).
- **Verifiers:** Hannah for provenance; Nora for the graph reproduction.
