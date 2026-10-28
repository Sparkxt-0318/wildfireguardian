# Experimental graph preparation and cache measurements

This note describes two **fixed offline research comparisons**, not an operational wildfire benchmark. They evaluated an isolated candidate and did not change the frozen routing release. See the [experimental routing-preparation package](../../../experimental/routing-preparation/) for implementation, setup and usage. The figures below measured the earlier research candidate; the repository packaging and any subsequent refactoring have not been benchmarked by those runs. The prepared graph is an opt-in implementation technique: hazard and request inputs still have to be validated for each routing request. These results do not establish forecast accuracy, physical safety, or a general end-to-end speedup.

## Native graph preparation

The October 2026 matched campaign compared the existing fast A4 implementation with the experimental per-instance native preparation candidate, using cold application-level preparation in both arms. The frozen panel had 20 missions, two repetitions and two implementations: **80 executions and 40 matched pairs**. A 30-second request limit and a 3,072 MiB sampled process-family memory guard applied. Operating-system page caches were not flushed.

| Measurement | Baseline median | Candidate median | Median paired candidate/baseline |
|---|---:|---:|---:|
| Graph constructor, 40 pairs | 0.309 s | 0.201 s | 0.6224 (37.76% lower); candidate faster in 40/40 pairs |
| Complete request, 30 pairs with checked routes in both arms | 7.328 s | 7.074 s | 0.9838; candidate faster in 24 and slower in six pairs |

Each arm produced 15 checked-route missions and five model-scoped no-route decisions in both repetitions. All 30 matched route-execution pairs agreed on route and arrival, and their published scenario exposure values matched. The independently graded contexts were deduplicated: matching input/witness and refusal contexts were checked once and reused across repetitions. Independent checks covered route grammar, centre feasibility and whole-road contact; whole-road thermal radiation used the project's checker, whose numerical enclosure has not been independently proved.

## Authenticated disk cache on repeated requests

A second campaign compared the **same native candidate** with cold preparation against an authenticated disk-cache path. It used five regional graphs and four chronological historical mission records per graph, repeated twice: **40 pairs / 80 executions**. Two regional panels share the 2025 Gyeongbuk parent incident; repetitions and missions are not independent fires. These are historical input replays, not live forecast updates or repeated replans of one vehicle.

Each of ten four-request streams started with a cache miss and build, followed by three authenticated hits. Of the 30 hit pairs, 20 followed a changed hazard input and ten were new missions under the same hazard. The hazard and request were freshly processed for each call, and both arms used separate fresh worker processes with the same constraints and native package.

| Measurement | Pairs | Cold median | Cached median | Median paired cached/cold |
|---|---:|---:|---:|---:|
| Preparation wrapper on hit | 30 | 0.200 s | 0.100 s | 0.5188 (48.12% lower); cached faster in 30/30 pairs |
| Complete request on hit | 30 | 6.152 s | 6.026 s | 0.9671; cached faster in 24, cold faster in six |
| Complete request on initial build | 10 | 7.000 s | 7.157 s | 1.0267; cached faster in two, cold faster in eight |

The preparation wrapper includes source identity checks and, as applicable, graph construction, authenticated cache construction or authenticated restoration. Complete request is launch through worker exit, including graph preparation, request/hazard validation, search and publication; external forecasting and offline checks are excluded.

Summing all four complete-request times per stream, including the initial build, produced cold and cached medians of **24.190 s and 23.820 s** across ten streams. The median paired cached/cold ratio was **0.9946**, with the cached sum lower in eight streams and higher in two. These are sums of request wall times, not continuous session measurements; inter-request gaps, external forecast generation and common cache-root setup/cleanup were excluded. The data show a preparation-stage benefit here; they do not demonstrate a general request-time benefit.

All 40 pairs reproduced the applicable previously checked input/witness/refusal contexts and matched graph fingerprints and route, arrival and published per-member exposure where applicable. This benchmark reused matching earlier checks; it did not rerun the independent checkers. Cache artifacts were 602,606–37,381,630 bytes across the five graphs, excluding key, lock and filesystem overhead. The private cache stores were removed after the runs. Owner authentication is not protection against an attacker with access to the same user's key.

## Numerical evidence and recomputation

`native_cold_pairs.csv` and `warm_cache_pairs.csv` are path-free exports of the paired records used for the tables. `python3 recompute.py` recomputes the descriptive medians and median *paired ratios* from those records using the Python standard library. Column medians are calculated independently; a median paired ratio is not the ratio of the displayed medians. The CSVs are curated measurement exports, not the original graphs, hazard packets, route witnesses, full execution logs or checker reruns. This repository material alone cannot recreate the experiment or independently establish the underlying route results.

The complete local research evidence archives were independently checked by SHA-256 at packaging:

- Native-preparation campaign: `24b0f70e7c107beaf73643953a3d4095e63856dd25067bfc929139499c95c19f`.
- Repeated-request cache campaign: `5a0d0266a7ae9d76f82b374e95bb25bd0e8d803dd362da05be867cd41580a398`.

The archives reference their original source inputs and interpreter by host paths and are not self-contained distributions. They are not included in these CSVs. No private owner keys or cached graph artifacts are published here.
