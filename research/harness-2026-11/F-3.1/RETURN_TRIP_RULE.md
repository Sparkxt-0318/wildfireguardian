# Return trips: outbound checked, return not (counting rule, committed before tabulating)

Results are **model statements on scenarios**: F-DYN SCENARIO, not what happened. Contact field, cert rule.

## Trips

* **Outbound.** From the place's entry node, departing at the start (t = 0), to its own destinations (INSTANCE.json,
  dwell as listed).
  * Outbound is checked if 0 lies in the union of feasible departure sets.
  * The outbound destination is the own destination with the **earliest arrival**, by the exact earliest-arrival
    witness `core.witness`. Ties go to the lowest node id.
* **Return.** Origin and destination swapped: from that destination node back to the place's entry node.
  * Departure t_ret = arrival + dwell + Δ, for Δ ∈ {30, 60, 120} min.
  * Return destination window [0, H], dwell 0.
  * Return is checked if t_ret lies in the return field's feasible departure set from the destination node.
  * If t_ret > H, the return is outside the scenario: it is counted "beyond horizon", not as failed.

## What is counted (per packet and Δ; never pooled)

* Places with outbound checked.
* Among them, places whose return is:
  * checked;
  * **not checked**;
  * beyond the horizon.
* Places whose outbound arrival is not computed (memory cap 2 GiB on the witness).

## Packets

* F-DYN v3.3 manifest, 6 recorded starts.
* 5 h only.
* kriged_mean and firms_early (bracket-start, not a lower bound).

## Not claimed

* Nothing about actual returns in 2025.
* No traffic.
* The return is a single trip back to the entry node; access restrictions and road closures by authorities are not
  modelled.
