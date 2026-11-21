### Step 1: burn-out time from the Camp Fire workbook (per road cell, minutes after first fire evidence)

| quantity | cells | min | p25 | median | p75 | p80 | p90 | p95 | max |
|---|---|---|---|---|---|---|---|---|---|
| last blocked report (all cells with one) | 108 | 0.0 | 0.0 | 49.0 | 146.5 | 192.6 | 270.6 | 402.5 | 700.0 |
| last blocked report, blocked again after first fire (**sets τ**) | 75 | 3.0 | 40.5 | 91.0 | 201.0 | 228.2 | 347.2 | 465.0 | 700.0 |
| first passable or vehicle-present after first fire | 131 | 1.0 | 30.0 | 81.0 | 200.5 | 252.0 | 415.0 | 509.0 | 786.0 |
| same, cells with a passable report | 15 | 1.0 | 25.5 | 55.0 | 121.5 | 161.8 | 250.8 | 284.4 | 360.0 |
| first passable or vehicle-present after the last blocked report | 37 | 1.0 | 63.0 | 125.0 | 237.0 | 247.0 | 376.4 | 438.8 | 505.0 |

Frozen (PROTOCOL §2.2): **τ = 240 min**, low 105, high 465 (n = 75 cells). Cross-fit halves: west 240, east 225 min. Cells with both a last blocked report and later open evidence: 37; the open evidence came before 240 min in 29 of them, the bracket contains 240 in 6, lies above it in 2.

### Test 4.1: the two documented movements (2 h horizon, dwell 120 s)

| movement, issue | variant | rule | road cells closed / reopening within 2 h / burned over at issue | origin closed (s after issue) | feasible at issue | departures feasible (s) | route at issue: share on documented roads (incl. OSM 'New Skyway') | pass |
|---|---|---|---|---|---|---|---|---|
| (a) 12:00 | no margin | permanent (kcf-camp) | 165 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | no margin | window, τ 105 | 165 / 50 / 115 | 0–2819 | **no** | 2820–6952 | — | FAIL |
| (a) 12:00 | no margin | **window, τ 240 (frozen)** | 165 / 85 / 27 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | no margin | window, τ 465 | 165 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | no margin | residents, confirmed only, τ 240 | 165 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | no margin | window τ 240, neighbour arrival (exploratory) | 165 / 85 / 52 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | spread margin R(h) | permanent (kcf-camp) | 657 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | spread margin R(h) | window, τ 105 | 657 / 50 / 115 | 0–2819 | **no** | 2820–6875 | — | FAIL |
| (a) 12:00 | spread margin R(h) | **window, τ 240 (frozen)** | 657 / 85 / 27 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | spread margin R(h) | window, τ 465 | 657 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | spread margin R(h) | residents, confirmed only, τ 240 | 657 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (a) 12:00 | spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 657 / 153 / 105 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:34 | no margin | permanent (kcf-camp) | 194 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:34 | no margin | window, τ 105 | 194 / 36 / 158 | open | yes | 0–6816 | 4% (12%) | FAIL |
| (b) 13:34 | no margin | **window, τ 240 (frozen)** | 194 / 48 / 102 | open | **no** | none | — | FAIL |
| (b) 13:34 | no margin | window, τ 465 | 194 / 12 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:34 | no margin | residents, confirmed only, τ 240 | 194 / 0 / 9 | open | **no** | none | — | FAIL |
| (b) 13:34 | no margin | window τ 240, neighbour arrival (exploratory) | 194 / 33 / 138 | open | yes | 0–6728 | 65% (65%) | FAIL |
| (b) 13:34 | spread margin R(h) | permanent (kcf-camp) | 723 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:34 | spread margin R(h) | window, τ 105 | 723 / 36 / 158 | open | **no** | none | — | FAIL |
| (b) 13:34 | spread margin R(h) | **window, τ 240 (frozen)** | 723 / 48 / 102 | open | **no** | none | — | FAIL |
| (b) 13:34 | spread margin R(h) | window, τ 465 | 723 / 12 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:34 | spread margin R(h) | residents, confirmed only, τ 240 | 723 / 0 / 9 | open | **no** | none | — | FAIL |
| (b) 13:34 | spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 723 / 74 / 253 | open | yes | 0–1304 | 65% (65%) | FAIL |
| (b) 13:58 | no margin | permanent (kcf-camp) | 198 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:58 | no margin | window, τ 105 | 198 / 27 / 171 | open | yes | 0–6816 | 9% (30%) | FAIL |
| (b) 13:58 | no margin | **window, τ 240 (frozen)** | 198 / 58 / 107 | open | **no** | none | — | FAIL |
| (b) 13:58 | no margin | window, τ 465 | 198 / 34 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:58 | no margin | residents, confirmed only, τ 240 | 198 / 0 / 9 | open | **no** | none | — | FAIL |
| (b) 13:58 | no margin | window τ 240, neighbour arrival (exploratory) | 198 / 40 / 141 | open | yes | 0–6728 | 65% (65%) | FAIL |
| (b) 13:58 | spread margin R(h) | permanent (kcf-camp) | 723 / 0 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:58 | spread margin R(h) | window, τ 105 | 723 / 27 / 171 | open | yes | 0–1231 | 9% (30%) | FAIL |
| (b) 13:58 | spread margin R(h) | **window, τ 240 (frozen)** | 723 / 58 / 107 | open | **no** | none | — | FAIL |
| (b) 13:58 | spread margin R(h) | window, τ 465 | 723 / 34 / 0 | 0–7200 | **no** | none | — | FAIL |
| (b) 13:58 | spread margin R(h) | residents, confirmed only, τ 240 | 723 / 0 / 9 | open | **no** | none | — | FAIL |
| (b) 13:58 | spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 723 / 83 / 260 | open | yes | 0–1304 | 65% (65%) | FAIL |

Witness routes checked by research/kcf-theorem/checker.py: 36, invalid 0.

### Test 4.2a: the 23 passable reports (state at the reported time, ±15 min)

| variant | rule | open | burned over | closed | closed share (95% CI) | distinct cells (not closed) | verdict (closed ≤ 20 %) |
|---|---|---|---|---|---|---|---|
| no margin | permanent (kcf-camp) | 21 | 0 | 2 | 9% (0.02–0.27) | 21 (19) | **INCONCLUSIVE** |
| no margin | window, τ 105 | 21 | 2 | 0 | 0% (0.00–0.14) | 21 (21) | **PASS** |
| no margin | **window, τ 240 (frozen)** | 21 | 2 | 0 | 0% (0.00–0.14) | 21 (21) | **PASS** |
| no margin | window, τ 465 | 21 | 0 | 2 | 9% (0.02–0.27) | 21 (19) | **INCONCLUSIVE** |
| no margin | residents, confirmed only, τ 240 | 21 | 0 | 2 | 9% (0.02–0.27) | 21 (19) | **INCONCLUSIVE** |
| no margin | window τ 240, neighbour arrival (exploratory) | 21 | 2 | 0 | 0% (0.00–0.14) | 21 (21) | **PASS** |
| spread margin R(h) | permanent (kcf-camp) | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| spread margin R(h) | window, τ 105 | 1 | 2 | 20 | 87% (0.68–0.95) | 21 (3) | **FAIL** |
| spread margin R(h) | **window, τ 240 (frozen)** | 1 | 2 | 20 | 87% (0.68–0.95) | 21 (3) | **FAIL** |
| spread margin R(h) | window, τ 465 | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| spread margin R(h) | residents, confirmed only, τ 240 | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 1 | 4 | 18 | 78% (0.58–0.90) | 21 (5) | **FAIL** |
| running-class R(h) | permanent (kcf-camp) | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| running-class R(h) | window, τ 105 | 1 | 2 | 20 | 87% (0.68–0.95) | 21 (3) | **FAIL** |
| running-class R(h) | **window, τ 240 (frozen)** | 1 | 2 | 20 | 87% (0.68–0.95) | 21 (3) | **FAIL** |
| running-class R(h) | window, τ 465 | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| running-class R(h) | residents, confirmed only, τ 240 | 1 | 0 | 22 | 96% (0.79–0.99) | 21 (1) | **FAIL** |
| running-class R(h) | window τ 240, neighbour arrival (exploratory) | 1 | 4 | 18 | 78% (0.58–0.90) | 21 (5) | **FAIL** |

### Test 4.2b: vehicle-present observations (AVL-located rows on a road cell; one field per row)

| variant | rule | open | burned over | closed | closed share (95% CI) | distinct cells (not closed) | verdict (closed ≤ 20 %) |
|---|---|---|---|---|---|---|---|
| no margin | permanent (kcf-camp) | 219 | 0 | 210 | 49% (0.44–0.54) | 170 (118) | **FAIL** |
| no margin | window, τ 105 | 219 | 177 | 33 | 8% (0.06–0.11) | 170 (165) | **PASS** |
| no margin | **window, τ 240 (frozen)** | 219 | 78 | 132 | 31% (0.27–0.35) | 170 (153) | **FAIL** |
| no margin | window, τ 465 | 219 | 28 | 182 | 42% (0.38–0.47) | 170 (130) | **FAIL** |
| no margin | residents, confirmed only, τ 240 | 219 | 14 | 196 | 46% (0.41–0.50) | 170 (124) | **FAIL** |
| no margin | window τ 240, neighbour arrival (exploratory) | 219 | 119 | 91 | 21% (0.18–0.25) | 170 (162) | **INCONCLUSIVE** |
| spread margin R(h) | permanent (kcf-camp) | 52 | 0 | 377 | 88% (0.84–0.91) | 170 (29) | **FAIL** |
| spread margin R(h) | window, τ 105 | 52 | 177 | 200 | 47% (0.42–0.51) | 170 (104) | **FAIL** |
| spread margin R(h) | **window, τ 240 (frozen)** | 52 | 78 | 299 | 70% (0.65–0.74) | 170 (75) | **FAIL** |
| spread margin R(h) | window, τ 465 | 52 | 28 | 349 | 81% (0.77–0.85) | 170 (48) | **FAIL** |
| spread margin R(h) | residents, confirmed only, τ 240 | 52 | 14 | 363 | 85% (0.81–0.88) | 170 (38) | **FAIL** |
| spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 52 | 161 | 216 | 50% (0.46–0.55) | 170 (106) | **FAIL** |
| running-class R(h) | permanent (kcf-camp) | 22 | 0 | 407 | 95% (0.92–0.97) | 170 (11) | **FAIL** |
| running-class R(h) | window, τ 105 | 22 | 177 | 230 | 54% (0.49–0.58) | 170 (91) | **FAIL** |
| running-class R(h) | **window, τ 240 (frozen)** | 22 | 78 | 329 | 77% (0.72–0.80) | 170 (58) | **FAIL** |
| running-class R(h) | window, τ 465 | 22 | 28 | 379 | 88% (0.85–0.91) | 170 (30) | **FAIL** |
| running-class R(h) | residents, confirmed only, τ 240 | 22 | 14 | 393 | 92% (0.89–0.94) | 170 (20) | **FAIL** |
| running-class R(h) | window τ 240, neighbour arrival (exploratory) | 22 | 161 | 246 | 57% (0.53–0.62) | 170 (89) | **FAIL** |

Vehicle-present rows by their own class (spread margin, frozen τ): FIRE_ARRIVAL 189 of 261 closed; OTHER 81 of 123 closed; ROAD_BLOCKED_OTHER 1 of 1 closed; ROAD_CLOSED 23 of 38 closed; ROAD_PASSABLE 5 of 6 closed.

### Test 4.3a: guard, the 195 road-blocked reports

| variant | rule | hits | hits under permanent closure | reopened too early | verdict (no loss) |
|---|---|---|---|---|---|
| no margin | permanent (kcf-camp) | 37 / 195 | 37 | 0 | **PASS** |
| no margin | window, τ 105 | 7 / 195 | 37 | 30 | **FAIL** |
| no margin | **window, τ 240 (frozen)** | 21 / 195 | 37 | 16 | **FAIL** |
| no margin | window, τ 465 | 33 / 195 | 37 | 4 | **FAIL** |
| no margin | residents, confirmed only, τ 240 | 37 / 195 | 37 | 0 | **PASS** |
| no margin | window τ 240, neighbour arrival (exploratory) | 16 / 195 | 37 | 21 | **FAIL** |
| spread margin R(h) | permanent (kcf-camp) | 170 / 195 | 170 | 0 | **PASS** |
| spread margin R(h) | window, τ 105 | 140 / 195 | 170 | 30 | **FAIL** |
| spread margin R(h) | **window, τ 240 (frozen)** | 154 / 195 | 170 | 16 | **FAIL** |
| spread margin R(h) | window, τ 465 | 166 / 195 | 170 | 4 | **FAIL** |
| spread margin R(h) | residents, confirmed only, τ 240 | 170 / 195 | 170 | 0 | **PASS** |
| spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 131 / 195 | 170 | 39 | **FAIL** |
| running-class R(h) | permanent (kcf-camp) | 191 / 195 | 191 | 0 | **PASS** |
| running-class R(h) | window, τ 105 | 161 / 195 | 191 | 30 | **FAIL** |
| running-class R(h) | **window, τ 240 (frozen)** | 175 / 195 | 191 | 16 | **FAIL** |
| running-class R(h) | window, τ 465 | 187 / 195 | 191 | 4 | **FAIL** |
| running-class R(h) | residents, confirmed only, τ 240 | 191 / 195 | 191 | 0 | **PASS** |
| running-class R(h) | window τ 240, neighbour arrival (exploratory) | 152 / 195 | 191 | 39 | **FAIL** |

Cross-fit (each half scored with the other half's τ, {'west': 225, 'east': 240}): reopened too early no margin 16, spread margin R(h) 16.

### Test 4.3b: guard, the 23 burnovers (closed or inside the 30-min margin)

| variant | rule | at t − 60 | at t − 30 | at t | permanent (t − 60 / t − 30 / t) | burnovers lost | verdict (no loss) |
|---|---|---|---|---|---|---|---|
| no margin | permanent (kcf-camp) | 9 | 9 | 9 | 9 / 9 / 9 | none | **PASS** |
| no margin | window, τ 105 | 6 | 6 | 6 | 9 / 9 / 9 | BO 23, BO 16, BO 19 | **FAIL** |
| no margin | **window, τ 240 (frozen)** | 7 | 7 | 7 | 9 / 9 / 9 | BO 16, BO 19 | **FAIL** |
| no margin | window, τ 465 | 7 | 7 | 7 | 9 / 9 / 9 | BO 16, BO 19 | **FAIL** |
| no margin | residents, confirmed only, τ 240 | 9 | 9 | 9 | 9 / 9 / 9 | none | **PASS** |
| no margin | window τ 240, neighbour arrival (exploratory) | 6 | 5 | 5 | 9 / 9 / 9 | BO 14, BO 16, BO 18, BO 19 | **FAIL** |
| spread margin R(h) | permanent (kcf-camp) | 14 | 16 | 21 | 14 / 16 / 21 | none | **PASS** |
| spread margin R(h) | window, τ 105 | 14 | 16 | 21 | 14 / 16 / 21 | none | **PASS** |
| spread margin R(h) | **window, τ 240 (frozen)** | 14 | 16 | 21 | 14 / 16 / 21 | none | **PASS** |
| spread margin R(h) | window, τ 465 | 14 | 16 | 21 | 14 / 16 / 21 | none | **PASS** |
| spread margin R(h) | residents, confirmed only, τ 240 | 14 | 16 | 21 | 14 / 16 / 21 | none | **PASS** |
| spread margin R(h) | window τ 240, neighbour arrival (exploratory) | 14 | 15 | 19 | 14 / 16 / 21 | BO 14, BO 17 | **FAIL** |
| running-class R(h) | permanent (kcf-camp) | 17 | 19 | 23 | 17 / 19 / 23 | none | **PASS** |
| running-class R(h) | window, τ 105 | 17 | 19 | 23 | 17 / 19 / 23 | none | **PASS** |
| running-class R(h) | **window, τ 240 (frozen)** | 17 | 19 | 23 | 17 / 19 / 23 | none | **PASS** |
| running-class R(h) | window, τ 465 | 17 | 19 | 23 | 17 / 19 / 23 | none | **PASS** |
| running-class R(h) | residents, confirmed only, τ 240 | 17 | 19 | 23 | 17 / 19 / 23 | none | **PASS** |
| running-class R(h) | window τ 240, neighbour arrival (exploratory) | 17 | 18 | 21 | 17 / 19 / 23 | BO 14, BO 17 | **FAIL** |

### Step 5: Korean expressway sections, traffic return (15-min VDS) and model reopening (KST)

| official closure | section | km (share in lattice) | cells with fire (discs) | fire on section, first – last | official reopening message | traffic returned (median, n conzone-dirs) | model reopen τ 105 / 240 / 465 | model − traffic at τ 240, min | Choi: model reopen, − traffic | closed spell at closure → ends, − traffic (secondary) |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-03-22 20:38 | 청주영덕선 서의성IC~안동분기점 | 22.3 (0.34) | 25 / 25 | 03-23 03:23 – 03-25 15:55 | 2025-03-24 09:00 서산영덕선 서의성IC~안동분기점 | none (0) | 03-25 17:40 / 03-25 19:55 / 03-25 23:40 |  | 03-26 06:58,  | open  |
| 2025-03-23 13:44 | 청주영덕선 서의성IC~안동분기점 | 22.3 (0.34) | 25 / 25 | 03-23 03:23 – 03-25 15:55 | 2025-03-24 09:00 서산영덕선 서의성IC~안동분기점 | 03-24 03:22 (2) | 03-25 17:40 / 03-25 19:55 / 03-25 23:40 | 2432 | 03-26 06:58, 3096 | closed → 03-23 14:43, -760 |
| 2025-03-24 13:20 | 서산영덕선 북의성IC~동안동IC | 19.1 (1.0) | 58 / 58 | 03-24 12:44 – 03-25 14:10 | — | 03-25 06:45 (1) | 03-25 15:55 / 03-25 18:10 / 03-25 21:55 | 685 | 03-26 04:02, 1278 | closed → 03-24 18:19, -746 |
| 2025-03-24 15:35 | 서산영덕선 북의성IC~영덕TG | 69.1 (1.0) | 216 / 221 | 03-24 12:44 – 03-26 01:02 | 2025-03-25 00:15 서산영덕선 청송IC~영덕IC | 03-25 06:30 (4) | 03-26 02:47 / 03-26 05:02 / 03-26 08:47 | 1352 | 03-26 15:25, 1975 | closed → 03-24 18:19, -731 |
| 2025-03-25 00:15 | 중앙선 의성IC~남안동JC | 23.0 (0.76) | 58 / 58 | 03-25 01:28 – 03-25 16:07 | 2025-03-25 05:40 중앙선 의성IC~안동JC | 03-25 05:45 (1) | 03-25 17:52 / 03-25 20:07 / 03-25 23:52 | 862 | 03-26 07:57, 1573 | open  |
| 2025-03-25 15:30 | 서산영덕선 안동JC~청송IC | 37.5 (1.0) | 114 / 114 | 03-24 12:44 – 03-25 16:35 | — | 03-25 17:00 (2) | 03-25 18:20 / 03-25 20:35 / 03-26 00:20 | 215 | 03-26 04:02, 663 | closed → 03-25 20:35, 215 |
| 2025-03-25 15:58 | 서산영덕선 서의성IC~청송IC | 58.5 (0.78) | 137 / 137 | 03-23 03:23 – 03-25 16:35 | — | 03-25 17:00 (2) | 03-25 18:20 / 03-25 20:35 / 03-26 00:20 | 215 | 03-26 06:40, 821 | closed → 03-25 20:35, 215 |
| 2025-03-25 18:00 | 중앙선 의성IC~예천IC | 51.4 (0.56) | 96 / 96 | 03-25 01:28 – 03-25 17:27 | — | 03-28 18:37 (2) | 03-25 19:12 / 03-25 21:27 / 03-26 01:12 | -4150 | 03-27 00:45, -2512 | closed → 03-25 21:27, -4150 |
| 2025-03-25 21:26 | 중앙선 의성IC~풍기IC | 73.4 (0.39) | 96 / 96 | 03-25 01:28 – 03-25 17:27 | 2025-03-25 23:10 중앙선 풍기IC~영주IC | 03-28 18:45 (3) | 03-25 19:12 / 03-25 21:27 / 03-26 01:12 | -4158 | 03-27 00:45, -2519 | closed → 03-25 21:27, -4158 |
| 2025-03-26 10:00 | 서산영덕선 서의성IC~영덕TG | 95.4 (0.87) | 255 / 260 | 03-23 03:23 – 03-26 01:02 | — | 03-26 22:15 (4) | 03-26 02:47 / 03-26 05:02 / 03-26 08:47 | -1032 | 03-26 15:25, -410 | open  |
| 2025-03-26 10:00 | 중앙선 의성IC~예천IC | 51.4 (0.56) | 96 / 96 | 03-25 01:28 – 03-25 17:27 | — | 03-28 18:30 (6) | 03-25 19:12 / 03-25 21:27 / 03-26 01:12 | -4142 | 03-27 00:45, -2504 | open  |
| 2025-03-26 10:31 | 서산영덕선 동상주IC~영덕TG | 106.2 (0.78) | 255 / 260 | 03-23 03:23 – 03-26 01:02 | — | 03-27 15:45 (7) | 03-26 02:47 / 03-26 05:02 / 03-26 08:47 | -2082 | 03-26 15:25, -1460 | open  |
| 2025-03-26 10:31 | 중앙선 의성IC~예천IC | 51.4 (0.56) | 96 / 96 | 03-25 01:28 – 03-25 17:27 | — | 03-28 18:30 (6) | 03-25 19:12 / 03-25 21:27 / 03-26 01:12 | -4142 | 03-27 00:45, -2504 | open  |

Fire-disc record ends 03-26 02:58 KST; fire that first reached a cell later is not in the discs.

### Step 6: kcf-robust's comparison with responder windows, twin (24 cases)

| rule | failed evacuations / advised | missed cut-offs / true cut | false cut-offs / true not cut | lead time given up, median (min) | failed − CURRENT (95% CI) | lead given up − CURRENT, median (95% CI) |
|---|---|---|---|---|---|---|
| a. CURRENT | 5 / 204 | 34 / 92 | 154 / 2068 | 100.3 | — | — |
| b. TIME-ROBUST | 0 / 0 | 54 / 92 | 52 / 2068 | -47.0 | -5 [-10, +0] | [-234, -36] |
| c. REACH-ROBUST | 1 / 30 | 39 / 92 | 79 / 2068 | 202.7 | -4 [-9, +0] | [-30, +149] |
| d. FASTEST | 6 / 18 | 88 / 92 | 9 / 2068 | -122.7 | +1 [-8, +10] | [-299, -161] |
| e. FORECAST-AWARE | 4 / 121 | 42 / 92 | 81 / 2068 | 37.2 | -1 [-6, +3] | [-106, -0] |

CURRENT with permanent closures against the permanent truth (reproduction check): failed 5 / 210, missed 12 / 221, false 146 / 1939.

Margin field vs plain slack at departure 0 (per place and shelter, feasible at 0):

| closures | pairs | margin = slack | margin = horizon cap | differ | margin below slack | largest difference (s) |
|---|---|---|---|---|---|---|
| permanent | 5995 | 403 | 5353 | 239 | 0 | 423 |
| responder windows | 6268 | 413 | 5576 | 279 | 40 | 16687 |

Step 7, later windows (rule CURRENT): 2160 place-issues (90 places).
* responders: 146 place-issues gain a later window (54 places); 8 place-issues with more than one window; 138 gain a departure where there was none; median gain 476 min; the route at the new latest departure repeats a road piece (drives a loop) in 0, and is the greedy (not earliest) witness in 0.

### Step 6: kcf-robust's comparison with responder windows, replay (26 cases)

| rule | failed evacuations / advised | missed cut-offs / true cut | false cut-offs / true not cut | lead time given up, median (min) | failed − CURRENT (95% CI) | lead given up − CURRENT, median (95% CI) |
|---|---|---|---|---|---|---|
| a. CURRENT | 143 / 308 | 327 / 339 | 355 / 1923 | -149.2 | — | — |
| b. TIME-ROBUST | 0 / 0 | 338 / 339 | 736 / 1923 | -156.7 | -143 [-156, -130] | [-8, -7] |
| c. REACH-ROBUST | 40 / 83 | 327 / 339 | 281 / 1923 | -150.0 | -103 [-110, -96] | [-3, +0] |
| d. FASTEST | 17 / 48 | 338 / 339 | 60 / 1923 | -156.7 | -126 [-138, -114] | [-8, -7] |
| e. FORECAST-AWARE | 240 / 439 | 317 / 339 | 487 / 1923 | -126.1 | +97 [+82, +112] | [+7, +79] |

CURRENT with permanent closures against the permanent truth (reproduction check): failed 184 / 349, missed 719 / 1887, false 126 / 375.

Margin field vs plain slack at departure 0 (per place and shelter, feasible at 0):

| closures | pairs | margin = slack | margin = horizon cap | differ | margin below slack | largest difference (s) |
|---|---|---|---|---|---|---|
| permanent | 3275 | 580 | 2324 | 371 | 0 | 657 |
| responder windows | 5062 | 670 | 3561 | 831 | 422 | 26337 |

Step 7, later windows (rule CURRENT): 2262 place-issues (174 places).
* responders: 1141 place-issues gain a later window (162 places); 76 place-issues with more than one window; 1063 gain a departure where there was none; median gain 470 min; the route at the new latest departure repeats a road piece (drives a loop) in 0, and is the greedy (not earliest) witness in 0.
* residents (confirmed only): 0 place-issues gain a later window (0 places); 0 place-issues with more than one window; 0 gain a departure where there was none; median gain n/a min; the route at the new latest departure repeats a road piece (drives a loop) in 0, and is the greedy (not earliest) witness in 0.

