# Documented times, re-read at source (2026-11-16)

`research/harness-2026-11/research-scout/MISSION_A.md` was snippet-only. Every time used in this replay was re-read
on the article page itself on 2026-11-16 (page fetch, HTTP 200) unless marked otherwise. All times are KST.
**SINGLE** = one outlet only. **UNVERIFIED** = could not be re-read at source; kept and labelled, not used as a fact.
Quotes are short and exact. No victim is named here or anywhere in this directory.

## Official alerts, orders and road closures, 영덕군, 25 March 2025

Source: 뉴스로 (newsro.kr) 2025-03-29 14:43, https://www.newsro.kr/articles/832886, block "3.25.(화) 조치사항"
(a county action log reproduced by one outlet: every row is **SINGLE**).

| KST | Entry (quoted) | vs Mission A |
|---|---|---|
| 17:54 | "cctv 산불확인 이후 소방서 신고" | confirmed |
| 18:00 | "주민대피 명령 공고 및 CBS 발송(지품면, 달산면)" | confirmed |
| 18:25 | "황장재 통행제한 CBS 발송" | **corrected**: Mission A had 18:26 "Route 34 closed" |
| 18:52 | "지품면 옥류리 주민대피 CBS 발송" | confirmed |
| 18:58 | "국도34호선(구미~황장) 교통 통제" | **new**: this is the Route 34 closure |
| 19:00 | "중대본 1단계 발령" | new |
| 19:04 | "지품면 도계 → 영양군 방향 도로통제" | new |
| 19:18 | "영해면 대리 주민대피 CBS 발송" | confirmed |
| 19:30 | "주민대피 명령 공고(영덕군 9개읍면)" | confirmed |
| 19:40 | "창수면 주민대피 CBS 발송" | confirmed |
| 20:25 | "눌곡리, 신안리, 낙평리, 수암리, 복곡리, 원전리, 황장리, 지품리, 기사리, 송천리, 구미리 단전" | **corrected**: Mission A had "19:50 power cut in 지품면"; no 19:50 entry. A power cut, not a fire arrival |
| 21:00 | "영덕군 주민대피 CBS 발송" | confirmed |
| 21:15 | "취약계층(장애인, 아동) 관리시설 대피 완료" | new |
| 21:58 | "국도7호선 송라면 지경삼거리에서 영덕방향 교통 통제" | new |

* 문화일보 column https://www.munhwa.com/article/11284913 (texts "only at 9 pm", 매정리 already burning):
  **UNVERIFIED** (page refused the fetch: "403 / 접근이 거부되었습니다"). The 뉴스로 log above lists CBS at 18:00,
  18:52, 19:18, 19:40 and 21:00, so the column's claim conflicts with it as worded; both kept.

## Village-level times

| Place | KST | What (quoted / paraphrased) | Source | Flag |
|---|---|---|---|---|
| 매정리 (영덕읍) | — | texts told only "지품면과 영해면 등의 주민만 대피하라고 알릴 뿐 영덕읍은 빠져 있었다" | 한국일보 2025-03-27 20:00, https://www.hankookilbo.com/news/article/A2025032714350000238 | SINGLE |
| 매정리 | 20:00 | "오후 8시 이장이 집집마다 문을 두드리자" | same | SINGLE, one resident |
| 매정리 | ~20:30 | resident left "오후 8시 30분쯤" (photo caption) | same | SINGLE, one resident |
| 매정리 | ~20:40 | **fire arrival** (resident): "내가 피하고 10분 뒤 불길이 마을을 집어삼켰다" | same | SINGLE, one resident, derived (20:30 + 10 min) |
| 지품면 | ~19:00 | "오후 5시에 대피했는데 재난 문자는 2시간 뒤에 왔다" (relative's account) | same | SINGLE, hearsay |
| 화매리 (영양군 석보면) | ~18:00 | 이장 sent a "스마트 방송" voice message to 46 households; "화염이 마을 가장자리까지 밀고 들어왔고" | 매일신문 2025-03-26 16:43, https://www.imaeil.com/page/view/2025032616432400355 | SINGLE; **corrected** from Mission A "18:13" (page says "오후 6시쯤") |
| 노물리 | ~24:00 | residents "자정이 돼서야 이 사실을 인지했던 것으로 알려졌다" (awareness, not arrival) | 대구신문 2025-03-31 21:38, https://www.idaegu.co.kr/news/articleView.html?idxno=505161 | SINGLE, "알려졌다" |
| 강구면·남정면 | 00:07 (26 Mar) | county text: "새벽 0시7분쯤" | 경향신문 2025-03-26 13:11, https://www.khan.co.kr/article/202503261311001 | SINGLE |
| 강구면·남정면 | ~00:37 (26 Mar) | **fire arrival**: "약 30여분 뒤 산불이 들이닥쳤다" | same | SINGLE, derived |
| 강구면·남정면 | 00:41 (26 Mar) | second text ("다시 보냈다", not a correction) | same | SINGLE |
| 경정리 | ~20:00 | flames over the ridge (Mission A, kbmaeil) | URL not recorded in Mission A | **UNVERIFIED** (not re-read) |

## Rule and rate sources (used by HOTSPOT_RULE.md)

| Item | Status | Source |
|---|---|---|
| 5 h → 위험구역, 8 h → 잠재적 위험구역 when the fire line is known | confirmed: "도달거리 5시간 이내 예상 지역은 위험구역으로 … 8시간 이내는 잠재적 위험구역으로 설정해" | YTN 2025-04-16 18:50, https://www.ytn.co.kr/_ln/0115_202504161850430810 |
| 취약계층 pre-evacuate at stage 2 | confirmed: "취약계층은 2단계 때 사전 대피하도록 합니다" | same |
| 27.6 m/s worst case when the fire line is unknown | confirmed (YTN); 뉴스서울 gives 27.6 m/s only as the observed Andong gust | YTN as above; 뉴스서울 2025-04-16, https://newsseoul.co.kr/news/view/1065591618401273 |
| care facilities pre-evacuate | confirmed: "요양원 및 장애인 시설과 같은 취약시설은 사전대피하고" | 뉴스서울 as above |
| 위험구역 = "leave now" | **NOT stated** in either article (YTN gives three stages 준비 / 실행 대기 / 즉시 실행 without a zone mapping). "Leave now" for the 5 h zone is this replay's reading | — |
| 8.2 km/h | confirmed as a peak-period rate ("확산 속도가 가장 빨랐을 때를 기준으로 시속 8.2㎞"); attributed to an unnamed 산림 당국 official (Ajunews) and to YTN's own satellite analysis (25 March from 03:00, 51 km in 12 h). **Not** found as a named 산림청/국립산림과학원 release. 51 km / 12 h = 4.25 km/h | 아주경제 2025-03-27 15:34, https://www.ajunews.com/view/20250327150623055 ; YTN 2025-03-28 00:52, https://www.ytn.co.kr/_cs/_ln_0108_202503280052156709_005.html |
| spot fires > 3 km ahead; 8 h forecast available, 2 h provided | confirmed (claims of Rep. 서삼석 from 산림청 data); 뉴스서울 says 2 km | 노컷뉴스 2025-10-02 10:08, https://www.nocutnews.co.kr/news/6409424 |
