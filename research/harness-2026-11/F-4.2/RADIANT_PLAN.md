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
