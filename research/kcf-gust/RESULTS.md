# RESULTS: gusts on 25 March 2025 and the frozen gust-class margin (kcf-gust)

**PROVISIONAL.** The primary series (KMA ASOS/AWS hourly maximum gust via data.go.kr) was **not fetched**: `DATA_GO_KR_KEY`
is not set in this session, and data.go.kr is not reachable from it. Everything below is ERA5 only (the secondary series),
at five county-seat points. Rules: `PROTOCOL.md`, committed before any gust value was read (a4ff4f1c). Every table is PROVISIONAL.

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

KMA observations: **not fetched** (no key; host not reachable). Repo note (`research-scout/LOG.md:822`, Newsis 2025-03-27) reports gusts
of about 27 m/s for this fire. ERA5 here peaks at 22.4 m/s (Yeongyang cell, 17:00 KST). The user's recollection of about 14 m/s
reanalysis in the repo's record was not found in the repo by search, so it is not used; ERA5 may still read low against stations (not
tested: that needs the KMA series).

## Hour by hour, 25 March 2025 KST, 00 to 24

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

- No KMA observation was used: ERA5 at 0.25 degrees smooths gusts, and each point is one grid cell near a county seat, not the fire.
- The class for a window uses the realised gust over the next h hours (a perfect forecast; ASSUMED). At the issue time itself the
  gust was < 20 m/s until 15:00 KST (ERA5).
- The >= 20 m/s class has 9 fires behind it. 0 of 9 missed in the calibration, with 95% CI 0-34%.
- Reach is from satellite detections with ~1-2 km pixels, not perimeters; one fire, one day.
- Nothing here says what anyone should have done.
