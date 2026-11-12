# Radiant-heat side task (FIRE 6.2): assumptions and counting rules

Written 12 Nov, 11:20 UTC. The frozen policy is not edited. This is an opt-in screen only.

**Disclosure.** The 1-hour standoff table produced by `standoff.py` at `b3668b6` (11:15 UTC) was computed *before*
this plan was written, on Iris's suggestion and before the orchestrator asked for pre-registration. It is therefore
**exploratory**. The rules below are fixed now. The F-DYN counts (part 2) have not been computed and will follow
these rules exactly. Part 3 is re-run under these rules, including the window-factor sensitivity, which the
exploratory table did not have, and is reported beside the exploratory table.

## 1. One-hour panel (arithmetic, no computation)

At a contact-free (non-flaming) position, the flux bounds **add**:

- Richard's maximum in-domain non-flame flux is 0.0156 kW/m².
- The packet builder's cap on omitted outside sources is 0.703 kW/m² (`cap_W_m2` 702.991, present in the 6 windowed
  packets).
- Together they bound flux at **≤ 0.0156 + 0.703 ≈ 0.72 kW/m² < 1.0**.

So under the proposed rule (ceilings 1.0 kW/m² vulnerable and 2.5 kW/m² general, radiant term zero below threshold,
flame contact a no-go), no 1-hour verdict or deadline can change.

**The conclusion rests on two inputs.** The first is Richard's 0.0156 kW/m² non-flame figure, which Mira has not
verified. Without it, the in-domain maximum *including* flaming cells (0.7019 kW/m²) plus the cap would be 1.40 > 1.0,
and the argument would not close. The second is that flame contact is a no-go, so flaming cells never count as
positions.

(Corrected after Mira's REQUEST 5 review; earlier text presented the two bounds separately, each below 1.0.)

**Verification of the first input (Nora, 12:15 UTC, PASS WITH NOTES; ledger row 29 on `verification/nora-fire`).**
- Nora's scan covered every non-flame HAZARD.json flux value, over all members, bins and cells of the 15 one-hour
  packets.
- The maximum is 0.015545 kW/m² (Uiseong 03-25 17Z). The next largest are 0.01016 (Uljin 03-04 06Z) and 0.01004
  (Yeongdeok 03-25 19Z); all others are ≤ 0.0067.

**Scope (her note, adopted).** The statement covers the **packet's cell-binned flux model**, the one the router and
kit verdicts read. Under it, a contact-free route never reads a flame bin, so its peak is ≤ 0.0156 kW/m². The
statement does **not** bound the continuous whole-road radiation enclosure computed by the kit checker. The claim is
therefore: "a 1.0 kW/m² ceiling changes no router or kit verdict on the 1-hour panel", not a statement about physical
flux along the road.

## 2. F-DYN counts (per packet; the 4 packets and 12 requests of `../F-3.4/FDYN_PLAN.md`)

For each request, with its published route if one is published:

- **(a) Linear dose binds:** the route's certified dose upper bound is ≥ 100 kJ/m² for some member, or the
  request's verdict is a refusal or unresolved and its reason cites dose. This count is reported both per packet and
  per request.
- **(b) Physiological flux reached:** over every contact-free position of the request's published route, the
  maximum certified peak-flux upper bound reaches 1.0 kW/m² (and, separately, 2.5 kW/m²). "Position" means the
  route's own trajectory, including waits and dwell. The bound used is the kit checker's certified
  `peak_upper_kw_m2`. It is an enclosure, so the count is conservative: a count of 0 is a proof of "never reached",
  while a count > 0 can be an artefact of the enclosure.
- **(c) Packet-wide maximum flux:** the maximum over the packet's flux field (HAZARD.json, every member and
  interval) at cells containing a routed road segment, excluding cells that are flaming in that interval. This is
  reported as a packet-level number. It is an upper bound on what any contact-free route could receive at cell
  resolution, but **not** an enclosure of road-segment flux. It is labelled as cell-centre model flux.
- **Window factor.** Flux is multiplied by 1.0 by default. The factor 0.5 (window attenuation inside a vehicle) is
  reported as a labelled sensitivity only.

## 3. Standoff versus clearance (assumptions fixed here)

- **Flame.** A vertical planar face radiating to a ground-level receiver facing it, at horizontal distance d.
  Transmissivity is 1 (no smoke or attenuation). The face spans 0..H above the receiver. The configuration factor
  uses the Howell C-11 corner form summed over two half-width rectangles.
- **Ranges, all assumptions, not measurements:**
  - flame height H ∈ {5, 10, 20} m;
  - emissive power E ∈ {50, 100} kW/m²;
  - face width W ∈ {375 m (one burning cell), 3,750 m (a long front)}.
  That gives 12 combinations.
- **Thresholds:** 1.0 and 2.5 kW/m², each at window factor 1.0 (default) and 0.5 (sensitivity). The standoff is the
  d at which window × E × F(d) equals the threshold.
- **Counting rule.** A route counts as "below standoff" iff its published-route clearance (`results/CLEARANCE.jsonl`,
  `published_clearance_m`, distance from the closed flaming cell rectangle) is strictly less than the standoff.
  The count is reported for each of the 12 × 2 × 2 cases, as a range over the assumptions; no single "true" value is
  claimed. Routes whose clearance is CROP-limited are counted the same way, and the count of those is reported
  separately.
- **The same rule applies on F-DYN** to every published route there, once its clearances exist.

## 4. Follow-ups approved 11:16 UTC (Iris; orchestrator) — plan committed before results (5d88f09, 62 s before 12c32af)

These are a sensitivity range under the flame assumptions of §3, **not a count of unsafe routes**. A
clearance-based policy variant is **not** approved; nothing here changes any policy.

**4a. Time inside the standoff, and fractional dose, per published route.**
- **Positions.** Sample the route's position at every integer second of the full mission (issue, edges with linear
  timing, waits, the 120 s dwell). This is the same geometry as `clearance.py`.
- **Distance.** d(t) is the Euclidean distance to the *nearest* closed cell rectangle that is active at t (any
  member). Only the nearest source counts; the long-front width W = 3,750 m stands in for many adjacent burning cells.
- **Flux.** q(t) = window · E · F(d(t)), with the §3 flame model and the same 24 cases (12 flames × window 1.0/0.5).
- **Reported per route and case:**
  - seconds with q(t) ≥ 1.0 and seconds with q(t) ≥ 2.5 kW/m²; this equals the time inside each standoff;
  - how many of those seconds are on waits or the dwell, versus on moving edges;
  - **fractional dose FD** = Σ over seconds with q ≥ 1.0 of q^(4/3) · 1 s, divided by **80 (kW/m²)^(4/3)·s**.
- **Dose assumptions, stated.**
  - The 4/3-power "thermal dose" form and the 80 TDU threshold, the low end of the pain / first-degree-burn range
    commonly cited, are assumptions chosen here.
  - The radiant term is zero below 1.0 kW/m² (Iris's rule).
  - FD ≥ 1 is reported as "threshold dose reached under these assumptions".

**4b. Per mission: is there a route with clearance above the standoff, and what does it cost?**
- **Thresholds.** For each distinct standoff value d* in the §3 table (both thresholds and both windows, rounded up
  to the next metre), run `clearance.Instance.search(d*)`. It returns the earliest arrival over routes with clearance
  > d*, with the same opening/dwell/horizon rules.
- **Reported per mission and d*:** whether such a route exists by the horizon, and its arrival cost relative to the
  earliest arrival a(0).
- **Sound "no route" statement.** "None exists" is claimed only when `relaxed(d*)` also finds nothing, or when its
  relaxed arrival together with the opening start already exceeds the horizon deadline. Otherwise the result is
  "not found (witness search)". The † condition (present-fire expiry before the deadline) is carried over.
- **Witness checks.** Every witness route is re-checked with the unchanged full checker (`verify_witnesses.py`) and
  for exact clearance > d*.
- **Run order.** This runs after the F-DYN profile, which keeps priority on the quiet host.

## 5. Refinements from Iris (11:19 UTC) — plan committed before results (3b1b929 before 49a50b3)

**5a. Destination versus wait exposure.** The stationary seconds of 4a are split into DWELL (the required stay at the
destination) and WAIT (waits along the route). For each mission and each case, report:

- whether **the destination point itself** lies inside the 1.0 and the 2.5 kW/m² standoff at any second of the
  required stay;
- the number of such dwell seconds;
- separately, the wait seconds inside the standoffs.

Iris's destination-admissibility rule (no stay within the standoff of active fire) is evaluated as a count only. No
policy is adopted.

**5b. Three outcomes per mission and standoff in 4b.**

1. A route with clearance > d* exists to the **same** destination.
2. One exists only to **a different candidate destination**.
3. None exists. The "none" is claimed only under the soundness rule of §4b.

The frozen 1-hour requests each name exactly **one** destination, so outcome 2 cannot arise there; the panel is
reported with outcomes 1 and 3. On F-DYN, each origin has **3** candidate destinations (`INSTANCE.json`), so the
search runs once per candidate and outcome 2 is reported there.

## 6. Literature-based flame set (Sofia 11:26 UTC), added after §3; plan committed before results

The §3 grid used E 50–100 kW/m² and H 5–20 m. Sofia's reading (sources in her message to Iris and the orchestrator)
puts that range on the low side for crown fires.

**Model check.** My model reproduces her three published distances (100 m front) to within 1 m. For E76/H5,
E112/H20 and E200/H30, it gives 102.5/58.2, 263.8/163.8 and 434.9/273.1 m, against her 103/58, 264/164 and 435/273.
The receiver height (ground level or flame centre) changes these by less than 1 m.

**Second set of cases, stated as assumptions:**
- E ∈ {76 (AS 3959 surface), 112 (1200 K crown), 200 (measured crown, sensitivity)} kW/m²;
- H ∈ {5, 10, 20, 30, 40} m;
- W ∈ {100 m (rule-setting front), 3,750 m};
- receiver at flame-centre height;
- window factor 1.0 (default) and 0.5 (sensitivity);
- τ = 1;
- no convection allowance; Zárate's +20% is stated, not applied.

**Counting rule** as §3. Routes with published clearance strictly below the standoff are counted. The result is a
sensitivity range, **not a count of unsafe routes**.

**Not modelled** (Sofia's 2025 Korean cases):
- ember ignition of slow or stopped vehicles before the front arrives;
- smoke and visibility loss (road-departure deaths at Yeongyang).
A flux-only standoff does not cover either.

## 7. Surface-fire and crown-fire cases; spotting distances (orchestrator and Iris, 11:27 UTC) — plan committed before results

**7a. Standoff table with separate fire types** (Sofia's sourced ranges). This supersedes §3 and §6 as the main table;
both stay as exploratory.

**Model:** solid vertical planar flame, receiver facing it at flame-centre height, τ = 1, view factor of four corner
rectangles (H/2 × W/2).

| Case | E (kW/m²) | H (m) | W (m) |
|---|---|---|---|
| Surface fire | 76 (AS 3959) | {1, 2, 5, 10} | 100 |
| Crown fire | {112, 118} (1200 K); sensitivity {150, 200} (measured crown) | {10, 20, 30, 40, 50} | 100 |
| Long-front sensitivity | the same values | as above | 3,750 |

- Window factor 1.0 by default; 0.5 is a labelled sensitivity.
- Thresholds are 1.0 and 2.5 kW/m².
- Count rule as in §3: routes whose published clearance is strictly below the standoff.
- No convection allowance; Zárate +20% is stated only.

**7b. Spotting distance: route side.** For d ∈ {500, 1000, 2000} m:

- the number of the 15 published routes with published clearance < d;
- for each route, the seconds of its mission (integer-second positions as in §4a) spent within distance d of any
  active flaming cell rectangle, split into moving (EDGE) and stationary (WAIT + DWELL + ISSUE);
- the number of routes with stationary seconds inside d.

These are reported beside Richard's deadline-side numbers at the same d. No downwind version is attempted, because
there is no wind field.

## Validation status of the flame model (Sofia 11:48 UTC; her reading, not checked here)

No published independent comparison of a solid-flame view-factor model against flux measured 50–400 m from a
vegetation fire front was found. Measured fluxes stop at about 15 m (Morandini 2006), and crown-fire wall panels at
10–30 m give qualitative results only (Cohen 2000).

**Bias direction.** Every check found reports that a blackbody solid flame (ε = 1, about 1200 K, τ = 1)
**over-predicts**, increasingly with distance. Sofia's indicative back-test against Morandini 2006 is 2–3× high.

**Possible under-prediction:**
- convection on slopes and in wind;
- hotter flames (+10% T is about +46% flux);
- fronts wider than assumed.

**Statement attached to every standoff table** (§3, §6, §7): the 50–400 m distances, the 1.0–2.5 kW/m² range,
flames above about 25 m, smoke attenuation, and roadside or vehicle exposures are **not validated** anywhere found.
These rows are extrapolations of a model that is conservative in the near field. Ember ignition and smoke are not
covered at all.

**Not applied** (proposals for the orchestrator and Iris):
- a distance safety factor of about 1.5;
- a flag that rows with H < 3 m are likely conservative;
- a convective minimum of 20–50 m.

## F-DYN results for §2 and §3 (12 Nov, about 16:00 UTC; rules as fixed above; non-evaluated)

**Data.** `results/fdyn/RADIANT_FDYN.json` (`radiant_fdyn.py`) and `results/fdyn/FDYN_CLEARANCE.jsonl`.

**Routes.**
- **KIT:** the 2 routes published by the unmodified kit at 900 s / 3,072 MiB. This is the kit figure.
- **TESTKIT:** the 5 routes from the modified A3(b) test kit, labelled and never pooled.
- No F-DYN request was refused on dose. The non-published requests are UNRESOLVED or AT_ISSUE_FAILURE (contact),
  so §2(a)'s refusal clause counts 0.

**§2(a) Linear dose binds (certified dose upper bound ≥ 100 kJ/m²).**
- KIT **0/2**: maximum 0.0017 kJ/m².
- TESTKIT **0/5**: maximum 4.92 kJ/m², on the 3,953 s route.

**§2(b) Physiological flux reached (certified peak upper bound, an enclosure).**
- KIT **0/2 at both 1.0 and 2.5 kW/m²**: maximum 6.2e-6 kW/m².
- TESTKIT **0/5 at both thresholds**: maximum 0.543 kW/m², on the 3,953 s route.
- Because the bound is an enclosure, these zeros are proofs of "never reached" under the kit's model. With window
  factor 0.5 the counts are also 0.

**§2(c) Packet-wide maximum cell-centre model flux** over cells containing a routed road segment, excluding cells
flaming in that interval:
- Uiseong 0325T17: 0.0160 kW/m² (kriged) and 0.0160 (firms);
- Yeongdeok 0325T23: 0.0089 kW/m² (both variants).
- This is cell-centre model flux, **not** an enclosure of road-segment flux.

**§3 standoff counting rule on F-DYN.** A route counts as below a standoff iff its published clearance is strictly less
than the standoff. The standoffs used are every one in the §3, §6 and §7 tables: 7.6 m to 3,125 m.
- **KIT: 0/2 routes below any standoff.** Their clearances are 12,082 m and 5,118 m, both CROP-limited, so the
  true clearance could be smaller if fire lies outside the packet domain.
- **TESTKIT: 2/5 routes below every standoff in every case.** These are the 3,953 s route on both packets, with a
  clearance of **4.4 m** below the smallest standoff (7.6 m). The other 3 are above all standoffs (CROP-limited).

**What this is and is not.**
- It is a sensitivity range under the stated flame assumptions, **not a count of unsafe routes**.
- The flame-model validation statement (above) applies.
- The 3,953 s route is certified contact-free and within the dose and peak limits by the kit's checker, yet passes
  within metres of an active flaming cell. That is exactly the case the standoff screen is meant to show.
