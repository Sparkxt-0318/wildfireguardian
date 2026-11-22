# ROAD_RULE addendum 1: the waitable rule

This addendum adds to ROAD_RULE.md (draft 2 at ff7b93af, contingency at 64404d63). It does not edit that file.

## Source

Thomas measured `node["waitable"]` on all 5 owner graphs. The orchestrator forwarded the result to me through Richard and Leo at 20:07 UTC on 12 Nov. On every graph, waitable is true exactly for the graph's dead ends: the nodes with one distinct neighbour. There are 0 exceptions.

No code or provenance states this rule. It is inferred from the data.

## Independent check

I checked this against the owner graphs (release research-final-20261015) with `check_waitable.py`. The output is in `CHECK_WAITABLE_OUTPUT.txt`.

| graph | waitable | dead-end | exact set match |
|---|---|---|---|
| hongseong_2023 | 39 | 39 | yes |
| miryang_2022 | 78 | 78 | yes |
| uljin_2022 | 337 | 337 | yes |
| yeongdeok_2025 | 1,527 | 1,527 | yes |
| uiseong_andong_2025 | 554 | 554 | yes |

These counts agree with Thomas's.

## Rule for the rebuild

The rebuild sets `waitable = (number of distinct neighbours == 1)`. This holds until the owner confirms the intended rule.

Step 1 (ACCEPTANCE_STEP1.md) adds one check. When the rebuild runs against the owner graphs, the waitable set must exactly match the shipped `graph.json` for each region, using the counts above.

## Required wording

Any table with NO_ROUTE, or with deadlines that depend on waiting, carries this wording:

> waiting is allowed only at graph dead-end nodes (as supplied in graph.json; rule undocumented)
