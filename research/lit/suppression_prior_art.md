# Suppression prior-art note (stub)

Owner: A7. **This is a started stub, not a swept prior-art note.** The
program's priority this round was the roads direction (see
`roads_prior_art.md`, T1.6/T1.7/T1.8). No dedicated sweep for H-SUPP has been
run yet. Do not treat the absence of a finding here as evidence the
literature is thin; it has not been looked at closely.

H-SUPP, in the hypothesis wording `FORBIDDEN_CLAIMS.md` requires: the
recorded Korean fire-size distribution is right-censored by suppression, and
fires that would have grown large can be separated from the rest using
information available in the first hours. Status: untested, no containment
or tail model fitted.

## What is already verified

**Ustun and Rudin 2017** (`ustun2017riskslim` in `bibliography.bib`), "RiskSLIM"
/ "Optimized Risk Scores," Proceedings of the 23rd ACM SIGKDD International
Conference on Knowledge Discovery and Data Mining, pp. 1125-1134, DOI
10.1145/3097983.3098161. Verified by Crossref DOI lookup on 2026-09-16.
Method source for building a small, interpretable, integer-weighted risk
score; the suppression direction plans to use this for an early-hours
escape-risk score.

**Liu, Zhong, Li, Seltzer and Rudin 2022** (`liu2022fasterrisk`), "FasterRisk:
Fast and Accurate Interpretable Risk Scores," Advances in Neural Information
Processing Systems 35, pp. 17760-17773, DOI 10.52202/068431-1291. Verified by
Crossref DOI lookup on 2026-09-16. Faster method for the same family of
interpretable risk-scoring models; a practical alternative or complement to
RiskSLIM for fitting a score on Korean fire-incident features.

Both are general-purpose interpretable-ML methods, not fire-specific and not
Korean; korea_data = no in the bibliography, method source only.

## A flagged discrepancy, not (yet) resolved

The brief also lists "Keeling et al. 2001" as an already-verified reference
for this agent to add to the bibliography. A7 could not verify any paper by
that author-year combination in a context relevant to suppression, censoring,
or fire-size distributions; see `UNVERIFIED.md` for the full search log. It
is possible this was intended to be a different name (a search for "Keeley,"
the well-known wildfire scientist, turned up real 2001 papers, but none
closely enough on point to assert as a substitute), a different year, or a
reference that does not in fact exist as described. This is flagged
prominently in the round-1 report and should be resolved by whoever supplied
the original reference before it is treated as settled.

## Not yet done

- No sweep yet for the actual statistical machinery H-SUPP needs: censored
  or truncated fire-size distribution models, survival/hazard models for
  containment time, or comparable "early warning of a large event" work in
  wildfire, flood or other hazard domains.
- No sweep yet for Korean-language suppression/containment literature (진화
  실패, 대형산불 전이, 초기진화).
- No check yet on whether the Cumming 2001 "parametric model of the
  fire-size distribution" (Canadian Journal of Forest Research, DOI
  10.1139/x01-032, found incidentally while chasing the "Keeling et al.
  2001" lead, see UNVERIFIED.md) is itself relevant prior art for the
  right-censoring question; it was not added to the bibliography this round
  because it was not part of the assigned task and its relevance has not
  been assessed, but it looks worth a look given its title.

Next suggested task for whichever agent picks this up: a dedicated sweep
round for H-SUPP, resolving the Keeling/Keeley discrepancy first since it
blocks knowing what is actually already verified.
