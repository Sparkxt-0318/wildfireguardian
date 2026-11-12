# Multi-hour headline outputs (rule, committed before any headline run)

The orchestrator adopted these points from an external review of Main that the owner passed on. They apply to the
#132 follow-up. Every multi-hour output is a **SCENARIO, not what happened**; roads are limited to the recorded
windows.

## 1. No re-entry is the default

* **Headline arm.** Every multi-hour output a person sees uses **no re-entry**: a cell that has burned is closed from
  its birth to the end of the horizon. This is the never-clears arm (`PacketModel(duration_factor="never")`). It
  matches the #137 rule.
* **Research variant.** The fixed-burn-duration reopening model (the packet as built) is labelled "research variant:
  fixed burning duration, reopening after burn-out (unsourced; Sofia)". It is never a person-facing number.
* **Consequence.** Under no re-entry every feasible-departure set is a prefix [0, x] (verified: Nora rows 35 and 40).
  So the resident-facing contiguous deadline is the whole set and there are no holes.
* **Policy check.** The full checker reads the packet as built (with reopening). A no-re-entry witness is checked
  against it as a necessary condition, and the no-re-entry field is reported as contact-field. It is labelled "no
  re-entry contact field; witness checked against the as-built packet".

## 2. Bands across hazard variants

* **Report a band, never a point.** A multi-hour deadline is a band across hazard variants: min–max over the
  variants that give a deadline, with each variant's value and label listed.
* **Variants and labels.**
  * kriged_mean (central scenario);
  * firms_early (bracket-start, not a lower bound);
  * envelope (bracket-start, not a lower bound);
  * envelope_burnset (sound relative to the final mapped burn set; single implementation, not independently
    checked).
* **Variant with no route.** Where a variant gives no checked route (for example envelope_burnset in Uiseong), the
  band says so explicitly. It is not dropped.
* **Packets.** Only packets whose builder self-check passes are used: MANIFEST_v3_5, Nora row 41, content-identical
  to v3.4. Every result row prints the packet hash and the writer identity.

## 3. Issue-order-by is a headline output

* **Formula.** Issue-by = leave-by (no re-entry, per variant, and as a band) − notification latency − mobilisation
  (door-to-door) time.
* **Results table.** It gets its own table, with every latency setting and its source:
  * **notification latency 99 min.** Board of Audit, mean time from situation room to text alert, 1 h 39 min
    (Sofia's source).
  * **15 and 180 min.** Assumptions (low and high), no source.
  * **90 and 120 min.** Assumptions (orchestrator's lat1.5h / lat2h), no source.
  * **mobilisation 15 / 30 / 60 min.** Assumptions, no source.
* **Counts.** Every origin gets a line. Per packet the table counts future / past / late_window_only / no_route.
  Under no re-entry, late_window_only cannot occur. It counts horizon-censored leave-bys separately.

## 4. Rate-assumed and worst-case tiers are one-hour tools only

* **Not extended.** The rate-assumed tiers (unknown support) and any worst-case spread envelope are **not** extended
  to 5 h or 8 h.
* **Why.** At 8.2 km/h a rate bound reaches 41 km in 5 h and 66 km in 8 h. The KFS_01 grid is 89 × 30 km, so the
  bound covers nearly the whole region and carries no information.
* **Statement in RESULTS.** This is said explicitly next to the one-hour tier results.

## Order

* R16.4 / B16.4 and lever A/B go to Nora first.
* Then the headline runs: v3.5 packets × 4 variants × 6 starts × {5 h, 8 h}, no re-entry, with full-checker witnesses,
  bands and issue-by.

## Amendment 2026-11-12: Iris's tightenings (orchestrator), committed before any headline run

* **(a) Issue-order-by is on hold as a headline.**
  * It stays a research row until kit-v2's 9,722-verdict gate passes and the bands exist. Section 3 is suspended
    until then.
  * When it is shown, it shows the **earliest** edge of the band, with the latency and mobilisation assumption beside
    it.
* **(b) Bands.**
  * Each band is **"a range across named variants"**: kriged_mean, firms_early, envelope, envelope_burnset. It is
    never called an interval and never presented as a confidence statement.
  * **Every band includes at least one pessimistic variant.** That is envelope_burnset (sound relative to the final
    mapped burn set). A band built only from optimistic variants is one-sided and is not reported as a band.
  * Where envelope_burnset gives no route (for example Uiseong), the band's earliest edge is "no checked route under
    envelope_burnset".
* **(c) Assumption line.** Every multi-hour output, person-facing or not, carries: *"Assumes no fire outside mapped or
  forecast cells; no conservative unknown-support tier exists at multi-hour."*
* **(d) No re-entry vs clearing.**
  * Per packet, report the count of verdicts that differ between the no-re-entry field and the clearing variant (as
    built, fixed burning duration).
  * The unit is (origin, destination, 30-min grid departure); the count gives feasible → infeasible and
    infeasible → feasible separately.
* **(e) Wording.** "Exact" means exact for the time-dependent **model**'s field, not for the fire. Every error or
  difference statement is worded "relative to the time-dependent model".
* **Harness rule (all cuts).** Before each cut, diff every README hunk that Main changed since my previous cut, so a
  whole-file copy cannot revert a verified erratum.
* **(f) Road-limited no-route (routing reviewer, via the orchestrator).**
  * Every multi-hour "no route" computed on today's clipped graphs (graphs_interim) is labelled **ROAD-LIMITED**:
    *"graph clipped to the recorded one-hour window; a road out may never have been loaded"*. It is counted separately
    from fire-limited no-route. This holds until Daniel's full-export-grid graph is verified by Hannah.
  * **Split.** A no-route is reported as *possibly road-limited* if the set of nodes reachable from the origin at the
    departure in the field (states with a feasible continuation ignored) contains a graph-boundary node: a node of
    degree 1 within one cell of the clipped window edge. Otherwise it is reported as *fire-limited within the loaded
    graph*.
  * Where the split cannot be computed, the output says so. Neither label claims that a real road out exists or does
    not exist.
* **(g) Acceptance 7 (Leo's NOREENTRY_RULE, delegated by the orchestrator).** This is a row of the headline results.
  * **Unit.** Each no-re-entry deadline witness is checked by the unchanged full checker on both packets: the v3.6
    reopening packet and the v3.6 no-re-entry packet (F1 flux).
  * **Count.** Requests whose PEAK_BUDGET / DOSE_BUDGET codes differ, split into pass → fail and fail → pass, by
    variant.
  * **Flame-contact differences** are reported separately and are expected to be 0. The field equality holds at the
    deadline (`results/NOREENTRY_CHECK_v36.json`).
  * **Scope.** The headline set: v3.6 packets × 4 variants × 6 starts × {5 h, 8 h}. The headline runs use the v3.6
    no-re-entry packets directly; they are content-identical to the never arm, checked on UA 25T17 h5.
