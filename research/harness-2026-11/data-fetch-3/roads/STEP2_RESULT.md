# Roads step 2: KFS_01 export grid + 5 km. Result: PASS

> **roads as of 2025-01-01 (before the March 2025 fires)**

Built 2026-11-13 at 02:28Z with the same `build_graph.py`, class set and exclusions as step 1. The rule was fixed in STEP1_RESULT.md (27c5fe80) before this build.

## Grid

The KFS_01 export grid (x 1,085,250–1,174,125, y 1,815,750–1,845,375) is padded by 14 cells, or 5,250 m. The extra 250 m beyond 5 km keeps the grid on the 375 m lattice.

| item | value |
|---|---|
| CRS | EPSG:5179 |
| origin | x0 1,080,000, y0 1,810,500 |
| cells | 265 × 107, 375 m each |
| extent | x 1,080,000–1,179,375, y 1,810,500–1,850,625 |

The densified grid outline lies inside the lon/lat box of the extract, so no node is cut off at the grid edge.

## Graph (`kfs01_grid5km.json`, 132.7 MB, not committed; sha256 2232df00… in MANIFEST.json)

| item | value |
|---|---|
| nodes | 185,747 (106,315 outside both current windows) |
| edges | 367,094 |
| forbidden_turns | 347,783 |
| waitable (dead ends) | 4,494 |
| distinct ways | 14,386 |
| direction evidence | 341,946 missing → two-way · 14,842 explicit one-way · 10,198 explicit two-way · 108 motorway implicit one-way |
| restriction relations | 121 used, 38 skipped (outside the grid, or not single from–via–to) |
| excluded ways | 0 (none in the class set carries private/no access or a `:conditional` key) |

## Check (criterion 6 of ROAD_RULE.md, `step1/compare_step2.py`, output `step1/STEP2_COMPARE.txt`)

| window | step-1 edges | widened edges with both ends in the window | missing | extra | field or segment differences | node x/y differences | result |
|---|---|---|---|---|---|---|---|
| uiseong_andong_2025 | 43,801 | 43,801 | 0 | 0 | 0 | 0 | PASS |
| yeongdeok_2025 | 111,814 | 111,814 | 0 | 0 | 0 | 0 | PASS |

Segments were compared after mapping cells to absolute (col, row), with fractions within 1e-9. Node x/y are bit-identical.

waitable is reported only, as the rule states. The counts inside the windows fall from 565 to 478 (UA) and from 1,524 to 1,454 (YD), because dead ends at a window edge connect outward in the wider graph.

## Not decided here

Using this graph for the hazard/route contract means padding the hazard grid, which Leo has flagged. That is the orchestrator's call. The graph is built as an input only.

The snapshot is 79 days older than the owner graphs. Step 1 lists every difference (C1/C2/C3).

## Correction to STEP1_RESULT.md

Its header says the step-1 graphs were "built 02:23–02:31Z". In fact the extract was made at 02:23Z, both graphs were built at 02:24Z, and the comparison ran by 02:26Z. The file is not edited.
