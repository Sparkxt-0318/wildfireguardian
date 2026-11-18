# Village cards: summary (25 March 2025 worked example, 174 places)

모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order. Issue times: 의성·안동 12:00 KST and 영덕 18:00 KST.
Fire input: the MEASURED reconstruction with an 8 h horizon. Margin 30 min. Every assumed value is marked ASSUMED in
the audit CSVs.

**Files.** Cards: `*/cards_ko_*.pdf` and `*/cards_en_*.pdf`, one A5 page per place (84 + 90). Audit: `*/audit_*.csv`.
Van routes: `*/pickup_*.csv`. Overlap check: `OVERLAP.md`. To rebuild: `python3 roadlayer.py cards-example`
(about 3–4 min).

**Exits.** 113 of 174 places have one independent road exit (58 of 84 in 의성·안동, 55 of 90 in 영덕). 59 have two,
and two places in 영덕 have three. In 5 places (원호리, 조탑리; 봉산리, 사암리, 연평리) the two exits pass through the
same 375 m road cell, so one closure cuts both.

**Forest along the exits.** The median exit route has mapped OSM forest within 50 m along 33 % (의성·안동) and 52 %
(영덕) of its length. The **conifer share was not computed**: the repository has no Korean forest-type map
(`research/kcf-idea-forecast/SURVEY.md`), and the offline basemap has no leaf type. These are any-forest shares.

**Traffic.** The narrowest road on almost every route is a village road, at 800 veh/h (ASSUMED). Village
households are cited county or 읍·면 totals split equally (ASSUMED). The median clearance is 14 min (의성·안동) and
13 min (영덕); the longest is 34 min. Counting clearance, 3 of the 16 villages with a deadline inside 8 h in
의성·안동 (동변리, 사촌리, 서변리) are already late at 12:00; none of the 22 in 영덕 are. Each card shows the leave-by
time with and without clearance.

**Trigger line.** 30 places have a trigger line inside 8 h (10 + 20). For 42 the trigger has already passed at the
issue time, 34 of them because the road is already cut. For 102 the trigger is beyond the horizon.

**Departure order and vans.** The cards put villages that share a road into 16 departure groups: 46 places in
의성·안동 and 22 in 영덕. In 3 places the shared road leaves less time than the deadline needs. The van pickup
uses 3 vans × 15 seats (ASSUMED) and a no-car share of 36 % (ASSUMED). It cannot reach most assumed residents inside
8 h: 4,032 of 7,734 in 의성·안동 and 9,916 of 10,525 in 영덕 remain. On these assumptions three vans are nowhere near
enough. The number is set by the vans setting, not by the roads.

**Check (item 5).** "Earliest cut-off" means the first quartile, per region, of each place's earliest replay
cut-off (`research/kcf-replay/per_place.csv`, MEASURED, 8 h). In 의성·안동 that is every place already cut at 12:00
(34), because of ties; in 영덕 it is cut by 20:44 (23).

| flag | flagged | earliest | both | both if unrelated |
|---|---:|---:|---:|---:|
| single exit | 113 | 57 | **46** | 37.0 |
| dangerous road (one cell cuts all exits) | 5 | 57 | **0** | 1.6 |
| either | 118 | 57 | **46** | 38.7 |

Single-exit places are somewhat over-represented among the earliest cut-offs: 46 against 37 if unrelated, with 11
early places having more than one exit. The 5 dangerous-road places are not among them. These are counts only, with
no test.

**Limits.**
* Households, vehicles per household, lane counts, village-road capacity, the no-car share, van numbers and care
  residents are ASSUMED or derived from province-level figures.
* The exits ignore turn restrictions.
* The trigger line is only as good as the fire-arrival input.
* Roads are OSM 2025-03-21, and road classes come from 2026 OSM.
