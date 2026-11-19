## Literature survey: algebraic path problems and semiring/dioid frameworks vs. the deadline-field algebra

`date -u` at start: Wed Nov 18 22:53:05 UTC 2026. At end: Wed Nov 18 23:00:59 UTC 2026 (about 8 minutes by the machine clock, well short of the 25-minute budget).

No project files were written. PDFs were read by running `pdftotext` on the copies WebFetch saved, with the text dumps going to `$TMPDIR`.

**Headline:** the shift-and-mask algebra with waiting is not new. Minoux 1976 treats it explicitly (in the forward direction) as his worked example, with a generalized Dijkstra theorem. I could not open Gondran–Minoux 2008 Chapter 4 itself, so I cannot quote its Section 4.4 heading. The (max, min, +offset) algebra is not named anywhere I read, but it is an instance of three published Dijkstra-validity conditions. A threshold-decomposition lemma exists for plain max-min matrices only.

---

### A. Sources opened and read (full text unless noted)

**1. Minoux 1976 (primary; the key source)**
- Citation: M. Minoux, "Structures algébriques généralisées des problèmes de cheminement dans les graphes: théorèmes, algorithmes et applications", RAIRO Recherche opérationnelle 10(V2), 1976, pp. 33–62.
- URL: https://www.numdam.org/item/RO_1976__10_2_33_0.pdf (landing page https://www.numdam.org/item/RO_1976__10_2_33_0/).
- Read: full text (French, OCR; some formulas garbled). I read Sections I, III, V and parts of VI.
- Result:
  - Path problems are posed over (S, ⊕) with arc labels in the set H of ⊕-endomorphisms of S (sum pointwise, product composition), because some problems "ne rentrent pas dans le cadre des formulations classiques" (Carré, Gondran).
  - Chapter III, "plus court chemin avec contraintes temporelles (P.C.C.T.)", after Halpern & Priess 1974: S is the set of finite unions of closed intervals of R+ ∪ {+∞}, and ⊕ is union.
  - Each arc has a travel time d_ij ≥ 0 and a set V_ij of allowed departure instants. Each node has a set W_i of instants "où le parking est autorisé".
  - The transition is h_ij(E) = d_ij T [(E ⊥ W_i) ∩ V_ij], where T is translation and ⊥ is "extension" of a collection by the waiting windows. It is proved to be an endomorphism; composition is non-commutative.
  - He notes that the product of two such endomorphisms "ne peut être assimilé à un triplet [τ, V, W]", so only images of a state are computed, not A* itself.
  - Existence of A* follows from K-stability (d_min > 0 and a finite horizon t_max; Theorem 4).
  - Chapter V, "Algorithme de Dijkstra généralisé" (A3), assumes a total preorder with (H1) ⊕ idempotent, (H2) a ≥ c and b ≥ c imply a ⊕ b ≥ c, (H3) h(a) ≥ a for all h. Theorem 6: adding (H4) b ≥ a ⇒ a ⊕ b = a gives termination in at most N iterations.
  - Explicit N.B.: for maximal states, reverse the preorder in (H2) and (H3).
  - He states that (A3) on P.C.C.T. itself does not in general converge in N iterations, because the preorder on interval sets (by earliest element) is not antisymmetric.
  - Section VI.1 covers time-dependent arc lengths (Cooke–Halsey, Dreyfus): h_ij nondecreasing is the endomorphism condition for (R ∪ {∞}, min), and Theorem 6 applies.
  - Section VI also lists, by substituting max/min for min/+, "chemin de capacité maximale et de longueur inférieure à une constante donnée" (time discretised).
- Relation to context:
  - This is the context's algebra in forward orientation: sets of time points, union, shift composed with mask, plus a waiting closure, with a fixed-point existence argument from positive delays and a finite horizon.
  - Differences: forward arrival sets from one origin rather than backward "can-still-reach" sets; real intervals rather than integer seconds; waiting as an operator ⊥ rather than a closed-form downward extension.
  - The max-orientation of Theorem 6 covers the permanent-closure collapse: f(x) = min(c−1, x−D) is a max-endomorphism with f(x) ≤ x on a total order with selective max.

**2. Bernardoni et al. 2023**
- Citation: W. Bernardoni, R. Cardona, J. Cleveland, J. Curry, R. Green, B. Heller, A. Hylton, T. Lam, R. Kassouf-Short, "Algebraic and Geometric Models for Space Networking", arXiv:2304.01150v2, Oct 2023.
- URL: https://arxiv.org/pdf/2304.01150
- Read: full text of Sections 1–2.5.
- Result:
  - A time-varying graph is a matrix over the powerset/"lifetime" semiring (P(R), ∪, ∩).
  - Theorem 2.16: Mat_n(P(R)) ≅ Fun(R, Mat_n(Bool)), i.e. a time-indexed family of Boolean graphs.
  - Definition 2.28, "Propagation Delay Semi-Ring" on L(R) × [0, ∞): (I,s) ⊗ (J,t) := (I ∩ (J − s), s + t) and (I,s) + (J,t) := (I ∪ J, max{s,t}). It embeds into End(L(R)) via the "intersect and shift" endomorphism φ(K) = {x + s | x ∈ I ∩ K}.
  - They state that "For this semi-ring Theorem 2.16 fails to hold" and that Carré's Kleene-star convergence result does not apply.
  - Definition 2.37, "Universal Contact Semi-Ring": maps f: R → 2^R with (f ⊙ g)(t) = ∪_{x ∈ f(t)} (g(x+t) + x). It models store-and-forward (waiting) via self-loops t ↦ [0, ∞).
  - Novelty claim: "we believe that the matrix TVG semi-ring, the propagation delay semi-ring, and the universal contact semi-ring are all new".
- Relation to context:
  - Their ⊗ is exactly the composition law of (delay d, open set O) path operators.
  - Their + is a lossy "worst-case" sum, not the exact operator union the context uses.
  - Their Theorem 2.16 is a per-time Boolean decomposition that they say breaks once delays are present.
  - Their novelty claim overlooks Minoux's 1976 P.C.C.T. algebra (they cite [Min76] only for generalized Ford/Moore/Dijkstra).

**3. Baras & Theodorakopoulos 2010**
- Citation: J. S. Baras, G. Theodorakopoulos, "Path Problems in Networks", Synthesis Lectures on Communication Networks, Morgan & Claypool, 2010.
- URL: https://terpconnect.umd.edu/~baras/publications/Books/S00245ED1V01Y201001CNT003.pdf
- Read: full text; Sections 2.2.4, 3.3.2, 4.7 and the non-semiring chapter headings.
- Result:
  - Section 2.2.4, "Semirings of Endomorphisms": (H, +, composition) is a semiring, and a dioid if S is. Since A* consists of functions, "the algorithms for computing A* will be used to compute the image of a single element".
  - Section 3.3.2, "Generalization of Dijkstra": "The semiring has to be a selective dioid where 1 is the largest element".
  - Section 4.7, "Shortest path with time-inhomogeneous edges": nondecreasing arrival-time functions w_ij as endomorphisms of (R ∪ {∞}, min), for earliest arrival.
  - Section 4 lists widest path (max, min) and widest-shortest path.
- Relation to context: a textbook statement of the endomorphism framework and the Dijkstra condition. It treats only the scalar earliest-arrival (FIFO) case, not set-valued labels or forbidden waiting.

**4. Sobrinho 2005**
- Citation: J. L. Sobrinho, "An Algebraic Theory of Dynamic Network Routing", IEEE/ACM Trans. Networking 13(5), Oct 2005, pp. 1160–1173.
- URL: https://www.di.ens.fr/~busic/mar/projets/sob05.pdf
- Read: full text (formulas partly lost in extraction).
- Result:
  - Routing algebra of labels, signatures, weights, and a total order.
  - Monotonicity (weight does not improve when prefixed by a link) implies path-vector convergence in every network (Theorem 3).
  - Isotonicity (order between two paths preserved under a common prefix link) implies the converged local-optimal in-tree is optimal (Theorem 5), with a converse.
  - The widest-path algebra is "both monotone and isotone"; the IGRP composite metric is monotone but not isotone.
- Relation to context: the scalar algebra's edge map x ↦ min(c−1, x−D) is isotone (nondecreasing) and monotone (f(x) ≤ x, in fact strictly below x on finite labels since D ≥ 1). It falls in the class where local optimality equals global optimality. The exact algebra is not named.

**5. Sobrinho & Griffin 2010**
- Citation: J. L. Sobrinho, T. G. Griffin, "Routing in Equilibrium", MTNS 2010.
- URL: https://www.cl.cam.ac.uk/teaching/1415/L11/routing_in_equilibrium_mtns_2010.pdf
- Read: full text.
- Result:
  - Left- or right-distributivity of ⊗ over ⊕ is equivalent to isotonicity for the natural order.
  - For selective semirings, Dijkstra computes A* when every arc weight is ≤ 1 in the natural order (citing Gondran–Minoux).
  - For non-distributive "prebimonoids", Theorem 4.1: "If the network is left-absorptive, then Algorithm 1 [generalized Dijkstra] computes the t-th column of a left-local solution".
  - It discusses the lexicographic product "bw ×~ sp" of bandwidth and shortest path as an example where distributivity fails. The paper's naming of which product is distributive is the reverse of the usual shortest-widest/widest-shortest convention as I read it, so check the original before quoting.
- Relation to context: gives the precise split of roles. Absorption (inflationarity) is what makes Dijkstra's label-setting find a fixed point; isotonicity/distributivity is what makes that fixed point the global optimum. The context's scalar algebra has both.

**6. Griffin & Sobrinho 2005**
- Citation: T. G. Griffin, J. L. Sobrinho, "Metarouting", SIGCOMM 2005.
- URL: https://mae.engr.ucdavis.edu/dsouza/metarouting.pdf
- Read: full text; Sections 1–3 skimmed.
- Result: vectoring is correct under strict monotonicity (SM). "It is possible to generalize link state flooding and Dijkstra's algorithm to an arbitrary algebraic context", but that needs associativity and isotonicity (I) plus left and right SM. The lexical product preserves monotonicity properties under stated conditions.
- Relation to context: confirms the standard "isotone + monotone ⇒ generalized Dijkstra" condition.

**7. Dynerowicz & Griffin 2013**
- Citation: S. Dynerowicz, T. G. Griffin, "On the Forwarding Paths Produced by Internet Routing Algorithms", ICNP 2013.
- URL: https://www.cl.cam.ac.uk/~tgg22/publications/dynerowicz_griffin_icnp_2013.pdf
- Read: abstract and theorem statements only.
- Result: for widest-shortest paths, Bellman–Ford and Dijkstra may compute different path sets. Theorem 1: a lexicographic product of semirings is distributive iff its components are distributive and a cancellativity/constancy condition holds.
- Relation to context: a caution for any lexicographic tie-break added on top of the deadline label, such as "latest deadline, then fewest hops".

**8. Mohri 2002**
- Citation: M. Mohri, "Semiring Frameworks and Algorithms for Shortest-Distance Problems", J. Automata, Languages and Combinatorics 7(3), 2002, pp. 321–350.
- URL: https://cs.nyu.edu/~mohri/pub/jalc.pdf
- Read: full text; Sections 1–4.
- Result: a generic single-source queue-based relaxation algorithm is correct for semirings that are "k-closed for G" (Theorem 1). It does not need idempotence; it is stated for commutative semirings with a remark that it extends to the non-commutative case; and it works with any queue discipline. Bounded (0-closed) semirings are idempotent.
- Relation to context: the worklist/Bellman–Ford side of the framework. The context's operator algebra is idempotent and non-commutative, and closedness comes from the finite horizon H with D ≥ 1, as in Minoux's K-stability, not from 0-closedness.

**9. Rote 1990**
- Citation: G. Rote, "Path problems in graphs", Computing Supplementum 7 (1990), pp. 155–189.
- URLs: https://page.mi.fu-berlin.de/rote/Papers/pdf/Path+problems+in+graphs.pdf and the abstract page https://page.mi.fu-berlin.de/rote/Papers/abstract/Path+problems+in+graphs.html
- Read: full text; Sections 5.4 and 6.4 closely.
- Result: a survey of the algebraic path problem with elimination and iterative algorithms. Section 5.4: Dijkstra "can be generalized to semirings which come from a linearly ordered semigroup in which 1 is the largest element". Section 6.4 lists maximum capacity paths over (R+ ∪ {∞}, max, min) and Boolean reachability as the two-element (max, min) semiring.
- Relation to context: standard background. No time-dependent or endomorphism material and no (max, min, +) hybrid.

**10. Ramalingam & Reps 1996 (used as the source for Knuth's definitions)**
- Citation: G. Ramalingam, T. Reps, "An Incremental Algorithm for a Generalization of the Shortest-Path Problem", J. Algorithms 21 (1996).
- URLs: https://research.cs.wisc.edu/wpis/papers/jalg96.pdf (abstract page https://research.cs.wisc.edu/wpis/abstracts/jalg96.abs.html)
- Read: full text; Sections 1–2.
- Result:
  - Restates Knuth's grammar problem and definition: g is a superior function "if it is monotone non-decreasing in each variable and if g(x1,…,xk) ≥ max(x1,…,xk)". Listed examples are max(x1,…,xk) and x + y.
  - Extends Dijkstra/Knuth to weakly superior functions: g(…xi…) < xi ⇒ g(…xi…) = g(…∞…). Here min(x1,…,xk) is weakly superior but not superior.
  - Gives an incremental algorithm for arbitrary mixes of insertions, deletions and cost changes.
- Relation to context: in the order-reversed (min) orientation, the scalar recurrence is ℓ_s = min(−a_s, min_j max(1−c_j, ℓ_j + D_j)). Each production function max(const, x + D) with D ≥ 0 is a composition of the listed superior functions, so the scalar deadline field is an SF grammar problem solvable by Knuth's algorithm. The incremental algorithm is relevant to re-solving when closure times change.

**11. Ramusat, Maniu, Senellart 2021**
- Citation: Y. Ramusat, S. Maniu, P. Senellart, "A Practical Dynamic Programming Approach to Datalog Provenance Computation", arXiv:2112.01132.
- URL: https://arxiv.org/pdf/2112.01132
- Read: Sections 1–4.
- Result: Knuth's algorithm corresponds to best-first search in "a monotonic superior hypergraph". Lemma 2: an idempotent semiring is superior for its natural order iff it is 0-closed. Their Theorem 14 gives a Knuth/Dijkstra algorithm for 0-closed totally ordered semirings.
- Relation to context: secondary confirmation of the Knuth conditions and their semiring reading.

**12. Myšková & Plavka 2021 (source for the threshold-decomposition lemma)**
- Citation: H. Myšková, J. Plavka, "Strong X-robustness of interval max-min matrices", Kybernetika 57(4), 2021, pp. 594–612.
- URL: https://www.kybernetika.cz/content/2021/4/594/paper.pdf
- Read: Section 2.
- Result:
  - Defines the threshold digraph G(A, h) (arcs with a_ij ≥ h) and threshold matrices A^(h).
  - Lemma 2.1 (Molnárová et al.): G(A, h2) ⊆ G(A, h1) for h1 < h2.
  - Lemma 2.2 (attributed to Semančíková, "Orbits in max-min algebra", Linear Algebra Appl. 414, 2006): "A = ⊕_{h∈H} (h ⊗ A^(h))" and "(A ⊗ B)^(h) = A^(h) ⊗ B^(h) for any h".
- Relation to context: a published threshold-decomposition statement for the max-min (bottleneck/fuzzy) algebra. Thresholding is a homomorphism onto Boolean matrices, so a max-min matrix problem is a nested family of Boolean ones.

**13. Batz, Geisberger, Sanders 2008**
- Citation: G. V. Batz, R. Geisberger, P. Sanders, "Time Dependent Contraction Hierarchies — Basic Algorithmic Ideas", arXiv:0804.3947.
- URL: https://ar5iv.labs.arxiv.org/html/0804.3947
- Read: HTML full text through WebFetch's summarizer, not raw.
- Result: algorithms "view travel-time functions (TTFs) as an abstract data type" with evaluation, chaining and minimum. They assume FIFO, piecewise-linear TTFs. Chaining and min are linear in the number of segments. There is no algebra or semiring language.
- Relation to context: the engineering counterpart of the endomorphism dioid (min, ∘) on piecewise-linear functions, and the closest analogue for the μ-parametric variant (piecewise-linear labels under pointwise max/min and shifts).

**14. Baccelli, Cohen, Olsder, Quadrat 1992**
- Citation: F. Baccelli, G. Cohen, G. J. Olsder, J.-P. Quadrat, "Synchronization and Linearity: An Algebra for Discrete Event Systems", Wiley 1992 (web edition).
- URL: https://www.rocq.inria.fr/metalau/cohen/documents/BCOQ-book.pdf
- Read: opened full text, but only grepped the table of contents and Section 9.6.
- Result: I confirmed that Section 9.6 "Min-Max Systems" exists, including 9.6.4 "Stochastic Min-Max Systems", and that distributivity of ⊕ over ∧ is used there. I did not read enough to state its theorems.
- Relation to context: background for (max, min, +) recurrences. It concerns cycle times and eigenproblems, not single-destination fixed points.

**15. Gurney & Griffin 2011**
- Citation: A. J. T. Gurney, T. G. Griffin, "Pathfinding through Congruences", RAMiCS 2011.
- URL: https://www.cl.cam.ac.uk/~tgg22/publications/ramics2011.pdf
- Read: abstract and introduction only.
- Result: congruences and quotients of path algebras relate properties of an algebra to its quotient, even with weakened semiring axioms.
- Relation to context: the natural language for "prefix sets [0, L] collapse the set algebra to a scalar algebra" (a sub-algebra or quotient argument). I found no such collapse stated for time-set algebras.

**16. Gondran & Minoux 2008 (front matter only)**
- Citation: M. Gondran, M. Minoux, "Graphs, Dioids and Semirings: New Models and Algorithms", Springer 2008.
- URLs: preface PDF https://beckassets.blob.core.windows.net/product/preamble/111413/9780387754499_intro_001.pdf and the Springer Chapter 4 landing page https://link.springer.com/chapter/10.1007/978-0-387-75450-5_4
- Read: preface in full; the Chapter 4 landing page (title and opening paragraphs only).
- Result:
  - The preface lists among its contributions extensions of classical shortest-path algorithms "to a whole class of nonclassical path-finding problems (such as: shortest paths with time constraints, shortest paths with time-dependent lengths on the arcs, etc.), cf. Chap. 4, Sect. 4.4".
  - Chapter 4 is titled "Solving Linear Systems in Dioids".
- Relation to context: confirms the book covers the topic at Chapter 4, Section 4.4. I could not read that section itself.

Also read, less central:
- R. E. Tarjan, "A Unified Approach to Path Problems", JACM 28(3), 1981, pp. 577–593. URL: https://collaborate.princeton.edu/en/publications/a-unified-approach-to-path-problems/. Abstract only. Path expressions (regular expressions over path sets) are built by elimination and then reinterpreted; "the problem of constructing path expressions is in some sense the most general path problem". Relation: the deadline field is one reinterpretation of union, concatenation and star, with star being the waiting closure.
- D. Lehmann, "Algebraic structures for transitive closure", Warwick Theory of Computation Report 10, 1976 (journal version TCS 4, 1977, pp. 59–76). URL: https://wrap.warwick.ac.uk/id/eprint/46308. Repository abstract only; the PDF returned 403. It defines closed semirings and "Dijkstra semirings", for which a generalized Dijkstra algorithm computes rows of the closure.
- M. Haouari, P. Dejax, "Plus court chemin avec dépendance horaire: résolution et application aux problèmes de tournées", RAIRO RO 31(2), 1997, pp. 117–131. URL: https://www.numdam.org/item/RO_1997__31_2_117_0.pdf. Abstract only. Shortest path with time windows plus time-varying cost and duration, inside column generation; operations-research, not algebraic.

---

### B. Could not open (what I relied on instead)

- **Gondran & Minoux 2008, Chapter 4 Section 4.4 body text.** The nzdr.ru PDF returned 404, the Scribd copy was truncated, and Springer is paywalled. I relied on the preface (opened), Minoux 1976 (the primary source, opened), and Baras–Theodorakopoulos's and Sobrinho–Griffin's citations of the book. I therefore cannot quote the exact Section 4.4 subsection headings.
- **Knuth 1977**, "A generalization of Dijkstra's algorithm", Information Processing Letters 6(1), pp. 1–5. ScienceDirect returned 403. Definitions are taken from Ramalingam–Reps and Ramusat et al.
- **Sobrinho 2002**, "Algebra and algorithms for QoS path computation and hop-by-hop routing in the Internet", IEEE/ACM ToN 10(4), pp. 541–550. IEEE returned 418. Search-result abstract only: isotonicity is necessary and sufficient for a generalized Dijkstra algorithm to yield optimal paths.
- **Halpern & Priess 1974**, "Shortest path with time constraints on movement and parking", Networks 4(3), pp. 241–253. Search-result description plus Minoux's restatement.
- **Lengauer & Theune 1991**, "Unstructured path problems and the making of semirings" (WADS'91, LNCS 519) and "Efficient algorithms for path problems with general cost criteria" (ICALP'91, LNCS 510, pp. 314–326). Springer paywalled, Fraunhofer blocked. Bibliographic data only, plus Baras–Theodorakopoulos's remark that "there are methods [32] for transforming certain non-semiring costs to semirings".
- **Gunawardena 1994**, "Min-max functions", Discrete Event Dynamic Systems 4(4), pp. 377–406. Not found in openable form; search metadata only.
- **Carré 1971** (J. Inst. Maths Applics 7, pp. 273–294) and **Backhouse & Carré 1975** (J. Inst. Maths Applics 15, p. 161). Search-result abstracts only. Backhouse's thesis PDF opened but is an image scan with no extractable text.
- **Wendt, Coyle, Gallagher 1986**, "Stack filters", IEEE Trans. ASSP 34(4), pp. 898–911. Search-result abstract only (threshold decomposition and stacking properties).
- **Semančíková 2006** and **Cechlárová 1996** (powers of max-min matrices). Known only through Myšková–Plavka's citations and a search abstract.
- **Zadeh 1971**, "Similarity relations and fuzzy orderings". Bibliographic data only; nothing on α-cuts retrieved.
- **Dolan 2013**, "Fun with semirings". Both URLs failed (403, 404); bibliographic data only.
- **Not attempted:** Zimmermann 1981, Pouly & Kohlas, Tarjan's "Fast algorithms" companion paper, Batz et al. 2013 (JEA), and Kleene algebra with tests.

---

### C. Answers to the three specific questions

**(1) Is the shift-and-mask algebra on time-point sets explicitly treated? Yes, in forward orientation.**
- Minoux 1976, Chapter III, "plus court chemin avec contraintes temporelles (P.C.C.T.)", is precisely this: S = finite unions of closed intervals, ⊕ = union, transition h_ij(E) = d_ij T [(E ⊥ W_i) ∩ V_ij], non-commutative composition, and existence of A* via K-stability from d_min > 0 and a bounded horizon.
- Forbidden or restricted waiting is built in through the parking sets W_i, following Halpern–Priess. From the identity triple (τ = 0, V = everything, W = ∅), W = ∅ appears to be the no-waiting case; I did not check the garbled definition of ⊥ to confirm this.
- Gondran–Minoux 2008's preface confirms the book version is at "Chap. 4, Sect. 4.4" ("shortest paths with time constraints, shortest paths with time-dependent lengths on the arcs"). I could not open that section to quote its heading.
- Bernardoni et al. 2023 give the no-waiting composition law in closed form, (I,s) ⊗ (J,t) = (I ∩ (J − s), s + t), with the "intersect and shift" embedding into End(L(R)).
- What I did not find anywhere:
  - the backward (latest-departure, "still reachable") orientation as an algebraic object;
  - the exact set-valued least fixed point over integer seconds with reopenings;
  - the closed-form waiting star;
  - the statement that prefix-closed sets collapse the algebra to a scalar one.
- Minoux explicitly declines to compute A* in closed form and notes that label-setting does not finish in N iterations on the set-valued problem.

**(2) Is the (max, min, +offset) algebra and Dijkstra's validity for it stated? Not by name; it is an instance of published conditions.**
- I found no source that names "bottleneck with additive offsets" or writes L_s = max(a_s, max_j min(c_j − 1, L_j − D_j)).
- Minoux 1976, Theorem 6 with the reversed-order N.B., covers it: x ↦ min(c−1, x−D) is a max-endomorphism, satisfies h(a) ≤ a, on a total order with selective ⊕. Label-setting terminates in at most N iterations.
- Knuth's superior functions cover it in the min orientation: max(1−c, x+D) is monotone and ≥ x, built from max and +, both of which Ramalingam–Reps list as superior functions.
- Sobrinho's conditions cover it: the edge maps are isotone and monotone; widest path is "both monotone and isotone". Sobrinho–Griffin Theorem 4.1 gives the Dijkstra result under absorption.
- The semiring-only statements (Rote Section 5.4; Baras–Theodorakopoulos Section 3.3.2; Lehmann's Dijkstra semirings) do not directly apply. The edge action is an endomorphism, not multiplication by an element of a (max, ⊗) semiring, so the endomorphism or routing-algebra formulation is the right citation.
- The nearest explicitly listed neighbour is Minoux's "chemin de capacité maximale et de longueur inférieure à une constante donnée", which is handled by time-expanded state, not as a scalar algebra.

**(3) Is there a threshold-decomposition or parametric-lifting theorem for path problems? Only for the plain max-min algebra, at matrix level.**
- Semančíková's lemma, as quoted in Myšková–Plavka 2021 Lemma 2.2: A = ⊕_h (h ⊗ A^(h)) and (A ⊗ B)^(h) = A^(h) ⊗ B^(h), with nested threshold digraphs G(A, h) (Lemma 2.1).
- That it extends to powers and the Kleene star, so that a bottleneck closure is a monotone family of Boolean closures, is my inference from the lemma. I did not see it stated as a path-problem theorem in a source I opened.
- Rote notes only that Boolean reachability is the two-element (max, min) semiring.
- Bernardoni et al. Theorem 2.16 is a time-indexed Boolean decomposition for zero-delay time-varying graphs. They state it fails once delays are present.
- I found no published lifting theorem for thresholds interacting with additive time offsets (a monotone family of Boolean time-expanded reachability problems solved as one (max, min, +) problem), nor one for the μ-parametric piecewise-linear variant.
- A search snippet (not opened) mentions Camerini's threshold approach and binary search over capacity thresholds with Boolean matrix products for bottleneck paths. That is algorithmic use of the same idea, unverified.
- The stack-filter threshold decomposition (Wendt et al.) was confirmed only at abstract level and concerns signals, not path problems.