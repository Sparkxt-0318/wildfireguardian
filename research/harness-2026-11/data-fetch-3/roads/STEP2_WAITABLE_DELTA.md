# Waitable set per current window: step 1 vs widened graph (requested by Leo, 13 Nov 02:35Z)

`STEP2_WAITABLE_DELTA.json` lists the node ids by OSM node id. It was computed with `step1/waitable_delta.py`. Both graphs use the dead-end rule from addendum 1: a node is waitable when it has exactly one distinct neighbour.

Here, "in window" means every widened-graph node whose x/y lies inside the window's half-open bounds.

| window | step-1 waitable | widened waitable in window | unchanged | removed | added |
|---|---|---|---|---|---|
| uiseong_andong_2025 | 565 | 479 | 478 | 87 | 1 |
| yeongdeok_2025 | 1,524 | 1,456 | 1,454 | 70 | 2 |

**Removed.** These step-1 dead ends at the window edge now connect outward.

**Added.** All 3 added nodes (`osm:11633929719` in UA; `osm:1868088706` and `osm:9140938586` in YD) are absent from the step-1 graph. Each lies inside the window, but its only road edge crosses the window boundary. Step 1 drops such edges, so the node does not appear there; the widened graph keeps the edge. As a result the widened graph has 2 more in-window nodes than step 1 in each window (UA 23,128 vs 23,126; YD 56,304 vs 56,302).

**Correction to STEP2_RESULT.md.** It gives "478 / 1,454" as the in-window waitable counts. Those counts covered only nodes on edges with both ends inside the window. Counting every in-window node, the figures are 479 and 1,456. The step-2 PASS is unaffected: its test covers edges with both ends inside, and those are unchanged.
