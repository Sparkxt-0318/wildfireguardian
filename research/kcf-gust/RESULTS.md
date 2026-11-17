# RESULTS: gusts on 25 March 2025 and the frozen gust-class margin (kcf-gust)

**PROVISIONAL (hour-by-hour tables).** KMA observations were added after the first version of this file (see "KMA ASOS observations",
amendment 1 in `PROTOCOL.md`), but only what data.go.kr serves: **daily** maximum instantaneous gust with its time, and **hourly mean wind**.
The **hourly maximum gust** series (apihub.kma.go.kr, `KMA_API_KEY`, which also holds AWS) was not available in this session, so the
hour-by-hour class and R-held tables below are still ERA5 only and PROVISIONAL. Rules: `PROTOCOL.md`, committed before any gust value
was read (a4ff4f1c); amendment 1 committed before any KMA value was read (3be97228).

**Result.** ERA5 gusts were below 20 m/s at every point until 15:00 KST, and the fire-wide maximum at the 10:00 and 11:00
stamps was 10.6 and 12.6 m/s. So gusts as observed at the issue hour gave no warning at 10-11 KST either. A gust >= 20 m/s
appears only *ahead* of those hours: the next-5 h maximum from 10 KST is 21.0 m/s (15:00, Yeongyang grid cell), and from 11 KST
21.9 m/s. Reading that forward window as a perfect forecast (ASSUMED, as in the margin protocol), the gust >= 20† class would
have applied from the 10 KST issue hour on, and the frozen R(5 h) = 8.6 km held at 10 and 11 KST (reach 4.9, 6.6 km) and failed
from 12 KST (reach 12.4 km) to 20 KST. † The gust >= 20 m/s class rests on **9 fires**.

## Sources and fetch times

ERA5 10 m wind gust, Open-Meteo archive API (`models=era5`, `hourly=wind_gusts_10m`, m/s, GMT), 2025-03-22 to 2025-03-26.
Each value is the maximum over the hour before its stamp. Raw responses: `work/era5_gusts.json` and `work/fetch_log.json` (both committed).

| point | ERA5 grid cell | fetched (UTC) |
|---|---|---|
| Uiseong | 36.25 N 128.75 E | 2026-11-17T02:01:17+00:00 |
| Andong | 36.5 N 128.75 E | 2026-11-17T02:01:18+00:00 |
| Cheongsong | 36.5 N 129.0 E | 2026-11-17T02:01:19+00:00 |
| Yeongyang | 36.75 N 129.0 E | 2026-11-17T02:01:19+00:00 |
| Yeongdeok | 36.5 N 129.25 E | 2026-11-17T02:01:20+00:00 |

KMA ASOS via data.go.kr (`AsosDalyInfoService`, `AsosHourlyInfoService`), key held outside the repo and never logged:

| point | station | daily fetched (UTC) | hourly fetched (UTC) |
|---|---|---|---|
| Uiseong | ASOS 278 | 2026-11-17T02:46:28+00:00 | 2026-11-17T02:46:29+00:00 |
| Andong | ASOS 136 | 2026-11-17T02:46:29+00:00 | 2026-11-17T02:46:30+00:00 |
| Cheongsong | ASOS 276 | 2026-11-17T02:46:34+00:00 | 2026-11-17T02:46:35+00:00 |
| Yeongdeok | ASOS 277 | 2026-11-17T02:46:36+00:00 | 2026-11-17T02:46:37+00:00 |
| Yeongyang | none (no ASOS id assumed; an AWS site would come from apihub only) | - | - |

Repo note (`research-scout/LOG.md:822`, Newsis 2025-03-27) reports gusts of about 27 m/s for this fire. ERA5 here peaks at 22.4 m/s
(Yeongyang cell, 17:00 KST). The user's recollection of about 14 m/s reanalysis in the repo's record was not found in the repo by search.

## KMA ASOS observations beside ERA5 (data.go.kr; added by amendment 1)

KMA daily maximum **instantaneous** gust (`maxInsWs`) and its time, against the ERA5 daily maximum of the same KST day (ERA5 stamp =
end of the hour). n = 4 stations x 5 days for KMA; Yeongyang has no ASOS here, so ERA5 only. These are daily maxima, not hourly gusts: they
do not enter any class, R or score above.

| point | KMA ASOS station | day | KMA max instantaneous gust m/s (time KST) | ERA5 max gust m/s (stamp KST) | ERA5 minus KMA |
|---|---|---|---|---|---|
| Uiseong | 의성 (278) | 2025-03-22 | 17.9 (15:57) | 17.4 (15:00) | -0.5 |
| Uiseong | 의성 (278) | 2025-03-23 | 8.1 (14:34) | 8.0 (01:00) | -0.1 |
| Uiseong | 의성 (278) | 2025-03-24 | 10.3 (13:48) | 18.7 (11:00) | +8.4 |
| Uiseong | 의성 (278) | 2025-03-25 | 14.5 (17:10) | 19.2 (17:00) | +4.7 |
| Uiseong | 의성 (278) | 2025-03-26 | 8.2 (16:00) | 11.5 (16:00) | +3.3 |
| Andong | 안동 (136) | 2025-03-22 | 15.4 (14:26) | 16.5 (16:00) | +1.1 |
| Andong | 안동 (136) | 2025-03-23 | 7.5 (15:15) | 7.8 (16:00) | +0.3 |
| Andong | 안동 (136) | 2025-03-24 | 13.4 (15:11) | 17.9 (12:00) | +4.5 |
| Andong | 안동 (136) | 2025-03-25 | 19.7 (17:44) | 19.8 (16:00) | +0.1 |
| Andong | 안동 (136) | 2025-03-26 | 5.7 (00:08) | 10.4 (01:00) | +4.7 |
| Cheongsong | 청송군 (276) | 2025-03-22 | 16.5 (15:09) | 18.4 (16:00) | +1.9 |
| Cheongsong | 청송군 (276) | 2025-03-23 | 7.1 (13:17) | 9.9 (01:00) | +2.8 |
| Cheongsong | 청송군 (276) | 2025-03-24 | 12.0 (14:23) | 19.4 (12:00) | +7.4 |
| Cheongsong | 청송군 (276) | 2025-03-25 | 25.1 (18:15) | 20.6 (18:00) | -4.5 |
| Cheongsong | 청송군 (276) | 2025-03-26 | 7.8 (01:58) | 14.7 (01:00) | +6.9 |
| Yeongyang | none assumed (no ASOS id; AWS needs apihub) | 2025-03-22 | - | 18.3 (16:00) | - |
| Yeongyang | none assumed (no ASOS id; AWS needs apihub) | 2025-03-23 | - | 7.9 (01:00) | - |
| Yeongyang | none assumed (no ASOS id; AWS needs apihub) | 2025-03-24 | - | 21.4 (12:00) | - |
| Yeongyang | none assumed (no ASOS id; AWS needs apihub) | 2025-03-25 | - | 22.4 (17:00) | - |
| Yeongyang | none assumed (no ASOS id; AWS needs apihub) | 2025-03-26 | - | 13.4 (01:00) | - |
| Yeongdeok | 영덕 (277) | 2025-03-22 | 17.8 (14:28) | 16.4 (15:00) | -1.4 |
| Yeongdeok | 영덕 (277) | 2025-03-23 | 11.6 (05:08) | 11.0 (01:00) | -0.6 |
| Yeongdeok | 영덕 (277) | 2025-03-24 | 15.2 (09:15) | 18.6 (12:00) | +3.4 |
| Yeongdeok | 영덕 (277) | 2025-03-25 | 25.4 (21:56) | 20.4 (23:00) | -5.0 |
| Yeongdeok | 영덕 (277) | 2025-03-26 | 9.9 (15:52) | 15.8 (01:00) | +5.9 |

- On 25 March KMA observed >= 20 m/s at two of four stations: Cheongsong 25.1 m/s at 18:15 and Yeongdeok 25.4 m/s at 21:56 KST (Andong 19.7 at
  17:44, Uiseong 14.5 at 17:10). Neither >= 20 gust falls at 10-11 KST. ERA5 read **lower** than KMA at the two stations that peaked
  (-4.5 and -5.0 m/s) and **higher** at Uiseong (+4.7); on 22 March the differences are -1.4 to +1.9. So ERA5 reads low here at the two peak
  stations only; one day, four stations, no general bias is claimed.
- The daily series cannot say what the maximum gust was in any given hour, and a gust >= 20 m/s earlier in the day is not excluded by it. It
  shows that the daily maximum at every station occurred at 14:26 or later on 22 and 25 March; the 25 March times are 17:10 to 21:56.
- The >= 20 m/s class rests on **9 fires**; the observed 25.1 and 25.4 m/s are above anything this calibration can speak to.

KMA hourly **mean** wind `ws` on 25 March (m/s, KST hour; mean, not gust; Cheongsong has no value from 21:00):

| KST hour | Uiseong | Andong | Cheongsong | Yeongdeok |
|---|---|---|---|---|
| 00:00 | 0.2 | 0.2 | 0.5 | 1.5 |
| 01:00 | 0.1 | 1.2 | 0.2 | 2.1 |
| 02:00 | 0.3 | 1.5 | 0.8 | 2.0 |
| 03:00 | 0.0 | 0.9 | 0.6 | 2.8 |
| 04:00 | 0.4 | 0.6 | 0.4 | 2.1 |
| 05:00 | 0.1 | 1.3 | 0.6 | 4.1 |
| 06:00 | 0.0 | 1.3 | 0.4 | 4.2 |
| 07:00 | 0.2 | 1.0 | 0.9 | 4.2 |
| 08:00 | 0.1 | 0.1 | 0.3 | 2.7 |
| 09:00 | 0.4 | 1.4 | 0.5 | 2.6 |
| 10:00 | 0.5 | 1.4 | 0.5 | 1.8 |
| 11:00 | 2.7 | 0.6 | 1.8 | 3.8 |
| 12:00 | 2.0 | 1.5 | 4.7 | 2.8 |
| 13:00 | 3.4 | 2.1 | 3.4 | 2.4 |
| 14:00 | 4.3 | 3.5 | 2.9 | 3.6 |
| 15:00 | 3.8 | 4.5 | 3.1 | 4.7 |
| 16:00 | 5.9 | 7.8 | 4.6 | 4.0 |
| 17:00 | 6.2 | 6.5 | 5.4 | 2.6 |
| 18:00 | 5.6 | 8.7 | 8.7 | 3.4 |
| 19:00 | 6.5 | 7.7 | 8.5 | 4.8 |
| 20:00 | 4.7 | 6.9 | 7.0 | 8.8 |
| 21:00 | 2.1 | 3.4 | n/a | 10.5 |
| 22:00 | 1.6 | 3.5 | n/a | 12.2 |
| 23:00 | 2.5 | 2.0 | n/a | 10.5 |

At 10:00 and 11:00 KST the hourly mean wind is 0.5 to 3.8 m/s at all four stations. That is a mean, so it is only an indication that the
hours had no strong wind; it does not bound the gust.

## Hour by hour, 25 March 2025 KST, 00 to 24 (ERA5 only, PROVISIONAL)

Columns 2-6: ERA5 gust at the stamp (m/s, max over the previous hour). Class at stamp: < 10, 10-20, >= 20. Forward columns:
issue hour t = the row, window (t, t+h], maximum over the five points, class, frozen R(h) at the 10% target (km), reach from
detections (km, `numbers.json` -> `gyeongbuk_stress`), and whether reach <= R. "Not scored" = the h-hour window runs past the
end of AHI coverage. n = 1 fire, 1 day. R values: gust < 10: 2.6 / 3.0; 10-20: 4.7 / 5.9; >= 20†: 8.6 / 12.0 km.
**PROVISIONAL, ERA5 only.**

| KST stamp | Uiseong | Andong | Cheongsong | Yeongyang | Yeongdeok | fire-wide max | class at stamp | 5 h: fwd max / class / R / reach / verdict | 8 h: fwd max / class / R / reach / verdict |
|---|---|---|---|---|---|---|---|---|---|
| 00:00 | 6.2 | 5.8 | 8.6 | 7.8 | 9.3 | 9.3 | <10 | 8.8 / <10 / R 2.6 / reach 0.8 / held | 8.8 / <10 / R 3 / reach 0.8 / held |
| 01:00 | 5.7 | 5.5 | 8.0 | 7.0 | 8.8 | 8.8 | <10 | 8.1 / <10 / R 2.6 / reach 0.8 / held | 9.2 / <10 / R 3 / reach 0.8 / held |
| 02:00 | 5.0 | 4.8 | 6.7 | 5.9 | 8.1 | 8.1 | <10 | 7.2 / <10 / R 2.6 / reach 0.8 / held | 10.6 / 10-20 / R 5.9 / reach 0.8 / held |
| 03:00 | 3.6 | 3.3 | 5.1 | 4.8 | 7.2 | 7.2 | <10 | 6.4 / <10 / R 2.6 / reach 0.4 / held | 12.6 / 10-20 / R 5.9 / reach 0.4 / held |
| 04:00 | 2.8 | 2.9 | 4.5 | 4.6 | 6.1 | 6.1 | <10 | 9.2 / <10 / R 2.6 / reach 0.0 / held | 14.0 / 10-20 / R 5.9 / reach 2.2 / held |
| 05:00 | 2.7 | 2.9 | 4.3 | 4.8 | 6.4 | 6.4 | <10 | 10.6 / 10-20 / R 4.7 / reach 0.0 / held | 15.4 / 10-20 / R 5.9 / reach 2.2 / held |
| 06:00 | 2.7 | 2.5 | 3.8 | 4.5 | 6.3 | 6.3 | <10 | 12.6 / 10-20 / R 4.7 / reach 0.0 / held | 17.6 / 10-20 / R 5.9 / reach 2.2 / held |
| 07:00 | 3.2 | 2.6 | 3.8 | 4.6 | 6.1 | 6.1 | <10 | 14.0 / 10-20 / R 4.7 / reach 2.2 / held | 21.0 / >=20† / R 12 / reach 4.9 / held |
| 08:00 | 4.2 | 3.7 | 5.5 | 6.4 | 6.3 | 6.4 | <10 | 15.4 / 10-20 / R 4.7 / reach 2.2 / held | 21.9 / >=20† / R 12 / reach 6.6 / held |
| 09:00 | 5.9 | 6.0 | 8.1 | 9.2 | 7.2 | 9.2 | <10 | 17.6 / 10-20 / R 4.7 / reach 2.2 / held | 22.4 / >=20† / R 12 / reach 12.4 / **MISSED** |
| 10:00 | 7.5 | 7.6 | 9.6 | 10.6 | 9.1 | 10.6 | 10-20 | 21.0 / >=20† / R 8.6 / reach 4.9 / held | 22.4 / >=20† / R 12 / reach 23.9 / **MISSED** |
| 11:00 | 10.1 | 9.7 | 11.5 | 12.6 | 10.4 | 12.6 | 10-20 | 21.9 / >=20† / R 8.6 / reach 6.6 / held | 22.4 / >=20† / R 12 / reach 34.7 / **MISSED** |
| 12:00 | 12.0 | 11.4 | 13.0 | 14.0 | 11.6 | 14.0 | 10-20 | 22.4 / >=20† / R 8.6 / reach 12.4 / **MISSED** | 22.4 / >=20† / R 12 / reach 34.9 / **MISSED** |
| 13:00 | 14.1 | 13.3 | 14.3 | 15.4 | 12.5 | 15.4 | 10-20 | 22.4 / >=20† / R 8.6 / reach 23.9 / **MISSED** | 22.4 / >=20† / R 12 / reach 44.0 / **MISSED** |
| 14:00 | 16.5 | 15.9 | 16.4 | 17.6 | 13.9 | 17.6 | 10-20 | 22.4 / >=20† / R 8.6 / reach 34.7 / **MISSED** | 22.4 / >=20† / R 12 / reach 50.3 / **MISSED** |
| 15:00 | 18.6 | 18.8 | 19.3 | 21.0 | 15.7 | 21.0 | >=20† | 22.4 / >=20† / R 8.6 / reach 32.9 / **MISSED** | 22.4 / >=20† / R 12 / reach 46.6 / **MISSED** |
| 16:00 | 18.8 | 19.8 | 19.6 | 21.9 | 15.3 | 21.9 | >=20† | 22.4 / >=20† / R 8.6 / reach 40.1 / **MISSED** | 22.4 / >=20† / R 12 / reach 46.4 / **MISSED** |
| 17:00 | 19.2 | 19.6 | 20.2 | 22.4 | 16.6 | 22.4 | >=20† | 22.1 / >=20† / R 8.6 / reach 38.6 / **MISSED** | 22.1 / >=20† / R 12 / reach 38.6 / **MISSED** |
| 18:00 | 18.8 | 19.0 | 20.6 | 22.1 | 17.7 | 22.1 | >=20† | 20.4 / >=20† / R 8.6 / reach 27.3 / **MISSED** | 20.4 / >=20† / R 12 / reach 27.3 / **MISSED** |
| 19:00 | 18.5 | 17.0 | 19.5 | 18.6 | 19.5 | 19.5 | 10-20 | 20.4 / >=20† / R 8.6 / reach 20.3 / **MISSED** | 20.4 / >=20† / R 12 / reach 20.3 / **MISSED** |
| 20:00 | 15.3 | 14.0 | 16.6 | 17.0 | 18.4 | 18.4 | 10-20 | 20.4 / >=20† / R 8.6 / reach 15.7 / **MISSED** | 20.4 / >=20† / R 12 / reach 15.7 / not scored (truncated) |
| 21:00 | 13.4 | 12.8 | 16.1 | 17.0 | 19.0 | 19.0 | 10-20 | 20.4 / >=20† / R 8.6 / reach 6.5 / held | 20.4 / >=20† / R 12 / reach 6.8 / not scored (truncated) |
| 22:00 | 13.2 | 12.7 | 16.4 | 17.1 | 20.2 | 20.2 | >=20† | 20.4 / >=20† / R 8.6 / reach 4.9 / held | 20.4 / >=20† / R 12 / reach 4.9 / not scored (truncated) |
| 23:00 | 13.3 | 12.7 | 16.6 | 16.9 | 20.4 | 20.4 | >=20† | 18.9 / 10-20 / R 4.7 / reach 3.0 / not scored (truncated) | 18.9 / 10-20 / R 5.9 / reach 3.0 / not scored (truncated) |
| 24:00 | 12.4 | 11.7 | 15.9 | 15.6 | 18.9 | 18.9 | 10-20 | - | - |

† gust >= 20 m/s class: **9 fires**.

## Counts (PROVISIONAL, ERA5 only; one fire, one day; no rate)

| | 5 h | 8 h |
|---|---|---|
| complete issue hours | 23 | 20 |
| gust-class R held | 14 | 9 |
| gust-class R missed | 9 | 11 |
| held / hours in class < 10 | 5 / 5 | 2 / 2 |
| held / hours in class 10-20 | 5 / 5 | 5 / 5 |
| held / hours in class >= 20† | **4 / 13** | **2 / 13** |
| for comparison, prior-3 h class R held (RESULTS of kcf-margin) | 12 | 7 |

† **9 fires**. In the >= 20† class (13 issue hours at each horizon) the 5 h hours that held are 10, 11, 21 and 22 KST; the 8 h hours that held are 07 and 08 KST. Every 5 h issue hour from 12 to 20 KST fails against 8.6 km (reach 12.4 to 40.1 km), and every 8 h issue hour from 09 to 19 KST fails against 12.0 km (reach 12.4 to 50.3 km).

## What this does not show

- The hour-by-hour tables use no KMA hourly gust (only daily maxima and hourly means were available): ERA5 at 0.25 degrees smooths gusts, and each point is one grid cell near a county seat, not the fire. Where KMA is available it read higher than ERA5 at the two peak stations.
- Answer to "was a gust >= 20 m/s present at 10-11 KST, observed or in ERA5": ERA5, no (10.6 and 12.6 m/s fire-wide at the stamps); KMA, not shown by the data that could be fetched (the >= 20 m/s gusts it recorded came at 18:15 and 21:56 KST; hourly gust was not available).
- The class for a window uses the realised gust over the next h hours (a perfect forecast; ASSUMED). At the issue time itself the
  gust was < 20 m/s until 15:00 KST (ERA5).
- The >= 20 m/s class has 9 fires behind it. 0 of 9 missed in the calibration, with 95% CI 0-34%.
- Reach is from satellite detections with ~1-2 km pixels, not perimeters; one fire, one day.
- Nothing here says what anyone should have done.
