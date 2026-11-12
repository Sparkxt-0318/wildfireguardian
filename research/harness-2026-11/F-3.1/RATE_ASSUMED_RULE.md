# Rate-assumed unknown-support tier: sensitivity and refutation test (rules, committed before running)

Requested by the orchestrator, under Iris's conditions, for the headline-tier decision, which belongs to the owner.

**Naming.** The tier is called **"rate-assumed, v km/h"**, never "bounded". Its definition is tier R in
`deadline_field/unknown.py`: U_state and U_q cells at centre distance d from S0R (present fire OR positive native
probability) are blocked from ceil(d / v).

## (1) Sensitivity over v (6 one-hour planner caches)

* **Variants.** Rate-assumed at v ∈ {1.5, 8.2, 16.4} km/h, plus Tier A (every unknown cell blocked from 0).
* **Field and definitions.** Cert contact field, with the same definitions as `deadline_field/threeway.py`. The
  existing A, R1.5 and R8.2 runs are reused unchanged; only R16.4 is new, through the same code path.
* **Counted per cache and variant, never pooled.** Per origin (start node), the exact deadline against the optimistic
  (frozen packet) field:
  * **removed:** optimistic has a deadline, the variant has none;
  * **moved:** both have one and they differ. The count is reported with the median and maximum of
    (optimistic − variant), in seconds;
  * **unchanged:** the remaining origins with a deadline under both;
  * job-level counts of recorded verdict → variant label, as in `results/threeway_jobs/`.
* **Scope.** "Checked" under any variant is contact-only: the dose/peak precondition for hypothetical unknown sources
  is not established.

## (2) Refutation test of 8.2 km/h as the highest rate in scope

### Data

* Leo's FIRMS CSVs (F-DYN `_data/firms/`: viirs-snpp, viirs-jpss1, modis), sha256 recorded in the output.
* Detections are kept if all of the following hold:
  * acquired 2025-03-21 00:00 to 2025-03-29 00:00 UTC;
  * inside the KFS_01 export grid (both regions share it);
  * `type` = 0 (presumed vegetation fire);
  * in a cell with a finite kriged arrival time (inside the final mapped footprint).

  The last two filters keep static industrial sources and other fires out.
* **Position:** the detection's latitude/longitude, transformed to EPSG:5179.

### Brackets

* Leo's `firms_early` definition is used.
* **End e_k:** the detection's acquisition time. Fire was present by then.
* **Start s_k:** the last overpass strictly before e_k that recorded at least one detection in the grid. This is the
  earliest arrival consistent with a clear-sky non-detection. Clouds or smoke could hide fire, so the true arrival
  may be earlier still.

### Statistics

* **Primary, per detection.** For each detection j:
  * r_j = min over detections i with s_i < e_j and i ≠ j of dist(i, j) / (e_j − s_i), in km/h.
  * r_j is the slowest spread from any detected earlier fire that explains j.
  * Detections with no admissible i (the first overpass) are excluded and counted.
* **Reported for r_j:** the maximum, the distribution (p50, p90, p99, max), the count above 8.2 and the count above
  16.4 km/h, and the 10 largest cases with coordinates and times so they can be inspected.
* **Secondary, the literal all-pairs version.** Over all ordered pairs (i, j) with s_i < e_j:
  dist / (e_j − s_i). Its maximum and distribution are reported but **not** used for the decision. It is dominated
  by simultaneous detections on separate fronts (two fronts far apart at the same overpass), which no single spread
  path has to explain.

### Decision rule (fixed now)

* **8.2 km/h is refuted** as the highest rate in scope if max r_j > 8.2 km/h, **unless** every exceeding j is
  attributable to a separate ignition or spotting rather than front spread. Attribution must be stated case by case
  from the listed cases; it is not decided here.
* Otherwise it is **not refuted by these detections**. That is not a proof: there are unseen arrivals between
  overpasses, and cloud or smoke can hide fire.

### Source of 8.2 km/h

* I have **no primary source**. The value came into `unknown.py` from Iris and Leo as a scenario speed.
* It is to be confirmed by Sofia.
