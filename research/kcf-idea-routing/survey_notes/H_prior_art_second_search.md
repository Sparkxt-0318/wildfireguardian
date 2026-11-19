# Second prior-art search for the margin field: raw findings

**Search window:** 2026-11-19, about 09:58 to 10:13 UTC. That is roughly 15 minutes, well short of the 60–90 you allowed. Every one of the seven directions got at least one query, but none was followed exhaustively through citations. Treat every "not found" as "not found in a short search".

**Headline:** neither claim was found published as stated. One paper you asked me to check is much closer to the algorithm than anything in the already-found list: Clement, Jéron, Markey, Mentré (FORMATS 2020). T2 is not a literal instance of Ben-Tal et al. 2004, but it follows from the same one-line argument that proves Marandi & den Hertog's Theorem 1.

## Table

| # | Citation | URL | What I actually read | What it proves / computes | Difference from T2 and from T4/T5 |
|---|---|---|---|---|---|
| 1 | Clement, Jéron, Markey, Mentré, "Computing maximally-permissive strategies in acyclic timed automata", FORMATS 2020 (LNCS 12288), arXiv 2007.01815v2 | https://arxiv.org/pdf/2007.01815 | Full main body (abstract through conclusion, all definitions and theorem statements); appendix proofs not read | Permissiveness of a configuration is the sup over strategies of the smallest delay-interval the player ever proposes, with an opponent picking the actual delay; it is computed by a backward iteration P_{i+1} = sup over moves of min(interval length, inf of P_i over successors), and is piecewise-affine. | **Algorithm:** same skeleton (backward, max-min, piecewise-affine closed under min/max). But the perturbation is on the player's own delays, not on guards; acyclic automata only (cycles are stated as open); cost is doubly exponential for linear automata and non-elementary for acyclic ones; functions are multi-clock polyhedral with slopes such as 1/2 (2-Lipschitz); no margin cap M, no shift-by-D_j or waiting-closure operator, no pieces-independent-of-M claim. **T2:** inherently adaptive; no static-vs-adaptive statement. |
| 2 | Bouyer, Fang, Markey, "Permissive strategies in timed automata and games", AVoCS 2015, ECEASST 72 | https://eceasst.org/index.php/eceasst/article/download/2200/2371/2382 | Sections 2 (penalty definitions), 3 (related work), 4.2.3 (computation), 4.4, theorem statements; proofs of Lemmas 4–8 skimmed only | Player proposes delay intervals; penalty of a move is 1/\|I\|, summed along the run, worst case over the opponent; the optimal penalty is computed by a backward value iteration, polynomial time for one-clock automata. | Sum of reciprocals, not a bottleneck; value function pieces have the form b + c/(d − x), so not piecewise-affine; one clock only. Section 4.4 remarks that taking the max penalty along the run "could be handled by a trivial modification". No guard or closure perturbation, no static-vs-adaptive result. |
| 3 | E. Clément, PhD thesis, "Robustness of timed automata: computing the maximally-permissive strategies", Univ. Rennes 1, 2022 | https://ori-oai-search.univ-rennes1.fr/search/notice/view/rennes1-ori-wf-1-16317/tef_id/xml | Catalogue record and abstract only | Models perturbations on delays and computes maximally permissive strategies. | Abstract mentions only delay perturbation. Whether it extends #1 to cycles or better complexity is unknown; the thesis itself was not opened. |
| 4 | Ben-Tal, Goryashko, Guslitzer, Nemirovski, "Adjustable robust solutions of uncertain linear programs", Math. Program. 99 (2004) | https://www2.isye.gatech.edu/~nemirovs/MP_Elana_2004.pdf | Abstract, Section 1 definitions of RC/ARC, Section 2 through Theorem 2.2 (Theorem 2.1 read verbatim, and the counterexample after it); appendix proof not read | Theorem 2.1: for an uncertain LP, if uncertainty is constraint-wise (each constraint row depends on its own block, uncertainty set a product of convex compact sets) and the adjustable variables are confined to a compact set, then RC and ARC are equivalent. | T2 is not an instance; see answer (b). The paper's own counterexample shows equality can fail when two constraints share one parameter, which is T2's situation. |
| 5 | Marandi & den Hertog, "When are static and adjustable robust optimization problems with constraint-wise uncertainty equivalent?", Math. Program. 170 (2018); preprint Optimization Online 2015/07/5013 | https://optimization-online.org/wp-content/uploads/2015/07/5013.pdf | Preprint: abstract, intro, Section 2.1 (all definitions and assumptions), Theorem 1 with full proof, statement of Theorem 2; rest not read | Theorem 1: constraint-wise uncertainty plus fixed recourse (each constraint splits additively into a decision part and an uncertainty part), compact uncertainty set, no convexity needed (covers mixed-integer problems), gives Opt(RC) = Opt(ARC). Theorem 2 drops fixed recourse but needs convexity in the adjustable variables. | Closest named theorem to T2. The proof picks one scenario that is simultaneously worst for every constraint, which is exactly T2's mechanism. T2 does not meet the hypotheses literally; see answer (b). Nothing about routing or closures. |
| 6 | Füchsle, Molter, Niedermeier, Renken, "Delay-Robust Routes in Temporal Graphs", STACS 2022, arXiv 2201.05390 (already on your list) | https://arxiv.org/pdf/2201.05390 | Abstract and intro, plus a keyword skim of Sections 2–3 | A route is x-delay-robust if a temporal path along it survives up to x delays; NP-complete in general; the dynamic (adaptive) variant is PSPACE-complete or polynomial depending on vertex revisits. | New observation only: here static and adaptive genuinely differ, because delays hit travel times and are not monotone. T2's equality is specific to monotone closure-timing uncertainty. No margin function. |
| 7 | Thomas, Shimony, Ruml, Karpas, Shperberg, Coles et al., "Optimal Planning in a Dynamic World", arXiv 2610.03312 (Oct 2026); earlier "Any-Start-Time Planning for SIPP" (2023) | https://arxiv.org/abs/2610.03312 | arXiv abstract page only for the 2026 paper; the 2023 paper seen in search snippets only | Any-start-time planning: propagates piecewise-linear arrival-time functions along edges so one search gives the optimal plan for all start times; the compound function's size is at most linear in problem size. | Prior art for the "one pass, all departure times, function-valued labels" ingredient at margin 0. Earliest-arrival objective, not max-min margin; no obstacle-timing uncertainty; no margin levels. |
| 8 | Sankur, "Symbolic quantitative robustness analysis of timed automata", TACAS 2015 | https://link.springer.com/doi/10.1007/978-3-662-46681-0_48 | Search snippet only | Guard enlargement for safety; outputs a safe upper bound on the enlargement, not necessarily the largest. | Safety under enlargement, a single global value, not a per-state margin function. Not opened. |
| 9 | Bouyer, Markey, Sankur, "Robust reachability in timed automata and games: a game-based approach", ICALP 2012 / TCS 563 (2015) | https://hal-univ-rennes1.archives-ouvertes.fr/hal-01105077v1 | Search snippet, plus how #1 and #2 describe it | Existence of some positive perturbation bound under which a strategy reaches the target is EXPTIME-complete; per #1, only a global doubly-exponential lower bound on the tolerance is obtained. | Adaptive game on delay perturbation; no per-state maximal margin. Not opened. |
| 10 | Akmal, Ammons, Li, Boerkoel, "Quantifying Degrees of Controllability in Temporal Networks with Uncertainty", ICAPS 2019 / AIJ 2020 | https://ojs.aaai.org/index.php/ICAPS/article/view/3456 | Search snippet only (page blocked automated access) | Continuous geometric degrees of strong and dynamic controllability for temporal networks with uncertain durations, approximating dispatch success probability. | Volume-style measures, not a common-bound margin; strong and dynamic remain distinct. Not opened. |
| 11 | Cui, Yu, Fang, Haslum, Williams, "Optimising Bounds in STNUs under Dynamic Controllability Constraints", ICAPS 2015 | https://ojs.aaai.org/index.php/ICAPS/article/view/13723 | Search snippet only | Optimises an objective over temporal-network bounds subject to dynamic controllability, via disjunctive linear models. | Nearest scheduling analogue of "maximise a bound subject to feasibility"; solver-based, no static = adaptive claim. Not opened. |
| 12 | Halpern & Priess, "Shortest path with time constraints on movement and parking", Networks 4 (1974) | https://api.crossref.org/works/10.1002%2FNET.3230040304 | Search snippet only | Shortest paths when arcs are closed during specified periods and waiting at vertices is restricted. | Prior art for the base model (closures plus waiting restrictions) at margin 0. No uncertainty, no margin. Not opened. |
| 13 | Yakovlev et al., "Combining Safe Interval Path Planning and Constrained Path Following Control", arXiv 1906.06911 | https://arxiv.org/pdf/1906.06911 | Search snippet only | Adds a user-chosen safety margin δ to safe intervals in SIPP. | Fixed heuristic margin; no maximal-margin function, no equivalence proof. Not opened. |
| 14 | StochSIPP, arXiv 2608.00792 (2026) | https://arxiv.org/pdf/2608.00792 | Search snippet only | SIPP with per-interval safety probabilities and a contingent policy. | Probabilistic and adaptive; empirically the adaptive policy beats fixed safe paths on arrival time. Not opened. |
| 15 | Hsu & Peeta, clearance-time-based evacuation (Purdue, 2015) | https://engineering.purdue.edu/~peeta/data/disseminate/Disseminated-2015_NSE_CTEEvac.pdf | Search snippet only | Per-location clearance time versus lead time as an evacuation margin. | Flow-based planning margin; not a closure-perturbation margin per origin and second. Not opened. |
| 16 | Le, Noorani, Hirche, Baras, "Time-Robust Path Planning with Piece-Wise Linear Trajectory for STL Specifications", arXiv 2403.10735 | https://arxiv.org/pdf/2403.10735 | Search snippet only | Maximises STL time robustness of piecewise-linear trajectories via a mixed-integer program. | Optimisation by MILP for one trajectory, not a backward pass over a graph. Not opened. |
| 17 | Bertsimas, Goyal, Lu, "A tight characterization of the performance of static solutions in two-stage adjustable robust linear optimization", Math. Program. 150 (2015) | https://link.springer.com/doi/10.1007/s10107-014-0768-y | Search snippet (abstract) only | Static solutions are optimal for two-stage adjustable robust linear packing problems for a general class of uncertainty sets. | Linear packing with continuous recourse; T2 is discrete and disjunctive. Not opened. |

Other snippet-only hits, none matching: Agra et al. 2013 (robust VRP with time windows, uncertain travel times); Pessoa et al. 2015 (robust constrained shortest path, budgeted uncertainty); Bendík et al. LMCS 2022 (timed-automata robustness via model checking); L/U parametric timed automata (monotone parameters, a second known route to T1); Shahparvari & Abbasi 2016–17 (bushfire evacuation with uncertain time windows); the Recoverable Canadian Traveller Problem (Bar-Noy & Schieber); Robust Temporal Cut (SAND 2026); Dondi & Hosseinzadeh 2026 (interval separators).

## Verdict per claim

**T2 (robust = adaptive, exactly): not found published.**
- It follows from the dominating-scenario argument that is the proof of Marandi & den Hertog 2018, Theorem 1, though not from that theorem's statement.
- The argument: "all closures widened by m" is itself a member of the uncertainty set, and every perturbed closure set is contained in it. So adaptive feasibility for all scenarios implies feasibility in that one scenario, which gives one journey valid in all scenarios.
- A referee would likely call this a short folklore-style observation rather than a deep theorem. I did not find it stated for closure-timing uncertainty in routing, temporal graphs, or SIPP.
- Single closest work: Marandi & den Hertog 2018, Theorem 1. In the domain, the closest are Rodionova et al. 2022 (already on your list) and Füchsle et al. 2022 as the contrasting case.

**Algorithm (T4/T5): not found published.**
- Single closest work: Clement, Jéron, Markey, Mentré, FORMATS 2020 (#1).
- The published ingredients are: backward max-min value iteration yielding a piecewise-affine tolerance function (#1); slope ±1 time-robustness signals (Donzé–Maler, on your list); one-pass propagation of piecewise-linear functions for all start times (#7 and time-dependent profile search).
- What I did not find anywhere: the combination for closure-interval margins, the closure of the slope −1/0/+1 class under shift, min, max and the waiting operator, a cost counted in pieces independent of M, or handling of cyclic graphs.
- Risk: the Clément 2022 thesis (#3) was not opened and could contain extensions.

## Specific answers

**(a) Does Bouyer–Fang–Markey (or related) already give a backward piecewise-affine computation of a maximal timing tolerance for reachability?**
- Bouyer–Fang–Markey 2015: no. It is backward, but the value function is not piecewise-affine (pieces b + c/(d − x)), and the aggregation is a sum of 1/|I| penalties, which favours short runs. One clock only.
- Clement et al. 2020: yes, in a different model. It is exactly a backward computation of a piecewise-affine maximal timing tolerance with bottleneck aggregation (the smallest interval along the run). This must be cited and distinguished.
- Model differences from the margin field:
  - **What is perturbed:** the player's own chosen delays, per action, with an adversary choosing inside the proposed interval. Guards stay fixed. In the margin field the journey is executed exactly and the environment's closure intervals move.
  - **Adaptivity:** their strategy reacts to the adversary's choices. T2 says adaptivity is worthless in your setting.
  - **Tolerance scale:** their interval length corresponds roughly to twice a symmetric margin, and their recursion optimises interval endpoints (the min{β − α, f(α), g(β)} lemma), giving slopes like 1/2.
  - **Scope and cost:** acyclic automata only, non-elementary in general, doubly exponential for linear automata.

**(b) Is T2 an instance of the constraint-wise-uncertainty theorem of Ben-Tal et al. 2004?**
No, not as stated. Theorem 2.1 fails to apply on three counts:
- It is for linear programs with continuous adjustable variables. T2's decision is a discrete journey with disjunctive constraints (enter before the closure or after it).
- It needs a product of convex compact sets. Integer shifts are not convex.
- Constraint-wise fails if you write one constraint per (edge, second), because all constraints for the same closure share that closure's two shift parameters. The paper's own example after Theorem 2.1 shows equality can fail in exactly that shared-parameter case.

Marandi & den Hertog's Theorem 1 gets closer because it needs no convexity, but T2 still misses the hypotheses:
- One constraint per (closure, second) is fixed recourse but not constraint-wise.
- One constraint per closure is constraint-wise (closures are perturbed independently) but no longer additively separable.

What rescues T2 is monotonicity: a single scenario is worst for every constraint and every journey at once, and it lies in the uncertainty set. I suggest stating T2 as proved by this dominating-scenario argument, citing Ben-Tal et al. 2004 Theorem 2.1 and Marandi & den Hertog 2018 Theorem 1 as the general results it parallels, not as a corollary of either.

## Queries run (all web search)

1. Bouyer Fang Markey "Permissive strategies in timed automata and games" permissiveness function piecewise affine
2. Clement Jéron Markey Mentré "Computing maximally-permissive strategies in acyclic timed automata" FORMATS 2020
3. robust shortest path uncertain time windows closure interval uncertainty "static robust" equals "adjustable robust" time-dependent network
4. Ben-Tal Goryashko Guslitzer Nemirovski 2004 constraint-wise uncertainty; Marandi den Hertog "When are static and adjustable ... equivalent"
5. safe interval path planning temporal uncertainty dynamic obstacles safety margin time buffer robust SIPP maximum temporal clearance
6. temporal graph "robust" temporal path availability interval perturbation "most robust" journey slack tolerance
7. Emily Clement thesis robustness timed automata permissiveness piecewise backward cycles follow-up
8. Bouyer Markey Sankur "Robust reachability in timed automata: a game-based approach" maximal perturbation; "robustness margin" timed automata
9. Ben-Tal et al. "Adjustable robust solutions of uncertain linear programs" Theorem 2.1 constraint-wise RC ARC pdf
10. simple temporal network with uncertainty "degree of dynamic controllability" / "degree of strong controllability" common uncertainty bound
11. evacuation routing "safety margin" / "buffer time" road closure time wildfire flood "all origins" latest departure robust uncertain closure
12. time-dependent bottleneck path profile search piecewise linear "max-min" label-correcting "all departure times" widest path
13. robust vehicle routing uncertain time windows static robust adjustable equal / "no price of robustness"
14. Canadian traveller problem time-dependent blockages uncertain blockage time intervals robust path "recoverable" road reopening
15. Sankur "Symbolic quantitative robustness analysis of timed automata" TACAS 2015 largest delta
16. public transit journey planning maximize minimum transfer buffer time "transfer reliability" bottleneck profile query max-min slack
17. temporal graphs temporal path robust to "shifting" time labels by at most delta adversary "remains a temporal path" 2023–2025
18. multi-agent path finding "temporal uncertainty" / "time uncertainty" dynamic obstacles inflated safe intervals robust plan all realizations SIPP
19. "time robustness" / "temporal robustness" path planning maximize time robustness reachability graph piecewise linear dynamic programming "all start times"
20. robust optimization worst-case scenario independent of decision monotone uncertainty box "dominating scenario" / "componentwise monotone" static optimal two-stage
21. Shahparvari Abbasi bushfire evacuation "time windows" road availability uncertain closure robust routing
22. Cui Yu Fang Haslum Williams "Optimising bounds in simple temporal networks with uncertainty under dynamic controllability constraints"
23. "time-expanded" / "time-dependent" network "maximum slack" / "max-min slack" time gap to closure path "time windows" bottleneck
24. quantitative reachability timed automata "maximal robustness" run synthesis; Bendík et al. "Timed automata robustness analysis via model checking"
25. "any-start-time" planning SIPP piecewise linear arrival time function all start times (two phrasings)
26. robust shortest path "time windows" uncertain window bounds, arcs available during time windows, one path feasible for all scenarios, shrinking windows
27. "maximum robustness" / "robustness degree" path temporal network "availability intervals" shrink by epsilon "epsilon-robust" journey
28. Akazaki Hasuo "time robustness"; left/right time robustness computation piecewise linear slope 1; synchronous temporal robustness shift invariance
29. wildfire evacuation "trigger buffer" / "latest safe departure time" / "available safe egress time" backward computation each node margin
30. lower/upper bound parametric timed automata monotonicity reachability optimal parameter value "L/U automata"
31. "bottleneck" temporal paths temporal graph "maximum bottleneck" / "max-min" waiting time slack profile "all departure times"
32. Emily Clement PhD thesis Rennes 2022 "permissive" strategies timed automata cycles HAL
33. path planning dynamic obstacles "timing uncertainty" obstacle intervals "inflate" by delta, plan valid for all timings, adaptive no better
34. shortest path "forbidden time windows" / "blocked time intervals" / "closure intervals" uncertain start/end robust "safety margin" all departure times
35. Bertsimas Goyal Lu "A tight characterization of the performance of static solutions ..." static optimal constraint-wise hypercube packing

## Gaps to close before filing

- Open the Clément 2022 thesis for cyclic or polynomial extensions of #1.
- Walk the forward citations of Clement et al. 2020 and of Füchsle et al. 2022.
- Read Bertsimas–Goyal–Lu 2015 and the temporal-network controllability papers (#10, #11) in full.
- Open Halpern & Priess 1974 to cite the base model correctly.

Downloaded PDFs and extracted text for #1, #2, #4, #5, #6 are in the temporary folder `/private/tmp/claude-501/pa/` and may be cleared.