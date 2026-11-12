# Mission A: what goes wrong in wildfire warning and evacuation

Accessed 2026-11-12. **Every item is SNIPPET-ONLY**: page fetching was blocked from the scout container, so each finding was seen only in search-result text. Dates marked "(URL)" are read from the article ID. Verify against the source before citing.

## Korea

| # | Finding | Source | Date | Implication for a leave-by planner |
|---|---|---|---|---|
| K1 | Texts sent people to shelters after fire had probably reached roads and villages; most victims were elderly, in cars or on roads | twig24/Kukmin https://www.twig24.com/news/accident/2025/03/27/20250327008006 | 2025-03-27 (URL) | Check fire arrival on route edges, not only at the village |
| K2 | Shelters changed repeatedly: one shelter changed less than 5 minutes after it was announced; Cheongsong corrected its shelter 3 times (another report says 4) | imaeil https://www.imaeil.com/page/view/2025032617350901807 ; Newsis https://www.newsis.com/view/NISX20250328_0003118155 | 2025-03-26/28 (URL) | Check destinations against the forecast too |
| K3 | Yeongyang resident: about 15 texts said only "피하라" (flee), with no route | Seoul/Kyongbuk coverage (outlet not pinned down) | n/a | Output a route, shelter and time |
| K4 | Elderly residents were warned by the 이장 (village head) or neighbours, not by texts | Newsis NISX20250328_0003118155 | 2025-03-28 (URL) | Budget the 이장's door-to-door round inside the leave-by time |
| K5 | Greenpeace Korea et al. survey (300 residents in Andong, Yeongdeok and Uiseong, plus 32 interviews): village broadcasts and neighbours mattered more than texts (percentages not seen) | https://www.greenpeace.org/static/planet4-korea-stateless/2026/03/d2fe67f5-2025-%EC%98%81%EB%82%A8-%EC%B4%88%EB%8C%80%ED%98%95-%EC%82%B0%EB%B6%88-%EC%8B%A4%ED%83%9C%EC%A1%B0%EC%82%AC-%EC%B5%9C%EC%A2%85%EB%B3%B4%EA%B3%A0%EC%84%9C.pdf | 2026-03 | Weight broadcast and neighbour reach above texts |
| K6 | KFS data via Rep. Seo Sam-seok: 8 h of spread forecast available but only 2 h provided; not re-run after spot fires more than 3 km ahead; text-recommendation alerts not sent to 3 of 5 counties | Nocut https://www.nocutnews.co.kr/news/6409424 | likely autumn 2025 | Re-forecast from spot fires; use a horizon of 8 h or more |
| K7 | The forecast used flat-ground mean wind and underestimated spread; drones and helicopters were grounded, so the fire line was unknown | kbmaeil https://kbmaeil.com/article/20250416500583 | 2025-04-16 (URL) | Use gust-driven upper quantiles; a worst case when the fire line is unknown |
| K8 | 행안부/산림청 plan: max gust instead of mean wind; land the fire can reach within 5 h = risk zone (leave now); within 8 h = potential risk zone (vulnerable people leave first); 27.6 m/s worst case if the fire line is unknown; 읍·면-wide orders at gusts of 20 m/s or more; care facilities evacuate in advance | newsseoul https://newsseoul.co.kr/news/view/1065591618401273 ; YTN https://www.ytn.co.kr/_ln/0115_202504161850430810 | 2025-04-16 | **Official benchmark for our leave-by times** |
| K9 | 행안부 alert reform: standard texts must say when, where and how; village loudspeaker re-broadcast; automated voice calls; county → village → in-person helper chain | newsseoul https://newsseoul.co.kr/news/view/1065590420237796 ; Kyunghyang https://www.khan.co.kr/article/202508272014015/ | 2025-08-27 | Our output can feed the when/where/how wording |
| K10 | Amendment to the 재난 및 안전관리 기본법 (Disaster and Safety Management Act), cabinet-approved: evacuation orders must give specific methods; plans required for people who cannot self-evacuate; takes effect 6 months after publication (publication not confirmed) | fnnews https://www.fnnews.com/news/202606301244473177 | 2026-06-30 | Fits the new planning duty |
| K11 | Board of Audit and Inspection (BAI) audit pooled across Uljin 2022, Itaewon and Miryang: disaster texts averaged 1 h 39 min from situation rooms, 28 of 67 (41.8%) never sent; Uljin CCTV could see the ignition point but nobody was assigned to watch it | Newsis https://www.newsis.com/view/NISX20251023_0003373693 | 2025-10-23 (URL) | Assume a 1-2 h alert delay or a missing alert |
| K12 | Yeongdeok 매정리 care home: car left about 21:00, caught fire on Route 7 within about 10 minutes of embers starting; 3 of 6 on board died; chaotic traffic with wrong-way cars | Seoul Shinmun https://m.seoul.co.kr/news/2025/03/26/20250326500007 ; JoongAng Daily https://www.koreajoongangdaily.com/korea/three-die-as-aged-care-facility-evacuation-ends-in-disaster/12354127 | 2025-03-26 | Earlier facility leave-by; congestion on the single highway |
| K13 | Yeongyang 석보면: a family reached the shelter, then went back home for a tractor and died; the 삼의리 이장 couple died driving toward the fire to rescue a relative; 3 others died at home (reports conflict on whether these cases overlap) | Segye https://www.segye.com/newsView/20250326520531 ; Hankyung https://www.hankyung.com/article/2025032686617 ; MT https://www.mt.co.kr/society/2025/03/26/2025032614151447220 | 2025-03-26 | Model return trips as a failure mode |
| K14 | Narrow two-lane roads; the 서산영덕 (Sangju-Yeongdeok) expressway closed; phone and data networks down in some counties early on 26 March | imaeil (as K2) ; Asiae https://www.asiae.co.kr/en/article/2025032608022873968 | 2025-03-26 | Capacity limits; text delivery can fail |
| K15 | KFS: "예측 못했다" (we did not predict it) that the fire would reach Yeongdeok; 51 km in about 12 h | Hankyung https://www.hankyung.com/article/2025032735267 ; Nate https://news.nate.com/view/20250327n40566 | 2025-03-27 | Case for probabilistic long-tail forecasts |

### Village timeline, 25-26 March 2025 (for F-C1 and model checks)

**Yeongdeok**

| Time | Event | Source |
|---|---|---|
| 17:54 | CCTV detects the fire | Newsro https://www.newsro.kr/articles/832886 (single outlet) |
| 18:00 | Order and cell broadcast for 지품면 and 달산면 | Newsro; Munhwa column https://www.munhwa.com/article/11284913 |
| 18:26 | Route 34 closed near 황장재 | Newsro |
| 18:52 | Text for 지품면 옥류리 | Newsro |
| 19:18 | Text for 영해면 대리 | Newsro |
| 19:30 | Order for all 9 읍·면 | Newsro |
| 19:40 | Text for 창수면 | Newsro |
| 19:50 | Power cut in 지품면 (another outlet: 20:25) | Newsro |
| 21:00 | County-wide text | Newsro |

- **Conflict:** the Munhwa column says texts came "only at 9 pm", by which time 매정리 was already burning.
- **매정리:** a resident received texts naming only 지품면 and 영해면, not 영덕읍, and left about 20:30 on the 이장's word. Six people died there, the most of any village (Hankook Ilbo https://www.hankookilbo.com/news/article/A2025032714350000238).
- **경정리:** a resident says flames came over the ridge behind the village about 20:00; people escaped by boat; 104 were trapped on breakwaters (kbmaeil).
- **노물리:** residents became aware only around midnight (Daegu Shinmun https://www.idaegu.co.kr/news/articleView.html?idxno=505161).
- **강구면 / 남정면:** text at 00:07; fire arrived about 30 minutes later; corrected text at 00:41 (Kyunghyang https://www.khan.co.kr/article/202503261311001).
- **Siren:** never sounded, per a testimony book (https://www.m-economynews.com/news/article.html?no=70353).

**Cheongsong**

| Time | Event | Source |
|---|---|---|
| 16:50s | Texts to 파천 병부리 and 안덕 고와리 | Ajunews, Gukjenews, Kyunghyang |
| 17:12 | All of 파천면 to the sports centre | same |
| 17:29 | Order for 파천면 and 진보면 | https://www.khan.co.kr/article/202503251742011 |
| ~17:30 | Fire crosses from Andong 길안면 | n/a |
| 17:42 | County-wide text | same |
| ~18:00 | Flames on the hill opposite the 파천 office, about 30 minutes after the order | Yeongnam https://www.yeongnam.com/web/view.php?key=20250326021353530 |

- **Conflict:** imaeil (2025-03-30) quotes a resident: no text for more than 5 hours, and the shelter changed 4 times.

**Andong**

- About 17:00: fire near the 길안면 office, followed by an order to go to central Andong. No minute stamps found.

**Yeongyang**

| Time | Event | Source |
|---|---|---|
| ~18:00 | Fire into 입암면 and 석보면 | n/a |
| 18:13 | 화매리 이장 sends a smart-broadcast voice call to 46 households; wireless service cutting out around then | imaeil 2025032616432400355 |
| ~20:00 | 삼의리 이장 couple found dead | n/a |

**8.2 km/h figure**

- Announced 27 March 2025 by 산림청 and 국립산림과학원 (원명수, head of the national forest satellite information centre).
- Measured from US satellite heat detections, about 2 passes a day.
- Described as "시간당 평균 8.2km" (hourly average) during the fastest-spreading period, with gusts to 27 m/s. It is not an instantaneous front speed.
- Sources: Ajunews https://www.ajunews.com/view/20250327150623055 ; YTN https://www.ytn.co.kr/_cs/_ln_0108_202503280052156709_005.html
- Original press release not found.

## Abroad

| # | Finding | Source | Date | Implication |
|---|---|---|---|---|
| X1 | West Altadena: first order at 3:25 am on Jan 8; never got a "warning"; signs of westward spread from 9:30 pm on Jan 7 | FSRI https://fsri.org/news/new-report-shows-fire-shifted-toward-west-altadena-hours-official-accounts | late 2025 | Compute leave-by for every zone the forecast reaches |
| X2 | 18 of 19 Eaton deaths were in west Altadena | LA Times via https://www.fireengineering.com/?p=703008 | 2025-11-02 | Show the forecast-to-alert gap per zone |
| X3 | Midnight suggestion to widen orders went unheeded; a May 2026 review found "no failure" | via https://goodfest.westfield.com/2026/05/report-finds-no-failures-in-altadena-fire-evacuations-critics-decry-lack-of-accountability/ | 2026-05 | Time-stamped recommendation log |
| X4 | LA County after-action review (AAR): "slow, convoluted" decision chain; outdated policies; system switch from CodeRED to Genasys with 4 trained staff; alerts needing a link click; Joint Information Center opened 3 days after ignition | https://file.lacounty.gov/SDSInter/lac/1192778_AAR_HighlightsandRecommendations.pdf ; CBS https://www.cbsnews.com/losangeles/news/la-county-report-eaton-palisades-fires-evacuation-alert-failures | 2025-09-25 | Pre-compute zone alert text; flag zone edges that cut across the forecast fire path |
| X5 | Eaton victims: mostly over 65, mean age 77; disabled residents | GV Wire https://gvwire.com/?p=183503 | 2025 | Earlier leave-by for older and disabled residents |
| X6 | Care facilities (MonteCedro, Terraces at Park Marino) left residents behind; about 95 residents waited in a car park for a SWAT vehicle and a bus | https://www.spokesman.com/stories/2025/nov/12/residents-were-left-behind-at-senior-facilities-as | 2025-11-12 | Facility clearance time and room checks |
| X7 | Palisades: order about 40 min after crews were responding; gridlock; bulldozed cars | AP https://www.pbs.org/newshour/nation/homes-were-burning-and-roads-jammed-before-evacuation-order-for-palisades-fire-ap-finds | 2025-01 | Congestion and closures in the route check |
| X8 | Lahaina: sirens not sounded (fear of sending people uphill toward the fire); cell and internet outages | NBC https://www.nbcnews.com/news/us-news/maui-emergency-management-director-defends-decision-not-sound-sirens-f-rcna100336 | 2023-08-17 | Direction plus destination; channel failure |
| X9 | Lahaina roadblocks; FSRI report: 84 findings, 140 recommendations; drivers who went around barricades survived | https://ag.hawaii.gov/wp-content/uploads/2024/09/FSRI_Lahaina_Report_Findings_and_Recommendations_09102024.pdf ; https://www.adn.com/nation-world/2023/08/23/in-deadly-lahaina-fires-many-in-vehicles-found-no-way-out-those-who-drove-around-barricades-survived/ | 2024-09 / 2023-08 | Closures as inputs; alternative routes |
| X10 | Lahaina deaths: about 42 in buildings, 39 outdoors, 15 in vehicles; more than two-thirds aged 60 or over | Civil Beat https://www.civilbeat.org/2024/02/maui-police-report-reveals-locations-of-lahaina-fire-victims-and-lessons-learned/ | 2024-02 | Post-deadline fallback |
| X11 | Maui: about 40% of firefighting resources already committed elsewhere | AP https://www.pbs.org/newshour/nation/maui-fire-department-report-on-deadly-wildfire-details-how-it-was-no-match-for-unprecedented-blazes | 2024-04-16 | Do not assume escorts or rescues are available |
| X12 | Paradise: zoned orders (first at 7:46 am); about 3 h for 11 mi on the Skyway; at least 7 died in vehicles | https://gizmodo.com/as-camp-fire-overtook-paradise-many-were-gridlocked-or-1830524170 | 2018 | Test staggered release against fast spread |
| X13 | Camp Fire: CodeRED opt-in; no Wireless Emergency Alert (WEA) sent; an operator on vacation | GovTech https://www.govtech.com/public-safety/deadly-camp-fire-did-not-prompt-an-emergency-alert.html | 2018-11 | Multiple channels plus door-to-door |
| X14 | Camp Fire victims: mean age 72; 77% over 65; many in mobile homes | CalMatters https://calmatters.org/projects/older-californians-increased-risk-wildfires/ | 2019-22 | Independent older residents are the larger at-risk group |
| X15 | Black Saturday: 113 of 173 died in houses; 44% vulnerable | https://insurancenews.com.au/local/royal-commission-most-bushfire-victims-died-indoors | 2009-10 | Registry of people needing help, with an earlier trigger |
| X16 | CSIRO: 48.3% of 1901-2011 bushfire deaths involved late evacuation | https://www.csiro.au/en/news/all/articles/2016/december/bushfire-loss-data | 2016-12 | Present leave-by as an early deadline with a buffer |
| X17 | NSW Bushfire Inquiry Recommendations 71 and 73 (aged-care plans, vulnerable people); Royal Commission Ch. 12 | https://www.nsw.gov.au/departments-and-agencies/premiers-department/access-to-information/nsw-bushfire-inquiry/nsw-bushfire-inquiry-report | 2020-08 | Align with care-facility decision guidelines |
| X18 | Mallacoota: no primary timeline found | IGEM https://www.igem.vic.gov.au/node/494 | n/a | One-road towns need a fixed early trigger |

### Not found

- Final report text of the 2009 Victorian Bushfires Royal Commission.
- Maui Police final after-action review.
- California Department of Social Services (CDSS) facility reports.
- Butte County Grand Jury report.
- Lahaina WEA timing.
- Uljin-only alert delay figures.
- Survey percentages from the Greenpeace report.
