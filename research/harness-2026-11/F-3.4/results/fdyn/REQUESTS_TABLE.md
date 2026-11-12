# F-DYN 12 requests: inputs and outcomes (FDYN_PLAN.md)

Request JSONs are in requests/<tag>.json. They were built by fdyn_profile.py with api.requests_build.build_request:
departure 0, the first destination of each origin, limits 10 kW/m2 peak and 100 kJ/m2 dose, incurred dose 0,
destination window [0, H]. Packets are v3.1 (MANIFEST_v3_1.json sha 1c2e73db20db7b1caa309ebde42d20629054cd49c8f1f2cd9e4e81b0b9c89bbe, horizon 5 h).
Graphs are graphs_interim/<region>/graph.json.

| tag | packet (region/start/variant) | HAZARD sha256 | request sha256 | frozen kit 900 s / 3 GiB | A1: 300 s, solver and controller gates 12 GiB | A3b modified kit, 450 s |
|---|---|---|---|---|---|---|
| uiseong_andong_2025__20250325T170000Z_firms_early__osm_node_415158323 | uiseong_andong_2025/20250325T170000Z_h5_firms_early_central_q300 | 55426074f84088a1 | 290ab79a2c331281 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / LATE_RESULT | UNRESOLVED / LATE_RESULT |
| uiseong_andong_2025__20250325T170000Z_firms_early__osm_node_415158324 | uiseong_andong_2025/20250325T170000Z_h5_firms_early_central_q300 | 55426074f84088a1 | d184797f82678b09 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / LATE_RESULT | UNRESOLVED / LATE_RESULT |
| uiseong_andong_2025__20250325T170000Z_firms_early__osm_node_415158334 | uiseong_andong_2025/20250325T170000Z_h5_firms_early_central_q300 | 55426074f84088a1 | 9767952d0a06687c | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | AT_ISSUE_FAILURE / AT_ISSUE_FAILURE | - |
| uiseong_andong_2025__20250325T170000Z_kriged_mean__osm_node_415158323 | uiseong_andong_2025/20250325T170000Z_h5_kriged_mean_central_q300 | d63b01b28ccafc32 | 9ebbde02d598a868 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / LATE_RESULT | UNRESOLVED / LATE_RESULT |
| uiseong_andong_2025__20250325T170000Z_kriged_mean__osm_node_415158324 | uiseong_andong_2025/20250325T170000Z_h5_kriged_mean_central_q300 | d63b01b28ccafc32 | 58c2191c73a68039 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / LATE_RESULT | UNRESOLVED / LATE_RESULT |
| uiseong_andong_2025__20250325T170000Z_kriged_mean__osm_node_415158334 | uiseong_andong_2025/20250325T170000Z_h5_kriged_mean_central_q300 | d63b01b28ccafc32 | 90027cd562651828 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | AT_ISSUE_FAILURE / AT_ISSUE_FAILURE | - |
| yeongdeok_2025__20250325T230000Z_firms_early__osm_node_11753630207 | yeongdeok_2025/20250325T230000Z_h5_firms_early_central_q300 | 0c15bc3e1180efc8 | 66c0e95a702b90bb | CHECKED_JOURNEY_FEASIBLE /  @59 | CHECKED_JOURNEY_FEASIBLE /  @59 | - |
| yeongdeok_2025__20250325T230000Z_firms_early__osm_node_415158166 | yeongdeok_2025/20250325T230000Z_h5_firms_early_central_q300 | 0c15bc3e1180efc8 | 5adb620157c0916a | UNRESOLVED / LATE_RESULT | UNRESOLVED / SEARCH_TIMEOUT | CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN /  @3953 |
| yeongdeok_2025__20250325T230000Z_firms_early__osm_node_415158168 | yeongdeok_2025/20250325T230000Z_h5_firms_early_central_q300 | 0c15bc3e1180efc8 | d0ed9094b7ae38fd | CHECKED_JOURNEY_FEASIBLE /  @274 | CHECKED_JOURNEY_FEASIBLE /  @274 | CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN /  @274 |
| yeongdeok_2025__20250325T230000Z_kriged_mean__osm_node_11753630207 | yeongdeok_2025/20250325T230000Z_h5_kriged_mean_central_q300 | cf4f134b8bba520a | 221c9bd2a55b95ef | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / SEARCH_TIMEOUT | CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN /  @59 |
| yeongdeok_2025__20250325T230000Z_kriged_mean__osm_node_415158166 | yeongdeok_2025/20250325T230000Z_h5_kriged_mean_central_q300 | cf4f134b8bba520a | a4a7dd444d2a7774 | UNRESOLVED / STALE_OR_IDENTITY_MISMATCH | UNRESOLVED / SEARCH_TIMEOUT | CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN /  @3953 |
| yeongdeok_2025__20250325T230000Z_kriged_mean__osm_node_415158168 | yeongdeok_2025/20250325T230000Z_h5_kriged_mean_central_q300 | cf4f134b8bba520a | 4b6c17bf13874904 | UNRESOLVED / LATE_RESULT | UNRESOLVED / SEARCH_TIMEOUT | CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN /  @274 |
