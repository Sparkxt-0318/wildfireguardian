# Radiant-heat side task (FIRE 6.2): assumptions and counting rules

Written 12 Nov, 11:20 UTC. The frozen policy is not edited. This is an opt-in screen only.

**Disclosure.** The 1-hour standoff table produced by `standoff.py` at `b3668b6` (11:15 UTC) was computed *before*
this plan was written, on Iris's suggestion and before the orchestrator asked for pre-registration. It is therefore
**exploratory**. The rules below are fixed now. The F-DYN counts (part 2) have not been computed and will follow
these rules exactly. Part 3 is re-run under these rules, including the window-factor sensitivity, which the
exploratory table did not have, and is reported beside the exploratory table.

## 1. One-hour panel (arithmetic, no computation)

The packet model's largest peak-flux bound anywhere is 0.703 kW/m² (the packet builder's bound on omitted sources;
Richard's maximum non-flame flux is 0.0156 kW/m²). Both are below 1.0 kW/m². So under the proposed rule (ceilings
1.0 kW/m² vulnerable and 2.5 kW/m² general, radiant term zero below threshold, flame contact a no-go), no 1-hour
verdict or deadline can change. The rule's only binding element would be contact, which is already a no-go.

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
