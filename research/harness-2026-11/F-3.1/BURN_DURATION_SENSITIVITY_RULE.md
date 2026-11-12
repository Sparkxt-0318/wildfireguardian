# Burn-duration sensitivity of feasible-departure holes (rule, committed before running)

Approved by the orchestrator, proposed by Iris. This rule is written before any sensitivity number is computed.

## What is run

* **Packets.** The 12 Uiseong F-DYN v3.1 packets: starts 03-23 01Z, 03-24 09Z and 03-25 17Z × {5 h, 8 h} ×
  {kriged_mean, firms_early}. firms_early is labelled bracket-start, not a lower bound. All are SCENARIOS, not what
  happened.
* **Field.** The deadline field (cert rule = router OR closed footprint, contact field) is computed with every burning
  phase's duration changed by a factor f:
  * f = 1: as built (the baseline);
  * f = 0.5;
  * f = 2;
  * never-clears: no cell stops burning within the horizon.
* **How f is applied.** A drawn ignition at b burns on [b, b + f·T). Present fire burns on [0, f·R). Under
  never-clears, both run to beyond the horizon. Births are unchanged.
* **Counterfactual status.** These are contact-field counterfactuals. The unchanged full checker reads the packet as
  built, so witnesses are not policy-checked under f ≠ 1.

## What is counted (per packet, per f; never pooled)

* **Union.** For each origin, U = the union over its recorded candidate shelters of the feasible departure seconds
  in [0, H].
* **Hole.** An origin has a hole when U is non-empty and is not a single interval starting at 0. The set has either
  a gap, or an infeasible start followed by later feasible seconds.
* **Contiguous deadline.** If U's first interval starts at 0, it is the end of that first interval. Otherwise there is
  none. This is the resident-facing time under the merged planner rule.
* **Reported per packet:**
  * the number of origins with a hole;
  * the number of origins whose contiguous deadline differs from f = 1 (including appearing or disappearing).

## Classification of holes that survive never-clears

Under never-clears, every blocked set is a suffix [s, ∞) of start times, and destination acceptance is a suffix
complement. Leaving earlier is then never worse in this contact field, so **no hole is expected**.

Any hole that survives never-clears is classified by inspecting its blocking pieces, in this order:

* destination opening window (here every window is [0, H], so it is not expected);
* issue-point or wait blocking;
* an implementation fault (to be reported).

Dose and transient radiation are not part of the contact field, so they cannot cause a field hole. They would show
up only in full-checker verdicts, which are not run under f ≠ 1.

## Decision rule (fixed now)

* If holes disappear under never-clears, they are attributed to burn-out under the placeholder burning-duration law.
  They are reported as a model finding and are **never** shown to residents. Staff see them labelled "not the
  deadline, do not plan on it" (the merged rule).
* Surfacing windows after a gap is reconsidered **only** if holes persist under never-clears with a physically
  grounded cause, and then for staff first.
