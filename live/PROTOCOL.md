# PROTOCOL — live/ : the reach margin and road layer on current Korean fires

**모델 출력 · 참고용 · 공식 명령 아님. 당국의 안내에 따르십시오.**
**Model output, advisory, not an official order; follow instructions from authorities.**

Frozen 2026-11-19, committed before the first scheduled run and before any live record exists. Every number used
below is in `live/config/live.toml`. A change after this commit goes in "Amendments" at the end, with the time and
the reason, and applies only to records made after it. Records are never edited.

No new science. Nothing here is fitted, tuned or calibrated. The service applies three committed pieces unchanged
(imported, not copied):

| piece | what it gives | where |
|---|---|---|
| reach margin | R(5 h), R(8 h) by prior-3 h spread class; the closure-time curve | `research/kcf-replay/measured_arms.py` (MEASURED arm, R from `research/kcf-margin/numbers.json`) |
| out-of-range score | five-predictor tail score against 28 calibration fires, threshold tau | `research/kcf-abstain/abstain.py`, `predictors.py`, `fetch_nwp.py`, `derived/hours.csv.gz` |
| gust rule G | forecast gust >= 20 m/s at two consecutive valid hours | `research/kcf-aloft/rules.py` (`levels`, `RULES["G"]`) |
| road layer | last-road-out windows, stages, flags, village cards, departure order | `product/wfg-roadlayer` CLI (`run`, `cards`) |

## 1. Inputs (each fetched live; source, fetch time, HTTP status and SHA-256 recorded in every record)

**a. Active fires — Korea Forest Service, 국가산불정보시스템 (fd.forest.go.kr).**
- No public data feed was found. data.go.kr lists Forest Service fire *statistics*, camera locations and crew
  stations, not a live incident feed (searched 2026-11-18). The 실시간산불정보 web page
  (`/ffas/pubConn/movePage/sub1.do`) and the forest.go.kr front-page panel are filled by the page's own JSON call
  `GET https://fd.forest.go.kr/ffas/pubConn/selectPublicFireShowList.do` (found in `/ffas/js/publicConnect/main/publicMain.js`,
  2026-11-18). **This is a web page's data call, not a published API.** It may change without notice (RUNBOOK §1).
- Read politely: **one GET per run (two runs an hour)**, a User-Agent naming this repository, no login, no cookies kept,
  no other page of the site fetched by the service. `www.forest.go.kr/robots.txt` allows every path except
  `/kfsweb/kfs/search.do`; `fd.forest.go.kr/robots.txt` does not exist (the server answers 403), so no rule is stated
  for that host. Reachable from GitHub-hosted runners (US); not reachable from the build container.
- Fields used: `frfrInfoId` (record id), `frfrPrgrsStcd` / `frfrPrgrsStcdNm` (진행 상태; 02 = 진화중),
  `frfrLctnXcrd`, `frfrLctnYcrd` (WGS84 lon, lat), `frfrSttmnDt` + `frfrSttmnHms` (신고 일시, KST), `frfrSttmnAddr`,
  `lgdngCd` (법정동 code), `frfrStepIssuNm` (대응 단계), `frfrPotfrRt` (진화율 %). Everything else is kept in the
  raw copy and not interpreted.

**b. Satellite hotspots.**
- **NASA FIRMS NRT**, area API, CSV: VIIRS S-NPP, NOAA-20, NOAA-21 and MODIS, box 124.5-131.0 E, 33.0-39.0 N,
  5 days (the most one call serves), four calls per run. Key: Actions secret `FIRMS_MAP_KEY`; if that is empty,
  `live/config/firms_map_key.txt` (temporary, see RUNBOOK §2). With no key, FIRMS counts as missing.
- **Himawari-9 AHI**, Japan-area scans (2.5 min cadence), bands 7 and 14, NOAA open-data bucket `noaa-himawari9`
  (no key), decoded with satpy `ahi_hsd`. Fetched only when an in-scope fire is active, for scans in
  [max(report − 1 h, issue − 6 h), issue). Pixels within 60 km of an in-scope report point are kept.

**c. Forecast — GFS 0.25°**, the issued source of `research/kcf-abstain` (NOAA bucket `noaa-gfs-bdp-pds`), fetched
with `research/kcf-abstain/fetch_nwp.py::one` unchanged: seven fields, Korea lattice 33-39 N, 125-131 E, leads
6-18 h. Cycle c(t) = latest 00/06/12/18 UTC cycle with c + 5 h <= t (the kcf-abstain availability rule). Each
cycle is stored once in the log.

## 2. Schedule and issue time

- Every 30 minutes, at :07 and :37 UTC, started by the relay workflow (amendment 1; first written as GitHub Actions cron
  `7,37 * * * *`). GitHub can delay or drop runs; every page shows the actual run time and data age, and a gap is
  visible in the log.
- **Issue time T** = the run's start time, to the minute (UTC). Hotspots are used only if acquired strictly before T.
- **Issue hour t** = T rounded down to the whole UTC hour. The forecast flags (§5) are defined on whole hours and use t.

## 3. Fires in scope

A KFS record is **active** when `frfrPrgrsStcd` = 02 (진화중). It is **in scope** when it is active and in
Gyeongbuk or Gangwon: `lgdngCd` starts with 47, 42 or 51, or the address starts with 경상북도, 경북 or 강원.
Records in other provinces, or not active, are listed on the status page with their status and get nothing else.

## 4. Known fire area (frozen rule)

For an in-scope fire with report point p and report time r (KST → UTC), at issue time T:

1. **Seed:** a disc of radius 375 m at p, time r.
2. **Candidates:** FIRMS VIIRS detections with confidence n/h (radius 375 m), MODIS with confidence >= 30 (radius
   1 km), and AHI hotspots (radius 2 km), acquired in [r − 1 h, T). Time = FIRMS `acq_date`+`acq_time`; AHI = scan
   end of the second flagged scan (below).
3. **AHI hotspot** (the `research/kcf-margin` Gyeongbuk rule): a pixel with B07 >= 320 K and B07 − B14 >= 25 K in at
   least 2 scans of one UTC clock hour. It becomes known at the end of the second such scan.
4. **Persistent heat sources are ignored:** a 0.01° cell with FIRMS detections on 3 or more distinct UTC days among the
   fetched days before the report's UTC day. Detections in it, and AHI hotspots whose 2 km disc contains its centre,
   are left out. (Industrial sources such as steelworks are lit every night; a fire is not.)
5. **Membership:** the connected set containing the seed, where two discs are linked when the gap between their edges
   is <= 5 km (the kcf-margin separate-fire distance), and no disc whose centre is more than 100 km from p.
   *Disclosure:* the cap was first written as 50 km; on the 25 March 2025 test fixture (§11), before freezing, it
   dropped 460 detections of the 의성 fire, which ran about 80 km. It was raised to 100 km for that reason only.
6. **Known fire area K_T** = the union of the member discs. Its **centroid** P_T = mean of member centres (EPSG:5179).
7. **Evidence age** = T − the latest member time (the seed counts). Over 3 h: no numbers (§7).

## 5. Margin, road layer and flags

- **Margin.** `measured_arms.curve("MEASURED", discs, T, 8)` gives the class (quiet / slow / running / all) and R(5 h),
  R(8 h); `measured_arms.closure_s` gives each 375 m cell's closure time from its distance to K_T (distance to a disc
  = max(0, centre distance − radius)). Not reached within 8 h = +inf. Horizon 480 min.
- **Road layer.** For each prepared region (영덕 `yeongdeok_2025`, 의성·안동 `uiseong_andong_2025`) whose road cells
  have any closure within 8 h, the arrival raster (minutes, EPSG:5179, the KFS_01 375 m lattice of
  `product/wfg-roadlayer/examples/build_example_raster.py`, minimum over the in-scope fires) is passed to
  `roadlayer.py run` and `roadlayer.py cards` with `--settings live/config/roadlayer_settings.toml` (live: the
  road layer's own clock is the as-of time; a replay of a record passes `--as-of T`, and its sheets then say 재현).
  **Villages affected** = places of that region whose last road out is cut within 8 h or whose fire
  arrival is within 8 h. Everything else in Gyeongbuk and Gangwon has **no road data in this repository**: the
  page says so and gives the zone only.
- **Gust-rule flag (G).** `research/kcf-aloft` rule G at issue hour t: from cycle c(t), the largest forecast gust over
  the four 0.25° lattice points around P_T at valid hours t+1 … t+8; G is on when it is >= 20.0 m/s at two
  consecutive valid hours (`rules.levels(...)["g_k2"] >= 20.0`). Missing field: unknown.
- **Out-of-range flag (OOR).** The kcf-abstain primary score at issue hour t: the four forecast predictors from
  `predictors.one` (same cycle, points and window) and prior-3 h spread from `measured_arms.spread_class`; the score s
  is the minimum over predictors of the fire-weighted tail probability against the 28 calibration fires
  (`abstain.Calib` on the committed `derived/hours.csv.gz`); **OOR is on when s <= tau = 0.010728508563521567**.
  When prior-3 h spread is undefined (nothing known 3 h before T), s is the minimum over the four forecast
  predictors and the flag is labelled "partial (4 of 5 predictors)". Missing forecast: unknown.

## 6. Daily wind-flag bulletin (shown always; the main content when no in-scope fire is active)

At issue hour t, rule G for every 0.25° lattice cell inside 35.5-38.75 N, 127.0-129.75 E (its four corners, the same
window). The bulletin for a KST day lists every cell that was on at any issue hour of that day so far (earlier hours
from the log), and the **single-exit villages** in on cells: prepared places with `single_exit = yes` in the committed
card audits (`product/wfg-roadlayer/examples/cards/*/audit_*.csv`; exits are fire-independent).

## 7. When no number is shown (the fire and its flags are still listed, with the reason)

1. The KFS list was not fetched in this run → no fire page is updated, the status page says "fire list unavailable".
   Old numbers are never carried forward.
2. FIRMS was not fetched (no key, or no VIIRS source answered) → no numbers for any fire.
3. The KFS list, FIRMS or AHI input was fetched more than 45 min before T, or the fire's evidence age is over 3 h.
   (GFS is an issued, unchanging file; its age is governed by the cycle rule c(t) alone.)
4. The GFS cycle c(t) is incomplete → both flags unknown → no numbers (the out-of-range check cannot be made).
5. **OOR on → the margin's numbers are withheld** (the kcf-abstain rule: conditions outside the calibration fires;
   the fire may spread much farther than the margin). Villages within reach are still listed, without times.
6. The road layer refuses (its own codes, e.g. `FIRE_INPUT_UNCOVERED`) → no number for that region or village.
7. **In the reader's browser**, when the page is more than 75 min older than the reader's clock, all numbers are hidden
   and the age is shown instead.
8. Road data: the only road graph is the OpenStreetMap snapshot of **2025-03-21**. The road layer's own limit
   (365 days) would refuse every live run; live/ raises it to 1,100 days in a settings copy, and every page states the
   road-data date. Roads built or closed since then are not known.

## 8. Publication (GitHub Pages, `/live/`)

- `/live/index.html`: national status (every listed fire, scope, status, flags, last run time, age of each input,
  next expected run), the bulletin, links to fire pages and the card lookup.
- `/live/fire/<frfrInfoId>.html`: one page per in-scope fire: report point and time, known area summary, class and
  R(5 h), R(8 h), flags, villages affected (each with its last-road-out windows, leave-by, road cut, stage, gap to
  fire arrival, departure order and a link to its village card), or the reason numbers are withheld.
- `/live/cards.html`: card lookup for any prepared place (demonstration: fire-independent facts from the committed
  audits and the 25 March 2025 worked-example cards, labelled as a replay, not a current fire).
- Korean first, English toggle. Every page and message carries the notice at the top of this file, the run time, the
  data age, and "no official use is claimed". No person is ever named (inputs contain addresses and places only;
  free-text fields are not displayed).

## 9. Alerts (Telegram channel or email; credentials from environment variables)

Telegram when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set; email when `SMTP_HOST`, `SMTP_USER`,
`SMTP_PASSWORD` and `ALERT_EMAIL_TO` are set. With neither, alerts are skipped and the record says so. Exactly two
kinds of message: (1) the first run in which a fire affects any village (§5); (2) a village's last-road-out time moving
by more than 15 minutes from the last time alerted for it. Nothing else is sent. State is kept in the log.

## 10. Prospective log (replaces `research/kcf-validate/PROSPECTIVE_LOG.md`)

- Every run writes one record `live/log/records/YYYY/MM/DD/<T>.json` on the branch **`live-log`**, holding: issue
  time, code commit, settings hash, every input's source/fetch time/status/SHA-256, the in-scope fires with their
  known-area discs, class, R, flags, villages and numbers (or the withholding reasons), alerts sent, and the published
  page hashes. Raw inputs go beside it (`inputs/<T>/`; GFS once per cycle in `inputs/gfs/`).
- The record is **signed** with Sigstore keyless signing from the workflow's GitHub OIDC identity (bundle
  `<T>.sigstore.json`: certificate naming this workflow and commit, Rekor transparency-log entry with its
  integrated time) and **committed and pushed in the same run**, before any outcome it predicts can be known.
  If signing fails the record is still committed, marked unsigned, and RUNBOOK §4 applies.
- Append-only. A record is never edited; a correction is a new record naming the one it corrects.
- **Scoring** (`live/score.py`, separate, run daily by the same workflow): a record is scored no earlier than
  T + 8 h + 24 h, from later records only. For each fire in it: new detections acquired in (T, T + h] linked to K_T by
  §4 (5 km rule); reach S_h = the largest edge distance from K_T; the margin **held** if S_h <= R(h), h = 5, 8.
  Villages: a village counts as **reached early** when a later known area covers its road entry cell before the
  record's fire arrival time for it. KFS outcome: the first later record in which the fire is no longer 진화중.
  Each score is a new file `live/log/scores/<T>.json`, with its misses, whatever it is. Withheld records are scored
  too (the score says what the margin would have done).

## 11. Tests

`live/tests`: a recorded-input run that reproduces a past day exactly (25 March 2025, 의성 fire, from committed
FIRMS/AHI detections and GFS extracts), a replay of a logged live record from its stored inputs, and one failure test
for each missing input (KFS, FIRMS, AHI, GFS, road data).

## Amendments

1. **2026-11-19 03:45 UTC — how the 30-minute runs are started (no rule changed).** GitHub's cron (`7,37 * * * *`)
   did not start a single run in the first 4 h on Main (the one manual run at 23:50 UTC worked; this repository's daily
   cron ran 5 h 17 min late the same day). With the owner's approval the cadence now comes from
   `.github/workflows/live-relay.yml`: one job dispatches `live.yml` at every :07 and :37 UTC for about 5 h 40 min,
   then dispatches its own successor; its 2-hourly cron only restarts a broken chain. The cron trigger is removed from
   `live.yml` so that runs are not doubled. Records say who started a run (`run.trigger`: `relay`, `manual`, or the
   GitHub event). Issue time, inputs, rules and limits are unchanged; §2's "every 30 minutes at :07 and :37" still holds.

2. **2026-11-21 — reported cause shown (no rule changed).** Each fire's record and page now carry the cause the Forest
   Service reports, its status, the first-report time and the number of ignition points, and a background panel of
   ten-year cause shares for the same province and month. Report only: a cause is read only from feed fields named in
   `live.toml [cause]` (none exist today, so every fire shows "not reported"), never inferred or predicted, and it is
   not an input to §4, §5 or any time or flag. Record schema unchanged; the new fields are optional. §11's tests gain
   cause cases (with, without, changing).
