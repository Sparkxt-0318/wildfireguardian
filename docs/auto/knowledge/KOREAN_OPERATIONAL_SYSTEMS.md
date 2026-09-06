# Korean operational wildfire-prediction systems — what already exists, and what WildfireGuardian is not

*Knowledge note · written 2026-09-06 (research routine, sandbox) · status: **landscape note — no code, no artifact, no committed value touched** · maintained by the research routine (CHARTER §13). Companion notes: `PYROGEOGRAPHY.md` §2.5, `ROUTING_FUNDAMENTALS.md` §2.*

**Why this note exists.** Until this run, the repository described Korean fire-danger *forecasting* only through the occurrence-side 국가산불위험예보시스템 (`PYROGEOGRAPHY.md` §2.5), and its answer to 「어떻게 다릅니까」 was framed against academic work. That leaves the single most likely booth question unanswered: **Korea already operates wildfire-spread prediction systems, run by the agency that would deploy this project, and neither of them appears anywhere in the repository.** A judge from the disaster-response side will know at least one. This note collects what is publicly stated about them, with agency, date and scope per CHARTER §3 rule 5b, and states the honest differentiator.

⚠ **Read the source discipline first.** Everything in §1 and §2 is what an agency or a newspaper **says the system does**. None of it is a measured result this repository has reproduced, and the full technical documents were not opened (see §4). Nothing here may be used to compare accuracy with WildfireGuardian in either direction, on any surface. The differentiator in §3 is about the **output object**, and that is the only comparison the evidence supports.

## 1. NIFoS — AI 기반 산불확산예측시스템

- **What it is.** 국립산림과학원 (National Institute of Forest Science, the Korea Forest Service's research arm) operates an AI-based wildfire spread prediction system. Its user guide is published as 「AI 기반 산불확산예측시스템 사용자가이드」, 연구자료 제1201호 (2026), through the NIFoS library: <https://book.nifos.go.kr/library/10130/contents/7732761> [opened, catalogue page only]. The catalogue's table of contents describes an operator workflow — login, main screen, creating a fire origin point, entering fire information, running the spread prediction, firefighting resources, fuel parameters, administration. So it is an **operator console for suppression planning**, driven by a human-entered origin point.
- **What the agency says it improved.** A 사이언스타임즈 report of 2026-02-12 on the NIFoS AI/big-data wildfire response system states 「산불확산예측 정밀도를 기존 대비 약 30% 향상시키고」, 「지형 분석 정밀도를 5ｍ 수준까지 높인다」, and, on the *risk* (occurrence) side, 「현재 76% 수준인 산불위험 예측 정확도를 내년까지 88%로 끌어올릴 계획이다」, with a stated 60-second target for producing a suppression strategy and a 2030 completion horizon (<https://www.sciencetimes.co.kr/nscvrg/view/menu/249?searchCategory=221&nscvrgSn=261448>) [opened]. ⚠ These are **agency plan figures restated by a newspaper**, with no metric definition, no dataset and no validation scheme attached; the 76 %/88 % pair is an occurrence figure and the 30 % a spread figure, and they are not comparable to each other, let alone to anything here.
- **Terrain resolution is the number to notice.** 5 m terrain analysis against this project's 500 m hazard grid is two orders of magnitude, and it is a real capability gap, in their favour. It is also a gap in *inputs*, not in *conclusions*: the question this project answers is not answered better by a finer DEM alone.

## 2. 경기도 — 민방위 경보 예측모델 (G-DAPS)

- **What it is.** Gyeonggi Province built G-DAPS, a civil-defence alert prediction model that forecasts, from initial detection onward, a wildfire's route, the affected area, expected arrival times and when an alert should be issued. Risk is analysed in **30-minute steps** and damage is resolved to the **읍면동** (township) level. It ingests KMA short-range forecasts, KFS fire-risk alerts, MOLIT digital-twin data and the audible-coverage footprint of **589 civil-defence alert facilities**. Trial operation was stated to begin the following month, i.e. April 2026, with intended extension to floods and heavy snow (경향신문, 2026-03-30, <https://www.khan.co.kr/article/202603301116001/>) [opened]. The article reports **no accuracy figure**.
- **The unit is the point.** 읍면동 is an administrative area, typically thousands of residents. G-DAPS answers 「which township do we sound the sirens in, and when」. It does not answer 「can the person in this house walk out, and along which path」.

## 3. What this means for WildfireGuardian

**The differentiator is the output object, not the forecast, and not the accuracy.**

1. **Different consumer.** NIFoS's console is for a suppression commander choosing where to put crews and helicopters; G-DAPS is for a civil-defence officer choosing which sirens to sound. WildfireGuardian's consumer is a 이장, a county emergency desk and a rescue crew deciding **which household to reach first and along which walking route**. That is the frame the project was submitted under (CHARTER §3 rule 4) and it is not the frame either system serves.
2. **Different spatial unit of the decision.** 읍면동 (G-DAPS) versus **household origin** (this project's 458 canonical Yeongdeok origins). A township-level alert cannot say that a specific origin's fire-blind route enters the hazard and its forecast-aware route does not; that statement requires a per-origin routing pass, and it is the project's actual claim.
3. **Different question about the same forecast.** Both agency systems predict *where the fire goes*. This project's contribution is not a better answer to that question — the honest position is that a 500 m grid on ERA5 is coarser than a 5 m terrain analysis on operational weather — but the demonstration that **a forecast of where the fire will be changes which route and which rescue order are safe**, measured as a paired contrast on committed public data with every number re-derivable by a gate. Reproducibility on public data is a claim neither agency system makes, and it is the one an ISEF or IEEE reviewer weighs.
4. **What must never be said.** Do not claim this project is more accurate, faster, finer or better validated than either system. Nothing here supports it, the agency figures are plan statements rather than measurements, and CHARTER §3 rule 5 makes the claim unshippable. If a judge presses on accuracy, the answer is that the comparison has not been made and could not be made from public information — which is itself a true and defensible sentence.

## 4. What the routine could not open, and what it would take

- The NIFoS user guide's contents. The catalogue page is public; the document itself is an ~18 MB PDF served through the NIFoS library, which this sandbox did not retrieve. Its 「확산예측 모델링」 and 「연료 매개변수」 chapters would settle what model class, what resolution and what inputs the system uses, which is the difference between the honest §3 above and a genuinely informed comparison. **Escalated as NH-039** — the author can download it and drop it under `data/raw/evidence/`.
- Any published validation of either system. None was found. If none exists, that is itself worth one sentence in the manuscript's related work.
- Whether G-DAPS or the NIFoS console covers 경상북도 / 영덕 at all. G-DAPS is a 경기도 product by construction; the NIFoS console is national in principle. Not established here.

## 5. Backlog candidates

| id | question | data | when | rules |
|---|---|---|---|---|
| **C1** | Does `docs/auto/JUDGE_QA.md` carry a card for 「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」, and does the related-work panel (WFG-026) name both systems? | this note; no artifact | **before-freeze**, and deliberately **after** the WFG-134/WFG-130 kit rebuild so the printed pages are not made stale again; filed this run as **WFG-144** | yes — prose only; **no accuracy comparison on any surface**, agency/date/scope on every figure (§3 rule 5b) |
| **C2** | What does the NIFoS user guide actually specify (model class, resolution, inputs)? | the 18 MB PDF, author-supplied | after **NH-039** | yes once the PDF is in the tree with its sha256 registered as evidence |

## 6. Sources

- 국립산림과학원 (2026). 「AI 기반 산불확산예측시스템 사용자가이드」, 연구자료 제1201호. <https://book.nifos.go.kr/library/10130/contents/7732761> [opened — catalogue record and table of contents only; the PDF was not retrieved]
- 사이언스타임즈 (2026-02-12). 산림과학원, AI·빅데이터 기반 '산불 대응 시스템' 가동. <https://www.sciencetimes.co.kr/nscvrg/view/menu/249?searchCategory=221&nscvrgSn=261448> [opened; the figures it carries are agency plan statements]
- 경향신문 (2026-03-30). 산불 경로·피해 지역, 미리 예측해 전파한다 — 경기도, AI 예측 모델 자체 개발. <https://www.khan.co.kr/article/202603301116001/> [opened]
- 국립산림과학원 (2026-03-13). 「2026 산불 제대로 알기」 발간 (public Q&A booklet; ignition, spread, evacuation guidance). 대한민국 정책브리핑 <https://www.korea.kr/briefing/pressReleaseView.do?newsId=156748710&call_from=rsslink> [abstract — search result summary; the booklet itself was not opened]
- 국가산불위험예보시스템 (occurrence side, already in `PYROGEOGRAPHY.md` §2.5). <https://forestfire.nifos.go.kr/> [opened previously, 2026-09-04]
