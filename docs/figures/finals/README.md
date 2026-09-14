# Finals figure set (2026-09-14)

Built by `paper/make_finals_figures.py` from committed artifacts only; PNG at 300 dpi and PDF vector. House style: `paper/style.py`. Captions live in the documents that cite them.

| file | what | artifact |
|---|---|---|
| F16_coverage | 124 OSM vs 19,959 address-register buildings; forecast-graded classes, sample vs census | juso manifest; building_origin_routing*.json |
| F12_observed_grading | three-way observed grading, 458 sample and 19,250 census, with the adjacent-cell sensitivity | regrade_three_way; building_origins_observed_grading |
| F13_diagnosis_intervention | flags on the 54 no-safe-route nodes; buildings completed by a vehicle vs fleet size | building_origins_observed_grading; vehicle_pickup_intervention |
| F14_last_safe_departure | cumulative latest-safe-departure by policy with the 5 h / 8 h doctrine lines; the 5-hour rule counts | last_safe_departure |
| F15_leakfree_fold | canonical vs leak-free forecast core vs FIRMS; 42 → 34 and 1,606 → 1,277 | leakfree_yeongdeok_fold |
