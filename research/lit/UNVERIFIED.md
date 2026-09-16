# Unverified references

Anything in this file failed A7's verification bar (Crossref DOI lookup, or a
publisher page fetch that confirms the record) and does **not** appear in
`research/lit/bibliography.bib`. Each entry records exactly what was searched
and what was found or not found, so a later agent does not repeat the same
dead ends without knowing they were dead ends.

## Keeling et al. 2001

**Status: could not be verified. This citation may not exist as described.**

The program brief (A7's task instructions, round 1) lists "Keeling et al.
2001" among references "already verified" elsewhere in the program, asking
A7 only to add it to the bibliography with its DOI. A7 could not find any
paper matching that author-year combination in a context relevant to this
program (wildfire, forest roads, landslides, suppression, risk scoring, or
right-censored/extreme-value statistics, which is the area the surrounding
brief text suggests it was meant to support).

What was searched:

- Crossref `query.bibliographic` for combinations of "Keeling 2001" with:
  magnitude of completeness / earthquake catalogs, power-law wildfire,
  extreme value statistics, right-censored distribution, forest fire size
  distribution. None returned a plausible match.
- Crossref `query.author=Keeling` restricted to `from-pub-date:2000-01-01`
  to `until-pub-date:2002-12-31`. This returned 15 results, all by different
  Keelings (David Keeling on coagulation disorders, Patrick J. Keeling on
  molecular phylogeny, Richard P. Keeling on college health, Jean W. Keeling
  on fetal pathology, K. M. Keeling on gene therapy, Sally Keeling on ageing
  in New Zealand). None is a wildfire, forestry, geohazard or risk-modeling
  paper.
- A web search for "Keeling et al. 2001 wildfire suppression escape
  probability containment" returned no match.
- As a plausibility check for a name transcription error (Keeley is a
  well-known wildfire scientist and the two names are one letter apart), a
  Crossref author search for `Keeley` restricted to 2000 to 2002 was also
  run. It returned several real 2001 papers by Jon E. Keeley on chaparral
  fire regimes and fire history in California (for example
  `10.1046/j.1523-1739.2001.00097.x`, `10.1086/323594`), but nothing that
  matches a fire-size-distribution, escape-probability or risk-scoring
  context closely enough to assert it is "the" intended reference. Guessing
  would violate the verification rule, so none of these was added to the
  bibliography as a stand-in for "Keeling et al. 2001".

**What is missing:** the correct spelling of the author's name, the exact
title, and the venue. Until one of those is supplied, this citation cannot
enter the bibliography. Flagged in the round-1 report as a finding, not
silently dropped or silently substituted.

## Kim and Im 2024, full paper (beyond the conference abstract)

The conference abstract itself (`kim2024` in bibliography.bib) is verified
via the earticle.net aggregator page. What is **not** verified is whether a
fuller journal-length version of this study exists beyond the one-page
autumn-conference abstract (pp. 11-11 of the 2024 KSFE conference
proceedings). A targeted Crossref search
(`query.bibliographic=Kim+Im+firebreak+fire+dynamics+simulator+roadside+fuel+management+Yeongdeok`)
returned no matching DOI, and no full-length KCI or DBpia journal record was
found in the time available this round. If a full paper exists, it should be
searched again in KCI/DBpia directly by the authors' Korean names (김정윤,
임상준, Seoul National University) rather than by English keyword.

## NIFoS attachment 2-2 (the source data behind the 6 m claim)

Not a citation-verification failure but a related gap: the press release
page itself was confirmed and quoted directly (see `nifos2025pressrelease`
in bibliography.bib and `roads_prior_art.md`), but attachment 2-2, which the
release says is where the supporting research is referenced, is a
session-bound download this agent cannot reach without violating the "no
accounts, no terms-of-service acceptance" rule. This is already tracked as
human gate **WJ-004** on the taskboard; A7 does not duplicate it there since
the taskboard is not A7's file to edit, but the underlying evidence gap is
recorded here for completeness.
