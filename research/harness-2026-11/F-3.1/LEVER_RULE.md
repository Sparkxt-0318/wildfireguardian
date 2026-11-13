# Timing lever vs destination lever (counting rule, committed before tabulating)

Assigned by the orchestrator, following Sofia's lever review. Results are **model statements on scenarios** (F-DYN
SCENARIO, not what happened in 2025; the 1-h caches are forecast scenarios at recorded input times). This model has no
traffic, no saturation and no congestion closures, so any destination (route) effect is free-flow only. Sofia notes
that the route effect is about 0 by construction without saturation.

## Fields

* Contact field, cert rule (router OR closed footprint).
* One backward field per destination of the region. Every origin is read off every destination field.
* Feasible departure set of origin o for a destination set D: U_D(o) = ∪_{d ∈ D} feasible departure seconds from o
  to d.
* **Own destinations** D_o:
  * F-DYN: the origin's listed destinations in INSTANCE.json (3 each).
  * 1-h caches: every destination spec the planner checked for that origin.
* **All candidate destinations** D_all: every destination appearing for any origin of the region (F-DYN) or of the
  cache file (1-h).

## Reference departure (fixed now)

* **F-DYN:** t_ref = 150 min after the start = 2 h alert latency + 30 min door-to-door (the "lat2h" setting of the
  issue-order-by). This is a latency assumption, not data.
  * Sensitivity, reported separately: every 30-min grid departure t with t ≥ 120 min.
* **1-h caches:** t_ref = 50 min (the planner's last offset). Only lever A at 30 min is defined; 60 and 120 min would
  fall before the input time and are reported as N/A.

## Levers

* **Base checked:** t_ref ∈ U_{D_o}(o).
* **Lever A (timing, s ∈ {30, 60, 120} min):** depart at t_ref − s to the same destinations. Rescued if
  t_ref − s ∈ U_{D_o}(o).
* **Lever B (destination):** depart at t_ref to any candidate destination. Rescued if t_ref ∈ U_{D_all}(o).

## What is counted (per packet = region × start × horizon × variant; never pooled)

* Among place-starts **not checked at t_ref**, the count per category for each s:
  * A only;
  * B only;
  * both;
  * neither.
* **Arrival gain where both rescue.** Earliest arrival under A (at t_ref − s, same destinations) and under B (at t_ref,
  any destination), both by the exact earliest-arrival witness (`core.witness`), and the difference (B − A, seconds).
  If the witness exceeds the memory cap (2 GiB), the arrival is "not computed" and counted as such.
* **Context.** The number of place-starts checked at t_ref (no lever needed).
* **Variants.**
  * F-DYN: kriged_mean, firms_early (bracket-start, not a lower bound), envelope (bracket-start, not a lower bound),
    envelope_burnset (sound relative to the final mapped burn set; single implementation, not independently checked).
  * 1-h: the recorded c651 packets.

## Not claimed

* Nothing about what happened in 2025.
* No route-choice effect under congestion (not modelled).
* Leaving earlier than the start is outside every scenario, so lever A is bounded by the start.
