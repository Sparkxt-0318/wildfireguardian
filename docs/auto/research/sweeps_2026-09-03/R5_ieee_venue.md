# R5 — IEEE publication plan for WildfireGuardian

Written 2026-09-03. Inputs: `README.md`, `docs/MODEL_CARD.md`, `docs/HANDOFF_ROUND3.md` §1–§2-A, `docs/results_rescue_draft.md`, `docs/multi_region.md`, `docs/NUMBERS.json` (260 entries at HEAD `25f1e14`), the KCF 운영요강 PDF (pp. 5–11, 12–24 grepped), and the web sources listed at the end. Nothing under the repo was modified.

**Bottom line.** The paper is publishable in an IEEE venue, but not as the paper the repo currently implies. The defensible contribution is not "AUC 0.89" (six fires, one fold with 8 positives, ERA5 at 28 km, recall 0.14 at the operating threshold) and it is not "our dispatch ordering" (it loses 59.7 % of head-to-heads and 0/180 at the shipped 75-min window). It is the **coupling**: a calibrated next-overpass ignition surface consumed by a time-expanded household-level walk/rescue router, evaluated with paired contrasts on three real Korean fires under one parameter set, with every reported number machine-verified against a committed artifact. That framing fits **IEEE Access** (first choice) or **IEEE OJ-ITS** (second), with a 4-page **IGARSS 2027** paper on the spread-model/DEM-defect story as a low-cost companion. Do not submit anything before the KCF awards (Dec 2026); post a TechRxiv preprint the week after; submit IGARSS by 11 Jan 2027 and the journal in Jan–Feb 2027 so that it is at least "under review" at ISEF (8–14 May 2027, Los Angeles). Three experiments are missing for acceptance (§4.6), of which the coupling ablation (forecast vs. static-perimeter vs. oracle) is the one a reviewer will reject without.

---

## 1. What the repo actually supports (the evidence discipline a reviewer will see)

Facts a paper can lean on, each traceable to a committed artifact and a `NUMBERS.json` entry:

| Claim | Committed value | Artifact | Caveat that must travel with it |
|---|---|---|---|
| Next-overpass ignition model, 6 Korean fires, LOFO-CV | mean-of-folds ROC-AUC **0.890 ± 0.107** (range 0.682–0.974); pooled **0.905** [0.901, 0.909] | `spread_v2_lofo.json`, `auc_intervals.json` | folds are 208.9× unequal in size; `gangneung_2023` has ~8 positives; pooled is the row-weighted primary; DEM correction moves mean +0.0048 / pooled −0.0017 (`spread_v2_lofo_dem_corrected.json`) |
| Controlled ML baselines (same 16 features, folds, seed) | RF 0.914 ± 0.044 / pooled 0.896; LR 0.903 ± 0.060 / 0.826; HGB 0.894 ± 0.092 / 0.904 | `ml_baselines.json` | RF beats HGB on mean-of-folds; calibration is not a GBM advantage (Brier/ECE HGB 0.0183/0.0086 vs RF 0.0174/0.0068, `calibration_metrics.json`) |
| Operating-point honesty | threshold 0.3: recall 0.138, precision 0.308, F1 0.190 | `oof_classification_metrics.json` | threshold is a config default, never tuned |
| Forward-simulated footprint | IoU ≈ 0.40 (3–12 h) vs Rothermel surface model ≈ 0.09 | `ROUTING_INTEGRATION_REPORT.md`, `yeongdeok_forward_sim.json` | envelope bias flips sign across regions (7.34× over / 0.07× under / 0.45× under) |
| Coupled routing, canonical Yeongdeok field | 458 origins → 414 both-safe / **42 future-aware-only** / 2 no-safe-route (9.17 %) | `real_roads_real_hazard_canonical.json` | walk bbox covers **32.6 %** of the predicted core; decision closed, reported as a limit |
| Three regions, identical parameters | 의성·안동 368 → 263/91/12/2 (24.73 %, coverage 99.2 %, 0 depots in OSM); 울진·삼척 393 → 377/3/10/3 (0.76 %, 81.5 %) | `multi_region_comparison.json` | n = 3, three covariates co-move — no ranking |
| Walk budget sweep w(t) | 56.55 / 40.17 / 28.38 / 22.27 / 9.61 % at 30/60/90/120/600 min (5.89×) | `objective_budget_canonical.json` | future-aware router never enters hazard (`both_enter` = 0 at every budget) |
| Terrain on OSM edges | +26.6 % walk time, mean \|slope\| 8.18 %, asymmetry 20.0 %; routes change for 33–48 % of origins, verdicts essentially do not | `slope_sweep_canonical.json` | substantive null, not literal null (413/42/3, 414/42/2, 415/41/2) |
| Network sensitivity | 0.047 % walk-node change → binary verdict moves 33 % (24→32); paired exposure contrast moves 0.56 pp | `network_drift_experiment.json` | the methodological finding of the project: report contrasts, not counts |
| Dispatch ordering (negative result) | wins 3.6 %, ties 36.7 %, loses 59.7 % over 270 configs; **0/180 at W = 75 min** | `dispatch_ordering_comparison.json` | contribution restated as *computing* `ingress_survival_time_min`, not sorting by it |
| Live path | detection → dispatch list 9.961 s; 458-origin scan 10.9 s after hoisting the time-expanded table | `live_pipeline.md`, `service_layer.md` | one machine; A4 rendering excluded |
| Evidence registry | 260 registered numbers, re-derived by `make verify`; forbidden-string gate; DEM sea-fill (−497 m, 49 % of raster) and reverted-run artifact both caught by it | `NUMBERS.json`, `Makefile` | 16 Round-2 values are verified-but-unreproducible (OSM graph overwritten 2026-07-24) |

Withdrawn and must stay withdrawn in the paper: "severity dominates wind direction ~44×"; "quasi-static core"; any bare "58 % need a rescuer"; any 439-series value presented beside 458-series values without saying they are different pipelines. Also: `days_since_rain` is importance-rank 1 and *removing it raises* mean-of-folds AUC by +0.027 — a paper must report that, it is exactly the kind of thing a reviewer finds.

What this means for venue choice: the ML result alone is a small-n regional study that TGRS/T-ITS reviewers would reject on novelty; the *systems + evidence-discipline* story is what is publishable, and it needs a venue that accepts applied, multidisciplinary, negative-result-tolerant work.

---

## 2. Venues, ranked

Legend: APC/OPC figures are from the IEEE 2026 APC list PDF unless noted; IFs are the latest publicly quoted (JCR year noted where the source gave it, else UNVERIFIED as to year).

### Rank 1 — IEEE Access (journal, fully OA)
- **Scope fit: high.** Multidisciplinary, explicitly welcomes applied/systems papers and interdisciplinary work; the coupling + evidence-registry narrative has no single-society home, which is what Access is for.
- **Impact/acceptance:** IF 4.2 (Q2) per journalmetrics/manusights; IEEE's own stated acceptance language is "about 20 %" (manusights quoting IEEE Access author pages; a 27 % figure also circulates — treat 20–27 % as the range). ~30-day median first decision; full cycle with revision 2–4 months.
- **Length:** no page limit; strongly recommended < 20 pages; no overlength charges.
- **Cost:** APC **US$2,160** + tax; 5 % off for IEEE members, 20 % off for IEEE + Society members (a student IEEE + GRSS/ITSS membership costs far less than the 15 % it saves).
- **Timeline:** rolling; submit Jan–Feb 2027 → first decision Feb–Mar → likely "major revision" at ISEF time, plausibly accepted by June 2027.
- **Student-authored:** graduate-student first authors are the norm; high-school first authors exist but are rare — I could not verify a specific 2025 example (UNVERIFIED). IEEE has no affiliation or degree requirement; ORCID is required at submission.
- **Risk:** Access's reputation is mixed in some circles; for an ISEF judge or an IEEE reader it is still a peer-reviewed IEEE journal with a DOI, which is all the project needs.

### Rank 2 — IEEE Open Journal of Intelligent Transportation Systems (OJ-ITS, fully OA)
- **Fit: medium-high.** Evacuation routing is core ITS; pedestrian/household routing plus rescue-vehicle ingress survivability is a genuine ITS problem; the ML forecast is the input, not the contribution. ITS reviewers will ask for a comparison with an established evacuation formulation (Borgwardt et al. 2024/25 max-flow on time-expanded networks is the obvious one — see §4.6 E3).
- **Impact:** newer journal (2020–); IF not verified here (UNVERIFIED). Same society as T-ITS (IF 9.1, JCR 2025).
- **Length/cost:** APC **US$2,160** (2026 list; earlier years were $1,850–$1,950). Page limit per ITSS guidelines — UNVERIFIED for OJ-ITS specifically.
- **Timeline:** rolling; ITSS journals quote ~3 months to first decision.
- **Student-authored:** common at graduate level.

### Rank 3 — IEEE JSTARS (fully OA)
- **Fit: medium.** "Applied papers on remote sensing … derived information such as forecast data … to address science and engineering issues" fits the FIRMS/ERA5/DEM ignition model and the DEM-defect finding; the routing half is outside scope and would be compressed to an "application" section.
- **Impact:** IF ≈ 5.3 (bioxbio; year UNVERIFIED).
- **Cost:** APC **US$1,800** for submissions on/after 1 Jan 2025 (GRSS page); the 2026 IEEE list marks JSTARS "Full" with a multi-year subsidised price moving toward the standard fee — assume $1,800–$2,160.
- **Length:** no explicit limit on the GRSS page.
- **Best use:** if reviewers at Access/OJ-ITS insist the ML part is too thin, split: JSTARS gets the model + DEM/weather-dependency methodology; the routing paper cites it.

### Rank 4 — IGARSS 2027 (conference, Reykjavík, 11–16 July 2027)
- **Deadline: 11 January 2027** (portal opens 10 Nov 2026; CFP text says 10 Jan in one place, 11 Jan in the dates table — assume 10 Jan to be safe). Notification 12 Mar 2027; final paper 30 Apr 2027.
- **Format:** 4-page full paper (IEEE Xplore) — eligible for the **Student Paper Competition** (also due 11 Jan; needs advisor attestation). Also accepts 400–600-word abstracts (not indexed).
- **Fit: high for the spread-model story** ("next-overpass ignition probability from FIRMS + ERA5 + DEM with LOFO-CV; a DEM sea-fill defect that trained every fold; weather-window artefacts in `days_since_rain`"). Routing gets one figure.
- **Cost:** registration + Iceland travel (≈ US$2.5–4 k all-in, UNVERIFIED); travel-support applications due 11 Jan 2027.
- **Student-authored:** very common; a dedicated student competition.
- **Rules note:** the student competition is judged in July 2027, after both KCF awards and ISEF — no "타 대회 수상" exposure.

### Rank 5 — IEEE Transactions on Intelligent Transportation Systems (T-ITS, hybrid)
- **Fit: medium; bar: high.** IF 9.1 (JCR 2025), CiteScore 17.8. Regular papers 10 pages, US$175/page overlength; hybrid OA US$2,800 (optional). ~3 months to first decision.
- **Why not first:** T-ITS expects methodological novelty in the optimisation/traffic model; a 458-origin pedestrian scan with a shortest-path router will be judged against network-flow evacuation literature and lose unless E3 (§4.6) is done well. Stretch target after a first paper exists.

### Rank 6 — IEEE Transactions on Computational Social Systems (TCSS, hybrid)
- **Fit: medium.** Vulnerable-population evacuation and rescue prioritisation is "modeling social systems computationally"; the elderly-household framing is the hook. IF 7.27 (2024, per search snippet; UNVERIFIED for 2025). Regular papers ~10 pages, US$175/page overlength capped at 2 extra pages; review target "approximately ten weeks"; OA option US$2,150 (SMC page) / US$2,800 (IEEE list — discrepancy, cite the SMC page).
- **Risk:** reviewers will want behavioural/social modelling (immobility is a random placeholder in the 439 series — a real weakness here).

### Rank 7 — IEEE Geoscience and Remote Sensing Letters (GRSL, hybrid)
- **Fit: medium (model only).** 5-page maximum; pages 4–5 US$230/page (US$200 GRSS member) — **fully waived if the corresponding author is a GRSS member** (since 1 June 2025). ~30-day turnaround; IF 4.4 (2025 per journalmetrics).
- **Use:** a letter on "LOFO next-overpass ignition probability on six Korean fires + the DEM-defect/weather-window audit" if IGARSS is not pursued or as its journal extension.

### Rank 8 — IEEE SMC 2027 (conference, Ho Chi Minh City, 7–10 Oct 2027)
- Deadline **15 April 2027**; systems/human-machine tracks fit the operator-console + evidence-gate story. Mid-tier; cheap travel from Shanghai/Korea. Good fallback if IGARSS rejects.

### Rank 9 — IEEE GHTC 2027 (Global Humanitarian Technology Conference)
- 2026 edition: full papers 4–8 pages, deadline was 13 May 2026, conference 7–10 Oct 2026 Boulder; poster abstracts closed 31 Aug 2026. 2027 CFP not yet posted; expect a ~May 2027 deadline, ~Oct 2027 US venue. Theme "Technologies in Context" fits rural-elderly evacuation exactly; low bar; student poster competition. **Do not** enter the 2026 student poster competition even if late abstracts were accepted — it would be a competition award before the KCF ceremony.

### Rank 10 — IEEE ISC2 2027 (Smart Cities)
- 2026: track papers due 15 May 2026, conference 27–30 Oct 2026 Porto. 2027 not announced. Fit is weak (rural, not city); only as a last resort.

### Not recommended
- **IEEE TGRS** (IF 9.4, OPC threshold 10 pages at US$230/page from 1 Jan 2026): a six-fire, ERA5-0.25° model with recall 0.14 at threshold is not a TGRS paper.
- **IEEE Sensors Journal** (8-page OPC threshold, US$175/page): scope is sensor devices/physics; nothing in the project is a sensor contribution.
- **IEEE OJ-CS** (APC US$2,160, 12 pages): possible home for a pure "auditable evidence registry for computational science" paper, but that is a different paper.
- **IEEE BigData 2026** (Phoenix, 14–17 Dec 2026): main deadline 21 Aug 2026 has passed; **IEEE ICDM 2026** workshops (Shenyang, Nov 2026): workshop papers closed 20 Aug 2026. Neither is worth chasing for 2026; BigData 2027 deadline will be ~Aug 2027, after the ISEF window.

### Summary table

| # | Venue | Type | Fit | Deadline / cadence | Length | Cost (USD) | First decision |
|---|---|---|---|---|---|---|---|
| 1 | IEEE Access | journal, OA | high | rolling | none (< 20 rec.) | 2,160 (−5/−20 %) | ~30 d |
| 2 | IEEE OJ-ITS | journal, OA | med-high | rolling | UNVERIFIED | 2,160 | ~3 mo |
| 3 | IEEE JSTARS | journal, OA | medium | rolling | none stated | 1,800–2,160 | UNVERIFIED |
| 4 | IGARSS 2027 | conf | high (model) | **11 Jan 2027** | 4 pp | reg + travel | 12 Mar 2027 |
| 5 | IEEE T-ITS | journal, hybrid | medium | rolling | 10 pp (+175/pg) | 0 (OA 2,800) | ~3 mo |
| 6 | IEEE TCSS | journal, hybrid | medium | rolling | 10 pp (+175/pg, cap 2) | 0 (OA 2,150) | ~10 wk |
| 7 | IEEE GRSL | letter, hybrid | medium (model) | rolling | 5 pp | 0 if GRSS member | ~30 d |
| 8 | IEEE SMC 2027 | conf | medium | 15 Apr 2027 | 6 pp (typ.) | reg + travel | ~Jun 2027 |
| 9 | IEEE GHTC 2027 | conf | high (humanitarian) | ~May 2027 (UNVERIFIED) | 4–8 pp | reg + travel | ~Jul 2027 |
| 10 | IEEE ISC2 2027 | conf | weak | ~May 2027 (UNVERIFIED) | 6 pp (typ.) | reg + travel | ~Jul 2027 |

---

## 3. Rules interplay and timing

### 3.1 KCF 운영요강 (2026, 제8회) — what it actually says
Page 5, 개요:
> ※ 한국코드페어 시상식(12월 예정) 이전 동일 작품으로 타 대회 수상 시 대회 참가가 불가능하며, 참가 이후 해당 사실이 확인될 경우 모든 참가, 선정, 수상 사실 취소 및 상장 회수

Page 18 (붙임, 행동강령 area, grep hit): "…소속된 교육청 등재 교내 대회 수상작은 허가)" — school-internal competition awards are exempted.

Page 9, 작품개선: functional additions/changes are free "첫 제출 당시의 작품 목적, 주제에 반하지 않는 범위 내에서"; and 제출자료: "개인정보 제외한 제출된 모든 자료는 주관기관이 대중에 공개될 수 있음" — the organiser itself may publish the materials, so there is no confidentiality obligation that a preprint would violate.

Reading:
- A journal article or a conference paper is **not** "타 대회 수상". The prohibited thing is a *competition award* on the same work before the December ceremony. Nothing in pp. 5–24 mentions 논문/학회/출판/게재 (grep confirmed).
- The exposure is **conference student-paper / best-paper / poster competitions** decided before December 2026 (e.g. GHTC 2026's student poster competition, 7–10 Oct 2026). Avoid any such contest until after the ceremony. IGARSS 2027's student competition (July 2027) and any 2027 event are safe.
- Publishing a paper does not conflict with the "same purpose/theme" rule as long as the paper's stated purpose matches 서식1/2 (spread prediction → rescue priority and safe routes for mobility-impaired rural residents). It does.
- Conservative recommendation anyway: **no public preprint and no submission before the ceremony.** The benefit of being two weeks earlier is nil; the cost of a judge or a rival reading a rule creatively is not.

### 3.2 ISEF (Regeneron ISEF 2027, Los Angeles, 8–14 May 2027)
- Rules for All Projects: judged only on data collection "over 12 continuous months beginning no earlier than January 2026 and ending May 2027"; nothing older than 18 months before the fair. The repo's work is 2026 — fine. Any 2025 work would need Form 7 (continuation).
- Prior publication: neither the International Rules page, the ISEF FAQ, nor the Rules FAQ prohibits presenting work that has been published or submitted; the Educator Guide only discusses continuation (Form 7), IP (patents), and copyrighted instruments. A published paper is therefore allowed; it must simply be disclosed in the research plan / Form 1A narrative and in the abstract's "prior work" sense, and at the booth published papers may be shown only inside the lab notebook / project data book (display-rule snippet; exact wording UNVERIFIED — read the Display & Safety Rules before the fair).
- Team rule: "Once a project has competed in a science fair at any level, team membership cannot change." A paper with adult co-authors (mentor, firefighter consultant) is fine, but the ISEF project stays individual and the research plan must "delineate what parts of the project were done by the student and which parts by the mentor". Keep the student as sole first author and write the contribution statement to match the ISEF research plan.
- Selection into the Korea delegation: 운영요강 p. 11 — 은상 이상 → 면접 → selection (parent brief says 5 teams; a namu-wiki summary of the 2026 notice says "동상 이상 7팀" for the 2026 cycle — conflicting, UNVERIFIED; the kcf.or.kr notice pages returned 404 to me). Interview date for the 2027 cycle: UNVERIFIED; the 2026 cycle's notice existed on kcf.or.kr around Jan 2026, so plan for **Jan–Feb 2027**.

### 3.3 IEEE preprint policy
IEEE explicitly permits posting to arXiv or TechRxiv before submission and does not treat it as prior publication; after acceptance the preprint must credit IEEE as copyright holder and add the DOI. TechRxiv is free, IEEE-run, gives a DOI, and its moderation is a non-technical screen; arXiv needs an endorser for a first-time submitter in cs.* — TechRxiv is the frictionless path for a student.

### 3.4 Recommended timeline
| When | Action |
|---|---|
| now → 18 Oct 2026 | No paper work. Only: cut a tagged release and mint a Zenodo DOI (helps 제출 자료 20 pts too). |
| 19 Oct → 30 Nov 2026 | Run E1–E3 (§4.6) in the autonomous loop; draft the journal manuscript from the skeleton below; draft the 4-page IGARSS paper. |
| KCF awards ceremony (Dec 2026, date TBA) | Wait. |
| ceremony + 1 week | Post the TechRxiv preprint (journal version). Register ORCID. Join IEEE + one society (GRSS or ITSS) as a student member for the APC discount and GRSL waiver. |
| by 10 Jan 2027 | Submit IGARSS 2027 full paper + Student Paper Competition + travel-support application. |
| Jan–Feb 2027 | Submit to IEEE Access (or OJ-ITS if E3 came out well). |
| Jan–Feb 2027 | ISEF Korea selection interview: present the preprint DOI and "submitted to IEEE Access / IGARSS". |
| Mar 2027 | IGARSS notification (12 Mar); Access first decision likely in hand. |
| 8–14 May 2027 | ISEF: paper is "under revision" or "accepted" — disclose in Form 1A/research plan; put the preprint in the data book. |
| 11–16 Jul 2027 | IGARSS Reykjavík (if accepted and funded). |

---

## 4. Paper skeleton (IEEE two-column, target 12–14 pages for Access; 4 pages for IGARSS)

### 4.1 Title options
1. *Coupling Next-Overpass Wildfire Ignition Forecasts to Household-Level Evacuation and Rescue Routing: A Three-Region Korean Study with an Auditable Evidence Registry*
2. *Forecast-Aware Walking Evacuation and Rescue Ingress for Rural Elderly Residents: Paired-Contrast Evaluation on Three Korean Wildfires*
3. *When the Route Must Know Where the Fire Will Be: Satellite-Driven Ignition Probability as an Input to Time-Expanded Evacuation Routing* (Access-style)
4. IGARSS 4-pager: *Leave-One-Fire-Out Next-Overpass Ignition Probability from FIRMS, ERA5 and SRTM on Six Korean Wildfires — and What a DEM Defect Taught Every Fold*

### 4.2 Abstract (≈250 words, committed numbers only)
> Rural elderly residents die in Korean spring wildfires because the fire reaches them before a route or a rescuer does. We couple a data-driven, per-cell ignition-probability model to household-level evacuation and rescue routing and evaluate the coupling, not the components, with paired contrasts. The model, a gradient-boosted classifier on 16 features from NASA FIRMS active-fire detections, ERA5 reanalysis and SRTM terrain, predicts whether a 500 m cell ignites by the next satellite overpass. Under leave-one-fire-out cross-validation on six Korean fires (151,904 cells, 1.97 % positive) it reaches a pooled out-of-fold ROC-AUC of 0.905 (95 % CI 0.901–0.909) and a mean-of-folds AUC of 0.890 ± 0.107; a random-forest baseline is statistically indistinguishable, and at the operating threshold recall is only 0.138, so the surface is a calibrated risk ranking (Brier 0.018), not a perimeter. That ranking is consumed by a time-expanded router over OpenStreetMap walking and driving networks that forbids entering cells predicted to have ignited before arrival and computes, per household, the time until every vehicle ingress corridor closes. Applied with one parameter set to three fires, 42 of 458 scanned Yeongdeok origins, 91 of 368 in Uiseong–Andong and 3 of 393 in Uljin–Samcheok reach a refuge only when the router is forecast-aware; walk-failure rises 5.9× as the time budget tightens from 600 to 30 minutes; terrain changes which route is walked but rarely whether safety is reached; and a 0.05 % change in the road graph moves binary verdicts by 33 % while paired exposure contrasts move by 0.6 percentage points. A deadline-sorted dispatch order, an initial contribution, is shown to lose to nearest-first under the operational window and is reported as a negative result. All 260 reported quantities are re-derived from committed artifacts by a verification gate that also caught a DEM defect present in every training fold.

(Word count ≈ 300; trim the sentence on terrain for a hard 250 limit.)

### 4.3 Section outline
1. **Introduction** — the 2025 의성→영덕 event (27 deaths, 8 in Yeongdeok, mostly 60–80s; cite press + 서울환경연합); the gap: spread forecasts and evacuation models exist separately, pedestrian/household-level and rescue-ingress coupling on real fires does not; contributions (4 bullets, incl. the negative result and the evidence registry).
2. **Related work** — (a) data-driven spread: NDWS/WildfireSpreadTS-style next-day models, and why their PR-AUC is not comparable (label, grid, prevalence — MODEL_CARD "read this before comparing"); (b) evacuation: Cova et al. protective actions, WUI-NITY, agent-based frameworks, Borgwardt et al. time-expanded max-flow with wildfire shapefiles (arXiv 2410.14500), RESCUE (ICDCN 2026) stochastic edge costs; (c) reproducibility/evidence registries in computational science. Position: household-level *walking* + rescue-vehicle ingress survivability on a *forecast* surface, evaluated by paired contrast, is the gap.
3. **Data** — six fires, FIRMS VIIRS/MODIS, ERA5 0.25°, SRTM, ESA WorldCover, OSM (ODbL); acquisition manifests; the DEM sea-fill defect (−497 m, 49 % of raster) and its measured effect (+0.0048 / −0.0017); the 2026-07-24 graph loss and why 16 numbers are verified-but-unreproducible.
4. **Ignition model** — label (next overpass, ≥ 90-min gate), 16 features, HistGradientBoosting, LOFO protocol, fold-size imbalance (208.9×), DeLong CIs, baselines, calibration, operating-point metrics, permutation importance with the `days_since_rain` window artefact; forward simulation and footprint IoU with the sign-flipping envelope bias.
5. **Coupled routing** — time-expanded hazard table (pure function of network × field × departure × budget, built once per scan); walk router with future-aware constraint; rescue layer: drive network, depot loaders, `ingress_survival_time_min`; buckets (both-safe / FA-only / no-safe / over-budget); slope on edges (60 m sampling); parameters from `config/default.yaml`.
6. **Evaluation design** — paired contrasts as the primary estimand; why absolute rates carry the 32.6 % coverage caveat; three regions, one parameter set; sensitivity axes (budget, slope spacing, objective, network drift, forecast spatial error 125–530 m, dilation 122 m).
7. **Results** — Tables II–IV, Figs. 3–6; the dispatch-ordering negative result; the shelter-density finding (Session 22: "one refuge saves 20 of 24; two save all" — commit `25f1e14`; verify against its artifact before use).
8. **Operational path** — FIRMS NRT trigger → routing → SMS/A4/broadcast drafts; 9.961 s detection→list; approval-gated delivery; EXIF-coordinate intake; offline console. Keep to one page; it is evidence of feasibility, not a contribution.
9. **Evidence registry** — `NUMBERS.json` schema, `make verify`, forbidden-string gate, region-literal gate, gate-behind-pipe failure mode; what it caught (DEM, reverted-run artifact, three region literals). Half a page + one figure.
10. **Limitations** — ERA5 wind resolution (양강지풍 unresolved), n = 6 fires / n = 3 regions, overpass cadence (hours), coverage 32.6 %, immobility placeholder in the 439 series, OSM depot completeness (0 in 919 km²), no field validation, not operational.
11. **Conclusion** + Data/Code availability (Zenodo DOI) + Author contributions (student vs. mentor, matching ISEF Form 1A).

### 4.4 Figures and tables (8) and the artifacts that feed them
| # | Content | Feeds from |
|---|---|---|
| Fig. 1 | System diagram FIRMS → state layers → P(ignite) → time-expanded router → deliverables, with the verification gate drawn as a layer | `docs/architecture.md`, README block diagram (redraw as vector) |
| Fig. 2 | Per-fire LOFO ROC-AUC with DeLong CIs + baseline overlay + fold-size bars | `spread_v2_lofo_auc.png` (regenerate), `auc_intervals.json`, `ml_baselines.json`, `fold_sizes.json` |
| Fig. 3 | Reliability diagram + operating-point PR curve | `calibration_reliability.png`, `oof_classification_metrics.json` |
| Fig. 4 | Canonical Yeongdeok field, five time slices, with one fire-blind vs future-aware route pair | `routing_demo_canonical.npz`, `routing_hazard_sequence.png`, `route_away_from_front.png` |
| Fig. 5 | Budget sweep w(t) and slope-spacing bucket movement (two panels) | `objective_budget_canonical.json`, `slope_sweep_canonical.json` |
| Fig. 6 | Dispatch-ordering head-to-head heat map (4 arms × windows × teams) | `dispatch_ordering_comparison.json`, `ordering_boundary.png` |
| Table I | Fires, dates, rows, positives, weather completeness, DEM status | `spread_v2_lofo.json`, `data_provenance/` manifests |
| Table II | Model comparison: HGB / RF / LR — mean-of-folds, pooled, far-band, Brier, ECE, with DEM-corrected column | `ml_baselines.json`, `calibration_metrics.json`, `spread_v2_lofo_dem_corrected.json` |
| Table III | Three-region routing partition with coverage, envelope area, road/node density, depots (both denominators) | `multi_region_comparison.json` |
| Table IV | Sensitivity ledger: network drift, forecast shift, dilation, slope, objective — effect on verdicts vs. on paired contrasts | `network_drift_experiment.json`, `forecast_robustness.json`, `dilation_perturbation.json`, `routing_objective_experiment.json` |
| (Supp.) | Registry excerpt: 10 rows of `NUMBERS.json` with derivation and caveat | `docs/NUMBERS.json` |

### 4.5 IGARSS 4-page cut
Intro ½ p; data + DEM defect ¾ p; model + LOFO + baselines + `days_since_rain` artefact 1½ p (Fig. 2, Table II); one routing figure as "application" ½ p; limitations/conclusion ¼ p; refs.

### 4.6 The three experiments still missing for acceptance
**E1 — Coupling ablation (mandatory).** Today the only contrast is fire-blind vs. forecast-aware. A reviewer's first question is "what does the *learned forecast* buy over a trivial one?" Run the identical 3-region scan on: (a) fire-blind; (b) static current perimeter + fixed buffer (500 m, 1 km, 2 km); (c) persistence (last two overpasses extrapolated); (d) Rothermel surface field (already in the tree); (e) `spread_v2` canonical; (f) hindsight oracle (actual later FIRMS detections). Report FA-only and no-safe counts and paired exposure per arm. If (e) does not beat (b) and (c), the paper's thesis changes — better to know now. *Effort: 2–4 days* (all fields except (c) and (f) exist or are one script; runners take ~25 s/arm/region).

**E2 — Uncertainty propagation into routing decisions.** Retrain the model under 20 seeds (and a LOFO-bootstrap of fires), re-simulate the field for each, re-route, and report the distribution of the 42/91/3 counts and of per-origin bucket stability. The existing forecast-robustness (125–530 m) and dilation (122 m) experiments were on the synthetic/reverted field; redo them on the canonical field for all three regions. This converts "42 of 458" into "42 (IQR a–b)". *Effort: 3–5 days compute-bound* (20 seeds × 3 regions × ~25 s routing + simulation ~minutes each).

**E3 — External comparison for the routing layer.** Implement Borgwardt et al.'s time-expanded max-flow (NetworkX, public code) on the same OSM graph and hazard slices and compare: coverage of origins reaching a refuge, exposure, run time, and — the project's differentiator — whether it can express per-household rescue-ingress closure at all. Without this, OJ-ITS/T-ITS reviewers will call the router "Dijkstra with a mask". *Effort: 1–2 weeks.*

Optional but cheap **E4 — Wind-resolution ablation**: replace ERA5 wind with KMA LDAPS (1.5 km) or ERA5-Land (0.1°) for `wind_alignment` on the two 2025 fires and re-run LOFO; this is the only honest way to close the withdrawn severity-vs-direction claim. *Effort: 1–3 weeks*, dominated by KMA API acquisition and regridding.

### 4.7 Reproducibility package (what the "Data and Code Availability" paragraph must point at)
- **Code:** tagged release (e.g. `paper-v1`) of `Sparkxt-0318/wildfireguardian`, MIT licence, `CITATION.cff`, `pyproject.toml`/`requirements.txt` pinned, `docs/ENVIRONMENT.md`; `make verify` and `make all-checks` documented as the reproduction entry point; the registry `config_hash` recorded in the paper.
- **DOI:** enable the GitHub–Zenodo integration (public repo, licence present, create a Release → Zenodo mints a version DOI + concept DOI). Cite the concept DOI in the paper, the version DOI in the supplement.
- **Data manifests:** `docs/data_provenance/` (6 fire manifests, acquisition logs) with SHA-256 of every raw file (FIRMS CSVs, ERA5 NetCDF, SRTM tiles, WorldCover tiles, Overpass responses); licences: FIRMS (NASA, open), ERA5 (Copernicus licence — redistribution with attribution allowed), OSM (ODbL — share-alike on derived graph snapshots), WorldCover (CC BY 4.0).
- **Frozen intermediate artifacts** (these are what the 2026-07-24 loss shows you cannot regenerate): the OSM graph snapshots for all three regions, `routing_demo_canonical.npz`, `hazard_*.npz`, the LOFO OOF prediction CSVs, `real_roads_real_hazard_*`, `multi_region_comparison.json`, `dispatch_ordering_comparison.json`. Deposit them in the Zenodo record (size UNVERIFIED — check < 50 GB Zenodo limit; expect a few hundred MB).
- **Model card** (`docs/MODEL_CARD.md`) shipped as a supplement, including the "do not compare to NDWS/WSTS" section verbatim.
- **Registry export:** `NUMBERS.json` plus a generated `numbers.csv` so reviewers can grep paper figures against entries; the forbidden-string list as an appendix demonstrates the discipline.
- **Determinism statement:** seed 20250603, `osmnx == 2.0.7`, the 8-minute regeneration gate for `calibration_metrics.json`, and the statement that 16 Round-2 numbers are verified-but-unreproducible with the reason.
- **Author/ethics:** no human-subject data; EXIF handling described (only 4 GPS tags read, photo discarded); IEEE conflict-of-interest and AI-use disclosure (the autonomous agent loop that develops the repo must be disclosed under IEEE's AI-generated-content policy — state that all numbers are produced by deterministic scripts and human-reviewed).

---

## 5. Unverified items
- IEEE OJ-ITS impact factor and page limit; JSTARS 2026 APC exact figure (list shows "Full" without a legible number); TCSS IF year; GRSL IF year.
- IGARSS 2027 deadline shows both 10 and 11 Jan 2027 on the official site — use 10 Jan.
- GHTC 2027 and ISC2 2027 dates/deadlines (not announced).
- Existence of a high-school first-author IEEE Access paper in 2025 (not found; not disproved).
- ISEF Korea delegation: team count (5 vs. 7) and 2027 interview date; kcf.or.kr notice URLs returned 404.
- ISEF display rule wording on published papers (snippet only).
- Session-22 shelter finding ("one refuge saves 20 of 24") — from the commit title only; not read.
- Iceland travel cost estimate.

## Sources
- IEEE Access APC page: https://ieeeaccess.ieee.org/about/article-processing-charges/
- IEEE Access acceptance/decision-time (third-party, quoting IEEE): https://manusights.com/blog/ieee-access-acceptance-rate ; https://manusights.com/blog/ieee-access-review-time ; IF: https://www.journalmetrics.org/journal/ieee-access
- IEEE 2026 APC list (PDF): https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE-Article-Processing-Charges-List.pdf
- JSTARS information for authors: https://www.grss-ieee.org/publications/jstars-information-for-authors/ ; IF: https://www.bioxbio.com/journal/IEEE-J-STARS
- GRSL page/OPC/waiver: https://www.grss-ieee.org/publications/geoscience-and-remote-sensing-letters/ ; https://x.com/IEEE_GRSS/status/1926285861382971708 ; IF: https://www.journalmetrics.org/journal/ieee-geoscience-and-remote-sensing-letters
- TGRS OPC 2026: https://www.grss-ieee.org/publications/author-resources/tgrs-information-for-authors/ ; https://x.com/IEEE_GRSS/status/2009627476490698958
- IGARSS 2027: https://2027.ieeeigarss.org/important_dates.php ; https://2027.ieeeigarss.org/call_for_papers.php ; IGARSS 2026 paper kit: https://2026.ieeeigarss.org/papers/paper_kit.php
- T-ITS guidelines: https://ieee-itss.org/wp-content/uploads/T-ITS-Paper_Submission_Guidelines.pdf ; https://ieee-itss.org/pub/t-its/ ; IEEE citation-rankings note: https://www.ieee.org/about/news/2025/ieee-journals-lead-the-field
- OJ-ITS: https://ieee-itss.org/pub/oj-its/ ; https://ieeexplore.ieee.org/xpl/aboutJournal.jsp?punumber=8784355
- TCSS information for authors: https://www.ieeesmc.org/publications/transactions-on-computational-social-systems/information-for-authors/
- OJ-CS: https://www.computer.org/digital-library/journals/oj/cfp-open-journal ; https://askbisht.com/journals/ieee-open-journal-of-the-computer-society
- IEEE Sensors Journal guide: https://ieee-sensors.org/ieee-sensors-journal/for-authors/
- IEEE BigData 2026 dates: https://bigdataieee.org/BigData2026/important-dates/
- ICDM 2026 dates: http://icdm2026.neu.edu.cn/dates/list.htm
- IEEE SMC 2027: https://callforpaper.org/cfp/call-for-papers-ieee-smc-2027 ; http://www.wikicfp.com/cfp/servlet/event.showcfp?copyownerid=90704&eventid=201207
- GHTC 2026 CFP: https://ieeeghtc.org/author-central/call-for-papers/ ; https://ieee-region6.org/2026/ghtc-2026-call-for-papers-deadline-extended/
- ISC2 2026: https://dei.fe.up.pt/ieee-isc2-2026/call-for-papers/
- IEEE preprint policy: https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE-Article-Sharing-and-Posting-Policies.pdf ; https://cis.ieee.org/publications/t-emerging-topics-in-ci/tetci-ieee-preprint-policy ; TechRxiv: https://www.techrxiv.org/faqs
- ISEF rules: https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/ ; https://www.societyforscience.org/isef/international-rules/faq/ ; https://www.societyforscience.org/isef/faq/ ; Educator Guide 2025–26: https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/Rules-Educator-Guide.pdf ; ISEF 2027 dates: https://societyforscience.tfaforms.net/1061
- KCF ISEF selection (2026 cycle summary; original notice 404): https://namu.wiki/w/%ED%95%9C%EA%B5%AD%EC%BD%94%EB%93%9C%ED%8E%98%EC%96%B4 ; https://www.kcf.or.kr/notice
- KCF 운영요강 PDF (local): /Users/jp/Desktop/2026년 제8회 한국코드페어_운영요강(공지)_260325.pdf, pp. 5, 9, 11, 18
- Prior work: Borgwardt et al., arXiv:2410.14500 https://arxiv.org/abs/2410.14500 ; RESCUE, ICDCN 2026 https://dl.acm.org/doi/10.1145/3772290.3772301 (open copy: https://scholarsmine.mst.edu/comsci_facwork/2138/)
- Zenodo–GitHub DOI: https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content
