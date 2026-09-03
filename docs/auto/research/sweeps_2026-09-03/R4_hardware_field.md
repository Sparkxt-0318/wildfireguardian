# R4 — Hardware / field / experiment integration: necessary or not?

Written 2026-09-03. 45 days to the KCF finals (2026-10-18, Gwangju, offline booth, 5 judges × ~5 min demo + ~5 min Q&A, no wifi). Student alone, physically in Shanghai, plus an autonomous cloud agent loop that can write code but cannot touch hardware.

Repo state read: `README.md` (Round 3), `docs/delivery_channels.md`, `docs/live_pipeline.md`, `docs/firefighter_consultation.md`, `docs/photo_exif.md`, `docs/operator_screen.md`, `docs/finals_demo_plan.md`, `docs/FINALS_DEMO.md`, `docs/HANDOFF_ROUND3.md` §4/§5, `docs/BLOCKERS.md` (GK2A/KMA rows), `docs/gk2a_direction_experiment.md`, `docs/SESSION22_REPORT.md`, the submitted `서식1_최종본_붙여넣기용.md` and `서식2_본문_*.md`, the judge Q&A note. Nothing under the repo or the parent folder was modified.

---

## 0. Bottom line

**Build no hardware.** None of the seven options beats "double down on software rigor" on KCF points per hour, and three of them (edge node, sensors/drones, formal human-subject study) actively conflict with either the submitted design philosophy, the repo's own recorded rules, or the ISEF human-participant rules. The only two additions worth doing are both software and both already half-built in the tree:

1. **GK2A (KMA API-hub) fire-detection ingestion as a second trigger source, run in offline replay against the March-2025 fires, reporting the measured detection-time gap vs FIRMS NRT.** This is the one "sensor" that is real, Korean, quantifiable, already preregistered in `docs/gk2a_direction_experiment.md`, and blocked only on a 15-minute API-key signup by the student (`docs/BLOCKERS.md`, "ACTION FOR JOHN").
2. **One real, gated, recorded delivery send** (the email path already exists and is blocked only by the SMTP-blocked network; a domestic SMS via a Korean aggregator at ₩18 is the cheap add-on) so that "SMS 전달은 모사" — the sentence still in the submitted 서식2 — can honestly become "one message was sent, under the approval gate, and here is the record."

Everything else: no.

The evidence that "ISEF-placing KCF projects have a physical component" is weaker than it looks. KCF's four ISEF grand awards were 2022 4th (project UNVERIFIED), 2023 4th Embedded Systems (blind-pedestrian walking-assist device), 2024 2nd Embedded Systems (CPR audiovisual feedback system), and **2025 3rd in Systems Software — a hand-gesture dementia-prevention app with no hardware**. So the most recent KCF→ISEF placement was software-only, and the 2025 고등부 은상 project that won an ISEF special award was an AI traffic-signal system. Hardware is a category choice (EBED), not a prerequisite. This project is registered against Systems Software and its submitted description says "고령자는 'user'가 아니라 'beneficiary'… 새로운 애플리케이션 설치를 요구하지 않습니다". A device in the elderly household contradicts the submission; KCF's rule that the finals work must not contradict the originally submitted purpose makes that a real risk, not a stylistic one.

---

## 1. Facts that constrain every option (from the repo and the submission)

| Fact | Where | Consequence |
|---|---|---|
| The demo path is **offline replay**, by design; live is "not the fallback". `web/finals.html` is a 2.0 MB single file whose gate forbids `fetch`/XHR/WebSocket/EventSource/serviceWorker/external URLs, even in comments. | `docs/live_pipeline.md` §1; `docs/finals_demo_plan.md` §1 | Anything that needs a network or a browser device API at the booth is fighting the artifact's own tests. Web Serial requires a secure context; `file://` is not one (MDN/WICG), so an LED model cannot be driven from `finals.html` opened as a file without moving to `localhost` and re-gating. |
| Delivery channels are fixed at four: A4 sheet (primary), 마을방송 script, SMS (DEMO_MODE, Twilio trial cannot verify +82), email (live, three locks, verification send never completed because outbound SMTP is blocked on the working network). | `docs/delivery_channels.md` §1, §3, §3-B | The "real send" gap is closable in hours from a home/hotspot network. |
| The firefighter consultation (N = 1) says field channels are 재난문자, 이장 마을방송, and a base-station 무전앱; **no GPS**; and the doc explicitly instructs "**채널 구성 자체는 바꾸지 마십시오** … 그런 통합은 이 프로젝트의 범위에 없습니다". | `docs/firefighter_consultation.md` §7.2 | An edge speaker/lamp node is a new channel. It is against a recorded decision. |
| The hazard surface is fixed (ERA5 ~5-day lag). Making it move needs a real-time weather source: "KMA's public API could, and that is a project, not a parameter." | `docs/live_pipeline.md` §9.1 | Real-time weather ingestion is out of reach by Oct 18; real-time *detection* ingestion is not. |
| GK2A L2 산불탐지(FF) via KMA API-hub is the preferred label source of a preregistered experiment; blocked only on a personal 인증키. NOAA's S3 mirror has L1B only. | `docs/BLOCKERS.md` "ACTION FOR JOHN"; `docs/gk2a_direction_experiment.md` | The one hardware-adjacent item with an existing plan and zero parts. |
| Submitted 서식2 limitations already say: 보행 속도 0.7 m/s is a setting, not a measurement; Tobler slope function is unvalidated for frail elderly; "SMS 전달은 모사이며 실제로 발송하지 않았습니다"; future work lists "30·60·90분 보행 예산에서의 w(t)" and "수혜자 전달 계층(SMS·음성·복지사 연계)의 운영 구현". | `서식2_본문_Ⅲ-붙임.md` lines 213–249 | Any addition should close a limitation the judges have already read, not open a new front. |
| Design philosophy: elderly are beneficiaries; operators are 가족·복지사·지자체; delivery via SMS/전화/복지사 방문/이장. | `서식2_본문_Ⅰ-Ⅱ.md` line 25 | A device the elderly must own or look at is a contradiction. |
| HANDOFF §5 rules: never modify committed artifacts, never re-acquire Yeongdeok OSM, never quote Yeongdeok absolutes without the 32.6 % caveat, etc. | `docs/HANDOFF_ROUND3.md` §5 | Any physical model showing Yeongdeok numbers has to carry the caveat on its face. |
| The KCF finals booth: 5 judges rotate; posters required; reports of wifi being unreliable even when advertised; hours of waiting. Power outlet availability UNVERIFIED. | namu.wiki 한국코드페어 | Anything battery-powered must last a full day; anything fragile will be knocked. |
| KCF Pass/Fail row: 위험성 검토. | rubric (given) | Lithium batteries, loudspeakers, drones add review surface a laptop does not. |

---

## 2. What the two rubrics actually reward

**KCF (100 pts).** Track B (SW 연구) is the honest fit: 연구 목적 20 / 설계·방법론 20 (variable definition & control, difference from prior research) / 데이터 수집·분석·해석 20 (reproducible results, appropriate statistics) / 창의성 20 / 제출 자료 20. Track A's 구현 및 유용성 20 is about "fits intended purpose, feasibility/completeness, resolves the need" — for this project that is the operator-side artifacts (A4 sheet, broadcast script, dispatch list, console), not a gadget.

**ISEF grand-award criteria (100 pts)** ([societyforscience.org](https://www.societyforscience.org/isef/grand-award/criteria/)): Research question/problem 10, Design & methodology 15, Execution 20, Creativity & potential impact 20, **Presentation 35 (poster 10, interview 25)**. Under the Engineering rubric, Execution requires a "prototype … tested in multiple conditions/trials"; under Science, "systematic data collection … reproducible results … appropriate statistical methods". This project scores on the Science/Software reading (LOGO-CV, DeLong CIs, sensitivity sweeps, negative results). A tabletop LED model contributes nothing to Execution under either rubric; it is at best a Presentation prop.

---

## 3. Option-by-option

Scale: KCF value = which rubric rows move, and which direction. Effort assumes the student alone; the agent loop only helps where marked.

### (1) Low-cost edge alert node (ESP32/Pi + LoRa or GSM → village loudspeaker/lamp)

- **KCF value: negative to neutral.** 개발 목적 row rewards "understanding of constraints" — the recorded constraint is that the field already has 이장 마을방송 and municipalities are rolling out 스마트 마을방송 (이장's phone/app → home phone, mobile, outdoor speaker; 군위 launching Nov 2025, 청주, 양양; DK Techin's KakaoTalk-based service with automatic call-back if unread). A student-built speaker node re-implements the municipality's own channel with worse reach and no legal standing. 창의성 does not reward reinventing infrastructure. It contradicts 서식2's beneficiary philosophy if any device goes into the elderly home.
- **ISEF value: low.** It would push the project toward EBED, where a two-board LoRa link with a buzzer is table stakes; the project's real strength (time-expanded routing + honest evaluation) would be judged by the wrong panel.
- **Real-world value: none as built.** The real integration point is the 마을방송 *script* the pipeline already emits (`broadcast.py`, ≤15 chars/line), read by a human on an existing PA, or fed into a 스마트 마을방송 vendor's text-to-speech — that is a partnership, not a board.
- **Cost:** Heltec WiFi LoRa 32 V3 $17.90–19.90 each ([heltec.org](https://heltec.org/project/wifi-lora-32-v3/)); two boards + antennas + speaker/amp + enclosure + battery ≈ $60–90 (≈ ₩80–120k). Korea's LoRa band is KR920-923 MHz, max EIRP +14 dBm ([rfwireless-world](https://www.rfwireless-world.com/terminology/lorawan-frequency-bands-korea-kr)), so the 863–928 MHz variant, set to 922.x MHz. GSM adds a Korean SIM/data plan the student cannot easily open from Shanghai.
- **Build time:** 2–3 weekends for a working demo link; the agent loop can write firmware but cannot flash, test RF, or debug power. Zero automation leverage.
- **Risk:** RF misconfiguration; KC 적합성평가 — personal-use import is exempt for 1 unit not for resale ([rra.go.kr 요건면제](https://www.rra.go.kr/ko/popup/popup_100430.jsp)), but a *pair* of radios plus a demo at a public venue is a grey area (UNVERIFIED whether "1대" is per model or per shipment); lithium batteries must be hand-carried, ≤100 Wh, never checked ([korea.kr](https://www.korea.kr/news/policyNewsView.do?newsId=148940158)); 위험성 검토 row gains content.
- **Shipping:** Buy on Taobao in Shanghai (Heltec is a Chinese vendor; domestic delivery days, price UNVERIFIED on Taobao), hand-carry to Gwangju. Feasible but every hour is the student's.
- **Verdict: do not build.**

### (2) Real SMS / cell-broadcast delivery demo

- **Cell broadcast (재난문자/CBS): impossible, and claiming it would be false.** Transmission authority sits with 행정안전부 and 시장·군수·구청장 under 재난 및 안전관리 기본법 제38조의2; private parties and 이장 cannot originate ([ko.wikipedia 재난문자방송](https://ko.wikipedia.org/wiki/%EC%9E%AC%EB%82%9C%EB%AC%B8%EC%9E%90%EB%B0%A9%EC%86%A1)). The correct framing is the one already in `docs/delivery_channels.md`: the system drafts, an authorized human sends.
- **Twilio:** outbound SMS to KR $0.0524/segment ([twilio.com pricing](https://www.twilio.com/en-us/sms/pricing/kr)); Korea guidelines: numeric sender only, auto-prefixed 009/006, messages tagged [국제발신]/[Web 발신], EUC-KR only, no two-way ([twilio.com/guidelines/kr/sms](https://www.twilio.com/en-us/guidelines/kr/sms)). The repo records that the trial tier cannot verify a +82 number; upgrading needs a paid account. An [국제발신] SMS is also exactly the kind of message rural elderly are told to distrust — a demo that lands as "국제발신" undercuts the story.
- **Domestic aggregator (SOLAPI/CoolSMS):** SMS ₩18, LMS ₩45, 알림톡 ₩13, no monthly fee ([solapi.com/pricing](https://solapi.com/pricing)); requires 발신번호 사전등록 under 전기통신사업법 §84-2 ([solapi guide](https://solapi.com/guides/sms-howtosend)). Whether an individual minor can register their own mobile as sender without a 사업자등록 is UNVERIFIED — check before relying on it; if it needs a business registration, drop SMS and keep email.
- **KCF value: small but real, on 구현 및 유용성 and 제출 자료.** It converts one sentence in the submitted materials ("모사") into a recorded, gated, real event, and gives one honest photo for the poster (phone showing the received draft, with 「재생 모드」 banner visible). It does not change any number.
- **ISEF value: marginal.** Delivery is not what ISEF judges will probe; the routing and evaluation are.
- **Cost:** ₩0 (email) to a few hundred won (SMS). **Build time:** hours — the email script, three locks, and `email_sent.json` record already exist; run `send_dispatch_email.py --confirm-send` from a home/hotspot network that allows outbound SMTP (`docs/delivery_channels.md` §3-B). An SMS channel through SOLAPI is a ~100-line adapter with the same `approval_token` shape as `sms.send`. The agent loop can write it; the student presses send once.
- **Risk:** low, provided DEMO_MODE semantics and the "never transmitted automatically" sentence stay exactly as written.
- **Verdict: do the email verification send (hours). Add domestic SMS only if sender registration is trivially available to an individual. Do not upgrade Twilio. Never say "cell broadcast".**

### (3) Physical booth model — tabletop terrain with LEDs showing the time-expanded hazard and routes

- **KCF value: 창의성/제출 자료 upside, 구현 downside.** Judges see 30 finalists in a hall; a lit terrain is memorable. But: it must carry the Yeongdeok 32.6 % caveat on its face (HANDOFF rule 19), it duplicates what `finals.html` Act 2 ("시간이 도로망을 바꾼다") already does in real geometry, and if it fails mid-rotation the judge's 5 minutes are gone. The rubric row 구현 및 유용성 asks whether the thing "fits the intended purpose" — a light-up model is not an operational artifact.
- **ISEF value: low.** A prop is Presentation (10 poster points at most); ISEF booths are cramped and ship-by-air; Simtable-style sand tables exist commercially ([simtable.com](https://www.simtable.com/); "Sand on fire" tangible platform, [academia.edu](https://www.academia.edu/128387286/Sand_on_fire_an_interactive_tangible_3D_platform_for_the_modeling_and_management_of_wildfires)), so it is not novel.
- **Real-world value: none.**
- **Cost:** ESP32 DevKit ≈ ₩10–15k (UNVERIFIED — devicemart pages did not render), WS2812B 1 m/60 LED ≈ ₩3.2–10.5k per strip (11번가/ICBanq via search), 5 V PSU, laser-cut or 3D-printed contour tiers of the 의성·안동 walk bbox (print/laser service in Shanghai: UNVERIFIED, plausibly ₩50–150k), total ≈ ₩100–200k.
- **Build time:** 3–5 weekends including a control script that replays the same `viz.json` slices over serial. Must NOT be wired into `finals.html` (Web Serial needs a secure context; `file://` is not one; the screen gate would need re-scoping). Drive it from a separate Python script. The agent loop can generate the LED-index-to-cell mapping and the driver; the student does all physical work.
- **Risk:** transport (a 40–60 cm terrain in checked luggage or carry-on from Shanghai), booth power (UNVERIFIED), fragility, and it diverts the last weeks from Q&A preparation, which is where 25 of ISEF's points and most of KCF's Q&A impression live.
- **Verdict: no. The cheapest and most on-message "physical" exhibit is already in the tree: print the 29 A4 dispatch sheets (one per village, one page each), the 마을방송 script, and put a phone on the table showing the received draft. That is the delivery philosophy as objects, costs ₩0, and cannot break.**

### (4) Drone / ground sensor integration (flame/smoke sensors, weather station) feeding the trigger

- **KCF value: negative.** The submission's premise is that the bottleneck is *not* detection ("병목이 탐지나 예보가 아니라 전달과 구조에 있음", 서식1 §3). A smoke sensor says detection is the problem. It also duplicates 산림청's 지능형 산불방지 ICT 플랫폼 (AI camera/thermal + drone linkage, expanding nationwide) — see [boannews](https://m.boannews.com/html/detail.html?idx=105880), [etnews](https://m.etnews.com/20220105000104).
- **ISEF value: negative for the same reason;** and ISEF 2025 already had IoT wildfire-detection projects (e.g., "AI-Driven Thermodynamics Based IoT Sensor Network for the Ultra-Early Detection of Wildfires" — [societyforscience.org full awards](https://www.societyforscience.org/press-release/regeneron-isef-2025-full-awards/)). Competing there means competing on their ground.
- **Real-world value:** a single sensor is meaningless at 375 m grid scale; a weather station cannot replace ERA5 in the trained model without retraining.
- **Cost/time/risk:** any drone >250 g needs the 4종 online course; >2 kg needs 기체신고 ([drone.onestop.go.kr](https://drone.onestop.go.kr/introduce/systemintro2/), [easylaw](https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?popMenu=ov&csmSeq=1814&ccfNo=2&cciNo=1&cnpClsNo=1)); the student is not in Korea to fly one; sensors cannot be field-tested on a Korean hillside from Shanghai.
- **Verdict: do not.**

### (5) Controlled field walking-speed experiment, or an operator usability test

- **ISEF rules (2025–26):** "Testing of student designed invention, prototype or computer application by human participants other than student researcher" is human-participant research and needs IRB approval **before recruitment or data collection** (Form 4, three signatures: medical/mental-health professional, educator, administrator; none may be the sponsor). Facilities for "protected groups" (retirement homes etc.) need written facility approval plus individual consent — this is the new 2026 item 6. Research done without prior approval goes to the SRC and can be disqualified. Expert feedback "prior to experimentation" is explicitly outside this scope. ([societyforscience.org human participants](https://www.societyforscience.org/isef/international-rules/human-participants/); [Form 4 2026 PDF](https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/4-Human-Participants.pdf); [2026 changes](https://science-fair.org/2026-changes-from-previous-rules-procedures/)).
- **KCF 서식4:** the local forms folder contains 서식1/2/3, 연구데이터시트, 참가신청서 only; no 서식4 was found. UNVERIFIED that KCF has a human-subject form; the rubric's 위험성 검토 is the relevant Pass/Fail row.
- **Walking-speed experiment with elderly participants:** requires recruiting 70+-year-olds in rural Korea on slopes, an IRB convened at a Shanghai international school, a protected-group facility approval if via 경로당, and it produces a number that the literature already supplies with better N: Peel, Kuys & Klein 2013 meta-analysis 0.58 m/s for clinical older adults ([pubmed 22923430](https://pubmed.ncbi.nlm.nih.gov/22923430/)), which 서식2 already cites, and a 2024 Fire Technology compilation of older-adult speeds for egress simulation ([springer 10.1007/s10694-024-01574-0](https://link.springer.com/article/10.1007/s10694-024-01574-0), abstract not fetched — UNVERIFIED contents). A student-only self-test is exempt but scientifically worthless for elderly. **Not feasible before Oct 18 and not worth it after.**
- **Operator usability test (복지사/119 상황실 using the console):** same IRB rule — "testing of … computer application by human participants other than student" — so a formal usability study is off the table for the 2027 ISEF cycle unless an IRB is convened first. **What is allowed and cheap:** more *expert consultations* of the kind already recorded in `docs/firefighter_consultation.md` (N = 1, structured, no numbers derived). Two or three more — an 이장, a 119 상황실 dispatcher, a 사회복지사 — documented with the same discipline, directly strengthen 개발 목적 (constraint understanding) and the Q&A, and the submission's own "실무자 평가 없음" limitation becomes "실무자 자문 N = 3–4, 평가 아님".
- **KCF value:** expert consultations: moderate, on 개발 목적 and Q&A credibility. Formal human-subject work: negative (Pass/Fail risk, no time).
- **Verdict: no experiment, no usability study. Yes to 2–3 more structured expert consultations, recorded as consultations, each ≤ 1 hour of the student's time, done by phone/video from Shanghai.**

### (6) GK2A / Himawari real-time ingestion as a "sensor"

- **What it is:** KMA's GK2A AMI produces an L2 산불탐지 (FF) product at 10-minute intervals via the API-hub (`authKey` required; text/NetCDF/PNG; archive from July 2019, so the March-2025 fires are covered) ([apihub.kma.go.kr seqApi=6](https://apihub.kma.go.kr/apiList.do?seqApi=6)). IR resolution ~2 km; GK2A-vs-MODIS fire-location agreement 1.28 ± 0.79 km; Korea sector scanned every 2 min ([KMA ATBD FF](https://nmsc.kma.go.kr/resources/common/pdf/%EC%99%B8GK2A_L2_ATBD_%EA%B5%AD%EB%AC%B8_%EC%82%B0%EB%B6%88%ED%83%90%EC%A7%80_FF.pdf); [nmsc GK2A intro](https://nmsc.kma.go.kr/enhome/html/base/cmm/selectPage.do?page=satellite.gk2a.intro)). NOAA's open-data mirror is L1B only, no FF ([registry.opendata.aws/noaa-gk2a-pds](https://registry.opendata.aws/noaa-gk2a-pds/)). FIRMS NRT is ~3 h global; FIRMS' <60 s URT feed is US/Canada only ([earthdata FIRMS URT](https://www.earthdata.nasa.gov/learn/articles/firms-urt-data)). API-hub delivery latency and daily call limits: UNVERIFIED.
- **Why it is the one "sensor" worth adding:** it is real Korean government data; it slots into the existing `live/firms.py` trigger abstraction as a second source; it can be replayed offline exactly like FIRMS replay (the demo path stays offline); and it yields a *measured* number the project does not have — first-detection time of the 2025-03 Uiseong/Andong and Yeongdeok fires from GK2A FF vs FIRMS NRT, and how many minutes of the 459-series closure windows that buys. That is a 데이터 수집·분석·해석 row contribution and a 구현 및 유용성 contribution at once, and it answers the firefighter's "한 템포 느리게" complaint (`firefighter_consultation.md` §6) with a measurement instead of a claim.
- **What it must not become:** a claim of real-time forecasting. The hazard surface stays fixed (ERA5 lag). The scope statement in `live/scope.py` must gain a third line ("탐지: FIRMS NRT + GK2A FF; 기상: 고정") rather than lose one.
- **Cost:** ₩0. **Build time:** the student: ~15 min to register at apihub.kma.go.kr and put the key in `.env`; the agent loop: 2–4 days for loader + replay + comparison doc + tests under the existing `make verify` discipline (the loader scaffold already raises `NotImplementedError` by design). Coverage detail (2 km pixels vs 375 m grid; false-alarm rejection tests in the ATBD) must be reported, not hidden.
- **Risk:** the key is personal to the student and must never enter the cloud sandbox unredacted (the repo already redacts `FIRMS_MAP_KEY` in URLs; reuse that path). If the API-hub is rate-limited or the March-2025 FF archive has gaps, the experiment degrades to "documented, not measured" — still honest.
- **Himawari:** JMA's product is not needed; GK2A covers Korea natively. Skip.
- **Verdict: do this first. It is the highest-value item on the list.**

### (7) None of the above — double down on software rigor

- The open items with the best points-per-hour are all in the tree: `W = 75` is ASSUMED with no measured basis (`config/default.yaml:365`) — the firefighter said the concept does not exist in the field, which is a limitation to state, not a value to hunt; the shelter-density (refuge decimation) experiment is sequenced and unstarted (HANDOFF §4); 30/60/90-min `w(t)` is promised as future work in 서식2; Session 22 found and fixed a directed-graph distance bug and left every household count "잠정" pending building footprints; `finals.html` needs rehearsal until "G" restarts it in one keystroke for the next judge.
- **KCF value:** these move 설계·방법론 (variable control), 데이터 수집·분석·해석 (reproducibility), and Q&A. **ISEF value:** Execution 20 + Interview 25 — the two largest blocks.
- **Cost:** ₩0. **Time:** the agent loop does most of it; the student rehearses.
- **Verdict: this is the baseline; (6) and (2) are the only additions that belong on top of it.**

---

## 4. Summary table

| # | Option | KCF rows moved | ISEF | Real-world | Cost | Student time | Automation leverage | Risk | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Edge alert node (ESP32/LoRa + speaker/lamp) | 개발 목적 −, 창의성 0 | low (wrong category) | none (duplicates 마을방송) | ₩80–120k | 2–3 weekends | none | RF/KC/battery/위험성 검토; contradicts 서식2 | **No** |
| 2 | Real delivery send (email now; domestic SMS ₩18 if individual sender allowed) | 구현·유용성 +, 제출 자료 + | marginal | closes a stated gap honestly | ₩0–1k | hours | high | low if gates untouched | **Yes (email); SMS conditional; no Twilio, no CBS** |
| 3 | LED terrain model | 창의성 +, 구현 −/risk | Presentation only | none | ₩100–200k | 3–5 weekends | low | transport, power, fragility, steals rehearsal time | **No** (print the A4 sheets instead) |
| 4 | Sensors / drone / weather station | 개발 목적 − (contradicts premise) | negative | none at grid scale | ₩50k+ | weeks | none | drone regs; cannot field-test from Shanghai | **No** |
| 5a | Elderly walking-speed field experiment | 설계·방법론 +? but Pass/Fail risk | IRB before start; protected group | literature already better | ₩0 | impossible by Oct 18 | none | SRC disqualification if done without IRB | **No** |
| 5b | Formal operator usability test | 구현·유용성 + | IRB before start | some | ₩0 | weeks incl. IRB | none | same | **No** |
| 5c | 2–3 more structured expert consultations (이장, 119 상황실, 복지사) | 개발 목적 +, Q&A + | exempt (expert feedback) | yes (channel constraints) | ₩0 | 1 h each | agent writes the protocol + doc | low; keep N-labelled, derive no numbers | **Yes** |
| 6 | GK2A FF ingestion as second trigger, offline replay, detection-gap measurement | 데이터 수집·분석 +, 구현·유용성 +, 창의성 + | Execution + | yes (Korean, 10-min cadence) | ₩0 | 15 min (API key) | very high | API latency/limits UNVERIFIED; must not be sold as forecasting | **Yes — first** |
| 7 | Software rigor (refuge decimation, w(t) budgets, footprints, rehearsal) | 설계·방법론 +, 데이터 +, Q&A + | Execution + Interview | yes | ₩0 | rehearsal | very high | none | **Baseline** |

---

## 5. Recommended order (45 days)

1. **Today–Sep 7 (student, 15 min):** register at apihub.kma.go.kr, issue the 인증키, put it in `.env` locally; give the agent loop only redacted access per the existing FIRMS key pattern. Unblocks (6).
2. **Sep 7–20 (agent loop):** GK2A FF loader → second trigger source with the same seen-set/dedupe/all-or-nothing rules as `firms.py` → offline replay of 2025-03 Uiseong-Andong and Yeongdeok → one document with first-detection deltas and how many minutes of the earliest 459-series closure windows that recovers; scope statement extended, never weakened; tests; `make verify` green.
3. **First weekend the student is on a home/hotspot network (hours):** run the PHASE-7 email verification send; commit the `email_sent.json` record. If SOLAPI sender registration is available to an individual (check first — UNVERIFIED), add the ₩18 SMS adapter with the identical approval gate and send exactly one message to the student's own phone; photograph it with the 「재생 모드」 header visible.
4. **Sep–early Oct (student, 1 h each; agent writes the protocol):** two or three expert consultations recorded in the `firefighter_consultation.md` format, N-labelled, no numbers derived.
5. **Sep–Oct 10 (agent loop):** the software items in (7); refresh `finals.html` only from canonical artifacts through `make finals`.
6. **Oct 10–18 (student):** rehearse the 5-minute demo and the Q&A note; print the A4 sheets and broadcast script for the table; verify `finals.html` with wifi off on the laptop that will travel.

## 6. Explicitly do NOT

- Do not buy any board, LED strip, speaker, sensor, or drone for this competition.
- Do not put a device in the elderly household in any narrative, slide, or poster — it contradicts the submitted 서식2 and the recorded consultation.
- Do not upgrade the Twilio account; do not send [국제발신] SMS; do not say "cell broadcast" or "재난문자 연동" — only the state can originate CBS.
- Do not run any survey, usability test, or walking-speed measurement with anyone other than the student before an IRB has signed Form 4; do not visit a 경로당/요양원 for data.
- Do not wire Web Serial or any device API into `web/finals.html`; do not re-scope `check_screen_assets.py` to allow it.
- Do not describe GK2A ingestion as real-time forecasting; the hazard surface remains fixed and the two mandated scope lines stay on every artifact.
- Do not touch committed artifacts, Yeongdeok OSM, or any HANDOFF §5 item to make a demo prettier.

---

## 7. Sources

- KCF ISEF history: [koreasisailbo 2024 (EBED 2등상, CPR feedback)](http://www.koreasisailbo.com/1377657); [boannews 2023 (EBED 4등상, 시각장애인 보행 보조 장치)](https://m.boannews.com/html/detail.html?idx=118327); [BBS News 2024 (3년 연속)](https://news.bbsi.co.kr/news/articleView.html?idxno=3156502); [enewstoday 2025 (SOFT 3등상 hand-gesture dementia app; 특별상 AI traffic signal; 6 teams)](http://www.enewstoday.co.kr/news/articleView.html?idxno=2278657); [KCF ISEF 선발 안내 2026 (JS-rendered, not readable here)](https://www.kcf.or.kr/notice/?bmode=view&idx=168593490); [namu.wiki 한국코드페어 (booth format, wifi)](https://namu.wiki/w/%ED%95%9C%EA%B5%AD%EC%BD%94%EB%93%9C%ED%8E%98%EC%96%B4); [kcf.or.kr 2026 대회 안내](https://kcf.or.kr/71/?bmode=view&idx=172288990).
- ISEF: [Grand award criteria](https://www.societyforscience.org/isef/grand-award/criteria/); [Human participants rules](https://www.societyforscience.org/isef/international-rules/human-participants/); [Form 4 (2026)](https://sspcdn.blob.core.windows.net/files/Documents/SEP/ISEF/2026/Forms/4-Human-Participants.pdf); [2026 rule changes](https://science-fair.org/2026-changes-from-previous-rules-procedures/); [ISEF 2025 full awards](https://www.societyforscience.org/press-release/regeneron-isef-2025-full-awards/).
- SMS/CBS: [Twilio KR SMS guidelines](https://www.twilio.com/en-us/guidelines/kr/sms); [Twilio KR pricing](https://www.twilio.com/en-us/sms/pricing/kr); [SOLAPI pricing](https://solapi.com/pricing); [SOLAPI 발신번호 guide](https://solapi.com/guides/sms-howtosend); [재난문자방송 (ko.wikipedia)](https://ko.wikipedia.org/wiki/%EC%9E%AC%EB%82%9C%EB%AC%B8%EC%9E%90%EB%B0%A9%EC%86%A1); [재난문자방송 기준 및 운영규정](https://www.ulex.co.kr/%EB%B2%95%EB%A5%A0/2100000232288-28580-%EC%9E%AC%EB%82%9C%EB%AC%B8%EC%9E%90%EB%B0%A9).
- Village broadcast infrastructure: [군위군 스마트 마을방송](https://www.idaegu.com/news/articleView.html?idxno=650583); [청주시](https://www.goodmorningcc.com/news/articleView.html?idxno=430905); [양양군](https://g1tv.co.kr/news/?mid=1_207_3&newsid=343614); [DK Techin KakaoTalk 스마트 마을방송](https://dktechin.com/news/42).
- GK2A / FIRMS: [KMA API-hub GK2A products](https://apihub.kma.go.kr/apiList.do?seqApi=6); [GK2A FF ATBD](https://nmsc.kma.go.kr/resources/common/pdf/%EC%99%B8GK2A_L2_ATBD_%EA%B5%AD%EB%AC%B8_%EC%82%B0%EB%B6%88%ED%83%90%EC%A7%80_FF.pdf); [NMSC GK2A intro](https://nmsc.kma.go.kr/enhome/html/base/cmm/selectPage.do?page=satellite.gk2a.intro); [NOAA GK2A S3 registry](https://registry.opendata.aws/noaa-gk2a-pds/); [FIRMS URT article](https://www.earthdata.nasa.gov/learn/articles/firms-urt-data); [FIRMS URT feature](https://www.earthdata.nasa.gov/news/feature-articles/firms-adds-ultra-real-time-data-from-modis-viirs).
- Hardware/regulatory: [Heltec WiFi LoRa 32 V3](https://heltec.org/project/wifi-lora-32-v3/); [KR920 band](https://www.rfwireless-world.com/terminology/lorawan-frequency-bands-korea-kr); [RRA 적합성평가 요건면제](https://www.rra.go.kr/ko/popup/popup_100430.jsp); [RRA 적합성평가 FAQ](https://www.rra.go.kr/ko/notice/D_e_faq2_1.do?fa_type=a&fa_category=compt); [보조배터리 기내 반입 (korea.kr)](https://www.korea.kr/news/policyNewsView.do?newsId=148940158); [Korean Air battery notice 2026](https://www.koreanair.com/contents/footer/customer-support/notice/2026/260123-lithium-batteries); [드론원스톱](https://drone.onestop.go.kr/introduce/systemintro2/); [easylaw 드론 장치신고](https://www.easylaw.go.kr/CSP/CnpClsMainBtr.laf?popMenu=ov&csmSeq=1814&ccfNo=2&cciNo=1&cnpClsNo=1); [WS2812B 1 m 60 LED (ICBanq)](https://www.icbanq.com/P014162724); [Web Serial API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API); [Web Serial spec](https://wicg.github.io/serial/).
- Existing detection systems: [산림청 ICT 플랫폼 (etnews)](https://m.etnews.com/20220105000104); [열화상 산불감지 (boannews)](https://m.boannews.com/html/detail.html?idx=105880); [Simtable](https://www.simtable.com/); [Sand on fire](https://www.academia.edu/128387286/Sand_on_fire_an_interactive_tangible_3D_platform_for_the_modeling_and_management_of_wildfires).
- Walking speed: [Peel, Kuys & Klein 2013 (PubMed 22923430)](https://pubmed.ncbi.nlm.nih.gov/22923430/); [Fire Technology 2024 older-adult speeds](https://link.springer.com/article/10.1007/s10694-024-01574-0); [elderly in smoke-filled stairwells (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC13087748/).

## 8. UNVERIFIED

- KCF 2022 ISEF 4th-place project title/category.
- KCF 2026 ISEF selection: 5 vs 7 teams and whether 동상 qualifies (search snippet only; kcf.or.kr notice is JS-rendered and returned no text).
- Whether KCF has a "서식4" human-subject form (not present in the local forms folder).
- KMA API-hub GK2A FF delivery latency and daily call limits; whether the March-2025 FF archive is gap-free.
- Whether SOLAPI/CoolSMS accept an individual (non-사업자) sender-number registration.
- KRW prices for ESP32 DevKit and Raspberry Pi 5 (retailer pages did not render); Taobao prices; 3D-print/laser-cut terrain cost.
- Booth power outlets at the Gwangju venue.
- Fire Technology 2024 paper contents (abstract behind a redirect).
- RRA "1대" personal-use exemption as applied to two identical radio boards.
