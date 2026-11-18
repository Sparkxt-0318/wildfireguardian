# SURVEY: where spread prediction is weakest and people are most exposed (kcf-idea-forecast)

Written 18 November 2026 (Asia/Shanghai). Stage 1 of five.

**How the sources were read.** Three search sub-agents opened every page listed under "Opened" and reported one fact from each; I wrote this file from their reports. "Not opened" lists papers that are relevant but returned a login wall, a 403 or a timeout; nothing is quoted from them. A number marked *[news]* comes from a press report, not a paper.

**Starting point (this repo).** `kcf-margin`: a 5 h reach margin of 3.8 km held on 28 California fires and failed for 11 consecutive issue hours on 25 March 2025 in Gyeongbuk (reach up to 40.1 km). `kcf-gust`: no station gust ≥ 20 m/s before or during the first missed hours. `kcf-evidence/NEGATIVE_RESULTS.md` rows 1–4: the learned forecast and FARSITE both score worse than persistence. `kcf-heat`: radiant heat changes few leave-by times.

## Gap 1. Onset of a fast run

**Known.**
- Operational models under-predict. Over 49 evaluation datasets (1,278 observations) 75% showed under-prediction bias and mean percent error ranged 20–310% (Cruz & Alexander 2013). Rothermel-based crown-fire systems (NEXUS, FlamMap, FARSITE, BehavePlus) have a "significant underprediction bias" (Cruz & Alexander 2010).
- The 10% rule: forward spread ≈ 10% of the average 10 m open wind speed, fitted slope about 8%, on wildfires spreading at 0.3–10.5 km/h; mean absolute error 1.11 km/h (Cruz & Alexander 2019, via CSIRO PyroPage 23). An independent check on 88 runs (0.55–12.5 km/h, winds 30–80 km/h) put most within ±35%, with over-prediction below 2 km/h (Cruz & Alexander, *Wildfire* magazine).
- Its stated limits: dry fuel (fine dead fuel moisture ≤ 7.5%), wind > 30 km/h, free-spreading fire on level to undulating terrain. Steep one-directional slopes are called "questionable".
- Extreme documented rates: Kilmore East 2009 above 5 km/h for hours, the active fire zone growing from 14 to 54 km in one hour (CSIRO 2017 article). GOFER reports maximum hourly spread of 2.2–11.3 km/h across its 28 fires (Liu et al. 2024).

**Missing.** No opened source measures skill at predicting *when* a quiet fire starts a run. Every evaluation is of the rate of an established run. The 10% rule is not validated for steep terrain or spotting-dominated spread, which is the Korean case.

**Data.** GOFER hourly reach (`kcf-margin/derived/gofer_reach.csv.gz`), ERA5 hourly wind (Open-Meteo), Himawari and VIIRS detections for 25 March 2025 (`harness-2026-11/data-fetch-2/ahi_kfs01`).

**Opened.** Cruz & Alexander 2013, Environ. Model. Softw. 47:16 (https://research.fs.usda.gov/treesearch/49457). Cruz & Alexander 2010, IJWF 19:377 (https://digitalcommons.usu.edu/barkbeetles/201). CSIRO PyroPage 23, 2019 (https://research.csiro.au/pyropage/wp-content/uploads/sites/17/delightful-downloads/2019/06/CSIRO-PyroPage-Issue-23-Bushfire-ROS-rule-of-thumb.pdf). Cruz & Alexander, *Wildfire* magazine (https://www.iawfonline.org/article/evaluating-the-10-wind-speed-rule-of-thumb-for-estimating-a-wildfires-forward-spread-rate/). CSIRO 2017 (https://www.csiro.au/en/news/all/articles/2017/february/firespotting). Maranghides et al. 2021, NIST TN 2135 summary (https://www.nist.gov/node/1651796): Camp Fire spotting to 6.3 km, winds to 22 m/s.
**Not opened.** Cruz & Alexander 2019, Ann. For. Sci. 76:44 (login). Cruz et al. 2012, For. Ecol. Manage. 284:269 (403).

## Gap 2. Long-range ember transport

**Known.**
- Fall speed: eucalypt bark flakes 2.5–8 m/s; non-spinning karri 5.11 ± 1.08 m/s, jarrah 4.72 ± 1.84 m/s (Ellis 2010). A firebrand reaches terminal velocity in 2–3 s against a burning lifetime of 2–3 min (Tarifa, quoted in Koo et al. 2010).
- Maximum-distance models: Albini 1979 (torching trees), 1981, 1983, and Albini, Alexander & Cruz 2012 (active crown fire). Albini 1979 takes three terrain inputs: ridge-to-valley elevation difference, ridge-to-valley horizontal distance, and whether the source is on a ridgetop, mid-slope or valley bottom (Table 2 of Page et al. 2019). Albini called the 1983 model "speculative".
- Observations: 338 line scans in south-east Australia, maximum spot distance 5 m to 13.9 km, mean 0.9 km, 95th percentile 3.9 km; source-fire area was the strongest predictor (Storey et al. 2020). Northern Rockies 2017: 7,214 spots, 94% within 500 m, maximum 2.7 km (Page et al. 2019).
- Spotting-to-spread models exist as mathematics: a birth-jump integro-differential equation with a minimal wave speed (Hillen et al. 2015, abstract only); randomised level-set fronts (Pagnini & Mentrelli 2014; Kaur et al. 2016; Trucchia et al. 2019). Each states it is a proof of concept without validation.
- The one operational rule found: at spread above about 20 m/min, a spot must land more than 300 m ahead to avoid being overrun (Alexander & Cruz 2006, quoted in Page et al. 2019).

**Missing.** No validated closed-form spread rate for the spotting-dominated regime. No fall-speed or burnout data for *Pinus densiflora* bark or cones. Albini's terrain treatment gives a maximum distance for one idealised ridge; it gives no spread rate.

**Data.** As Gap 1, plus a DEM (AWS Terrarium tiles, about 60 m).

**Opened.** Koo et al. 2010, IJWF 19:818 (https://research.fs.usda.gov/download/treesearch/38384.pdf). Ellis 2010, J. R. Soc. West. Aust. 93:21 (https://www.rswa.org.au/wp-content/uploads/2023/10/VOL-93.1-P-ELLIS-21-27.pdf). Storey et al. 2020, IJWF 29:459 (https://connectsci.au/wf/article-split/29/6/459/21517/Drivers-of-long-distance-spotting-during-wildfires). Page et al. 2019, CJFR 49:317 (https://research.fs.usda.gov/download/treesearch/57899.pdf). Albini 1979 record (https://www.frames.gov/catalog/8153); Albini 1981 record (https://www.frames.gov/catalog/8157); Albini 1983 record (https://firedoc.nist.gov/article/zXczXYQBWEcjUZEYBfF9); Albini et al. 2012 abstract (https://agris.fao.org/search/en/providers/122535/records/65e002a84c5aef494fe789ba). Hillen et al. 2015 abstract (https://lup.lub.lu.se/record/7584943). Pagnini & Mentrelli 2014 (https://nhess.copernicus.org/articles/14/2249/2014/). Kaur et al. 2016 (https://arxiv.org/abs/1601.06272). Trucchia et al. 2019 (https://gmd.copernicus.org/articles/12/69/2019/).
**Not opened.** Martin & Hillen 2016 (403). Sardoy et al. 2007, 2008; Tarifa 1965; Tohidi & Kaye; Boychuk et al. 2009 (walls or not reached).

## Gap 3. Crown-fire transition in pine

**Known.**
- Van Wagner 1977 initiation, as in Scott & Reinhardt 2001 eq. 11: I′ = [CBH·(460 + 25.9·FMC)/100]^1.5 kW/m (CBH canopy base height in m, FMC foliar moisture in %). Active crowning needs R ≥ 3.0/CBD m/min (CBD canopy bulk density, kg/m³).
- Cruz et al. 2005: active crown spread = 11.02·U10^0.90·CBD^0.19·exp(−0.17·EFFM) m/min, n = 37, level terrain, mean absolute error 26%.
- Korean red pine: CBD 0.067–0.27 kg/m³ depending on definition (Lee et al. 2010; Kim et al. 2020), CBH 3.6–5.2 m, critical surface intensity 847–4,392 kW/m by age class (KOSHAM 2016). March cone moisture 10.9% and cone ignition time 19 s in a cone calorimeter (Kwon & Lee 2023).

**Missing.** No field-measured crown-fire spread rate in Korea and no *P. densiflora* model. Cruz's models are for level terrain.

**Data.** No stand-level canopy data for the Gyeongbuk burn area in this repo; Korea Forest Service forest-type maps would need a login. Not testable here in 36 h.

**Opened.** Scott & Reinhardt 2001, RMRS-RP-29 (https://research.fs.usda.gov/download/treesearch/4623.pdf). Cruz et al. 2004 (https://victoriasforestryheritage.org.au/pinefire/Cruz_etal_2004_ModelingTheLikelihoodOfCrownFireOccurrenceInConiferForestStands.pdf). Cruz et al. 2005 (https://victoriasforestryheritage.org.au/pinefire/Cruz_etal_2005_DevelopmentAndTestingOfModelsForPredictingCrownFireRateOfSpread.pdf). Lee et al. 2010 (https://koreascience.kr/article/JAKO201034952231538.page). Kim et al. 2020 (https://www.ukdr.uplb.edu.ph/journal-articles/5545). KOSHAM 2016 (https://scholar.kyobobook.co.kr/article/detail/4010024985764). Kwon & Lee 2023 (https://koreascience.kr/article/JAKO202329058013629.pdf).
**Not opened.** Van Wagner 1977 original.

## Gap 4. Night behaviour

**Known.**
- Vapour-pressure-deficit thresholds below which night detections are rare; flammable night hours rose by 110 per year over 1979–2020 (Balch et al. 2022).
- 1,095 overnight burning events in 23,557 North American fires, 99% in fires over 1,000 ha; daytime drought predicts the following night (Luo et al. 2024).
- GOFER growth peaks at 14–15 h local time with a second peak near 19–20 h (Liu et al. 2024).

**Missing.** Neither paper gives how far a fire travels at night in km/h. No hourly product is validated for Korea; the Himawari product missed the day-to-night transition on 25 March 2025, when spread was fastest (Sung et al. 2025).

**Data.** GOFER hourly reach by local hour. Testable, but the result (night spread is slower on average, with exceptions under wind) is already in Liu et al. 2024.

**Opened.** Balch et al. 2022, Nature 602:442 (https://experts.boisestate.edu/en/publications/warming-weakens-the-night-time-barrier-to-global-fire/). Luo et al. 2024, Nature 627:321 (https://ideas.repec.org/a/nat/nature/v627y2024i8003d10.1038_s41586-024-07028-5.html). Liu et al. 2024, ESSD 16:1395 (https://essd.copernicus.org/articles/16/1395/2024/). Sung et al. 2025, Korean J. Remote Sensing 41:565 (https://www.kjrs.org/journal/view.html?uid=1117&vmd=Full).

## The March 2025 Gyeongbuk fire: what is on record

- 8.2 km/h is a Korea Forest Service briefing figure of 27 March 2025 "based on US satellite thermal detection" *[news, Money Today]*; the method is unpublished. The same briefing gave 51 km in about 12 hours (14:00 on 25 March to 02:00 on 26 March), an average of 4.25 km/h *[news, Newsis]*.
- Gusts of about 27 m/s *[news]*; contested by a civic survey *[news, Daegu MBC 2026]*. This repo's `kcf-gust` found KMA station gusts of 25.1 and 25.4 m/s, both in the evening.
- No measured spotting distance for this fire. The National Institute of Forest Science's general figure is up to about 2 km *[news, SBS]*.
- The only peer-reviewed paper opened (Sung et al. 2025) gives no spread rates.

**Opened.** https://www.mt.co.kr/policy/2025/03/27/2025032716355753806 ; https://www.newsis.com/view/NISX20250327_0003116059 ; https://news.sbs.co.kr/news/endPage.do?news_id=N1008035854 ; https://dgmbc.com/NewsArticle/826650 ; https://eos.org/articles/climate-change-heightened-conditions-of-south-korean-fires .
**Not opened.** MDPI Fire 8(9):363, Fire 9(10):439, Forests 17(2):182 (403).

GAPS_5_TO_7_PLACEHOLDER
