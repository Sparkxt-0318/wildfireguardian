# Roads step 1 (the CURRENT windows): result

Built 13 Nov 2026, 02:23–02:31Z, from the owner-supplied pbf. The rule was committed first, at e358b679 (ROAD_RULE_ADDENDUM_2_owner_pbf.md).

> **roads as of 2025-01-01 (before the March 2025 fires)**

The owner graphs are dated 2025-03-21T23:59:59Z, 79 days later.

**Verifiers:** Hannah for provenance; Nora for the graph reproduction.

**Erratum to addendum 2.** Its header says it was written "at about 02:35Z". It was committed at 02:21:06Z. In both cases it was before any build: the first graph was built at 02:24Z. The file is not edited.

## Summary

| region | strict (A) | recipe on unchanged ways (B) | C1 created after 1 Jan | C2 changed between dates | C3 rebuild-only ways | C4 |
|---|---|---|---|---|---|---|
| uiseong_andong_2025 | FAIL | FAIL by the letter (1,984 ways, 40,916 edges): see B | 676 | 2,260 | 581 (19 ways) | 2 |
| yeongdeok_2025 | FAIL | FAIL by the letter (3,738 ways, 105,215 edges): see B | 1,444 | 4,173 | 34 (1 way) | 0 |

The strict failure was expected, because the snapshot is older. Part B is the test of the recipe. It fails as written, and the cause is below.

## B. Recipe on unchanged ways

An unchanged way has the same in-window node sequence in the pbf as in the owner graph. UA has 1,984 of 2,065 owner source ways; YD has 3,738 of 3,849. Results:

- **Edge identity: EXACT.** Every one of the 40,916 (UA) and 105,215 (YD) edges on unchanged ways has the same id, u, v, direction_evidence and reverse_edge. There are 0 missing and 0 extra edges.
- **forbidden_turns on unchanged ways: EXACT.** All U-turn pairs match: 36,934 of 36,934 (UA) and 100,441 of 100,441 (YD).
- **Node coordinates.** Of the common nodes (22,921 UA, 56,259 YD), all but 655 (UA) and 233 (YD) agree within **1.9e-9 m**. The others differ by 0.34–23.1 m (median 7.5 m UA, 4.4 m YD). Those are mapped positions edited between the two dates. Re-projection does not produce offsets like these. In B, 203 (UA) and 214 (YD) of those moved nodes lie on unchanged ways.
- **travel_ticks / segments.** 68 (UA) and 72 (YD) edges differ. All of them except one UA pair have an endpoint that moved (diagnosis in `step1/STEP1_DIAG.txt`).
- **The one UA pair** is `w986625602:s11:f/r`. Its ticks are equal (3), and its endpoints agree within 3e-10 m. Its cell-crossing fraction differs by **1.016e-9**, just above the pre-registered 1e-9 tolerance. The chord runs nearly parallel to the crossed grid line (dy = 0.18 m over 23 m), so the fraction is ill-conditioned. This is a numerical tolerance miss, not a recipe difference. It is still reported as a failure, because that is what the rule says.

**Reading.** The recipe (node selection, edge ids with full-way k, direction rules, 40 km/h ceil ticks, 375 m segments, the dead-end U-turn rule) reproduces the owner graph exactly wherever the OSM data is the same. Every B difference traces to node positions that changed in OSM between 1 Jan and 21 Mar 2025, except the 1.0e-9 numerical case above. B therefore FAILS as written. I report it, I do not re-grade it, and I do not change the tolerance.

## C. Differences outside B

- **C1.** An owner way or node id exceeds the pbf maximum (way 1,347,834,848; node 12,467,520,948). It was created after 1 Jan 2025.
  - UA: 413 edges, 235 nodes and 28 moved nodes.
  - YD: 1,333 edges, 110 nodes and 1 moved node.
- **C2.** The way exists in both, but its node sequence differs, or it is absent from the pbf as a highway. Both counts are date-attributable, but the causes cannot be verified here.
  - UA: 37 changed and 44 absent source ways.
  - YD: 44 changed and 67 absent.
- **C3.** Ways that only the rebuild emits.
  - UA: 19 ways, 17 of them `highway=service` with no service or access tag, and 2 `primary_link`.
  - YD: 1 way, a `secondary`.
  - These are consistent with deletion or retagging after 1 Jan. They may instead be an exclusion I do not reproduce. That cannot be separated here, and the tags are listed in `step1/STEP1_COMPARE.txt`.
- **C4.** UA has 2 items: nodes `osm:6602598067` (moved 3.79 m) and `osm:6602597991` (moved 1.57 m). Both are moved nodes. They land in C4 only because each also lies on a C3 way. YD has 0.
- **waitable** (strict check against the shipped set): UA owner 554, rebuild 565; YD owner 1,527, rebuild 1,524. The differences sit on C1, C2 and C3 ways. On unchanged ways the dead-end rule (addendum 1) is consistent, because the forbidden-turn U-turn subset, which is derived from the same dead-end set, matches exactly.
- **Non-U forbidden turns.**
  - YD: 9 of 9 match pbf restriction relations.
  - UA: 19 of 30 match. 10 of the 11 owner-only pairs involve a way created after 1 Jan (C1). The 11th, `(w531647788:s19:f, w480917267:s0:f)`, has no restriction relation in the pbf. w480917267 is a C2 changed way.

## Step 2 rule: export grid + 5 km (fixed here, before that build)

**Grid.** The margin is 14 cells (5,250 m), not exactly 5 km, so that the grid stays on the 375 m KFS_01 lattice; 5 km is not a multiple of 375 m.
- EPSG:5179, x0 = 1,080,000, y0 = 1,810,500.
- 265 × 107 cells of 375 m: x 1,080,000–1,179,375 and y 1,810,500–1,850,625.

**Same recipe, same class set.** Same pbf extract (area_grid5km.json covers it).

**Acceptance (criterion 6 of ROAD_RULE.md).** Inside each current window, take the widened graph's edges whose two endpoints both lie inside the window. They must equal the step-1 graph's edges on all of these:
- id, u, v, travel_ticks, direction_evidence;
- segments, with cells mapped to absolute (col, row) on the shared lattice and fractions within 1e-9.

Node x/y must be identical. reverse_edge is checked only for edges whose reverse also lies inside the window. waitable and forbidden_turns differ by construction at the window boundary, because a dead end at the window edge may connect outside it. They are reported as counts, not tested.

Outside the windows, counts only.

## Files

The step-1 graphs are 15.6 MB and 40.4 MB, above the 5 MB commit limit. They stay in scratch; their sha256 values are in `MANIFEST.json`. In `step1/`:
- `pbf_header.py`, `extract_area.py`, `build_graph.py`, `compare_step1.py`, `diag_b.py`;
- `STEP1_COMPARE.txt` (output of the rule's A/B/C);
- `STEP1_DIAG.txt` (post-hoc diagnosis of B, not part of the pass rule).

Environment: pyosmium 4.3.2, pyproj 3.8.0, scripts run with `python -I` from a scripts directory separate from the data.
