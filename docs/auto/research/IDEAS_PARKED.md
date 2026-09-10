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

---

## P-003 · 2026-09-08 · Multi-window (7/30/90-day) drought windows as `spread_v2` features

**The idea.** Chen et al. <!-- forbidden-ok: Chen --> (2026-09-01, *PLOS ONE*, 10.1371/journal.pone.0355829, <https://doi.org/10.1371/journal.pone.0355829>, [opened]) build FWI-MSNet, which encodes fuel dryness at **three timescales at once** — parallel 1D-CNN channels with 7-, 30- and 90-day kernels for daily fuel response, monthly drying and seasonal drought accumulation — and report test R² 0.9251 against seven baselines, with an approximate 56.1 % error reduction. The suggestion is to add matching multi-window drought features to this project's `spread_v2` feature set.

**Why it is attractive.** The design observation is genuinely good and genuinely transferable in principle: dryness carries information at more than one timescale, and a flat feature vector at one window throws part of it away. It is also cheap to describe and would make an easy slide.

**The objection that parks it (root, from `hate`).** **It is a refit, and a refit is the one thing this project cannot do before the finals.** CHARTER §3 rule 2 forbids modifying, overwriting or regenerating a committed artifact, and every headline number in the repository — the operating point, the LOFO-CV AUC, the reconciliation, the forward-sim envelope — is downstream of the fitted `spread_v2` model. Changing its features means refitting, which means every one of those numbers becomes a new number, seven days before the sprint ends and six weeks before the finals, with no time to re-validate any of them. A second leg: the source task is **regression of a fire-danger index at a station**, not next-overpass ignition on a 500 m grid, so the transfer of the *architecture* to this label is unevidenced — the paper gives no reason to expect the 7/30/90-day decomposition to help a different target, and its own cross-geography transfer (R² 0.9251 → 0.57–0.77) shows how much its performance depends on where it was fitted.

**The cheapest test that would revive it.** After the finals, and only on the ISEF/IEEE track (WFG-032's leak-free fold is the natural place): fit one additional arm with the multi-window drought features against the existing arm on the identical LOFO-CV split, and report both. If the multi-window arm does not beat the existing one under leave-one-fire-out, the idea is dead and the null is publishable; if it does, it is a paper result with a clean provenance, produced with a new filename and a new registry key rather than by editing anything. **Not filed as a row this run**, because it cannot start before 2026-10-24 and the backlog already carries twelve P0 rows with seven sprint days left.

**Status:** parked, post-finals. Chen et al. <!-- forbidden-ok: Chen --> stays cited in `PYROGEOGRAPHY.md` §Update 2026-09-08 for the thing it is actually good for here: a second external instance of the honest-validation penalty, measured across geography rather than across spatial blocks.

---

## P-004 · 2026-09-10 · Replace time-expanded routing with D* Lite incremental replanning

**The idea.** Bokade et al. (2026-09-09, 10.5281/zenodo.22668357, <https://doi.org/10.5281/zenodo.22668357>, [opened]) route evacuees with an internal **D* Lite** heuristic grid fallback that 「incrementally routes traffic away from actively predicted fires」, alongside OpenRouteService vector routing. D* Lite repairs an existing path when the cost surface changes, which is cheap, standard, and demonstrably good enough for a same-architecture system published this month. The suggestion is to adopt it here, either as the routing engine or as a second arm.

**Why it is attractive.** It is the textbook answer for routing under a changing cost field; it would give the project a well-known algorithm name to say at a booth; and it would make a live demo trivially interactive, because replanning is incremental by construction.

**The objection that parks it (root, from `hate`).** **It answers a different question from the one this project asks, and adopting it would quietly delete the project's actual contribution.** D* Lite repairs a path when the world has *already changed* — it is reactive, and it prices an edge at the cost it has *now*. This project's whole claim is that an edge's usability is a function of **when a walker would traverse it** under a *forecast* hazard field: a route that looks open now and will be cut in forty minutes is exactly the route a time-expanded graph refuses and a replanner cheerfully hands to an eighty-year-old on foot. Swapping in D* Lite would turn the per-point walk-or-be-rescued verdict back into a navigation feature. Second leg: CHARTER §3 rule 4 forbids changing the project's method frame before the finals, and this is a method change, not an extension.

**The cheapest test that would revive it — and it is worth doing after the finals.** Construct one origin on the committed Yeongdeok walk graph where the two disagree: a path that a replanner would take at t = 0 and that the time-expanded solver refuses because the hazard reaches an edge before the walker does. If such an origin exists in the committed data, the contrast is a **figure and a paragraph** that justify the method choice better than any prose can, and the idea stays parked with its own evidence. If no such origin exists, the time-expansion is doing no work on this graph and that is a finding the paper must report. Either outcome is publishable; neither can run before 2026-10-24, because building a second router is not a sprint row.

**Status:** parked, post-finals. Bokade et al. stays cited in `ROUTING_FUNDAMENTALS.md` §Update 2026-09-10 for the two things it is genuinely good for here: independent evidence that routing-against-a-forecast is a recognised design choice (so this project should claim the output object, not the architecture — **WFG-239**), and its own headline negative result on persistence bias, which is external support for **WFG-234**.
