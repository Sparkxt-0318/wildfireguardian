# live/ — 실시간 산불 도로 계층 / live fire road layer for Korea

**모델 출력 · 참고용 · 공식 명령 아님. 당국의 안내에 따르십시오.**
**Model output, advisory, not an official order; follow instructions from authorities.** No official use is claimed.

Live site: <https://sparkxt-0318.github.io/wildfireguardian/live/>

Every 30 minutes (GitHub Actions, `.github/workflows/live.yml`, cron `7,37 * * * *` UTC) the service:

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
| `score.py` | scores records against later records |
| `config/live.toml` | every frozen number |
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

Limits: road data exists only for 영덕 and 의성·안동 (OpenStreetMap, 2025-03-21); elsewhere a fire page gives the
known area, margin and flags but no village times. The margin is calibrated on 28 California fires and failed on
25 March 2025; the out-of-range flag withholds it in such conditions. The Forest Service data call is not a published
API and can change without notice.
