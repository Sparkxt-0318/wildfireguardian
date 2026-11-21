### Test 1 table (strict hold-out: 500 m and ±60 min)

| variant | road-closed rows scored | hits | misses (of which no closure at all) | hit rate (95% CI) | passable rows scored | false closures | false-closure rate (95% CI) | time error C − t, min: median | verdict |
|---|---|---|---|---|---|---|---|---|---|
| no margin | 195 | 37 | 158 (97) | 19% (0.14–0.25) | 23 | 2 | 9% (0.02–0.27) | +119 (95% CI +72 to +151; IQR -170 to +218; n = 98) | **FAIL** |
| 30-min card margin | 195 | 37 | 158 (97) | 19% (0.14–0.25) | 23 | 2 | 9% (0.02–0.27) | +89 (95% CI +42 to +121; IQR -200 to +188; n = 98) | **FAIL** |
| frozen spread margin R(h) | 195 | 170 | 25 (0) | 87% (0.82–0.91) | 23 | 22 | 96% (0.79–0.99) | -119 (95% CI -157 to -92; IQR -290 to -36; n = 195) | **FAIL** |
| running-class R(h) (secondary) | 195 | 191 | 4 (0) | 98% (0.95–0.99) | 23 | 22 | 96% (0.79–0.99) | -165 (95% CI -195 to -136; IQR -337 to -76; n = 195) | **FAIL** |

Leaky input (only exact duplicates of road-state rows removed), same columns:

| variant | hits / scored | hit rate (95% CI) | false closures / passable | rate (95% CI) | time error median | verdict |
|---|---|---|---|---|---|---|
| no margin | 141 / 195 | 72% (0.66–0.78) | 14 / 23 | 61% (0.41–0.78) | -46 (95% CI -66 to -30; IQR -136 to -2; n = 167) | FAIL |
| 30-min card margin | 149 / 195 | 76% (0.70–0.82) | 17 / 23 | 74% (0.54–0.88) | -76 (95% CI -96 to -60; IQR -166 to -32; n = 167) | FAIL |
| frozen spread margin R(h) | 187 / 195 | 96% (0.92–0.98) | 23 / 23 | 100% (0.86–1.00) | -128 (95% CI -157 to -106; IQR -302 to -54; n = 195) | FAIL |
| running-class R(h) (secondary) | 193 / 195 | 99% (0.96–1.00) | 23 / 23 | 100% (0.86–1.00) | -165 (95% CI -198 to -143; IQR -343 to -89; n = 195) | FAIL |

By day (strict):

| variant | 8 Nov hits / scored | 8 Nov false / passable | 9 Nov hits / scored | 9 Nov false / passable |
|---|---|---|---|---|
| no margin | 30 / 176 | 2 / 20 | 7 / 19 | 0 / 3 |
| 30-min card margin | 30 / 176 | 2 / 20 | 7 / 19 | 0 / 3 |
| frozen spread margin R(h) | 151 / 176 | 19 / 20 | 19 / 19 | 3 / 3 |
| running-class R(h) (secondary) | 172 / 176 | 19 / 20 | 19 / 19 | 3 / 3 |

### Test 2 table (closed or inside the 30-min margin, of placed burnovers)

| variant | at t − 60 | at t − 30 | at t | closed (not just unsafe) at t − 30 | lead of first closure before t, min | verdict |
|---|---|---|---|---|---|---|
| no margin | 9 / 23 (39%; 0.22–0.59) | 9 / 23 (39%; 0.22–0.59) | 9 / 23 (39%; 0.22–0.59) | 9 | +2 (95% CI -66 to +80; IQR -66 to +82; n = 18) | **FAIL** |
| 30-min card margin | 9 / 23 (39%; 0.22–0.59) | 9 / 23 (39%; 0.22–0.59) | 9 / 23 (39%; 0.22–0.59) | 9 | +32 (95% CI -36 to +110; IQR -36 to +112; n = 18) | **FAIL** |
| frozen spread margin R(h) | 14 / 23 (61%; 0.41–0.78) | 16 / 23 (70%; 0.49–0.84) | 21 / 23 (91%; 0.73–0.98) | 14 | +65 (95% CI +1 to +83; IQR -7 to +163; n = 23) | **INCONCLUSIVE** |
| running-class R(h) (secondary) | 17 / 23 (74%; 0.54–0.88) | 19 / 23 (83%; 0.63–0.93) | 23 / 23 (100%; 0.86–1.00) | 17 | +66 (95% CI +36 to +172; IQR +21 to +195; n = 23) | **INCONCLUSIVE** |

Per burnover (state at t − 60 / t − 30 / t; C = model closure of the first cell of the burnover stretch):

| BO | place | start | no margin | 30-min card margin | frozen spread margin R(h) | running-class R(h) (secondary) |
|---|---|---|---|---|---|---|
| 1 | Hoffman Rd | 11-08 07:50 | o/o/o (C never) | o/o/o (C never) | o/o/U (C 08:12) | o/o/U (C 07:51) |
| 2 | Concow Rd | 11-08 07:50 | o/o/o (C 08:52) | o/o/o (C 08:22) | o/o/U (C 08:18) | o/o/U (C 07:57) |
| 20 | Camelot Ln | 11-08 07:55 (e) | o/o/o (C 08:58) | o/o/o (C 08:28) | o/o/U (C 08:00) | o/U/C (C 07:45) |
| 3 | Chapman Ln | 11-08 08:30 | o/o/o (C never) | o/o/o (C never) | o/o/o (C 09:01) | o/o/U (C 08:32) |
| 4 | Skyway (upper) | 11-08 08:30 | o/o/o (C 09:37) | o/o/o (C 09:07) | o/o/U (C 08:45) | o/U/C (C 08:30) |
| 5 | Windermere Ln | 11-08 08:35 (e) | C/C/C (C 07:30) | C/C/C (C 07:00) | C/C/C (C 07:30) | C/C/C (C 07:30) |
| 6 | Pentz Rd | 11-08 08:45 | o/o/o (C 09:53) | o/o/o (C 09:23) | o/U/C (C 08:28) | U/C/C (C 08:13) |
| 7 | Pearson Rd | 11-08 09:15 | o/o/o (C 10:18) | o/o/o (C 09:48) | U/C/C (C 08:31) | C/C/C (C 08:10) |
| 8 | Bille Rd | 11-08 09:25 | C/C/C (C 08:02) | C/C/C (C 07:32) | C/C/C (C 08:02) | C/C/C (C 08:02) |
| 21 | Edgewood Ln | 11-08 09:30 | o/o/o (C never) | o/o/o (C never) | o/o/o (C 10:32) | o/o/U (C 09:31) |
| 9 | Wagstaff Rd | 11-08 09:30 | C/C/C (C 08:24) | C/C/C (C 07:54) | C/C/C (C 08:24) | C/C/C (C 08:24) |
| 10 | Clark Rd / American Way | 11-08 10:00 | C/C/C (C 08:40) | C/C/C (C 08:10) | C/C/C (C 08:40) | C/C/C (C 08:40) |
| 11 | Clark Rd / Airport Rd | 11-08 10:00 | o/o/o (C 11:14) | o/o/o (C 10:44) | o/o/U (C 10:09) | U/C/C (C 09:24) |
| 12 | Skyway (lower) | 11-08 10:15 | o/o/o (C 11:38) | o/o/o (C 11:08) | U/C/C (C 09:27) | C/C/C (C 09:09) |
| 13 | Jordan Hill Rd / Granite Hill Rd | 11-08 11:30 | o/o/o (C never) | o/o/o (C never) | C/C/C (C 09:19) | C/C/C (C 08:30) |
| 22 | Neal Rd | 11-08 11:30 | o/o/o (C 17:18) | o/o/o (C 16:48) | C/C/C (C 10:24) | C/C/C (C 09:29) |
| 23 | Clark Rd / Cypress Ln | 11-08 11:45 (e) | C/C/C (C 08:30) | C/C/C (C 08:00) | C/C/C (C 08:30) | C/C/C (C 08:15) |
| 14 | Clark Rd / Black Bear Diner | 11-08 13:10 | C/C/C (C 11:36) | C/C/C (C 11:06) | C/C/C (C 08:27) | C/C/C (C 08:12) |
| 15 | Rattlesnake Flats Rd | 11-08 15:15 | o/o/o (C never) | o/o/o (C never) | o/U/C (C 15:14) | C/C/C (C 12:23) |
| 16 | Coutolenc Rd | 11-09 00:00 | C/C/C (C 12:18) | C/C/C (C 11:48) | C/C/C (C 09:00) | C/C/C (C 08:31) |
| 17 | Chestnut Cir | 11-09 06:00 | o/o/o (C 11-09 07:05) | o/o/o (C 11-09 06:35) | C/C/C (C 10:54) | C/C/C (C 09:27) |
| 18 | Ponderosa Way | 11-09 07:15 | C/C/C (C 11-09 05:59) | C/C/C (C 11-09 05:29) | C/C/C (C 10:40) | C/C/C (C 09:21) |
| 19 | Concow Fire Station 37 | 11-09 07:15 | C/C/C (C 21:00) | C/C/C (C 20:30) | C/C/C (C 13:29) | C/C/C (C 10:15) |

### Test 3 table

| movement, issue time | variant | road cells closed (at issue) | feasible at issue? | latest feasible departure | route (roads in order) | share on documented roads | pass |
|---|---|---|---|---|---|---|---|
| (a) 12:00 | no margin | 165 (165) | **no** | none | — | — | FAIL |
| (a) 12:00 | 30-min card margin | 165 (165) | **no** | none | — | — | FAIL |
| (a) 12:00 | frozen spread margin R(h) | 657 (165) | **no** | none | — | — | FAIL |
| (a) 12:00 | running-class R(h) (secondary) | 891 (165) | **no** | none | — | — | FAIL |
| (b) 13:34 | no margin | 194 (194) | **no** | none | — | — | FAIL |
| (b) 13:34 | 30-min card margin | 194 (194) | **no** | none | — | — | FAIL |
| (b) 13:34 | frozen spread margin R(h) | 723 (194) | **no** | none | — | — | FAIL |
| (b) 13:34 | running-class R(h) (secondary) | 982 (194) | **no** | none | — | — | FAIL |
| (b) 13:58 | no margin | 198 (198) | **no** | none | — | — | FAIL |
| (b) 13:58 | 30-min card margin | 198 (198) | **no** | none | — | — | FAIL |
| (b) 13:58 | frozen spread margin R(h) | 723 (198) | **no** | none | — | — | FAIL |
| (b) 13:58 | running-class R(h) (secondary) | 982 (198) | **no** | none | — | — | FAIL |

Fire-free fastest routes (for the road match when the field is infeasible):

* (a) 12:00: 128 s, Middle Libby Road → Pearson Road, 76% on documented roads; first closed cell on it: M0: Middle Libby Road, closes +0 s, reached +0 s; M30: Middle Libby Road, closes +0 s, reached +0 s; MR: Middle Libby Road, closes +0 s, reached +0 s; MR_running: Middle Libby Road, closes +0 s, reached +0 s
* (b) 13:34: 264 s, Skyway → New Skyway, 64% on documented roads; first closed cell on it: M0: Skyway, closes +0 s, reached +0 s; M30: Skyway, closes +0 s, reached +0 s; MR: Skyway, closes +0 s, reached +0 s; MR_running: Skyway, closes +0 s, reached +0 s
* (b) 13:58: 264 s, Skyway → New Skyway, 64% on documented roads; first closed cell on it: M0: Skyway, closes +0 s, reached +0 s; M30: Skyway, closes +0 s, reached +0 s; MR: Skyway, closes +0 s, reached +0 s; MR_running: Skyway, closes +0 s, reached +0 s
