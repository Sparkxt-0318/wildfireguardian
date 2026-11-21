# kcf-camp protocol: scoring the road layer at the Camp Fire observations

Frozen 2026-11-21, before any test outcome was computed. What had been read before freezing: the workbook's sheet names
and first five rows per sheet, NIST TN 2252 Table 30 (burnover list), §9.1.2, §9.1.3, §9.3.1, Table 21, and the
column definitions of the supplement's Table A-2. No classification count, hold-out count, model closure or route
had been computed. Later changes are logged as dated amendments at the end; nothing above them is edited.

**What this is.** Model output on inputs rebuilt from public observations, scored against other public observations.
Not what happened to people. No claim about what any responder or official should have done.

## 0. Why not one field

`research/kcf-validate` rebuilt one arrival field from the NIST tables (thin-plate spline) and scored everything
against it; the field's own leave-one-out error was about 100 min, so the test could not separate the closure rule
from the interpolation. Here no continuous field is interpolated. Every number is a comparison at an observation:
the model state at the observation's cell and time, built only from other observations.

## 1. Sources

| id | file (evidence folder, not committed) | used for |
|---|---|---|
| W | `camp/nist_fire_spread_observations.xlsx` (NIST data catalog mds2-2954), 15 sheets | fire-arrival input, road-state observations |
| N | `camp/nist_tn2252_nettra.pdf` (NIST TN 2252, July 2023) | burnovers (Table 30), movements (§9.1.2, §9.1.3, §9.3.1) |
| S | `camp/nist_tn2252_supplement.pdf` (TN 2252 sup) | Table F-1 burnover sources, Appendix I TRA locations, Table A-2 (NETTRA rows) for locating places |
| A | `camp/nist_tn2128_avl_source.pdf` (TN 2128) | context only: the AVL CSV it describes is not public |

PDFs are not committed. Only extracted tables are committed, each row with printed page and PDF page.

Road network: OpenStreetMap drivable ways (`highway` = motorway … living_street and links; `service` kept in the
file but excluded from the graph) for lat 39.66–39.88, lon −121.80 to −121.46, fetched via the Overpass API on
2026-11-21. It is the present-day network used as a proxy for November 2018. Graph format and rules as
`research/kcf-validate/paradise/build_graph.py`: EPSG:32610, 375 m cells (the product lattice size), two-way unless
`oneway=yes`, free-flow speeds by class (motorway 100, trunk 80, primary 70, secondary 60, tertiary 50,
unclassified 40, residential 30, living_street 15 km/h; links as their parent class), largest connected component.
A *road cell* is a 375 m cell crossed by at least one graph edge. If Overpass cannot be reached, Overture
2026-10-21.0 segments are used instead and an amendment says so.

Times are Pacific Standard Time on 8 November 2018 unless marked. The workbook's date column reads 2021-11-08; the
README and the NIST reports place every row on 8 November 2018, and the date column is not used.

## 2. Data steps

**2.1 De-duplication.** The same observation appears on several sheets. Two rows are the same observation when
Source #, time, latitude and longitude (rounded to 5 decimals) and the whitespace- and case-normalised text are all
equal. One copy is kept with the list of sheets it came from. Rows from different sources reporting the same thing
are kept as separate observations (they are separate reports); their count is reported.

**2.2 Classes.** Each unique observation gets exactly one class:

| class | meaning | examples of text |
|---|---|---|
| `ROAD_CLOSED` | fire across or on the road, fire on both sides of the road, road blocked or impassable **because of fire** or burning debris, vehicles burning in the roadway | "fire across roadway", "fire both sides of road", "road impassable, fire" |
| `ROAD_BLOCKED_OTHER` | road blocked or impassable for a reason that is not fire (traffic, abandoned vehicles, power lines, trees) or the reason is not stated | "road blocked by downed lines" |
| `ROAD_PASSABLE` | the road was driven or was open/passable at that time and place | "drove through", "road still passable" |
| `FIRE_ARRIVAL` | fire present at the observation's location: spot fire, vegetation or structure burning, fire front, flames | "spot fire", "house on fire", "fire in yard" |
| `OTHER` | embers or smoke only, sounds, fire seen at a distance, statements that fire has not yet arrived, anything else | "embers falling", "can hear propane tanks" |

Road-state = the first three classes. A row that is road-state is not also `FIRE_ARRIVAL` (it is held out, §3.1).

**2.3 First pass.** A keyword rule (`classify.py`, committed with the first data commit) assigns classes.
**Second pass.** A separate reader, given only the text, time and sheet of every row that the first pass marked
road-state **or** whose text mentions a road word (road, rd, lane, ln, way, drive, dr, skyway, highway, hwy, street,
across, both sides, blocked, impassable, passable, drove, traffic), assigns one of the five classes without seeing the
first-pass label. Agreement (count, Cohen's kappa) is reported. Each disagreement is resolved by reading the text,
and the final label and reason are written to the table. The road-state classes used in the tests are the resolved
labels.

**2.4 Burnovers.** Every row of TN 2252 Table 30 (23 events) with ID, place, community, initiation time, duration,
date flag, printed page and PDF page. Location: the named road's cells within the extent the report describes
(Table 30 "roadway length affected" centred on the stated intersection or the location given in the report text,
§6.3.3, §8 or Appendix F), else the named road's cells within 400 m of the stated intersection. Each location gets its
source page. A burnover that cannot be placed on a named graph road is listed as not placed, with the reason.

**2.5 Movements.** (a) Convoy from Fire Station 82 (TRA-O) via Pearson Road to Clark Road and the Ace Hardware lot
(TRA-Q), "just before noon" / "at 12:00" (N §9.1.2 p. 143, §9.3.1 p. 152); documented roads Pearson Rd, Clark Rd;
documented departure 12:00 (stated as approximate). (b) Engines northbound on Skyway parked at Firland Drive (TRA-X)
at 13:34, waited 24 min, then proceeded on Skyway to Magalia (N §9.1.3 p. 144); documented road Skyway; documented
departures: held at 13:34, proceeded at 13:58. Destination for (b): the Skyway graph node nearest the Skyway /
Coutolenc Rd junction in Magalia (the report gives only "their assignment in Magalia"). Origin and destination
coordinates come from S Appendix I or Table A-2 rows naming the place; if none, from the named intersection on the
graph; the source is written next to each.

## 3. The model under test

The product closure rule (`product/wfg-roadlayer`, unchanged): a road cell is closed from the fire-arrival time of
that cell, permanently; the deadline field (vendored F-3.1 `engine.build_instance`, `core.backward`,
`core.issue_set`, `core.witness`) answers which departures reach a destination. The fire-arrival input is built from
`FIRE_ARRIVAL` observations only:

* each observation is placed in its 375 m cell; a cell's observed time is its earliest observation time;
* **no margin (M0):** a cell is closed from its own observed time; cells never observed never close;
* **30-min margin (M30):** M0 with every closure moved 30 min earlier (`cards.toml` `[trigger] margin_min = 30`);
* **spread margin (MR, the frozen fixed margin):** issued at any time T, a cell at centre distance d from the nearest
  observed cell with time < T closes at T + h(d), with h from `research/kcf-replay/measured_arms.closure_s` and the
  frozen all-hours R(5 h) = 3.8 km, R(8 h) = 5.0 km of `research/kcf-margin` (beyond R(8 h): never within 8 h).
  Taken over all issue times, a cell's closure is min over observed cells i of (t_i + h(d_i)).
* **MR-running (secondary):** as MR with the running class R(5 h) = 7.6 km, R(8 h) = 10.0 km.

"With margin" in the task is read as MR (the frozen spread margin that builds the product's fire input); M30 is
reported beside it because the cards call their 30 min the margin. Every test is run under M0, M30, MR and
MR-running; none is dropped after seeing results.

## 4. Split and hold-out

**4.1 Test 1 input.** All `FIRE_ARRIVAL` observations except those within **500 m and within ±60 min** of any
scored road-state observation (`ROAD_CLOSED` or `ROAD_PASSABLE`). The road-state observations themselves are never
input. Counts removed are reported. **Sensitivity (leaky):** only exact duplicates of road-state rows removed.
**4.2 Test 2 input.** All `FIRE_ARRIVAL` observations except those within 500 m of any cell of the burnover's location
and within ±60 min of its initiation time, removed separately for each burnover.
**4.3 Test 3 input.** All `FIRE_ARRIVAL` observations with time before the issue time.

## 5. Tolerances

* Matching an observation to a road cell: its own cell if it is a road cell; else the nearest road cell with centre
  within 375 m; else *not placed* (counted, not scored).
* Time: an observation's time is its recorded time t. The workbook resolution is about 15 min (NIST tables use
  15–30 min windows), so **15 min** is the tolerance.
* Hit (`ROAD_CLOSED`): model closure C ≤ t + 15 min. Miss: C > t + 15 min or no closure. Time error = C − t
  (negative = model earlier), for every scored row with a finite C.
* False closure (`ROAD_PASSABLE`): C ≤ t − 15 min (the model had the cell closed more than 15 min before it was
  seen passable).
* `ROAD_BLOCKED_OTHER`: reported (model closed or not), not scored.

## 6. Tests and pass rules

Proportions get Wilson 95 % intervals; medians get a bootstrap 95 % interval (2,000 resamples, seed 0). A test is
**INCONCLUSIVE** when the class it rests on has fewer than 10 scored rows or the 95 % interval of the deciding
proportion contains the threshold.

**Test 1, road closures.** Per margin variant: hits, misses, hit rate; false closures among `ROAD_PASSABLE`; time
error median and IQR. **PASS** when hit rate ≥ 0.80 and false-closure rate ≤ 0.20; **FAIL** when either is outside
and its interval excludes the threshold.

**Test 2, burnovers.** For each placed burnover and each variant, the state of its cells at t − 60, t − 30 and t
(t = Table 30 initiation): `CLOSED` if any cell has C ≤ τ; `UNSAFE` if not closed and any cell has C ≤ τ + 30 min
(inside the cards' 30-min margin); else `OPEN`. **PASS** when ≥ 80 % of placed burnovers are `CLOSED` or `UNSAFE` at
t − 30. Burnovers with an "e" flag (first observation, conditions existed earlier) are scored like the others and
listed. November 9 events are scored with the same November 8 input and reported separately.

**Test 3, movements.** For each movement and variant, the deadline field is built at issue time T = the documented
departure (horizon 2 h, the product's dwell of 120 s at the destination). Feasible = departure 0 is in the origin's
issue set. Route = `core.witness` at departure 0; match = share of its length on the documented roads (by OSM `name`).
**PASS** for a movement when the trip is feasible at the documented departure and ≥ 80 % of the route length is on
the documented roads. For (b) the 13:58 departure decides; the 13:34 state is reported (the engines chose to wait;
an infeasible answer at 13:34 is consistent with the record, a feasible one is not a failure). If the field is
infeasible, the fastest fire-free route is reported for the road match instead.

## 7. What is reported regardless

Counts at every step (rows read, duplicates, per class, placed, not placed), every not-placed row with reason, the
OSM fetch time and checksum, and this file's commit hash in RESULTS.md. If a test cannot be run from the public data
it is stopped and the reason given.

## Amendments

1. **2026-11-21, after the first-pass keyword run and before the second pass, any hold-out or any model value.**
   Precedence when one text has both fire on the road and passage: a row that says the road was driven, got through,
   was passable (also "barely passable", "passable one lane") or that traffic was flowing is `ROAD_PASSABLE`, even when
   it also says fire was on or across the road ("fire both sides, but is good enough to get through", "drove through
   fire"). These rows are exactly the case the closure rule is meant to judge. The second reader gets this rule with
   the class definitions. The first-pass rule order in `classify.py` (passage first) implements it.
2. **2026-11-21, same time.** The Overpass response for the whole box was truncated at 4.0 MB (client timeout). The
   network is fetched in four tiles with the same filter and merged by OSM id; nothing else changes.
3. **2026-11-21, before any hold-out or model value.** §1 said the workbook date column is not used. That was wrong:
   it separates 8 November (2,016 unique rows, earliest 06:25, the ignition time) from 9 November (248 rows, 00:00–19:40).
   Only its year is mistyped (2021). The day is taken from the month-day of that column; times are minutes after
   2018-11-08 00:00 PST (9 November adds 1,440). Rows of both days are used in input and scoring; 9 November rows are
   also reported separately. De-duplication keys and observation ids are unchanged (checked: identical before and
   after adding the day).
