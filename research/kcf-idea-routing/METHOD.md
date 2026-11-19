# The one-pass margin field

Stage 3 of `research/kcf-idea-routing`. Code: `margin_field/pl.py`, `margin_field/field.py`. The existing code in
`research/harness-2026-11/F-3.1/deadline_field` is used read-only and is not changed. Model and notation are those
of `research/kcf-theorem/THEOREM.md` §1 ("THEOREM" below).

## 0. Result in five lines

* **What it returns.** For every edge state s and second t, the number μ_s(t): the largest safety margin m (in
  seconds) such that t is still in the deadline field when **every closure is widened by m seconds on both sides**
  (the road closes m seconds earlier and reopens m seconds later). One pass returns this for all margins 0..M.
* **Exactness (Theorem 1).** {t : μ_s(t) ≥ m} is exactly the F-3.1 field of the m-widened instance, for every m.
* **Meaning (Theorem 2).** μ_o(t) ≥ m iff departure t has one route that stays valid whenever every closure boundary
  is wrong by at most m seconds. It cannot be read off the windows (Proposition 3).
* **Stability (Theorem 6, round 2).** μ is 1-Lipschitz in the closure times, and μ_o(t) + 1 is exactly the distance
  from the forecast to the nearest forecast under which leaving at t fails.
* **Algorithm (Theorems 4, 5).** Every function involved is piecewise linear in t with slopes −1, 0, +1. One
  heap-ordered backward pass over such functions computes μ. Its cost is stated in pieces, not in M.

What is and is not new is in §6. In short: Theorem 1 is an instance of a published general theorem; the algorithm and
its exactness for this model were not found in the literature.

## 1. The margin family

Fix an instance I = (graph, D, forbidden turns, waitable nodes, H, B, W, A, IB, AN) as in THEOREM §1, and a largest
margin M ≥ 0. For a set X ⊆ ℤ and m ≥ 0 write

  X ⊕ m = {t : |t − x| ≤ m for some x ∈ X}  (widening),  X ⊖ m = {t : [t − m, t + m] ⊆ X}  (narrowing).

**The m-widened instance I(m)** has the same graph, D, turns, waitable nodes and H, and

  B_j(m) = B_j ⊕ m, W_v(m) = W_v ⊕ m, IB_o(m) = IB_o ⊕ m.

Acceptance has two variants, chosen by the caller (`erode_accept`):
* **keep**: A_j(m) = A_j, AN_o(m) = AN_o (shelter windows are not uncertain);
* **erode**: A_j(m) = A_j ⊖ m, AN_o(m) = AN_o ⊖ m (also the m seconds next to each end of an acceptance interval are
  dropped).

I(0) = I. In code: `field.widen(inst, m, erode_accept=...)`.

**Level functions.** For t ∈ ℤ define, with max ∅ = −1 ("bottom"):

  β_j(t) = max{m ∈ {0..M} : t ∉ B_j(m)} = min(M, dist(t, B_j) − 1),

where dist(t, X) = min_{x ∈ X} |t − x| (∞ if X = ∅). So β_j(t) = −1 iff t ∈ B_j. In the same way ω_v from W_v, ι_o
from IB_o, and for acceptance α_j(t) = max{m ≤ M : t ∈ A_j(m)}: in the keep variant α_j = M on A_j and −1 elsewhere;
in the erode variant α_j(t) = min(M, dist(t, ℤ \ A_j) − 1). β_j is restricted to t ∈ [0, H − D_j] and ω_v to
[0, H − 1] (a move must end by H); outside they are −1.

**(L)** For every m ∈ {0..M}: t ∉ B_j(m) ⟺ β_j(t) ≥ m, and likewise for ω, ι, α. *Proof.* The sets B_j(m) grow with
m, so {m : t ∉ B_j(m)} is an initial segment of {0..M}; its maximum is β_j(t). ∎

**The margin field.** With R\*_s(m), G\*_s(m), Feas(o; m) the truth sets of THEOREM §1 for I(m):

  μ\*_s(t) = max{m ∈ {0..M} : t ∈ R\*_s(m)},  γ\*_s(t) = max{m : t ∈ G\*_s(m)},  μ\*_o(t) = max{m : t ∈ Feas(o; m)},

each −1 if the set is empty (in particular for t ∉ T).

## 2. Theorem 1: threshold decomposition

**Lemma 2.1 (nested).** If m ≤ m′ then R\*_s(m′) ⊆ R\*_s(m), G\*_s(m′) ⊆ G\*_s(m), Feas(o; m′) ⊆ Feas(o; m).
Hence t ∈ R\*_s(m) ⟺ μ\*_s(t) ≥ m for all m ∈ {0..M}, and likewise for γ\* and μ\*_o.

*Proof.* A journey is valid iff its edge starts avoid B, its wait seconds avoid W, its departure avoids IB, its turns
are allowed, its moves end by H, and its final arrival is in A (THEOREM §1). I(m′) has larger B, W, IB and smaller A
than I(m), and everything else is equal. So a journey valid in I(m′) is valid in I(m). The set of m with
t ∈ R\*_s(m) is therefore an initial segment, and its maximum is μ\*_s(t). ∎

**Theorem 1.** (a) μ\* is the unique family of functions μ_s : ℤ → {−1, 0, …, M}, equal to −1 outside T, with

  μ_s(t) = max( max_{j : tail(j) = head(s), (s, j) ∉ F} min(β_j(t), γ_j(t + D_j)),
         [head(s) ∈ Wt] min(ω_head(s)(t), μ_s(t + 1)) ),  γ_j = max(α_j, μ_j).  (E_μ)

(b) For every m ∈ {0..M} and every edge state s: {t : μ\*_s(t) ≥ m} = R\*_s(m) and {t : γ\*_s(t) ≥ m} = G\*_s(m).
These are the sets the existing `backward` returns on I(m) (THEOREM, Theorem 1).

(c) For an origin o: μ\*_o = min(ι_o, max(α^N_o, c_o)), where c_o is the waiting closure (§3.3) of
X_o(t) = max_{j out of o} min(β_j(t), γ\*_j(t + D_j)) if o is waitable, and c_o = X_o otherwise; α^N_o is the level
function of AN_o. And {t : μ\*_o(t) ≥ m} = Feas(o; m) = `issue_set` on I(m).

*Proof.* (b) is Lemma 2.1. For (a), fix s, t ∈ T and m ∈ {0..M}. THEOREM Lemma 1.1 applied to I(m) says
G\*_j(m) = A_j(m) ∪ R\*_j(m) and

  t ∈ R\*_s(m) ⟺ (∃ allowed j: t ∉ B_j(m) and t + D_j ∈ G\*_j(m)) or (head(s) ∈ Wt, t ∉ W(m), t + 1 ∈ R\*_s(m)).

By (L) and Lemma 2.1 the right side reads: (∃ j: β_j(t) ≥ m and γ\*_j(t + D_j) ≥ m) or (ω(t) ≥ m and
μ\*_s(t + 1) ≥ m). Since min(x, y) ≥ m iff both are, and a maximum is ≥ m iff one term is, this is exactly
"the right side of (E_μ), evaluated on μ\*, is ≥ m at t". The left side is "μ\*_s(t) ≥ m". Two numbers in
{−1..M} that pass the same thresholds m = 0..M are equal. The same argument gives γ\* = max(α, μ\*). So μ\* solves
(E_μ). *Uniqueness:* the right side of (E_μ) at t uses only values at t + D_j > t and t + 1 > t (C1). Two solutions
agree for t > H (both −1), hence, by induction downwards on t, everywhere.

(c) is the same argument applied to the origin read-off in the proof of THEOREM Theorem 1: the first-move set is the
union over out-edges, closed under waiting at o when o is waitable; AN_o is added without waiting closure; IB_o is
removed. Each step is a union (max), an intersection with a complement of a closure (min with a level function) or
the waiting closure, whose threshold form is Lemma 3.3(a). ∎

## 3. Theorem 2 and Proposition 3: what the number means

**Perturbation class.** 𝒫(m) is the set of instances I′ with the same graph, D, turns, waitable nodes and H as I and
B′_j ⊆ B_j(m), W′_v ⊆ W_v(m), IB′_o ⊆ IB_o(m), A′_j ⊇ A_j(m), AN′_o ⊇ AN_o(m). It contains every instance obtained
from I by moving each start and each end of each closure interval by at most m seconds (and, in the erode variant,
each end of each acceptance interval), or by deleting closures.

**Theorem 2.** For an origin o, a second t and m ∈ {0..M} the following are equivalent:
1. μ\*_o(t) ≥ m;
2. there is **one** journey from o departing at t that is valid in every I′ ∈ 𝒫(m);
3. for every I′ ∈ 𝒫(m) there is **some** journey from o departing at t valid in I′.

*Proof.* (1 ⟹ 2) By Theorem 1(c) there is a journey valid in I(m). Validity only asks that certain seconds are
outside the closure sets and one second is inside an acceptance set; I′ has smaller closure sets and larger
acceptance sets than I(m). (2 ⟹ 3) is trivial. (3 ⟹ 1) I(m) itself is in 𝒫(m). ∎

So the robust reading (one route for all errors) and the adaptive reading (a route for each error) coincide, because
I(m) is the worst member of 𝒫(m) in every component at once. This would fail for an additive quantity such as a dose
summed along the route with member-dependent doses (`SURVEY.md` §5).

**Proposition 3 (the margin is not the distance to the edge of the window).** In the erode variant, if
μ\*_o(t) ≥ m then every t′ ≥ 0 with |t′ − t| ≤ m is a feasible departure of I, with the same route shifted by t′ − t.
So μ\*_o(t) ≤ min(M, d − 1), where d is the distance from t to the nearest infeasible second of I at or above 0. The
inequality can be strict by any amount.

*Proof.* Take the journey valid in I(m) and start every move t′ − t seconds later (or earlier). Each edge start u
moves to u′ with |u′ − u| ≤ m, and u ∉ B_j ⊕ m gives u′ ∉ B_j; the same for waits and the departure. The final
arrival a ∈ A_j ⊖ m gives a′ ∈ A_j ⊆ T, so every move still ends by H; starts stay ≥ t′ ≥ 0. Turns are unchanged.
*Strictness:* two parallel edges 0 → 1, D = 1, H = 12, A = [0, 12]; edge 1 has B = [6, ∞), edge 2 has B = [0, 5].
Feas(0) = [0, 11]: one unbroken window. The nearest infeasible second to 5 is 12, so the bound gives 6. But at margin
m ≥ 1 edge 1 is open only up to 5 − m and edge 2 only from 6 + m, so μ\*_0(5) = 0. ∎
(`tests/test_margin_field.py::test_two_route_example`.)

This is why a wide window is not evidence of a safe leave-by time: the window can be the union of two routes' windows
that meet where one road closes and another opens.

### 3.1 Theorem 6: the margin is a stability radius (added in round 2)

**Distance between forecasts.** Let I and I′ have the same graph, D, turns, waitable nodes and H. Write
I′ ≼_δ I ("I′ is within δ of I, from above") if B′_j ⊆ B_j ⊕ δ, W′_v ⊆ W_v ⊕ δ, IB′_o ⊆ IB_o ⊕ δ, and A′_j ⊇ A_j,
AN′_o ⊇ AN_o (erode variant: A′_j ⊇ A_j ⊖ δ, AN′_o ⊇ AN_o ⊖ δ). Let d(I → I′) be the least such δ (∞ if none) and
d(I, I′) = max(d(I → I′), d(I′ → I)). For the closure sets this is the Hausdorff distance, edge by edge. Moving each
start and each end of each closure interval by at most δ seconds, without making an interval vanish, gives
d(I, I′) ≤ δ; deleting closures as well gives d(I → I′) ≤ δ.

**Theorem 6.** Let μ and μ′ be the margin functions of I and I′ with the same cap M. For every origin o (and every
edge state) and every second t:
1. *(one-sided)* if d(I → I′) ≤ δ then μ′(t) ≥ μ(t) − δ;
2. *(1-Lipschitz)* if d(I, I′) ≤ δ then |μ′(t) − μ(t)| ≤ δ;
3. *(radius)* if μ_o(t) = m < M then min{ d(I → I′) : t is not a feasible departure of o in I′ } = m + 1; if
   μ_o(t) = M the minimum is at least M + 1.

*Proof.* (1) If μ(t) < δ then μ(t) − δ ≤ −1 ≤ μ′(t). Otherwise let m = μ(t) − δ ≥ 0. On the integers
(X ⊕ a) ⊕ b = X ⊕ (a + b), so B′_j ⊕ m ⊆ (B_j ⊕ δ) ⊕ m = B_j ⊕ (m + δ), the same for W and IB, and in the erode
variant A′_j ⊖ m ⊇ (A_j ⊖ δ) ⊖ m = A_j ⊖ (m + δ). So every closure set of I′(m) is inside the corresponding set of
I(m + δ) and every acceptance set contains it. By Theorem 1(c) t is feasible in I(m + δ); validity of a journey only
asks that certain seconds avoid closure sets and one second lies in an acceptance set (as in the proof of Theorem 2),
so the same journey is valid in I′(m), and μ′(t) ≥ m by Theorem 1(c) for I′. (2) is (1) both ways.
(3) If d(I → I′) ≤ m then (1) with δ = m gives μ′_o(t) ≥ 0, so t is feasible in I′: the minimum is at least m + 1
(for m = −1 this is empty). For m < M, I(m + 1) satisfies I(m + 1) ≼_{m+1} I and t is infeasible in it by
Theorem 1(c): the minimum is at most m + 1. ∎

**Reading.** μ_o(t) + 1 is the distance, in seconds of closure timing, from the forecast to the nearest forecast under
which leaving at t fails. Operationally: *a leave-by time issued with margin ≥ δ stays valid after any forecast
revision that moves closure times by at most δ and adds no closure farther than δ from an old one; no recomputation
is needed to know this.* A revision's δ is computed from the two closure tables alone. The definition of robustness
as distance to the violating set is that of Fainekos and Pappas (2009) for temporal logic over signals, and
"stability radius" is the classical name in combinatorial optimisation (Leont'ev, Sotskov, Gordeev 1995); what is
specific here is that the radius is exact, is in closure time, and comes out of one pass for every place and second.
Checked on the random graphs: 838,729 (origin, second) pairs against a forecast with every closure end moved by up to
δ, no violation; the bound was attained with equality at 2,095 of them (`results/property_tests.json`, `thm6_*`).

## 4. The algorithm

### 4.1 Tent functions

**Definition.** 𝒯 is the set of functions f : ℤ → {−1} ∪ ℕ with finite support {f ≥ 0} that are given by finitely
many pieces (lo, hi, v, σ): f(t) = v + σ(t − lo) on the integer interval [lo, hi], σ ∈ {−1, 0, +1}, all values ≥ 0,
pieces disjoint. |f| is the number of pieces in the greedy-maximal form (`pl.canon`).

**Lemma 4.1 (closure).** If f, g ∈ 𝒯 then so are t ↦ f(t + d) (shift), the restriction of f to an interval, min(f, g)
and max(f, g), and they are computed in O(|f| + |g|) time by one merge of the two piece lists.

*Proof.* Shift and restriction are immediate. On an integer interval where both are linear, f − g is linear with slope
in {−2, …, 2}, so it changes sign at most once; the interval splits at an integer into at most two parts on each of
which min (and max) is one of the two pieces. The split point is ⌊−d₀/δ⌋ past the left end, d₀ the difference at the
left end and δ its slope (`pl.pmin`, `pl.raise_to`). The crossing of a +1 and a −1 line can fall on a half-integer;
on the grid the two integer neighbours are each on one piece, so nothing is lost. The merge visits each piece
once. ∎

**Lemma 4.2 (level functions are tents).** β_j, ω_v, ι_o and α_j are in 𝒯, with at most 3 pieces per gap between
consecutive closure intervals (rise, flat at M, fall).

*Proof.* Between two consecutive closure intervals with last second ℓ and first second r,
min(M, dist(t, B) − 1) = min(M, t − ℓ − 1, r − t − 1). Before the first or after the last interval one of the terms
is absent. ∎ (`pl.tent`.)

### 4.2 The waiting closure

For μ, ω ∈ 𝒯 let cl_ω(μ) be the least function c with c ≥ μ and c(t) ≥ min(ω(t), c(t + 1)) for all t.

**Lemma 4.3.** (a) cl_ω(μ)(t) = max_{u ≥ t} min( μ(u), min_{t ≤ x < u} ω(x) ) (the inner minimum is +∞ for u = t).
Its level set at m is the downward waiting closure of {μ ≥ m} under the wait mask {ω < m}, i.e. `_wait_close` of the
existing code applied to I(m).

(b) Let ω be linear on [x, y] (one piece) and c = cl_ω(μ). Then for t ∈ [x, y]

  c(t) = max( μ(t), min( ω(t), max( Q(t + 1), min(c(y + 1), ω(y)) ) ) ),  Q(t + 1) = max_{t < u ≤ y} min(μ(u), ω(u − 1)),

with Q(y + 1) = −1. Outside the support of ω, c = μ.

(c) cl_ω(μ) ∈ 𝒯, and it is computed by processing the pieces of ω from right to left with the operations of Lemma
4.1 and one suffix maximum per piece.

*Proof.* (a) Call the right side r. r ≥ μ (take u = t). r(t) ≥ min(ω(t), r(t + 1)), because every term of r(t + 1)
with index u, cut by ω(t), is the term of r(t) with the same u. If c ≥ μ and c(t) ≥ min(ω(t), c(t + 1)), then by
induction on u − t, c(t) ≥ min(μ(u), min_{t ≤ x < u} ω(x)); so c ≥ r. The level set statement follows by taking
thresholds as in Theorem 1. (b) Split the maximum in (a) at u = t, t < u ≤ y, and u > y. For t < u ≤ y, ω is linear
on [t, u − 1], so its minimum there is at an end: min(ω(t), ω(u − 1)). This gives min(ω(t), Q(t + 1)). For u > y
every term passes through all of [t, y], whose minimum is min(ω(t), ω(y)), and the rest of the term is a term of
c(y + 1); taking the maximum over u > y gives min(ω(t), ω(y), c(y + 1)). (c) q(u) = min(μ(u), ω(u − 1)) is in 𝒯 by
Lemma 4.1. Its suffix maximum is in 𝒯: scanning pieces from the right with running maximum k, a piece with slope ≥ 0
contributes the constant max(k, its right-end value); a piece with slope −1 contributes itself where it exceeds k and
the constant k elsewhere, split at one integer (`pl.suffix_max`). The rest is min and max. ∎ (`field.wait_close`.)

### 4.3 The pass

```
beta_j, alpha_j, omega_v  <- tents of the instance (Lemma 4.2)
mu_s <- bottom for every s;   dirty <- {}
for every j with alpha_j not bottom:  dirty[j] <- hull of the support of alpha_j;  push (top of hull, j)
while the heap is not empty:
    pop the entry with the largest key, state j;   [a, b] <- dirty.pop(j)   (skip if j has no dirty hull)
    g    <- max(alpha_j, mu_j) restricted to [a, b]                 # the part of gamma_j not yet delivered
    cand <- min(beta_j, g shifted by -D_j)                          # on [a - D_j, b - D_j] ∩ [0, H - D_j]
    for every s with head(s) = tail(j) and (s, j) not forbidden:
        new <- max(mu_s, cand);   if new = mu_s: continue
        if head(s) is waitable:  new <- cl_omega(new)               # Lemma 4.3
        [c, d] <- hull of {t : new(t) > mu_s(t)};   mu_s <- new
        dirty[s] <- hull(dirty[s] ∪ [c, d]);   push (top of dirty[s], s)
```

One dirty interval (a hull) is kept per state, and a popped state delivers the whole of it. The existing `backward`
pushes every new piece separately.

**Theorem 4 (the pass is exact).** `margin_field` terminates, and on return mu_s = μ\*_s and
gamma_s = γ\*_s for every edge state s; `issue_margin(fld, o)` = μ\*_o for every node o.

*Proof.* Write μ for the current values and γ_j = max(α_j, μ_j).

*(i) Sound: μ ≤ μ\* always.* Initially μ = −1. A candidate satisfies cand(t) = min(β_j(t), γ_j(t + D_j)) ≤
min(β_j(t), γ\*_j(t + D_j)) ≤ μ\*_s(t) by (E_μ) and induction. For the closure: μ\*_s(t) ≥ min(ω(t), μ\*_s(t + 1)) by
(E_μ), so μ\*_s is one of the functions over which cl_ω takes the least; hence cl_ω(new) ≤ μ\*_s whenever
new ≤ μ\*_s.

*(ii) Wait-closed: at a waitable head, μ_s(t) ≥ min(ω(t), μ_s(t + 1)) always.* True for −1; every update ends with
cl_ω.

*(iii) Delivered: for every edge j, every s ∈ pred(j) and every t ∈ T outside dirty[j] with t − D_j ≥ 0:
μ_s(t − D_j) ≥ min(β_j(t − D_j), γ_j(t)).* Initially γ_j = α_j, which is −1 outside the seed hull. Popping j
delivers every t ∈ [a, b] with the current γ_j, and μ_s only grows afterwards. γ_j changes only where μ_j is
raised, and those seconds are put into dirty[j] in the same step.

*(iv) Termination.* A push after the seeds follows a strict increase of some μ_s(t). Values lie in {−1..M} and
t ∈ T, so there are at most |E|(H + 1)(M + 1) such pushes.

*(v) Complete.* At the end dirty is empty, so by (iii) and (ii) μ_s(t) ≥ right side of (E_μ) evaluated on μ, for
all s and t. Induct on t from H down: μ\*_s(t) equals the right side of (E_μ) on μ\*, which uses μ\* at later
seconds only, where μ\* ≤ μ by induction; so μ\*_s(t) ≤ right side on μ ≤ μ_s(t).

(i) and (v) give μ = μ\*; `issue_margin` evaluates the formula of Theorem 1(c). ∎

`field.check_fixed_point` checks (E_μ) with equality on the stored functions. By the uniqueness part of Theorem 1 that
alone certifies a stored field, independent of the order of solving.

**Theorem 5 (cost).** Let P be the number of pops, Δ the largest number of edges into a node, π the largest number
of pieces of any function during the run, and w the largest number of pieces of an ω_v. Then the pass takes
O(P · Δ · (π · max(1, w) + log P)) time and O(Σ_s |μ_s| + Σ_j (|β_j| + |α_j|) + Σ_v |ω_v|) memory, with
P ≤ |E| + |E|(H + 1)(M + 1) and π ≤ H + 1.

*Proof.* One pop does one restriction, one max, one shift and one min (Lemma 4.1: O(π)), then for each of at most Δ
predecessors one max (O(π)), at a waitable head one closure (w pieces of ω, each O(π), Lemma 4.3(c)) and one hull
comparison (O(π)), and one heap push (O(log P)). P is bounded in Theorem 4(iv). ∎

**What the bound does and does not say.** M enters only through π and P. The worst-case bound on P is
pseudo-polynomial and does grow with M; no better worst-case bound is proved here (and, by `SURVEY.md` point 3, a
bound polynomial in the number of intervals should not be expected even for M = 0). The claim "the cost does not grow
with the number of margins" is therefore an **empirical** claim about the recorded data, measured in `BENCH.md`. The
baseline for the same output is one existing pass per margin.

**Under M1–M4 (permanent closures, keep variant)** every level set is a prefix (THEOREM, Theorem 2, applied to each
I(m), which again satisfies M1–M4), so μ_s is non-increasing in t, and the leave-by time as a function of the margin
is L_o(m) = max over paths P of min(a_P, c_P − m), with a_P = a − len(P) the acceptance bound and
c_P = min_k (c_{j_k} − 1 − offset_k) the closure bound of the path: flat where a long safe route binds, slope −1
where a closure binds, and it can switch from one route to another as m grows.

### 4.6 The fast path (added in round 2)

`margin_field(..., fast=True)`, the default from round 2 on, returns the same functions as the pass of §4.3
(`fast=False`). Three changes, none of which alters a value:

1. **Tents and predecessor lists on first use.** β_j, ω_v and the predecessor list of j are built when edge j is
   first popped (or first read by the read-off). An edge that is never popped never contributes to any μ_s.
2. **A constant piece crossing a closure-free edge.** If B_j = ∅, α_j = ∅ and the delivered part of μ_j is one piece
   (lo, hi, v, 0), then β_j ≡ M on [0, H − D_j] and v ≤ M, so min(β_j, μ_j(· + D_j)) is the one piece
   (max(lo − D_j, 0), min(hi − D_j, H − D_j), v, 0). This is Lemma 4.1 evaluated by hand.
3. **Landing on an empty or a dominating constant function.** If μ_s is empty, the maximum is the candidate itself;
   if moreover the head of s is waitable with W = ∅, then ω ≡ M ≥ v and Lemma 4.3(a) gives
   cl_ω(μ_s)(t) = v for every 0 ≤ t ≤ hi, i.e. the one piece (0, hi, v, 0). If μ_s is one constant piece that
   contains the candidate's interval with a value ≥ v, nothing is raised and nothing is pushed, exactly as when
   `raise_to` returns an empty hull.

Every other case goes through the general routines. Checked: equality of every μ_s and γ_s between `fast=True` and
`fast=False` on 18,000 random graphs (99,176 states), three bugs planted in the fast path (each caught), and the
six-cache run repeated with the fast path (`BENCH.md` §2). The fast path is engineering, not part of the idea: it
uses nothing about margins, and the same three shortcuts could be written into the existing pass.

### 4.7 The compiled port (added in round 2)

`margin_field/nb.py` is the pass of §4.3 on fixed-size integer arrays, compiled with numba: each routine is a
line-by-line port of the routine of the same name in `pl.py` / `field.py` (general path, no fast path). A state has
room for `cap` pieces (16, grown to 64 and 256 if needed); if that, a scratch buffer of 1,024 pieces, or the heap
runs out, the compiled pass gives up and the pure-Python pass is run instead (`stats["fallback"]`). So the result is
the function of Theorem 4 in every case. Heap ties are broken differently from the Python pass; by Theorem 4 the
result does not depend on the order. Checked: equal to the reference pass on all 99,176 states of the 18,000 random
graphs, and on the caches in `BENCH.md` §2.

## 5. What the code returns

| call | returns |
|---|---|
| `margin_field(inst, M, erode_accept=False)` | `MarginField` with `mu`, `gamma` (per edge state), tents, `stats` |
| `issue_margin(fld, o)` | μ\*_o as a tent function |
| `issue_set_at(fld, o, m)` | Feas(o; m) as an interval list (equals `core.issue_set` on `widen(inst, m)`) |
| `leave_by(fld, o)` | [(m, end of the first window if it starts at 0)] at every margin where it changes |
| `field_at(fld, m)` | an ordinary F-3.1 `Field` of I(m), read off without a new pass; the unchanged `core.witness` and `core.check_fixed_point` work on it |
| `check_fixed_point(fld)` | certificate: (E_μ) holds with equality |
| `widen(inst, m, ...)` | the instance I(m) |

With M = 0 every function is 0 or −1, and the pass is a second, independent implementation of the F-3.1 field.

## 6. Search for this exact result

Search run 18 Nov 2026, 22:59–23:03 UTC, by a search agent; full record with URLs and reading levels in
`survey_notes/G_prior_art_margin_field.md`. It covered temporal robustness of signal temporal logic, robustness of
timed automata under guard shrinking, scheduling slack, max-min path algebra and multi-valued model checking, and
evacuation routing with time buffers. It was a short, targeted search with no citation-forward step; an obscure exact
match cannot be excluded.

**Outcome: the result as a whole was not found. Parts of it are known.**

| claim | status |
|---|---|
| Theorem 1 (threshold decomposition) | **Known in general form.** It is a direct corollary of the reduction theorem for multi-valued model checking (Bruns and Godefroid 2004, Lemma 1 and §3.2): on a bounded horizon the time-expanded graph is a finite structure with transitions valued in the chain {−1..M}, μ is the value of a reachability formula, and "value ≥ m iff the m-thresholded structure satisfies the formula". The same fact is the threshold decomposition of max-min matrices (`SURVEY.md` §4). Only the step "β_j(t) ≥ m iff t ∉ B_j ⊕ m" is specific. Not found written for this model. |
| Theorem 2 (robust = adaptive, exact) | Not found. The sufficiency half is the analogue of Donzé and Maler 2010, Theorem 2. The exactness half is a three-line argument here because the property is monotone in the closure sets; the temporal-logic papers stress that their measure is sufficient only. |
| Proposition 3 | **Known phenomenon**, not found for this model: it is the gap between "synchronous" and "asynchronous" temporal robustness (Rodionova et al. 2022, Theorem 4.10, "often strict"). |
| Lemmas 4.1–4.3, Theorems 4 and 5 (tent class closed under the pass including the waiting closure; one heap-ordered pass for all margins) | Not found. Closest: Donzé and Maler compute time robustness of a formula over one signal with piecewise-linear functions. No pass over a cyclic road graph with reopening closures and blocked waiting was found; the general reduction above costs one Boolean run per threshold. |

**The three closest prior works and the difference.**

1. **Donzé and Maler, "Robust satisfaction of temporal logic over real-valued signals", FORMATS 2010; Rodionova,
   Lindemann, Morari, Pappas, "Temporal robustness of temporal logic specifications", ACM TECS 2022.** Their
   time robustness is built the same way: signed distance to the nearest switching time at the leaves, then min and
   max, with a tolerance theorem and piecewise-linear computation. Difference: theirs is for a logic formula over one
   trace, with one-sided shifts and a sufficiency theorem. Here it is the least fixed point over a cyclic graph with
   travel-time shifts, turn bans and per-node waiting, two-sided, and exact (Theorems 1, 2).
2. **Bruns and Godefroid, "Model checking with multi-valued logics", ICALP 2004.** Their reduction theorem contains
   Theorem 1. Difference: no time structure, no distance functions, no widening or robustness reading, and the
   algorithm it gives is one Boolean run per threshold, which is the baseline here, not one pass.
3. **Sankur, Bouyer, Markey, "Shrinking timed automata", FSTTCS 2011; Jaubert and Reynier, "Quantitative
   robustness analysis of flat timed automata", FoSSaCS 2011.** Timed automata whose guards are tightened by a
   parameter. Difference: Sankur et al. decide whether some small enough shrinking keeps behaviour, Jaubert and
   Reynier compute the largest safe enlargement for flat automata. Neither returns the largest margin per state and
   per second for reachability, nor all margins in one pass.

Closest in application: Artigues et al. 2018 maximise the smallest slack between fire deadlines and the last use of
each evacuation arc, for the same stated reason (uncertain closure times), with fixed routes, closures that never
reopen and one optimal value. FlexSIPP (Hanou et al. 2026) computes a scalar slack along one fixed trajectory.

**Decision.** The exact result is not published as far as this search shows, so there is no return to Stage 2. The
novelty claim made in Stage 5 is limited to: the result for this model, Theorem 2's exactness, and the algorithm
(§4). Theorem 1 is credited to the general theorem above.

### 6.1 Second search (round 2, 19 Nov 2026, 09:58–10:13 UTC)

Record: `survey_notes/H_prior_art_second_search.md` (35 queries; reading level stated per paper). It was a
15-minute search, shorter than asked for; every "not found" below means "not found in a short search". It was aimed at
finding the result, in seven directions: timed-automata robustness and permissiveness, temporal graphs, uncertain
time windows, max-min profile search and safe-interval planning, temporal networks with uncertainty, evacuation
margins, and static-versus-adjustable robust optimisation.

**Outcome: neither Theorem 2 nor the algorithm was found published. Two things change in the account above.**

* **A closer work for the algorithm.** Clement, Jéron, Markey, Mentré, "Computing maximally-permissive strategies in
  acyclic timed automata", FORMATS 2020 (main body read). They compute, backward, a piecewise-affine "permissiveness"
  of every configuration: the largest δ such that the player can always propose a delay interval of length ≥ δ and
  still reach the target, with bottleneck (max-min) aggregation. Same skeleton as §4. Differences: what is perturbed
  is the traveller's own delays, not the closures; the strategy is adaptive by construction; acyclic automata only
  (cycles are left open there); slopes such as 1/2; doubly exponential cost for linear automata; no shift, waiting
  closure or cap. This replaces Sankur et al. as the third closest work.
* **Theorem 2 is short and its mechanism is known.** It is not an instance of Ben-Tal, Goryashko, Guslitzer,
  Nemirovski 2004, Theorem 2.1 (linear, convex, constraint-wise; their own counterexample is the shared-parameter
  case, which is ours) nor of Marandi and den Hertog 2018, Theorem 1 (constraint-wise with fixed recourse). But its
  proof is the same dominating-scenario argument as the proof of the latter: one scenario, I(m), is in the
  uncertainty set and is worst for every constraint and every journey at once. A referee would call Theorem 2 a
  short observation. It was not found stated for closure timing in routing, temporal graphs or safe-interval
  planning. Füchsle et al. 2022 is the contrasting case: when travel times are what is delayed, static and adaptive
  routes differ and the static problem is NP-complete.
* **Theorem 6** was added after this search; it was searched for in §6.2. Its definition
  pattern is published (Fainekos and Pappas 2009, robustness degree as distance to the violating set; stability radius,
  Leont'ev, Sotskov, Gordeev 1995; both seen as search summaries only, not opened). Given Theorem 2 it is a
  three-line corollary. No novelty is claimed for it beyond "not found for this model".

**The three closest prior works, revised:** (1) Donzé and Maler 2010 with Rodionova et al. 2022; (2) Bruns and
Godefroid 2004; (3) Clement, Jéron, Markey, Mentré 2020. Not done: the Clément 2022 thesis was not opened and could
extend (3) to cycles; forward citations of (3) and of Füchsle et al. were not walked.

**Decision unchanged**: no return to Stage 2. The novelty claim is narrowed in one respect: Theorem 2 is claimed as
"not found stated", not as a deep result.

### 6.2 Third search (round 2, 19 Nov 2026, 10:20–11:05 UTC)

Record: `survey_notes/I_prior_art_third_search.md` (78 queries, 28 works, reading level per work, and a list of what
stayed unread). It closed the gaps left by §6.1: Clément's 2022 thesis, forward citations of Clement et al. 2020
and of Füchsle et al. 2022, the stability-radius literature for Theorem 6, the base model, and transit routing.

| claim | outcome | closest work found | difference |
|---|---|---|---|
| Theorem 2 | not found | Cui, Yu, Fang, Haslum, Williams, ICAPS 2015 (section read): the largest uniform deviation under which a schedule stays controllable, computed under both strong (static) and dynamic (adaptive) controllability | There the two values **differ** (in 6 % of their schedules the static value is zero and the adaptive one is not). The equality in Theorem 2 is therefore specific to uncertainty that acts on the environment's closure sets and is monotone. |
| Theorem 6 | not found for any routing, scheduling or temporal-graph model; **every ingredient has a published analogue** | Rodionova et al. 2022, Theorems 4.3/5.4 (read through a summarising tool only): in discrete time, shifts up to r preserve satisfaction and shift r + 1 flips it | One fixed signal under one uniform shift; no choice of journey, no ball of forecasts. Also: the definition "stability radius = largest distance within which every perturbed model still satisfies the specification" is Henzinger and Otop, CONCUR 2013, Def. 6 (untimed; the timed case is left open there); μ is a "radius of robust feasibility" in the sense of Liers, Schewe, Thürauf 2022; the Hausdorff distance between edge-availability sets as a metric on time-varying graphs is Bernardoni et al. 2023 (no reachability theorem); Fainekos and Pappas 2009 define robustness as distance to the violating set and compute only an under-approximation of it outside one fragment. Classical stability radii (Chakravarti and Wagelmans 1998, bottleneck case) concern the optimality of one solution under cost changes, not the feasibility of a decision under changes of constraint times. |
| Algorithm | not found | Busatto-Gaston, Monmege, Reynier, Sankur, CAV 2019, Prop. 6 (read): the largest admissible perturbation of **one given lasso** of a timed automaton, by a backward operator with a shrink-by-δ step over zones piecewise-affine in δ | One given cycle, not all paths, origins and seconds; the controller's own delays are perturbed and errors accumulate, so the strategy is adaptive. Clément's thesis keeps the backward permissiveness computation acyclic and non-elementary, and states cycles as open. |

**Base model credit.** Road closures over several periods together with no-waiting periods at nodes are the model of
Halpern and Priess, "Shortest path with time constraints on movement and parking", Networks 4 (1974) (abstract read;
body not available). The waiting policies are Orda and Rom 1990. The margin field adds nothing to the base model.

**What stayed unread** is listed in the record; the main items are Sotskov, Leont'ev, Gordeev 1995 (the stability
survey), the body of Halpern–Priess 1974, and the proofs in Clément's thesis.

**Position after three searches.** Not found published: the one-pass algorithm on cyclic graphs; Theorem 2 for
closure timing; Theorem 6 for any routing model. Known: Theorem 1 (Bruns and Godefroid); the mechanism of Theorem 2
(dominating scenario); the definition pattern and every ingredient of Theorem 6; the base model. The honest size of
the contribution is: a known kind of quantity (a robustness radius), shown to be exact and adaptivity-free for this
model by short proofs, with an algorithm that was not found elsewhere and that works where the closest algorithms
(permissiveness, lasso perturbation) stop: on cyclic graphs, for every state and second at once.

## 7. Limits

* The margin is in **time**. A reach margin in kilometres is a different family: its level functions are linear in t
  with slope 1/d_c, Theorem 1 holds for it word for word, but the tent class (slopes ±1) does not; it needs
  rational slopes and is not implemented (`CANDIDATES.md` C3b).
* All closures get the **same** m. Per-cell or per-member margins are not covered.
* Unpredicted closures far from any predicted one are outside 𝒫(m). The margin protects against timing error, not
  against fire where none was forecast.
* The margin field inherits every assumption of the F-3.1 instance (THEOREM §7), including that the dose budget does
  not bind (C3); with a binding dose the robust and adaptive readings separate (§3).
