LITERATURE SURVEY: time-dependent shortest paths, latest departure, profile search

Start `date -u`: Wed Nov 18 22:53:04 UTC 2026. End: Wed Nov 18 23:00:45 UTC 2026 (about 8 minutes of wall time, well short of the 25-minute budget; the search is therefore not exhaustive). No files were written to the project; PDFs were only cached by the fetch tool and read with pdftotext.

Reading levels: FULL = PDF text extracted and the relevant sections read; ABSTRACT = abstract or record page opened; SECONDARY = only search snippets or another paper's description.

## Headline answers

**(1) Exact feasible-departure SETS (unions of intervals with gaps), all nodes, arc windows, waiting forbidden at some nodes.** I found no published algorithm that does this. The closest pieces, none of which combines all the ingredients:
- Zeitz 2023 (FULL): forbidden waiting, non-FIFO, boolean reachability array R[v][tau] over the time-expanded graph, O(tau_max·|E|). It is forward from one source and departure time, per-second booleans, not interval sets, not backward.
- Chabini 1998 / Dean's discrete-time "decreasing order of time" pass (ABSTRACT + Dean FULL): all-to-one, all departure times, backward in time, O(mT), valid for non-FIFO and arbitrary waiting policies. Output is a per-(node, time-step) label table; the feasible set is implicit (finite labels), not manipulated as intervals.
- Bentert, Himmel, Nichterlein, Niedermeier 2020 (FULL): temporal walks with per-vertex min/max waiting (beta(v)=0 forbids waiting at v, so mixed waiting is covered), includes "reverse-foremost" (latest departure), O(|V|+|E| log|E|) in the number of time-arcs. Point model, single source, one optimal value per vertex, not the full set.
- Dehne, Omran, Sack 2012 (FULL abstract/intro/theorems): arc availability intervals with reopening, all start times, O(lambda(|E|+|V| log|V|)), output has O(lambda) breakpoints. But waiting is allowed everywhere (FIFO), so the result is a monotone profile with no gaps.
- Aubian et al. 2025 (FULL, selected sections): interval temporal graphs, s-t profile via "last departure time" sweep, near-linear, but zero delay, undirected, waiting allowed.
- Wu et al. 2014 (FULL): latest-departure time from every vertex to a target in one reverse scan, O(n+M); unrestricted waiting, one scalar per vertex.
So the project's interval-set backward pass with a waiting closure only at some nodes appears to be a combination not published as such, in what I searched. Caveat: I did not check the timed-automata (one-clock reachability) literature, which is a plausible place for an equivalent result; that is a lead from my own background, not something I verified.

**(2) Latest departure as a FUNCTION of a scalar that scales arc closure times (hazard speed).** Not found. Nearest:
- Wildfire trigger buffers (Li, Cova, Dennison 2015 FULL; Cova et al. 2005 SECONDARY): reverse Dijkstra over a fire travel-time raster for a given lead time T; nested buffers for different wind speed/fuel scenarios are produced by rerunning, not by a parametric profile.
- Maheshwari, Nouri, Sack 2018 (ABSTRACT): earliest-arrival function A(t) among growing discs; the bounds depend on the ratio V_r/V_c (robot speed / disc growth rate), but the growth rate is not treated as a parameter of the output.
- Parametric shortest paths (Gusfield, Carstensen; SECONDARY) have weights linear in a parameter with n^{Theta(log n)} breakpoints; Foschini et al. (FULL abstract) reduce from this for their lower bound. Different problem: the parameter scales weights, not closure times.
- Hasan & Van Hentenryck (partial read of ar5iv): arcs have "block times" and nodes "evacuation deadlines" taken from a flood simulation; sensitivity analysis is on population, flow rates and horizon, not hazard speed (the last 40% of the page was not read).

**(3) Complexity statements for forbidden-waiting / time-window reachability.**
- Orda & Rom 1990 (FULL): for forbidden waiting, shortest paths may be non-simple and non-concatenated; "(The problem can be shown to be NP-hard.)" stated without proof; a shortest path can even need infinitely many hops in continuous time.
- Zeitz 2023 (FULL): proves earliest arrival with no waiting and integer travel-time functions is weakly NP-hard (Theorem 2), with a pseudo-polynomial O(tau_max·|E|) algorithm; strongly NP-hard for rational-valued functions (Corollary 3) and for piecewise-linear functions given by integer breakpoints (Theorem 7). Notes the Orda-Rom proof was only in an unpublished 1989 Technion report.
- Dean, FIFO report (FULL): non-FIFO EA_sd(t) is NP-hard by reduction from Subset-Sum; discrete time solves all departure times in O(mT); arbitrary waiting policies add O(nT^2) waiting arcs, reducible to O(mT) in common cases.
- Cai, Kloks, Wong 1997 (ABSTRACT): pseudo-polynomial algorithms for arbitrary, zero, and per-vertex-bounded waiting.
- He, Boland, Nemhauser, Savelsbergh 2020 (FULL, theorems read): limit on waiting at ALL nodes is weakly NP-hard for W>=0 (Theorem 3, from Exact Path Length, even with constant travel times, because the path must end exactly at the horizon); waiting forbidden at a PROPER subset of nodes is polynomial (Theorem 8). I did not verify whether their polynomial cases assume FIFO.
- Omer & Poss 2019 (FULL intro): per-node waiting bounds make the problem NP-hard, solvable in time polynomial in n, m and W (i.e. pseudo-polynomial); a global waiting bound is polynomial for continuous piecewise-linear travel times.
- Casteigts, Himmel, Molter, Zschoche (FULL, theorems): restless temporal PATH is NP-complete for every finite Delta>=1 and W[1]-hard for distance to disjoint paths; restless WALKS are polynomial (citing Himmel et al.). Aubian et al. cite a result that no-waiting restless path is NP-hard in interval temporal graphs of vertex-interval-membership-width 3.
- My inference (not a citation): the project's case (walks, constant integer D_j, interval closures, shelter windows) is polynomial in the time-expanded size, hence pseudo-polynomial; He et al.'s Theorem 3 style reduction suggests no algorithm polynomial in the number of intervals with binary-encoded times should be expected when waiting is forbidden everywhere. This needs checking against whether Exact Path Length hardness holds for walks.

## Sources opened

1. Orda, A., Rom, R. (1990). Shortest-path and minimum-delay algorithms in networks with time-dependent edge-length. J. ACM 37(3):607-625. https://sites.cs.ucsb.edu/~suri/cs231/Rlist/ordaRom.pdf — FULL. Arbitrary delay functions; three policies: unrestricted waiting (UW), forbidden waiting (FW), source waiting (SW). UW1 is Dijkstra-like, O(|V|^2); UW2 computes minimum delay for ALL starting times at once with O(|V||E|) function operations and must be Ford-type. FW: no efficient algorithm, NP-hard asserted; SW equals UW for continuous or negatively-discontinuous delays (Theorem 3). Relation: UW2 is the origin of "profile search"; confirms that forbidden waiting breaks dominance. Links becoming unavailable (infinite weight) are mentioned only as background.

2. Zeitz, T. (2023). NP-hardness of shortest path problems in networks with non-FIFO time-dependent travel times. Inf. Process. Lett. 179:106287. https://publikationen.bibliothek.kit.edu/1000147976/148924256 — FULL. Results as in answer (3). Motivating example is a tunnel open only at certain times with no parking. Relation: the cleanest published complexity reference for the project's forbidden-waiting setting; its Algorithm 1 is a forward analogue of the project's pass on single seconds.

3. Dean, B. C. (2004). Shortest paths in FIFO time-dependent networks: theory and algorithms. Technical report, MIT. https://people.csail.mit.edu/bdean/tdsp.pdf — FULL. Defines LD_sd (latest departure) as inverse of EA_sd under FIFO; time-reversal transformation turns earliest-arrival into latest-departure problems; notes time reversal "no longer applies" in non-FIFO networks, where LD variants must be solved directly. Discrete time: O(mT) over the time-expanded graph in topological (reverse chronological) order. Relation: the project's backward pass is this O(mT) scan compressed to intervals; the report gives no interval-set version for non-FIFO.

4. Foschini, L., Hershberger, J., Suri, S. (2011/2014). On the complexity of time-dependent shortest paths. SODA 2011; Algorithmica 68(4):1075-1097. https://sites.cs.ucsb.edu/~suri/psdir/soda11.pdf — FULL abstract and intro, theorem list skimmed. With piecewise-linear FIFO edge functions the shortest path can change n^{Theta(log n)} times; polynomial for restricted slopes; output-sensitive algorithm; (1+eps)-approximation; minimum-delay path over a departure interval in polynomial time. Assumes waiting allowed to neutralise non-FIFO. Relation: profile size bound for continuous travel-time functions; not applicable to forbidden waiting or gapped sets.

5. Dehne, F., Omran, M. T., Sack, J.-R. (2012). Shortest paths in time-dependent FIFO networks. Algorithmica 62:416-435. https://people.scs.carleton.ca/~dehne/papers/1-61.pdf — FULL (abstract, model, theorems). TDSP_int: each link has disjoint availability intervals with a travel time per interval; outside them one waits for the next interval. All start times solved in O(lambda(|E|+|V| log|V|)); O(lambda) breakpoints in the output; TDSP_lin in O((F_d+gamma)(|E|+|V| log|V|)). Relation: closest match on arc availability intervals with reopening, but waiting is allowed at every node.

6. Wu, H., Cheng, J., Huang, S., Ke, Y., Lu, Y., Xu, Y. (2014). Path problems in temporal graphs. PVLDB 7(9):721-732. https://www.vldb.org/pvldb/vol7/p721-wu.pdf — FULL. Defines earliest-arrival, latest-departure, fastest, shortest paths within [t_alpha, t_omega]; Algorithm 2 computes the latest-departure time from every vertex to a target in one scan of the reverse edge stream, O(n+M) time, O(n) space. Relation: scalar analogue of the deadline field under unrestricted waiting (where sets are prefixes).

7. Bentert, M., Himmel, A.-S., Nichterlein, A., Niedermeier, R. (2020). Efficient computation of optimal temporal walks under waiting-time constraints. Applied Network Science 5:73 (arXiv:1909.01152). https://arxiv.org/pdf/1909.01152 — FULL. Per-vertex minimum alpha(v) and maximum beta(v) waiting; optimal walks for foremost, reverse-foremost, fastest, shortest, etc. and linear combinations, from one source to all vertices, in O(|V|+|E| log|E|) (Theorem 1). Notes maximum-waiting constraints force cycles and that the path version is NP-hard. Relation: the nearest polynomial algorithm with waiting forbidden at only some nodes; point model, so interval closures must be expanded.

8. Casteigts, A., Himmel, A.-S., Molter, H., Zschoche, P. (2020/2021). Finding temporal paths under waiting time constraints. ISAAC 2020; Algorithmica 83:2754-2802. https://drops.dagstuhl.de/opus/volltexte/2020/13374/pdf/LIPIcs-ISAAC-2020-30.pdf (and arXiv abs 1909.06437) — FULL (theorems). Results as in answer (3); FPT in path length. Relation: hardness is for simple paths only; the project's walk semantics stay on the polynomial side.

9. He, E., Boland, N., Nemhauser, G., Savelsbergh, M. (2020). Time-dependent shortest path problems with penalties and limits on waiting. https://optimization-online.org/wp-content/uploads/2019/02/7083.pdf (published INFORMS J. Comput. 33(3):997-1014 per search record) — FULL (intro, Theorems 1-3, 8). Results as in answer (3). Relation: the only source I found that treats waiting restricted at a SUBSET of nodes explicitly.

10. Omer, J., Poss, M. (2019). A polynomial algorithm for minimizing travel time in time-dependent networks with waits. https://optimization-online.org/wp-content/uploads/2019/03/7101.pdf — FULL (abstract, intro, Theorem 1). Global waiting bound W; polynomial in n, m and breakpoints for continuous piecewise-linear travel times. Intro summarises prior pseudo-polynomial DP work (Cai et al.; Chabini; Dean) and the per-node-bound NP-hardness.

11. Batz, G. V., Geisberger, R., Sanders, P., Vetter, C. (2013). Minimum time-dependent travel times with contraction hierarchies. ACM JEA 18, art. 1.4. https://publikationen.bibliothek.kit.edu/1000139527/142975495 — FULL (grep-level read of the relevant sections). Travel-time profile queries on FIFO piecewise-linear functions; profile search attributed to Orda & Rom 1990; backward profile search and latest-departure times defined; under 40 ms for a 24-hour profile on Germany. Relation: engineering of profile search; FIFO only, no closures with forbidden waiting.

12. Dibbelt, J., Pajor, T., Strasser, B., Wagner, D. (2018). Connection Scan Algorithm. ACM JEA 23 (arXiv:1703.05997). https://arxiv.org/pdf/1703.05997 — FULL (profile section). All-to-one earliest-arrival profile by scanning connections in decreasing departure time, storing a profile per stop. Relation: same backward-in-time sweep structure as the project's pass; waiting at stops allowed.

13. Aubian, G., Brunelli, F., Dragan, F., Ducoffe, G., Habib, M., Ibiapina, A., Viennot, L. (2025). Complexity gaps between point and interval temporal graphs for some reachability problems. arXiv:2501.11380. https://arxiv.org/abs/2501.11380 and PDF — ABSTRACT + FULL (profile section). Interval model can be exponentially more compact than the point model; fastest path is near-linear in the point model but quadratic (conditionally) in the interval model; near-linear s-t profile for undirected zero-delay interval graphs (Theorem 6). Relation: direct evidence that interval-native algorithms differ in complexity from time-expanded ones.

14. Li, D., Cova, T. J., Dennison, P. E. (2015). A household-level approach to staging wildfire evacuation warnings using trigger modeling. Comput. Environ. Urban Syst. 54:56-67. https://content.csbs.utah.edu/~pdennison/reprints/denn/2015_Li_etal_CEUS.pdf — FULL (abstract, method). Trigger buffers by reversing arcs of a fire travel-time network and running Dijkstra from a location with lead time T; households ranked by available time. Relation: domain analogue of a deadline; no road-network time windows, no parametric profile.

15. Chabini, I. (1998). Discrete dynamic shortest path problems in transportation applications: complexity and algorithms with optimal run time. Transp. Res. Rec. 1645:170-175. https://bibbase.org/network/publication/chabini-discretedynamicshortestpathproblemsintransportationapplicationscomplexityandalgorithmswithoptimalruntime-1998 — ABSTRACT. All-to-one shortest paths for all departure time intervals with run time equal to the problem's complexity. The "decreasing order of time" name and the waiting-allowed/not-allowed variants come from search snippets about the 1997 IFAC paper (SECONDARY).

16. Cai, X., Kloks, T., Wong, C. K. (1997). Time-varying shortest path problems with constraints. Networks 29(3):141-149. https://iaorifors.com/paper/35081 — ABSTRACT. As in answer (3).

17. Dean, B. C. (2004). Algorithms for minimum-cost paths in time-dependent networks with waiting policies. Networks 44(1):41-46. https://iaorifors.com/paper/45565 — ABSTRACT. Surveys classes of waiting policies and DP speed-ups in discrete time. Running times O(PT+mT) etc. are from a search summary only.

18. Sancho, N. G. F. (1994). Shortest path problems with time windows on nodes and arcs. J. Math. Anal. Appl. 186(3):643-648. https://iaorifors.com/paper/27253 — ABSTRACT. DP formulation with one window [alpha, beta] per node and per arc; a zbMATH review (search snippet) says complexity analysis is missing.

19. Phillips, M., Likhachev, M. (2011). SIPP: Safe interval path planning for dynamic environments. ICRA, pp. 5628-5635. https://publications.ri.cmu.edu/sipp-safe-interval-path-planning-for-dynamic-environments — ABSTRACT. States are (configuration, safe interval) pairs. Relation: interval-compressed time expansion, forward, single start time.

20. Kleff, A., Schulz, F., Wagenblatt, J., Zeitz, T. (2020). Efficient route planning with temporary driving bans, road closures, and rated parking areas. SEA 2020 (arXiv:2004.09163). https://arxiv.org/abs/2004.09163 — ABSTRACT. Timed closures with waiting only at parking areas; Pareto arrival time vs cost; polynomial under a constraint on cost parameters. Relation: same modelling ingredients (reopening closures, waiting only at some nodes), forward single query.

21. Maheshwari, A., Nouri, A., Sack, J.-R. (2018). Time-dependent shortest path queries among growing discs. arXiv:1808.01984. https://arxiv.org/abs/1808.01984 — ABSTRACT. As in answer (2).

22. Thejaswi, S., Lauri, J., Gionis, A. Restless reachability problems in temporal graphs. arXiv:2010.08423. https://arxiv.org/abs/2010.08423 — ABSTRACT. Restless path reachability, O(2^k·k·m·Delta) time.

23. Fluschnik, T., Pucic, A., Renken, M. (2026). Smooth routing in decaying trees. arXiv:2603.23504. https://arxiv.org/abs/2603.23504 — ABSTRACT. Edges become impassable over time (floods, fires); ILP for the latest possible evacuation time; NP-hard on stars and paths (the hardness comes from capacities).

24. Hasan, M. H., Van Hentenryck, P. Large-scale zone-based evacuation planning. arXiv:2003.11005. https://ar5iv.arxiv.org/html/2003.11005 — PARTIAL (first 100k characters). As in answer (2); closures appear permanent.

## Could not open; what I relied on instead

- Cooke & Halsey 1966 (JMAA 14:493-498): search record only; described by He et al. and Omer-Poss as the discrete-time Bellman-equation origin.
- Dreyfus 1969 (Oper. Res. 17(3):395-412): search-result abstract only; Foschini et al. note Dreyfus implicitly assumed unrestricted waiting.
- Orda & Rom 1991 (Networks 21:295-319): search snippet only (time-dependent weights and delays; optimal paths may be infinite).
- Kaufman & Smith 1993 (IVHS Journal 1(1):1-11): search-result abstract only (consistency/FIFO condition gives static-complexity fastest paths). The PDF I fetched from umich turned out to be Kaufman, Smith, Wunderlich 1997, which only cites it.
- Ziliaskopoulos & Mahmassani 1993 (TRR 1408:94-100): TRID refused connection; search snippet only (all nodes to one destination for every time step).
- Daganzo 2002 (Transp. Res. B 36(7):665-668): EconPapers page had no abstract, ITS Berkeley 404, scispace returned nothing; search snippet says a forward FIFO quickest-path algorithm also solves the backward problem. Dean's report gives the equivalent time-reversal argument, which I read.
- Halpern 1977 (Z. Oper. Res. 21:117-124): only a third-party blog note (opened) and Orda & Rom's critique (read in full): waiting restricted to given intervals per node, FW is a special case, and the algorithm can fail without tighter assumptions.
- Pallottino & Scutellà 1998 (Chrono-SPT): search snippets only.
- Bui-Xuan, Ferreira, Jarry 2003: lip6 refused connection, HAL blocked by bot protection; search snippet only.
- Delling 2008 "Time-dependent SHARC-routing": URL 404; the KIT link returned a different paper (Brunel et al., Space-efficient SHARC). Profile search is covered through Batz et al.
- Desrochers & Soumis 1988 / Desrosiers et al. SPPTW: search snippet only (pseudo-polynomial O(|A|W) label setting).
- Cova, Dennison, Kim, Moritz 2005: not retrieved; described from Li et al. 2015.
- Omer & Poss "Time-dependent shortest paths with discounted waits" (Networks 74:287-301): search snippet only.
- "Any-Start-Time Planning for SIPP" (Thomas et al. 2023): AAAI site blocked; search snippet only (arrival-time functions per state so one search covers all start times). Worth a proper read, since it is the interval-native all-start-times idea in robotics.
- Dean's waiting-policies paper full text (core.ac.uk 403) and the MIT thesis (dspace 429) were not read.
- Even, Schutt, Van Hentenryck 2015 (arXiv:1505.02487): abstract only; the "last possible departure time" definition came from a search snippet.