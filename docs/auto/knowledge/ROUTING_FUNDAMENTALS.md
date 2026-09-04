# Routing fundamentals for WildfireGuardian — a sourced primer

**Compiled:** 2026-09-04 (research lap, knowledge base). **Scope:** the routing and
evacuation-modelling mechanisms the project uses (`src/wildfireguardian/routing/`)
and the adjacent literature it could draw on. **Not a results document**: every
figure below that is *not* from this repository is an external literature value,
labelled with author, year, venue and scope per CHARTER §3 rule 5b; it is not a
project measurement and must not be registered in `NUMBERS.json`. Repository facts
quoted here were read from the committed docs named in each place, not re-derived.

**Verification legend.** *[opened]* — URL opened in this lap (HTML, PDF text, or
the Semantic Scholar DOI record). *[metadata only]* — title/authors/venue confirmed,
full text paywalled; content rests on the abstract or on an opened source that
cites it. *UNVERIFIED* — not opened; search snippets only; check before the paper.

---

## 0. What the project's router actually is (so the literature maps onto it)

From the `routing/` docstrings and `docs/routing_limitations.md`: an osmnx `walk`
graph for residents and a `drive` graph for responders (EPSG:5179, DEM slopes); a
time-sliced P(ignite) field (`HazardSequence`, bilinear in space, linear in time,
canonical slices 0/180/360/540/720 min); a fire-blind `naive_route` (shortest
distance to the nearest refuge, then scored); a `future_aware_route` that runs
Dijkstra over `(node, time_bin)` states with 10-min ceil-rounded bins, edge cost
P(head, arrival) × travel time, and a hard gate at `p_cut` = 0.5; elderly walking
at 0.7 m/s with Tobler slope dependence and a 600-min budget; a rescue layer with a
vehicle cutoff of 0.7, ETA = 30-min dispatch delay + drive, a 12-min margin, a
closing-window dispatch sort, and a round-trip margin / withdrawal trigger line.
`routing_limitations.md` records that the optimised functional is a right-endpoint
rounded-bin sum while reported exposure is left-endpoint exact-time, and that the
search is not provably optimal over exact clocks. Paired contrasts are the unit of
evidence because both arms share the code. Everything below is read against that.

---

## 1. Graph fundamentals

### 1.1 Static shortest paths

Dijkstra's label-setting algorithm with a priority queue is the baseline; A* adds a
goal-directed potential; bidirectional search runs forward and backward and stops
when the frontiers meet; **contraction hierarchies** (Geisberger, Sanders, Schultes
& Delling, 2008, WEA) pre-order nodes by importance and contract them one by one,
inserting shortcuts, so a query is a bidirectional upward search that answers in
microseconds on continental road graphs *[metadata only]*. The reference survey is
Bast et al. (2016, *Algorithm Engineering*, LNCS 9220, arXiv:1504.05140) *[opened]*,
which also covers time-dependent variants and the trade-off between preprocessing,
space and query time.

**Relevance.** The graphs are county-scale (≈8.4 k walk nodes, `network_drift.md`),
so plain Dijkstra suffices; the cost is building the node × time-bin table, which
`TimeExpandedField` hoists. CH-style preprocessing does not transfer to a hazard
that changes every forecast.

### 1.2 Time-dependent shortest paths, FIFO, and waiting

Orda & Rom (1990, *J. ACM* 37(3)) *[metadata only; content via Foschini et al.
2011, opened]* studied shortest paths when edge delays are arbitrary functions of
departure time. Their key results, as summarised by Foschini, Hershberger & Suri
(SODA 2011) *[opened]*: (i) under an **unrestricted waiting** policy the problem
behaves well and Dijkstra generalises (Dreyfus 1969 had already observed this);
(ii) if **waiting is forbidden** and the network is **non-FIFO**, shortest paths can
be non-simple and non-concatenated, sub-path optimality fails, and variants are
NP-hard. The **FIFO property** — leaving later never gets you there earlier — is
what makes label-setting valid: in a FIFO network waiting is never beneficial, and a
non-FIFO edge becomes FIFO-equivalent if waiting at its tail is allowed. Dean's
technical report (MIT, 2004) *UNVERIFIED — not opened; cited via Foschini et al.*
is the standard treatment of algorithms for the FIFO case. Foschini et al. also
settle Dean's conjecture: with piecewise-linear costs the s–d shortest path can
change n^Θ(log n) times over a day, yet a minimum-delay path for any departure
interval is still polynomial.

Ziliaskopoulos & Mahmassani (1993, *Transportation Research Record* 1408)
*[opened]* is the classic **discrete-time label-correcting** formulation: paths from
all nodes to one destination for every time step, working backwards from the
destination, and — the point that matters here — handling costs that are *not*
travel time.

**Why a closing hazard makes this time-dependent with waiting semantics.** Edge
*travel time* is fixed (length ÷ speed), so the travel-time network is trivially
FIFO; what varies is the **cost** (P × tt) and the **feasibility** (the `p_cut`
gate). A gate closing at T is an edge whose delay jumps to ∞ at T. Because the
hazard is monotone non-decreasing, leaving earlier is always at least as good, so
"waiting never helps" holds and the router is right not to model waiting. If the
field were ever non-monotone (a burned-out cell reopening — which the cumulative
envelope forbids), a "stay" edge would be needed. And the Ziliaskopoulos–Mahmassani
point that cost ≠ travel time breaks the earliest-arrival ordering is exactly why
`routing_limitations.md` §4 cannot claim optimality over exact clocks: two labels at
one `(node, bin)` can differ in exposure and clock, and the cheaper one is not
necessarily the one that keeps downstream gates open.

### 1.3 Time-expanded versus time-aggregated graphs

The **time-expanded** graph copies every node for every time step and connects
`(u, t)` → `(v, t + τ)`; the **time-aggregated / time-dependent** graph keeps one
copy of each node and stores a delay *function* per edge. Köhler, Langkau &
Skutella (ESA 2002, LNCS 2461) *[metadata only]* use time-expanded graphs for flows
over time with flow-dependent transit times and show the quickest-flow problem
becomes NP-hard once transit times depend on inflow. Hamacher & Tjandra (2001,
*Pedestrian and Evacuation Dynamics*) *UNVERIFIED — metadata from search only*
survey macroscopic (dynamic network flow, lower bounds on clearance time) versus
microscopic (individual movement) evacuation models, both time-parametrised.

**Relevance.** The `(node, time_bin)` state *is* a lazily built time-expanded
graph, and the 10-min ceil-rounded bin is its resolution choice, with a known
conservative bias. The time-aggregated alternative — evaluate the hazard at the
*exact* arrival time — would remove the quantisation artefact reproduced in
`routing_limitations.md` §1 (an origin lands in `fa_exceeds_budget` because a bin,
not the budget, blocks every detour), at the cost of O(1) lookups.

---

## 2. Evacuation modelling

### 2.1 Trigger buffers: the Cova/Dennison/Li line and WUIVAC

Cova, Dennison, Kim & Moritz (2005, *Transactions in GIS* 9(4): 603–617)
*[metadata only; abstract via search]* introduced **evacuation trigger points**:
given an estimated evacuation time for a community, run fire spread *backwards*
from the asset so that a fire crossing the buffer's edge means "evacuate now"
(case: 1996 Calabasas Fire, Malibu). Dennison, Cova & Moritz (2007, *Natural
Hazards* 41: 181–199) formalised this as **WUIVAC** using Finney's minimum-travel-
time fire-spread method *[cited from the reference list of Li et al. 2019, opened;
not itself opened]*. Fryer, Dennison & Cova (2013, *IJWF* 22(7): 883–893)
*[opened, PDF]* applied WUIVAC to **firefighter** escape: trigger buffers for
evacuation on foot, by engine and by dozer on the 2007 Zaca Fire; on-foot travel at
0 % slope was set to 90 m/min (1.5 m/s), and *evacuation travel time was the single
most important determinant of buffer size*. Li, Cova & Dennison (2015, *CEUS* 54:
56–67) *[metadata only]* moved triggers to the **household level** (Julian, CA);
Li, Cova & Dennison (2019, *Fire Technology* 55: 617–642) *[opened, PDF]* replaced
expert-judged evacuation time with **traffic simulation** and produced
probability-based buffers — in Julian, 95 % of residents reached safety in 160 min
in one demand scenario and 292 min when demand doubled.

**Relevance.** `margins.py`'s withdrawal trigger line is the same object on a
probabilistic field, snapped down to the containing slice. Fryer's and Li's lesson
is uncomfortable: buffer size is dominated by the *travel-time* term, and the
project's is set by assumed values (0.7 m/s, 30-min dispatch delay, `t_load`), not
observed movement. Li 2019's move from a point estimate to a distribution is the
natural upgrade path.

### 2.2 Fire-arrival-time evacuation and the shelter/rescue option

Cova, Drews, Siebeneck & Musters (2009, *Natural Hazards Review* 10(4): 151–162)
*[metadata only]* give the typology of protective actions (evacuate, shelter-in-
refuge, shelter-in-home) and the distinction between shelter as a *backup* when
evacuation is too risky and shelter to protect the structure. Cova, Dennison &
Drews (2011, *Sustainability* 3(10): 1662) *[abstract opened via S2]* cast community
protection as **assigning households to one of three actions** under available
time, expected intensity and shelter quality — evacuation protects most, *except*
when time is short. Blanchi et al. (2014, *Environmental Science & Policy* 37:
192–203) *[abstract opened via S2]* built the 1901–2011 Australian fatality
database; a search snippet attributes 48.3 % of analysed civilian deaths to **late
evacuation** and most deaths to within 100 m of home *(percentages UNVERIFIED
against the full text)*. Whittaker et al. (2017, *IJDRR*, sheltering on Black
Saturday) *UNVERIFIED — not opened*.

**Relevance.** This licenses the four-way rescue split (`rescue_routing.md` §4):
"no safe pedestrian route but a responder can reach" is the *be-rescued* action and
"no surviving vehicle ingress" is the residual Cova et al. say must be planned for.
The late-evacuation fatality pattern is why a fire-blind shortest path is the right
*baseline* and the paired contrast the right *claim*.

### 2.3 Elderly walking speed and slope

Bohannon & Andrews (2011, *Physiotherapy* 97(3): 182–189) *[opened, CSP abstract
page]*: meta-analysis of 41 studies / 23,111 healthy adults; comfortable gait speed
declines with age, fastest stratum men 40–49 at 143.4 cm/s, slowest women 80–99 at
94.3 cm/s. Studenski et al. (2011, *JAMA* 305(1): 50–58) *[abstract opened via S2]*
pooled nine cohorts (34,485 community-dwelling adults ≥65): gait speed predicts
survival, and the abstract places a speed of about 0.8 m/s at median life
expectancy for age and sex — i.e. 0.7 m/s already sits in the frailer half of the
older population, not at its centre. Fujiyama & Tyler (2010, *Transportation
Planning and Technology* 33(2): 177–202) *[opened, UCL e-print]* predict walking
speed on stairs from body weight, **leg extensor power** and gradient — the
mechanism by which age reduces speed on slopes more than on the flat.

**Slope functions.** Tobler's hiking function (1993, NCGIA TR 93-1) *[metadata
only; formula confirmed on Wikipedia, opened]*: W = 6·exp(−3.5·|S + 0.05|) km/h,
peaking at ≈6 km/h on a slight downgrade (≈−2.86°) and ≈5 km/h on the flat, fitted
to Imhof's (1950) Swiss hiking data. **Naismith's rule** (1892; Scarf 2007,
*J. Sports Sciences* 25(6): 719–726 *[abstract opened via S2]*): 1 m of climb costs
about 7.92 m of horizontal travel; Scarf's fell-running data support ≈1:8 for men
and ≈1:10 for women. Campbell, Dennison, Butler & Page (2019, *Applied Geography*
106: 93–107) *[opened, PDF]* fitted 421,247 Strava hikes/runs from 29,928 people
and found Tobler/Naismith rest on tiny samples and assume symmetry; a **Lorentz**
(Cauchy-shaped) function with an uphill/downhill asymmetry term fits best
(percentile models R² ≈ 0.958, MAE 0.078 m/s), and the fit is *better at low
percentiles* — slow walkers are more consistent than fast runners — which is
exactly the population the project models.

**Relevance.** The project keeps Tobler's *shape* rescaled to 0.7 m/s. A **low
percentile** (5th–10th) of Campbell et al.'s model is a frail-walker curve with an
empirical basis, and it is asymmetric where Tobler's |S + 0.05| is not.
`slope_integration.md` found slope added +28.1 % uphill / +25.1 % downhill to
walking time (longest walk 283 → 444 min) yet moved one origin on the canonical
field — a statement about hazard geometry versus budget, not about slope functions;
an asymmetric curve is the cleaner sensitivity arm.

### 2.4 ASET/RSET transferred to landscape scale

Building fire engineering compares **ASET** (time until untenable conditions)
with **RSET** (detection + notification + pre-movement + movement). Averill, Reneke
& Peacock (NIST, c. 2008) *[opened, PDF; year inferred]* argue RSET inputs should be
distributions and outputs CDFs. The landscape transfer is explicit in the WUI-NITY
line: Ronchi, Gwynne, Rein, Intini & Wadhwani (2019, *Safety Science*
118: 868–880) *[abstract opened via S2]* define the three coupled layers (wildfire,
pedestrian, traffic); Wahlqvist et al. (2021, *Safety Science* 136: 105145)
*[abstract opened via S2]* deliver the platform; Kuligowski, Ronchi, Wahlqvist,
Gwynne, Kinateder, Rein, Mitchell, Bénichou & Kimball (2022, *Australian Journal of
Emergency Management*) *[opened, PDF]* describe the **PERIL** trigger-buffer tool
that places the buffer where fire arrival equals the wildfire-RSET plus a safety
factor, on a generic notification → pre-evacuation → movement timeline; Mitchell,
Gwynne, Ronchi, Kalogeropoulos & Rein (2023, *Safety Science* 157: 105914)
*[metadata only]* apply PERIL to two rural communities; PERIL's code is open
(Mitchell & Rein 2020, Zenodo, CC-BY-4.0) *[opened]*. Ronchi et al. (2023, *Natural Hazards*) *[abstract opened via S2]* publish a
**24-test verification protocol** for such models. Pishahang et al. (PSAM16, 2022,
WISE) *[opened, PDF]* compute ASET from fire dynamics and RSET from a Bayesian
network, reporting a *probability* of successful evacuation.

**Relevance.** `_time_to_cutoff` is an ASET quantised to the slice grid (an upper
bound, `routing_limitations.md` §3); the resident RSET is walk time with **no
pre-movement term** (responders get a 30-min delay). Every model in this line has
one; it is the largest unmodelled RSET component and belongs in a sensitivity arm.
Ronchi et al.'s verification tests are a template for `test_margins.py`-style pins.

---

## 3. Routing under uncertainty

### 3.1 Objectives: shortest time vs exposure vs reliability

Erkut & Verter (1998, *Operations Research* 46(5): 625–642) *[metadata only]*
compared hazmat risk models — expected consequence, population exposure,
incident probability, conditional risk — and showed on the US network that
**different risk objectives pick different "optimal" paths**; the path-integral
"exposure" objective (sum over edges of probability × population or time) is one
member of that family. Nie & Wu (2009, *Transportation Research B*) *[metadata
only]* define the **reliable shortest path**: maximise the probability of arriving
within a time budget (the SPOTAR family), one of three stochastic paradigms
alongside least-expected-time and α-reliable paths. Shirdel & Abdolhosseinzadeh
(2016, *SpringerPlus* 5: 1529) *[opened]* treat an **unstable topology**: each arc
has a probability of being traversable, and the objective is the *arrival
probability* of the path, computed as an absorbing Markov chain. Bertsimas & Sim
(2003, *Mathematical Programming* 98: 49–71) *[metadata only]* give **robust**
shortest paths under budgeted interval uncertainty (Γ arcs may take their worst
value), solvable with n+1 nominal shortest-path calls.

### 3.2 Forecast probability as edge cost versus hard cutoff

The literature offers three ways to consume a P(ignite) field: (a) as a **cost**
(exposure integral, the project's objective), (b) as a **constraint** (hard cutoff
`p_cut`, the project's gate — a chance constraint on each visited node), (c) as a
**reliability objective** (maximise the probability the whole path stays
passable, which under independence is Π(1 − p) along the path, i.e. minimise
Σ −log(1 − p), a *different* additive cost from Σ p·tt). The project uses (a) + (b), the standard hazmat compromise, with a failure mode
it has already met: the gate is a **threshold on a survival time**, and thresholds
amplify — `network_drift.md` saw a 0.05 % network change move
`no_surviving_vehicle_ingress` from 24 to 32 while the paired exposure contrast
moved 0.56 pp. Bertsimas & Sim's Γ and Nie & Wu's on-time probability exist to
tame exactly this: report how much would have to go wrong for a verdict to flip.
Cheap additions on committed data: a log-survival cost arm scored by the same
`_evaluate_path`, and a slack-to-cutoff column beside each binary bucket.

---

## 4. Rescue and dispatch

Solomon (1987, *Operations Research* 35(2): 254–265) *[metadata only]* is the root
of the **VRPTW** literature: customers with time windows, capacity constraints,
insertion heuristics that perform robustly, and the "latest feasible start"
propagation that underlies every time-window feasibility check (a visit is feasible
iff arrival ≤ latest start, with latest starts propagated backwards from the
deadline). Jagtenberg, Bhulai & van der Mei (2017, *Health Care Management
Science* 20: 517–531) *[metadata only; abstract via search]* asked whether the
**closest-idle** ambulance rule is optimal: for a Dutch EMS region an MDP-derived
heuristic cut late arrivals by 18 % but *raised mean response time by 37 %* — the
ordering rule that wins depends on whether you minimise mean response or the
fraction missing a deadline. Cova & Johnson (2003, *Transportation Research A*
37(7): 579–604) *[opened, PDF]* formulate **lane-based evacuation routing** as an
integer minimum-cost flow trading travel distance against merging conflicts —
the network-flow (capacity-aware) side of evacuation routing.

**Relevance.** `dispatch_ordering.md` found closing-window ordering beats
nearest-first in 3.6 % of 360 configurations, ties in 36.7 %, loses in 59.7 %, and
wins only at W = 240, never at the committed W = 75 — because at W = 75 almost every
home shares a deadline (2–6 distinct per region), so distance decides. That is
Jagtenberg's finding in miniature. Two moves on committed data: (i) treat dispatch
as **VRPTW feasibility** — Solomon-style latest feasible departures from
`ingress_survival_time`, reporting the set infeasible under *any* ordering; (ii)
score orderings on deadline misses and mean response separately, since they
disagree.

---

## 5. Shelter and refuge location

Hakimi (1964, *Operations Research* 12(3): 450–459) *[metadata only]*: the
**p-median** — locate p facilities minimising total weighted distance; optimal
sites lie on nodes. Church & ReVelle (1974, *Papers in Regional Science* 32:
101–118) *[metadata only]*: the **maximal covering location problem** — with a
fixed number of facilities, maximise the demand within a coverage radius/time.
Steer, Abebe, Almashor, Beloglazov & Zhong (2017, *Fire Safety Journal*, IBM
Research) *[opened, IBM abstract page]* simulated 64 shelter configurations under
three fire scenarios in the Dandenong Ranges: some cut median exposure by up to
10 %, **others increased it**, and the effect depended on shelter position relative
to ignition and fire progression — i.e. refuge value is scenario-dependent and can
be negative. Butler (2014, *IJWF* 23(3): 295–308) *[opened, NWFSC abstract]*
reviews firefighter **safety zones**: guidance rests on flat-terrain radiant-heat
assumptions, entrapments typically occur within about two flame heights, and
convective heating on slopes is under-represented. Australian **Neighbourhood
Safer Places / Bushfire Places of Last Resort** are designated by fire agencies
against radiant-heat and access criteria and are framed as *last resort, no
guarantee of safety, travel to them may itself be dangerous* (NSW RFS, CFA and EMV
pages *UNVERIFIED — all returned HTTP 403 in this lap*).

**Relevance.** The project takes OSM refuge POIs as given and asks which survive.
Steer et al. mean "rescue-reachable refuge exists" ≠ "refuge lowers risk for this
origin" — the b→c contrast (`rescue_routing.md` §3) measures the latter. The MCLP
frame recasts the 32.6 % coverage caveat (`walk_bbox_coverage.md`) as *which*
origins are covered within a walk budget, which the scans already answer.

---

## 6. Data realities: OpenStreetMap, osmnx, drift

**Completeness.** Barrington-Leigh & Millard-Ball (2017, *PLOS ONE* 12(8):
e0180698) *[opened]* estimate the global OSM road network ≈83 % complete (95 % CI
81–84 %), with over 40 % of countries fully mapped; completeness is *highest at low
and high densities* and worst in **small towns and villages** — the settlement
class WildfireGuardian's origins live in; the measure counts geometry only, not
attributes. No South-Korea-specific figure is given there, and no peer-reviewed
Korea-specific road-completeness paper was found in this lap. The OpenCage
interview with a Korean mapper (2021-11-29) *[opened]* reports residential roads
"nearly complete" with names, railways very detailed, but only ≈7.6 % of buildings
mapped, in part because government building footprints cannot legally be exported;
Naver/Kakao dominance suppresses contribution. Kontur's road-completeness layer
*[opened]* is a heuristic (OSM length ÷ (OSM + AI-detected roads), regression where
AI roads are missing) — usable as a *prior*, not as ground truth.

**Graph building.** Boeing (2017, *CEUS* 65: 126–139) *[opened, arXiv]* and Boeing
(2025, *Geographical Analysis* 57(4): 567–577) *[opened, arXiv]* document osmnx: the
`network_type` presets (`walk`, `drive`, `drive_service`, `bike`, `all`,
`all_public`) are **different Overpass tag filters**, so a walk graph and a drive
graph over the same bbox are different graphs, not views of one; `simplify_graph`
removes non-intersection nodes while keeping edge geometry;
`consolidate_intersections` merges nearby nodes by tolerance; `nearest_nodes` /
`nearest_edges` snap points by k-d/ball tree (OSMnx 2.1.1 user reference,
*[opened]*). **Snapping** a footprint centroid to the nearest node is the usual origin
construction; practitioner sources treat snap distance as a quality flag and
densify long edges (nodes ≤20 m apart) before snapping *(secondary sources only;
UNVERIFIED as a peer-reviewed recommendation)*.

**Reproducibility and drift.** Because OSM is edited continuously, a re-download
is a *different dataset*. Two mechanisms exist to pin it: osmnx's
`settings.overpass_settings` accepts an Overpass `[date:"…"]` attic query for a
historical snapshot *[opened, OSMnx docs]*, and Geofabrik publishes **dated
extracts** for South Korea (`south-korea-YYMMDD.osm.pbf`, monthly from 2015 and
daily recent) *[opened]*. `DATA_LOSS_2026-07-24.md` / `network_drift.md` record the 2026-07-19 graphs being
overwritten and the 2026-07-24 graphs preserved under `data/snapshots/` with
sha256. The literature's standard — snapshot + hash + date — is now the project's
practice.

---

## 7. What this means for WildfireGuardian

### 7.1 Sourced insights

1. **The router is a time-expanded shortest path on a monotone-closing network,
   and that is why "no waiting" is safe** (Orda & Rom via Foschini et al. 2011;
   Ziliaskopoulos & Mahmassani 1993). State that in the paper: monotone hazard ⇒
   FIFO-equivalent ⇒ waiting never helps ⇒ Dijkstra over `(node, bin)` is valid
   *up to the bin/clock issue already recorded in `routing_limitations.md` §4*.
2. **Cost ≠ travel time is the known source of the non-optimality caveat**
   (Ziliaskopoulos & Mahmassani 1993). It is a literature-recognised property, not
   a project bug; cite it rather than apologise for it.
3. **Bin quantisation is a time-expansion resolution choice** (Köhler et al. 2002
   framing). The `fa_exceeds_budget` misnomer in `routing_limitations.md` §1 is a
   quantisation artefact the time-aggregated formulation would not produce.
4. **Evacuation-time assumptions dominate trigger geometry** (Fryer et al. 2013;
   Li et al. 2019). The project's 0.7 m/s, 30-min dispatch delay and `t_load` are
   the load-bearing assumptions; the literature's remedy is distributions, not
   better point values.
5. **0.7 m/s is a frail-half speed, not a median** (Bohannon & Andrews 2011;
   Studenski et al. 2011). Defensible for the target population; say so with the
   strata, and note it is a *comfortable* speed, not an emergency speed.
6. **Slope functions with an empirical low-percentile basis exist** (Campbell et
   al. 2019). An asymmetric Lorentz curve at the 5th–10th percentile is a better
   "frail walker" arm than a rescaled Tobler.
7. **Residents have no pre-movement term** — every ASET/RSET model in the WUI line
   includes one (Averill et al.; Kuligowski et al. 2022; Pishahang et al. 2022).
   This is the largest unmodelled RSET component.
8. **Thresholds amplify; contrasts do not** — the project's `network_drift.md`
   result is the reliable/robust-path literature's motivation (Nie & Wu 2009;
   Bertsimas & Sim 2003). Report slack-to-cutoff with every binary verdict.
9. **Deadline-aware dispatch only pays when deadlines differ and the objective is
   misses** (Jagtenberg et al. 2017). `dispatch_ordering.md`'s negative result is
   the expected one at W = 75; the ordering-free VRPTW feasibility statement is
   what the data can support.
10. **Refuge value can be negative** (Steer et al. 2017). The b→c contrast, not
    refuge existence, is the claim.

### 7.2 Candidate backlog items (testable on committed data; no re-acquisition of
Yeongdeok OSM; no change to committed artifacts before the 2026-10-16 freeze)

Each is a *new* artifact under a new filename on the committed snapshots and
canonical field, with its paired contrast stated up front.

- **B1 — Exact-time vs binned gate.** How many of the 458 canonical Yeongdeok
  origins change bucket if the `p_cut` gate is evaluated at the exact interpolated
  arrival time instead of the ceil-rounded 10-min bin, all else fixed?
  (`routing_limitations.md` §1 predicts a small non-zero set; §1.3 above.) Tags:
  **before-freeze** (sensitivity arm, not a default change), **for-the-paper**.
- **B2 — Log-survival cost arm.** Does minimising Σ −log(1 − p)·tt (§3.2) pick
  different routes than Σ p·tt, and by how much does *reported* exposure (same
  `_evaluate_path`) differ per origin? Tags: **after-finals**, **for-the-paper**
  (Erkut & Verter's "different risk models, different paths" on this field).
- **B3 — Resident pre-movement delay sweep.** With a pre-evacuation delay of
  {5, 10, 20, 30} min before departure (§2.4), how do the three-bucket counts and
  the FA-only share move? A table mirroring `budget_sweep.md`. Tags:
  **before-freeze** if time allows (sensitivity only), **for-the-paper**.
- **B4 — Frail-walker slope curve.** Replacing elderly-scaled Tobler with a
  Campbell et al. (2019) low-percentile Lorentz curve at the same 0.7 m/s flat
  speed, does the one-origin slope null in `slope_integration.md` survive?
  Coefficients must be transcribed from the paper's tables first. Tags:
  **after-finals**, **for-the-paper**.
- **B5 — Slack-to-cutoff beside every binary verdict.** For each
  `no_surviving_vehicle_ingress` / `no_safe_route` origin in the committed rescue
  artifact, what is the signed slack (corridor survival − (ETA + margin)) and how
  many sit within one slice spacing of the threshold? Computed from values already
  in the artifact, no re-routing (§3.2). Tags: **before-freeze** (judge Q&A),
  **for-the-paper**.
- **B6 — Ordering-free dispatch infeasibility set.** With Solomon-style latest
  feasible departures from the committed `ingress_survival_time` / ETA values,
  which homes are infeasible under *every* ordering at W = 75 and W = 240, and does
  that set match the committed unreachable set? Tags: **after-finals**,
  **for-the-paper** (replaces the weak ordering claim with a feasibility one).

---

## References

Graph and time-dependent routing

- Bast, H., Delling, D., Goldberg, A., Müller-Hannemann, M., Pajor, T., Sanders, P., Wagner, D., Werneck, R. F. (2016). Route Planning in Transportation Networks. *Algorithm Engineering*, LNCS 9220, 19–80. https://arxiv.org/abs/1504.05140 *[opened]*
- Geisberger, R., Sanders, P., Schultes, D., Delling, D. (2008). Contraction Hierarchies: Faster and Simpler Hierarchical Routing in Road Networks. *WEA 2008*, LNCS 5038. https://link.springer.com/chapter/10.1007/978-3-540-68552-4_24 *[metadata only, via Semantic Scholar DOI record]*
- Orda, A., Rom, R. (1990). Shortest-path and minimum-delay algorithms in networks with time-dependent edge-length. *Journal of the ACM* 37(3), 607–625. https://dl.acm.org/doi/10.1145/79147.214078 *[metadata only — ACM page 403; content via Foschini et al. 2011]*
- Dean, B. C. (2004). Shortest paths in FIFO time-dependent networks: theory and algorithms. MIT technical report. https://www.semanticscholar.org/paper/4d8f5396656789ad766333e90bc25912476b06a9 *UNVERIFIED — not opened*
- Foschini, L., Hershberger, J., Suri, S. (2011). On the Complexity of Time-Dependent Shortest Paths. *SODA 2011*. https://sites.cs.ucsb.edu/~suri/psdir/soda11.pdf *[opened, PDF]*
- Ziliaskopoulos, A. K., Mahmassani, H. S. (1993). Time-Dependent, Shortest-Path Algorithm for Real-Time Intelligent Vehicle Highway System Applications. *Transportation Research Record* 1408, 94–100. https://onlinepubs.trb.org/Onlinepubs/trr/1993/1408/1408-012.pdf *[opened, PDF]*
- Köhler, E., Langkau, K., Skutella, M. (2002). Time-Expanded Graphs for Flow-Dependent Transit Times. *ESA 2002*, LNCS 2461, 599–611. https://link.springer.com/chapter/10.1007/3-540-45749-6_53 *[metadata only]*
- Hamacher, H. W., Tjandra, S. A. (2001). Mathematical Modelling of Evacuation Problems: A State of the Art. In *Pedestrian and Evacuation Dynamics*, 227–266. https://kluedo.ub.rptu.de/frontdoor/index/index/docId/1477 *UNVERIFIED — search metadata only*

Evacuation modelling

- Cova, T. J., Dennison, P. E., Kim, T. H., Moritz, M. A. (2005). Setting Wildfire Evacuation Trigger Points Using Fire Spread Modeling and GIS. *Transactions in GIS* 9(4), 603–617. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9671.2005.00237.x *[metadata only — Wiley 403; abstract via search]*
- Dennison, P. E., Cova, T. J., Moritz, M. A. (2007). WUIVAC: a wildland-urban interface evacuation trigger model applied in strategic wildfire scenarios. *Natural Hazards* 41(1), 181–199. *[cited from Li et al. 2019 reference list; not opened]*
- Fryer, G. K., Dennison, P. E., Cova, T. J. (2013). Wildland firefighter entrapment avoidance: modelling evacuation triggers. *IJWF* 22(7), 883–893. https://content.csbs.utah.edu/~pdennison/reprints/denn/2013_Fryer_etal_IJWF.pdf *[opened, PDF]*; catalogue https://www.frames.gov/catalog/52343 *[opened]*
- Li, D., Cova, T. J., Dennison, P. E. (2015). A household-level approach to staging wildfire evacuation warnings using trigger modeling. *CEUS* 54, 56–67. https://www.sciencedirect.com/science/article/abs/pii/S0198971515000629 *[metadata only]*
- Li, D., Cova, T. J., Dennison, P. E. (2019). Setting Wildfire Evacuation Triggers by Coupling Fire and Traffic Simulation Models: A Spatiotemporal GIS Approach. *Fire Technology* 55, 617–642. https://content.csbs.utah.edu/~pdennison/reprints/denn/2019_li_etal_ft.pdf *[opened, PDF]*
- Cova, T. J., Drews, F. A., Siebeneck, L. K., Musters, A. (2009). Protective Actions in Wildfires: Evacuate or Shelter-in-Place? *Natural Hazards Review* 10(4), 151–162. https://www.frames.gov/catalog/15454 *[metadata only]*
- Cova, T. J., Dennison, P. E., Drews, F. A. (2011). Modeling Evacuate versus Shelter-in-Place Decisions in Wildfires. *Sustainability* 3(10), 1662–1687. https://www.mdpi.com/2071-1050/3/10/1662 *[abstract opened via Semantic Scholar; MDPI page 403]*
- Cova, T. J., Johnson, J. P. (2003). A network flow model for lane-based evacuation routing. *Transportation Research Part A* 37(7), 579–604. https://www.redfish.com/projects/SFWildfire/papers/cova-johnson-2003.pdf *[opened, PDF]*
- Cova, T. J., Church, R. L. (1997). Modelling Community Evacuation Vulnerability Using GIS. *IJGIS* 11(8), 763–784. *[metadata only]*
- Blanchi, R., Leonard, J., Haynes, K., Opie, K., James, M., Dimer de Oliveira, F. (2014). Environmental circumstances surrounding bushfire fatalities in Australia 1901–2011. *Environmental Science & Policy* 37, 192–203. https://www.sciencedirect.com/science/article/pii/S1462901113002074 *[abstract opened via Semantic Scholar; the 48.3 % late-evacuation figure is from a search snippet — UNVERIFIED]*
- Whittaker, J., et al. (2017). Experiences of sheltering during the Black Saturday bushfires. *IJDRR*. https://www.sciencedirect.com/science/article/abs/pii/S221242091730050X *UNVERIFIED — not opened*
- Bohannon, R. W., Andrews, A. W. (2011). Normal walking speed: a descriptive meta-analysis. *Physiotherapy* 97(3), 182–189. https://www.csp.org.uk/journal/article/physiotherapy-september-2011/normal-walking-speed-descriptive-meta-analysis *[opened]*
- Studenski, S., et al. (2011). Gait Speed and Survival in Older Adults. *JAMA* 305(1), 50–58. https://pubmed.ncbi.nlm.nih.gov/21205966/ *[abstract opened via Semantic Scholar]*
- Fujiyama, T., Tyler, N. (2010). Predicting the walking speed of pedestrians on stairs. *Transportation Planning and Technology* 33(2), 177–202. https://discovery.ucl.ac.uk/id/eprint/145191/1/Fujiyama_WalkingSpeed.pdf *[opened, PDF]*
- Tobler, W. (1993). Three Presentations on Geographical Analysis and Modeling. NCGIA Technical Report 93-1. https://escholarship.org/uc/item/05r820mz *[metadata only]*; formula confirmed at https://en.wikipedia.org/wiki/Tobler%27s_hiking_function *[opened]*
- Scarf, P. (2007). Route choice in mountain navigation, Naismith's rule, and the equivalence of distance and climb. *J. Sports Sciences* 25(6), 719–726. https://pubmed.ncbi.nlm.nih.gov/17454539/ *[abstract opened via Semantic Scholar]*
- Campbell, M. J., Dennison, P. E., Butler, B. W., Page, W. G. (2019). Using crowdsourced fitness tracker data to model the relationship between slope and travel rates. *Applied Geography* 106, 93–107. https://content.csbs.utah.edu/~pdennison/reprints/denn/2019_Campbell_etal_AG.pdf *[opened, PDF]*
- Averill, J. D., Reneke, P., Peacock, R. D. (c. 2008). Required Safe Egress Time: Data and Modeling. 7th Int. Conf. on Performance-Based Codes and Fire Safety Design Methods (NIST). https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=913098 *[opened, PDF; year inferred]*
- Ronchi, E., Gwynne, S. M. V., Rein, G., Intini, P., Wadhwani, R. (2019). An open multi-physics framework for modelling wildland-urban interface fire evacuations. *Safety Science* 118, 868–880. https://doi.org/10.1016/j.ssci.2019.06.009 *[abstract opened via Semantic Scholar]*
- Wahlqvist, J., Ronchi, E., Gwynne, S. M. V., Kinateder, M., Rein, G., Mitchell, H., Kuligowski, E. (2021). The simulation of wildland-urban interface fire evacuation: The WUI-NITY platform. *Safety Science* 136, 105145. https://www.sciencedirect.com/science/article/pii/S0925753520305415 *[abstract opened via Semantic Scholar; publisher 403]*
- Kuligowski, E., Ronchi, E., Wahlqvist, J., Gwynne, S. M. V., Kinateder, M., Rein, G., Mitchell, H., Bénichou, N., Kimball, A. (2022). Evacuation modelling for bushfire: the WUI-NITY simulation platform. *Australian Journal of Emergency Management*. https://knowledge.aidr.org.au/media/9660/ajem-13-2022-04.pdf *[opened, PDF]*
- Mitchell, H., Gwynne, S., Ronchi, E., Kalogeropoulos, N., Rein, G. (2023). Integrating wildfire spread and evacuation times to design safe triggers: Application to two rural communities using PERIL model. *Safety Science* 157, 105914. https://www.sciencedirect.com/science/article/pii/S0925753522002533 *[metadata only]*
- Mitchell, H., Rein, G. (2020). Matlab Code for PERIL (Population Evacuation tRigger aLgorithm). Zenodo, CC-BY-4.0. https://zenodo.org/records/4106654 *[opened]*
- Ronchi, E., Wahlqvist, J., Ardinge, A., Rohaert, A., Gwynne, S. M. V., Rein, G. (2023). The verification of wildland–urban interface fire evacuation models. *Natural Hazards*. https://link.springer.com/article/10.1007/s11069-023-05913-2 *[abstract opened via Semantic Scholar]*
- Pishahang, M., Ruiz-Tagle, A., Lopez Droguett, E., Ramos, M., Mosleh, A. (2022). WISE: A Probabilistic Wildfire Safe Egress Planning Framework and Software Platform. *PSAM16*. https://www.iapsam.org/PSAM16/papers/MH163-PSAM16.pdf *[opened, PDF]*
- Zehra, S. N., Wong, S. D. (2024). Systematic review and research gaps on wildfire evacuations: infrastructure, transportation modes, networks, and planning. *Transportation Planning and Technology*. https://doi.org/10.1080/03081060.2024.2348713 *[abstract opened via Semantic Scholar; publisher 403]*

Uncertainty, dispatch, location

- Erkut, E., Verter, V. (1998). Modeling of Transport Risk for Hazardous Materials. *Operations Research* 46(5), 625–642. https://pubsonline.informs.org/doi/10.1287/opre.46.5.625 *[metadata only]*
- Nie, Y., Wu, X. (2009). Shortest path problem considering on-time arrival probability. *Transportation Research Part B* 43(6), 597–613. https://doi.org/10.1016/j.trb.2009.01.008 *[metadata only]*
- Shirdel, G. H., Abdolhosseinzadeh, M. (2016). The shortest path problem in the stochastic networks with unstable topology. *SpringerPlus* 5, 1529. https://pmc.ncbi.nlm.nih.gov/articles/PMC5020038/ *[opened]*
- Bertsimas, D., Sim, M. (2003). Robust discrete optimization and network flows. *Mathematical Programming* 98, 49–71. https://link.springer.com/article/10.1007/s10107-003-0396-4 *[metadata only]*
- Solomon, M. M. (1987). Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints. *Operations Research* 35(2), 254–265. https://doi.org/10.1287/opre.35.2.254 *[metadata only]*
- Jagtenberg, C. J., Bhulai, S., van der Mei, R. D. (2017). Dynamic ambulance dispatching: is the closest-idle policy always optimal? *Health Care Management Science* 20, 517–531. https://pubmed.ncbi.nlm.nih.gov/27206518/ *[metadata only]*
- Hakimi, S. L. (1964). Optimum Locations of Switching Centers and the Absolute Centers and Medians of a Graph. *Operations Research* 12(3), 450–459. *[metadata only]*
- Church, R., ReVelle, C. (1974). The maximal covering location problem. *Papers in Regional Science* 32(1), 101–118. https://link.springer.com/article/10.1007/BF01942293 *[metadata only]*
- Steer, K., Abebe, E., Almashor, M., Beloglazov, A., Zhong, X. (2017). On the utility of shelters in wildfire evacuations. *Fire Safety Journal*. https://research.ibm.com/publications/on-the-utility-of-shelters-in-wildfire-evacuations *[opened]*
- Butler, B. W. (2014). Wildland firefighter safety zones: a review of past science and summary of future needs. *IJWF* 23(3), 295–308. https://nwfirescience.org/biblio/wildland-firefighter-safety-zones-review-past-science-and-summary-future-needs *[opened]*
- NSW Rural Fire Service — Neighbourhood Safer Places guidelines. https://www.rfs.nsw.gov.au/plan-and-prepare/neighbourhood-safer-places *UNVERIFIED — 403*; CFA Victoria https://www.cfa.vic.gov.au/plan-prepare/your-local-area-info-and-advice/neighbourhood-safer-places *UNVERIFIED — 403*

Data realities

- Barrington-Leigh, C., Millard-Ball, A. (2017). The world's user-generated road map is more than 80% complete. *PLOS ONE* 12(8), e0180698. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0180698 *[opened]*
- Boeing, G. (2017). OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks. *CEUS* 65, 126–139. https://arxiv.org/abs/1611.01890 *[opened]*
- Boeing, G. (2025). Modeling and Analyzing Urban Networks and Amenities with OSMnx. *Geographical Analysis* 57(4), 567–577. https://arxiv.org/abs/2505.00736 *[opened]*
- OSMnx 2.1.1 User Reference (network_type presets, nearest_nodes, simplify_graph, consolidate_intersections, overpass_settings date). https://osmnx.readthedocs.io/en/stable/user-reference.html *[opened]*
- OpenCage (2021-11-29). Interview: OpenStreetMap in Korea. https://blog.opencagedata.com/post/openstreetmap-in-korea *[opened]*
- Kontur Inc. Measuring Completeness of Road Network in OpenStreetMap (blog, undated). https://www.kontur.io/blog/osm-road-completeness/ *[opened]*
- Geofabrik. South Korea extracts (dated `south-korea-YYMMDD.osm.pbf`). https://download.geofabrik.de/asia/south-korea.html *[opened]*
- Wikipedia. 2025 South Korea wildfires (context on elderly victims and Yeongdeok port stranding; secondary). https://en.wikipedia.org/wiki/2025_South_Korea_wildfires *[opened; tertiary source, cite the underlying Korea Herald / Yonhap items instead]*

Repository documents read for §0 and §7 (not re-derived): `README.md` (TL;DR, Round 3), `docs/routing_limitations.md`, `docs/rescue_routing.md`, `docs/horizon_grounding.md`, `docs/decision_shift.md`, `docs/network_drift.md`, `docs/dispatch_ordering.md`, `docs/slope_integration.md`, `docs/walk_bbox_coverage.md`, `docs/auto/CHARTER.md` §1 and §3, and the module docstrings under `src/wildfireguardian/routing/`.
