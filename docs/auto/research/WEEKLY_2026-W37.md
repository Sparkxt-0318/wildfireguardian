# Research lap — ISO week 2026-W37 (run 2026-09-08T1817Z)

*`wfg-autoloop-research`, second run under the sprint cadence (CHARTER §11, §14: every second day at 18:17 UTC, 09-06/08/10/12/14, taking that slot from dev). Sprint ends 2026-09-15; this run is inside it. Head at start: `298a09c`. No code, no data, no figure and no `docs/NUMBERS.json` entry was touched.*

## 0. What this run is, and the honest size of its window

**Two days.** The previous research lap ran 2026-09-06T1817Z and its scan reached publications dated to about 2026-09-03. This run therefore scans 2026-09-04 → 2026-09-08 for the preprint channels. Two days of arXiv is not a literature, and a run that pretends otherwise is padding.

So this run did what the last one's own §1 said the next one should do: **it fixed the broken channel instead of re-running the working one.** Semantic Scholar returned HTTP 429 to this sandbox for the second consecutive run. **OpenAlex was tried as the substitute and it works**, with no key, at full rate, and it reaches the journal literature that arXiv structurally cannot — which was the exact hole the 09-06 run named. That change is worth more than any single paper below, and it is why this run has **four opened journal sources** where an arXiv-only run would have had one.

The most consequential finding is again from channel (c), and again it is domestic: **Korea has a published national timing standard for evacuating elderly residents ahead of a fire line, and its two thresholds sit inside this project's forecast horizon.**

## 1. Scan channels

| channel | what it returned | status |
|---|---|---|
| (a) alphaXiv connector | 10 ranked items, `published_after 2026-09-03`, recency-weighted. One already known (BEACON), the rest off-topic | **worked, thin** |
| (a) Scholar Gateway MCP | **still unavailable — the server requires OAuth and this is a non-interactive cloud session.** Unchanged since 09-06 | **blocked** |
| (b) arXiv API over WebFetch | two queries (wildfire ∧ (evacuation ∨ spread); conformal ∧ (risk control ∨ wildfire ∨ hazard)), newest-first. Two new-window entries, both already known | **worked, thin** |
| (b) Semantic Scholar Graph API | **HTTP 429 again**, second consecutive run, same anonymous endpoint | **failed — and now diagnosed, not just observed** |
| (b) **OpenAlex API — NEW THIS RUN** | three queries (wildfire evacuation; wildfire spread prediction ML; evacuation routing time-dependent shortest path hazard), each `from_publication_date` filtered and date-sorted. **This is where every journal source below came from** | **worked** |
| (c) plain web search, Korean | four queries on 산불/대피/고령자, 산불확산예측 AI, G-DAPS 시범운영, 한국코드페어 일정 | **worked, and it is again where the important finding came from** |

⚠ **Four sources this run could not open, recorded as UNVERIFIED and not used for any claim:** the Research Square preprint on the April 2025 East Asian wind extremes (HTTP 403), the Springer *Top* paper on congestion in time-expanded networks (paywall redirect to `idp.springer.com`), the *Ecological Processes* Yunnan WUI/WCI fire-regime paper (same paywall redirect), and the Zenodo record "Racing the Fire: Censored Survival Analysis for Wildfire Evacuation Forecasting" (HTTP 504, twice). Each is listed in §6 as a lead for the next run. **None of their substance is written anywhere in this repository**, including in the paragraphs where their titles appear.

## 2. What is new, and what it does to this project's claims

### 2.1 Korea publishes an 8-hour and a 5-hour elderly-evacuation threshold — and our horizon brackets both

**This is the run's headline.** 헤럴드경제, 2026-02-12, 「산림과학원, AI·빅데이터 기반 '산불 전방위 대응 시스템' 가동」, <https://biz.heraldcorp.com/article/10675702> [opened]. Reporting NIFoS's 2026-02-12 strategy announcement, in the agency's own framing:

> 「'준비(Ready)-실행 대기(Set)-즉시 실행(Go)'으로 이어지는 단계별 체계」에 따라, 「화선 도달 8시간 전 산불확산 예측 정보를 바탕으로 고령자 등 안전 취약계층의 선제적 대피를 돕고, 5시간 전에는 대상 주민이 안전한 곳으로 지체 없이 이동하도록 유도할 방침」

**What it is:** a national, inter-agency (산림청·국립산림과학원 with 행정안전부) staged-evacuation doctrine whose two decision points are expressed as **lead time to fire-line arrival** — 8 h to begin preemptively moving 고령자 등 안전 취약계층, 5 h to complete the move. The same article restates the accuracy plan figures already recorded on 09-06 (산불위험 예측 정확도 76 % → 88 % by 2027; 산불확산예측 정밀도 약 30 % 향상), which stay in the knowledge note with their agency, date and scope and reach no card and no registry.

**How it changes this project's claims.** It changes the *status of the horizon*, and it changes nothing measured.

`docs/MODEL_CARD.md:344` states the project's forecast horizon as **3–12 h**, evaluated at 3/6/9/12 h (forward-sim envelope ≈ 0.40). Until today the honest answer to a judge's 「왜 3–12시간입니까?」 was about data and model constraints — the FIRMS overpass cadence and what the label supports. As of this source there is a second, better answer available: **5 h and 8 h are the two lead times Korean national policy actually makes an elderly-evacuation decision at, and both lie strictly inside 3–12 h.** The project's horizon is not an artifact of its data; it is the window in which the country's own doctrine says the decision gets made.

⚠ **Three boundaries, and they are load-bearing.** (i) These are **plan statements in a press restatement of an agency announcement**, not validated lead times, not a measured standard, and not a document this run opened in primary form — the same class of figure that produced WFG-049 and CHARTER §3 rule 5b. The permitted sentence is 「국가 정책이 상정하는 대피 의사결정 시점이 5–8시간이고, 이 작품의 예보 지평이 그 구간을 포함한다」. The forbidden sentence is 「따라서 우리 예보가 정책 요건을 충족한다」 — nothing here measures whether this project's forecast is *good enough* at 5–8 h, and its own 3–12 h envelope figure of ≈ 0.40 says the opposite of comfortable. (ii) 「화선 도달」 is fire-line arrival at a place; this project's horizon is time from forecast issue. They are the same clock only if detection is instant, which `docs/detection_floor.md` exists to say it is not. (iii) No number from this source enters README, the manuscript or `docs/NUMBERS.json`.

Written up in `KOREAN_OPERATIONAL_SYSTEMS.md` §Update 2026-09-08. Filed as **WFG-197**.

### 2.2 Somebody published this project's route-existence method, for a different hazard — 10.3389/fbuil.2026.1856100

Opanasopit & Louis, 2026-08-06, *Frontiers in Built Environment*, <https://doi.org/10.3389/fbuil.2026.1856100> [opened]. **What they did:** a GIS framework that identifies **isolated communities** after a disaster by converting the surviving road network into an undirected NetworkX graph and running **connected-component analysis** to find components that have lost ground connectivity to the regional network; population-level accessibility is then a Census-Block **road-length ratio** (surviving connected road length ÷ pre-disaster road length, times block population) computed per facility type. **Study area:** Clatsop County, Oregon, under earthquake, tsunami, flood, landslide and windstorm scenarios. **The metric and numbers:** under the combined all-hazards scenario, **70 isolated communities**, and the population retaining access to critical facilities falls from **38,100 to 11,900**; flooding produced the most network fragments while tsunami produced the largest accessibility loss; one airstrip remained the only road-accessible airport under tsunami and flood, which the authors name as single-access-route vulnerability.

**How it changes this project's claims — and it strengthens the novelty claim rather than diluting it.** WildfireGuardian's route-existence result has read, in this repository, as the project's own construction. It is not: it is an instance of a recognised method — connected-component accessibility on a disrupted network — and saying so is the stronger move, because it lets the contribution be stated as the *difference* rather than as the whole. The difference is precise and defensible: **Opanasopit & Louis remove edges under a static post-event hazard footprint and ask who is cut off; this project removes an edge's usability as a function of when a walker would traverse it under a moving, forecast hazard field, and asks who can still get out in time.** Static severance versus time-dependent severance under a forecast. That sentence is a related-work line and a booth answer at once, and it costs no number.

⚠ Different hazard, different country, different unit (Census Blocks, vehicles, road network) — it validates the **method class**, never a fire number here. Filed as **WFG-198**.

### 2.3 Multi-window fuel-drought encoding, from an East Asian station — 10.1371/journal.pone.0355829

Chen et al. <!-- forbidden-ok: Chen -->, 2026-09-01, *PLOS ONE*, <https://doi.org/10.1371/journal.pone.0355829> [opened]. **What they did:** FWI-MSNet, a forest-fire-risk predictor that organises inputs by the Fire Weather Index system's own temporal structure — **three parallel 1D-CNN channels with kernel widths of 7, 30 and 90 days** for daily fuel response, monthly and seasonal drought accumulation — fused by a GRU-Transformer hybrid. **Data:** Huitong Ecological Station, China, 2005–2022 (18 years of continuous observation); transfer tested on the 2020 Australian fires over six ERA5 regions. **The metric:** R² **0.9251**, RMSE 1.6892, MAE 1.4046, MAPE 30.47 % on the test set, an approximate 56.1 % error reduction against seven baselines; on the Australian transfer, R² **0.57–0.77** across regions with MAPE near 25 %.

**How it changes this project's claims.** It is a **regression of a fire-danger index**, not next-overpass ignition, so its R² and this project's AUC are not comparable and must never be placed side by side. What it contributes is one design observation: the fuel-dryness signal that matters is **multi-timescale in time**, and the transfer result (0.9251 → 0.57–0.77 off the training station) is a second external instance of the honest-validation penalty the 09-06 run recorded from Farajpoor & Narimani — this time across *geography* rather than across spatial blocks. It confirms `PYROGEOGRAPHY.md` §6 insight 2 from a new direction. It does **not** license a feature change: adding 7/30/90-day drought windows to `spread_v2` is a refit, which CHARTER §3 rule 2 forbids before the finals. Parked as **P-003**.

### 2.4 Read and deliberately not carried further

- **BEACON** (arXiv:2609.03301), **RF-informed cellular automaton** (arXiv:2609.01675): both already recorded on 09-06; nothing to add.
- **Occupancy-based Quantile Risk Control** (arXiv:2609.03104, 2026-09-02) and three other conformal-risk-control papers (2609.01375, 2608.27124, 2608.26529): all outside hazard mapping — CSI prediction, LLM judging, vision-language factuality. The conformal topic remains open with **no wildfire-hazard instance found in two consecutive runs**, which is itself worth recording.
- **Evac-cast** (*Safety Science*, 10.1016/j.ssci.2026.107391, 2026-08-21), an interpretable ML framework for evacuation prediction: surfaced by OpenAlex, **not opened** (Elsevier 403). A lead, not a source.
- Scanned and not relevant: crowd DEM reviews, urban flood evacuation path optimisation, quantum ACO evacuation, tunnel-fire ceiling temperature, Malaysian fire-susceptibility mapping, post-fire restoration remote sensing.

## 3. Ideation — two survivors, one parked

Each candidate is new relative to the literature actually read above, and each ran `macrothink` (three independent starts) then `hate` (one root objection, one cheapest test).

### C1 → **WFG-197**. Anchor the 3–12 h horizon to the national 5–8 h decision points

- **Claim.** The strongest available answer to 「왜 3–12시간 예보입니까?」 is not a data constraint but a policy fact: Korean national doctrine makes the elderly-evacuation decision at 8 h and completes it at 5 h before fire-line arrival, and this project's horizon contains that window. The deliverable is one Q&A card, one line in the manuscript's operational-relevance framing, and the sourced paragraph in the knowledge note.
- **`macrothink`, three independent reads.** *(i) KCF disaster-response judge:* this judge knows the Ready-Set-Go doctrine and will hear a horizon justified by satellite cadence as a technical excuse; a horizon justified by the decision point is an operational design choice, and it is the same number. *(ii) Fire scientist:* the 8 h/5 h are agency plan statements with no published derivation, so they establish *where the decision is made*, not that anyone's forecast is skilful there — and this project's own 3–12 h envelope of ≈ 0.40 forbids any claim of sufficiency. *(iii) Paper reviewer:* a Discussion that names the operational decision point its horizon serves is standard and expected; one without it reads as a benchmark exercise. **Convergence:** all three land on the same narrow object — a *framing* claim about where the decision sits, with an explicit disclaimer of any sufficiency claim in the same breath.
- **`hate` — one root objection.** *Quoting an agency's press-restated plan to justify our own design is borrowing authority we did not earn, and it is the exact shape of the WFG-049 failure that CHARTER §3 rule 5b was written for.* **Cheapest test:** draft the card asserting only 「정책이 대피 결정을 상정하는 시점」 and never 「우리 예보가 그 시점에서 충분하다」, and check that it still answers the question. **It does** — the question is why the horizon is what it is, not how good it is there. The card must carry the ≈ 0.40 envelope figure in the same card, so the honest limit travels with the framing.
- **Preregistration.** *Claim:* not empirical; deliverable is a card plus a related-work/Discussion line. *Data:* the two opened Korean sources in `KOREAN_OPERATIONAL_SYSTEMS.md` §6 and §Update 2026-09-08; no new artifact. *Metric:* none. *Expected effect size / power at n = 6 fires or 3 regions:* **not applicable, and deliberately so** — no estimate is produced, so nothing is under-powered; a lap that finds itself computing something here has left the row. *Falsified if:* the project's horizon does not in fact contain 5–8 h (it does: `docs/MODEL_CARD.md:344`, evaluated at 3/6/9/12 h), or if the card cannot be written without implying sufficiency. *Effort:* hours.

### C2 → **WFG-198**. State route-existence as time-dependent severance, against a published static-severance method

- **Claim.** The project's route-existence contribution is more defensible stated as a *difference from* connected-component accessibility analysis (Opanasopit & Louis 2026) than as an unsituated construction: static severance under a post-event footprint versus time-dependent severance under a moving forecast field.
- **`macrothink`, three independent reads.** *(i) ML reviewer:* an unsituated method claim is the easiest kind to attack; situating it converts 「did you invent this?」 into 「what is new?」, which has a one-sentence answer. *(ii) Fire scientist:* the cited work is earthquake/tsunami/flood, so it can validate the graph method and never a fire result — the boundary must be in the sentence itself. *(iii) Booth:* 「기존 접근성 분석과 뭐가 다릅니까」 currently has no card, and this is a cleaner differentiator than any accuracy comparison, which §2.4 of the 09-06 run already established this project cannot make honestly. **Convergence:** a related-work line plus one Q&A card; no code, no number.
- **`hate` — one root objection.** *Importing a tsunami paper into a wildfire related-work section is padding unless it changes a sentence the repository already writes.* **Cheapest test:** name the sentence it changes. It changes the route-existence framing from an invention claim to a delta claim, which is both weaker in scope and stronger in defensibility — a reviewer can refute an invention claim with one citation and cannot refute the delta. Survives.
- **Preregistration.** *Claim:* not empirical. *Data:* prose plus one `references.bib` entry, verified at its DOI by the lap that adds it (CHARTER §12). *Metric:* none. *Expected effect size / power:* **not applicable** — no estimate produced. *Falsified if:* the repository already situates route-existence against accessibility literature (checked this run: `ROUTING_FUNDAMENTALS.md` §2 and §5 carry evacuation and shelter-location literature and **no** isolation/accessibility literature), or if the delta sentence cannot be written without overclaiming the moving-hazard part. *Effort:* hours.

### Parked → **P-003**. Multi-window (7/30/90-day) drought windows in `spread_v2`

Root objection: it is a **refit**, and CHARTER §3 rule 2 forbids regenerating a committed artifact before the finals; the source task is also index regression rather than next-overpass ignition, so the transfer of the design is unevidenced for this label. Full entry with the cheapest test that would revive it in `IDEAS_PARKED.md`.

**Two rows, not three, and that is deliberate.** The 09-06 run filed three P1 rows and explained why none was P0; that argument holds harder today. At `298a09c` there are **twelve P0 `todo` rows** and the sprint has seven days left. Both rows below are **P1**, judge-facing, and cost prose only.

## 4. Competitive and fair landscape

- **KCF.** The 2026 제8회 한국코드페어 운영요강 and announcement pages (<https://kcf.or.kr/84/?bmode=view&idx=171493723>, <https://kcf.or.kr/71/?bmode=view&idx=172288990>) confirm the schedule the charter already records — 접수 5/26–6/15, 서면심사 6월, 예선 8월, **본선 10월 광주** — and the year's theme, 「AI와 데이터로 해결하는 우리 사회의 문제」. No rule change, no published finalist list. Nothing to act on; the theme line is worth the student knowing verbatim.
- **ISEF / KSEF.** No new wildfire-evacuation-routing project surfaced this run. This is the **third consecutive sweep** returning nothing in this exact niche; it remains a weak negative (only awarded projects surface in search) and should keep being reported as one.
- **Korean news a judge might have read.** The NIFoS Ready-Set-Go doctrine of §2.1 is the item — it was announced 2026-02-12 and is the frame a disaster-response judge is most likely to be carrying. Also surfaced: 국립산림과학원's AI 산사태 영향범위 예측 for 전국 마을 단위 (경향신문, 2026-06-10, <https://www.khan.co.kr/article/202606100953001/>) — a *different* hazard by the same agency, useful only as evidence that the agency's direction is village-granularity AI hazard prediction, which is the granularity this project works at.
- **G-DAPS trial operation.** Re-checked for a results publication after the April 2026 시범운영 start. **None found.** The 09-06 run's record stands: route, 읍면동, arrival times and alert timing at 30-minute steps, **no accuracy figure published**. WFG-163 (which narrows the trial-operation claim in the manuscript) is unaffected and still correct.

## 5. IEEE plan status

`docs/auto/research/IEEE_PLAN.md` updated: the related-work section gains two entries from this run (Opanasopit & Louis 2026 for accessibility/isolation; the NIFoS doctrine as an operational-relevance anchor rather than a citation of method), and the venue and timing are unchanged — submission after 2026-12, outside the sprint. **Nothing was submitted anywhere.**

## 6. Escalation and leads

- **NH-048 (DECISION/ASK, LOW)** — filed this run. The routine prompt names Semantic Scholar as channel (b); it has now returned HTTP 429 to this sandbox on **two consecutive runs**, and **OpenAlex** was proven this run to be a working, key-free substitute that reaches strictly more (journal) literature. The ask is one line on the routine page. Details and options in `docs/auto/NEEDS_HUMAN.md`.
- **NH-039 remains open** (the NIFoS user guide is an ~18 MB PDF this sandbox cannot retrieve). §2.1 raises its value: the guide is now the primary source for a doctrine this project wants to cite, and a press restatement is the only version the loop can reach.
- **Leads for the next run, all UNVERIFIED, none cited:** the April 2025 East Asian wind-extremes preprint (rs-10649476, 403 — potentially the mechanism behind the motivating event's winds); "Racing the Fire: Censored Survival Analysis for Wildfire Evacuation Forecasting" (10.5281/zenodo.22327368, 504 twice — on the face of the title, the closest published object to this project's time-to-decision framing found so far, and the single highest-value lead outstanding); Evac-cast (10.1016/j.ssci.2026.107391, Elsevier 403); the *Top* lifeboat/congestion paper (10.1007/s11750-026-00724-7, paywalled — bears on P-001's parking); the *Ecological Processes* Yunnan WUI/WCI paper (10.1186/s13717-026-00745-x, paywalled).

## 7. What this run did not do

No code, no data, no figure, no `docs/NUMBERS.json` entry. No number from any source above entered `README.md`, the manuscript or the registry; every figure quoted stays in its knowledge note with its agency, date and scope (CHARTER §13, §3 rule 5b). No paper was cited that this run did not open, and the five it could not open are named as such in §1 and §6 with their HTTP status. `docs/auto/DIRECTION.md` was rewritten (§14) and **no P0 row was moved below a non-P0 row**; the two new rows enter at the end of the P1 block, which reorders nothing.
