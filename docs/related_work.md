# Related work, and what this project does that the surveyed work does not

*WFG-026. Written 2026-09-07 by the autonomous dev lap (CHARTER §9: the method was
proposed by the loop; the student rewrites the booth panel in their own voice before
speaking it). The Korean one-page booth version of this file is
[`docs/auto/finals/RELATED_WORK_PANEL.md`](auto/finals/RELATED_WORK_PANEL.md), and it
prints inside the booth kit.*

## What this document is, and what it is not

**It is** the survey this project positions itself against: every entry is a work whose
citation was resolved to a DOI or a permanent URL, what it computes, and what it does
**not** compute. It exists so that the sentence 「기존 연구와 무엇이 다릅니까」 has an
answer a judge can check line by line rather than take on trust.

**It is not** a comparison of results. No entry here is benchmarked against this
repository, in either direction, and no accuracy number of ours appears on this page.
Three reasons, all of them binding:

1. **The metrics are not comparable.** Label definition, geometry and above all
   prevalence differ between these settings, and prevalence moves average precision by
   construction. [`docs/MODEL_CARD.md`](MODEL_CARD.md) and `paper/manuscript.md` §2 say
   the same thing.
2. **For the two Korean operational systems, no published validation was located at
   all** (`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md` §4). The capability figures
   in circulation are agency plan statements restated by newspapers, with no metric
   definition, no dataset and no validation scheme attached.
3. **The claim this project actually makes is not an accuracy claim.** It is that a
   forecast of where the fire will be changes which walking route and which rescue order
   are safe. What is measured, and its limits, lives in
   [`docs/MODEL_CARD.md`](MODEL_CARD.md) (the canonical spread-model numbers),
   [`docs/routing_limitations.md`](routing_limitations.md) (what the routing layer does
   NOT support, measured and deliberately unfixed) and
   [`docs/dispatch_ordering.md`](dispatch_ordering.md) (the dispatch-order effect,
   measured, and it goes against us) — not here.
   ⚠ [`docs/rescue_routing.md`](rescue_routing.md) is the older methods note and opens
   with a DO-NOT-CITE banner over its pre-flip synthetic figures; read it for method and
   take no number from it.

**Positioning language.** Every gap below is written as *not found in the surveyed
work*, never as 최초 or 처음. The survey is a survey and not a proof of absence; it is
what one student, one loop and a search of public sources found by 2026-09-07.
`scripts/check_forbidden.py`'s claim rules enforce the wording.

---

## 1. The table

| # | work | citation | what it computes | what it does **not** compute |
|---|---|---|---|---|
| 1 | Cova & Johnson, lane-based evacuation routing | [10.1016/s0965-8564(03)00007-7](https://doi.org/10.1016/s0965-8564(03)00007-7) | evacuation as a network-flow / lane-assignment problem on a road network | pedestrians; a hazard field that moves during the evacuation |
| 2 | Cova et al., wildfire evacuation trigger points | [10.1111/j.1467-9671.2005.00237.x](https://doi.org/10.1111/j.1467-9671.2005.00237.x) | a spatial line whose crossing by the fire front should start an evacuation, from coupled spread modelling and GIS | *which way* to leave once the trigger fires |
| 3 | Li, Cova & Dennison, trigger buffers by reverse geocoding | [10.1016/j.apgeog.2017.05.008](https://doi.org/10.1016/j.apgeog.2017.05.008) | names the road segments a trigger buffer implicates | a per-household walking route on those segments |
| 4 | Li, Cova & Dennison, triggers coupled to traffic simulation | [10.1007/s10694-018-0771-6](https://doi.org/10.1007/s10694-018-0771-6) | trigger geometry that accounts for how long the evacuation itself takes | slow pedestrians with no vehicle; rescuer ingress |
| 5 | Wahlqvist et al., WUI-NITY | [10.1016/j.ssci.2020.105145](https://doi.org/10.1016/j.ssci.2020.105145) | a coupled fire / pedestrian / traffic platform at community scale | a learned hazard field held out at the fire level; a rescue-dispatch order |
| 6 | Finney, FlamMap minimum travel time | [10.1139/x02-068](https://doi.org/10.1139/x02-068) | physical fire growth as a minimum-travel-time problem over a fuel/terrain grid | anything about who evacuates, or how |
| 7 | Borgwardt et al., evacuation as time-expanded max flow | [arXiv:2410.14500](https://arxiv.org/abs/2410.14500) | maximum flow on a time-expanded network with wildfire hazard integrated | individual pedestrians; a crew driving *toward* the fire |
| 8 | Tammali et al., RESCUE (ICDCN 2026) | [10.1145/3772290.3772301](https://doi.org/10.1145/3772290.3772301) | vehicle evacuation routing under stochastic congestion and uncertain spread | household-level walk-out on a real walk graph |
| 9 | Dayan, conformal risk control applied to wildfire | [arXiv:2603.22331](https://arxiv.org/abs/2603.22331) | distribution-free guarantees on a monotone risk by calibrating a threshold | what the guarantee costs at six fires (this project measures that in [`docs/operating_point.md`](operating_point.md), which recomputes from committed leave-one-fire-out held-out probabilities and trains nothing) |
| 10 | Lahrichi et al., WSTS+ | [arXiv:2502.12003](https://arxiv.org/abs/2502.12003) | next-day spread learned over many fire-years; time-series inputs beat single-day inputs | any decision object downstream of the prediction |
| 11 | Sung et al., GK2A detection (KJRS 2025) | [KJRS](https://www.kjrs.org/journal/view.html?pn=mostdownload&uid=1117&vmd=Full) | geostationary detection of Korean fires at the imager's cadence and resolution | the evacuation consequence of detecting late |
| 12 | Kwon, Kim & Han, Uiryeong shelter MIP | [10.3390/systems13121125](https://doi.org/10.3390/systems13121125) | shelter siting / assignment for a Korean rural county as a mixed-integer program | a time-varying hazard between the household and the shelter |
| 13 | **NIFoS 산불확산예측시스템** (operational) | [user guide, 연구자료 제1201호, 2026](https://book.nifos.go.kr/library/10130/contents/7732761) | an **operator console** for suppression planning, driven by a human-entered origin point | which household can still walk out, and along which path |
| 14 | **경기도 G-DAPS** (operational) | [경향신문 2026-03-30](https://www.khan.co.kr/article/202603301116001/) | a civil-defence alert model: route, arrival times and the **읍면동** an alert should cover, in half-hour steps | anything below the township; a walking route for one person |
| 15 | ISEF 2026 **SFTD059T** | [abstract](https://abstracts.societyforscience.org/Home/FullAbstract?projectId=27978) | **indoor** egress: floor-plan recognition, a fire/toxic-gas model trained on FDS output, A\* with time-varying risk, a Raspberry Pi display | outdoor landscape fire; rural settlement; rescuer dispatch |
| 16 | ISEF 2026 **FireChain (EAEV039)** | [abstract](https://abstracts.societyforscience.org/Home/FullAbstract?projectId=28121) | routing suppression **crews to firelines**, with conformal bounds as time-window constraints | routing residents away from the fire |

> ⚠ **Citation provenance, split by how strong it actually is.** This distinction was
> not in the first draft of this page, which claimed 「entries 1–12 … each is carried in
> `paper/references.bib` with its `verified` note」. **That was false of three of
> them**, and it was caught by cross-checking every identifier on this page against the
> `.bib` rather than by re-reading the sentence. The true split:
>
> - **Carried in `paper/references.bib` with a `verified` note** (a lap opened the work
>   at its URL): entries **1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 14**.
> - **Resolved on 2026-09-03 outside this sandbox and NOT yet in `references.bib`**:
>   entries **9** (Dayan, arXiv:2603.22331 — note the manuscript cites
>   `angelopoulos2024crc` for conformal risk control, which is a *different* work),
>   **11** (Sung et al., KJRS 2025) and **12** (Kwon, Kim & Han, `10.3390/systems13121125`).
>   They are carried here from the WFG-026 backlog row's resolved list. **This page does
>   not assert that a lap re-opened them**, and none of them may enter the manuscript
>   until one does (`paper/` §12's rule: a paper the lap could not open is not cited).
> - **Abstract pages read on 2026-09-03**: entries **15, 16**
>   (`docs/auto/research/sweeps_2026-09-03/R2_isef_category_landscape.md`).
>
> Entries 13–14 were opened by the research routine on 2026-09-06; their scope and date
> limits are in `docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`. **A citation this
> repository could not re-resolve from the sandbox is kept with its provenance stated
> rather than silently dropped or silently promoted**, which is the rule WFG-026 was
> written under.

---

## 2. The two Korean operational systems, stated fairly

This is the question most likely to be asked by a judge from the disaster-response side,
and until 2026-09-06 the repository had no answer to it: **Korea already operates
wildfire-spread prediction, run by the agency that would deploy anything like this.**

- **NIFoS's 산불확산예측시스템** is an AI-based spread-prediction console published with a
  2026 user guide (국립산림과학원, 연구자료 제1201호). Its table of contents describes an
  operator workflow — create a fire origin point, enter fire information, run the spread
  prediction, fuel parameters, firefighting resources. A 사이언스타임즈 report of
  2026-02-12 states an intended terrain-analysis resolution of **5 m** (agency plan
  statement, spread side, no metric definition attached).
- **경기도's G-DAPS** forecasts a fire's route, affected area, expected arrival times and
  when to issue an alert, analysing risk in **30-minute steps** and resolving damage to
  the **읍면동**, drawing on the audible footprint of **589 civil-defence alert
  facilities**; trial operation was announced for April 2026 (경향신문, 2026-03-30). The
  article reports **no accuracy figure**.

**Where they are ahead, said plainly.** A 5 m terrain analysis is two orders of magnitude
finer than this project's hazard grid. That is a real capability gap, in their favour,
and the booth panel says so. It is a gap in *inputs* rather than in *conclusions*: the
question this project answers is not answered better by a finer DEM alone.

**Where the difference actually lies — the output object.**

| | NIFoS console | G-DAPS | WildfireGuardian |
|---|---|---|---|
| consumer | suppression commander | civil-defence officer | 이장 · county emergency desk · rescue crew |
| decision | where to put crews and helicopters | which sirens to sound, and when | which household to reach first, and along which walking route |
| spatial unit | fire origin and front | 읍면동 (township) | **household origin** |
| origin of the fire | entered by a human operator | from initial detection | satellite trigger with committed offline replay |
| reproducible by a stranger | not stated | not stated | committed public data, every number re-derived by a gate |

**⚠ The rule that governs this section, on every surface, in both directions: no accuracy
comparison with either system.** Nothing in public information supports one, and CHARTER
§3 rule 5 makes it unshippable. If a judge presses, the honest answer is that the
comparison has not been made and could not be made from what is published — which is
itself true, checkable and worth saying out loud.

---

## 3. The SFTD059T differentiation panel

**Why this one work gets its own panel.** SFTD059T — *Development of an FDS-Grounded
Risk-Aware Evacuation Route Design and Visualization System for Incident Support* (Seo,
Ko, Lee; Gyeonggibuk Science High School; ISEF 2026, AAAI student-membership special
award) — is the nearest neighbour this project has, it is Korean, it is a high-school
project, and judges may remember it. Saying how the two differ is more convincing than
hoping nobody makes the connection.

| axis | SFTD059T | WildfireGuardian |
|---|---|---|
| the fire | **indoor** compartment fire and toxic gas, a lightweight model trained on FDS output | **landscape wildfire**, a learned spread field on Korean fires from committed public observations |
| the space | a building floor plan, recognised by computer vision; multi-floor hazard transfer | a rural walk graph from OpenStreetMap, with terrain |
| the person | an occupant leaving a building | a **rural elderly resident** walking out of a household, at a conservative fixed gait speed |
| the algorithm | A\* with time-varying risk in the cost | shortest path on a **time-expanded graph** whose edge feasibility comes from the forecast hazard field |
| the rescue side | not addressed | rescuer **ingress** feasibility and a dispatch order — a crew driving *toward* the fire |
| the trigger | a static scenario pack | a live satellite trigger with a committed **offline replay** for the booth |
| the artefact | Raspberry Pi display panel | offline single-file console (`web/finals.html`) plus a printed dispatch sheet for a village with no smartphone |

**What the two share, and it is worth conceding at the booth:** both put *time-varying
hazard into the routing cost* rather than routing on distance, and both value cumulative
exposure over shortest path. That idea is not this project's invention, and entries 2–4
of the table above are where it comes from. **What is not found in the surveyed work** is
that idea applied to *rural household-level walk-out on a learned, held-out landscape
hazard field, with a rescue-side ingress term beside it.*

FireChain (EAEV039) is the mirror image and is worth one sentence for the same reason: it
routes **crews to firelines** under conformal bounds. Routing crews in and routing
residents out are different objectives on the same graph, and this project carries both.

---

## 4. What this document does not show

- **It does not show that no such work exists.** It shows what a search of public sources
  by 2026-09-07 found. A judge who names a work not on this list is right to, and the
  correct answer at the booth is to write it down, not to argue.
- **It does not compare results with anything.** See the top of this page for why. In
  particular it establishes **no** ranking against the NIFoS console or G-DAPS.
- **It does not establish that the differences listed are advantages.** A finer terrain
  model, a national deployment and an operations team are advantages the agency systems
  have and this project does not. What the table claims is that the *object produced* is
  different, and that the difference is the reason this project could sit beside them
  rather than compete with them.
- **It reads two of its sixteen entries from abstract pages only** (15, 16) and two from
  a catalogue record and newspaper reporting (13, 14). The full NIFoS user guide is an
  ~18 MB PDF the sandbox could not retrieve; **NH-039** asks the author to fetch it, and
  until then §2's account of that system is what the agency says it does.

## 5. Where the numbers on this page come from

Every figure in §2 is an **external** figure and carries its agency, date and scope in
the sentence that uses it, per CHARTER §3 rule 5b — 5 m and the 2026-02-12 사이언스타임즈
report; 30-minute steps, 읍면동, 589 facilities and the 2026-03-30 경향신문 report. None
of them is registered in `docs/NUMBERS.json`, and none of them may be: they are not this
repository's measurements. **This page states no measurement of this repository's own**,
which is why it needs no registry key of its own; the project's numbers live in
[`docs/MODEL_CARD.md`](MODEL_CARD.md), [`docs/operating_point.md`](operating_point.md),
[`docs/dispatch_ordering.md`](dispatch_ordering.md),
[`docs/routing_limitations.md`](routing_limitations.md) and
[`docs/submission_reconciliation.md`](submission_reconciliation.md), each with its key.

⚠ **The first draft of this page pointed at four files that do not exist** —
`docs/model_card.md`, `docs/routing.md`, `docs/rescue_dispatch.md` and <!-- dead-path-ok -->
`docs/conformal.md`, seven present-tense assertions in all. They were not a rename away: <!-- dead-path-ok -->
the nearest real file to the third was the superseded `rescue_routing.md`, and the
conformal pointer named the wrong subject entirely. This lap's independent reviewer
found them by running `os.path.exists` over every backticked repository path, which is
the check the repository does not have and which **WFG-157** now files.
