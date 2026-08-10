# 산불지킴이 / WildfireGuardian — Launch Advertising Campaign

> **Operator's playbook.** Everything here is ready to paste, schedule, or hand
> to an agency. Product truths come from
> [`docs/app/ARCHITECTURE.md`](ARCHITECTURE.md) and are **binding on all copy**:
> every life-safety feature is free forever, three danger levels only
> (안전/주의/대피), demo mode is always labelled, and the app supplements —
> never replaces — 재난문자 and 119.
>
> **Two copy laws that override everything else in this file:**
> 1. **Never promise safety. Promise information, speed, and simplicity.**
> 2. **Never monetize fear. The free tier is the message; Plus is a convenience
>    for the family, sold to the family.**
>
> Research metrics (AUC etc.) never appear in any ad, store listing, or
> resident-facing surface. Journalists get pointed at `docs/MODEL_CARD.md`
> instead (§8).

---

## 0. Campaign at a glance

| item | value |
|---|---|
| Product | 산불지킴이 (WildfireGuardian) — free wildfire status, spread awareness, evacuation guidance for rural residents |
| Paid tier | Guardian Plus (가디언 플러스): family circle notifications, SMS/phone-call alert delivery, offline map packs, multiple addresses. Convenience only — **no safety feature is ever paywalled** |
| Hero regions | 경북 (Gyeongbuk), 강원 (Gangwon) — highest wildfire exposure, target demographic density |
| Primary buyer | Adult child (40–60, urban) purchasing Plus for parents (60–80s, rural) |
| Primary user | The rural elderly resident — always free |
| Peak window | Korean spring fire season: 봄철 산불조심기간 (Feb 1 – May 15) |
| Campaign shape | 8-week ramp (soft launch → peak in March) + always-on layer (§5) |
| Budget tiers | ₩5M / ₩30M / ₩150M (§6) |
| Assets | `marketing/assets/` — see §4.0 for the manifest |
| Hard rule | **Circuit breaker:** all paid ads pause in any 시·군 with an active major wildfire (§9.4) |

---

## 1. Positioning, promise, brand voice

### 1.1 Positioning statement (internal)

For rural elderly Koreans and the city-dwelling children who worry about them,
산불지킴이 is the wildfire app that tells you — in three colors, huge type, and
plain speech — whether you are safe, what to prepare, and which way to walk.
Unlike news apps and general disaster apps, it shows **one person's situation,
one action at a time**, and every life-safety feature is free, forever, with no
sign-up. Guardian Plus adds one thing only: the family, watching together.

### 1.2 One-sentence promise

| | |
|---|---|
| **ko** | 산불이 가까워지면 바로 알기 쉽게 알려드리고, 대피소까지 가는 길을 안내해 드립니다 — 생명을 지키는 기능은 모두, 영원히 무료입니다. |
| **en** | When wildfire comes close, we tell you right away — clearly and simply — and show you the way to shelter. Every life-safety feature is free, forever. |

### 1.3 Brand voice rules

| # | Rule | Do (ko) | Never (ko) |
|---|---|---|---|
| V1 | **Urgent, never fear-exploiting.** Urgency lives in *speed and preparedness*, not in flames and loss. No burning homes, no victims, no smoke-filled skies in any creative. | "산불이 다가오면 바로 알려드립니다" | "다음 희생자는 누구입니까?" |
| V2 | **Hope + preparedness framing.** Every ad ends on the prepared, calm state — the green screen, the family at ease. | "준비된 마을이 가장 안전합니다" | "겁나지 않으세요?" |
| V3 | **존댓말, always, in every elder-facing word.** Respectful, warm, unhurried. Address as 어르신 / 부모님, never 노인 in copy. | "어르신, 세 가지 색만 기억해 주세요" | "노인용 앱" |
| V4 | **Simple words. No jargon.** No "AI", "위성 데이터 파이프라인", "머신러닝", "알고리즘" in elder-facing copy. (Fine in B2G/press materials.) | "산불이 다가오면 알려드립니다" | "AI 기반 확산 예측 솔루션" |
| V5 | **No guarantees, ever.** Not "지켜드립니다" as an absolute, no "100% 안전", no "완벽". The app informs and guides; it does not promise outcomes. | "알려드립니다 · 안내해 드립니다" | "안전을 보장합니다" |
| V6 | **Honesty is the brand.** "무료" claims always name what *is* paid in the same breath (landing pages, store listings). Demo visuals always carry 연습 모드/시연 화면 labels. | "생명 안전 기능은 전부 무료, 편의 기능만 유료입니다" | hiding the paid tier behind an unqualified "완전 무료" |
| V7 | **Defer to officials, visibly.** Every long-form ad, poster, and listing carries the disclaimer: the app supplements 재난문자 and 119. This is a trust asset, not fine print — say it proudly. | "재난문자와 119의 안내를 대신하지 않고, 곁에서 돕습니다" | implying the app replaces official alerts |
| V8 | **The 2025 fire is honored, not used.** The 의성→영덕 fire (2025.3, 27명 사망, 대부분 고령자) is why we exist. It may be referenced factually in press materials and B2G pitches. It never appears in paid ads, never as imagery, never as a scare hook. | (press only) "2025년 3월의 산불 이후, 다시는 같은 일이 없도록" | victim imagery, death-toll headlines in ads |

**Tagline system** (use consistently):

| use | ko | en |
|---|---|---|
| Master tagline | 생명을 지키는 기능은 모두 무료입니다 | Every life-safety feature is free |
| Elder-facing | 어르신을 위해 만들었습니다 | Made for you |
| Family-facing | 멀리 살아도, 곁에 있는 것처럼 | Far away, yet right beside them |
| B2G-facing | 마을 방송이 닿지 않는 순간에도 | Reaching residents when the village loudspeaker can't |

---

## 2. Audience segments

### 2.1 Segment map

| | (a) 어르신 — rural elderly (60–80s) | (b) 자녀 — adult children (40–60, urban) | (c) B2G — 지자체·소방·산림 당국 |
|---|---|---|---|
| **Role** | User. Never pays. | Installer, payer (Plus), advocate | Distributor, credibility multiplier |
| **Core message** | 무료입니다 · 간단합니다 · 어르신을 위해 만들었습니다 | 어디에 계시든, 부모님을 함께 지켜보세요 | 예산 0원으로 주민에게 닿는 산불 안내 채널 |
| **Emotional driver** | "나도 쓸 수 있다" (I can actually use this) | 죄책감 아닌 안심 — relief, not guilt | 인명피해 제로 실적, 고령주민 보호 책무 |
| **Channels** | TV·라디오·신문(지역), 마을방송/이장 네트워크, 경로당, 노인복지관, 농협, 보건소 포스터 | Naver 검색/밴드, Kakao, YouTube 프리롤, Instagram/Facebook, 앱스토어 | 직접 제안(공문+대면), 산림청/도청/시군청, 소방본부, 대한노인회 |
| **Call to action** | "자녀분께 설치를 부탁해 보세요" / 경로당 설치 행사 방문 | 지금 설치 → 부모님 주소 등록 → 가족 알림 연결 | 시범사업 MOU 체결 (§2.4) |
| **What we never say** | anything requiring tech literacy; anything scary | "부모님을 방치하실 겁니까"-style guilt attacks | 정부 인증·공식 채널을 사칭하는 표현 |
| **Success metric** | activation (주소 등록), 경로당 행사당 설치 수 | install→family-circle attach, Plus conversion | signed pilots, shelters verified, co-distribution reach |

### 2.2 Segment (a) — 어르신: "free, simple, made for you"

The honest structural fact: most elderly users will not install an app from an
ad. They install because **a child, a grandchild, an 이장, or a 경로당 volunteer
does it with them**. Elder-facing media therefore has two jobs:

1. **Familiarity** — when the child says "산불지킴이 깔아 드릴게요", the parent
   already trusts the name (radio, poster at the 보건소, the 이장 mentioned it).
2. **Permission ask** — every elder-facing piece ends with:
   **"자녀분께 한마디 부탁해 보세요 — '산불지킴이 깔아 다오.'"**
   This line is the bridge between segments (a) and (b). Use it everywhere.

Proof points to repeat: 요금 없음 · 가입 없음 · 큰 글씨 · 세 가지 색 ·
소리로 읽어 줌 (read-aloud) · 버튼 하나.

### 2.3 Segment (b) — 자녀: "watch over your parents from anywhere"

The actual revenue segment. Journey to sell:

```
YouTube/Kakao ad → install (free) → set parents' address (activation)
→ invite family circle (free trial of togetherness)
→ Guardian Plus: SMS/call alerts + family notifications + offline maps + multi-address
```

Copy stance: **relief, not guilt.** The insight is the phone call — every time
wildfire is on the news, they call their parents. The app is the call that's
already answered. Peak cultural moment: **설날 귀성** (Seollal homecoming,
late Jan–Feb) — "고향 가시는 길에, 부모님 휴대폰에 설치해 드리세요" (§5, W2–3).

Plus pitch is always honest-by-construction:
**"부모님이 쓰시는 안전 기능은 전부 무료입니다. 플러스는 '가족이 함께 받는
알림'을 더할 뿐입니다."** — the free-first statement *is* the conversion
argument: a company that refuses to paywall safety is a company you trust with
your parents.

### 2.4 Segment (c) — B2G one-page pitch (ready to send)

Realistically the highest-leverage channel in Korea: one 시군 MOU = thousands
of installs through official channels, plus credibility no ad can buy.
Print on one page, 공문 style, with the hero banner strip on top.

> ---
>
> ### 산불지킴이 × ○○군 — 고령주민 산불 안전 시범사업 제안 (1쪽)
>
> **문제.** 2025년 3월 경북 산불(의성→안동→청송→영양→영덕)로 27명이
> 희생되었고, 대부분 60–80대 고령 주민이었습니다. 재난문자는 닿아도,
> "우리 집이 위험한가, 어디로 가야 하는가"는 각 가정이 스스로 판단해야
> 했습니다.
>
> **제안.** 주민 휴대폰에서 곧바로 쓰는 무료 앱 '산불지킴이'의 3개월
> 시범 운영 (대상: 관내 2개 면, 경로당 ○○개소).
>
> **앱이 하는 일.** 위성 화재 관측 기반으로 ① 우리 집 기준 위험 단계
> (안전/주의/대피, 3색), ② 준비·대피 안내 카드, ③ 대피소까지 도보 경로를
> 큰 글씨·음성 읽어주기로 제공합니다. 검증된 연구 시스템(한국 실제 산불
> 6건 교차검증)에서 출발한 앱이며, 기술 문서 일체를 열람하실 수 있습니다.
>
> **군에 요청드리는 것 (예산 0원).**
> 1. 이장·통장 네트워크 및 마을방송을 통한 안내 협조
> 2. 경로당·보건소 포스터 게시 및 설치 도우미 행사 장소 협조
> 3. 관내 대피소(마을회관·학교 등) 목록 검증 협조
>
> **저희가 제공하는 것.**
> 1. 주민 전원 무료 이용 (생명 안전 기능은 영구 무료 — 원칙입니다)
> 2. 경로당 방문 설치 지원 (인력·자료 자부담)
> 3. 시범 기간 종료 후 이용 현황 보고서 (개인정보 제외, 읍면 단위 통계)
>
> **명확히 말씀드리는 것.** 본 앱은 재난문자·119 등 공식 체계를 **보완하는
> 보조 수단**이며, 안전을 보장하는 시스템이 아닙니다. 시범사업은 정부·군의
> 앱 보증을 의미하지 않으며, 저희도 그렇게 홍보하지 않습니다.
>
> **연락처.** [담당자명 / 전화 / 이메일] · 기술문서: 요청 시 제공
>
> ---

Escalation path and MOU sequencing: §8.2.

---

## 3. Channel plan (Korea-first)

Budget share below = share of **paid media** in the ₩30M reference tier (§6.2).
Community/print is bought media here; PR and B2G labor is not in these
percentages.

### 3.1 Korea core

| Channel | Why | Format | Targeting | Share |
|---|---|---|---|---|
| **Naver 검색광고 (SA)** | Where Koreans verify anything before installing; captures active intent ("산불 앱", "부모님 안전") and brand searches driven by radio/PR | 파워링크 (search text ads) + 브랜드검색 (if budget allows); sitelinks to "무료 안내" page | Keywords: 산불 알림, 산불 앱, 대피소 찾기, 부모님 안전, 고향 부모님; geo-boost 서울/수도권 (children) + 경북/강원 (locals). **Negative-match live-fire event terms (§9.4)** | 13% |
| **Naver 밴드 (BAND)** | Highest 40–60 penetration of any Korean social app; 귀농·향우회·마을 밴드 communities are exactly segment (b)+(a) overlap | Feed ads (image `ad_creative_family.jpg` 4:5 crop), 밴드 게시글 partnerships with 향우회 밴드 | Age 40–65, interests: 고향, 귀농귀촌, 부모님, 건강; regions both metro and 경북/강원 | 7% |
| **KakaoTalk 채널 + Kakao Moment** | Kakao is where family logistics happen; a 카카오톡 채널 doubles as CRM (seasonal preparedness messages) and the ad unit reaches essentially all adults | Kakao Moment: 비즈보드 (talk-tab banner) + display; 채널 add-friend campaign; 알림톡 later for opted-in Plus onboarding | 비즈보드: age 35–59, parents-of-rural-parents proxy (interests: 효도, 건강식품, 고향), device Android-heavy; 채널 콘텐츠 organic | 17% |
| **YouTube 프리롤** | The moving-image channel for 40–60; scripts §4.4 are built for skippable in-stream; also the only paid channel that can carry the full emotional arc | 15–30s skippable in-stream (Scripts A/B), 15s bumper cut (Script C); companion banner from `hero_banner.jpg` | Age 40–60, KR; affinity: 부모님/가족, 트로트, 귀농, 뉴스; placement on news & 트로트 channels; exclude children's content; **geo-pause per §9.4** | 20% |
| **Instagram / Facebook (Meta)** | Secondary reach for 40–55; strong 4:5 creative fit; Facebook still holds 50대 커뮤니티 groups | 4:5 feed + Stories from `ad_creative_family.jpg`; carousel: 3-color explainer | Age 38–60 KR; Advantage+ placements off — manual Feed/Stories only, no Reels; conservative creative per Meta policy (§9.2) | 8% |
| **Community (bought print + field)** | The elder channel that actually converts installs — 경로당 install events with 이장 endorsement | A2 posters (경로당·보건소·농협 게시판, `ad_creative_elder.jpg` layout §4.6), A5 leaflets for 농협 창구, install-event kits | 경북·강원 우선 (시군 리스트: 의성·안동·청송·영양·영덕·울진·삼척·강릉 등 산불 이력 지역 우선 — 존중의 원칙 §1.3 V8 준수) | 13% |
| **Local radio/TV (경북·강원)** | Radio is the trusted background medium of rural elders; builds the name recognition that makes the child's install offer land | 20s radio spot (§4.5) on 지역 MBC·CBS·TBN 한국교통방송; TV only at ₩150M tier (지역민방 20s, Script C cutdown) | Morning & early-evening dayparts; 농어촌 프로그램 인접 | 12% |

### 3.2 Global / secondary

| Channel | Why | Format | Targeting | Share |
|---|---|---|---|---|
| **Google App Campaigns (Android)** | Korea is ~75% Android — and elderly users are overwhelmingly Android/Galaxy; cheapest install volume once creative assets exist | UAC with text assets (headlines §4.2), images, 15s video (Script C) | KR, language ko; tCPI per §6.4; conversion = install→activation event | 8% |
| **Apple Search Ads** | Adult children skew iPhone; high-intent store search ("산불", "재난 알림") | Search results ads on brand + category keywords | KR storefront, exact + broad on §4.7 keyword list | 2% |

Rationale for the split: paid digital buys the **payer** (segment b);
print/radio/field buys the **user** (segment a); B2G (unpaid, §8.2) buys
**scale and trust**. Do not let a media agency invert this into a
digital-only plan — installs without elder activation are vanity.

### 3.3 First moves — the concrete first action per channel

| Channel | Do this first (before any spend) |
|---|---|
| Naver SA | Open the 네이버 검색광고 account; register 비즈채널 (landing domain + both store links); submit the §4.7 keyword list **and** the §9.4 live-fire negative list for review (2–3 영업일 lead) |
| Naver 밴드 | Create the official 산불지킴이 밴드 page; book feed ads via 네이버 성과형 디스플레이 광고(GFA) with the 4:5 `ad_creative_family.jpg` crop |
| Kakao | Open the 카카오톡 채널 (@산불지킴이) and finish 비즈니스 인증 first — it gates Moment and 알림톡; then create the Kakao Moment account and load the 비즈보드 unit |
| YouTube | Upload finished Scripts A/B as unlisted videos; link the channel to Google Ads; build both audiences (KR 40–60; news/트로트 affinity) the week before the flight |
| Meta | Set up Business Manager + domain verification; submit one 4:5 unit for review a full week early — Meta's automated review is the strictest (§9.2), learn its verdict before committing budget |
| Community | Choose the 2 pilot 시군; reach the 이장/경로당 회장 through each 읍면 행정복지센터; fix the first install-event date — print posters only after the date is set |
| Local radio/TV | Request rate cards (지역 MBC·CBS·TBN); submit the §4.5 script for 방송광고 심의 immediately — the longest lead time in the plan (§9.6) |
| Google App Campaigns | Link Play Console ↔ Google Ads; import the activation event (주소 등록) as the conversion; start tCPI at the §6.4 assumption midpoint |
| Apple Search Ads | From App Store Connect, start exact-match on the brand term only; widen to §4.7 category keywords once W4 CPI data exists |

---

## 4. Creative briefs + ready-to-run copy

### 4.0 Asset manifest

All assets are **AI-generated** (see `marketing/assets/README.md` for
provenance and mandatory usage rules — hopeful imagery only, AI-disclosure
where required, never presented as real people/events).

| Asset (path) | Brief | Where used |
|---|---|---|
| `marketing/assets/app_icon_concept.png` | Shield + flame + path-to-safe-house mark. Redraw as vector for stores. Must read at 48px. | Store icon, avatar for Naver/Kakao/YouTube channels, favicon |
| `marketing/assets/hero_banner.jpg` | 16:9 hopeful hero (grandmother, green check screen); copy space right third. Overlay master tagline + store badges. | Landing page, store feature graphic, YouTube companion, press kit header, B2G one-pager header strip |
| `marketing/assets/ad_creative_family.jpg` | 4:5 social creative for segment (b); headline space top quarter. Pair with headlines H3/H4/H9. | Kakao Moment, Naver 밴드, Instagram/Facebook feed |
| `marketing/assets/ad_creative_elder.jpg` | 4:5 print-first creative for segment (a); text space bottom quarter. Pair with poster copy §4.6. | 경로당/보건소/농협 posters, leaflets, local newspaper |
| `marketing/assets/promo_video.mp4` | 5s hopeful clip (not in git; regenerate per assets README: animate `hero_banner.jpg`, slow push-in, no fire/smoke/text). | Script C bumper base, social loops, landing-page header |

**Every creative, every format, carries somewhere legible:**
`재난문자·119 안내를 보완하는 보조 수단입니다` (long-form / landing / poster),
and any app-screen footage shows the real `연습 모드 / DEMO` banner — never
crop it out (§9.5 checklist).

### 4.1 The 10 headlines (short, ready to run)

| # | ko | romanization | en | best fit |
|---|---|---|---|---|
| H1 | 생명을 지키는 기능은 모두 무료입니다 | Saengmyeong-eul jikineun gineung-eun modu muryo-imnida | Every life-safety feature is free | all channels — master |
| H2 | 산불이 다가오면, 바로 알려드립니다 | Sanbul-i dagaomyeon, baro allyeodeurimnida | When fire draws near, you'll know right away | YouTube, Naver SA |
| H3 | 부모님 계신 곳, 지금 안전한가요? | Bumonim gyesin got, jigeum anjeonhangayo? | Is it safe where your parents are, right now? | Kakao, Meta (b) |
| H4 | 멀리 살아도, 곁에 있는 것처럼 | Meolli sarado, gyeote inneun geotcheoreom | Far away, yet right beside them | Kakao, 밴드 (b) |
| H5 | 세 가지 색만 기억하세요 — 안전, 주의, 대피 | Se gaji saek-man gieokhaseyo — anjeon, juui, daepi | Remember just three colors — Safe, Watch, Go | poster, radio, explainer |
| H6 | 버튼 하나로, 대피소 가는 길을 | Beoteun hanaro, daepiso ganeun gireul | One button shows the way to shelter | store listing, UAC |
| H7 | 우리 마을에도 산불지킴이 | Uri maeul-edo Sanbuljikimi | WildfireGuardian, for our village too | B2G, community, radio |
| H8 | 준비된 마을이 가장 안전합니다 | Junbidoen maeur-i gajang anjeonhamnida | A prepared village is the safest village | B2G, poster, PR |
| H9 | 부모님 휴대폰에, 지킴이 하나 | Bumonim hyudaepon-e, jikimi hana | A guardian on your parents' phone | Seollal push (b) |
| H10 | 가입도, 요금도 없습니다 | Gaip-do, yogeum-do eopseumnida | No sign-up. No fees. | elder print, 농협 leaflet |

> **Why no headline says "가장 안전한", "산불보다 먼저", or "지켜드립니다":**
> arrival-timing claims ("the alert beats the fire") and superlatives ("safest
> route") cannot be substantiated under 광고 실증제 (§9.3) — satellite
> detection has latency, and routes carry warnings by design (ARCHITECTURE
> §5.2, honest `no_safe_walk` failure). Headlines promise only what the app
> verifiably does: prompt, clear notification and a route to shelter. Hold
> every new variant to the same line.

### 4.2 The 5 body texts

**B1 — elder print/leaflet (a):**
> ko: 산불은 소식이 빠를수록 안전합니다. '산불지킴이'는 산불이 가까워지면 큰
> 글씨와 세 가지 색으로 알려드리고, 대피소로 가는 길을 안내해 드립니다. 요금도,
> 가입도 없습니다. 글을 읽기 어려우시면 소리로 읽어 드립니다. 자녀분께
> 한마디 부탁해 보세요 — "산불지킴이 깔아 다오."
>
> en: With wildfire, the sooner you know, the safer you are. WildfireGuardian
> tells you in big letters and three colors when fire comes near, and shows you
> the way to shelter. No fees, no sign-up. If reading is hard, it reads aloud to
> you. Just ask your son or daughter: "Put WildfireGuardian on my phone."

**B2 — adult children digital (b):**
> ko: 뉴스에 산불 소식이 나올 때마다, 고향에 전화부터 하게 되시나요?
> 산불지킴이는 부모님 댁 주변을 지켜보다가 위험이 다가오면 부모님 휴대폰으로
> 바로, 알기 쉽게 알려드립니다. 부모님이 쓰시는 안전 기능은 전부 무료입니다.
> '가디언 플러스'를 더하시면, 위험 알림이 문자와 전화로도 전해지고, 온 가족이
> 같은 알림을 함께 받습니다.
>
> en: Every time wildfire is on the news, is your first move calling home?
> WildfireGuardian watches the area around your parents' house and alerts their
> phone — clearly and simply — when danger nears. Everything your parents use
> is free. Add Guardian Plus and alerts also arrive by SMS and phone call —
> to the whole family at once.

**B3 — the trust/honesty ad (all audiences; run this one proudly):**
> ko: 안전을 돈 받고 팔지 않습니다. 위험 알림, 지도, 대피 경로, 대피소 안내 —
> 생명과 관련된 기능은 전부, 영원히 무료입니다. 유료 서비스 '가디언 플러스'에는
> 가족 함께 알림, 문자·전화 알림, 오프라인 지도 같은 '편리함'만 담았습니다.
> 무엇이 무료이고 무엇이 유료인지 먼저 밝히는 것이, 저희가 드리는 첫 번째
> 약속입니다.
>
> en: We do not sell safety. Danger alerts, the map, evacuation routes, shelter
> guidance — everything life-safety is free, forever. The paid tier, Guardian
> Plus, holds only conveniences: family notifications, SMS and call alerts,
> offline maps. Telling you plainly what is free and what is paid — that is our
> first promise.

**B4 — community / B2G poster body (c → a):**
> ko: 우리 마을 어르신들의 휴대폰에 산불지킴이 하나면, 마을 방송이 닿지 않는
> 순간에도 안내가 닿을 수 있습니다. 사용법은 세 가지 색만 기억하시면 됩니다 —
> 초록이면 안전, 노랑이면 주의, 빨강이면 대피. 경로당과 마을회관에서 설치를
> 도와드립니다.
>
> en: With WildfireGuardian on our elders' phones, guidance can reach them even
> when the village loudspeaker can't. Just remember three colors — green means
> safe, amber means watch, red means evacuate. Install help available at
> the senior center and village hall.

**B5 — app store / generic digital:**
> ko: 산불지킴이는 위성 화재 관측을 바탕으로 산불 상황을 알기 쉽게 보여주는
> 앱입니다. 화면에는 꼭 필요한 것만 담았습니다 — 지금 안전한지, 무엇을
> 준비해야 하는지, 어디로 가야 하는지. 재난문자와 119의 안내를 대신하지 않고,
> 곁에서 돕습니다.
>
> en: WildfireGuardian turns satellite fire observations into plain answers:
> Am I safe right now? What should I prepare? Which way should I go? It never
> replaces official disaster alerts or 119 — it stands beside them.

### 4.3 Creative briefs per asset (paid units)

| Unit | Asset base | Headline | Body | CTA | Notes |
|---|---|---|---|---|---|
| Kakao 비즈보드 | `ad_creative_family.jpg` crop | H3 | — (banner) | 설치하기 | Talk-tab banner; no fire imagery; free-line as sub if space |
| Kakao/Meta feed 4:5 | `ad_creative_family.jpg` | H4 or H9 | B2 (short cut) | 무료로 시작하기 | headline in top-quarter copy space |
| Naver 밴드 feed | `ad_creative_family.jpg` | H9 | B2 | 부모님 폰에 설치 | Seollal flight swaps headline to "고향 가시는 길에" |
| Naver SA text | — | H2 / H6, ≤15자 축약형 (e.g. "산불 오면 바로 알림") | B5 first sentence as desc | 사이트링크: 무료 안내 / 사용법 / 가족 연결 | negatives per §9.4 |
| YouTube in-stream | Scripts A/B (§4.4) | end-card H1 | — | 지금 설치 | companion = `hero_banner.jpg` |
| UAC / ASA | icon + `hero_banner.jpg` + Script C | H1, H6 rotate | B5 | Install | store-policy safe wording only |
| Poster A2 | `ad_creative_elder.jpg` | §4.6 layout | B1/B4 | QR + 전화번호 | bottom-quarter text zone |

### 4.4 YouTube scripts (15–30 s, storyboard beats)

**Script A — 「전화 한 통」 (30 s, targets segment b, skippable in-stream)**

| t | Visual | Audio |
|---|---|---|
| 0–3s | Night. City apartment. A woman (50s) sees a news *text headline* on her phone: "산불 확산 우려" — generic wording, **no region name** (naming 경북 would evoke the real 2025 fire, §9.5 item 4), text on screen only, **no fire footage** | (SFX: quiet room, phone buzz) |
| 3–8s | She dials. Ringing tone. Her face: worry. | (SFX: 통화 연결음) VO(따뜻하게): "산불 소식이 나오면, 가장 먼저 하게 되는 일." |
| 8–14s | Cut: countryside morning. Grandmother's phone on the table — **green 안전 screen, `연습 모드` banner visible**. She answers brightly: "응, 여기는 괜찮아~" | VO: "이제, 전화보다 먼저 알 수 있습니다." |
| 14–22s | App UI: Family screen — parent's status card, green. Daughter's phone shows the same. Split-screen of both smiling. | VO: "부모님 댁의 산불 상황을, 부모님과 함께, 내 휴대폰에서도." |
| 22–27s | Card: 큰 글씨 "생명을 지키는 기능은 모두 무료입니다" | VO: "생명을 지키는 기능은 모두 무료입니다." |
| 27–30s | Logo + 산불지킴이 + store badges. Super(small): "재난문자·119를 보완하는 보조 수단입니다 · 시연 화면" | VO: "산불지킴이." |

**Script B — 「세 가지 색」 (20 s, product explainer, both digital segments)**

| t | Visual | Audio |
|---|---|---|
| 0–4s | Full-screen green 안전 UI (demo banner visible), elderly hand holding phone steadily | VO: "초록이면, 안심하셔도 됩니다." |
| 4–9s | Amber 주의 UI: 준비 카드 3장이 순서대로 | VO: "노랑이면, 함께 준비합니다." |
| 9–14s | Red 대피 UI: 큰 버튼 하나 → 지도 위 도보 경로 | VO: "빨강이면, 대피소까지 가는 길을 안내해 드립니다." |
| 14–20s | Three colors side by side → logo. Super: H1 + disclaimer + "시연 화면 · 연습 모드" | VO: "복잡한 앱이 아닙니다. 색 하나, 버튼 하나. 산불지킴이 — 무료입니다." |

**Script C — 「우리 마을」 (15 s bumper, built from `promo_video.mp4`)**

| t | Visual | Audio |
|---|---|---|
| 0–5s | `promo_video.mp4`: slow push-in, breeze in the trees, grandmother smiles at the green check screen | (음악: 잔잔한 국악 크로스오버) |
| 5–10s | Super over footage: "산불이 다가오면, 바로 알려드립니다" | VO: "산불이 다가오면, 바로 알려드립니다." |
| 10–15s | Logo + H1 + store badges + disclaimer super | VO: "산불지킴이. 생명을 지키는 기능은 모두 무료입니다." |

Production rules for all three: no flames, no smoke, no destroyed property, no
crying, no sirens-as-fear (short alert chime OK); demo banner never cropped;
disclaimer super ≥ 2 s on end card; AI-generated footage disclosed where the
platform requires (§9.5).

### 4.5 Radio 20 s (ko, 경북·강원 local)

> **(차분하고 따뜻한 남성 또는 여성 성우, 어르신께 말씀드리는 속도로)**
>
> 산불은, 소식이 빠를수록 안전합니다. (쉼)
> 휴대폰에 '산불지킴이'를 설치해 두시면, 산불이 다가올 때 바로 알려드리고,
> 대피소 가는 길도 함께 안내해 드립니다. (쉼)
> 요금도, 가입도 없습니다.
> 자녀분께 한마디 부탁해 보세요 — "산불지킴이, 깔아 다오."
>
> **(로고송/징글 2초)** 산불지킴이.

(약 90음절 + 쉼 = 20초. 협찬고지 필요 시 "이 캠페인은 산불지킴이가
함께합니다"로 대체 — §9.5.)

### 4.6 Poster copy — 경로당 / 보건소 (A2, layout on `ad_creative_elder.jpg`)

```
[상단 — 이미지 영역: ad_creative_elder.jpg, 희망적 이미지 그대로]

[하단 텍스트 영역 — 특대 활자, 고대비]

  산불이 나면, 이 앱이 바로 알려드립니다
  ─────────────────────────────
  무료입니다 · 가입이 없습니다 · 글씨가 큽니다 · 소리로 읽어 드립니다

  ① 자녀분께 부탁하세요 — "산불지킴이 깔아 다오"
  ② 우리 집 주소를 넣어 주세요
  ③ 화면의 색만 보세요
     ● 초록 = 안전   ● 노랑 = 주의   ● 빨강 = 대피

  [QR코드]  설치 도움: ○○경로당 매주 ○요일 / 문의 ○○○-○○○○

  ※ 이 앱은 재난문자와 119의 안내를 보완하는 보조 수단입니다.
     실제 상황에서는 항상 공식 안내를 먼저 따라 주세요.
```

보건소 variant: swap the 설치 도움 line to "설치 도움: 보건소 안내데스크",
and add "진료 대기 중 5분이면 설치해 드립니다." 농협 leaflet (A5): same copy,
front = headline + 3 steps, back = B1 + QR.

English rendering (for the doc record): "When wildfire comes, this app tells
you right away / Free · No sign-up · Big letters · Reads aloud / ① Ask your
child — 'Install WildfireGuardian for me' ② Enter your home address ③ Just
watch the color — green = safe, amber = watch, red = evacuate."

(The color legend uses the app's exact level words — 안전/주의/대피, Safe/Watch
— so what elders memorize from the poster matches what the screen says.)

### 4.7 App store listing (ASO)

| Field | ko | en |
|---|---|---|
| Title (≤30자) | 산불지킴이 – 산불 알림·대피 안내 | WildfireGuardian: Fire Alerts |
| Subtitle/short desc (≤30자) | 생명을 지키는 기능은 모두 무료 | Wildfire alerts & evacuation |

**Description (ko):**

> 산불지킴이는 위성 화재 관측을 바탕으로, 우리 집 기준의 산불 상황을 알기
> 쉽게 보여드리는 앱입니다.
>
> **세 가지 색이면 충분합니다**
> · 초록(안전): 안심하셔도 됩니다 — 오늘의 상황과 준비 안내를 보여드립니다
> · 노랑(주의): 산불의 거리와 바람 방향, 준비할 일을 알려드립니다
> · 빨강(대피): 큰 버튼 하나로 대피소까지 가는 도보 경로를 안내합니다
>
> **어르신을 생각해 만들었습니다**
> · 큰 글씨, 큰 버튼, 쉬운 우리말
> · 모든 안내를 소리로 읽어 드립니다
> · 화면마다 해야 할 일은 딱 하나
>
> **생명을 지키는 기능은 모두 무료입니다**
> 위험 알림, 지도, 확산 예측 안내, 대피 경로, 대피소 찾기 — 전부 무료이며,
> 가입 없이 바로 사용합니다.
>
> **가디언 플러스 (선택, 유료)**
> 가족 함께 알림, 문자·전화 알림, 오프라인 지도, 여러 주소 지켜보기 등
> '편의 기능'만 유료입니다. 안전 기능은 유료화하지 않습니다.
>
> ※ 본 앱은 행정안전부 재난문자, 119 등 공식 재난 대응 체계를 보완하는 보조
> 수단이며, 이를 대신하지 않습니다. 실제 재난 시 공식 안내를 먼저 따라 주세요.
> ※ 연습(데모) 모드의 화면과 시나리오는 훈련용 가상 자료이며 화면에 항상
> '연습 모드'로 표시됩니다.

**Description (en):**

> WildfireGuardian turns satellite fire observations into plain answers about
> *your* home: Am I safe right now? What should I prepare? Which way do I go?
>
> **Three colors are enough**
> · Green (Safe): at ease — today's conditions and preparedness tips
> · Amber (Watch): fire distance, wind direction, what to prepare
> · Red (Go): one big button guides you along a walking route to
>   shelter
>
> **Designed for elderly users**
> Big type, big buttons, plain words, read-aloud on every card, one action per
> screen.
>
> **Every life-safety feature is free** — alerts, map, spread guidance,
> evacuation routes, shelters. No account needed.
>
> **Guardian Plus (optional, paid)** adds conveniences only: family circle
> notifications, SMS/phone-call alerts, offline maps, multiple addresses. We
> never paywall safety.
>
> Note: this app supplements — never replaces — official disaster alerts and
> 119. Demo mode is clearly labelled and uses synthetic training scenarios.

**Keyword list (ASO):**

- ko: 산불, 산불 알림, 산불 앱, 대피, 대피소, 대피 경로, 재난, 재난 알림,
  안전, 안전 앱, 부모님, 부모님 안전, 어르신, 시니어, 고령자, 효도 앱, 시골,
  귀농, 바람, 위성
- en: wildfire, fire alert, wildfire alert, evacuation, shelter, escape route,
  disaster alert, safety app, elderly safety, senior safety, parents, korea
  fire, fire map, emergency

ASO ops: refresh keyword set monthly from Naver 검색어트렌드 + store search
console; screenshots must show real UI **with the 연습 모드 banner visible**
and captions from H5/H6/H1; never screenshot fabricated live-fire data (§9.5).

---

## 5. Launch calendar — 8 weeks + always-on

Anchored to the spring fire season (봄철 산불조심기간 Feb 1 – May 15) and
설날 (Seollal, late Jan/early Feb). Suggested absolute anchor: W1 = last full
week of January — so the 산불조심기간 opening (Feb 1) falls in W2. Seollal
moves each year (2027: Feb 6–8; 2028: Jan 26–28): in a late-January-Seollal
year, slide the whole ramp one week earlier so W2 still covers 귀성 week;
the Feb 1 season anchor stays fixed.

| Week | Theme | Actions | Milestone / gate |
|---|---|---|---|
| **W1** (late Jan) | **Soft launch** | Stores live (listing §4.7); landing page up; 2 pilot 시군 seeded via 경로당 install events (no paid media); analytics events verified; Kakao 채널 opened | Activation funnel measured; crash-free ≥ 99.5%; go/no-go for paid |
| **W2** (early Feb: Seollal + 산불조심기간 opens Feb 1) | **귀성 seeding** | Organic + small Kakao/밴드 flight: "고향 가시는 길에, 부모님 휴대폰에" (H9); leaflets at 농협 창구 in pilot counties; B2G outreach wave 1 (5 시군, §2.4 one-pager posted + calls) | ≥ 40% of installs reach activation (address set) — else fix onboarding before scaling |
| **W3** (mid-Feb) | **Press launch** | PR push (§8.1) on the just-opened 산불조심기간 hook; Naver SA on; radio starts 경북·강원; poster wave 1 (500 sites) | Coverage in ≥ 3 outlets incl. 1 지역지; brand-search volume baseline |
| **W4** | **Paid ramp 1** | Kakao Moment + 밴드 to 50% budget rate; YouTube Scripts A/B live; first B2G MOU target signed; install events ×4 | CPI within 1.5× assumption (§6.4) or creative iteration |
| **W5** | **Paid ramp 2** | YouTube to full flight; Meta on; Google App Campaigns + ASA on; poster wave 2 (보건소·복지관) | Family-circle attach ≥ 15% of activated (b-segment cohorts) |
| **W6** (early Mar) | **Peak begins** | All channels at peak rate; ₩150M tier: local TV spots start; 대한노인회 co-branded install month kickoff (§8.3); B2G outreach wave 2 (10 시군) | WAU in target regions growing WoW; 2nd MOU |
| **W7** (mid Mar) | **Peak** | Sustain; rotate headlines (H2→H4→H1); publish pilot-county story with 지자체 (with their sign-off); radio frequency up | Plus conversion measurable; CAC by channel reviewed, kill bottom channel |
| **W8** (late Mar) | **Peak → handover** | Sustain through end of March; retention push (가족 연결 리마인드 via Kakao 채널); full campaign review; reallocate per measured CAC; write down learnings | Transition to always-on; fall re-peak plan drafted |

**Always-on layer (post-W8, year-round):**

| Cadence | Activity |
|---|---|
| Continuous | Naver SA on brand + core keywords (small); ASA brand defense; store replies within 48h |
| Weekly | Kakao 채널 + 밴드 preparedness content (체크리스트, 대피소 알아두기 — never fear content) |
| Monthly | ASO keyword refresh; 1 경로당/복지관 install visit per active region; B2G pipeline touch |
| Seasonal | **Fall dry-season mini-peak (Nov, 가을철 산불조심기간)** at ~25% of spring spend; Chuseok 귀성 flight mirrors W2 |
| Event-driven | **Circuit breaker per §9.4 — paid off in affected regions during any active major fire; owned channels switch to safety-info-only, zero promotion, zero Plus mention** |

---

## 6. Budgets — three tiers

> **All CPI/CAC/conversion figures in this section are PLANNING ASSUMPTIONS,
> not measurements.** They are pre-launch estimates for a niche safety app in
> the Korean market. Replace them with observed data at W2/W4/W8 gates. Never
> quote them externally.

### 6.1 Tier 1 — ₩5,000,000 (community-first proof)

Philosophy: no broad paid media; prove the community install loop + seed brand.

| Line | ₩ | Notes |
|---|---|---|
| Print (A2 posters ×800, A5 leaflets ×20,000; 경로당·보건소·농협) | 1,500,000 | 2 pilot 시군 saturation |
| Install events (10회: transport, helpers, materials) | 1,000,000 | target 60–120 installs/event |
| Naver SA (brand + core keywords) | 1,000,000 | capture radio/PR-driven search |
| Kakao 채널 운영 + small Moment flight | 500,000 | Seollal week only |
| Local radio (1 station, 2 weeks, 20s spot) | 700,000 | 경북 우선 |
| Contingency | 300,000 | |
| **Total** | **5,000,000** | Assumption: 3,000–6,000 installs, blended CPI ₩900–1,700 (community installs are cheap but labor-heavy) |

### 6.2 Tier 2 — ₩30,000,000 (reference plan; §3 shares)

| Line | ₩ | Share of paid media (₩29M base — contingency excluded) |
|---|---|---|
| YouTube in-stream + bumper | 5,800,000 | 20% |
| Kakao Moment + 채널 | 4,900,000 | 17% |
| Naver SA | 3,800,000 | 13% |
| Community print + install events | 3,800,000 | 13% |
| Local radio (경북+강원) | 3,500,000 | 12% |
| Google App Campaigns | 2,300,000 | 8% |
| Meta (IG/FB) | 2,300,000 | 8% |
| Naver 밴드 | 2,000,000 | 7% |
| Apple Search Ads | 600,000 | 2% |
| Contingency | 1,000,000 | — |
| **Total** | **30,000,000** | Assumption: 15,000–35,000 installs, blended CPI ₩850–2,000 |

### 6.3 Tier 3 — ₩150,000,000 (regional saturation)

| Line | ₩ | Notes |
|---|---|---|
| YouTube (full-funnel, incl. 트로트/뉴스 채널 reservations) | 30,000,000 | Scripts A/B/C rotation |
| Local TV (지역민방/지역MBC 20s, 6주: W6 → mid-April, inside 봄철 조심기간) | 30,000,000 | Script C cutdown; 경북·강원 |
| Kakao (Moment + 비즈보드 + 채널 growth) | 20,000,000 | |
| Naver SA + 브랜드검색 | 15,000,000 | |
| Google App Campaigns | 15,000,000 | |
| Community program (50 install events, 3,000 posters, field staff) | 10,000,000 | the activation engine — do not cut this to buy more digital |
| Meta | 8,000,000 | |
| Local radio (3 stations, 8주: W3 → mid-April) | 7,000,000 | |
| Naver 밴드 | 5,000,000 | |
| Apple Search Ads | 5,000,000 | |
| Contingency | 5,000,000 | |
| **Total** | **150,000,000** | Assumption: 70,000–160,000 installs, blended CPI ₩950–2,100 (TV/radio counted as brand support, not per-install) |

### 6.4 Assumption table (label stays attached wherever these are copied)

| Metric (ASSUMPTION) | Value | Basis |
|---|---|---|
| Android CPI (UAC) | ₩1,500–3,500 | KR utility-app norms |
| iOS CPI (ASA) | ₩2,000–5,000 | KR ASA CPT ₩700–1,500, CVR 25–40% |
| Kakao Moment CPC | ₩300–700 | display norms |
| YouTube CPV (skippable) | ₩30–80 | KR 40–60 targeting |
| Community cost/install | ₩500–1,500 | event labor + print amortized |
| Install → activation (address set) | 45–65% | one-screen onboarding; gate at W2 |
| Activated → family-circle attach | 15–35% | segment-b cohorts higher |
| Family-circle creator → Plus | 2–6% | price-dependent |
| Plus price (placeholder — **pricing not yet set**; Stripe monthly/yearly exist per ARCHITECTURE §9) | ₩4,900/월 · ₩49,000/년 | must be confirmed before any price appears in an ad |
| Plus CAC target | ≤ ₩60,000 | blended, incl. free-user cost share |
| LTV (Plus, 18-mo avg life, placeholder price) | ≈ ₩80,000 | → CAC:LTV target ≥ 1:1.3 at launch, 1:3 by month 12 |

---

## 7. KPIs & measurement (privacy-respecting)

### 7.1 KPI tree

| KPI | Definition | 8-week target (assumption) | Measured how |
|---|---|---|---|
| Installs | store installs, by source | per tier §6 | store consoles + (Android) Play Install Referrer; (iOS) SKAdNetwork coarse postbacks |
| **Activation** | user sets a watched address (the app's "aha") | ≥ 50% of installs | first-party event, no login required |
| **WAU in target regions** | weekly actives whose watched address is in 경북/강원 시군 list | ≥ 35% of WAU | region derived from watched address, **aggregated to 시군 level before storage in analytics** |
| Family-circle attach | activated users who create/join a family circle | ≥ 20% of activated | first-party event |
| Plus conversion | family-circle creators → paying | ≥ 3% | Stripe subscription status (backend `store.py` truth) |
| CAC : LTV | per §6.4 | ≥ 1:1.3 | finance sheet, monthly |
| Elder-reach proxy | installs at 경로당 events + text-size=×1.25 or read-aloud usage share | track, no target yet | first-party events (feature usage, not content) |
| Brand search | "산불지킴이" Naver/Google query volume | up and to the right | Naver Search Advisor / GSC |
| B2G | MOUs signed; posters up; events held | 2 MOUs, 500 sites, 20 events | pipeline sheet |

### 7.2 Privacy rules for measurement (binding)

1. **No ad-network SDK sees location or watched addresses.** Attribution uses
   store-native mechanisms only (Play Install Referrer, SKAdNetwork). No MMP
   that requires device-ID graphing of elderly users.
2. **Region analytics are coarse.** Watched-address region is truncated to
   시군 before it enters any analytics store; raw coordinates stay in the
   serving path only (per ARCHITECTURE: no account needed).
3. **No custom audiences from user data.** We never upload phone numbers /
   emails to Meta/Kakao/Google for matching. Lookalikes only from
   platform-side ad engagement.
4. **Events are behavioral, not content.** We log "route opened", never which
   address, never health/mobility inferences.
5. **Retargeting: platform-standard, 30-day window cap.** Anyone who reached
   the app during an active-fire period in their region is excluded from
   retargeting and Plus upsell prompts for 60 days after (§9.4 rule 5) — no
   "we saw you were in danger, now buy Plus", ever.
6. Legal prerequisites tracked in §9.6 (개인정보보호법, 위치정보법 신고).

---

## 8. PR & partnerships

### 8.1 Press strategy

**Primary angle — the honesty story:**
"생명을 지키는 기능은 전부 무료로 풀었다 — 검증된 연구 시스템에서 출발한
산불 안전 앱" / "The wildfire app that refuses to paywall safety, built from a
validated research system."

What we can honestly say (and the press kit's exact substantiation):

| Claim in press materials | Substantiation handed to journalists |
|---|---|
| "검증된 연구 시스템에서 출발" (built from a validated research system) | `docs/MODEL_CARD.md` + repo; cross-validated on six real Korean wildfires. **Numbers live in the docs, not in our quotes or ads** — journalists may cite the docs themselves |
| "실패까지 기록하는 연구 문화" (a research culture that logs its failures) | The repo's superseded-approaches log — an unusual, genuinely good story |
| "생명 안전 기능 영구 무료" | ARCHITECTURE §1 product rule; store listings |
| "고령 이용자를 위한 설계" | 3-color system, read-aloud, one-action screens — demoable |

What we never say, in any press quote or briefing: guaranteed safety;
"정부 인증/공인/협력" before a signed MOU; casualty counterfactuals ("이 앱이
있었다면 ○명이 살았다" — forbidden, unprovable, obscene); research AUC numbers
in any consumer-facing quote.

**The 2025 fire anniversary (March):** if media revisit the 의성→영덕 fire, we
respond respectfully when asked — motivation, preparedness, free access — and
buy **zero** ads against anniversary coverage or event keywords (§9.4). We do
not pitch anniversary tie-ins.

**Press kit contents:** boilerplate (ko/en), founder/team Q&A, `hero_banner.jpg`
+ icon (marked AI-generated where applicable), screenshot set (demo banner
visible), fact sheet with the free/paid table, research-docs pointer.

**Target outlets:** 연합뉴스, 지역지 (매일신문, 경북일보, 강원일보), IT/스타트업
매체 (전자신문, 바이라인네트워크, 플래텀), 방송 지역 뉴스, 시니어 매체
(브라보마이라이프), and 소셜임팩트 verticals.

### 8.2 산림청 / 지자체 MOU path

Sequence bottom-up (fastest signature first), never claiming endorsement until
ink is dry:

1. **기초지자체 (시·군) pilot** — 2.4 one-pager to 안전재난과/산림과 of 2–3
   경북 시군. Ask: distribution + shelter-list verification. Give: free app,
   install events, 읍면-level usage report. Target: W4–W6 signature.
2. **광역 (경상북도·강원특별자치도)** — with one 시군 pilot running, approach
   도 산림자원과/안전정책과 for multi-군 rollout + 마을방송 연계.
3. **산림청 (Korea Forest Service)** — via 중앙산불방지대책본부 channels and
   public innovation programs; propose data cooperation (shelter/alert feeds)
   and listing in official preparedness materials. Long lead; treat as
   quarter-2+ objective.
4. **행정안전부 / 소방청** — shelter data verification and 재난안전 데이터
   공유 플랫폼 alignment; positions the app as a good citizen of the official
   ecosystem it explicitly defers to.

Rule for all of the above: partnership announcements are co-drafted and
co-approved; we never use an agency logo, seal, or "협력" wording without
written permission (§9.5 checklist item 9).

### 8.3 Senior organizations

- **대한노인회** (nationwide 경로당 network): propose a co-run
  "우리 마을 산불지킴이의 달" (install month) in March — their volunteers +
  our kits (posters, leaflets, QR cards, helper script). Their name appears
  only per their branding rules.
- **노인복지관 / 사회복지협의회**: digital-literacy classes adopt the app as a
  teaching example ("오늘 배운 것: 우리 집 지킴이 설치").
- **이통장협의회 / 새마을회 / 농협 지역조합**: the 이장 is the single most
  trusted broadcast node in a Korean village; 농협 창구 leaflets reach every
  farming household monthly.

### 8.4 Telecom bundling (exploratory)

Pitch to SKT/KT/LG U+ (and senior-focused MVNOs / 효도폰 lines):

1. **Preload or featured placement** on senior-plan Android devices (갤럭시
   시니어 모드) — the distribution shortcut to segment (a).
2. **Zero-rating** the app's data during declared wildfire periods — cheap for
   carriers, headline-worthy, genuinely useful when networks congest.
3. **Plus bundling** into senior/family plans (carrier billing) — revenue
   share; carriers get a warm "가족 안심" story for 부가서비스 lineups.

Honesty guardrail: bundling never makes safety features carrier-exclusive;
the free tier stays identical for everyone.

---

## 9. COMPLIANCE — load-bearing. Read before every flight.

Grounded in current platform policy (checked 2026-08; re-verify quarterly —
links in §9.7).

### 9.1 Google Ads

- **Sensitive Events policy**: during a sensitive event (natural disasters
  explicitly included), Google prohibits ads that exploit or capitalize on the
  event — including **keyword-jacking event terms to drive traffic**, price
  gouging, victim blaming, and products/services that exploit or dismiss the
  event. For us: never bid on live-fire event terms ("○○ 산불", "산불 실시간",
  place-name + 산불 during an active fire), and run the circuit breaker (§9.4).
- **Misrepresentation / Unreliable claims**: no improbable-result promises, no
  guarantees. Any "results" language must reflect what a typical user gets.
  For us: the app *informs*; ads never state or imply a safety outcome
  ("지켜드립니다"-as-guarantee, "안전을 보장" — banned in our own voice rules
  V5, and by Google).
- **Health-adjacent claims** defer to local regulation; our copy stays on
  information delivery, never medical/safety outcomes.

### 9.2 Meta (Facebook/Instagram)

- **Sensational content policy**: no shocking, gruesome, or sensational
  imagery; **disaster and injury imagery is restricted even in PSA/warning
  contexts**. Our creatives comply by design (hopeful imagery only, per
  `marketing/assets/README.md`) — keep every derivative that way. No burning
  hillsides, no smoke plumes, no distressed elders, ever, even "for awareness".
- Ads must not assert or imply personal attributes (age, health) of the viewer
  — target by interest, write copy about *parents*, not "you are old/at risk".
- Automated review is strict and fast; a rejected ad pattern can restrict the
  whole account — pre-flight every variant (§9.5).

### 9.3 Korea — 표시광고법 (Act on Fair Labeling and Advertising) + platform/store rules

표시광고법 제3조 prohibits four types of unfair advertising; our exposure and
controls:

| Type | Our risk | Control |
|---|---|---|
| 거짓·과장 (false/exaggerated) | overstating detection speed/coverage ("모든 산불을 감지") | copy review against ARCHITECTURE facts; keep 실증자료 (substantiation file) for every factual claim, per 광고 실증제 |
| 기만 (deceptive by omission) | shouting "무료" while hiding the paid tier | every "무료" claim is scoped: "생명을 지키는 기능은 모두 무료" + Plus named as paid on landing/store (§1.3 V6) — the honesty rule is also the legal control |
| 부당비교 (unfair comparison) | "다른 재난 앱보다 빠릅니다" without basis | no comparative claims at all at launch |
| 비방 (disparagement) | criticizing official alert systems | forbidden — we *defer* to them (V7) |

Also: 개인정보보호법 + 위치정보법 (location-based service 사업 신고 before
live location features are marketed — §9.6); app-store rules that reject
paywalled emergency info (our free-tier rule already satisfies this, per
ARCHITECTURE §1.1); 방송광고 심의 for radio/TV spots (submit §4.5 script for
심의 with lead time); required sponsorship disclosure (협찬고지) formats.

### 9.4 The circuit breaker (our own rule, stricter than the platforms)

**When a major wildfire is active in Korea (재난문자 issued / 산불 3단계 등):**

1. **Pause all paid media targeting the affected 시·도** within 2 hours
   (pre-built exclusion lists per channel; on-call owner named in the flight
   plan).
2. Owned channels (Kakao 채널, 밴드, site) switch to **safety information
   only** — shelter info, official links, no install CTA, no Plus mention.
3. No press outreach during the acute phase; respond factually if contacted.
4. Resume paid only after the situation is declared contained, and never with
   creative referencing the event.
5. Post-incident: users in affected regions are excluded from retargeting and
   Plus upsell prompts for 60 days (§7.2 rule 5).

This is what "aggressive" means for this brand: aggressive in reach and
preparedness season, absolutely silent as a seller during someone's disaster.

### 9.5 Pre-flight checklist — every ad, every format, before spend

```
□ 1.  No guarantee language ("보장", "100%", "반드시 안전", "지켜드립니다"
      as outcome). Promise = information + guidance only.
□ 2.  Free claim scoped: "생명을 지키는 기능은 모두 무료" — and if the unit
      links to purchase, Plus is named as paid on the landing surface.
□ 3.  No fire/smoke/damage/victim imagery. Hopeful imagery only.
□ 4.  No reference to the 2025 fire (or any real fire) in paid media.
□ 5.  Not scheduled/keyword-targeted against an active fire; exclusion lists
      loaded; circuit-breaker owner named for this flight.
□ 6.  App-screen footage/screenshots show the real 연습 모드/DEMO banner
      (never cropped); any scenario visuals labelled 시연 화면.
□ 7.  Disclaimer present where format allows ≥1 sentence:
      "재난문자·119 안내를 보완하는 보조 수단입니다."
□ 8.  No research metrics (AUC 등) anywhere in the unit or its landing page.
□ 9.  No government/agency logo, seal, "인증/공인/협력" wording without a
      signed, written permission on file.
□ 10. AI-generated imagery disclosed where platform/law requires; never
      captioned as a real family, real rescue, or real event.
□ 11. Korean copy read aloud by a native reviewer: natural 존댓말, no jargon,
      dignified to an 80-year-old listener.
□ 12. Bilingual pair exists (ko + en) and says the same thing.
□ 13. Substantiation note filed: every factual claim mapped to
      ARCHITECTURE.md / MODEL_CARD.md / store policy (광고 실증제).
□ 14. Targeting writes copy about parents/family, never asserting the
      viewer's age, health, or risk (Meta personal-attributes rule).
□ 15. Broadcast units: 심의 submitted; 협찬고지 wording approved.
```

### 9.6 Legal to-do before paid launch (owner: ops)

- [ ] 위치기반서비스사업 신고 (위치정보법) filed and accepted
- [ ] 개인정보 처리방침 published (ko/en), reflecting §7.2 exactly
- [ ] 광고 실증자료 binder started (claims ↔ evidence map)
- [ ] Radio/TV 심의 lead times booked (₩30M+ tiers)
- [ ] Trademark search/filing for 산불지킴이 / WildfireGuardian
- [ ] Plus pricing confirmed (removes §6.4 placeholder)

### 9.7 Policy sources (re-verify quarterly)

- Google Ads — Sensitive events: <https://support.google.com/adspolicy/answer/16489952>
- Google Ads — Misrepresentation: <https://support.google.com/adspolicy/answer/6020955>
- Google Ads — Unreliable claims: <https://support.google.com/adspolicy/answer/15936857>
- Meta — Advertising Standards: <https://transparency.meta.com/policies/ad-standards>
- Meta — Violent/graphic & sensational content: <https://transparency.meta.com/policies/ad-standards/objectionable-content/sensational-content>
- 표시광고법 부당 표시·광고 유형 (소비자24): <https://www.consumer.go.kr/user/bbs/consumer/380/940/bbsDataView/2813.do>
- 표시·광고의 공정화에 관한 법률 (국가법령정보센터): <https://law.go.kr> (검색: 표시광고법)

---

*Document owner: marketing. Copy changes require re-running §9.5. Product
claims are bounded by `docs/app/ARCHITECTURE.md`; when the two disagree,
ARCHITECTURE wins and this file gets fixed.*
