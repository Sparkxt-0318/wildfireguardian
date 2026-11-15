# Recovering forecast coverage on the frozen 273-case routing cohort

This experiment asks whether additional historical observations can support routes whose endpoints or intervening roads were previously missing forecast input. The reference is the preceding strict-support campaign on the same 273 requests. A supported journey has a finite native forecast in every occupied grid cell and hour for all four scenarios and passes the model's flame and heat checks. A model-scoped refusal has a proof under its configured scenario. An unresolved result has neither a checked journey nor such a proof.

## What changed in the input

The forecast grid uses 375 m cells. The c651 model needs the surrounding 9-by-9 patch to forecast new burning. Some road-grid cells previously fell near the edge of the model input, even though satellite imagery extended farther. The reconstruction supplies up to four additional cells of actual surrounding satellite, terrain, vegetation and weather input for forecasting, then crops back to the original road grid.

Two supplemental observation rules were fixed before the routing run. For Uljin, two additional pre-fire reference dates at the same time of day help interpret contemporary thermal scans when the original reference was cloudy. For Caldor, the other GOES satellite can supply qualifying evidence for locations left unknown by the primary view. The original observation rules and the supplemental rules have separate provenance. Both yield retrospective, sensor-conditioned forecasts. A clear classification can miss a real fire. Each cell's four scenario draws retain their original random stream.

## Measured outcome

| Independently checked outcome | Prior inputs | Recovered inputs |
|---|---:|---:|
| Supported route | 28 | 35 |
| Proven no route under the configured model | 78 | 114 |
| Unresolved | 167 | 124 |
| Earliest arrival proved among supported journeys | 26 | 33 |
| Minimum driving proved at the returned arrival | 23 | 30 |

Of the **153** cases whose original route had missing data at its origin or destination, **11** recovered support at both endpoints, **17** gained some endpoint coverage and still had a gap, and **125** gained no fully supported endpoint cells. Across those same 153 cases, **7** returned a fully checked route, **32** proved no route within the model, and **114** remained unresolved. The recovered cells account for 30 of 269 previously missing endpoint-cell visits. Several requests share a cell.

| Forecast support at the two endpoints | Cases | Checked route | Model no-route proof | Unresolved |
|---|---:|---:|---:|---:|
| Both endpoints supported | 11 | 7 | 1 | 3 |
| Some previously missing cells recovered, gaps remain | 17 | 0 | 8 | 9 |
| No additional endpoint cells fully supported | 125 | 0 | 23 | 102 |

Across all 273 cases, **43 previously unresolved requests received a decision**. Seven gained a checked route and 36 gained a model-scoped no-route proof. All 28 previous routes kept the same arrival and driving times, and all 78 previous no-route decisions were independently reconfirmed. The seven new routes comprised five in Miryang, one in Uljin and one in Yeongdeok. Every published route passed the independent model and cell-coverage checks. A missing endpoint alone cannot prove no route. A refusal requires an independent proof that a configured constraint already rules out all journeys, even when the search is allowed to traverse cells missing forecast input. All 124 unresolved cases ended without a checked route in the supported area.

Native coverage rose from 36,095 to **40,537 of 53,679** road-grid cell-hours. The gains came from 1,609 Korean cell-hours and 2,833 Caldor cell-hours. The complete audit found the same probabilities and scenario ignition draws on every previously supported cell. Sixteen of 18 forecast windows changed, covering 241 requests; 32 requests used their original packets.

The 273 executions produced 0 resource-guard stops. The maximum recorded worker time was 28.198 s, the largest sampled memory was 1,339.766 MiB, and the largest adapter-plus-supervisor time was 28.281 s. The worker guard was set to 30 s and the sampled memory guard to 3,072 MiB. Independent reconstruction recorded 0 discrepancies.

## Audit and reproduction

[All 273 decisions and resource readings](receipts.csv) · [Per-case changes](case_changes.csv) · [Endpoint and outcome comparisons](transitions.json) · [Per-packet forecast coverage](packet_coverage.csv) · [Route and optimality checks](proofs.json) · [Resource clocks](clocks.json) · [Raw satellite source identities](source_catalog_public.json) · [Flame and radiation replay](hazard_replay.json) · [Frozen identities](study_identity.json).

The recorded cohort uses retrospective reconstructions from five fires. The route-support check covers the actual movement, waiting and destination occupancy. Unobserved off-route heat sources and conditions in the field remain outside its scope. Powered-on timing includes the complete routing worker with a private authenticated warm graph cache and a sampled process-family-plus-controller memory guard. Earlier forecast generation and private cache copying are outside this timer.

The public receipts can be checked with `python experimental/forecast-input-recovery/verify_ledger.py` from the repository root. Given full local forecast packets, `python experimental/forecast-input-recovery/check_hazard_packets.py PACKET_DIR [PACKET_DIR ...]` independently recomputes the flame and radiation fields. It uses direct superposition and the rectangular solid-angle formula at every receiver cell and event interval. Full private benchmark inputs and the host timing environment are required to reproduce the mission rerun.

The [frozen routing protocol](routing_protocol.md), [Korean observation rule](korean_protocol.md), [Caldor observation rule](caldor_protocol.md), [per-source accounting](source_attribution.json) and [independently recomputed source values](independent_source_checks.json) document why a cell qualified for a new forecast. [Terrain source cross-check](terrain_window_crosscheck.json) compares the downloaded subsets with the full original terrain tiles. [Packet audit](packet_review.json) binds the original and revised forecast exports and hazard arrays. The radiation replay reproduces the packet’s declared initial-source duration convention and heat law.

Uljin accounted for 122 of the 153 priority cases. After recovery, 119 still had a missing endpoint. In that group, 117 lacked a fire-state observation somewhere in the model’s nine-by-nine input neighborhood, 54 lacked an environmental input there, and 52 had both gaps. [Uljin residual causes and counting method](uljin_residual.json)
