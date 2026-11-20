# live/ — 실시간 산불 도로 계층 / live fire road layer for Korea

**모델 출력 · 참고용 · 공식 명령 아님. 당국의 안내에 따르십시오.**
**Model output, advisory, not an official order; follow instructions from authorities.** No official use is claimed.

Live site: <https://sparkxt-0318.github.io/wildfireguardian/live/>

Every 30 minutes, at :07 and :37 UTC (`.github/workflows/live.yml`, started by `.github/workflows/live-relay.yml`
because GitHub's cron did not fire reliably here; PROTOCOL amendment 1), the service:

1. reads the Korea Forest Service's current fire list (the data call behind 국가산불정보시스템's 실시간산불정보 page;
   no public feed exists), NASA FIRMS hotspots, Himawari-9 AHI scans (only when a Gyeongbuk or Gangwon fire is
   active) and the issued GFS forecast, recording source, fetch time and SHA-256 of each;
2. for each active fire in Gyeongbuk or Gangwon, builds the known fire area from the report point and hotspots
   (frozen rule, `PROTOCOL.md` §4), applies the frozen reach margin (`research/kcf-replay` MEASURED arm, R from
   `research/kcf-margin`), runs `product/wfg-roadlayer` for prepared places within reach, and computes the gust-rule
   flag (`research/kcf-aloft`) and the out-of-range flag (`research/kcf-abstain`);
3. publishes `/live/` (status, one page per fire, daily wind-flag bulletin, card lookup), Korean first;
4. sends alerts only when a fire first affects a village or a last-road-out time moves by more than 15 min (when
   Telegram or email credentials are set);
5. signs the record (Sigstore) and commits it to the `live-log` branch before any outcome is known; `score.py` scores
   records later.

Read [PROTOCOL.md](PROTOCOL.md) for the frozen rules and [RUNBOOK.md](RUNBOOK.md) for what to do when a source breaks.

| path | what |
|---|---|
| `wfg_live/fetch.py` | fetch stage → an inputs folder with `manifest.json` |
| `wfg_live/compute.py` | compute stage (no clock, no network) → the record |
| `wfg_live/area.py`, `road.py`, `flags.py` | known fire area; raster + road layer; gust and out-of-range flags |
| `wfg_live/pages.py`, `alerts.py`, `run.py` | site, alerts, the run and the log |
| `wfg_live/cause.py` | reported cause per fire and the ten-year cause history (see "Cause" below) |
| `score.py` | scores records against later records |
| `config/live.toml` | every frozen number |
| `config/cause_history.json`, `probe/build_cause_history.py` | the official cause statistics behind the history panel, and the script that rebuilds them |
| `config/roadlayer_settings.toml` | road-layer settings copy (only the road-data age limit differs) |
| `tests/` | recorded-input reproduction (25 March 2025), failure tests per missing input |

```bash
python3 -m pip install -r live/requirements.txt
```

```bash
python3 product/wfg-roadlayer/roadlayer.py setup
```

```bash
python3 -m pytest -q live/tests
```

```bash
cd live && python3 -m wfg_live replay --inputs tests/fixtures/kfs01_20250325T0900Z --out /tmp/replay --site /tmp/replay/site
```

## Cause (reported only, never predicted)

Each fire's record and page show the cause the Forest Service reports, how firm it is, when the fire was first reported
and how many separate ignition points are given. Nothing is guessed: when the feed is silent the page says
**미보고 / not reported**. Checked 2026-11-21 against the live service; re-check with `probe/probe.sh` and the calls below.

**What the feed gives per fire** (`selectPublicFireShowList.do`, the call this service reads every 30 minutes):

| item asked for | feed field | found |
|---|---|---|
| cause | none | **No.** No field names or carries a cause. |
| confirmed / presumed / under investigation | none | **No.** `frfrPrgrsStcd`/`frfrPrgrsStcdNm` (02 진화중, 03 진화완료) is the state of the *fire*, not of the cause. |
| start time | `frfrSttmnDt` + `frfrSttmnHms` (KST), same instant as `frfrFrngDtm` | Yes. Used as "first reported". Also `potfrCmpleDtm` (put-out time) once out. |
| separate ignition points | none | **No.** One report coordinate (`frfrLctnXcrd`/`frfrLctnYcrd`, equal to `frfrSttmnLctnXcrd`/`Ycrd`). The 5 km "separate fire" rule in `area.py` is about satellite detections, not ignitions, and is not shown as a count. |
| other fields | `frfrInfoId`, `frfrSttmnAddr`, `frfrSttmnAddrDe`, `lgdngCd`, `frfrStepIssuCd`/`frfrStepIssuNm` (response step), `frfrPotfrRt` (% contained), `frfrPotfrRtDtm`, `frfrOccrrWndrcCd` (wind direction), `frfrOccrrPbmrl` | for reference |
| undocumented codes | `frfrOccrrTpcd`, `frfrOccrrStcd` | Present, meaning not published. **Not read as a cause.** |

The paged call `getPublicShowFireInfoList.do` (the page's own search, fields `frfr_*`) has the same items minus the
wind fields, and no cause either. The Forest Service does record a cause class for each fire *after the fact*: the
statistics page (`sub3.do`, call `selectStatallList.do`) lists past fires with 14 classes (입산자 실화, 쓰레기 태우기,
담뱃불 실화, 방화, 원인 미상, …), but it has no fire id, so it cannot be matched to a live fire and is not used that way.
It is the source of the history panel only. The data folder "wildfire 3 (1)" holds no cause data and no keys (its
`DATA_INDEX.md` lists none; the Drive copy was not reachable from here); no key is needed for this feature.

**What is stored and shown.** `fires[].cause` (and `listed[].cause`) in the record:
`text` (the feed's words, or `null`), `status` (`confirmed`, `presumed`, `investigating`, `unspecified` = a cause with no
status word the config knows, or `not_reported`), `first_reported_utc`, `ignition_points` (integer or `null`),
`source_fields`, `first_seen_utc`, and `changes`: every later difference in text or status, with the time of the run that
saw it. Because the live feed has no cause, `[cause]` in `config/live.toml` has empty key lists; when the feed adds a
field, its exact name goes there (a PROTOCOL amendment). Every record lists `cause_feed.unknown_keys`, the feed keys
this service has not seen before, so a new field is noticed. A change in a cause is recorded as a new entry in the
log's `state.json`; earlier records are never rewritten.

**History panel (background only).** `fires[].cause_history` and a dashed, separately labelled panel on the fire page:
the share of fires by recorded cause in the same province (경상북도; 강원 = 강원도 + 강원특별자치도) and the same calendar
month (KST) of the fire's report, for 2016–2025, with the count in brackets, the source, and the retrieval date. The page
says it is history and says nothing about the current fire. Source: Korea Forest Service 국가산불정보시스템, 산불통계 page,
`selectStatallList.do`, retrieved 2026-11-21 (1,484 fires; response checksum in the file). The causes are the Forest
Service's after-the-fact classes, including "원인 미상" and "기타". Months with few fires give small counts (shown). To rebuild:

```bash
python3 live/probe/build_cause_history.py
```

**Cause does not change the last-road-out calculation.** The known fire area, margin, flags and every village time are
computed from detections, wind and roads exactly as before; no cause enters them, and they are the same with a cause
or without. It is shown because it changes how crews respond: several ignition points, or a likely re-ignition, mean
a fire is harder to contain than its first report suggests. That is for the people responding; this page only passes on
what the Forest Service reports.

**Backward compatible.** The record schema id is still `wfg.live.record/1`. The new fields are optional additions
(`cause_feed`; `cause` and `cause_history` on fires; `cause` on listed fires). Old signed records lack them and still
load, score and render (`score.py` reads none of them); a record written now minus these fields equals the old format.
Tests (`tests/test_cause.py`): a fire with a cause, without one (the real feed), one whose cause changes later and one
whose cause is withdrawn, unknown status words and bad counts, unknown feed keys, old records, history figures.

Limits: road data exists only for 영덕 and 의성·안동 (OpenStreetMap, 2025-03-21); elsewhere a fire page gives the
known area, margin and flags but no village times. The margin is calibrated on 28 California fires and failed on
25 March 2025; the out-of-range flag withholds it in such conditions. The Forest Service data call is not a published
API and can change without notice.
