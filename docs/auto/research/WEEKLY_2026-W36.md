# Research lap — ISO week 2026-W36 (run 2026-09-06T1817Z)

*`wfg-autoloop-research`, first run under the sprint cadence (CHARTER §11, §14: every second day at 18:17 UTC, 09-06/08/10/12/14, taking that slot from dev). Sprint ends 2026-09-15; this run is inside it. Head at start: `e044ea1`. No code, no data, no figure and no `docs/NUMBERS.json` entry was touched.*

## 0. What this run is, and what it is not

Two days separate this run from the knowledge base's own writing date (2026-09-04). Two days is not a literature. So the scan below is deliberately narrow and reports **four genuinely new sources** and **one blind spot that was not new at all** — the domestic operational landscape, which no previous sweep had looked at and which turns out to be the most consequential thing found. The ideation section runs the discipline the routine prompt asks for on three candidates and files all three as **P1**, not P0, for a reason stated in §5 that is about the sprint rather than about the ideas.

## 1. Scan channels, and one that failed

| channel | what it returned | status |
|---|---|---|
| (a) alphaXiv connector | 13 ranked items, `published_after 2026-07-01`, recency-weighted. Four of them new to this repository | **worked** |
| (a) Scholar Gateway MCP | **unavailable — the server requires OAuth and this is a non-interactive cloud session.** The author can authorise it in claude.ai connector settings; until then this half of channel (a) does not run | **blocked** |
| (b) arXiv API over WebFetch | three queries (`all:"wildfire spread"`, `abs:evacuation AND abs:wildfire`, `abs:"time-dependent shortest path" OR abs:"time-expanded network"`), each newest-first | **worked** |
| (b) Semantic Scholar Graph API | **HTTP 429 on every attempt**, through WebFetch and through `curl` alike, on two different queries. Not rate-limited by us — the anonymous tier refused the sandbox outright | **failed; UNVERIFIED-by-absence** |
| (c) plain web search, Korean | four queries on 산불/대피/고령자, 산불확산예측 AI, 국립산림과학원, 한국코드페어 | **worked, and it is where the important finding came from** |

⚠ **The Semantic Scholar failure is a real hole in this run and should be said plainly rather than buried.** Channel (b) reduced to arXiv only, so anything published in 2026 in a journal without an arXiv preprint — which is most of the Korean forestry literature, and all of *Forests*, *Fire* and *KJRS* — was reachable this run only through channel (c)'s plain search. The pyrogeography note's open questions (§7) are exactly the kind of thing channel (b) would have settled and none of them moved. A later run should retry; if it 429s again, the routine needs either a key (author decision) or Crossref as the substitute.

## 2. What is new, and what it does to this project's claims

Four sources, each opened at its URL. Nothing below is a paper this routine did not read.

### 2.1 Spatially blocked validation costs ~0.17 AUC, measured on a fire — arXiv:2608.22293

Farajpoor & Narimani, 2026-08-23, <https://arxiv.org/abs/2608.22293> [opened]. **What they did:** modelled structure loss for 9,883 residential buildings in the January 2025 Palisades Fire from satellite predictors. **The metric:** ROC-AUC **0.92 under random cross-validation, 0.75 under 1 km spatial-block validation**, same data, same model. Predictors: building density within 100 m (odds ×4.12 per SD), NDMI 100–300 m (0.52, protective), NDVI 30–100 m (1.74); predictive information concentrated at 100–300 m.

**How it changes or confirms this project's claims.** It **confirms** the LOFO-CV design and gives it, for the first time, an external number for the size of the honest-validation penalty in a wildfire setting. WildfireGuardian's leave-one-fire-out is a stronger blocking than leave-one-1-km-block-out, so the skill it reports is the honest-validation kind. ⚠ It changes **no number here and may never be used to normalise ours**: different task, unit, geography and label. The permitted sentence is 「spatially honest validation is known to cost substantial skill in this domain, and here is a measured instance」. The forbidden sentence is 「so our AUC is fine」.

### 2.2 The condensed time-expanded network — arXiv:2605.00277

Chawla & Sheridan, 2026-04-30, <https://arxiv.org/abs/2605.00277> [opened]. **What they did:** for a network with uniform edge lengths whose capacities change at μ discrete *critical times*, constructed a **condensed time-expanded network** with O(n²μ) nodes and O(μmn) edges whose ordinary max flow equals the max flow over time; O(μ²n³m) with Orlin's algorithm. **The metric:** complexity in μ, not in the length of the horizon.

**How it changes this project's claims.** It names the discretisation principle the project's router half-follows: the parameter that should govern a time expansion is **the number of times the network actually changes**, not the clock. This project's hazard is piecewise-constant with a handful of slice boundaries and its router bins time at 10 minutes — finer than the hazard needs, which is where `docs/routing_limitations.md` §1's `fa_exceeds_budget` misnomer comes from. ⚠ It does **not** license removing the bins: they are also the Dijkstra label's arrival-time bookkeeping. What it licenses is evaluating the *gate* exactly, which is candidate B1 in `ROUTING_FUNDAMENTALS.md` §7.2 and is what WFG-143 screens.

### 2.3 Supported evacuation is a named problem class — arXiv:2608.05413

Moradi, Sauré & Patrick, 2026-08-05, <https://arxiv.org/abs/2608.05413> [opened]. **What they did:** defined *supported evacuation* of people who cannot self-evacuate (hospital patients, long-term-care residents) as a two-stage stochastic program over facility location, fleet sizing and vehicle routing under hard time windows; logic-based Benders decomposition with combinatorial Benders cuts; validated on a community wildfire drill in Roxborough Park, Colorado. **The metric:** improvement in shelter placement, vehicle utilisation and evacuation efficiency against alternative policies; the abstract states no headline number.

**How it changes this project's claims.** It **bounds** them, usefully. The rescue-dispatch layer answers a feasibility question — does a corridor survive long enough to reach this household — inside a problem whose full statement is this two-stage program. Saying that in related work is more accurate *and* more impressive than the current framing, and it explains `docs/dispatch_ordering.md`'s negative ordering result as a result at the easy end of a hard problem. Related-work row for WFG-026.

### 2.4 The domestic operational landscape — and this is the finding

Two systems, neither of which appears anywhere in this repository until today:

- **NIFoS 「AI 기반 산불확산예측시스템」**, user guide published as 연구자료 제1201호 (2026), <https://book.nifos.go.kr/library/10130/contents/7732761> [opened, catalogue only]. An operator console for suppression planning: origin point, fire information, spread prediction, firefighting resources, fuel parameters. A 사이언스타임즈 report of 2026-02-12 gives the agency's own plan figures — 「산불확산예측 정밀도를 기존 대비 약 30% 향상」, 「지형 분석 정밀도를 5ｍ 수준까지」, occurrence accuracy 76 % → 88 % — <https://www.sciencetimes.co.kr/nscvrg/view/menu/249?searchCategory=221&nscvrgSn=261448> [opened].
- **경기도 「민방위 경보 예측모델 (G-DAPS)」**, 경향신문 2026-03-30, <https://www.khan.co.kr/article/202603301116001/> [opened]. Forecasts a fire's route, affected 읍면동, arrival times and alert timing at **30-minute steps**, from KMA forecasts, KFS risk alerts, MOLIT digital-twin data and the audible coverage of 589 civil-defence alert facilities. Trial operation from April 2026. **No accuracy figure is reported.**

**How it changes this project's claims.** It does not weaken a single measured claim, and it changes what the project must be able to *say*. 「어떻게 다릅니까」 has been answered here against academic work; the version a KCF disaster-response judge will ask is against 산림청 and 경기도. The honest differentiator is the **output object** — a suppression-oriented spread footprint at township granularity versus a per-household walk-or-be-rescued decision on public, re-derivable data — and it is **never** accuracy, because the agency numbers are plan statements with no metric definition and this repository has no basis to compare. Written up as the new knowledge note `KOREAN_OPERATIONAL_SYSTEMS.md`; the card is WFG-144.

### 2.5 Read and deliberately not carried further

- **BEACON**, arXiv:2609.03301 (2026-09-03) [opened]: multilingual wildfire evacuation guidance app; routing is a 「polygon-avoidant routing pipeline」 around current fire perimeters; no evaluation reported. Useful only as a citation for what deployed guidance apps actually do — and note that its router is the present-perimeter opponent this repository already argues about.
- **Adaptive robust evacuation planning**, arXiv:2608.04225 (2026-08-04) [abstract]: shelter location + routing + fleet under uncertainty. Recorded in `ROUTING_FUNDAMENTALS.md`; refuge *placement* stays out of scope.
- **RF-informed cellular automaton for wildfire spread**, arXiv:2609.01675 (2026-09-01): already in `RESEARCH_BRIEF_2026-09-03.md`'s source list; nothing to add.
- Scanned and not relevant enough to carry: WildFireGS (arXiv:2608.11100), active-fire segmentation (2609.01392), UAV RGB-IR segmentation (2609.01390), conformal-risk-control papers outside hazard mapping (2608.27124, 2609.03104, 2608.28179).

## 3. Ideation — three candidates, each through `macrothink` then `hate`

Only claims new relative to the literature actually read above. Each survivor is written as a preregistered mini-experiment.

### C1 → **WFG-142**. The honest-validation penalty, stated with an external citation

- **Claim.** The manuscript's related work and the judge Q&A bank should state, with a citation, that spatially blocked validation is known to cost large amounts of skill in wildfire ML, so that this project's LOFO numbers are read as an honest-validation result rather than as a weak one.
- **`macrothink`, three independent reads.** *(i) ML reviewer:* the cited penalty is on a different task, unit and label; used as a calibration it is a category error. *(ii) KCF judge:* 「AUC가 낮은데요」 is a live question with no checkable external answer today; one external instance is a legible defence. *(iii) Statistician:* the only comparison that would settle it is internal — random CV versus LOFO on this project's own data — and that needs a refit, which CHARTER §3 rule 2 forbids before the finals. **Convergence:** this is a related-work-and-defence item, not a claim, and it must carry its own limits in the same sentence.
- **`hate` — one root objection.** *Citing another task's blocking penalty to make our own number feel acceptable is manufactured comfort, and it is precisely the sentence CHARTER §3.5 exists to stop.* **Cheapest test:** grep the repository for an existing random-split arm on `spread_v2`. If one exists, use the internal number and drop the external one entirely. If none exists, the card must say **in its own voice** that this project has not measured the penalty on its own data, and the citation may only establish the direction.
- **Preregistration.** *Data:* none — prose plus one `references.bib` entry, verified at its URL. *Metric:* not a measurement. *Falsified if:* the repository already carries a random-split arm (then the external citation is unnecessary), or if the drafted sentence cannot be written without implying our AUC is normal. *Power at n = 6 fires / 3 regions:* **not applicable, and that is the point** — no estimate is produced, so nothing is under-powered. *Effort:* minutes.

### C2 → **WFG-143**. The bin-quantisation screen, before B1 gets a lap

- **Claim.** The set of canonical Yeongdeok origins whose three-bucket verdict could change if the hazard gate were evaluated at the exact interpolated arrival time instead of the ceil-rounded 10-minute bin is bounded above by the set whose routed arrival time lies within one bin width of a hazard slice boundary — and that upper bound is computable from the committed routing artifact alone, with no re-routing.
- **`macrothink`, three independent reads.** *(i) Algorithms:* Chawla & Sheridan's cTEN says the resolution parameter should be the μ critical times; our bins are finer than the hazard, so quantisation error is pure loss and should be removed. *(ii) Code reality:* the bins are also the label's arrival-time bookkeeping, so they cannot be removed; only the gate can be made exact. *(iii) Paper:* the shippable statement is that the hazard is piecewise-constant with few breakpoints, so an exact gate is available and its effect is measurable. **Convergence:** read (ii) is right and (i) is wrong as stated; the contribution is the exact *gate*, and the cheap screen decides whether it is worth a lap.
- **`hate` — one root objection.** *B1 could burn a lap on a null.* **Cheapest test:** the screen itself — count origins within one bin width of a slice boundary, from the committed artifact, no routing. If it is zero, B1 is dead for the cost of one read and the null is itself a publishable sentence (「bin quantisation cannot change any verdict on this field」).
- **Preregistration.** *Claim:* the upper-bound set is small and non-empty. *Data:* the committed Yeongdeok routing artifact and the canonical field — both in the repository, no re-acquisition, no refit, new filename for the output. *Metric:* count of origins within one bin width of a slice boundary, and the same count split by current bucket. *Expected effect size:* fewer than about 20 of 458, i.e. under ~5 %, on the grounds that slice boundaries are sparse relative to the arrival-time spread. *Power:* this is an enumeration over all 458 origins, not a sample, so there is **no sampling error and no power question** — n = 6 fires and 3 regions do not enter, because the quantity is a property of one committed field. *Falsified if:* the count is zero (B1 dead) or is a large fraction of 458 (then the binning is load-bearing and `routing_limitations.md` §1 understates it, which is a finding). *Effort:* one lap, and probably much less.

### C3 → **WFG-144**. The card for 「산림청도 이미 하고 있는데요」

- **Claim.** The single most likely booth question this repository cannot currently answer is how the project differs from NIFoS's 산불확산예측시스템 and 경기도's G-DAPS, and the answer is the output object, not accuracy.
- **`macrothink`, three independent reads.** *(i) Booth:* five judges, ~5 minutes of Q&A, at least one from the disaster-response side; there is no card and the Q&A bank has no section on deployed domestic systems. *(ii) Science:* those systems are better resourced (5 m terrain against this project's 500 m grid); any novelty claim against them must be about the decision produced, not the forecast. *(iii) KCF rules:* §3 rule 4 forbids pivoting the frame — a Q&A card and a related-work line are squarely inside it. **Convergence:** high value, low risk, judge-facing, no code.
- **`hate` — one root objection.** *The routine could not open the NIFoS document, so every capability figure available is a press restatement of an agency plan; writing 76 %/88 %/30 %/5 m onto a judge-facing card is exactly the failure mode that produced WFG-049 and CHARTER §3 rule 5b.* **Cheapest test:** draft the card without any agency accuracy figure at all and check that it still answers the question. It does — the answer is the output object — so the figures stay in the knowledge note with their agency, date and scope and never reach a card.
- **Preregistration.** *Claim:* not an empirical one; the deliverable is a card and a related-work line. *Data:* the three opened sources in `KOREAN_OPERATIONAL_SYSTEMS.md` §6. *Metric:* none. *Falsified if:* a card can be written that compares accuracy honestly from public information — it cannot, and if a later lap believes otherwise it must produce the metric definition first. *Effort:* hours. *Sequencing constraint:* land it **after** the WFG-134/WFG-130 printables rebuild, or the printed 17 pages go stale a fourth time; WFG-140's freshness gate then covers the re-rebuild.

**Parked, with the objection that parked them:** two candidates went to `IDEAS_PARKED.md` — adopting a max-flow/capacity evacuation formulation, and a multilingual guidance layer.

## 4. Competitive and fair landscape

- **KCF.** The 2026 한국코드페어 finals are in Gwangju in October, as the charter records; the public pages (<https://www.kcf.or.kr/swcom>, <https://www.kcf.or.kr/notice>) surfaced no new rule or schedule change and no published finalist list. Nothing to act on.
- **ISEF 2026.** The Society for Science awards pages surfaced one wildfire ML project <!-- forbidden-ok: Chen --> — Angela Chen, 「Assessing and Predicting Wildfire Severity in California Based on Relationships Between Wildfires and Drought Using Machine Learning」, a NOAA Special Award (<https://www.noaa.gov/office-education/outreach-communication/international-science-and-engineering-fair/special-award-winners>) — and one wildfire-adjacent engineering project on firefighter VOC filtration. **No ISEF 2026 project on wildfire evacuation routing was found.** That is a weak negative (the finalist list is large and only awarded projects surface in search), but it is the second sweep to return nothing in this exact niche.
- **Korean news a judge might have read this month.** 국립산림과학원 published 「2026 산불 제대로 알기」 on 2026-03-13, a public Q&A booklet covering spread principles, prevention and **국민 대피 요령** (<https://www.korea.kr/briefing/pressReleaseView.do?newsId=156748710&call_from=rsslink>) — the same audience this project's 이장 A4 sheet serves, from the agency itself. Worth one sentence at the booth: the booklet tells a citizen what to do in general; this project tells a specific household which way to walk. Separately, Greenpeace Korea reported in 2026 on flooding in 안동 striking the same households displaced by the 2025 fires (<https://www.greenpeace.org/korea/update/38057/blog-ce-climate-disaster-site-flooded/>) — context, not evidence, and not to be cited as a project claim.
- **The Greenpeace 2025 영남 산불 실태조사 최종보고서 is already registered here** (`docs/evidence/greenpeace_2026_survey.md`, `data/processed/evidence/greenpeace_2026_survey.json`). Re-checked this run; nothing new.

## 5. Backlog rows proposed — three, all P1, and why not P0

**WFG-142** (paper/KCF, minutes), **WFG-143** (science, one lap), **WFG-144** (KCF, hours). Full cells in `docs/auto/BACKLOG.md`.

⚠ **All three are P1 on purpose, and this is a deliberate answer to NH-038 rather than an oversight.** Critic #28's second finding is that the `fix-before-next-row` mechanism has taken the last three dev laps while the booth kit has not moved since `3e92b69` and `KCF_READINESS.md` has read 4 of 11 for five consecutive critic laps. A research lap that responds to that by filing three new P0 rows would be adding to exactly the queue that is starving. WFG-144 is the one with a genuine claim on P0 — it is judge-facing and it is a question with no answer — and it is *still* P1, because its sequencing constraint says it must land after the printables rebuild anyway. **If the author disagrees, the row to promote is WFG-144 and nothing else.**

## 6. Escalation

**NH-039** (DECISION/ASK, LOW severity): the NIFoS user guide is an ~18 MB PDF this sandbox did not retrieve. The author can download it from the NIFoS library and drop it under `data/raw/evidence/` so a lap can register its sha256 and read what model class, resolution and inputs the national system actually uses. Until then `KOREAN_OPERATIONAL_SYSTEMS.md` §3 is the honest but uninformed version.

Also recorded, not escalated: the Scholar Gateway MCP requires OAuth and cannot be authorised from a non-interactive cloud session, so half of channel (a) did not run; and Semantic Scholar's anonymous API returned 429 to this sandbox on every attempt.

## 7. What this run did not do

No code, no data, no figure, no `docs/NUMBERS.json` entry. No number from any source above entered `README.md`, the manuscript or the registry; every figure quoted stays in its knowledge note with its agency, date and scope (CHARTER §13). `docs/auto/DIRECTION.md` was rewritten (§14) and **no P0 row was moved below a non-P0 row**; the only reorder is the three new rows entering at the end of the P1 block, which is not a reorder of anything existing.
