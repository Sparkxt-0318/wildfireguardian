# RUNBOOK — live/ (what to do when something breaks)

**Model output, advisory, not an official order; follow instructions from authorities.** The service must never show a
number it cannot stand behind. When in doubt, let it withhold (it does so by itself, PROTOCOL §7) and fix the input.

Where things are: workflow `.github/workflows/live.yml` (Actions tab, "live — Korean fire service"); site
`https://sparkxt-0318.github.io/wildfireguardian/live/`; log branch `live-log`; rules `live/PROTOCOL.md`; settings
`live/config/live.toml`. Each run writes a step summary (sources ok/failed, fires, alerts).

## 0. First checks for any problem

1. Actions → "live — Korean fire service": is there a run every 30 min (at :07 and :37 UTC)? GitHub may delay a
   scheduled run by many minutes or skip it under load; gaps of one run are normal, gaps of hours are not.
2. Open the latest run's summary: `kfs_ok`, `firms_ok`, `gfs_ok`, `ahi_ok`, `listed`, `in_scope`.
3. Open `/live/` and the record `/live/data/latest.json` → `inputs.<source>.error`.
4. Scheduled workflows are disabled by GitHub after **60 days without repository activity**: re-enable in the Actions
   tab ("Enable workflow").

## 1. Korea Forest Service list (`kfs`) fails

Effect: the status page says "fire list unavailable"; no fire page is updated; nothing old is carried forward.

- **HTTP 403 / 429 / connection refused:** the site may be blocking the runner. Do not raise the frequency or rotate
  addresses. Check by hand in a browser: `https://fd.forest.go.kr/ffas/pubConn/movePage/sub1.do`. If the page works
  for people but not for the runner, the service stays down for this input; say so on the issue tracker.
- **"unexpected JSON: no fireShowInfoList list" or "not JSON":** the page changed its data call. Open
  `https://fd.forest.go.kr/ffas/js/publicConnect/main/publicMain.js` and `/ffas/js/publicConnect/sub/sub1.js`,
  find the call that fills the fire list (it was `selectPublicFireShowList.do`; the paged list is
  `POST /ffas/pubConn/occur/getPublicShowFireInfoList.do` with `{"param":{"startDtm","endDtm",...},"pager":{...}}`).
  Changing the URL or field mapping is a **PROTOCOL amendment** (write it there first, with the time).
- **Field names changed** (e.g. coordinates missing → every fire gets `NO_LOCATION`): same as above.
- `live/probe/probe.sh` is the one-off probe used to find the call; re-run it by pushing a change under `live/probe/`
  on a development branch (workflow `live-probe.yml`), then read its log.

## 2. FIRMS fails

Effect: `FIRMS_MISSING` on every fire → no numbers.

- `no FIRMS map key`: add the Actions secret **`FIRMS_MAP_KEY`** (Settings → Secrets and variables → Actions). The
  temporary key file `live/config/firms_map_key.txt` is only a fallback and is to be deleted (owner's request); after
  deletion the secret is the only source.
- `HTTP 400 … Invalid MAP_KEY` / transaction limit: check the key at
  `https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=...` (5,000 transactions per 10 min; the
  service uses 4 per run). Request a new key at `https://firms.modaps.eosdis.nasa.gov/api/map_key/`.
- `not a FIRMS CSV`: FIRMS outage page; wait. FIRMS NRT can lag the overpass by up to about 3 h.
- One source missing (e.g. NOAA-21) does not withhold anything; the record lists it.

## 3. Himawari AHI fails (only fetched while a Gyeongbuk/Gangwon fire is active)

Effect: the known fire area has FIRMS only; between VIIRS overpasses (about 13:30 and 01:30 local) the evidence becomes
older than 3 h and numbers are withheld (`EVIDENCE_OLD`).

- `no AHI scan could be read`: check `https://noaa-himawari9.s3.amazonaws.com/?list-type=2&prefix=AHI-L1b-Japan/YYYY/MM/DD/`
  (NOAA open data; JMA occasionally pauses Japan-area scans). Decode errors: satpy version (pinned in
  `live/requirements.txt`).
- Slow runs: the first run with a fire downloads up to 6 h of scans (about 300 MB); later runs reuse the Actions cache
  `live-cache-*`. If a run nears the 28 min limit, delete old caches in Actions → Caches.

## 4. GFS, signing, log push

- **GFS** `cycle … incomplete`: NOAA posts GFS 0.25° about 3.5-4 h after the cycle; the rule allows 5 h. A late cycle
  makes both flags unknown → `FORECAST_MISSING` → no numbers for that run. Nothing to do unless it persists; check
  `https://noaa-gfs-bdp-pds.s3.amazonaws.com/index.html#gfs.YYYYMMDD/HH/atmos/`.
- **Signing failed** (a `.UNSIGNED` file next to the record): usually a Sigstore outage
  (`https://status.sigstore.dev`). The record is still committed by the run; its git push time is the receipt. Do not
  sign it later and do not edit it.
- **Verify a signed record:**

  ```bash
  python3 -m pip install sigstore
  python3 -m sigstore verify github --bundle REC.sigstore.json --repository Sparkxt-0318/wildfireguardian REC.json
  ```

- **Push rejected:** the step rebases and retries 4 times. If it still fails, the run fails and the record is lost for
  that run (the next run makes its own). Never force-push `live-log`. If the branch is missing the workflow stops at
  its first step: recreate it as an orphan branch with only `README.md` (see the branch's README) — but never delete
  an existing log.

## 5. Road layer

- `refused: DATA_NOT_SET_UP / DATA_CORRUPT`: the road-graph cache failed; re-run (the setup step re-downloads and
  verifies SHA-256). If the release asset is gone, nothing can be computed for villages; fire pages show zones only.
- `refused: FIRE_INPUT_UNCOVERED`: a bug in the raster (it must cover the KFS_01 lattice); open an issue with the record.
- `ROADS_STALE`: `live/config/roadlayer_settings.toml` allows road data up to 1,100 days old (until about
  2028-03-25). After that every village refuses until new OSM graphs are prepared — by design.

## 6. Pages

- The deploy job needs the `github-pages` environment to allow the default branch (Settings → Environments).
- The planner workflow redeploys the whole site; this workflow runs right after it (`workflow_run`) and puts `/live/`
  back. Between the two, `/live/` may be missing for a few minutes.
- If a run fails after the record step, the site keeps the previous version. The page then shows its age, and readers'
  browsers hide its numbers after 75 min.

## 7. Alerts

Set secrets `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (a channel the bot can post to), and/or `SMTP_HOST`, `SMTP_PORT`
(default 465, SSL), `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO`. Without them every record says
"alerts skipped". Test by a manual run while a fire is active only; there is no test-message path, by design
(PROTOCOL §9: no other messages).

## 8. Drills (no live effect)

```bash
cd live && python3 -m wfg_live replay --inputs tests/fixtures/kfs01_20250325T0900Z --out /tmp/drill --site /tmp/drill/site
```

```bash
python3 -m pytest -q live/tests
```

A logged run can be replayed the same way from `live-log:live/log/inputs/<issue>/` (copy the GFS file for its cycle
from `live/log/inputs/gfs/` into the folder first).

## 9. Stopping the service

Actions → "live — Korean fire service" → "Disable workflow". The site keeps its last version, whose numbers readers'
browsers hide after 75 min. Add a line to the status page only through a commit to `live/` (the pages are generated).
