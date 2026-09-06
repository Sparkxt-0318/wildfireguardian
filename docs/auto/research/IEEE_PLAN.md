# IEEE submission plan — status page

*Created 2026-09-06 by the research routine (ROUTINE_PROMPTS.md step 5, CHARTER §1 goal 3 and §2). **Nothing is submitted anywhere by any routine, ever.** This page tracks where the manuscript stands against a venue, what closes each gap, and what only the author can do. Kept current every research run.*

**Timeline from CHARTER §1:** freeze 2026-10-16 · KCF finals 2026-10-24 · KCF awards 2026-12 · **IEEE submission after 2026-12** · ISEF window 2027-01 → 05. So no submission decision is due inside the sprint, and nothing here is urgent. What *is* time-sensitive is that the gaps below close while the evidence is being built rather than afterwards.

## 1. Venue — candidate, and the one figure that is checked

**Primary candidate: IEEE Access.** Its Article Processing Charges page states 「There is no page limit for articles and therefore no over-length article charge」 and 「strongly recommend[s] keeping the page count under 20 pages for ease of readability」 (<https://ieeeaccess.ieee.org/about/article-processing-charges/>, read 2026-09-05 by paper lap 7, recorded in `paper/GAPS.md`). The manuscript measures **23 pages under Carlito** at the last render (paper lap 12), inside the author's own 25-page ceiling (NH-028) and above IEEE Access's readability recommendation. That is a recommendation, not a rule, and no action is taken on it this run.

⚠ **IEEE Access is an APC journal and this project may spend no money (CHARTER §3 rule 6).** The APC is therefore an **author decision and a possible blocker**, not something a lap resolves. It is recorded here so that it is not discovered late. Alternatives that avoid an APC — an IEEE conference in the disaster-informatics or geoscience line, or a society journal without a mandatory charge — have **not** been surveyed by any run yet, and that survey is the next research lap's IEEE task.

**Not yet checked, and each is a one-page task for a later run:** the exact IEEE Access scope statement against a wildfire-evacuation-decision paper; whether an ISEF-window submission conflicts with any ISEF rule on prior publication (this one bears on goal 3 and should be checked before, not after, a submission decision); and the reference-style conversion cost from the current `references.bib`.

## 2. What the manuscript already has that a reviewer will want

- Complete sections, author **Siyeong Park (박시영)**, every number a registry key or a committed artifact value, every citation opened at its URL and marked `verified` in `references.bib` (CHARTER §12).
- A withdrawn-claim record that is machine-checked across 925 gated files (`docs/auto/withdrawn_claims.json`, `WC-001`…`WC-004`), which is an unusual and genuinely reviewable thing to be able to show.
- Figures drawn from committed artifacts in one style at 300 dpi, colour-blind safe.
- Leave-one-fire-out cross-validation rather than random splits — and as of this run there is an external measurement of what that discipline costs elsewhere (Farajpoor & Narimani 2026, §2.1 of `WEEKLY_2026-W36.md`).

## 3. Open gaps that bear on a submission, in the order a reviewer will hit them

| # | gap | who closes it | when |
|---|---|---|---|
| G4 | **the hindsight-field routing arm** — until it runs, 「saved」 means 「re-routed around a model-flagged cell」, not 「away from where the fire went」. `paper/GAPS.md` calls it the single most load-bearing gap | needs the author's laptop (raw FIRMS detections are git-ignored) | after the sprint; **this is the one a reviewer is most likely to reject on** |
| G8 | which build of the present-perimeter opponent defines the comparison — two dev laps built it concurrently and disagree by about a factor of three | **NH-032 / NH-034, the author** | open |
| G7 | the present-perimeter arm on Yeongdeok's own 458 origins (the headline's origin set) | WFG-033(b), or the cheap 44-origin version `paper/GAPS.md` specifies | before the finals for the cheap version |
| G3 | the leak-free Yeongdeok fold with the co-located Uiseong-Andong fire excluded | laptop raw bundle, WFG-032 | after the sprint |
| G5 | the provenance of the detection reference clock | the author supplies a 신고접수시각 record (NH-019) | open |
| G2 | practitioner consultations, and naming permission for the three researchers already quoted | the author (NH-009) | before any submission |
| G6 | refuge provenance — OSM points versus the committed 주소정보누리집 designated sites | WFG-073, runnable in the sandbox | before freeze |
| new | related work does not yet name the two-stage supported-evacuation problem class (arXiv:2608.05413) or the domestic operational systems | WFG-026, WFG-144 | before freeze |

## 4. Author-only items, collected in one place

1. **The APC decision, or the choice of a venue without one** (§1). Nothing proceeds past a submission decision without it.
2. **Naming permission** from the three domain researchers, or the manuscript keeps 「an external researcher」 / 「three domain researchers」 (G2).
3. **The laptop raw bundle**, which is what unblocks G3 and G4 — the two gaps most likely to draw a reviewer's fire.
4. **Whether an IEEE submission before ISEF 2027 creates an ISEF prior-publication problem.** Not researched yet; flagged here so it is not discovered in 2027-01.

## 5. Standing rules for every routine touching this plan

- **Never submit anything anywhere.** No routine has, and none may.
- No venue claim without a URL read in the run that wrote it.
- The manuscript's length rule is the author's 25 pages; the 9,000-word budget is the proxy and a lap does not raise its own ceiling (NH-037 open).
- Nothing on this page is a judge-facing surface; KCF material never cites an unsubmitted paper as published.

## 6. Changelog

- **2026-09-06** — page created. Venue candidate recorded with the one figure that had already been read; the APC problem named as an author decision rather than left implicit; the alternative-venue survey filed as the next run's IEEE task; gap table assembled from `paper/GAPS.md` and this run's two new related-work items.
