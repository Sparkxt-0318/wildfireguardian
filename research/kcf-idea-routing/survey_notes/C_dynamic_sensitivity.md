REPORT: dynamic/incremental shortest paths and sensitivity analysis, for the deadline-field project

`date -u` at start: Wed Nov 18 22:53:05 UTC 2026. Last `date -u` reading: Wed Nov 18 23:00:40 UTC 2026; three more page fetches followed it (about a minute), so wall-clock was about 8-9 minutes, shorter than the 25 allotted because fetches were batched. No project files were written; PDFs were only pulled into the session scratchpad for text extraction.

Reading method: "full text" means I extracted the PDF text and read the abstract, intro and the theorem/algorithm passages I cite (by grep and targeted reading), not every page.

## A. Sources opened

### Incremental / dynamic shortest paths

1. **Ramalingam & Reps, "An incremental algorithm for a generalization of the shortest-path problem," J. Algorithms 21 (1996) 267-305.**
   - URL: https://research.cs.wisc.edu/wpis/papers/jalg96.pdf (abstract page https://research.cs.wisc.edu/wpis/abstracts/jalg96.abs.html). Full text.
   - Result: Knuth's grammar problem generalised to fixed points of "strict weakly superior function" (SWSF) equations. DynamicSWSF-FP handles arbitrary mixed batches of changes in O(||δ||·(log||δ|| + M_δ)), where ||δ|| is the size of the changed region plus its successors and M_δ the cost of one function evaluation. DynamicSSF-G is a bounded incremental algorithm for SSSP with positive lengths.
   - Caveat they state: max(x1..xk) and x+y are superior but not strict superior over the non-negative reals; strictness needs positive lengths.
   - Relation: closest general template for your update. Your recurrence is strict on the time axis because every move takes at least 1 s, which is the analogue of their strictness condition. They treat scalar-valued unknowns, not interval sets.

2. **Ramalingam & Reps, "On the computational complexity of dynamic graph problems," Theoretical Computer Science 158 (1996) 233-277.**
   - URL: https://research.cs.wisc.edu/wpis/papers/tcs96a.pdf. Full text.
   - Result: defines bounded incremental computation (cost as a function of ||δ||, input change plus output change). Proposition 1: SSSP>0 edge deletion and insertion each in O(||δ|| + |δ| log|δ|); deletion is a two-phase algorithm (find affected vertices via the shortest-path DAG, then Dijkstra over the affected set only).
   - Negative results: SSSP≥0 (zero-length edges), closed-semiring path problems and meet-semilattice dataflow problems are unbounded for locally persistent algorithms.
   - Relation: your "B_j grows" update is the deletion case, "B_j shrinks" the insertion case. The unboundedness results are the warning that plain max-min (bottleneck) without the strict time offset has no bounded algorithm in that model. The D_j ≥ 1 offsets are what rescue you.

3. **Frigioni, Marchetti-Spaccamela, Nanni: fully dynamic SSSP.**
   - Opened: abstract page of the companion report "Fully Dynamic Shortest Paths in Digraphs with Arbitrary Arc Weights," ALCOM-FT TR-01-31, https://cs.au.dk/~gerth/alcom-ft/TR/ALCOMFT-TR-01-31.html. Abstract only.
   - Result: for digraphs with a k-bounded accounting function, weight decrease in O(min{m, k·n_A}·log n) and increase in O(min{m log n, k(n_A+n_B) log n + n}), with n_A the number of nodes whose distance or parent changes.
   - The J. Algorithms 34 (2000) 251-281 paper itself was not opened; its bounds (O(log n) per output update on bounded-degree/genus graphs, O(√m log n) in general) come from a search-result summary only.
   - Relation: output-bounded cost, good for bounded-degree road graphs. Scalar distances only.

4. **Koenig, Likhachev, Furcy, "Lifelong Planning A*," Artificial Intelligence 155 (2004) 93-146.**
   - URL: http://idm-lab.org/bib/abstracts/papers/aij04.pdf. Full text.
   - Result: incremental A*; explicitly built on DynamicSWSF-FP plus heuristics. Theorem 4: ComputeShortestPath expands each vertex at most twice.
   - Relation: single start-goal pair. Your field is all-states, so the heuristic focus buys nothing; the underlying machinery is source 1.

5. **Koenig & Likhachev, "D* Lite," AAAI 2002.**
   - URL: http://idm-lab.org/bib/abstracts/papers/aaai02b.pdf. Full text (abstract and intro read).
   - Result: LPA* applied backward from the goal for a moving agent; same behaviour as Stentz's focussed D* but algorithmically different.
   - Relation: same as source 4. Stentz's original D* paper was not opened.

6. **Roditty & Zwick, "On dynamic shortest paths problems," ESA 2004 / Algorithmica 61 (2011) 389-401.**
   - URL: https://u.cs.biu.ac.il/~rodittl/papers/roditty.pdf. Full text (abstract and intro read).
   - Result: incremental and decremental weighted SSSP are, in a strong sense, at least as hard as static APSP. Also a fully dynamic unweighted APSP with Õ(m√n) amortized update and O(n^{3/4}) query.
   - Relation: no worst-case win over re-solving should be expected; only output-bounded guarantees are realistic.

7. **Schultes & Sanders, "Dynamic Highway-Node Routing," WEA 2007.**
   - URL: https://ae.iti.kit.edu/documents/research/routeplanning/dynamicHNR.pdf. Full text (abstract and intro read).
   - Result: an edge-weight change is absorbed by updating preprocessed overlay data in 2-40 ms, or by a "prudent query" without any update.
   - Relation: point-to-point speed-up technique; not a field computation.

8. **Delling, Goldberg, Pajor, Werneck, "Customizable Route Planning in Road Networks" (2013 version).**
   - URL: https://www.microsoft.com/en-us/research/wp-content/uploads/2013/01/crp_web_130724.pdf. Full text (abstract and customization passages).
   - Result: separator-based three-phase scheme; a new metric is incorporated in under a second, enabling live traffic.
   - Relation: partition idea (re-customize only the cells containing changed arcs) could be transplanted; they do point-to-point scalar distances only.

9. **Baum, Dibbelt, Pajor, Wagner, "Dynamic Time-Dependent Route Planning in Road Networks with User Preferences," arXiv:1512.09132.**
   - URL: https://arxiv.org/pdf/1512.09132. Full text (abstract and intro read).
   - Result: CRP extended to time-dependent travel-time functions with fast integration of global metric changes.
   - Relation: closest road-routing work combining time-dependence with updates. Objects are piecewise-linear travel-time functions, not reachability interval sets, and it is engineering without a changed-interval bound.

10. **Foschini, Hershberger, Suri, "On the Complexity of Time-Dependent Shortest Paths," SODA 2011.**
    - URL: https://sites.cs.ucsb.edu/~suri/psdir/soda11.pdf. Full text (abstract and intro read).
    - Result: with piecewise-linear FIFO edge costs the arrival-time function can have n^{Θ(log n)} breakpoints; polynomial for restricted slopes; output-sensitive algorithm given.
    - Relation: a caution for profile-style representations. Your sets are unions of intervals from closures with constant D_j; I did not find a matching bound on your piece count.

### Temporal reachability with intervals

11. **Brito, Albertini, Casteigts, Travençolo, "A Dynamic Data Structure for Temporal Reachability with Unsorted Contact Insertions," arXiv:2102.04187 (Social Network Analysis and Mining, per source 13).**
    - URL: https://arxiv.org/pdf/2102.04187. Full text (abstract and intro read).
    - Result: timed transitive closure storing non-nested (departure, arrival) intervals per vertex pair. Insert a contact in O(n² log τ) amortized, reachability query O(log τ), space O(n²τ). Insertions only.
    - Relation: interval-valued and incremental, but all-pairs, insertion-only, and bounded in n and τ rather than in changed intervals.

12. **Brito, Albertini, Travençolo, "A Dynamic Data Structure for Representing Timed Transitive Closures on Disk," arXiv:2306.13937.**
    - URL: https://arxiv.org/pdf/2306.13937. Full text (abstract read).
    - Result: disk-based variant with (u, v, t−, t+) tuples; insertion touches O(n²τ/B) pages. Its conclusion lists handling deletion as still open.
    - Relation: confirms there is no deletion support in this line.

13. **Bilò, Gualà, Leucci, Proietti, Straziota, "Temporal queries for dynamic temporal forests," arXiv:2409.18750 (ISAAC 2024).**
    - URL: https://arxiv.org/pdf/2409.18750. Full text (abstract and definitions read).
    - Result: linear-size structures for temporal forests supporting insertion and deletion of edge labels, answering reachability, earliest-arrival and latest-departure queries in polylogarithmic worst-case time (amortized for arbitrary latencies in the incremental-only or decremental-only case). States that Brito et al. is the only prior structure for general temporal graphs.
    - Relation: the only fully dynamic exact latest-departure structure I found, but forests only.

14. **Phillips & Likhachev, "SIPP: Safe Interval Path Planning for Dynamic Environments," ICRA 2011.**
    - URL: https://www.cs.cmu.edu/~maxim/files/sipp_icra11.pdf. Full text (abstract and conclusion read).
    - Result: search states are (configuration, safe interval) rather than (configuration, timestep), with the same optimality and completeness as full time expansion. The conclusion names an incremental extension as desirable future work and explains why backward search is awkward.
    - Relation: the forward, static, single-query analogue of your interval-piece representation. Useful evidence that incremental interval-state search was open in that community as of 2011.

### Incremental fixed points / Datalog

15. **McSherry, Murray, Isaacs, Isard, "Differential dataflow," CIDR 2013.**
    - URL: https://www.cidrdb.org/cidr2013/Papers/CIDR13_Paper111.pdf. Full text (abstract and model section).
    - Result: collections vary over a partially ordered set of versions and are stored as difference traces, allowing incremental update of arbitrarily nested iterative computations.
    - Relation: a general engine in which your fixed point could be re-evaluated incrementally. No interval-set representation and no bound of your kind.

16. **Szabó, Bergmann, Erdweg, Voelter, "Incrementalizing Lattice-Based Program Analyses in Datalog," PACMPL 2 (OOPSLA 2018), Art. 139.**
    - URL: https://voelter.de/data/pub/inca-oopsla2018.pdf. Full text (abstract, intro and running example).
    - Result: DRedL extends delete-and-rederive to recursive aggregation over lattices, requiring monotone recursive aggregation. Monotonically increasing replacements are handled without a deletion phase. Running example is an interval analysis.
    - Relation: the closest lattice-valued DRed. Your R_s is a lattice value under union; "B_j shrinks" is the cheap monotone direction, "B_j grows" needs overdelete/rederive. No complexity bound in changed intervals.

17. **Zhao, Chen, Wang, Hu, "Incremental Maintenance of DatalogMTL Materialisations," arXiv:2511.12169 (AAAI 2026).**
    - URL: https://arxiv.org/pdf/2511.12169. Full text (abstract and algorithm overview).
    - Result: DRedMTL, a DRed-style algorithm for Datalog with metric temporal operators over bounded intervals; facts carry intervals and materialisations are finite fact sets plus periodic intervals. The authors present this as the first incremental algorithm for DatalogMTL. Evaluation is empirical.
    - Relation: closest published exact incremental least-fixed-point algorithm whose facts are interval-stamped. Your recurrence (shift by D_j, subtract B_j, union, waiting closure) is expressible in that style. No bound in changed intervals, and nothing exploits your heap order.

18. **Hu, Motik, Horrocks, "Modular Materialisation of Datalog Programs," arXiv:1811.02304 (AAAI 2019).**
    - URL: https://arxiv.org/pdf/1811.02304. Abstract only.
    - Result: semi-naive materialisation and incremental maintenance split into modules with custom algorithms (for example transitive closure).
    - Relation: background for plugging a specialised operator into a DRed-style framework.

### Sensitivity analysis and replacement paths

19. **Ramaswamy, Orlin, Chakravarti, "Sensitivity analysis for shortest path problems and maximum capacity path problems in undirected graphs," MIT Sloan WP 4465-03 (revised Dec 2003); journal version Math. Programming 102 (2005) 355-369 (journal details from a search record only).**
    - URL: https://web.archive.org/web/2018id_/https://dspace.mit.edu/bitstream/handle/1721.1/7389/4465-03.pdf (core.ac.uk returned 403, dspace.mit.edu 429). Full text of the working paper.
    - Result: for a given optimal s-t path in an undirected graph, all upper and lower edge tolerances for both the shortest path and the maximum capacity path (MCP) problem in O(m + K log K), K the number of path edges, via equivalence to a "Minimum Cost Interval Problem".
    - Algorithm 1 (shortest path, off-path edges, O(m)): α_e = c(P*) − min(c(P*), d(s,i)+d(j,t), d(s,j)+d(i,t)), which is the forward-plus-backward-tree trick.
    - MCP upper tolerances (Algorithms 5 and 6, O(m)): threshold the graph at c_min(P*), take the components of s and t; an off-path edge has β_e = c_min(P*) if it joins the two components, else ∞.
    - MCP lower tolerances (Algorithm 7): use a maximum-capacity spanning tree T* and α_e = max{min(b(s,i), c_ij, b(j,t))} over non-tree edges that reconnect T* − e.
    - They show the shortest-path upper-tolerance theorem fails on directed graphs (counterexample), and note Hershberger-Suri's directed claim was withdrawn.
    - Relation: see Question 2.

20. **Hershberger & Suri, "Vickrey prices and shortest paths: what is an edge worth?" FOCS 2001, 252-259.**
    - URL: https://jmvidal.cse.sc.edu/library/hershberger01a.pdf. Full text (intro, related work, undirected section).
    - Result: d(x,y; G∖e) for every edge e in O(m + n log n), using one shortest-path tree from x and one from y. Per source 19 the directed-graph claim was retracted in the FOCS 2002 erratum (erratum not opened).
    - Relation: the model "all single-element what-ifs in the cost of one solve", but for deletion in undirected shortest paths.

21. **Pettie, "Sensitivity Analysis of Minimum Spanning Trees in Sub-Inverse-Ackermann Time," arXiv:1407.1910 (ISAAC 2005; JGAA 2015).**
    - URL: https://arxiv.org/pdf/1407.1910. Full text (abstract and intro read).
    - Result: MST and shortest-path-tree sensitivity in O(m log α(m,n)), improving Tarjan's O(m α(m,n)); restates that Tarjan reduced SSSP-tree sensitivity to MST sensitivity in linear time.
    - Relation: my source for Tarjan 1982, which I did not open. These are tree-preservation tolerances ("how far before the tree changes"), not "how much does the optimum move if I raise by Δ".

### Wildfire / evacuation

22. **Harris, Forbes, Taimre, "Logic-Based Benders Decomposition for Wildfire Suppression," arXiv:2209.01371 (Computers & Operations Research 2023, journal details from search record).**
    - URL: https://ar5iv.arxiv.org/html/2209.01371. Full text (HTML, via a summarising fetch).
    - Result: fire arrival is shortest path from ignition (Finney's minimum travel time); a resource at node i adds a constant Δ to all arcs leaving i; minimise unprotected nodes. Each candidate allocation is evaluated by a from-scratch Dijkstra; cuts say a node stays unprotected unless at least ⌈(ψ − d)/Δ⌉ more nodes on its binding fire path are interdicted. Reported about an order of magnitude faster than the MIP.
    - Relation: the same "delay one cell by Δ" primitive on the fire side. No per-cell sensitivity table and no incremental re-solve.

23. **Delazeri & Ritt, "Wildfire Suppression: Complexity, Models, and Instances," arXiv:2603.29865v2 (Aug 2026).**
    - URL: https://arxiv.org/pdf/2603.29865. Full text (abstract and model sections).
    - Result: the same delay-Δ suppression problem is strongly NP-complete on planar graphs and weighted directed grids, even with simultaneous release; a new MIP is state of the art; a Rothermel-based instance generator. Discusses Hof et al. (2000).
    - Relation: choosing a set of cells to delay is hard; ranking single-cell delays (your companion study) is the polynomial special case and is not what they study.

24. **Li, Cova, Dennison, "A household-level approach to staging wildfire evacuation warnings using trigger modeling," Computers, Environment and Urban Systems 54 (2015) 56-67.**
    - URL: https://content.csbs.utah.edu/~pdennison/reprints/denn/2015_Li_etal_CEUS.pdf. Full text (abstract and method).
    - Result: build a directional fire travel-time network, reverse the arcs, run Dijkstra backward from each household for a required lead time T to get trigger buffers; rank households by available time.
    - Relation: backward Dijkstra for lead time on the fire network, static.

25. **Borgwardt, Crawford, Horton, Morrison, Speakman, "Evacuation Planning on Time-Expanded Networks with Integrated Wildfire Information," arXiv:2410.14500v2.**
    - URL: https://arxiv.org/pdf/2410.14500. Full text (abstract plus grep).
    - Result: evacuation as max flow on a time-expanded network with nodes inside the fire polygon F(t) removed; plan re-optimised when fire data is revised. Warm-starting the re-optimisation is listed as future work.
    - Relation: closest evacuation paper with changing closures; it re-solves from scratch on an explicit per-time-step expansion.

26. **Akhlaghi, Campbell, Demir, "The Flood Mitigation Problem in a Road Network," arXiv:2302.07983.**
    - URL: https://arxiv.org/pdf/2302.07983. Abstract only.
    - Result: budgeted choice of roads to upgrade to maximise accessibility to healthcare, as a network design MIP.
    - Relation: an "upgrading" formulation; no single-element sensitivity method.

## B. Could not open; what I relied on instead

- Gupta, Mumick, Subrahmanian, "Maintaining views incrementally," SIGMOD 1993 (counting and DRed): researchr.org refused the connection, ACM not tried. Relied on a search-result abstract and the descriptions inside sources 16 and 17.
- Tarjan 1982 (IPL 14:30-33): relied on Pettie and on Hershberger-Suri's related-work paragraph.
- Fulkerson & Harding 1977 (Math. Programming 13:116-118): Springer redirected to login, scilit 403. Search-result summary only: budgeted arc lengthening to maximise the shortest s-t path is equivalent to min-cost flow.
- Frigioni et al. J. Algorithms 2000 paper itself; Demetrescu & Italiano JACM 2004 (search summary: O(n² log³ n) amortized fully dynamic APSP via locally shortest paths).
- Finney 2002 minimum travel time and Finney 2007 treatment optimisation (USFS PDF URLs returned HTML): search summaries only.
- Hof, Omi, Bevers, Laven 2000: only as described in source 23.
- Delling & Wagner "Landmark-based routing in dynamic graphs" (KIT URL returned HTML): only the remark in source 7 that landmark bounds stay valid under weight increases.
- Springer page for the journal version of source 19; I read the working paper.
- Not attempted or not found: Narváez-Siu-Tzeng 2000; Stentz D*; Geisberger et al. contraction hierarchies; Shier & Witzgall 1980; Gusfield 1983; Malik-Mittal-Gupta 1989; Nardelli-Proietti-Widmayer; Krumke et al.; and "Wei, Rideout, Kirsch". For the last, a search did not confirm a paper with that author set matching the description; nearby works surfaced were Kirsch & Rideout 2003, Wei 2008/2012 fuel-treatment MIPs, and Belval-Wei-Bevers. Treat that citation as unverified.
- One wrong fetch: arXiv 1809.04027 is an unrelated biology paper, discarded.

## C. Answers to the three questions

**(1) Exact incremental algorithm for interval-set-valued reachability on an implicit time-expanded graph, with cost bounded by changed intervals?**

I did not find one. Closest, in order:
- **Ramalingam-Reps (sources 1, 2):** the right algorithmic skeleton (heap-ordered re-evaluation of inconsistent unknowns, cost in ||δ||), but for scalar unknowns. Applying it to an explicit time expansion gives a bound in changed seconds, not intervals.
- **DRedMTL (17) and DRedL (16):** exact incremental least fixed points over interval-stamped or lattice-valued facts, covering both growth and shrinkage. No changed-interval bound; generic rule engines.
- **Bilò et al. (13):** fully dynamic latest-departure with polylog updates, forests only.
- **Brito et al. (11, 12):** interval-based temporal closure, insertion-only, O(n² log τ) amortized.
- **SIPP (14):** static interval-state search; the paper itself flags the incremental version as future work.

Hedged conclusion: within these searches, an output-bounded incremental algorithm on interval pieces (a Ramalingam-Reps pass whose work items are your pieces) appears unpublished as such. The ingredients are all standard, so the defensible novelty claim is the combination and the bound, not the idea. Sources 2 and 6 say only an output-bounded guarantee is to be expected.

**(2) One-pass method giving, for every element, the change in the max-min-with-offsets optimum if its capacity/closure time is raised by Δ?**

Not found as stated. What is published (source 19, read in full):
- The shortest-path decrease trick is there explicitly (Algorithm 1, two trees, O(m)).
- The bottleneck analogue appears explicitly as min(b(s,i), c_ij, b(j,t)), but in the lower-tolerance (deletion) algorithm, with b taken from a maximum-capacity spanning tree, which is an undirected device.
- For capacity increases they compute only the tolerance threshold: whether raising an off-path edge to +∞ beats the current optimum, by a component test in the thresholded graph. They do not tabulate the new optimum as a function of the raise.
- Everything is undirected, single s-t pair, pure bottleneck: no additive offsets, no time windows, no reopenings.

My own inference, not from a source: for a single arc (u,v) raised to c', the new optimum max(old, min(b(s,u), c', b(v,t))) follows directly from Theorem 2 of source 19 plus the walk argument, and should hold in directed graphs too because raising a capacity never needs the tree-exchange step. I found no paper stating it with offsets. Two caveats for your setting:
- It is per source-target pair; you want the whole field (all states to the shelter set), which needs the forward quantity per origin or a different decomposition.
- A map cell closes several edges at once, and the single-arc formula does not decompose over a group of arcs. For cells, the published tools reduce to incremental re-solve (source 2, insertion case) or a per-cell restricted search.

Tarjan/Pettie (21) and Hershberger-Suri (20) solve neighbouring "all elements at once" problems (tree-preservation tolerances; all single-edge deletions), not all single-element upgrades.

**(3) Anything treating many "what-if one closure delayed" queries jointly?**

Nothing found for latest-departure or evacuation fields. Nearest:
- Hershberger-Suri (20): all single-edge deletions jointly, undirected shortest paths.
- Source 19: all tolerances jointly.
- Wildfire suppression papers (22, 23): evaluate each candidate delay set with a fresh Dijkstra; their Benders cuts encode "which delays on the binding path could matter", which is a pruning idea rather than a joint evaluation.
- Borgwardt et al. (25): re-solve from scratch, warm start listed as future work.

Practical reading of the literature for the companion study (my synthesis): each single-cell delay is a "sets grow" update, the cheap monotone direction in both Ramalingam-Reps and DRedL (no overdelete phase). Running the hundreds of what-ifs as independent incremental insert-updates from the one baseline solution, each costing in proportion to its own changed region, is the approach best supported by what I read.