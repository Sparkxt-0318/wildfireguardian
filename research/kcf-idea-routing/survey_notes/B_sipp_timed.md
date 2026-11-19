## Literature survey: safe-interval planning and interval-based timed reachability

`date -u` at start: Wed Nov 18 22:53:04 UTC 2026. `date -u` at end: Wed Nov 18 22:57:04 UTC 2026. (The clock shows about 4 minutes; that seems short for the number of fetches, but it is what the command returned.)

No files were written. "Read" below means I viewed PDF pages myself; "via summariser" means the fetch tool's model read the full page and I rely on its extraction.

### Short answers

**(1) Backward, all-start-times, exact set of feasible departure times per vertex, with waiting not allowed everywhere:** I found no published method that does exactly this. The closest sources each miss at least one ingredient:
- **Any-start-time SIPP (Thomas et al. 2023)** is the closest in spirit: it computes a function of start time rather than a scalar. But it runs forward from one start state, assumes waiting is allowed in every safe interval, and outputs an earliest-arrival function, not a feasibility set per vertex. Its domain can have gaps (the function is infinite outside each path's [ζ, β] window).
- **SIPP-IP (Ali & Yakovlev 2023)** is the closest on the no-wait side: it propagates whole time intervals through moves, splitting them at unsafe periods, and only extends an interval upward where waiting is allowed. That is the forward mirror of your "shift, subtract B_j, waiting closure" step. But it is forward, from a single start time, and returns one optimal path.
- **Orda & Rom 1990** treats forbidden waiting and source-only waiting, and computes for "all instances of time", but as minimum-delay functions, forward, not feasibility sets with mixed per-node waiting.
- **Wu et al. 2014** computes latest-departure time to a target for every vertex by a backward scan in O(n+M), but with unrestricted waiting, so the answer is one scalar per vertex. This matches your permanent-closure special case (prefix [0, L]).
- **Timed-automata backward reachability** is the general theory your pass instantiates: iterated symbolic predecessors over unions of zones, which terminates. With a single clock (absolute time), a union of zones is a union of intervals. I found no source that specialises it to road graphs or states a complexity for that case.
- **Restless temporal walks (Himmel/Bentert et al.)** handle per-vertex minimum and maximum waiting in O(|V| + |E| log |E|), but return optimal walks from a source, not the set of feasible departure times.

**(2) Exact incremental update when one safe interval is added or removed:** I found none. 
- FlexSIPP (Hanou et al. 2026) says it "handles new delays sequentially by updating the precomputed @SIPP graphs", but gives no update algorithm or correctness proof, and mentions recomputing plans as an option.
- SRSIPP (Tang et al. 2023) reuses OPEN/CLOSED of a backward interval search only when the goal and constraint set are unchanged and the start moves; it gives no update for added or removed constraints.
- A secondary description of SIPP-IP lists incremental replanning under forecast changes as future work.
- MOPBD* (multi-objective D*-Lite-style search with safe intervals) surfaced only as a search snippet; I did not open it.

**(3) Version parameterised by obstacle speed or safety margin:** I found none in the SIPP literature. 
- The nearest is FlexSIPP's "temporal flexibility": a per-agent slack f that extends an edge's latest start β to β + f. It is computed once, not treated as a free parameter over which plans are valid.
- Hanou et al. 2024 includes a "safety envelope" as a fixed model feature (abstract only).
- The formal analogue is parametric timed automata, where André's survey says "any non-trivial problem studied is undecidable for general PTAs", with decidability for restricted cases such as parameters used only as upper or lower bounds. A monotone margin that only shrinks safe intervals is in that favourable direction, but I did not open a source proving it for your setting.
- Doyen 2007 "Robust parametric reachability for timed automata" appeared as a citation only.

### Sources opened

**1. Thomas, Shimony, Ruml, Karpas, Shperberg, Coles. "Any-Start-Time Planning for SIPP." ICAPS 2023 workshop paper (venue from search snippet; the PDF itself shows no venue).**
- URL: https://par.nsf.gov/servlets/purl/10465744. Full text, all 9 pages read.
- Result: defines @SIPP (start time unknown). Each edge gets an arrival-time function with parameters ⟨ζ, α, β, Δ⟩; path functions compose in closed form (α' = max(α_p, α_e − Δ_p), β' = min(β_p, β_e − Δ_p)); the multi-path function is the pointwise minimum. Algorithms: ASIPP (SIPP with a path function instead of scalar g, at most 11% overhead) and PEAT (partial-expansion A* collecting path functions for all start times; about 96 s precompute, 40x SIPP, average 11 path functions kept).
- It states the SIPP dominance relation "holds because any later time in an interval is reachable by waiting"; no complexity bound of its own, but cites Foschini et al. for linear function complexity with slopes {0, 1, ∞}.
- Relation: forward; all start times but one start state; waiting assumed everywhere within safe intervals; output is an arrival function whose finite domain can have gaps; not a per-vertex feasibility set.

**2. Hanou, Kemmeren, Thomas, de Weerdt. "Precomputing Multi-Agent Path Replanning using Temporal Flexibility: A Case Study on the Dutch Railway Network." arXiv:2601.04884 (2026).**
- URL: https://arxiv.org/html/2601.04884. Full text via summariser (two passes).
- Result: FlexSIPP precomputes an any-start-time plan for one delayed agent; other agents may be delayed within their "flexibility", computed by backward propagation from the goal in O(k·n²) per agent. Flexibility extends edge deadlines (β^F = β + f). Proposition 2: finds a solution within flexibility in polynomial time if one exists.
- Relation: forward search from one start; backward pass only for scalar slack; update after a new delay is described only at a high level.

**3. Hanou, Thomas, Ruml, de Weerdt. "Replanning in Advance for Instant Delay Recovery in Multi-Agent Applications." ICAPS 2024, pp. 258–266, DOI 10.1609/icaps.v34i1.31483.**
- URL: https://repository.tudelft.nl/record/uuid:e3f8a758-dc4a-4564-94ca-d2ff949ceac5. Abstract only (the AAAI OJS page was bot-blocked).
- Result: reduces delay replanning for trains to any-start-time SIPP; a delayed agent looks up its plan. Extended for agent speed, size and safety envelope.
- Relation: one agent, all start times, forward; no free margin parameter.

**4. Ali & Yakovlev. "Safe Interval Path Planning with Kinodynamic Constraints." AAAI 2023, arXiv:2302.00776.**
- URL: https://ar5iv.labs.arxiv.org/html/2302.00776. Full text via summariser.
- Result: SIPP is incomplete when waiting is impossible in some states. SIPP-IP nodes are (v, [t_l, t_u]); the interval is projected forward through each move, clipped and split by safe intervals, and its upper bound is extended only where the target state permits waiting. Proven complete and optimal; no big-O bound; about two orders of magnitude faster than time-expanded A*.
- Relation: forward; single start time; waiting only at some states (your setting); intervals as search state; one path as output.

**5. Phillips & Likhachev. "SIPP: Safe Interval Path Planning for Dynamic Environments." ICRA 2011, pp. 5628–5635.**
- URL: https://publications.ri.cmu.edu/sipp-safe-interval-path-planning-for-dynamic-environments. Abstract page only.
- Result: states are (configuration, safe interval); earliest arrival per state suffices; same optimality and completeness as time-expanded planning.
- Relation: forward, one start time, waiting everywhere, scalar per state.

**6. Narayanan, Phillips, Likhachev. "Anytime Safe Interval Path Planning for Dynamic Environments." IROS 2012, pp. 4708–4715.**
- URL: https://publications.ri.cmu.edu/anytime-safe-interval-path-planning-for-dynamic-environments. Abstract only.
- Result: anytime version with suboptimality bounds and an optional time horizon. Same assumptions as SIPP.

**7. Yakovlev & Andreychuk. "Any-Angle Pathfinding for Multiple Agents Based on SIPP Algorithm" (AA-SIPP(m)). arXiv:1703.04159, submitted to ICAPS 2017.**
- URL: https://arxiv.org/abs/1703.04159. Abstract only.
- Result: any-angle SIPP inside a prioritised multi-agent planner. Forward, single start time.

**8. Yakovlev, Andreychuk, Stern. "Revisiting Bounded-Suboptimal Safe Interval Path Planning." arXiv:2006.01195 (2020).**
- URL: https://arxiv.org/abs/2006.01195. Abstract only.
- Result: compares bounded-suboptimal SIPP variants; no single winner. Not relevant to all-start-times or no-wait.

**9. Tang, Liu, Li, Liu, Liu, Wang. "An Efficient Approach to the Online Multi-Agent Path Finding Problem by Using Sustainable Information." arXiv:2301.04446 (2023).**
- URL: https://ar5iv.labs.arxiv.org/html/2301.04446. Full text via summariser.
- Result: SRSIPP "is a backward search algorithm" from the goal over time-interval-space states, storing cost-to-goal; search context is reused when the start changes ("OPEN and CLOSED can be used directly without modification").
- Relation: backward, but a best-first search for one agent from its current state, not an all-start-times set; reuse only under an unchanged constraint set.

**10. Kerimov, Onegin, Yakovlev. "Safe Interval Randomized Path Planning For Manipulators." arXiv:2412.19567 (submitted to ICAPS 2025).**
- URL: https://arxiv.org/abs/2412.19567. Abstract only.
- Result: SI-RRT combines safe intervals with bidirectional RRT-Connect. The claim that its goal tree tracks latest feasible arrival times comes from a search snippet, not from text I read.

**11. Orda & Rom. "Shortest-Path and Minimum-Delay Algorithms in Networks with Time-Dependent Edge-Length." JACM 37(3), 1990, pp. 607–625.**
- URL: https://sites.cs.ucsb.edu/~suri/cs231/Rlist/ordaRom.pdf. Pages 1–4 read (abstract, introduction, model).
- Result: three policies: unrestricted waiting, forbidden waiting, source waiting. Algorithms find minimum delay "for all instances of time". With source waiting, a simple path achieves the unrestricted optimum; under restricted transit the minimum delay can be finite while the achieving path is infinite.
- Relation: function-of-start-time output, forward, non-FIFO allowed; all-or-nothing waiting policies rather than per-node; I did not read the algorithm or complexity sections.

**12. Wu, Cheng, Huang, Ke, Lu, Xu. "Path Problems in Temporal Graphs." PVLDB 7(9), 2014, pp. 721–732.**
- URL: https://www.vldb.org/pvldb/vol7/p721-wu.pdf. Pages 722–725 read.
- Result: Algorithm 2 computes latest-departure time from every vertex to a target by one reverse scan of the edge stream; Theorem 2 gives O(n+M) time, O(n) space. Lemma 2: a postfix-subpath of a latest-departure path need not be latest-departure.
- Relation: backward, all vertices, but unrestricted waiting and one scalar per vertex.

**13. Casteigts, Himmel, Molter, Zschoche. "The Computational Complexity of Finding Temporal Paths under Waiting Time Constraints." arXiv:1909.06437v5 (ISAAC 2020; Algorithmica 2021).**
- URL: https://arxiv.org/pdf/1909.06437. Pages 1–5 read.
- Result: Δ-restless temporal path (vertex-simple, at most Δ waiting) is NP-hard even with lifetime three, W[1]-hard by distance to disjoint paths, FPT in path length, feedback edge number and timed feedback vertex number. It notes restless walks (vertices may repeat) "can be computed in polynomial time".
- Relation: your problem allows revisits, so it is on the polynomial (walk) side; uniform Δ, existence question only.

**14. Himmel, Bentert, Nichterlein, Niedermeier. "Efficient Computation of Optimal Temporal Walks under Waiting-Time Constraints." arXiv:1909.01152; Applied Network Science 5 (2020).**
- URL: https://arxiv.org/abs/1909.01152. Abstract only.
- Result: optimal temporal walks with minimum and maximum waiting times at intermediate vertices in O(|V| + |E| log |E|) (E = time edges).
- Relation: closest polynomial algorithm for per-vertex waiting bounds; whether it is single-source and forward is not stated in the abstract.

**15. Bengtsson & Yi. "Timed Automata: Semantics, Algorithms and Tools." Lectures on Concurrency and Petri Nets, LNCS 3098, 2004.**
- URL: https://homes.cs.aau.dk/~adavid/UDBM/materials/by04-bookchapter.pdf. Pages 9–13 read (symbolic semantics, normalisation).
- Result: zone-based symbolic reachability is sound and complete (Theorem 1) but the zone graph may be infinite, so forward analysis needs k-normalisation. Non-convex results are "implemented as the union of a finite list of convex zones".
- Relation: forward; the union-of-zones representation is the multi-clock analogue of your interval sets.

**16. Bouyer, Gastin, Herbreteau, Sankur, Srivathsan. "Zone-based verification of timed automata: extrapolations, simulations and what next?" FORMATS 2022 invited, arXiv:2207.07479.**
- URL: https://ar5iv.labs.arxiv.org/html/2207.07479. Full text via summariser (first 100k of 105k characters).
- Result: reachability is PSPACE-complete (crediting Alur & Dill). Backward analysis by iterated symbolic predecessors "always terminates", but is poorly suited to discrete variables.
- Relation: backward set-valued fixpoint, the general form of your pass; no road-graph specialisation.

**17. André. "What's decidable about parametric timed automata?" STTT 21(2), 2019, arXiv:1907.01721.**
- URL: https://arxiv.org/abs/1907.01721. Abstract only.
- Result: general parametric problems are undecidable; restrictions on clocks or on parameter use (upper or lower bounds only) restore decidability for some problems.

### Could not open; what I relied on instead

- **Dean 2004, "Algorithms for minimum-cost paths in time-dependent networks with waiting policies," Networks 44(1):41–46.** core.ac.uk returned 403 and bohrium returned a bot wall. Search snippet only: waiting models where waiting at a node is "either forbidden or allowed".
- **Foschini, Hershberger, Suri, "On the Complexity of Time-Dependent Shortest Paths," Algorithmica 68(4), 2014.** dblp was bot-blocked. Relied on Thomas et al.'s description (linear function complexity for slopes {0, 1, ∞}) and a snippet (n^Θ(log n) breakpoints in general).
- **Bui-Xuan, Ferreira, Jarry, "Computing shortest, fastest, and foremost journeys in dynamic networks," IJFCS 14(2), 2003.** HAL was bot-blocked. Snippet only.
- **Alur & Dill 1994.** Not opened; secondary via source 16.
- **Li, Chen, Harabor, Stuckey, Koenig, MAPF-LNS2 / SIPPS (AAAI 2022).** Snippets only, and the author list is partly from memory. SIPPS adds soft constraints to SIPP; forward, single start.
- **MO-SIPP / MOPBD* (Ren et al.).** Snippets only. My fetch of arXiv 2010.07429 returned an unrelated UAV-exploration paper, so disregard that ID.
- **Halpern 1977 and Halpern & Priess 1974** (time-dependent shortest paths with node parking bans and arc closures). Known only through Thomas et al.'s related-work section. Worth opening: "arc closures plus limited parking at nodes" is very close to your model.
- **Doyen 2007, "Robust parametric reachability for timed automata."** Citation only.
- **"Generalized SIPP", time Petri nets, railway no-wait path search.** I did not find or open sources for these.
- **Two fetch guesses failed:** arXiv 2104.10809 is an NLP paper, not SIPPS.

### Caveat on the novelty answers

The three "none found" answers rest on about ten searches and the related-work sections of sources 1, 2 and 4. The least-checked area is the 1970s–1990s operations-research line (Halpern, Sancho 1992, Dean), which is where a backward dynamic programme with per-node parking limits is most likely to exist already.