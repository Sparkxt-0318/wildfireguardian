# Landslides direction, open questions

Owner: A4. Companion to
`research/landslides/PREREG_landslides_2026-09-16_v0.1.md`.

Every question carries A4's recommendation, so that nothing here reads as a
request for someone else to decide what A4 should have decided. Where the
recommendation is already binding inside the pre-registration, the question is
about whether to overturn it, not about whether to make it.

Each row names who owns the decision. A4 owns nothing outside
`research/landslides/**` and `research/reports/A4/**`.

| id | question | owner | A4's recommendation |
|---|---|---|---|
| Q1 | add a `RI_CENTROID` rung to the geocoding precision ladder | A1 | yes |
| Q2 | is the catchment the right primary unit | A6, at sign-off | yes, and the pre-registration already commits to it |
| Q3 | is an areal count likelihood acceptable in place of the binary hazard the brief specified | A6, at sign-off | yes |
| Q4 | does KOGL Type 3 permit a derived species covariate | John, WJ-012 | derive, never publish a layer, ask the licensor |
| Q5 | should the species arm be attempted at all | A6 and John | yes, as a permanently demoted secondary, and withdraw rather than report weakly |
| Q6 | does the registered 5,000 m block survive the rainfall correlation range | A6, once the radar lands | re-register if it does not, do not tweak |
| Q7 | does this direction need its own vocabulary detector | orchestrator | yes, and A4 will write it in the tree it owns |
| Q8 | is the reporting term worth fitting when it is not identified | A6 | yes, as a term, never as a claim |
| Q9 | which fire takes the held-out role Sancheong cannot fill | A6 | none; report the block cross-validation and say Sancheong tests only the level |
| Q10 | should the direction fit anything at all if the longer record never arrives | John and A6 | yes, but the reported quantity is a bound and is named as one |

---

## Q1. A `RI_CENTROID` rung in the precision ladder

**The question.** `research/shared/geo/geocode.py` defines the ladder as
`PARCEL`, `EUPMYEONDONG_CENTROID`, `SIGUNGU_CENTROID`, `UNRESOLVED`. The
landslide occurrence record's modal address bottoms out at a **리**, which is
finer than a 읍면동 and coarser than a parcel, and the ladder has no rung for it.

**What is measured.** From
`research/landslides/design/address_precision.py`, over all 5,118 records:
95.64 per cent carry all four address fields down to the 리, 4.28 per cent stop
at the 읍면동, 0.06 per cent carry a 리 with no 읍면동, and one record stops at
the 시군구. **Zero records carry a lot number in the finest field**, so the
`PARCEL` rung is unreachable for the whole file.

**Why it matters.** Carrying 95.64 per cent of the file at
`EUPMYEONDONG_CENTROID` would understate its precision. The rule that levels are
never mixed silently would then be satisfied in letter while discarding the one
property that makes the record spatially usable at all, and the assignability
measurements of pre-registration section 8.4 would be run at a coarser confusion
set than the data actually supports, which would push gate U1 toward a coarser
unit than necessary.

**Recommendation. Yes, add the rung.** Insert `RI_CENTROID` between `PARCEL` and
`EUPMYEONDONG_CENTROID`, keeping the `IntEnum` ordering property that a smaller
value means more precise. The change is additive and does not alter the meaning
of any existing rung. A4 does not own `research/shared/` and has not touched it;
`research/landslides/design/address_precision.py` names the proposed rung in a
local mapping so that nothing downstream depends on a change that has not been
made.

**If the answer is no**, the pre-registration runs at
`EUPMYEONDONG_CENTROID` for the whole record, gate U1 selects a coarser scale,
and the pre-registration is amended to say that the coarsening was a ladder
limitation rather than a data limitation. That distinction should not be lost.

---

## Q2. Is the catchment the right primary unit

**The question.** The brief specifies slope units. Pre-registration section 8
changes the primary unit to the catchment and demotes the slope unit to a
conditional secondary behind gate U2.

**The case for the change, in three independent arguments.**

1. **Geocoding.** No record carries a lot number, so the finest confusion set is
   a 리 polygon, which is very much larger than a slope unit. Assigning a record
   to a slope unit would be a draw from a distribution over many units, and the
   argmax would have no claim to be right.
2. **Terrain.** At 30 m posting the DEM cannot resolve the convergent hollow
   where a shallow Korean landslide initiates. Even a perfect coordinate would be
   assigned to a unit whose defining terrain has been smoothed away. This
   argument is independent of the first and survives a better occurrence record.
3. **Tuning.** A slope-unit partition is usually parameterised by tuning against
   a landslide inventory, which is tuning the unit against the outcome and fires
   leakage item A3. A catchment partition from flow accumulation has one free
   parameter and can be set by an outcome-free rule.

**Recommendation. Yes, the catchment, and the pre-registration already commits to
it.** What A4 asks A6 to review is not the choice but the **gate**: pre-registration
section 8.5 selects the scale by measurements M1 to M3 and gate U1, with fixed
thresholds of 0.60 assignable share and six covariates clearing an M3 floor of
0.30. Those two numbers are the place to argue, because they are the ones that
decide the answer, and they were fixed before any of the measurements ran.

**What would overturn it.** An occurrence record with coordinates, or a 5 m DEM
plus an occurrence record with coordinates. Either is a new pre-registration.

---

## Q3. An areal count likelihood in place of the binary hazard

**The question.** The brief specifies a discrete-time hazard model on the
probability that a slope unit fails in a given storm. Pre-registration section
10.2 fits a negative binomial count of recorded landslides per unit per storm,
with a forest-area offset, and recovers the failure probability as a derived
quantity.

**Why.** Address-level data does not identify which slope failed. A unit-level
binary label would therefore be manufactured by the assignment rule rather than
observed, and its error would be correlated with unit size and with terrain,
which are covariates. A count with an area offset is what an areal record
supports and it does not pretend to information the file does not carry. It also
admits repeat failures in one unit in one storm, which a binary label would
silently truncate and which leakage item C7 asks to be ruled on in advance.

**Recommendation. Yes.** The quantity the brief asks for survives as
`1 - exp(-mu)` at its own key path, labelled as a transformation of the fitted
intensity rather than as a separately estimated probability.

**The cost, stated.** A count model's dispersion parameter absorbs clustering
that a binary model would have to attribute, so a high fitted dispersion is
evidence that the unit is too coarse, and pre-registration section 22.2 reports
it. If dispersion is extreme at the chosen scale, that is information about gate
U1's choice and should be read as such.

---

## Q4. Does KOGL Type 3 permit a derived species covariate

**The question.** `kfs_forest_type_map` is licensed 공공저작물 제3유형, which is
attribution with **no modification**. The direction wants a pine-or-broadleaf
covariate derived from it. This is human gate WJ-012, and the download is a
separate gate, WJ-018.

**A4 is not a lawyer and does not own this.** The reasoning offered, for whoever
does:

- Computing a covariate from the layer, using it inside a model, and publishing
  only fitted coefficients neither redistributes the work nor alters it. That
  reads as analytical use.
- Publishing a derived raster or vector that another party could use in place of
  the original is the case a no-modification term most plausibly reaches.
- The two are separable at no cost, so the safe design costs nothing.

**Recommendation.** Derive the covariate, publish only coefficients, **never
publish a derived layer under any outcome**, attribute the source, and ask the
licensor in the same sitting as the WJ-018 application since both touch the same
office. Pre-registration section 11.2 fixes the never-publish-a-layer rule now,
so it is not a decision made under deadline later.

**If the answer is no**, the species arm falls to the phenological classifier of
pre-registration section 11.3, with the validation catch of section 11.4.

---

## Q5. Should the species arm be attempted at all

**The question.** A6 has already advised demoting it to a pre-registered
secondary before anyone invests in it. It sits behind two human gates, its
fallback cannot be validated on Korean data, and leakage item C6 says species
covaries with soil depth, aspect and management in Korea.

**The case against attempting it.** Three separate ways to be wrong, each of
which biases toward a spurious difference or toward a spurious null: the species
covariate may be misclassified, the soil conditioning is by class rather than by
depth, and the fires available give three cohorts.

**The case for.** It is half the question as posed, it costs nothing extra once
the layer exists because it is one covariate and one interaction, and a
pre-registered withdrawal is a cleaner scientific record than never having asked.

**Recommendation. Attempt it, permanently demoted.** Pre-registration section
11.4 demotes it permanently rather than conditionally, and failing condition F5
withdraws it rather than reporting it weakly, which is the specific failure mode
worth guarding: a species contrast reported as suggestive is the sentence that
gets quoted without its interval.

**The asymmetry that must be in the reading rule, and is.** Non-differential
misclassification of a binary covariate attenuates its contrast toward zero, so a
null species result is weak evidence against a difference. Reporting a null as
evidence of no difference would be the mirror of the roads direction's
attenuation problem and it is forbidden by the same logic.

---

## Q6. Does the registered 5,000 m block survive the rainfall correlation range

**The question.** Leakage item C1 requires the block to be larger than the
correlation range of the triggering rainfall, which is a property of the radar
product. `PRIMARY_SPLITS["landslides"]` registers 5,000 m with a declared
sensitivity grid of 2,000, 5,000 and 10,000 m. The radar product is behind an
unset key, so the range is unmeasured.

**Recommendation.** Fit an empirical variogram of storm accumulated rainfall over
the enumerated storms as soon as the product lands, report the range, and confirm
that 5,000 m exceeds it. **If it does not, raise the block size to the next cell
of the declared grid that does, and treat that as a new version of the
pre-registration rather than as a tweak.** Pre-registration section 12.4 commits
to that in advance, which is the only thing that stops it being a tweak.

**Why this is not a small item.** If the correlation range of Korean convective
storm rainfall exceeds 5,000 m, then the registered block puts correlated rows on
both sides of the fold boundary and every held-out number is optimistic. The
1,000 m buffer helps and does not fix it, because a buffer removes training rows
near the boundary and does not shorten the correlation range.

---

## Q7. Does this direction need its own vocabulary detector

**The question.** A6 made the roads direction's vocabulary enforceable rather
than promised, as condition C7 of `research/eval/signoffs/roads_v0.2.md`, and A3
answered with `research/roads/check_vocabulary.py`. This direction's permitted
vocabulary is pre-registration section 21.2 and nothing checks it.

**Recommendation. Yes, and A4 will write it**, in the tree A4 owns, matching the
pattern of the roads detector: fire on the assertive spellings (landslide risk,
the effect of fire on slope stability, the recovery period, post-fire landslide
susceptibility used as a measured quantity, a road causing a landslide) and spare
the permitted ones (recorded landslide rate, the association between years since
fire and recorded rate, the fitted root-strength term, the model-implied critical
rainfall). It is validated in both directions before it is added, per the bar
`research/FORBIDDEN_CLAIMS.md` sets: a rule that fires on legitimate hedged
wording is worse than no rule.

**It is not written in this round** because the vocabulary it would enforce is
itself under review at sign-off, and a detector written against a vocabulary that
A6 then changes is wasted work plus a stale rule. Sequencing it after the
sign-off is the recommendation, not skipping it.

---

## Q8. Is the reporting term worth fitting when it is not identified

**The question.** Pre-registration section 10.5 item 4 says the hazard rate and
the reporting probability are not separately identified, because they enter
`log mu` additively and the record observes only their product. If it is not
identified, why fit it.

**The case for dropping it.** A term that is not identified takes its posterior
from its prior, and reporting it invites a reader to treat a prior as a finding.
That is the exact defect A6 named in the roads direction's two-term breach
product, item B8.

**The case for keeping it.** The reporting covariates are not pure noise. They
have real spatial structure, and leaving them out does not remove the reporting
mechanism, it pushes it into the fire term and into the block random effect,
where it is invisible. The choice is not between an identified model and an
unidentified one; it is between an unidentified term that is named and an
unnamed confound.

**Recommendation. Keep it as a term, never as a claim.** No coefficient inside
the reporting term is reported as a mechanism, the road coefficient in particular
is forbidden a causal reading by pre-registration section 21.1 item 5, and the
composite is what is reported, exactly as the root-decay-versus-regrowth split is
handled in section 10.5 item 2. The consistent rule across both cases: when a
fitted quantity is a sum of two things the design cannot separate, rename the
quantity rather than caveat it.

---

## Q9. Which fire takes the held-out role Sancheong cannot fill

**The question.** Leakage item C8 says that if a paper's numbers set a prior,
Sancheong is not a valid held-out fire and another fire has to take that role.
Pre-registration section 3.3 records that no Sancheong number has set anything,
so C8's remedy is not triggered. But section 15.6 finds a different problem:
Sancheong contributes years since fire of zero only, so it cannot test the curve
whatever its validity as a holdout.

**The temptation to avoid.** Substituting Uljin 2022 as the held-out fire,
because it is the one cohort reaching years since fire of three. That would
remove the only cohort carrying the largest observable value of years since fire
from the training set, which would leave the shape of the curve supported by two
cohorts reaching at most two years.

**Recommendation. No substitute fire.** The held-out sets are the spatial blocks
of `PRIMARY_SPLITS["landslides"]`, which is what the registered split already
says, and Sancheong is reported as a **level** test at years since fire of zero
with the reading rule of section 15.6 fixed in both directions in advance. A
leave-one-fire-out arm is reported as a **secondary** diagnostic precisely
because with three usable cohorts it removes a third of the shape information
each time, and section 13.4 labels it secondary so it cannot be promoted.

---

## Q10. Should the direction fit anything if the longer record never arrives

**The question.** The committed exposure record observes years since fire of
zero, one, two and three, and prior art puts the analogous effect running to
about twenty-five years. The design is right-censored below the quantity it is
meant to estimate. Is fitting it at all the right call.

**The case against.** A right-censored estimate of a window will be quoted
without its censoring. Rule RC-003 exists for exactly that sentence, and a
machine-enforced rule is a weaker guard than not producing the number.

**The case for.** Three things this design produces are real regardless of the
censoring: whether burned ground carries a higher recorded landslide rate than
comparable unburned ground at year zero, under an explicit rainfall term; the
identified curvature of the fire term over years zero to three; and the
assignability and aliasing tables, which are outcome-free findings about what
Korean address-level records can support. The first two are worth having. The
third is worth having whether or not anything is fitted.

**Recommendation. Fit, and name the quantity for what it is.** The reported
quantity is a right-censored lower bound over years zero to three, under the
three-specification reading rule of pre-registration section 7.6, with the
largest observable value of years since fire quoted beside it every time. The
sentence that must never be written is any form of "burned Korean slopes return
to baseline after N years", and that sentence is already forbidden by rule
RC-003 rather than by A4's restraint.

**The ordering this implies, which is the practical answer.** The outcome-free
work of gate U1 and of the aliasing table comes first, before any outcome is
touched, because it can stop the direction cheaply. Pre-registration section 23
puts it at item 4 of the gate order for that reason.
