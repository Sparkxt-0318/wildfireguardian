# Fixed known-footprint contact K study

320 records, 160 paired comparisons, 72 independently rechecked local contact routes and 224 presearch unknown-endpoint records. Source phase `095b8d174d2f203ea67bea5fdd8c69eb0633b2a0`. Seed 20261008, uniform full-native timing then exact existing crop, original first-K 4/8/16/32, T = 3970.4642815249267 s and H = 3600 s. Original graph/request/export/record/masks and issued history are unchanged.

Host: macOS-27.0.1-arm64-arm-64bit. Python: 3.12.1 (v3.12.1:2305ca5144, Dec  7 2023, 17:23:38) [Clang 13.0.0 (clang-1300.0.29.30)]. NumPy: 1.26.4. Protocol SHA-256: `f3ba08b82410f6ff477220f99af403c7abaaf497b6508668b6b6b9d9c561f844`. BUNDLE.json retains all exact source, evidence and original input hashes. Original-input admission and controller fixture receipts are kept with this run or the adjacent protocol.

Commands from repository root:

```sh
python research/sipp-routing/run_known_footprint_campaign.py --preflight FRESH_PREFLIGHT.json
python research/sipp-routing/run_known_footprint_campaign.py --run FRESH_RUN --preflight-receipt FRESH_PREFLIGHT.json
python research/sipp-routing/analyze_known_footprint_campaign.py --run FRESH_RUN
```

Each mission/K uses ABBA: rep1 sweep,SIPP; rep2 SIPP,sweep. Every child acquires and releases HEAVY separately. The 30 s/3072 MiB guards include imports, admission, planning and a fresh original-data postcheck. Sampled RSS and final elapsed/self-reported peak admission are control evidence, not an instantaneous OS memory cap. Control refusals: {}. All owned process groups absent: True.

| Paired outcome | Count |
|---|---:|
| BOTH_PRESEARCH_UNSUPPORTED_ENDPOINTS | 112 |
| MATCHED_CHECKED_CONTACT_ARRIVAL | 36 |
| MATCHED_RESTRICTED_EXHAUSTION | 12 |

The six spatially supported missions have these outcomes. Numbers are arrival seconds and agree across both methods/repetitions when present. Restricted exhaustion is unresolved about the original unknown domain.

| Mission | K4 | K8 | K16 | K32 |
|---|---:|---:|---:|---:|
| 20250323T010000Z_FX2 | 2646 | 2646 | 2731 | restricted exhaustion |
| 20220304T060000Z_FL1 | restricted exhaustion | restricted exhaustion | restricted exhaustion | restricted exhaustion |
| 20250324T090000Z_FL2 | 1616 | 1616 | 1616 | 1616 |
| 20250325T230000Z_FL2 | 1922 | 1922 | 1922 | 1922 |
| 20220304T120000Z_FW2 | 1655 | 1655 | 1655 | restricted exhaustion |
| 20250325T170000Z_FW1 | 1064 | 1064 | 1064 | 1064 |

There are 48 joint completed-search pairs, including matched contact arrivals and matched restricted exhaustion. Their median SIPP/sweep contact-planner time ratio is 0.561111; the complete-child ratio is 0.671574. SIPP is slower in 0 contact-planner pairs. These host-specific ratios exclude presearch endpoint admission and are descriptive paired measurements, not a universal speedup. Repetitions are verification repeats, not independent missions or fires.

Figure 1, fig01_contact_K_time_paired, compares sweep and SIPP seconds for joint completed-search pairs. The left panel is the contact planner call including support/geometry preparation; the right is the complete child including imports, original-source admission and the separate original-data recheck when a route is returned. Unknown-endpoint admission records are excluded from both comparisons; the diagonal is equal time.

Figure 2, fig02_states_vs_members, reports SIPP expansions and sweep states reached in separate panels because their work units differ. Vertical axes are logarithmic to keep each mission's count range visible. Solid circles are repetition 1 and dotted crosses repetition 2. The original one-hour T>H law combines prefix and tail barriers, so increasing multi-interval fragmentation is not implied by adding members. The plot reports the observed counters; repetition-counter mismatches are 0. Missing or capped rows are never inserted as zero states.

Figure 3, fig03_contact_K_outcomes, retains all execution records at each K, including the original 14 unknown-endpoint missions, both methods and both repetitions. Counts are execution bookkeeping, not independent fire samples or estimated risk. The CSV ledger retains every unresolved outcome.

INDEPENDENT_RECHECKS.jsonl saves each fresh original-array/mask/geometry check separately from planner claims. Every returned contact route passed through full dwell inside finite source validity. The controller retained original request UTF8 and history; the private contact relaxation omitted thermal fields explicitly without rebinding them. Source and protocol pins match after the run. Peak, dose, full-policy acceptance and risk remain unknown. Restricted failure is unresolved about the original unknown domain; a returned optimum is conditional on the support-restricted contact problem. No physical safety, global original-domain optimum/refusal or scientific risk conclusion follows.
