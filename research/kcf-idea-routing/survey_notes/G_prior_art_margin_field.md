## Prior-art report: "margin field"

**(i) Timestamps.** `date -u` at start: Wed Nov 18 22:59:24 UTC 2026. At end: Wed Nov 18 23:02:56 UTC 2026 (a final check of two sources ran after that reading). The system clock shows about 3.5 minutes, far short of the 30 allowed, so this is a targeted pass and not an exhaustive one.

**Bottom line.** I did not find the margin field itself published: no paper computes, for a time-dependent closure/reopening road network, the largest closure-time dilation per departure second for all margins at once. But claim A is a direct corollary of a published general theorem, claim C is a known phenomenon in STL temporal robustness, and claim D has a close published analogue. Claim B is the least covered.

### (ii) Sources opened

| # | Source | URL | How much read | Precise result |
|---|---|---|---|---|
| 1 | Bruns & Godefroid, "Model Checking with Multi-Valued Logics", ICALP 2004 | https://patricegodefroid.github.io/public_psfiles/icalp2004.pdf | Full text extracted; read Sec. 3.1–3.2 | For a Kripke structure M over a finite distributive lattice L and a negation-free mu-calculus formula φ, M_x is M with propositions thresholded at x. Lemma 1: for join-irreducible x, (M_x, s) ⊨ φ iff x ≤ [(M,s), φ]. Theorem 1: the value is the join of the join-irreducibles x whose M_x satisfies φ. Sec. 3.2 extends this to lattice-valued transitions, with ◇ interpreted as the join over successors of R(s,s') ∧ value(s'). They note binary search over thresholds when the join-irreducibles are linearly ordered. |
| 2 | Donzé & Maler, "Robust Satisfaction of Temporal Logic over Real-Valued Signals", FORMATS 2010 | https://www-verimag.imag.fr/~maler/Papers/sensiform.pdf | Full text extracted; read Sec. 3.2, 4, 4.3 | Def. 4: left/right time robustness θ∓ of an atomic proposition is the signed distance to its nearest past/future switching point, then propagated through the formula by the min/max rules. Thm 2: if θ = s, shifting events by less than s preserves satisfaction (sufficient condition only). Sec. 4 gives an algorithm on piecewise-affine signals, closed under the operators; conjunction cost is linear in sample count. |
| 3 | Rodionova, Lindemann, Morari, Pappas, "Temporal Robustness of Temporal Logic Specifications: Analysis and Control Design", ACM TECS 2022 (arXiv 2203.15661) | https://ar5iv.labs.arxiv.org/html/2203.15661 | First ~160k of 252k characters, via a summarising fetch tool | Synchronous robustness η is the distance from t to the next switch of the formula's own satisfaction signal. Asynchronous robustness θ is the Donzé–Maler recursion from predicate level. Thm 4.10: \|θ\| ≤ \|η\|, "often strict". Lemmas 4.11/4.12: equality for the (∧, □) fragment when satisfied and the (∨, ◇) fragment when violated. Thm 5.4: η is exactly the tolerated synchronous shift. Thm 5.6: θ is only sufficient for asynchronous shifts, with a counterexample to tightness. η is piecewise linear with slopes ±1. Sec. 4.2 notes θ⁺ of p∨q equal to 1 at t=5 while p∨q stays true through t=9. Control is by MILP. |
| 4 | Rodionova et al., "Time-Robust Control for STL Specifications", CDC 2021 (arXiv 2104.02677) | https://arxiv.org/abs/2104.02677 | Abstract | MILP maximising STL time robustness. |
| 5 | Rodionova et al., "Combined Left and Right Temporal Robustness for Control under STL Specifications" (arXiv 2306.04936) | https://arxiv.org/abs/2306.04936 | Abstract | One measure covering left and right shifts together; MILP control for linear systems. |
| 6 | Sankur, Bouyer, Markey, "Shrinking Timed Automata", FSTTCS 2011 | https://drops.dagstuhl.de/storage/00lipics/lipics-vol013-fsttcs2011/LIPIcs.FSTTCS.2011.90/LIPIcs.FSTTCS.2011.90.pdf | Full text extracted; read abstract, intro, Thm 5, skimmed Sec. 4–5 | Guards are tightened by per-constraint parameters times δ. They decide existence of parameters keeping the automaton non-blocking (PSPACE) and time-abstract-simulating the original (EXPTIME), and compute the least shrinking parameters. Technique: shrunk DBMs M − δP and max-plus fixpoint equations, valid for small enough δ. |
| 7 | Jaubert & Reynier, "Quantitative Robustness Analysis of Flat Timed Automata", FoSSaCS 2011 | https://pageperso.lis-lab.fr/~pierre-alain.reynier/publis/fossacs11.pdf | Pages 1–3 (abstract, intro, related work) | Under guard enlargement by δ, computes the parametric reachability set of a flat timed automaton, hence the largest δ for which it is safe; that δ is rational. Parametric zones plus cycle acceleration. |
| 8 | Hanou, Kemmeren, Thomas, de Weerdt, "Precomputing Multi-Agent Path Replanning using Temporal Flexibility" (FlexSIPP), arXiv 2601.04884 | https://arxiv.org/html/2601.04884v1 | Full HTML, via the summarising fetch tool | Temporal flexibility f_a(x_j, t_j) is the delay an agent can absorb without reordering agents; computed by a backward min-recursion along one fixed trajectory, O(k·n²) per agent. The search returns piecewise-linear arrival-time functions. No global margin parameter, no sweep over margins. |
| 9 | Füchsle, Molter, Niedermeier, Renken, "Delay-Robust Routes in Temporal Graphs", STACS 2022 (arXiv 2201.05390) | https://arxiv.org/pdf/2201.05390 | Abstract, intro, problem definition, Thm 4 | A vertex sequence is x-delay-robust if a temporal path follows it even when up to x time arcs are delayed by at most δ. NP-complete in general; polynomial on forests; checking a given route is polynomial. |
| 10 | Enright, Larios-Jones, Meeks, Pettersson, "Reachability in temporal graphs under perturbation" (arXiv 2404.19479) | https://arxiv.org/abs/2404.19479 | Abstract | Up to ζ edge timestamps perturbed by ±δ; asks worst-case maximum reachability. Intractable in general, tractable for large ζ. |
| 11 | Artigues, Hébrard, Pencolé, Schutt, Stuckey, "Data instance generator and optimization models for evacuation planning in the event of wildfire", CEUR Vol-2146 (2018) | https://ceur-ws.org/Vol-2146/paperA4.pdf | Abstract, Sec. 2.3, objective (10), experiments | Maximises the minimum population-weighted slack between each evacuation arc's fire deadline b_e and the last use of the arc. Roads close once and never reopen; routes are fixed; solved by constraint programming. Motivated explicitly as a substitute for modelling uncertainty in closure times. |
| 12 | Bendík, Sencan, Gol, Černá, "Timed Automata Robustness Analysis via Model Checking", LMCS 2022 (arXiv 2108.08018) | https://arxiv.org/abs/2108.08018 | Abstract | Repair and robustness of timing constants for reachability and safety specifications; details not on the abstract page. |

Search-result snippets only (not opened): Bouyer–Markey–Sankur robust reachability (TCS 2015) and the RP 2013 survey; Donzé–Ferrère–Maler CAV 2013; Wendt–Coyle–Gallagher 1986 "Stack filters"; Wilson et al. STN flexibility (IJCAI 2013 / AIJ 2014); Mitchell et al. PERIL (Safety Science 2023); Kupferman–Lustig lattice automata; Artigues et al. multi-mode RCPSP with safety-margin maximisation; StochSIPP; Esfandeh–Batta–Kwon time-dependent closures.

### (iii) Verdict per claim

**Claim A (threshold decomposition): published in a more general form; direct corollary.**
- On a bounded horizon the time-expanded graph is a finite Kripke structure whose edge labels take values in the chain {−1, 0, 1, …}. μ is the value of the reachability formula μX.(goal ∨ ◇X) with chain-valued transitions.
- Bruns–Godefroid Lemma 1 with Sec. 3.2 gives "value ≥ m iff the m-thresholded Boolean structure satisfies the formula", for all m.
- The only instance-specific step is elementary: β_j(t) ≥ m iff t is outside B_j ⊕ [−m, m]. Uniqueness follows from D_j ≥ 1 and the t+1 waiting step.
- The same fact is the bottleneck-path/threshold equivalence and the stack-filter threshold decomposition; I did not open those primary sources.
- The leaf-distance-then-min/max shape of the equation is the Donzé–Maler Def. 4 recursion.
- Not found: this equation written for this road/shelter/waiting model.

**Claim B (robust = adaptive, exact): not found exactly.**
- The sufficiency half (μ ≥ m implies one journey survives all perturbations within m) is the analogue of Donzé–Maler Thm 2 and Rodionova Thm 5.6.
- The exactness half is not in those papers; they stress that asynchronous robustness is not tight in general. Here it holds because the property is monotone in the closure sets, so the m-dilated instance is the pointwise worst case. That is a short argument, but I found no statement of it.
- Temporal-graph robustness work (sources 9, 10) uses budgeted delays of time arcs and gets NP-hardness; that is a different model.
- Timed-automata shrinking (source 6) treats non-blockingness and simulation for infinitesimal δ, not the maximal margin for reachability.

**Claim C (μ is not the distance transform of the feasible window): known phenomenon, not found for this model.**
- This is the gap between synchronous and asynchronous temporal robustness: Rodionova Thm 4.10, "often strict", with the p∨q example in Sec. 4.2. The inference that a gap must occur where a disjunction is satisfied is mine, from Lemma 4.12.
- The STL results are for one-sided shifts; the two-sided version (source 5) I read only as an abstract.

**Claim D (one heap-ordered backward pass over slope-{−1,0,+1} functions, cost independent of the number of margins): not found as stated; close analogue published.**
- Donzé–Maler Sec. 4 (and, by snippet, Donzé–Ferrère–Maler CAV 2013) compute time robustness as piecewise-linear functions closed under min/max and temporal operators. That is the same function-class idea, for a formula over a trace.
- The time-dependent-routing profile search of FlexSIPP/@SIPP propagates piecewise-linear functions through a graph, but for arrival times, not margins.
- I found no heap-ordered pass on a cyclic road graph with reopening closures and blocked waiting.
- The general reduction (source 1) costs one Boolean run per threshold, or log(n) runs by binary search for a single state; "all margins in one pass" is not implied by it.

### (iv) Three closest prior works

1. **Donzé & Maler 2010, with Rodionova–Lindemann–Morari–Pappas 2022.** Their asynchronous time robustness is structurally the margin field: signed distance to the nearest switch at the leaves, min/max propagation, a perturbation-tolerance theorem, piecewise-linear slope-±1 computation. The differences: it is defined for an STL formula over one trace, not a least fixed point over a cyclic graph with travel-time shifts and waiting; the shifts are one-sided (two-sided only in the 2023 follow-up); and their theorem is sufficiency only, whereas claim B asserts exactness for this monotone reachability class.

2. **Bruns & Godefroid 2004** (also Gurfinkel & Chechik, CONCUR 2003, not opened). Their reduction theorem is claim A in general form: a lattice-valued mu-calculus value equals the set of thresholds whose Boolean model satisfies the formula. It has no temporal content: no distance transforms, no dilation or robustness reading (B), and its algorithm runs once per threshold instead of one pass over piecewise-linear functions (D).

3. **Sankur, Bouyer & Markey 2011**, with Jaubert & Reynier 2011 for the "largest parameter" side. These are the timed-automata analogues of tightening every timing constraint by a parameter. Sankur et al. preserve non-blockingness and simulation for small enough δ via max-plus equations on shrunk DBMs; Jaubert–Reynier compute the largest safe δ under enlargement for flat automata only. Neither gives a per-state, per-time maximal-margin function for reachability, a (max, min) threshold decomposition, or an all-margins single pass.

Closest in application: Artigues et al. 2018 maximise a minimum temporal slack against fire arrival for the same stated reason (uncertain closure times), but with single non-reopening deadlines, fixed routes, and one optimal value, not a field over departure times.

### (v) Could not open or only partly read

- core.ac.uk copy of "Shrinking timed automata" returned HTTP 403 (read the Dagstuhl PDF instead). The Information & Computation 2014 journal version was not opened.
- Rodionova et al. TECS 2022: the last ~92k characters (later sections, appendix) were not read, and Example 1, said to show strictness, was not seen.
- Not opened at all: Fainekos & Pappas 2009; Puri 2000; De Wulf–Doyen–Markey–Raskin 2004/2008; Doyen 2007; Bouyer–Markey–Sankur robust reachability and RP 2013 survey; Lindemann–Rodionova–Pappas HSCC 2022; Dechter–Meiri–Pearl 1991; Wilson et al. 2014; Wendt–Coyle–Gallagher 1986; Kupferman–Lustig 2007; Gurfinkel–Chechik 2003; Mitchell et al. 2023 PERIL; Li/Cova/Dennison; Donzé–Ferrère–Maler 2013; CPM/PERT float; SIPP safety-buffer papers. Statements about these rest on search snippets or prior knowledge.
- Bendík et al. and the two extra Rodionova papers were read as abstracts only.
- Sources 3 and 8 were read through a summarising fetch tool, not as raw text; sources 1, 2, 6, 9 and 11 were read from extracted PDF text, and source 7 from rendered pages 1–3.
- No Google Scholar citation-forward search was done, so an obscure exact match (for example a thesis or transport-journal paper) cannot be excluded.