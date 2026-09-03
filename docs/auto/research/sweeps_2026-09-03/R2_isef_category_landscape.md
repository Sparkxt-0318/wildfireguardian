# R2 — ISEF category strategy and competitive landscape for WildfireGuardian

Date: 2026-09-03. Scope: ISEF 2027 entry via the Korean delegation. Sources: Society for Science rules/forms/press releases (2025–26 and 2026–27 editions), the ISEF Projects Database (abstracts.societyforscience.org, queried directly for 2021–2026), and the project's own README / docs. Every external claim carries a URL. Items I could not confirm are marked UNVERIFIED.

Raw pulls (for audit): `research/r2/landscape_raw.txt`, `research/r2/landscape_abstracts.json`, `research/r2/winners_raw.txt`, `research/r2/{ai,ds,mods,all_forms,categories}.txt`.

---

## 0. Verdict in five lines

1. **Enter Software Design (SFTD), subcategory Algorithms (ALG).** "Systems Software (SOFT)" no longer exists — it was renamed **Software Design (SFTD)** for ISEF 2026 (22 categories; the 2026 Korean evacuation project carried booth code SFTD059T). The README (line 197, line 494) still says "ISEF (Systems Software)"; fix the name.
2. **EAEV is the fallback, not the target.** Wildfire-ML projects have a 6-year record in EAEV of 2nd–4th awards and unplaced finalists; the closest competitor to WildfireGuardian (FireChain 2026, detect→forecast→crew-routing with conformal bounds) entered EAEV and won **no grand award**. EAEV judges will attack the spread model's earth-science validity (ERA5 0.25°, six fires, AUC range 0.68–0.97) — the project's weaker arm — and under-weight the routing contribution.
3. **The biggest rule risk is not the 12-month window; it is AI disclosure.** 2026–27 rules: AI-written code is acceptable only "with explicit citation stating which portions of the code were AI generated and with a log of the prompts"; research plan, abstract and poster "must be the independent work of the student"; a new **Form 2A (Student Support Disclosure)** is required for every project. An autonomous agent loop developing the repo must be ledgered now, or the "degree of independence" interview criterion (part of 25 pts) becomes fatal.
4. **Expert consultations (firefighter N=1, professors) do not need Form 4**; an **operator usability test does**, and it needs IRB approval *before* recruiting anyone. Do not run one informally.
5. **The booth cannot have live internet, QR codes or URLs.** The live FIRMS trigger must be demonstrated from cached data (web/finals.html is already the right shape); a GitHub link cannot appear on the poster.

---

## 1. Category decision (ranked)

### 1.1 What the 2026 category list actually is

Regeneron ISEF 2026 has 22 categories (societyforscience.org/isef/categories-and-subcategories/): ANIM, BEHA, BCHM, BMED, ENBM, CELL, CHEM, CBIO, EAEV, EBED, EGSD, ETSD, ENEV, MATS, MATH, MCRO, PHYS, PLNT, ROBO, **SFTD (Software Design)**, TECA (Technology Enhances the Arts — new), TMED. The 2026 abstract/certification form (https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/2026-22-Categories.pdf) lists "Software Design" and no "Systems Software". The Society's own guidance on choosing: "Selection of category should be solely based on what best fits your project … Who will be the most qualified to judge my project? What area of expertise is the most important for the judge to have?" (same URL).

SFTD description and subcategories (https://www.societyforscience.org/isef/categories-and-subcategories/software-design/): "The study or development of software, information processes or methodologies to demonstrate, analyze, or control a process/solution." Subcategories: **Algorithms (ALG)** "the study or creation of algorithms – step-by-step procedure of calculations to complete a specific task in data processing, automated reasoning and computing"; Cybersecurity (CYB); Databases (DAT); **Human/Machine Interface (HMC)** "software application that presents information to a user about the state of a process and to accept and implement the operator's control instructions"; Languages & OS (LNG); Mobile Apps (APP); Online Learning (LRN); Other (OTH).

EAEV description and subcategories (https://www.societyforscience.org/isef/categories-and-subcategories/all-categories/): "Studies of the environment and its effect on organisms/systems … as well as studies of Earth systems and their evolution." Subcategories: Atmospheric Science (AIR), Climate Science (CLI), Environmental Effects on Ecosystems (ECS), Geosciences (GES), Water Science (WAT). **No subcategory mentions hazards, disasters, fire, GIS or remote sensing.** A wildfire-spread + evacuation project lands in AIR or "Other" by default.

ENEV (https://www.societyforscience.org/isef/categories-and-subcategories/environmental-engineering/): "processes and infrastructure to solve environmental problems in the supply of water, the disposal of waste, or the control of pollution" — subcategories are bioremediation, land reclamation, pollution control, recycling, water resources. Not a fit.

### 1.2 Ranking

| Rank | Category / subcat | Why it fits | Why it fails | Net |
|---|---|---|---|---|
| **1** | **SFTD / ALG** (secondary framing: HMC for the operator console) | Judge pool is software/CS professionals; the things WildfireGuardian does best are methodological and systems-level: fire-grouped LOGO-CV, the decision-shift metric (42 of 458 origins reach a refuge only with forecast-aware routing; 2 with no route), perturbation/dilation robustness, network-drift measurement, three-region replication under identical rules, a `make verify`-gated registry of ~260 numbers. These map 1:1 onto the **engineering rubric's** "prototype has been tested in multiple conditions/trials" and "prototype demonstrates engineering skill and completeness" (Execution, 20 pts) and "exploration of alternatives" (Design, 15 pts) (https://www.societyforscience.org/isef/grand-award/criteria/). Recent SFTD/SOFT first awards reward either provable algorithmic novelty or a validated end-to-end system with a novel architectural idea and honest evaluation (see §3). | The components (HistGradientBoosting, Dijkstra on a time-expanded graph) are off-the-shelf; SFTD judges will ask "what is the algorithm contribution?" The answer must be the **coupling** — a calibrated P(ignite) surface converted into a time-varying cost on a time-expanded pedestrian/vehicle graph with rescue-side feasibility and budget — plus the evaluation protocol, not the components. A wildfire-ML project that looked like "NASA CSV → RF/TabNet" (Taghizada & Abdinli 2025, SOFT031T) got 4th. | **Best expected score.** |
| 2 | EAEV / AIR (or OTH) | Six years of wildfire-ML precedent; NatGeo Geospatial and NOAA special awards flow to this category. | First awards go to field/lab earth science or to systems with self-collected ground truth (Vemuri 2024: 1,200 soil samples across 7 farms). Wildfire-ML record: 2nd (2023), 3rd (2023), 4th ×3 (2021, 2022, 2022), unplaced ×6 (2024–26) incl. **FireChain 2026**. EAEV judges (geoscientists/meteorologists) will interrogate ERA5 resolution, six-fire sample, label geometry, and treat routing as "engineering, not science". | Choose only if ISEF-year work adds genuine earth-science content (e.g., GK2A-derived fire weather validated against station data, field fuel data). |
| 3 | ROBO | Definition: "machine intelligence is paramount to reducing the reliance on human intervention." | 2023–26 first awards are physical robots, exoskeletons, rocket-landing control, hyperspectral robots. A decision-support console is not a machine; judges will ask where the robot is. | No. |
| 4 | MATH | Time-expanded-graph evacuation could be cast as applied optimisation (Hou 2023, MATH036, hurricane evacuation traffic model — unplaced). | WildfireGuardian is empirical; MATH judges want theorems or new mathematical objects. | No. |
| 5 | ETSD | Evacuation projects have landed here (Jamaldinian 2022, ETSD032; Mohammed 2023, ETSD042, 4th). | Category is statics & dynamics / engineering mechanics; no fit for software. | No. |
| — | EBED, ENEV, CBIO, BEHA | — | No hardware; not water/waste/pollution; not biology; not behaviour. | No. |

**Recommended framing inside SFTD:** an *engineering* project (Research Problem / Design & Methodology / Construction & Testing rubric), titled around the coupling and the decision metric, e.g. "Forecast-conditioned time-expanded routing for household-level wildfire evacuation and rescue: measuring when the forecast changes the decision." The "honest evidence registry" is not a scoring line by itself; it becomes evidence under Execution ("reproducibility of results") and Interview ("understanding interpretation and limitations of results").

<!-- forbidden-ok: Chen -->
**Special awards are category-agnostic and should be targeted from SFTD:** AAAI (awarded to the Korean SFTD059T evacuation project in 2026), National Geographic Excellence in Geography & Geospatial Science (won by wildfire-ML EAEV projects in 2023 and 2024), ASA, NOAA "Taking the Pulse of the Planet" (Angela Chen 2021). Whether NOAA restricts to EAEV: UNVERIFIED.

**README action:** change "ISEF (Systems Software)" (README.md line 197) and "Systems Software category" (line 494) to "ISEF Software Design (SFTD), Algorithms".

---

## 2. Competitive landscape 2021–2026 (ISEF Projects Database, queried 2026-09-03)

Method: POST search on abstracts.societyforscience.org for keywords wildfire / wildfires / forest fire / bushfire / evacuation / disaster response / elderly / fire spread, years 2021–2026, all abstracts; 142 unique rows, 56 fire/evacuation/disaster-relevant; abstracts fetched for 43. Full list in `research/r2/landscape_raw.txt`. Award column = grand award only (special awards noted in parentheses).

### 2.1 Direct neighbours (spread prediction, evacuation, satellite fire detection, disaster routing)

| Year | Booth / category | Project | Grand award | What it did |
|---|---|---|---|---|
<!-- forbidden-ok: XGBoost -->
| 2026 | **EAEV039** | **FireChain: A Satellite-Driven Deep Learning System for Autonomous Wildfire Response** — K. Bahl, University School, OH | **None** (NC State summer-camp scholarship) | Three layers: ConvLSTM on 1-h GOES sequences for detection; U-Net + temporal attention for spread at four horizons with physics-based loss penalties (monotonicity, ROS ceiling, wind alignment); **conformal prediction bounds feed a routing optimizer** that scores candidate fireline locations with XGBoost on federal fireline-effectiveness records. Claims earlier detection than the operational product and "competitive" spread prediction vs a published benchmark. (https://abstracts.societyforscience.org/Home/FullAbstract?projectId=28121) |
| 2026 | **SFTD059T** | **Development of an FDS-Grounded Risk-Aware Evacuation Route Design and Visualization System for Incident Support** — Seo, Ko, Lee, Gyeonggibuk Science High School, **South Korea** | **None** (AAAI student membership special award) | Building-scale: OpenCV floor-plan recognition (IoU 0.90), lightweight fire/toxic-gas spread model trained on FDS outputs, **A\* with time-varying risk in the cost**, Raspberry Pi display; multi-floor hazard transfer; 12-case "truth-backed evaluation pack". Prioritises cumulative hazard exposure over shortest distance. (https://abstracts.societyforscience.org/Home/FullAbstract?projectId=27978) |
| 2026 | ENEV035 | A Multimodal Late-Fusion of Weather Data and Satellite Imagery for Wildfire Prediction — H. Kim, Stevenson School | None | 413-incident weather model + EfficientNetB0 on ~6,300 satellite images, late fusion. Occurrence, not spread. |
<!-- forbidden-ok: XGBoost -->
| 2026 | EAEV037 | ML Model for Predicting Fire Probability in Global Peatlands — Veerichetty | None | XGBoost, 2016–22, daily global peatland fire probability. |
| 2026 | PHYS082 | FireAIDSS: Real-Time In-Situ Reconstruction of Wildfire Thermofluid Dynamics via Physics-Constrained Inverse PDE — Y. Gong, Shanghai | **3rd** | Physics inverse modelling of fire thermofluids; not routing. |
| 2025 | SOFT031T | Fire Radiative Power Prediction Using Ensemble and Deep Learning Models With Explainable AI — Taghizada & Abdinli, Azerbaijan | **4th** | NASA FRP CSV, Random Forest + TabNet, 5-fold CV, r² > 0.6. The cautionary case for a wildfire project in SOFT/SFTD. |
| 2025 | EAEV070 | MLP to Identify Optimal Camera Locations for Early Wildfire Detection — Govindaraju, OR | None | Camera-siting from risk index, topography, population. |
| 2025 | EBED032 | AI-driven thermodynamics-based IoT sensor network for ultra-early wildfire detection — Honary | **2nd** | Hardware refractive-index heat-signature sensing. |
| 2024 | EAEV053 | Novel Wildfire Spread Prediction Model Using Spatio-Temporal Analysis and Time-series Forecasting — K. Yan | None | GAN augmentation of the Next-Day-Wildfire-Spread satellite set (14,655 → 62,000 scenarios). |
| 2024 | EAEV044 | Comparative Analysis of ML Models for Wildfire Prediction — B. Kong | None | Ten models + CTGAN augmentation; occurrence classification. |
| 2024 | ETSD041 | Low-Cost Rapid-Response Rocket-Launched UAV for Wildfire Hotspot Detection — J. Zhao, Canada | **2nd** (+CAST) | Hardware. |
| 2024 | ROBO035 | Developing Practical Early Countermeasures to Wildfires: An Explainable AI Approach — R. Ide | None | XAI on wildfire drivers. |
| 2024 | EAEV058 | Post-wildfire vegetation recovery, ConvLSTM tensor regression — J. Liu | None (NatGeo Geospatial) | Post-fire NDVI forecasting. |
| 2023 | **EAEV065T** | **Comprehensive Dataset … for Next-Day Wildfire Spread Prediction** — Goel & Singirikonda, TAMS, TX | **2nd** | Re-gridded VIIRS fire mask to 375 m with DAYMET features; CNN-LSTM next-day spread. Dataset construction was the contribution. (https://abstracts.societyforscience.org/Home/PrintPdf/24159) |
<!-- forbidden-ok: XGBoost -->
| 2023 | EAEV041 | Predicting Large Wildfires Using ML Towards Environmental Justice via Remote Sensing — N. Agrawal, IL | **3rd** (+NatGeo, scholarships) | 2,109 fires / 20 yr, MODIS + reanalysis, XGBoost 90.4 % accuracy; later published in *Remote Sensing* 15(23):5501 (https://doi.org/10.3390/rs15235501). |
| 2023 | MATH036 | Mathematical model for traffic-flow risk in Hampton Roads emergency evacuation — K. Hou | None | Macro traffic model, hurricane evacuation. |
| 2023 | ETSD042 | Unbind the Blind: Emergency Evacuation Solution for the Visually Impaired — M. Mohammed | **4th** | Guide cane for house-fire escape. |
| 2022 | EAEV052T | It's Flaming Out: Using AI to Emulate Critical Aspects of Wildfire Growth — Bhowal & Singh, WA | **4th** | Perimeter propagation from met + topo + initial perimeter; target f1 ≥ 0.7 over 24 h. |
<!-- forbidden-ok: Chen -->
| 2022 | EAEV007 | ML model to predict wildfire risk and key drivers in California — A. Chen | **4th** (+ASA 1st, AMS HM) | Wavelet analysis + random forests on 1984–2018 burn area by climate division. |
| 2022 | ETSD032 | Fire, Smoke and Evacuation Modeling: The Ideal Theater — Jamaldinian | None | RSET/ASET of a theatre. |
| 2021 | EAEV111T | Forest Guard: sensor + AI fire-prone mapping, early detection, direction-of-spread, mobile app — Agnihotri & Mittal, India | None | $20 sensor modules, acoustic + environmental detection, GSM-IoT alerts. |
<!-- forbidden-ok: Chen -->
| 2021 | EAEV064 | Wildfire severity vs drought (sc-PDSI), wavelets + ML — A. Chen | **4th** (+NOAA 2nd) | Statewide severity, not spread. |
| 2021 | EAEV032 | How Do We Save Our Lives? Realistic Evacuation Issues — K. Takahashi, Japan | None | Tsunami evacuation with secondary hazards (collapse, liquefaction). |
| 2021 | ENEV010T | Project TetreNet: nanosatellite network + computer vision for wildfire mitigation — Bichal et al., TX | None | Detection concept. |
| 2021 | ROBO049 | FyreWatch: deep learning on satellite data for wildfire conditions — Mangat, Canada | None | Binary risk classification. |

Non-ISEF neighbours worth knowing: **Guardian Grid** (Doral Academy of Northern Nevada; Samsung Solve for Tomorrow 2026 national winner, $100k) — smoke detection from fire cameras, drone verification, real-time boundary mapping, automated alerts and traffic-signal adjustment for evacuation (https://thisisreno.com/2026/04/doral-academy-wildfire-detection-system/); **Fire Up** (A. Jha, Arcadia HS; Congressional App Challenge 2025 CA-28) — AI prediction, live detection, evacuation planner avoiding danger zones (https://chu.house.gov/media-center/press-releases/rep-chu-announces-winners-2025-congressional-app-challenge).

"Elderly" hits in the database (2021–26, ~60 rows) are all fall detection, dementia, virtual assistants, gait — **no project couples elderly vulnerability to disaster evacuation or rescue**. That gap is real.

### 2.2 What WildfireGuardian does that none of them did

1. **Household-level, person-centred evacuation + rescue on real road networks with a forecast-conditioned time-expanded graph.** FireChain routes *crews to firelines*; SFTD059T routes *people inside a building*; Hou routes *traffic*. Nobody routes rural households — with walking speed, refuge capacity, vehicle depots and a rescue-side feasibility/budget — against a forecast hazard surface at landscape scale.
2. **A decision-shift metric.** "42 of 458 origins reach a refuge only when the router accounts for where the fire will be; 2 have no safe walking route" is a statement about *when the forecast changes the decision*. No competitor reports anything of this form; FireChain reports "favored historically effective fireline locations above ablation baselines".
3. **Fire-grouped leave-one-fire-out CV on real Korean fires (n = 6) with per-fold AUC reported (0.68–0.97).** Goel/Singirikonda and Yan train/test on pooled satellite patches; Taghizada uses random K-fold; Agrawal uses a random split. Fire-grouped CV is the honest protocol and should be argued explicitly.
4. **Three-region replication under identical rules, with OSM-completeness covariates** (walk-network coverage 32.6 / 99.2 / 81.5 %), plus network-drift and dilation/perturbation robustness. No competitor reports a sensitivity analysis of the routing to map or forecast error.
5. **A verification-gated numbers registry and a public withdrawn-claims record** (the 44× ratio; the Rothermel ~9 % result). This is unusual at any level; in the interview it converts directly into "understanding interpretation and limitations of results".
6. **Elderly / mobility-impaired focus tied to a real national event** (2025 Korea fires: 32 deaths, 37,000+ displaced — https://en.wikipedia.org/wiki/2025_South_Korea_wildfires).

### 2.3 What they did that WildfireGuardian has not (judge will ask)

1. **Detection is not in the loop as a model.** FireChain trained its own GOES detector; WildfireGuardian consumes FIRMS. Fine, but say so.
2. **Uncertainty is not propagated into routing.** FireChain uses conformal bounds as time-window constraints; SFTD059T uses time-varying risk in A\*. WildfireGuardian has a P(ignite) surface and perturbation studies, but no calibrated uncertainty band on the route itself. This is the most obvious ISEF-year addition (and it is methodology-compatible with the "same methodology" continuation rule if planned now).
3. **Physics-informed constraints.** FireChain's loss penalties (monotonicity, ROS ceiling, wind alignment) and FireAIDSS's inverse PDE are the "scientific principle" content EAEV/PHYS judges reward. WildfireGuardian retired its Rothermel model; a hybrid check (e.g., physics-plausibility filter on the ML surface) is a cheap credibility win.
4. **Benchmark comparison.** Goel/Singirikonda and Yan compare against the Google "Next Day Wildfire Spread" benchmark; FireChain claims "competitive against the published benchmark". WildfireGuardian's AUC has no external benchmark reference; add one (even a negative one — Korean fires vs a US-trained baseline).
5. **A hardware/field artefact.** SFTD059T shipped a Raspberry Pi panel; ExpressBuddy (SFTD 1st 2026) shipped an on-device pipeline for Chromebooks. The offline single-file console (web/finals.html) is the equivalent; make it visibly a deployable artefact, not a slide.

---

## 3. Recent first/second Grand Award winners in SOFT/SFTD and EAEV (2023–2026) and why they won

Source: full-award press releases (https://www.societyforscience.org/press-release/regeneron-isef-full-awards-2023/, …-2024-full-awards/, …-2025-full-awards/, …-2026-full-awards/) and abstracts (abstracts.societyforscience.org).

### SOFT / SFTD

| Year | Award | Project | Why it won (from abstract) |
|---|---|---|---|
| 2023 | 1st | H. Avlani — *Analyzing the Effect of Mid-Circuit Measurement on Spectator Qubits* | New benchmarking method (interleaved randomized benchmarking variant) run on real IBM hardware; "sheds light on a never before seen type of quantum error and discovers a major deficiency in current quantum simulators." Novel method + real-system measurement + a falsified assumption. |
| 2024 | 1st (+ $50k Regeneron Young Scientist) | M. Wei — *Solving Second-Order Cone Programs in Matrix Multiplication Time* | Provable algorithmic improvement: approximate search direction + cone-splitting, "outperforms the previous best SOCP algorithm by a factor of √(number of constraints)", convergence proved. |
| 2025 | 1st | R. Sivaraman — *HM-Detect: Murmur Detection … Novel C²-LSTM Architecture* | New feature set (filterbank energies, spectral subband centroids) + a new two-memory-channel LSTM for multi-modal signals; validated on clinically verified recordings. Architecture novelty + clinical validation. |
| 2025 | 2nd | F. Lopuszanski — *Gate OS: Secure Rust Exokernel*; A. Zhang — *EnAct: multi-agent VLM guidance for vision-impaired*; H. Westemeier — *Integrity: artificial-image classification* | Gate OS: full OS with static analysis + benchmarks on real x86-64 hardware. EnAct: multi-agent VLM architecture with real-time 3D reach checking (YOLO-World + Depth Pro) for a concrete safety task. Systems completeness + a named architectural idea. |
| 2026 | 1st | Z. O'Leary — *M.A.N.T.I.S — Muon Analysis for Non-Invasive Tomography*; Javangula & Shekhar — *ExpressBuddy: AI companion with impediment-aware speech processing* | ExpressBuddy: on-device DSP + WebAssembly VAD (STFT + LSTM/GRU) that preserves dysfluent pauses, emotion-mirroring vision pipeline, designed for low-compute Chromebooks in noisy classrooms — engineering under real constraints for a defined user group. M.A.N.T.I.S abstract not fetched (UNVERIFIED detail). |

Pattern: SFTD first awards go to (a) provable/algorithmic novelty, or (b) a complete system with a **named architectural idea**, real-world validation and explicit constraints. Domain-application projects using stock models without a named idea land 3rd–4th.

### EAEV

| Year | Award | Project | Why it won |
|---|---|---|---|
| 2023 | 1st | F. Borneff — *Effects of Climate Change on Arctic Rivers* | New method to compute spring-thaw key dates from air temperature, discharge and satellite sea-ice for all six major Arctic rivers 1978–2022; quantified trends (up to 0.94 d/yr earlier). Field-scale earth science with a clean quantitative result. |
| 2023 | 1st | P. Hinkle — radon in household water and mitigation | Measurement + mitigation testing. |
| 2023 | 2nd | Goel & Singirikonda — next-day wildfire spread dataset + CNN-LSTM | The only wildfire-spread 2nd in the window; contribution was a higher-resolution dataset, not the model. |
| 2024 | 1st (+EUCYS award) | N. Vemuri — *ANOMaLY: real-time globalized system for agricultural N₂O emissions* | Self-collected ground truth (1,200+ soil samples, 7 farms, 6 months) → new Sentinel-2 spectral indices → PDE-informed neural network explaining ~80 % of regional N₂O variation vs ~30 % prior. **A software/data system won EAEV 1st because it had its own field data and a physics-informed model.** |
| 2024 | 1st (+ Gordon E. Moore $50k) | Huang & Ou — acoustic microplastic filtration | Lab engineering with measured removal. |
| 2025 | 1st | M. Haddad — ferrofluid oil-spill cleanup | 120+ trials, ANOVA/Tukey, 2–6 % → ≥30 %/>90 % removal; continuation project. |
| 2025 | 1st | L. Agrawal — water purification | (abstract not fetched) |
| 2026 | 1st | M. Eagleton — prebiotic uracil stability in impact hydrothermal systems; T. Jin — animal-bone water filtration | Lab geochemistry / materials with replicated trials. |
| 2026 | 2nd | Thogerson & Osborne — wildfire smoke effects on wheat/rice/broccoli (microscopy + germination) | Lab experiment; the only wildfire 2nd in 2026 — and it is biology, not modelling. |

Pattern: EAEV top awards go to measured earth-system science or to models anchored by **self-collected** ground truth. Pure satellite/reanalysis ML wildfire projects top out at 2nd and usually place lower or not at all.

---

## 4. ISEF rules that bite this project

### 4.1 The 12-month window and what counts as "this year's work" for ISEF 2027

- Rule text (2026–27): "That project may include no more than 12 months of continuous research and may not include research performed before January 2026." (https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/). Search-summarised phrasing: judged only on work over 12 continuous months beginning no earlier than January 2026 and ending May 2027; nothing older than 18 months before the fair. FAQ: "The start date of your project is when you begin to collect data for your experiment. The literature review and the design of your study will occur prior to your start date." (https://www.societyforscience.org/isef/international-rules/faq/)
- Repo facts: first commit 2026-05-27 (Rothermel scaffold); Round 2 submitted 2026-07; Round 3 2026-08; Session 22 on 2026-09-02. ISEF 2027 dates: UNVERIFIED (typically mid-May).
- Consequence: **all KCF 2026 work is inside the window** (after Jan 2026). 2026-05-27 → mid-May 2027 is essentially exactly 12 months, so there is **zero slack**. Two clean options:
  - (A) One project year: declare the data-collection start as 2026-05-27, **freeze new experimentation by ~2027-05-01**, and present KCF + ISEF-year work as one project. No Form 7. The "one year's work only" certification on the abstract form is then true.
  - (B) Treat the KCF-submitted state (tag `round2-submitted`, 2026-07) as the "previous project" and the ISEF entry as a **continuation** (Form 7 with the KCF abstract + research plan attached; display board and abstract reflect only current-year work; "reference to past work on the display board must be limited to summative past conclusory data and its comparison to the current year data set. No raw data from previous years may be publicly displayed" — DS rules, https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/DS-Rules.pdf). This is only worth doing if the ISEF-year work is a genuinely new question (e.g., uncertainty-propagated routing) — FAQ: "if there is anything you learned in your last study that is helping you in this study … it is considered a continuation."
  - Recommendation: **(A)**, with a dated logbook entry and a written freeze date. Note the Form 7 wording requires listing "Change in goal/purpose/objective … Changes in methodology … Variable studied" (https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/All.pdf) — keep that table filled in anyway as insurance.
- **Affiliate-fair lock.** FAQ (summarised): after the affiliated fair, additional data may be collected only "using the same methodology that was previously approved by the affiliate fair, with the project presented at ISEF being the same project that won at the affiliate fair with no new variables or experimental procedures." → **The autonomous agent loop must not introduce new variables/procedures after the Korean delegation selection event.** Date of that event: UNVERIFIED. Plan every methodological addition (uncertainty bands, GK2A weather, physics filter) *before* it.
- Forms 1, 1A, 1B (Adult Sponsor checklist, Student checklist, Research Plan + Approval) are required for every project; SRC/IRB *pre*-approval is required only for human participants / vertebrates / PHBA / tissue. A pure data/software project can start without SRC approval, but the Research Plan should exist and be dated. It does not yet; write it now with the seven required sections (Rationale; Research Question/Engineering Goals; Materials; Procedures; Risk and Safety; Data Analysis; Bibliography — 2026–27 edit, https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2027/Rules/FINAL-Rule-Modifications-for-2026-27.pdf).
- Form 2C (Regulated Research Institution) is needed only if work was done or mentored at a university/industry site. Consultations with professors are not RRI work; running code on a university machine would be. Form 2B (Qualified Scientist) is optional but adds credibility if a professor signs.

### 4.2 AI-usage disclosure (this is the sharp edge)

Verbatim, 2026–27 Eligibility #8: "Artificial Intelligence (AI) may be used as a resource but must be cited and given proper acknowledgment. A student is expected to do independent work and all materials presented must be in the researcher's own words. A student may not use generative AI to write the research plan, abstract, poster or to create citations (it is known to hallucinate and falsify references)." (Rule modifications PDF above; also https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/).

Generative-AI Use Table (Oct 2025, https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/Generative-AI-Use-Table.pdf), rows that apply:
- "Use AI to write initial code for your project" — Yes, "only with explicit citation stating which portions of the code were AI generated and with a log of the prompts."
- "Use AI to help identify appropriate statistical tests or software tools" — Yes, "requires a log of your prompts as part of your research notebook. (Interpretation of data must be done by the student researcher)."
- "Use generative AI to initially write the research plan, abstract, paper or poster" — No. "Guidance or refinement after the initial document has been completed can be done with explicit citation and a log."
- "Use AI to produce your conclusions, future steps, etc." — No.
- "Ask generative AI to produce a flowchart, graphic, or image" — Yes, "clearly marked as AI-generated and with explicit citation."
- "Affiliated fairs may adopt their own, more strict, policies." Korea's affiliate policy: UNVERIFIED.

New **Form 2A — Student Support Disclosure**, "required for all projects. It can be filled out before or after experimentation by the finalist" (2026–27 modifications). This is where the agent loop gets disclosed.

Consequences for WildfireGuardian:
1. The repo's session reports, README prose and much code are AI-authored. That is permitted **only** if (a) an AI-contribution ledger states which code portions were AI-generated, (b) prompt logs are kept as part of the research notebook, and (c) the research plan, abstract, poster and all display text are written by 박시영 first, with AI limited to grammar/syntax edits afterwards.
2. The autonomous cloud routine produces exactly the kind of "AI-produced conclusions" the table prohibits if its outputs are presented as the student's conclusions. Structure the routine's outputs as *candidate analyses* that the student reviews, re-runs, and writes up; keep the routine's run logs as the prompt log.
3. Interview criterion (25 pts) includes "degree of independence in conducting project" (https://www.societyforscience.org/isef/grand-award/criteria/). Judges at ISEF 2027 will ask directly. The honest answer ("I designed the experiments and the evaluation protocol; an AI coding agent implemented X, Y, Z under my prompts, logged here; I verified every number through `make verify`") is defensible only if the ledger exists.
4. Figures: every graphic must be labelled "Chart created by Finalist using …"; AI-generated graphics must be marked as such (DS rules, Photograph/Visual Image requirements).

### 4.3 Display & Safety rules for a software + map demo

From the 2025–26 DS rules (https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/DS-Rules.pdf) and the DS page (https://www.societyforscience.org/isef/international-rules/display-safety-rules/):
- **No live internet**: "Active Internet or email connections as part of displaying or operating the project at ISEF. Exceptions will only be made if requested by email to isef@societyforscience.org and approved in advance by the Display & Safety Committee." → the live FIRMS trigger, Overpass fetches, email/SMS channel cannot run live; demo from cached inputs (web/finals.html already offline — correct).
- **No URLs, QR codes, addresses**: prohibited on display — "Postal addresses, World Wide Web, email and/or social media addresses, QR codes, telephone and/or fax numbers." → no GitHub link on the poster.
- **Digital devices must be shown in entirety at inspection and not altered afterwards**: finalists using a "digital display/device outside of a project board must be prepared to show these materials in their entirety … may not be altered in any way after the Display & Safety inspection has been completed." Examples listed include "computer code … software program/simulation." → freeze the demo build before inspection; no last-minute patches.
- **Batteries**: "battery packs over 100 watt-hour capacity" prohibited; large power banks are out. Power: the DS rules describe 120/220 V AC supply rules, but the 2026 Project Material Guidelines state AC power will not be supplied to displays (https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Resources/Project-Material-Guidelines.pdf, per search summary) — plan for a fully charged laptop plus a ≤100 Wh pack. Which applies at ISEF 2027: UNVERIFIED; ask the delegation.
- **Photos of people**: any photo of a person other than the finalist needs a signed release in the notebook; no photos or identifying info of human-study participants. → do not show the firefighter; keep the N=1 consultation anonymous on the board.
- **Graphics attribution**: all graphics not created by the finalist cited individually (APA, URL/DOI); finalist-created graphics labelled "created by Finalist using …". OSM tiles/data, ERA5, FIRMS, SRTM/DEM layers all need attribution lines.
- **Abstract**: only the SRC-stamped Official Abstract may be displayed; the word "abstract" may not appear elsewhere on the board; no handouts for judges.
- **Forms at the booth**: Form 1C/2C and Form 7 must be vertically displayed if applicable; the 2026 sample abstract form asks "This abstract … represents one year's work only" and "This project is a continuation of previous research" — the answers must be consistent with option (A)/(B) in §4.1.
- Fits: booth max 122 cm wide × 76 cm deep; the rescue/evacuation map poster must fit that.

### 4.4 Human participants — Form 4

Definition: a human participant is "a living individual about whom an investigator conducting research obtains (1) data or samples through intervention or interaction with individuals(s) or (2) identifiable private information." IRB review "before any interaction (e.g., recruitment, data collection) with human participants may begin." (https://www.societyforscience.org/isef/international-rules/human-participants/)

Exempt studies (verbatim items): (1) "Student-designed Invention, Prototype, Computer Applications, Engineering/Design Project or Consumer Product Testing in which the student researcher (or researchers if a team) is the only person testing the invention, prototype, computer application or consumer product and the testing does not pose a health or safety hazard" (extends to a single adult guardian/sponsor tester); (2) data/record review of public datasets with no interaction; (3) public behavioural observation without interaction or identifiable data; (4) pre-existing de-identified data. And, critically: **"This is not intended to apply to receiving professional feedback from experts in the field of study prior to experimentation."** — i.e., expert feedback is outside the human-participant framework altogether.

Applied to WildfireGuardian:
- **Firefighter consultation (N=1, 2026-08-28) and professor consultations (임정호·이양원·안희영)** → *not* human-participants research, provided they are presented as expert feedback that shaped design, not as collected data with findings. `docs/firefighter_consultation.md` §0 already enforces exactly this ("This document produces no numbers … expert judgment, not measurement"). Keep it that way; do not tabulate, code or quantify the statements. No Form 4.
- **Operator usability test** (officials/firefighters using the console; timing, decisions, questionnaires, think-aloud) → **is** human-participants research (data obtained through interaction) → Form 4 + Research Plan human-participants section + informed consent, **IRB approval before recruiting**. If run without prior approval it cannot be presented and can fail the SRC review. If wanted for ISEF, design it now, get the school/affiliate IRB signature, then run it. Adults, minimal risk, no minors → simplest possible IRB path, but not skippable.
- **Live alert channel to real residents**: 2026–27 human-participant prohibition: "Students are prohibited from disclosing research data from their study and/or from providing advice … to participants without direct supervision." Any pilot that sends evacuation advice to real people is a human-participant study *and* touches this prohibition. The code-enforced `DEMO_RECIPIENT`-only rule (HANDOFF §5) is the right posture; keep it.
- Surveys of residents (e.g., mobility, refuge preference) → Form 4; if any respondent could be a minor, written parental permission with the survey attached.

### 4.5 Other eligibility points

- Team vs individual: fine either way; team projects are judged on "contributions to and understanding of project by all members."
- The affiliate route (KCF 은상 → KOFAC/ISEF-Korea selection interview) is as stated by the user; the mechanism, dates and any affiliate-specific AI or continuation policy are UNVERIFIED here. South Korea sent **58 finalists to ISEF 2026, the largest non-US contingent** (https://www.societyforscience.org/press-release/regeneron-isef-2026-special-awards-ceremony/, per search summary) — the delegation selection is itself highly competitive.

---

## 5. Recommended actions (ranked)

| # | Action | Why | Effort | Priority |
|---|---|---|---|---|
| 1 | Start an **AI-contribution ledger + prompt-log archive** now (per module: who wrote it, which prompts, which routine run), and require the cloud routine to append to it on every run. | 2026–27 rule + Generative-AI table + Form 2A; interview "degree of independence." Without it the project is un-presentable at ISEF. | days | P0 |
| 2 | Student-authored **Research Plan** (7 sections) and a dated logbook with start date 2026-05-27 and a planned experimentation freeze (~2027-05-01); complete Forms 1/1A/1B now. | 12-month window has zero slack; forms should predate the ISEF-year work. | days | P0 |
| 3 | Rename the target category everywhere to **Software Design (SFTD) / Algorithms**; rewrite the ISEF-facing title around the coupling + decision-shift metric. | SOFT no longer exists; framing determines judge pool. | hours | P0 |
| 4 | Plan the ISEF-year methodology additions **before** the Korean selection event: (a) calibrated uncertainty band on the hazard surface propagated into routing (conformal or bootstrap), (b) external benchmark comparison for the spread model, (c) a physics-plausibility filter or hybrid check. | Directly answers the three gaps vs FireChain/SFTD059T; "no new variables or procedures" after the affiliate fair. | weeks | P1 |
| 5 | If an operator usability study is wanted, write the protocol + consent, get IRB/Form 4 signed, then run it. Otherwise explicitly do not run one. | Human-participant pre-approval is non-negotiable. | days (paperwork) | P1 |
| 6 | Booth-compliance pass on the demo: offline-only build frozen before inspection; no URLs/QR; attribution lines for OSM/ERA5/FIRMS/DEM; "created by Finalist using …" on every figure; no firefighter photo; ≤100 Wh battery. | DS rules. | hours | P1 |
| 7 | Prepare a one-page "why not EAEV" note and the Form 7 comparison table as insurance, even under option (A). | Category challenges and continuation questions come up at SRC review. | hours | P2 |
| 8 | Target special awards from SFTD: AAAI, NatGeo Geospatial, ASA. | Category-agnostic; wildfire-ML and evacuation projects have won them. | hours | P2 |

---

## 6. Sources

Rules and forms
- International Rules hub: https://www.societyforscience.org/isef/international-rules/
- Rules for All Projects (12-month, AI, mentors, 2C): https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/
- Rules FAQ (start date, continuation): https://www.societyforscience.org/isef/international-rules/faq/
- Final Rule Modifications 2026–27 (AI #8, Research Plan sections, Form 2A, human-participant edits): https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2027/Rules/FINAL-Rule-Modifications-for-2026-27.pdf
- Generative-AI Use Table (Oct 2025): https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/Generative-AI-Use-Table.pdf
- Display & Safety rules: https://www.societyforscience.org/isef/international-rules/display-safety-rules/ and https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Rules/DS-Rules.pdf
- Project Material Guidelines 2026: https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Resources/Project-Material-Guidelines.pdf
- Human Participants rules: https://www.societyforscience.org/isef/international-rules/human-participants/
- All 2026 forms (Form 4, Form 7 text): https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/All.pdf
- 2026 abstract/certification form with category list: https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/2026-22-Categories.pdf
- Grand Award judging criteria: https://www.societyforscience.org/isef/grand-award/criteria/

Categories
- Categories & subcategories: https://www.societyforscience.org/isef/categories-and-subcategories/ ; all categories: https://www.societyforscience.org/isef/categories-and-subcategories/all-categories/
- Software Design: https://www.societyforscience.org/isef/categories-and-subcategories/software-design/
- Environmental Engineering: https://www.societyforscience.org/isef/categories-and-subcategories/environmental-engineering/

Awards
- 2023 full awards: https://www.societyforscience.org/press-release/regeneron-isef-full-awards-2023/
- 2024 full awards: https://www.societyforscience.org/press-release/regeneron-isef-2024-full-awards/
- 2025 full awards: https://www.societyforscience.org/press-release/regeneron-isef-2025-full-awards/
- 2026 full awards: https://www.societyforscience.org/press-release/regeneron-isef-2026-full-awards/
- 2026 special awards: https://www.societyforscience.org/press-release/regeneron-isef-2026-special-awards-ceremony/
- 2024 winners feature (Wei): https://www.snexplores.org/article/2024-regeneron-isef-winners-bioelectronics-genetics-math

Projects Database (abstracts.societyforscience.org; `projectId` links)
- FireChain 2026: https://abstracts.societyforscience.org/Home/FullAbstract?projectId=28121
- FDS-grounded evacuation 2026 (Korea): https://abstracts.societyforscience.org/Home/FullAbstract?projectId=27978
- Goel & Singirikonda 2023: https://abstracts.societyforscience.org/Home/PrintPdf/24159
- Agrawal 2023 (and paper): https://doi.org/10.3390/rs15235501
- Taghizada & Abdinli 2025: https://abstracts.societyforscience.org/Home/FullAbstract?projectId=27080
- Forest Guard 2021: https://abstracts.societyforscience.org/Home/FullAbstract?Category=Any+Category&AllAbstracts=True&FairCountry=Any+Country&FairState=Any+State&ProjectId=20232
- Tremsin 2018 (EAEV Best of Category, wildfire early warning): https://abstracts.societyforscience.org/Home/FullAbstract?ProjectId=15978
- Other rows: pid values listed in `research/r2/landscape_raw.txt`

Non-ISEF
- Guardian Grid (Samsung Solve for Tomorrow 2026): https://thisisreno.com/2026/04/doral-academy-wildfire-detection-system/
- Fire Up (Congressional App Challenge 2025): https://chu.house.gov/media-center/press-releases/rep-chu-announces-winners-2025-congressional-app-challenge
- TriplePundit 2024 ISEF wildfire projects: https://triplepundit.com/2024/wildfire-solutions-science-fair/
- 2025 South Korea wildfires: https://en.wikipedia.org/wiki/2025_South_Korea_wildfires

Local
- README.md lines 197, 494 (category name); docs/HANDOFF_ROUND3.md §5; docs/firefighter_consultation.md §0; git log (first commit 2026-05-27).

---

## 7. UNVERIFIED / not established

- Exact dates of Regeneron ISEF 2027 and of the Korean delegation selection interview (drives the 12-month arithmetic and the "no new procedures after the affiliate fair" lock).
- Whether Korea's ISEF affiliate applies a stricter AI policy than the Society's table.
- Whether AC power is supplied at ISEF 2027 booths (DS rules and Project Material Guidelines read differently for 2026).
- Whether the NOAA special award is restricted to EAEV entries.
- Abstract-level reasons for two first awards (M.A.N.T.I.S 2026; L. Agrawal 2025) — titles only.
- The exact scoring of the 2026 Korean SFTD059T project (special award only; no grand-award placement confirmed from the full-awards page).
- The claim "wildfire spread prediction from satellite imagery consistently produces ISEF finalists" seen on a coaching site is marketing, not evidence; the database shows finalists but few placements.
