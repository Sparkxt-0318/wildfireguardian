# Ideas parked — and the objection that parked each one

*Started 2026-09-06 by the research routine (ROUTINE_PROMPTS.md step 3, CHARTER §14). A candidate that survives `macrothink` but is stopped by `hate`, or that does not fit the sprint or the submitted frame, is written here with the objection that stopped it, so that a later run reads the objection instead of re-proposing the idea. **Nothing here is deleted.** An idea that later becomes viable gets a dated note saying what changed, and then a backlog row.*

---

## P-001 · 2026-09-06 · Reformulate evacuation as a max-flow-over-time / capacity-constrained problem

**The idea.** Borgwardt, Crawford, Horton, Morrison & Speakman (arXiv:2410.14500, <https://arxiv.org/abs/2410.14500>, [opened]) formulate wildfire evacuation as maximum flow on a time-expanded network with hazard information integrated from shapefiles, and Chawla & Sheridan (arXiv:2605.00277, <https://arxiv.org/abs/2605.00277>, [opened]) give a condensed time-expanded network for the case where capacities change at μ critical times. Together they suggest replacing this project's per-origin independent shortest paths with a single flow problem over all 458 origins at once, so that congestion and capacity are represented.

**Why it is attractive.** It is the formally stronger object; it would let the project say something about *simultaneous* evacuation rather than 458 independent walkers; and the cTEN result means the complexity would be governed by the small number of hazard slices rather than by the clock.

**The objection that parks it (root, from `hate`).** **Capacity is the thing that pedestrian rural evacuation least needs, and adopting a flow formulation would pivot the method for a constraint nobody has shown binds here.** Three legs: (i) the network is a *walking* graph in a county whose settlements are tens of households, so an edge's pedestrian capacity is nowhere near binding at these volumes, and this repository has never measured a congestion effect; (ii) John P. Wilson's reply to the author (2026-09-05, `ROUTING_FUNDAMENTALS.md` §Update 2026-09-05, WFG-093) makes the opposite point — pedestrians *leave* the mapped network, so capacity-aware routing designed for road-bound vehicles is the formulation least likely to transfer; (iii) CHARTER §3 rule 4 forbids changing the project's method-frame before the finals, and this is a method change, not an extension.

**The cheapest test that would revive it.** Show that any pedestrian edge on the committed Yeongdeok walk graph carries enough simultaneous walkers, under the project's own origin weights, to change a travel time. If no edge does, capacity is provably irrelevant here and this idea stays parked permanently — which would itself be a good sentence for the paper. That test is cheap and reads only committed artifacts; it is **not** filed as a row this run, because a null result would only confirm the parking.

**Status:** parked. Both papers stay cited in `ROUTING_FUNDAMENTALS.md` for what they do give — the time-expansion theory and the critical-times discretisation principle — which is where their value to this project actually is.

---

## P-002 · 2026-09-06 · A multilingual / conversational guidance layer

**The idea.** BEACON (arXiv:2609.03301, 2026-09-03, <https://arxiv.org/abs/2609.03301>, [opened]) delivers personalised wildfire evacuation guidance — routes, checklists, a chatbot — in the user's own language, motivated by the 26 million people in the US with limited English proficiency receiving over 80 % of emergency messages in English only. It suggests adding a language layer or a conversational front end to this project's resident-side output.

**Why it is attractive.** It is a real equity finding, it is recent, and a chatbot demo is easy to show at a booth.

**The objection that parks it (root, from `hate`).** **The constraint on this project's users is not language, and adding a feature that addresses a constraint they do not have would cost booth time and add no evidence.** The target population is rural elderly Korean speakers in 경상북도; the Greenpeace survivor survey already registered here shows the channel that actually worked was 마을방송 and neighbours, not a phone interface, and that a substantial share of 영덕 respondents live alone. A conversational layer is a product feature with no measurable claim attached, and the project's scarcity is judge-facing *evidence*, not features. BEACON also reports no evaluation of any kind, so there is nothing to build on empirically.

**The cheapest test that would revive it.** A source showing that language or literacy is a measured barrier for this specific population in a Korean wildfire evacuation. None was found this run.

**Status:** parked. BEACON is kept as a citation in `ROUTING_FUNDAMENTALS.md` §Update 2026-09-06 for one narrow purpose: its router is 「polygon-avoidant」 around the *current* perimeter, which is independent evidence for what deployed guidance systems actually do and therefore for why the present-perimeter opponent is the fair one to beat.
