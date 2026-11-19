## Literature survey: parametric and robust shortest/bottleneck paths

`date -u` at start: Wed Nov 18 22:53:04 UTC 2026. At end: Wed Nov 18 22:56:54 UTC 2026. Wall-clock was about 4 minutes of parallel fetching, well under the 25-minute budget, so depth is limited.

**How to read "opened" below.** Three levels of evidence:
- **Read directly**: I converted the PDF to text and read or grepped the passages myself.
- **Model-summarised**: fetched through WebFetch, where a small model summarised the page for me; reliable for headline claims, not verbatim.
- **Search snippet only**: listed separately at the end as not opened.

No files were written to the project. The fetched PDFs were converted to text in `/tmp/claude-501`, outside the scratchpad.

---

### A. Sources opened

**1. Aissi, Bazgan, Vanderpooten (2009).** "Min-max and min-max regret versions of combinatorial optimization problems: a survey." EJOR 197(2):427-438.
- URL: https://www.lamsade.dauphine.fr/~bazgan/Papers/EJOR09a.pdf
- Access: author PDF, relevant sections read directly.
- Result:
  - Proposition 3: an instance of Discrete Min-Max Bottleneck P with k scenarios is solved optimally by solving P once with c'_i = max_s c_i^s.
  - Proposition 4 and Corollary 1: "Discrete Min-Max Bottleneck P and Discrete Min-Max Regret Bottleneck P reduce to P."
  - Proposition 10, attributed to Averbakh 2000 (ORL 27(2):57-65), gives the interval-data analogue.
  - Tables 3-5: Discrete Min-Max Shortest Path is NP-hard with a pseudo-polynomial algorithm for a constant number of scenarios (Yu & Yang 1998), and strongly NP-hard for a non-constant number (Kouvelis & Yu 1997). Interval min-max regret shortest path is strongly NP-hard (Averbakh & Lebedev 2004).
- Relation: this is the published statement behind question 3. Their class is pure bottleneck (min over x of max_i c_i x_i), with no path offsets.

**2. Hune, Romijn, Stoelinga, Vaandrager (2001).** "Linear Parametric Model Checking of Timed Automata." BRICS RS-01-5 (also TACAS 2001, LNCS 2031; journal version JLAP 2002).
- URL: https://tidsskrift.dk/brics/article/download/20459/18026/46459
- Access: full PDF, key sections read directly.
- Result:
  - Defines L/U automata: every parameter occurs only as a lower bound or only as an upper bound.
  - Proposition 3: [[A]](λ,μ) ⊨ ∃◇φ iff the same holds for all λ' ≤ λ, μ ≤ μ'. Weakening guards only adds reachable states; the dual holds for ∀□.
  - Proposition 4 and Corollary 1: reachability emptiness is decidable for L/U automata by checking the non-parametric automaton A[(0,∞)].
  - The tool (an Uppaal extension using parametric DBMs) synthesises linear parameter constraints, with no termination guarantee in general.
- Relation: see question 4.

**3. André, Lime, Roux (2022).** "Reachability and liveness in parametric timed automata." LMCS 18(1:31). arXiv:2004.09171.
- URLs: https://arxiv.org/abs/2004.09171 and https://ar5iv.labs.arxiv.org/html/2004.09171
- Access: abstract plus the first ~100k characters of the full text, model-summarised.
- Result:
  - EF-emptiness is decidable for L/U-PTAs (Hune et al.); monotonicity is restated as Lemma 1.
  - Citing Jovanović, Lime, Roux (2015), the set of valuations reaching a location in an L/U-PTA "cannot be represented using a finite union of polyhedra". Emptiness is decidable but exact synthesis is intractable in general.
  - Bozzelli & La Torre (2009) give exact synthesis for reachability in L-PTAs and U-PTAs over integer-valued parameters.
  - EF-emptiness is undecidable for general PTAs even with a single integer parameter.
  - Existence of a valuation with an infinite run in an L/U-PTA is PSPACE-complete.
- Relation: generic L/U synthesis does not hand us the threshold function; our structure is much more special (see question 4).

**4. Nemesch, Ruzika, Thielen, Wittmann (2025).** "A Survey of Exact and Approximation Algorithms for Linear-Parametric Optimization Problems." arXiv:2501.11544.
- URL: https://ar5iv.labs.arxiv.org/html/2501.11544 (and the PDF)
- Access: first ~100k characters model-summarised; reference list and the MST passage read directly from the PDF text.
- Result:
  - Eisner-Severance method (Eisner & Severance, JACM 23(4), 1976): between 2B-1 and 3B-2 oracle calls for B breakpoints.
  - Megiddo parametric search (Megiddo 1979, 1983); Gusfield's breakpoint enumeration (JACM 1983) runs in O(B·T²).
  - Parametric shortest path: n^Ω(log n) breakpoints (Carstensen), upper bound n^(log n + O(1)) attributed to Gusfield's 1980 thesis; simplified by Mulmuley & Shah (JCSS 2001); extended to planar graphs by Gajjar & Radhakrishnan (FOCS 2019).
  - Special case with coefficients in {-1,0}: Karp-Orlin O(n³) and O(nm log n); Young-Tarjan-Orlin O(nm + n² log n).
  - Parametric MST breakpoints: Ω(m α(n)) and Ω(m log n) (Eppstein), O(m√n) (Gusfield), O(m n^(1/3)) (Dey).
  - Read directly: "There is also a lot of literature on parametric search or finding the shortest bottleneck edge for the parametric MST. However, this is not the focus of this survey", citing Chan 2005, Fernández-Baca 2000, Fernández-Baca & Slutzki 1997, Katoh & Tokuyama 2001.
- Relation: the most recent survey of the area has no section on parametric bottleneck or max-min path problems, and nothing on a mixed bottleneck-with-offsets form in the portion read.

**5. Eppstein (2021).** "A Stronger Lower Bound on Parametric Minimum Spanning Trees." WADS 2021. arXiv:2105.05371.
- URLs: https://arxiv.org/abs/2105.05371 and https://ar5iv.labs.arxiv.org/html/2105.05371
- Access: full text, model-summarised with quoted fragments.
- Result:
  - Ω(m log n) distinct parametric MSTs under linear edge weights.
  - On the parametric bottleneck shortest path problem: any upper bound for parametric MST is also an upper bound for it, so Dey's O(m n^(1/3)) applies. The older Ω(m α(n)) lower bound applies to bottleneck paths; the new Ω(m log n) does not.
- Relation: the explicit source for polynomial breakpoint bounds in the pure parametric bottleneck problem (question 2).

**6. Eppstein blog post, 12 May 2021.**
- URL: https://11011110.github.io/blog/2021/05/12/constructive-solid-geometry.html
- Access: full post, model-summarised. Not peer-reviewed.
- Result: confirms the bottleneck upper bound via Dey; an Ω(n log n) lower bound for the bottleneck function is left open.
- Relation: same as source 5.

**7. Gajjar & Radhakrishnan (2019).** "Parametric Shortest Paths in Planar Graphs." FOCS 2019. arXiv:1811.05115.
- URLs: https://arxiv.org/abs/1811.05115 and https://ar5iv.labs.arxiv.org/html/1811.05115
- Access: abstract plus introduction, model-summarised.
- Result:
  - Planar graphs with linear edge weights can have n^Ω(log n) pieces, refuting Nikolova's conjecture.
  - Upper bound n^(log n + O(1)) attributed to Gusfield 1980 and Dean 2009; lower bounds to Carstensen 1983 and Mulmuley & Shah 2001 (the latter with O(log³ n)-bit weights).
  - No mention of bottleneck paths.
- Relation: planarity of the road graph does not rescue the additive parametric problem.

**8. Nikolova, Kelner, Brand, Mitzenmacher (2006).** "Stochastic Shortest Paths via Quasi-convex Maximization." ESA 2006, LNCS 4168:552-563.
- URL: https://www.eecs.harvard.edu/~michaelm/postscripts/esa2006c.pdf
- Access: full PDF; abstract and Section 2.2 read directly.
- Result:
  - Exact n^Θ(log n) algorithm for maximising the probability of meeting a deadline with normally distributed edge lengths.
  - The optimum lies on the parametric shortest path envelope with edge lengths u_i + λ w_i.
  - Polynomial average-case and smoothed bounds for the number of parametric breakpoints.
- Relation: a deadline-probability problem solved through a one-parameter envelope. Their parameter enters additively, ours enters only through the min terms.

**9. Young, Tarjan, Orlin (1991).** "Faster parametric shortest path and minimum-balance algorithms." Networks 21(2):205-221. arXiv:cs/0205041.
- URL: https://ar5iv.labs.arxiv.org/html/cs/0205041
- Access: full text, model-summarised.
- Result:
  - Model: G_λ = (V, E, c − λ·δ_E'), a designated subset of edges with cost decreasing at unit rate.
  - At most n² shortest-path trees and O(n²) pivots, because the count of parameterised edges on tree paths is monotone.
  - Running time O(nm + n² log n), improving Karp-Orlin's O(nm log n).
- Relation: the best-known polynomial one-pass parametric path algorithm, but for unit-slope additive parameters, not arc-specific slopes inside a min.

**10. Karp & Orlin (1981).** "Parametric shortest path algorithms with an application to cyclic staffing." Discrete Applied Mathematics 3(1):37-45.
- URL: https://dspace.mit.edu/handle/1721.1/5180 (MIT working paper OR 103-80 record)
- Access: abstract only, model-summarised.
- Result: two algorithms, O(n³) and O(n|E| log n), for shortest paths from s parametric in λ where edges of E' have length c − λ. Generalises Karp's minimum cycle mean.
- Relation: same as source 9.

**11. Chakraborty, Fischer, Lachish, Yuster (2010).** "Two-phase algorithms for the parametric shortest path problem." STACS 2010:167-178. arXiv:1001.3749.
- URLs: https://arxiv.org/abs/1001.3749 and https://ar5iv.labs.arxiv.org/html/1001.3749
- Access: full text, model-summarised.
- Result:
  - Linear weights a_e x + b_e: preprocessing Õ(n⁴), then each instantiation answers single-source shortest paths in O(m + n log n). This is done by computing reweighting potentials valid over the whole no-negative-cycle interval, not by enumerating breakpoints.
  - Randomised ε-additive variant with Õ(n^3.5) preprocessing and O(1) per pair.
- Relation: an alternative "preprocess once, answer any parameter value" design. Additive weights only.

**12. Erickson (2010).** "Maximum Flows and Parametric Shortest Paths in Planar Graphs." SODA 2010:794-804.
- URL: https://jeffe.cs.illinois.edu/pubs/parshort.html
- Access: abstract page, model-summarised.
- Result: planar max flow as parametric shortest paths in the dual in O(n log n); each directed edge enters the tree at most once. On the torus the tree can change Ω(n²) times.
- Relation: an example where special structure gives a linear number of pivots.

**13. Borradaile & Shirley (2017).** "Time-dependent shortest paths in bounded treewidth graphs." arXiv:1706.01508.
- URL: https://ar5iv.labs.arxiv.org/html/1706.01508
- Access: full text, model-summarised. This was my secondary source for Foschini-Hershberger-Suri.
- Result:
  - Restates Foschini, Hershberger, Suri (SODA 2011; Algorithmica 68(4):1075-1097, 2014): with linear edge cost functions the end-to-end arrival-time function has n^Θ(log n) breakpoints.
  - Own bound: K·n^O(log² w) for treewidth w.
- Relation: profile search over departure time is superpolynomial in the worst case. Our parameter is not departure time, and the closures are hard deadlines, not travel-time functions.

**14. Even, Schutt, Van Hentenryck (2015).** "A Constraint Programming Approach for Non-Preemptive Evacuation Scheduling." arXiv:1505.02487.
- URL: https://ar5iv.labs.arxiv.org/html/1505.02487
- Access: full text, model-summarised.
- Result: defines lastdep(p_k), "the latest time at which a vehicle can depart on p_k without being blocked", as the minimum over path edges of block time b_e minus travel time to e. Block times are fixed; there is no parametric analysis.
- Relation: this is exactly our per-path inner formula (min_k (c_k − offset_k)), published in evacuation planning for fixed closure times and given paths.

**15. Berman, Einav, Handler (1990).** "The Constrained Bottleneck Problem in Networks." Operations Research 38(1):178-181.
- URL: https://ideas.repec.org/a/inm/oropre/v38y1990i1p178-181.html
- Access: abstract only, model-summarised.
- Result: min bottleneck subject to a cost bound, min cost subject to a bottleneck bound, and all Pareto optima. Adding the bottleneck measure raises complexity by at most a factor linear in the number of links.
- Relation: the standard threshold-enumeration argument for MINSUM-MAXMIN. It relies on the bottleneck value being edge-local, which ours is not.

---

### B. Not opened: search-result snippets only

- **Carstensen 1983**, Math. Programming 26:64-75. Snippets describe exponential breakpoints for parametric min-cost flow and 0-1 programs. Attribution caveat: Nikolova et al. cite Carstensen's 1983 Michigan PhD thesis for the n^Ω(log n) shortest-path bound, while the 2025 survey cites the Math. Programming paper for the lower bound and the thesis for tightness. I could not check which document holds the shortest-path construction.
- **Gusfield 1980 thesis; Dean 2009.** Bound n^(log n + O(1)) known only through sources 4, 7 and 11.
- **Mulmuley & Shah 2001**, JCSS 63(2):253-267. Via source 7 and search snippets.
- **Foschini, Hershberger, Suri.** The SIAM PDF returned 404; relied on source 13 and snippets.
- **Eisner & Severance 1976; Megiddo 1979/1983; Murty 1980.** Via source 4 (Murty via source 11: parametric LP can change exponentially often).
- **Chan 2005** (SODA, pp. 917-918). A one-line catalogue abstract only: a randomised technique for the shortest bottleneck edge in a parametric MST.
- **Fernández-Baca & Slutzki** (1989 J. Algorithms; 1997 TCS 181:57-74). Snippets only. I found no paper of theirs specifically on parametric bottleneck paths.
- **Hansen 1980** "Bicriterion path problems". Springer redirected to a login. Snippet: polynomial algorithms for MAXMIN-MAXMIN and MINSUM-MAXMIN; a later paper quotes O(m² log n).
- **Martins 1984; Gandibleux, Beugnies, Randriamasy 2006** (4OR 4:47-59). Snippets only.
- **Quickest path:** Chen & Chin 1990 (Computers & OR 17:153-161); Rosen, Sun, Xue 1991; Pascoal, Captivo, Clímaco 2006 survey (Annals of OR 147:5-21). Snippets: O(rm + rn log n), with r the number of distinct capacities. The baes.uc.pt PDF failed DNS.
- **Kouvelis & Yu 1997; Yu & Yang 1998; Averbakh 2000; Averbakh & Lebedev 2004.** Via Aissi et al. tables and reference list, which I read directly.
- **Bertsimas & Sim 2003**, Math. Programming 98:49-71. Third-party abstract snippets: with cost uncertainty only, the robust 0-1 problem is solved by at most n+1 nominal problems.
- **Bozzelli & La Torre 2009** (FMSD; ICALP 2007); **Jovanović, Lime, Roux 2015.** Via source 3 and snippets.
- **Never reached:** Alur-Henzinger-Vardi 1993, IMITATOR / inverse method, Montemanni & Gambardella 2004, Karasan-Pinar-Yaman 2001.
- Two guessed arXiv IDs (cs/0612055, 1903.01082) turned out to be unrelated papers and were discarded.

---

### C. Answers to the four questions

**(1) Is there a published algorithm or breakpoint bound for the mixed form max over paths of min over arcs of (α_arc·μ − accumulated offset)?**

I found none. This is a negative result from about 20 searches and the 2025 survey, not proof of absence. Closest results and how they differ:

- **Additive parametric shortest path** (Karp-Orlin, Young-Tarjan-Orlin, Gusfield, Carstensen, Chakraborty et al.): the parameter enters the summed path length. Our μ never enters a sum; it only enters the arc-wise caps.
- **Pure parametric bottleneck path / MST** (Eppstein, Dey, Chan): weights linear in the parameter, objective min-max of edge-local values. No path-dependent offsets.
- **Quickest path and MINSUM-MAXMIN bicriteria** (Chen-Chin, Rosen-Sun-Xue, Hansen, Martins, Berman-Einav-Handler): additive plus bottleneck, non-parametric. Their polynomiality rests on at most r ≤ m distinct edge-local bottleneck values. In our problem the bottleneck term c_j − offset_k(P) depends on the prefix, so that argument does not transfer directly.
- **Even et al. 2015**: the exact fixed-μ per-path formula, with no optimisation over a parameter.
- **Time-dependent profile search** (Foschini et al.): a function of departure time under additive travel-time functions.
- **L/U parametric timed automata**: the right logical frame, but a generic one (question 4).

My own observations, not from the literature and unverified:
- Each path's value is a concave piecewise-linear function of μ, with slopes from {d_j} ∪ {0} and integer intercepts. L(μ) is their upper envelope and is non-decreasing in μ.
- A crude pseudo-polynomial bound on distinct linear pieces is (number of distinct d values) × (number of distinct prefix lengths).
- I found no published polynomial or superpolynomial bound for this form. The Carstensen-type lower-bound constructions use parameters inside sums and do not obviously apply. The breakpoint complexity should be treated as open and measured empirically.

**(2) Breakpoint bounds: parametric bottleneck versus parametric shortest path.**

- **Shortest path, linear weights:** n^Θ(log n).
  - Upper bound n^(log n + O(1)): Gusfield 1980, Dean 2009.
  - Lower bound n^Ω(log n): Carstensen 1983; Mulmuley-Shah 2001; planar graphs too, Gajjar-Radhakrishnan 2019.
  - Special case with slopes in {0, −1}: O(n²) trees (Karp-Orlin, Young-Tarjan-Orlin).
  - Time-dependent arrival functions: n^Θ(log n) (Foschini-Hershberger-Suri).
- **Bottleneck path, linear weights:** polynomial.
  - Upper bound O(m n^(1/3)), inherited from Dey's parametric MST bound (stated by Eppstein 2021).
  - Lower bound Ω(m α(n)) (Eppstein 1998, via Eppstein 2021). Whether Ω(m log n) holds for bottleneck paths is open.
  - The parametric MST itself has Ω(m log n) breakpoints.

**(3) Does "one route safe in every scenario" reduce to a single solve on the worst-case instance, and is that stated?**

Yes for the pure bottleneck criterion, and it is stated explicitly: Aissi, Bazgan, Vanderpooten 2009, Proposition 3 and Corollary 1 (c'_i = max_s c_i^s; "Discrete Min-Max Bottleneck P ... reduce to P"), with the interval analogue credited to Averbakh 2000.

- **Our variant with offsets:** not literally covered by that proposition. The same one-line argument works, by my reasoning: the constraint "start edge j before c_j^s for all s" is edge-separable and equals "before min_s c_j^s", and the offsets do not depend on the scenario. So one solve on the pointwise-minimum closure times is exact, provided travel times D_j are scenario-independent.
- **Where it breaks:** any additive scenario-dependent criterion. Discrete min-max shortest path is NP-hard already for 2 scenarios, pseudo-polynomial for a constant number (Yu & Yang 1998), and strongly NP-hard for unboundedly many (Kouvelis & Yu 1997). A heat-dose budget summed along the path with scenario-dependent doses, or scenario-dependent travel times, falls on this side.
- Aissi et al. also give an explicit example showing that taking the best of the per-scenario optimal paths can be arbitrarily bad for additive costs.

**(4) Does a parametric-timed-automata result already give "the set of parameter values for which a deadline is met" for our structure?**

Partly: the qualitative shape, not the threshold function.

- **Encoding.** One global clock x; edge j has guard x < d_j·μ on entry; the shelter has x < a. The margin μ occurs only as an upper bound, so this is a U-PTA. Adding departure time t as a lower-bound parameter (x ≥ t before leaving) gives an L/U automaton.
- **What Hune et al. give.** Proposition 3 says the valuations reaching the shelter are upward-closed in μ and downward-closed in t. That is exactly "L(μ) is non-decreasing and the safe set is its hypograph". Proposition 4 and Corollary 1 decide emptiness by setting μ = ∞ and t = 0.
- **What they do not give.** A terminating exact synthesis in general: Jovanović-Lime-Roux 2015 (via André-Lime-Roux 2022) show the L/U reachability valuation set need not be a finite union of polyhedra. Exact synthesis is known for L-PTAs and U-PTAs with integer parameters (Bozzelli & La Torre 2009). Tools such as Hune et al.'s Uppaal extension, and IMITATOR (not opened), are semi-algorithms.
- **Our case.** With one clock, acyclic progress and one or two parameters, the set is trivially polyhedral: it is the hypograph of a piecewise-linear function. The PTA literature therefore supplies the monotonicity justification and vocabulary, not an algorithm competitive with a Dijkstra-type pass over piecewise-linear labels. I found no PTA paper that states the result as a latest-departure function.

---

### D. Bottom line for the project

- The proposed one-pass piecewise-linear label method appears to sit in a gap between four literatures: additive parametric shortest path, parametric bottleneck, bicriteria / quickest path, and L/U-PTA synthesis. I found no prior algorithm or breakpoint bound for the exact mixed form.
- Citable support exists for three points:
  1. Monotonicity in μ: Hune et al., Proposition 3.
  2. Scenario intersection for bottleneck-type criteria: Aissi et al., Proposition 3; Averbakh 2000.
  3. The contrast in breakpoint counts: polynomial for bottleneck (Eppstein / Dey) versus n^Θ(log n) for additive (Gusfield, Carstensen, Mulmuley-Shah, Gajjar-Radhakrishnan).
- Two things to check before relying on the method:
  1. The worst-case number of breakpoints of L(μ) is not established anywhere I looked.
  2. The scenario-intersection shortcut fails for additive scenario-dependent quantities such as the dose budget (NP-hard per Yu & Yang and Kouvelis & Yu).