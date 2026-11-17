# PROTOCOL: gusts on 22-26 March 2025 and the frozen gust-class margin (kcf-gust)

Frozen 2026-11-17, committed before any gust value was fetched or read and before any hour was classified.
Changes after this commit go in an "Amendments" section with a reason.

**Question.** For 25 March 2025 (KST), in each hour 00-24, which gust class applied, would the frozen gust-class
R(h) from `research/kcf-margin` have held, and was a gust >= 20 m/s present at 10-11 KST, when the prior-3 h spread
class gave no warning?

**Series (primary / secondary, as instructed).**
1. PRIMARY: KMA station observations (ASOS and AWS, hourly maximum gust) through data.go.kr, key in the
   environment variable `DATA_GO_KR_KEY`. If the variable is not set, or the service cannot be reached, this series is
   NOT run, the result is labelled **PROVISIONAL** in every table, and nothing is substituted for it.
2. SECONDARY: ERA5 10 m wind gust, Open-Meteo archive API (`models=era5`, `hourly=wind_gusts_10m`,
   `wind_speed_unit=ms`, `timezone=GMT`), 2025-03-22 to 2025-03-26 (UTC dates, covering all of 22-26 March KST).
   Open-Meteo stamps each value with the end of the hour it covers (maximum of the preceding hour). ERA5 is a ~0.25 deg
   reanalysis. The user's note, taken as given: reanalysis gusts read low in this repo's record (about 14 m/s against
   about 27 m/s reported). It is therefore a lower bound on what a station would show, ASSUMED, not tested here.
Source, URL pattern and UTC fetch time are written to `work/fetch_log.json` and reproduced in RESULTS.md.

**Points (county seats, fixed now).** Uiseong 36.3527 N 128.6970 E; Andong 36.5684 N 128.7294 E; Cheongsong
36.4361 N 129.0572 E; Yeongyang 36.6669 N 129.1124 E; Yeongdeok 36.4150 N 129.3654 E. ERA5 snaps each to its grid cell.
(If KMA ran: station = nearest ASOS/AWS to the point, distance recorded; not applicable if PROVISIONAL.)

**Classes.** < 10, 10-20 (10 <= g < 20), >= 20 m/s. Edges as in `research/kcf-margin/PROTOCOL.md` class (c).
The >= 20 m/s class rests on **9 fires** (GOFER, n = 28); this is stated next to every number that uses it.

**Hour rows.** For each KST stamp H = 00:00 ... 24:00 on 25 March (25 rows) the observed value g(H) is the value stamped H
(the maximum over the hour before H). Report per point and the maximum over the five points ("fire-wide").

**Frozen R (km, 10% target, all 28 fires, numbers.json `table`, fire set all28).** Used as stored:
gust < 10: R5 2.6, R8 3.0; gust 10-20: R5 4.7, R8 5.9; gust >= 20: R5 8.6, R8 12.0 (9 fires). The 20% target is not used.

**Which class applies to an issue hour t (KST hour 00-23) and horizon h in {5, 8}.** Class (c) of the margin protocol:
the maximum gust over (t, t+h], i.e. the maximum of the stamps t+1 ... t+h, taken **fire-wide** (maximum over the five
points). This treats the realised series as a perfect forecast (ASSUMED, as in the margin protocol).

**Would R have held.** Reach = `reach_km` for (kst_hour, h) from `score_gyeongbuk.py`, as stored in
`research/kcf-margin/numbers.json` -> `gyeongbuk_stress` (5 km separate-fire rule; detections, not perimeters).
Held if reach <= R(class, h). Only issue hours flagged complete for that h are counted; truncated hours are listed
as not scored. Hour 24 has no reach (no issue-hour row); only its gust is reported.

**The 10-11 KST question.** Report, for issue hours 10 and 11 KST: (a) g at the issue stamp (what was already
observed), (b) the maximum over (t, t+5] and (t, t+8] (forward), per point and fire-wide, and whether any is
>= 20 m/s. "Present" means >= 20.0 at any of the five points. If none, the result is that gusts gave no warning either,
and is reported as such.

**Not done.** No claim about what anyone should have done. One fire, one day: no rate is claimed.

## Amendments

1. **2026-11-17, before any KMA value was fetched or read.** A key for data.go.kr (`DATA_GO_KR_KEY`) became available, and the KMA
   hub key (`KMA_API_KEY`, apihub.kma.go.kr) is stored in the user's environment but was not present in this session. Keys are never
   printed, logged or committed. What the data.go.kr services give (checked by field names only, no values): the hourly ASOS service
   (`AsosHourlyInfoService/getWthrDataList`) returns the mean wind `ws`, **not** a maximum gust; the daily ASOS service
   (`AsosDalyInfoService/getWthrDataList`) returns the maximum instantaneous wind speed `maxInsWs` and its time `maxInsWsHrmt`. So:
   - The KMA hourly maximum gust series needed for the hour-by-hour class table can only come from apihub (`KMA_API_KEY`). If it is
     not available, the hour-by-hour class and R-held tables stay **PROVISIONAL (ERA5 only)**.
   - From data.go.kr, for each ASOS station nearest to a point (distance recorded; stations with no data for the dates are listed as
     such), 22-26 March 2025: daily `maxInsWs` and `maxInsWsHrmt`, and hourly `ws` on 25 March. Reported side by side with ERA5;
     none of it is used to change a class, R, or any score.
   - Station ids tried: Uiseong 278, Andong 136, Cheongsong 276, Yeongdeok 277, Yeongyang: no ASOS id assumed (an AWS site would come
     from apihub only). Presence is decided by the service, not by assumption.
   - "Gust >= 20 m/s observed at 10-11 KST" is answerable from the daily series only if `maxInsWsHrmt` falls in that window; otherwise
     the daily series can bound it (a daily maximum below 20 m/s rules out >= 20 at that station that day) but not locate it.

2. **2026-11-17, before any KMA hourly value was fetched or read.** The apihub key is now approved for `kma_sfctm2.php` (ASOS hourly,
   columns include `GST_WS` gust m/s, `GST_WD`, `GST_TM` time of the gust) and `nph-aws2_min` (AWS per minute; has `WSS`).
   - **Primary series (KMA, ASOS hourly):** `kma_sfctm2.php?tm=YYYYMMDDHH00&stn=0` for every KST hour 2025-03-22 00:00 to 2025-03-26 23:00
     (120 calls, EUC-KR), stations Uiseong 278, Andong 136, Cheongsong 276, Yeongdeok 277. The value for stamp H is `GST_WS` of the row
     with `tm` = H, read as the maximum gust over the preceding hour (same convention as the ERA5 stamp). One check, reported as it
     comes out: `GST_TM` should fall in (H-1 h, H]; violations are listed. Missing or negative codes (-9, -99) are dropped, not zeroed.
   - **Fire-wide KMA value** = maximum over the stations present at that stamp. Yeongyang has no ASOS here and AWS minute data would take
     about 2,000 calls for the windows needed, so **Yeongyang AWS is not used**; KMA therefore covers four of the five points. Stated next
     to every KMA table.
   - Classes, frozen R, window (t, t+h], "held" test and the 10-11 KST question are exactly as above, once with KMA (primary) and once
     with ERA5 (secondary), side by side. A hole in the KMA series for a window is reported, not filled with ERA5.
   - The >= 20 m/s class rests on 9 fires; stated next to every number that uses it.
   - With the KMA series, the hour-by-hour tables are no longer labelled PROVISIONAL (the KMA gust is observed, not a perfect forecast,
     for hours already past; for the forward window it is still the realised series read as a perfect forecast, ASSUMED).

