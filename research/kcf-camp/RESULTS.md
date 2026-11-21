# kcf-camp: the road layer scored at the Camp Fire observations

**Model output on inputs rebuilt from public observations, scored against other public observations. Not what
happened to people. No claim about what any responder or official should have done.**

Rules frozen first: [PROTOCOL.md](PROTOCOL.md), commit `0bb8a58`, with amendments 1–4 (commits `d8c36ba`, `692a2bf`),
all made before any test was run. Outputs: [`out/`](out). Every number below is generated from those files by
`make_tables.py` (tables) or quoted from them. "N p." = printed page of NIST TN 2252; "sup PDF p." = PDF page of its
supplement.

## Headline

1. **No margin (the closure rule on the reports alone) misses most closures.** Of 195 road-closed reports held out from the
   input, the road cell was closed by the reported time in **37 (19 %, 95 % CI 14–25 %)**; 97 of them were never closed
   at all, because nobody else reported fire in that cell more than 500 m / 60 min away. It wrongly closed 2 of 23 roads seen
   passable (9 %, 2–27 %). FAIL.
2. **The frozen spread margin R(h) catches closures early, and it also closes the roads crews drove.** It had **170 of
   195 (87 %, 82–91 %)** closed by the reported time, a median **119 min before** (95 % CI 92–157 min; IQR 36–290), but it
   had **22 of 23 passable roads (96 %, 79–99 %)** closed when crews were seen driving them. FAIL on false closures. By
   12:00 it had 36 % of all 2,121 road cells closed against 8 % with no margin (post hoc context).
3. **Burnovers.** With the spread margin, **16 of 23 burnover roads (70 %, 49–84 %)** were closed or inside the 30-min margin 30
   min before the burnover began, 21 of 23 at its start. INCONCLUSIVE against the 80 % rule. With no margin, 9 of 23 (39 %,
   22–59 %) at every lead time. FAIL.
4. **Real movements: neither documented trip is feasible in the deadline field under any variant.** In both cases the cell
   the vehicles were waiting in was already closed: Fire Station 82 had fire reports from 11:02, 58 min before the
   12:00 convoy; Firland Dr from 09:01, 4.5 h before the engines left at 13:58. Closures are permanent, so a road that has
   burned over and become passable again never reopens. FAIL for both, with and without margin.
5. **What this means for the product.** The rule "a cell is closed from fire arrival, forever" plus the margin is
   conservative where fire is coming (it closes early) and wrong where fire has passed. 19 of the 23 passable reports
   describe driving through or beside active fire, which a civilian router should still avoid. The three that describe a
   road open with no fire on it ("traffic full speed", "it clears up", "burned over already and is safe") are all closed by
   the margin and would stay closed.

## Data

* **Workbook** (`camp/nist_fire_spread_observations.xlsx`): 15 sheets, 2,839 rows, **2,264 unique observations** after
  removing 575 copies of the same row on several sheets (6 unique rows share time, place and text with another source and
  are kept). Day from the date column (year mistyped 2021; amendment 3): 2,016 rows on 8 November (from 06:25), 248 on 9
  November. 2 rows have no time and are not used.
* **Classes** (`data/classes_final.csv`): first pass by keyword rules (`classify.py`); a second reader labelled the 652
  rows that mention a road or that the first pass marked road-state, without seeing the first labels. Agreement **83.7 %,
  Cohen's kappa 0.72**. All 106 disagreements were resolved by reading the text: the second reading was taken in 103, the
  first in 2 (W0760 fire on Pentz Rd, W1923 businesses along Skyway), and 1 row both missed was set to road closed (W1165
  "fire has burned through Pearson Rd"). Final: **1,596 fire arrival, 202 road closed, 24 passable, 4 blocked for another
  reason, 436 other** (timed rows).
* **Road network**: OpenStreetMap via Overpass, fetched 21 November 2026 in four tiles (SHA-256 in
  `data/osm_tiles_sha256.txt`), 4,350 nodes, 9,585 directed edges, 2,121 road cells of 375 m (`build_graph_osm.py`).
* **Placing**: 195 of 202 road-closed and 23 of 24 passable reports fall on or within 375 m of a road cell; 7 and 1 are
  outside the graph and not scored. All 23 burnovers were placed; both movements were placed from the refuge-area
  coordinates in the supplement (snaps 5–61 m).

## Test 1: road closures at held-out road-state reports

Input: fire-arrival reports only, without any within 500 m and ±60 min of a scored road-state report (812 of 1,596 removed;
784 kept, in 320 cells). C = the variant's closure time at the report's road cell, t = the reported time; hit = C ≤ t + 15 min;
false closure = C ≤ t − 15 min at a passable report.

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

The leaky run keeps every fire report (no exact duplicates of road-state rows survived de-duplication): with reports from
the same place and hour in the input, no margin rises from 19 % to 72 % hits and its false closures from 2 to 14 of 23. A check
without the hold-out would credit the rule with hits that come from other reports of the same place and hour, often the same
crew or event. When no margin does close a held-out cell, it closes a median 119 min after the report (n = 98).

**The 23 passable reports** (`out/test1_road_state.csv`). Under the spread margin 22 were closed beforehand: 19 say fire was
on or around the road as it was driven (for example W0915 "fire both sides, but is good enough to get through", W1321 "fire
blowing across Clark Rd; driving through flames"); 3 describe an open road without fire on it (W1020 11:15 "traffic full speed
SB in NB lanes", closed 10:06; W1239 12:25 "it clears up, its barely passable", closed 10:59; W1599 14:25 "it has burned over
already and is safe", closed 10:47). The one not closed is W0324 (embers only, 08:15; closes 08:49). This split was made after
seeing the results.

## Test 2: burnovers

For each burnover's stretch of road (Table 30 length around the place in the table below), the state at t − 60, t − 30 and t
(t = Table 30 start): C = closed, U = not closed but closing within the cards' 30-min margin, o = open. Input: all
fire-arrival reports except those within 500 m and ±60 min of that burnover.

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

Nine burnovers were closed under every variant at least an hour ahead (BO 5, 8, 9, 10, 14, 23 on 8 November; 16, 18, 19 on
9 November): fire had been reported on those roads well before. The spread margin adds warning on Pentz Rd, Pearson Rd,
lower Skyway, Jordan Hill Rd, Neal Rd, Chestnut Cir and Rattlesnake Flats Rd. It left seven open 30 min before: the first
burnovers in Concow and east Paradise (Hoffman Rd, Concow Rd, Camelot Ln 07:50–07:55; Chapman Ln and upper Skyway 08:30),
when few earlier reports existed to grow from, and Edgewood Ln and Clark Rd at Airport Rd.

## Test 3: the two documented movements

(a) Convoy from Fire Station 82 (TRA-O, sup PDF p. 230) down Pearson Rd to Clark Rd and the Ace Hardware lot (TRA-Q, sup
PDF p. 236), about 12:00 (N p. 143, p. 152). (b) Engines held at Firland Dr (TRA-X, sup PDF p. 258) at 13:34 for 24 min,
then north on Skyway to Magalia, taken as Skyway at Coutolenc Rd (TRA-BB, sup PDF p. 270) (N p. 144). Deadline field
issued at the documented time, horizon 2 h, dwell 120 s. Input: fire-arrival reports before the issue time.

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

The 30-min card margin is identical to no margin here by construction (closures already at the issue time cannot move
earlier). Post hoc (`out/test3_endpoint_cells_posthoc.json`): the origin cell of (a) has 13 fire reports, the first at 11:02
("structures on fire"); its destination cell 33, the first at 11:39. The origin cell of (b) has 13, the first at 09:01. The
fire-free routes follow the documented roads: (a) Pearson Rd after a 25 m snap onto Middle Libby Rd at the station's node;
(b) Skyway, which OSM names "New Skyway" north of Paradise, so a strict name match gives 64 %. Because no variant finds
either trip feasible, the route-match half of the pass rule was not reached.

## Extracted tables

**Burnovers, NIST TN 2252 Table 30** (printed pp. 125–126, PDF pp. 163–164), with how each was placed
(`data/burnovers_tn2252.csv`). Durations and lengths as printed; "n/d" no data.

| BO | place (Table 30) | community | start | duration, min | road affected, m | fatalities | Table 30 page (printed / PDF) | where it is placed, and source |
|---|---|---|---|---|---|---|---|---|
| 1 | Hoffman Rd | Concow | 11-08 07:50 | 40 | 250 |  | 125 / 163 | TN 2252 sup App. I TRA-B (Hoffman Rd 350 m W of Concow Rd; TRA inside BO #1 area per N p. 137), sup PDF p. 188 |
| 2 | Concow Rd | Concow | 11-08 07:50 | 70 | 1000 |  | 125 / 163 | TRA-C Concow Rd at Hoffman Rd (BO #2 at that intersection, N §9.2 p. 147), sup PDF p. 191 |
| 20 | Camelot Ln | Concow | 11-08 07:55 (e: first observation) | 50 | n/a |  | 125 / 163 | sup App. F p. F-3 coordinates, sup PDF p. 151 |
| 3 | Chapman Ln | Paradise | 11-08 08:30 | n/d | 250 |  | 125 / 163 | no cross street in TN 2252; centroid of the named road on the graph |
| 4 | Skyway (upper) | Paradise | 11-08 08:30 | 360 | 2600 |  | 125 / 163 | between Wagstaff Rd and Clark Rd (N §9.1.2 p. 140); ends at TRA-N Wagstaff Rd at Skyway (sup PDF p. 227) and TRA-S Skyway at Clark Rd 39.798183 -121.585289 (sup PDF p. 242) |
| 5 | Windermere Ln | Concow | 11-08 08:35 (e: first observation) | n/d | 1100 | 1 | 125 / 163 | no cross street in TN 2252; centroid of the named road on the graph |
| 6 | Pentz Rd | Paradise | 11-08 08:45 | 150 | 1300 |  | 125 / 163 | Pentz Rd between Bille Rd and Pearson Rd (N p. 65, p. 137) |
| 7 | Pearson Rd | Paradise | 11-08 09:15 | 60 | 800 | 1 | 125 / 163 | east end of Pearson Rd between Cherry Ln and Hilbe Dr (N p. 138); TRA-J inside the burnover area, sup PDF p. 213 |
| 8 | Bille Rd | Paradise | 11-08 09:25 | 140 | 500 |  | 125 / 163 | Bille Rd / Pentz Rd intersection (N p. 65, p. 152); TRA-I, sup PDF p. 210 |
| 21 | Edgewood Ln | Paradise | 11-08 09:30 | n/d | 250 | 5 | 125 / 163 | sup App. F p. F-6 coordinates, sup PDF p. 154 |
| 9 | Wagstaff Rd | Paradise | 11-08 09:30 | 60 | 500 |  | 125 / 163 | Wagstaff Rd at and west of Rocky Ln (N §9.1.2 p. 140) |
| 10 | Clark Rd / American Way | Paradise | 11-08 10:00 | 120 | 700 |  | 125 / 163 | Table 30 place; N p. 95 (Table 19) and p. 170 |
| 11 | Clark Rd / Airport Rd | Butte County | 11-08 10:00 | 90 | 1500 |  | 125 / 163 | Table 30 place |
| 12 | Skyway (lower) | Paradise | 11-08 10:15 | 90 | 1000 |  | 125 / 163 | TN 2252 gives only 'Skyway (lower)'; 'west of Princeton Way' is from TN 2135 Table 33 as carried in research/kcf-validate/out/nist_burnovers.csv (TN 2135 not in the evidence folder) |
| 13 | Jordan Hill Rd / Granite Hill Rd | Concow | 11-08 11:30 | n/d | 800 |  | 125 / 163 | Table 30 place; N §7 p. 76; OSM has no Granite Hill Rd, placed at Granite Ridge Rd (workbook W1046), PROTOCOL amendment 4 |
| 22 | Neal Rd | Paradise | 11-08 11:30 | 90 | 800 |  | 126 / 164 | sup App. F p. F-9 coordinates, sup PDF p. 157 |
| 23 | Clark Rd / Cypress Ln | Paradise | 11-08 11:45 (e: first observation) | n/d | 1300 |  | 126 / 164 | sup App. F p. F-12 coordinates, sup PDF p. 160; 1.3 km stretch around Cypress Ln (N p. 142) |
| 14 | Clark Rd / Black Bear Diner | Paradise | 11-08 13:10 | n/d | 150 |  | 126 / 164 | Black Bear Diner on Clark Rd as geocoded by research/kcf-validate (Overture place); not in TN 2252 text |
| 15 | Rattlesnake Flats Rd | Butte County | 11-08 15:15 | 15 | 300 |  | 126 / 164 | no cross street in TN 2252; centroid of the named road on the graph |
| 16 | Coutolenc Rd | Magalia | 11-09 00:00 (g: 9 Nov) | 120 | 3000 |  | 126 / 164 | first responders sheltered at the Skyway/Coutolenc Rd intersection (N p. 145); TRA-BB, sup PDF p. 270 |
| 17 | Chestnut Cir | Magalia | 11-09 06:00 (g: 9 Nov) | n/d | 150 |  | 126 / 164 | no cross street in TN 2252; centroid of the named road on the graph |
| 18 | Ponderosa Way | Magalia | 11-09 07:15 (g: 9 Nov) | n/d | 400 |  | 126 / 164 | fire pinched Ponderosa Way and Compton Dr (N p. 145) |
| 19 | Concow Fire Station 37 | Concow | 11-09 07:15 (g: 9 Nov) | n/d | 600 |  | 126 / 164 | Concow Rd at Fire Station 37 (N p. 146); FS 37 position from workbook row naming 'Station 37'; TRA-EE (39.727044 -121.525026, sup PDF p. 279) is 250-900 m from it |

**Documented movements** (`data/movements_tn2252.csv`):

| | what the report says | time | documented roads | origin (source) | destination (source) | pages |
|---|---|---|---|---|---|---|
| a | Firefighters lead a convoy of 10–12 civilian vehicles (also given as 9) from Fire Station 82, where 10–20 civilians had sheltered from 10:55 while Pearson Rd was impassable toward Clark Rd due to fire, down Pearson Rd to Clark Rd and the Ace Hardware lot | "just before noon" / "at 12:00" | Pearson Rd, Clark Rd | TRA-O 39.748772, −121.593944 (sup PDF p. 230) | TRA-Q 39.751828, −121.607314 (sup PDF p. 236) | N p. 143 (PDF 181), p. 152 (PDF 190); Table 21 p. 100 (PDF 138) |
| b | Engines heading north to their Magalia assignment met fire and blocking vehicles on Skyway north of Rocky Ln, parked at Firland Dr, waited 24 min for conditions on Skyway to abate, then proceeded | held 13:34, left 13:58 | Skyway | TRA-X 39.782582, −121.601611 (sup PDF p. 258) | Skyway at Coutolenc Rd, TRA-BB 39.812789, −121.578443 (sup PDF p. 270); the report gives only "Magalia" | N p. 144 (PDF 182); p. 131 (PDF 169); TRA table p. 129 (PDF 167) |

## What this shows and what it does not

* **Firefighter and witness reports, not resident trips.** The road-state rows, the burnovers and the two movements are
  what firefighters, police and some civilians reported. The two movements are fire-engine and escorted-convoy trips.
  Nothing here measures whether a resident's evacuation would have been feasible. Engines drove through conditions
  (and were damaged) that the product's closure rule treats as closed; that is the gap the passable rows measure.
* **One fire, one day, one place.** The Camp Fire on 8–9 November 2018 in Paradise, Concow and Magalia: a wind-driven
  fire that crossed the town in a few hours. The rates do not transfer to other fires, terrain or weather.
* **Observations are densest where people were.** The workbook records fire where someone saw it: along roads, at
  the hospital, at refuge areas. Cells nobody reported never close under the no-margin variant. A "miss" can be
  a cell where fire arrived but no one wrote it down; a "hit" can follow from a report made on the same road by the
  same crew. The 500 m / 60 min hold-out removes the most direct leaks; the leaky run shows how much they matter.
* **The input is not the product's real input.** The product is fed a satellite- or forecast-based arrival raster.
  Here it is fed ground reports (point locations, 15–30 min resolution, some "Inferred" times). The tests check the
  closure rule and the frozen margin on that input, not the satellite pipeline.
* **Present-day roads.** OpenStreetMap as fetched on 21 November 2026 stands in for the 2018 network. Free-flow speeds,
  no congestion; the record describes hours of gridlock, so feasible times here are optimistic for civilians.
* **Locations.** Burnover stretches are built from the report's named roads, cross streets, refuge-area coordinates and
  Table 30 lengths; the report's own map (Fig. 24) is an image and was not digitised. Two burnover places rest on
  sources outside TN 2252 (BO 12, BO 14), marked in the burnover table.
* **Not public.** The CAL FIRE AVL CSV that NIST TN 2128 §3.2.1 describes (281 apparatus, 5–12 November) and the NETTRA
  database are not public. With them, Test 3 could be run on hundreds of real apparatus trips instead of two
  narrative movements. That is the single most useful next record (see the evidence folder's `records_requests.txt`).

## Reproduce

```
python3 -I dedup.py camp/nist_fire_spread_observations.xlsx data/observations_dedup.csv
python3 -I classify.py data/observations_dedup.csv data/classes_pass1.csv
# second pass: data/classes_pass2_blind.csv (blind reader); resolution in data/classes_final.csv
# Overpass, four tiles, highway filter in PROTOCOL §1 and amendment 2; checksums in data/osm_tiles_sha256.txt
python3 -I build_graph_osm.py graph.json osm_tile1.json osm_tile2.json osm_tile3.json osm_tile4.json
python3 -I score_tests12.py graph.json out
python3 -I test3_movements.py graph.json out
python3 -I make_tables.py > out/tables.md
```
Needs numpy, scipy, pyproj, openpyxl and `product/wfg-roadlayer` (its engine is imported unchanged). The PDFs and the
graph are not committed.
