# Stage 1: survey

Run on 18 Nov 2026, 22:53–23:03 UTC (19 Nov, 06:53–07:03 Shanghai), well inside the 6-hour limit. Six searches ran in
parallel, one per topic. A seventh, for the exact result chosen in Stage 3, is reported in `METHOD.md` §6.

**How to read this.** This page is the summary. The full record is in `survey_notes/`, one file per topic. Each
file lists every source with its URL, how much of it was read (full text, abstract, or a search snippet), and what could
not be opened. The searches were done by search agents working for this study; the notes are their reports, saved
unedited by `extract_report.py`. I did not re-open the sources myself. A claim below is only as strong as the reading
level stated in the notes. "Not found" means not found in about 10–20 searches per topic. It is not proof of absence.

| § | topic | notes file | sources opened |
|---|---|---|---|
| 1 | time-dependent shortest paths, latest departure, profile search | `survey_notes/A_time_dependent.md` | 24 |
| 2 | safe-interval path planning, timed reachability | `survey_notes/B_sipp_timed.md` | 17 |
| 3 | dynamic and incremental shortest paths, sensitivity analysis | `survey_notes/C_dynamic_sensitivity.md` | 26 |
| 4 | algebraic path problems | `survey_notes/D_algebraic.md` | 16 + 3 |
| 5 | parametric and robust shortest paths | `survey_notes/E_parametric_robust.md` | 15 |
| 6 | evacuation planning | `survey_notes/F_evacuation.md` | 24 |

## What the survey changes about how the deadline field should be described

1. **The interval-set algebra of the field is not new. Minoux published its forward form in 1976.** M. Minoux,
   "Structures algébriques généralisées des problèmes de cheminement dans les graphes", RAIRO 10 (1976), chapter III,
   after Halpern and Priess (1974): states are finite unions of closed intervals, sum is union, an arc acts by
   "extend by the parking windows, intersect with the allowed departure set, translate by the travel time", and a
   fixed point exists because delays are positive and the horizon is finite. Minoux also notes that label-setting
   does not finish in N steps on the set-valued problem (§4, source 1, full text read). What the survey did not find
   is the backward ("can still reach") form, the closed-form waiting closure, or the collapse to one number under
   permanent closures as an algebraic statement.
2. **The scalar (permanent-closure) pass is covered by published Dijkstra conditions.** The edge map
   x ↦ min(c − 1, x − D) is isotone and satisfies f(x) ≤ x, so Minoux's Theorem 6 (order reversed), Knuth's superior
   functions and Sobrinho's "isotone and monotone" condition each justify label-setting (§4). The per-path formula
   "latest departure = min over edges of (block time − travel time to the edge)" is published for evacuation with
   fixed paths (Even, Schutt, Van Hentenryck 2015; §5, source 14).
3. **Forbidden waiting makes the problem hard in the encoding of times.** Earliest arrival with no waiting and integer
   travel-time functions is weakly NP-hard, with an O(τ_max · |E|) algorithm (Zeitz 2023; §1, source 2, full text).
   Orda and Rom (1990) already noted non-simple optimal paths under forbidden waiting. So a bound polynomial in the
   number of intervals should not be expected for the field; bounds in H are the realistic kind.

## §1 Time-dependent shortest paths and profile search

* Profile search (all departure times at once) starts with Orda and Rom 1990 and needs label-correcting. Under FIFO
  with piecewise-linear travel times the profile can have n^Θ(log n) breakpoints (Foschini, Hershberger, Suri).
* Arc availability intervals with reopening, all start times: Dehne, Omran, Sack 2012, O(λ(|E| + |V| log |V|)), but
  with waiting everywhere, so the answer is a monotone profile with no gaps.
* Latest departure for all vertices in one reverse scan: Wu et al. 2014, with unrestricted waiting, one number per
  vertex. This is the field's permanent-closure special case.
* Per-vertex waiting limits, polynomial for walks: Bentert, Himmel, Nichterlein, Niedermeier 2020; one optimal value
  per vertex from one source, not the set of feasible departures.
* Discrete time, all-to-one, all departure times, any waiting policy, O(mT): Chabini 1998, Dean 2004. The field is
  this scan compressed to intervals; no interval version for the non-FIFO case was found.
* **Not found:** an algorithm that returns, for all nodes, the full set of feasible departure times with gaps under
  arc windows and waiting forbidden at some nodes; a latest departure as a function of a parameter that scales
  closure times.

## §2 Safe-interval path planning and timed reachability

* SIPP (Phillips and Likhachev 2011) is forward, from one start time, with waiting inside every safe interval, and
  keeps one earliest arrival per state. SIPP-IP (Ali and Yakovlev 2023) handles states where waiting is impossible by
  propagating whole intervals forward; it is the forward mirror of the field's step, for one start time.
* Any-start-time SIPP (Thomas et al. 2023) returns an arrival-time function of the start time, forward from one
  state, with waiting assumed. FlexSIPP (Hanou et al. 2026) adds a "temporal flexibility", a scalar slack per agent
  computed along one fixed trajectory.
* Backward reachability over unions of zones in timed automata is the general theory the field instantiates; with one
  clock a union of zones is a union of intervals. No specialisation to road graphs or complexity for it was found.
* **Not found:** a backward all-start-times set computation without waiting everywhere; an exact incremental update
  when a safe interval is added or removed (SIPP's authors list it as future work); a version parameterised by a
  margin.

## §3 Dynamic and incremental shortest paths, sensitivity

* Ramalingam and Reps 1996: fixed points of strict weakly superior function systems are maintained in
  O(‖δ‖(log ‖δ‖ + M_δ)), with ‖δ‖ the size of the change. Closed-semiring path problems without a strict offset are
  unbounded in that model. The field's D_j ≥ 1 is the strictness that makes a bounded update possible.
* LPA* and D* Lite are that machinery with a heuristic for one start–goal pair. DRedL (Szabó et al. 2018) and
  DRedMTL (Zhao et al. 2026) maintain lattice-valued and interval-stamped least fixed points; growth needs no
  delete phase.
* Sensitivity: Ramaswamy, Orlin, Chakravarti (2005) give all edge tolerances for shortest and maximum-capacity paths
  in undirected graphs for one s–t pair. All single-edge deletions: Hershberger and Suri 2001.
* **Not found:** an incremental algorithm for interval-set reachability with a bound in changed intervals; a one-pass
  table of "new optimum if this element's closure is delayed by Δ" for a bottleneck problem with path offsets; any
  joint treatment of many what-if delays. Wildfire suppression papers (Harris, Forbes, Taimre; Delazeri and Ritt)
  evaluate each candidate with a fresh Dijkstra.

## §4 Algebraic path problems

See points 1 and 2 above. In addition:
* Bernardoni et al. 2023 define a "propagation delay semiring" with product (I, s)(J, t) = (I ∩ (J − s), s + t), the
  composition law of shift-and-mask operators, and call it new; Minoux's 1976 algebra already contains it.
* Threshold decomposition is published for max-min matrices: A = ⊕_h (h ⊗ A^(h)) and (A ⊗ B)^(h) = A^(h) ⊗ B^(h)
  (Semančíková 2006, as quoted by Myšková and Plavka 2021, Lemma 2.2).
* **Not found:** a lifting theorem for thresholds combined with additive time offsets.

## §5 Parametric and robust shortest paths

* Additive parametric shortest paths have n^Θ(log n) breakpoints (Gusfield; Carstensen; Mulmuley and Shah), also on
  planar graphs (Gajjar and Radhakrishnan 2019). With unit slopes there are O(n²) trees (Karp and Orlin; Young,
  Tarjan, Orlin).
* Pure parametric bottleneck paths are polynomial: O(m n^(1/3)) breakpoints via the parametric spanning tree bound
  (Eppstein 2021).
* Robust versions: a min-max bottleneck problem over scenarios is solved by one run on the worst-case instance
  (Aissi, Bazgan, Vanderpooten 2009, Proposition 3; Averbakh 2000 for intervals). Min-max shortest path is NP-hard
  for two scenarios (Yu and Yang 1998).
* Parametric timed automata: for L/U automata, reachability is monotone in the parameters (Hune et al. 2001,
  Proposition 3), but exact synthesis is not available in general (André, Lime, Roux 2022).
* **Not found:** an algorithm or breakpoint bound for max over paths of min over arcs of (α_arc · μ − offset along
  the path). The breakpoint count of that form is open as far as the search went.

## §6 Evacuation planning

* Wildfire trigger buffers (Cova et al. 2005; WUIVAC, Dennison et al. 2007): reverse Dijkstra on a fire travel-time
  raster from one community, stopped at the evacuation time T. The evacuation side is one number T. The buffer "would
  have to be recomputed as wind conditions change".
* Household departure deadlines: Li, Cova, Dennison 2015, for one simulated fire. Stochastic trigger boundaries
  (k-PERIL, Kalogeropoulos et al. 2023): the share of about 1,000 fire simulations in which evacuation succeeds.
* Time-expanded road network with fire-removed nodes: Borgwardt et al. 2024, a max-flow plan, closures never reopen,
  the update is a re-solve, and warm starts are listed as future work.
* Slack against fire deadlines on fixed routes, maximised by constraint programming: Artigues et al. 2018
  (found by the Stage 3 search, `survey_notes/G_prior_art_margin_field.md`).
* **Not found:** leave-by time per place as an exact function of a margin over a road graph with closing and
  reopening segments; an exact incremental update of deadlines after one closure report; a one-pass benefit of
  delaying fire at every location.

## Limits of this survey

* Wall time was about ten minutes per topic. Many primary sources were paywalled or blocked; the notes say which
  (for example Gondran and Minoux 2008 §4.4, Knuth 1977, Halpern and Priess 1974, Dean's Networks paper, Cova 2005 in
  two of the three reports that cite it).
* No citation-forward search was done. A thesis or a transport-journal paper with the same result cannot be excluded.
* The oldest operations-research line (Halpern 1977; Sancho 1994; Cai, Kloks, Wong 1997) was read at abstract level
  only. That is where a backward dynamic programme with per-node parking limits is most likely to exist already.
