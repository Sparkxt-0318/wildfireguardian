# Landslides prior-art note (stub)

Owner: A7. **This is a started stub, not a swept prior-art note.** The
program's priority this round was the roads direction (see
`roads_prior_art.md`, T1.6/T1.7/T1.8). A full Korean-language and
English-language sweep for H-SLIDE has not been run yet: whether pine and
broadleaf stands differ in recovery window is part of the untested <!-- research-claim-ok: RC-004 -->
hypothesis, not a swept topic. Do not treat the absence of a finding here as
evidence the literature is thin; it has not been looked at closely.

H-SLIDE, in the hypothesis wording `FORBIDDEN_CLAIMS.md` requires: a burned
Korean slope stays more landslide-prone for a bounded number of years after
fire, and that window differs between pine-dominated and
broadleaf-dominated stands. Status: untested, no hazard model fitted.

## What is already verified and load-bearing

**Sidle 1992** (`sidle1992` in `bibliography.bib`), Roy C. Sidle, "A
theoretical model of the effects of timber harvesting on slope stability,"
Water Resources Research 28(7), 1897-1910, DOI 10.1029/92WR00804. Verified by
Crossref DOI lookup on 2026-09-16.

This is the paper the landslide direction plans to draw its root-cohesion
curve shape from, so getting the functional form right matters. What this
agent could confirm about the published model, from the abstract and
methods summary reached (not a full line-by-line read of the paper's
equations; a follow-up sweep should confirm exact parameter values against
the PDF or a library copy):

- The model tracks root cohesion and vegetation surcharge through repeated
  timber-harvest cycles, together with a stochastic rainfall-driven
  pore-water-pressure term.
- **Decay of the old root network** (roots of the harvested/removed stand)
  is modeled as an **exponential decay function** of time since removal.
- **Recovery of root strength and surcharge from the regrowing stand** is
  modeled as a **sigmoid (S-curve) relationship** with time since regrowth
  begins. The two curves are not mirror images of each other; the model
  combines a decaying old-root term and a growing new-root term, and the net
  root reinforcement at any time is their combination, which is why the
  reported impact on landslide frequency is strongest in the first 1 to 10
  years and tapers but is still present out to about 25 years after
  harvest.
- This is a **timber-harvest** model, not a fire model. Sidle 1992 is prior
  art for the mathematical shape (exponential decay plus sigmoid regrowth),
  not a direct measurement of a fire-caused root-strength decay curve for
  Korean stands, and it uses no Korean data. It is method-and-prior-art
  only; korea_data = no in the bibliography entry.
- **Open item for a follow-up sweep:** this agent has not yet pinned down
  the exact published parameter values (decay rate constant, sigmoid
  midpoint and steepness) with page or equation numbers, as the brief asked
  for. A follow-up pass should read the full PDF (a copy may be reachable at
  iahs.info or via the AGU DOI page) and record the equation numbers
  directly, since the landslide direction will need the actual constants,
  not just the functional forms, before it can adapt the curve to a
  fire-decay context.

## Not yet done

- Korean-language sweep for post-fire landslide studies (산불 이후 산사태,
  화재 후 토사재해, 소나무 활엽수 사면안정) has not been run.
- No search yet for papers that directly measure a post-fire (rather than
  post-harvest) root decay and hazard window, which is the actual mechanism
  H-SLIDE needs, as opposed to the post-harvest analogy Sidle 1992 provides.
- No search yet for the pine-versus-broadleaf species contrast specifically.
- The Sancheong landslide inventory (Nguyen, Song and Kim 2026, 568
  initiation points) mentioned on the taskboard as WJ-005 (a drafted request
  to Pukyong National University) is a data-access matter, not a literature
  item, and is out of scope for this note; flagging only so it is not
  confused with a literature gap.

Next suggested task for whichever agent picks this up: a dedicated sweep
round for H-SLIDE, Korean-language first, following the same verify-before-
citing discipline as the roads note.
