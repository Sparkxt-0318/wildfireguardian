# Known limitations & blockers

This document records issues encountered during overnight builds that the
next session (or the human collaborator) will need to address. Each entry
is honest about what was tried, what didn't work, and what would be
needed to close it out.

---

## Session 20 (horizon grounding, 2026-08-31)

### ✅ CLOSED — the CSV arrived, and every figure reproduced

**John placed the file at `data/raw/kfs_fire_statistics/`.** sha256 and byte
count match exactly; it decodes as CP949 and UTF-8 fails, as it must.

`scripts/ingest_kfs_statistics.py` recomputed all **36 checks** and every one
agrees with the figures supplied in the brief — no percentile-convention
differences, no data differences. The 240-minute horizon is now **grounded**:
79.23 % of 2,008 Korean wildfires are contained within it, while fires of
10–100 ha take a median 1,374 min (5.7x) and fires ≥ 100 ha 4,025 min (16.8x),
which confirms the horizon as a **behavioural** window rather than a
fire-lifetime one. Full argument: `docs/horizon_grounding.md`.

**This closes the Session 16 and Session 17 stop-gates below.** The horizon
default is unchanged at 240 minutes; only its justification moved, and the
ranking-instability finding (ρ = 0.333 between 30 and 240 min) still governs
how the layer may be used.

⚠ **Two things did NOT close.** (1) 발생일시 is a *reported* start time, so the
distribution is report-to-containment, not ignition-to-containment — the same
limitation Session 19's GK2A delays carry, and no dataset here fixes it.
(2) The 12 negative durations are excluded and reported, but their cause
(midnight rollover, year typo, swapped order) was not diagnosed.

⚠ **The ignition-likelihood layer is still NOT built**, and the constraint on it
turned out to be *looser* than recorded — see `docs/horizon_grounding.md` §5:
~1,711 usable cause labels, not ~540, with 454 free-text strings to normalise.

<details>
<summary>Original stop-gate entry, kept for the audit trail</summary>

### ⛔ STOP-GATE — ACTION FOR JOHN: the CSV did not reach this environment

**Supersedes the Session 17 entry below as the current state of this blocker.**

The Session 20 brief states that `산림청_산불통계데이터_20250911.csv` was
downloaded manually and "is now available for ingestion". **It is not present in
this environment.** No figure from the brief was adopted, no document was
rewritten, and no number was registered.

**Exactly what was searched, and what was found:**

| where | result |
|---|---|
| `data/raw/kfs_fire_statistics/` | directory does not exist |
| `data/raw/` | `dem`, `firms_*`, `vworld` only |
| the uploads folder | **empty** |
| the whole connected folder, every `*.csv` | 31 files, all FIRMS detections or skill fixtures |
| the whole connected folder, `*산불통계*` / `*15121380*` | **0 matches** |
| every file 150–400 KB anywhere under the mount | no CSV; PDFs, PNGs, `.so` libraries |
| everything modified since 2026-08-29 | project cache and repo files only |

The likely cause is mundane: the file was downloaded to the Mac (probably
`~/Downloads`), and **only `~/Desktop/Korea Code Fair` is connected to this
session.** Nothing outside that folder is visible here.

**WHY THIS IS A HARD STOP RATHER THAN A DEGRADED RUN.** The brief's own
instruction is that the Phase 2 figures "were computed outside the repo and must
not be trusted until your own script reproduces them." Without the file there is
nothing to reproduce them from. Writing those numbers into
`docs/label_geometry_analysis.md`, the vulnerability score definition or
`NUMBERS.json` on trust would put ~30 unverified values into the frozen
registry — the exact failure this project self-reported in Session 19, where
four numbers in prose turned out to exist in no artifact.

**WHAT WAS BUILT INSTEAD — the work is ready, only the file is missing.**
`scripts/ingest_kfs_statistics.py` performs the whole of Phases 1, 2 and 4 in
one command and **verifies rather than assumes**:

- checks sha256 against `ae3e8426…a92c153` and size against 195,891 bytes;
- confirms the file decodes as CP949/EUC-KR **and that UTF-8 fails**, since a
  successful UTF-8 decode would mean a different or re-encoded file arrived;
- recomputes all ~30 figures — counts, p25/median/p75/p90/p95, the four
  cumulative shares, 경북, both damage-area bands, cause counts, the free-text
  share, seasonality;
- prints computed vs claimed **side by side** and **exits non-zero on any
  mismatch**, printing the five percentile conventions when a percentile
  disagrees so a convention difference can be told apart from a data difference;
- **refuses to write any artifact while any figure disagrees**; and
- never computes a mean, because one row's year-field error dominates it.

**ACTION FOR JOHN — one command:**

```bash
mkdir -p ~/Desktop/"Korea Code Fair"/wildfireguardian/data/raw/kfs_fire_statistics
mv ~/Downloads/산림청_산불통계데이터_20250911.csv \
   ~/Desktop/"Korea Code Fair"/wildfireguardian/data/raw/kfs_fire_statistics/
```

Then the next session runs:

```bash
python scripts/ingest_kfs_statistics.py --write
```

⚠ If the filename differs after the browser download (the portal sometimes
appends a suffix), pass it explicitly with `--csv <path>`; the sha256 check is
what confirms identity, not the name.

**Consequence, unchanged:** the 240-minute horizon remains **ungrounded —
arbitrary-but-swept**. The full sweep (30/60/120/180/240/360 min) and the
ranking-instability finding (ρ = 0.333 between 30 and 240 min) continue to
govern how the layer may be used, exactly as before.

</details>

---

## Session 17 (tautology decomposition, 2026-08-31)

> ✅ **CLOSED by Session 20** — the file arrived and the horizon is grounded.
> See the Session 20 entry above. Kept for the audit trail.

### ⛔ STOP-GATE — ACTION FOR JOHN: the page now loads, the FILE still does not

**This entry CORRECTS the Session 16 diagnosis below. Read this one first.**

**Attempt 2 of 2 (the agreed limit), 2026-08-31.** Retried
`https://www.data.go.kr/data/15121380/fileData.do`. **It succeeded.** The full
dataset page returned, HTTP 200, `text/html;charset=UTF-8`.

> ⚠ **Session 16 was wrong about the cause.** That entry concluded a
> "host-specific path issue" from a TLS handshake timeout while four other hosts
> answered in the same run. The evidence was real, but the inference was not:
> **the same host answers normally today from the same sandbox with the same
> tooling.** The failure was transient, not structural. Session 16's diagnosis
> table is left in place below as the record of what was measured, but its
> conclusion is withdrawn.

**The remaining blocker is a different one, and it is not a network problem.**
The CSV has **no published direct download URL**:

| source | field | value |
|---|---|---|
| DCAT `https://www.data.go.kr/biz/dcat/metadata/15121380.do` | `dct:accessURL` | **empty** |
| DCAT | `dcat:distribution / dcat:format` | `csv` |
| Schema.org `https://www.data.go.kr/catalog/15121380/fileData.json` | `distribution` | **absent** |

The portal serves the file through an in-page JavaScript download control, and
the page carries a 자동등록방지 (CAPTCHA) widget. **No attempt was made to drive
that flow, guess internal endpoint parameters, or solve the CAPTCHA**, and none
should be: bypassing bot protection is out of bounds regardless of the data
being public. Two attempts is the agreed limit and both are now spent.

**What WAS recovered, and it is worth having.** The dataset page carries the
authoritative 컬럼 정의서, so the future ignition layer can now be designed
against verified column names instead of prose:

| 항목명 | 타입 | 최대길이 |
|---|---|---:|
| `발생일시_년` / `_월` / `_일` / `_시간` / `_요일` | VARCHAR | 4 / 2 / 2 / 5 / 1 |
| `진화종료시간_년` / `_월` / `_일` / `_시간` | VARCHAR | 4 / 2 / 2 / 5 |
| `발생장소_관서` / `_시도` / `_시군구` / `_읍면` / `_동리` | VARCHAR | 100 each |
| `발생원인_구분` / `_세부원인` / `_기타` | VARCHAR | 100 each |
| `피해면적_합계` (ha) | VARCHAR | 100 |

Also verified from the page: **2,020 rows**, coverage **2022년 ~ 2024년 9월**,
전국, CSV, **이용허락범위 제한 없음**, 연간 갱신, 차기 등록 예정일 2026-11-30,
제공기관 산림청 산림재난총괄과 (042-481-4258).

⚠ Every field above is read from the **dataset page**, not from the file. Row
count, coverage and column names are the portal's claims about its own file and
have not been checked against it. In particular, **nothing here says how many of
the 2,020 rows have a non-null 진화종료시간** — a containment-time distribution
computed on a partly-empty column would be silently biased toward short fires.
Check that first when the file arrives.

**What would close it — ACTION FOR JOHN, about two minutes:**

1. Open `https://www.data.go.kr/data/15121380/fileData.do` in a normal browser.
2. Press the CSV **다운로드** button in the 파일데이터 정보 panel (no login
   required; complete the 자동등록방지 CAPTCHA if it appears).
3. Drop the file at `data/raw/kfs_fire_statistics/` (any filename).

Then the horizon can be grounded: 진화종료시간 − 발생일시 per event, reported as
a distribution (median and the 240-minute quantile), with the null-rate stated.

**Consequence, unchanged and stated plainly.** The 240-minute horizon remains
**ungrounded — arbitrary-but-swept**. No distribution was guessed or
substituted. Session 17 makes this materially more important, not less: the
null-hazard control shows the horizon is the **only** thing that decides the
failing set at 영덕 (see `docs/SESSION17_REPORT.md`).

⚠ **Still explicitly NOT built:** the ignition-likelihood layer from 발생원인 /
발생장소. Design only, pending the file.

### 📌 FUTURE WORK — raised by the Session 17 decomposition, deliberately NOT pursued

Task 1 answered its question and opened three new ones. The brief said to record
rather than chase them, and work now moves to 본선 deliverables, so they are
parked here with what is already known about each.

**1. The clearance-margin threshold never fires — and the cause is unknown.**
Zero of 2,496 failure events came from `MARGIN_FAIL_MIN = 10.0`. Two candidate
causes were **not** separated:
 - the elliptical hazard's reach is small relative to household spread, so no
   route ever passes near burning ground; or
 - `clearance` is finite only when some point on the route reaches the cutoff
   *within the horizon* (`_evaluate_path` skips infinite `time_to_cutoff`), so
   the threshold may be near-dead by construction.
 If the second, the margin component of the vulnerability score is a design
 defect, not a tuning value — and `MARGIN_FAIL_MIN` has been carried since
 Session 14 as though it did work. **Diagnostic:** count how often
 `clearance_margin_min` is non-`None` at all, per horizon.

**2. What would make the fire actually bite.** The null-hazard control says the
elliptical hazard at 영덕 is outside the regime where it can change the failing
set. Four candidates, none tried: a stronger spread scenario; an ignition prior
seeded *inside* the household distribution rather than at human-proximity peaks;
the arrival-time survival buffer (open item 1 in every report since Session 14 —
this is the most likely of the four, since refuge non-survival is currently
0 events); or a site where refuges genuinely burn.

**3. The control was run at ONE site with ONE hazard.** 영덕, elliptical,
human-proximity prior, 4 ignitions, corrected refuge set. It was **not** run at
Paradise and **not** run with `TrainedModelHazard`. "The fire contributes
nothing" is a measurement about that configuration and must not be generalised.

⚠ Also unmeasured: why the free-flow proxy and the null-hazard control disagree
for 6 households at H=240. Five-minute time-bin rounding and the
exposure-minimising tie-break are both candidates; neither was quantified. The
control settled the verdict, so the decomposition did not need it — but it is
not known.

---

## Session 16 (vulnerability drivers, 2026-08-30)

### ⛔ STOP-GATE — ACTION FOR JOHN: 산불통계데이터 download is unreachable from here

> ⚠ **SUPERSEDED BY THE SESSION 17 ENTRY ABOVE.** The host is reachable; the
> diagnosis below was drawn from a transient failure. Kept as the record of
> what was measured on 2026-08-30, not as a current statement of the cause.

**What was needed.** Per-event 발생일시 and 진화종료시간 to compute the
containment-time distribution and ground the vulnerability layer's 240-minute
horizon, which is currently the layer's single largest assumption (household
ranking correlation between a 30-minute and a 240-minute horizon is only
**0.333**).

**Exact URL:** `https://www.data.go.kr/data/15121380/fileData.do`
(산림청_산불통계데이터_20250911, 공공데이터포털)

**Exact failure.** The host is reachable at the TCP level and then the TLS
handshake never completes:

```
www.data.go.kr    dns=ok 27.101.236.55   tcp443=ok   https=FAIL URLError:
                  <urlopen error _ssl.c:999: The handshake operation timed out>
```

**This is host-specific, not a general network restriction.** Measured in the
same run, from the same sandbox:

| host | DNS | TCP 443 | HTTPS |
|---|---|---|---|
| `www.data.go.kr` | ok | ok | **TLS handshake timeout** |
| `www.forest.go.kr` | ok | ok | ok (200, 0.5 s) |
| `fd.forest.go.kr` | ok | ok | ok (200, 0.9 s) |
| `overpass-api.de` | ok | ok | ok (200, 1.0 s) |
| `pypi.org` | ok | ok | ok (200, 0.3 s) |

**The reachable alternative was tried and does not carry the data.**
`fd.forest.go.kr/ffas/pubConn/movePage/sub3.do` and two `forest.go.kr`
statistics pages return HTTP 200 but are JavaScript shells: a raw-HTML scan for
진화종료 / 진화시간 / 진화완료 / 평균진화 / 소요시간 found **zero** occurrences in
any of them. No further fetch method was attempted.

**Consequence, recorded rather than papered over.** The 240-minute horizon
remains **ungrounded — arbitrary-but-swept**. No distribution was guessed or
substituted. The full horizon sweep (30/60/120/180/240/360 min at both sites)
is reported beside the default in every report that cites it.

**What would close it:** download the file on a machine that can reach
data.go.kr — a normal browser session should suffice, the dataset is a public
file download — and drop it at `data/raw/kfs_fire_statistics/`. The columns
needed are 발생일시 and 진화종료시간.

⚠ **Also worth noting for later, NOT built here:** the same file carries
발생원인 (구분·세부원인) and 발생장소 (관서·시도·시군구·읍면·동리). That is a
label source for a future ignition-likelihood layer, which would replace the
current assumed ignition prior. The columns were named from the dataset
description page, **not** verified against the file, because the file could not
be downloaded.

---

## Session 10 (wind downscaling / front assimilation, 2026-08-29)

### ⛔ ARM C DEFERRED — WindNinja has no build for this session's CPU architecture

**This is not a verdict on WindNinja.** It is a fact about where Session 10
ran. Arm C is deferred, not stopped, and the path that will work is below.

**The four options in the brief, in order, and what each returned:**

1. **conda-forge package — EXISTS.** `windninja 3.13.0.1` is published on
   conda-forge (MIT, `conda install conda-forge::windninja`). All **15**
   files on the channel are `osx-64` or `linux-64`. There is **no
   `osx-arm64` build and no `linux-aarch64` build** — checked against the
   channel's own file listing, not inferred.
2. **Prebuilt binary / release — not usable here.** The upstream project
   ships installers for Windows; the wiki states that Linux and macOS
   require building from source. Neither route produces an aarch64 binary.
3. **Docker image — unavailable.** No Docker in this environment, and the
   `linux-64` image could only run under qemu/binfmt emulation, which
   needs root. This session has no root (`sudo` is blocked by the
   no-new-privileges flag).
4. **Build from source — unavailable.** WindNinja is C++ over GDAL, Boost,
   NetCDF and Qt. Without root there is no `apt-get install`, and the
   sandbox has no cmake, no GDAL headers and no conda to supply them.

**Session 10 ran on Linux aarch64**, so all four are closed. Per the
brief's stop-gate, Arm C was not attempted and **no hand-rolled terrain
adjustment was substituted** — an unvalidated approximation presented as a
validated model is worse than the missing arm.

#### ACTION FOR JOHN — the path that should work on your Mac

Apple Silicon has no native WindNinja either, but it can run the `osx-64`
build under Rosetta 2. The standard conda mechanism is an x86-64 subdir env:

```bash
CONDA_SUBDIR=osx-64 conda create -n wnj -c conda-forge python=3.11 -y
conda activate wnj
conda config --env --set subdir osx-64      # keep later installs on osx-64
conda install -c conda-forge windninja -y
WindNinja_cli --help                        # confirms the CLI is on PATH
```

⚠ **Untested from here** — this session could not run macOS. Two things to
check before building any pipeline on it: that Rosetta 2 is installed
(`softwareupdate --install-rosetta`), and that the first `WindNinja_cli`
call actually returns (Rosetta's first-run translation is slow, and a hang
is easy to mistake for a crash).

Phase 1's remaining questions — does the output field vary spatially, does
direction deviate in valleys and on lee slopes, what is the speed-ratio
range, and what is the wall-clock cost of `hours × 6 fires` — are all
**unanswered** and stay unanswered. Nothing in Session 10 estimated them.

#### What Arm D says about Arm C's premise

Worth reading before spending a session on Rosetta. The direction claim was
withdrawn partly because ERA5's 0.25° (~28 km) grid cannot resolve the wind
the model was asked to learn direction from. Arm D tested a directional
signal with **no resolution problem at all** — the fire's own observed
direction of travel, from its own detections — and it ranked 17th of 23
features at +0.00005 AUC drop with a fold sd of 0.0025.

That does not refute the WindNinja hypothesis: terrain-resolved wind is a
different quantity from observed front motion, and 6–16 h between usable
overpasses is coarse for estimating a direction of travel. But it does mean
Arm C should be entered expecting a null, not a rescue.

---

## Session 8 (post-interview refactor, 2026-08-29)

### ⚠️ OPEN — ACTION FOR JOHN: 도로명주소 건물 데이터 needs a manual, logged-in download

**Why this replaced the VWorld path**: the follow-up session retried VWorld
(below) and it still fails, so the government building layer is now the
primary route to real rural building coverage. It is a **portal download,
not an anonymous file URL** — this session could not fetch it and stopped
rather than working around the login.

**Exact steps (2026-08-29, verified against the portal pages)**:

1. 주소기반산업지원서비스 — https://business.juso.go.kr/jst/jstAddressDownload
   (「주소정보 다운로드」). Requires a member account (회원가입) and login.
2. For building **polygons/points** with coordinates, the layer is the
   전자지도 building layer:
   https://business.juso.go.kr/addrlink/elctrnMapProvd/geoDBDwldList.do?menu=건물
   — 11 layers are offered (건물, 건물군, 도로구간, 실폭도로, 기초구간,
   출입구, 기초구역, 행정구역). ⚠ The portal states that downloads are
   released **according to approval by the agency managing the requested
   area**, so a 신청 → 승인 step stands between the account and the file.
   Request 경상북도 (or 영덕군) only; the national file is unnecessary.
3. Alternative, coarser: 공공데이터포털 entry **15050424**
   「행정안전부_도로명주소 건물DB」 —
   https://www.data.go.kr/data/15050424/fileData.do — but its 제공형태 is
   「기관자체에서 다운로드」 and its URL redirects to juso.go.kr (menuId=DT06),
   i.e. the same portal, and the TXT product is address records rather than
   footprint geometry.
4. Place the downloaded file under `data/raw/juso_buildings/` and tell the
   next session; the loader seam is
   `src/wildfireguardian/buildings/` (`BuildingSource` protocol) — a new
   `JusoBuildingSource` class tagged `source = "juso"` is the whole change.

**Until then**: Phase 2 counts stay on the 124-building OSM snapshot and are
labelled provisional everywhere they appear (`docs/rescue_routing.md` §6).

### ⚠️ OPEN: VWorld Data API unreachable — retried 2026-08-29, still failing

**Retry result (follow-up session)**: unchanged. Measured with curl from the
same machine:

| target | result |
|---|---|
| `https://api.vworld.kr/req/data?...&data=LT_C_SPBD&...` (with key) | connection failed, `http_code = 000` |
| `https://api.vworld.kr/req/search?...` (with key) | **HTTP 502** |
| `https://api.vworld.kr/req/data` (no key at all) | **HTTP 502** |
| `https://api.vworld.kr/` (root) | **HTTP 502** |
| `https://www.vworld.kr/` (root) | connection failed, `http_code = 000` |
| `https://business.juso.go.kr/addrlink/main.do` (control, unrelated .go.kr) | connection failed, `http_code = 000` |

⚠ **The control matters**: an unrelated Korean government host fails the same
way, and a keyless VWorld request fails identically to a keyed one. So this
is **not** an API outage or a bad key — the path from this machine to
`*.go.kr` / `vworld.kr` is blocked or intercepted (a 502 from an
intermediary, not from VWorld's application). Retrying from a different
network is still the first thing to try.

### ⚠️ OPEN: VWorld Data API unreachable (502 on every endpoint) — original entry, 2026-08-29

**What's needed**: working access to the VWorld Data API
(`api.vworld.kr/req/data`, 건물통합정보 layer) so building origins can move
from the 124-building OSM snapshot to authoritative footprints.

**What was tried (2026-08-29)**: the `VWORLD_API_KEY` in `.env` (found
concatenated onto the `DEMO_RECIPIENT` line without a newline — fixed this
session; `.env` is git-ignored). Requests to `req/data` (`LT_C_SPBD`,
`LT_C_ADSIDO`) and `req/search` all return **HTTP 502 Bad Gateway** (curl) or
`RemoteDisconnected` (urllib) — the previously-recorded VPN-interference
failure mode. The outcome is recorded verbatim in
`data/processed/rescue_routing_village_edge.json::data_path.vworld_attempt`.

**Next action (John)**: retry off-VPN or from another network; if 502
persists, check the key's approval state at https://www.vworld.kr (콘솔 →
인증키 관리). The loader seam is `src/wildfireguardian/buildings/`
(`BuildingSource` protocol) — ingestion is one class once the endpoint
answers.

**Fallback used (per the session-8 gated plan)**: OSM building snapshot,
`source = "osm"`, coverage caveat attached everywhere it is quoted.

### ⚠️ ACTION FOR JOHN: GK2A L2 산불탐지(FF) product needs a KMA API-Hub key

See Session 8 Phase 5 (`docs/gk2a_direction_experiment.md`). The sub-daily
direction experiment's preferred labels are the GK2A AMI L2 FF (산불탐지)
product served through the KMA API Hub, which requires a personal 인증키.

**Signup URL**: https://apihub.kma.go.kr (회원가입 → 마이페이지 → API 인증키
발급; the GK2A satellite product list is at
https://apihub.kma.go.kr/apiList.do?seqApi=6). No key was requested this
session — authentication is a stop-gate, not something to work around.

**Keyless alternative documented in the plan**: NOAA NODD mirrors GK2A AMI
**L1B** imagery (not L2 FF) at `s3://noaa-gk2a-pds` (2023-02 → present,
`--no-sign-request`), which covers the March-2025 fires but would require
deriving hotspots from L1B radiances ourselves — an added confounder the
preregistration treats as a fallback arm, not the primary.

---

## Session 7 (diagnostic) — the crown result was a bug

### ✅ FIXED: crown foliar-moisture conflation (the "54 %" artifact)
The Session-6 crown trigger fed the surface drought-LFMC (40 %) into the
Van Wagner tree-crown check; live crowns are ~119 % (measured). Fixed by
decoupling `crown_foliar_moisture_pct`. **Corrected result: crown
initiation ~0 %, 24-h capture ~9 %** (was the artifact 54 %). See
`docs/OVERNIGHT_REPORT_SESSION7.md`.

### ⚠️ RE-OPENED (the real bottleneck): surface fire too weak to crown
With realistic foliar moisture, the WAF-corrected surface intensity
(I_B ≲ 1500 kW/m) never reaches the Van Wagner critical intensity (1686
kW/m at CBH 4 m). So the surface→crown trigger alone cannot reproduce the
(real, crown-driven) 2025 event. **The limiting factor is the surface
intensity, not the crown threshold** — re-attack via real gusty KMA wind
and a re-examination of the WAF / provisional surface fuel. This is the #1
scientific gap, restored from Session 5.

### Finding (not a blocker): crown initiation is CBH-sensitive
Capture ~9 % at measured CBH (3.6–5.2 m), ~27 % at CBH 2 m. Stand structure
governs crown potential — documented as a contribution, with an uncertainty
band replacing the point estimate.

---

## Session 6 (fire-type physics) — progress and remaining gaps

### ✅ ADDRESSED: surface-only model missed ~90 % (the S5 #1 gap)
Added crown fire (Van Wagner 1977 + Cruz/Alexander 2005), spotting (Albini
1979), topographic wind (Föhn heuristic), and a rule-based regime
classifier. 24 h area capture 9 % → **54 %** (crown) / 59 % (spotting), IoU
0.086 → **0.295**. Crown fire is the dominant recovery (32 % of cells reach
active crown). See `docs/OVERNIGHT_REPORT_SESSION6.md`.

### ⚠️ STILL OPEN — early-front under-prediction (1–3 h)
Capture stays ≤ 1 % in the first 3 h across all configs. The CA needs time
to develop crowning and the real fire's early explosive run isn't captured.
**Fix:** faster crown onset + real gusty wind time series.

### ⚠️ STILL OPEN — over-prediction / no containment
Crown over-predicts 24 h area by +38 %; spotting by +104 %. There is no
suppression / fuel-break / containment model, so spotting runs away.
**Fix:** a containment model or a Monte-Carlo burn-probability framing to
restore precision (IoU peaked at ~0.30).

### Heuristic / provisional pieces added this session (flagged)
- Topographic-wind coefficients (k_slope, channel gain, lee factor) are
  cited heuristics, not calibrated to Korean obs.
- Albini spotting constants (loft ratio, drift coeff) are calibrated to
  magnitude, not validated.
- Korean canopy CBH/CBD/FMC are measured (Lee et al. 2018); the Rothermel
  *surface* bed remains provisional (carried from S5).

---

## Session 5 (mentor refocus) — resolved, corrected, and newly-exposed

### ✅ RESOLVED: missing Wind Adjustment Factor (the root wind bug)
Rothermel needs **midflame** wind; the code fed raw 10-m / station wind into
φ_w, inflating the wind factor to ~115×. `spread_model/wind.py` now applies
the Andrews 2012 WAF (closed Korean pine canopy WAF ≈ 0.10), giving a
corrected wind factor ~5×. All wind now routes through this conversion.

### ✅ CORRECTED (retracted): tautological "multiplicative coupling"
The Session-4 "interaction ratio = 1.000" was a tautology (Rothermel is
separable). Replaced by the dimensional cross-partial ∂²R/∂M∂U and the
marginal wind effect ∂R/∂U (`spread_model/interaction.py`,
`docs/methodology/interaction.md`).

### ⚠️ NEWLY EXPOSED (genuine, unresolved): surface model under-predicts ~90%
With physically-correct midflame wind, the Rothermel **surface** model
under-predicts the Yeongdeok front by ~90 % at every horizon. The real run
was crown/spotting-driven. **Fix needed**: a crown-fire / spotting ignition
module on top of the surface model. This is the #1 scientific gap. Until
then the spread model is insufficient to predict this event, and the
routing spine must be fed a better front than the surface model produces.

### ⚠️ PROVISIONAL: Korean surface fuel bed (not measured)
Live moisture (119 %) and canopy structure are measured (Lee et al. 2018);
the Rothermel surface bed (litter load 0.7 kg/m², depth 0.08 m, SAV
6000 m⁻¹, dead m_x 0.30) is a flagged best-estimate. **Fix needed**: Korean
surface-litter field data (KFRI/NIFoS ground-fuel surveys).

### Carried forward (need data access / a later session)
- Real KFS perimeter shapefile (validation ground truth still approximate).
- Real KMA AWS wind (still synthetic-historical reconstruction; no key).
- Real Sentinel-1/2 + Korean LFMC labels for the retrieval model.
- Real OSM pedestrian network for routing (synthetic grid used offline).
- Real fire+weather data for the empirical super-multiplicativity test
  (`empirical_interaction.py` is a synthetic-data scaffold only).

---

## ✅ RESOLVED in Session 2

### BLOCKERS-1: Single-class Rothermel vs. multi-class BehavePlus  ✅ RESOLVED

**Status**: RESOLVED in Session 2.

**Resolution**: implemented Andrews 2018 multi-class weighting in
`src/wildfireguardian/spread_model/rothermel/spread.py::compute_multi_class_spread_rate`.
Multi-class FM10 R0 dropped from 4.6 ft/min (single-class, 2.3× published
overestimate) to 2.06 ft/min (within Andrews 2018 Table 7 published band
of 1.5–2.2 ft/min). See `tests/test_rothermel_multiclass.py::
test_multi_class_reproduces_andrews_2018_table7` for the assertions.

The Session 1 single-class `FuelModel` API is preserved for back-compat;
all Session 1 tests (`tests/test_rothermel.py`) still pass.

### BLOCKERS-2: No real geographic CRS  ✅ RESOLVED

**Status**: RESOLVED in Session 2.

**Resolution**: `FireGrid.from_region(region_config, cell_size_m)` now
constructs a grid sized and anchored to EPSG:5179. Outputs:

- `FireGrid.perimeter()` returns coordinates in EPSG:5179 metres.
- `FireGrid.perimeter_geodataframe()` returns a GeoDataFrame with proper CRS.
- `FireGrid.to_wgs84_perimeter()` reprojects to EPSG:4326 for GeoJSON.
- `FireGrid.to_geotiff(path)` writes EPSG:5179 GeoTIFF.

The Yeongdeok demo (`demo_yeongdeok_synthetic.py`) now uses
`YEONGDEOK_2025` and emits a CRS-tagged GeoJSON with WGS84 lon/lat coords
per RFC 7946.

---

## Still open — Session 2 still has known limits

### 3. Huygens elliptical wavelet flank ratio is small at moderate winds

**Status**: known, documented (carried from Session 1).

**Issue**: with the Anderson 1983 length-to-breadth ratio capped at
`LB_MAX = 3.0`, the eccentricity is ≈ 0.943 and the flank-rate is ≈ 5.7 %
of head-rate.

**Consequence**: in the cellular automaton, lateral spread is much slower
than downwind spread.

**To close**: optional spotting / crown-fire ignition would dominate
lateral spread in real wind-driven fires; or replace the universal
Anderson 1983 correlation with a per-fuel-model LB correlation
(Cruz & Alexander 2010). Either is a Session 4 task.

### 4. CA does not split wind and slope into a vector sum

**Status**: known simplification (carried from Session 1).

**Issue**: FARSITE combines wind and slope vectorially into an effective
direction of maximum spread (Finney 1998 §2.2.4). Our implementation
uses the wind direction alone for the ellipse major axis; slope
contributes only to the scalar R_max via Rothermel's φ_s.

**Consequence**: on steep terrain with cross-wind, the fire elongates
along the wind axis rather than along the combined vector.

**To close**: implement Finney 1998 eq. 14–17. Half a day of work.

---

## ✅ RESOLVED in Session 4

### Slow-initial-spread warm-up  ✅ RESOLVED

**Status**: RESOLVED in Session 4.

**Issue (found in Session 3)**: the CA lost to the isotropic baseline at
1 h / 3 h / 6 h because a single-cell ignition has zero perimeter and
therefore takes one full cell-ring-time (~11 min at 100 m) before any
spread, and the effective rate only reaches ~91 % of steady-state by
60 min.

**Resolution**: `FireGrid.ignite_disc()` initialises the fire from a
finite established front (standard FARSITE practice). The validation uses
a principled radius (head rate × 15-min establishment ≈ 155 m, NOT tuned
to observed). 1 h IoU rose 0.160 → 0.477; horizon-averaged IoU 0.145 →
0.264. Baselines get the same initial disc for fairness. Full diagnosis
and sensitivity in `docs/methodology/spread_warmup.md`.

**Remaining (not a warm-up issue)**: the 3–6 h under-prediction is genuine
missing physics (spotting / crown fire, gusts), documented in
`docs/methodology/validation_limitations.md` — candidate Round-2 feature.

---

## ✅ PARTIALLY RESOLVED in Session 3

### BLOCKERS-6 (DEM): SRTM path implemented  ✅ (SRTM done, NGII pending)

**Status**: SRTM RESOLVED in Session 3; NGII still pending.

**Resolution**: `data_io.raster.load_dem(source='srtm')` now downloads and
ingests real NASA SRTMGL1 (30 m) tiles from the AWS Mapzen archive
(no auth required), reprojects to EPSG:5179, and derives slope/aspect via
the Horn (1981) gradient method. The Yeongdeok validation now runs on REAL
terrain (0–820 m, with the East Sea correctly at 0 m). NGII 1:5000 Korean
DEM (higher accuracy) remains a Round-2 enhancement; SRTM is an adequate
free fallback for Rothermel slope.

### BLOCKERS-2b (validation numbers): produced  ✅

**Status**: RESOLVED in Session 3 (with honest provenance caveats).

**Resolution**: `scripts/run_yeongdeok_validation.py` produces
`data/processed/yeongdeok_2025_validation_results.json` with IoU /
Sørensen-Dice at 1/3/6/24 h for our model vs persistence + isotropic
baselines. The numbers are honest: our model beats persistence at all
horizons and beats isotropic at 6 h and 24 h, but the inputs are still
mostly synthetic/approximate (see new blockers below).

---

## New in Session 2 — data ingestion blockers (status updated in Session 3)

### 5. KFS perimeter shapefiles are not yet ingested

**What's needed**: the official KFS post-event perimeter polygons for the
three validation cases (영덕 2025, 울진/삼척 2022, 고성 2019).

**Why**: the validation harness's IoU / Sørensen-Dice / Brier metrics all
compare predicted to observed perimeter polygons. Session 2 uses stub
manifests in `data/validation_cases/*.json` with approximate ignition
points and total burn area only — the actual shapefile path is `null`.

**Expected impact**: until real perimeters are ingested, the metric
values produced by `validation.run_validation()` are not scientifically
meaningful. The pipeline runs end-to-end (see
`tests/test_validation.py::test_harness_runs_end_to_end_on_synthetic_yeongdeok`)
but the numbers are structural placeholders.

**Suggested next steps**:
1. Request KFS post-event perimeter shapefile via KFS 산불방지과 (forest
   fire prevention division).
2. Drop the shapefile under `data/raw/perimeters/<event>/`.
3. Update each manifest's `observed_perimeters_path` field.
4. Re-run `notebooks/02_yeongdeok_validation_dryrun.ipynb` and confirm
   IoU / Sørensen-Dice numbers are now defensible.

### 6. NGII DEM access is not yet wired up

**What's needed**: NGII 1:5000 digital map → 30 m DEM in EPSG:5179 for
each validation region.

**Why**: synthetic DEM is currently the only working source in
`data_io.raster.load_dem`. Slope and aspect from the synthetic DEM are
NOT representative of the real Yeongdeok / Uljin / Goseong terrain — and
slope drives Rothermel φ_s, which can change spread rates by ≥ 2× on
steep terrain.

**Expected impact**: until NGII DEM is ingested, model spread rates may
be systematically wrong for the validation cases — too slow in real
mountainous terrain, too fast in real flat terrain. Until then, all
validation numbers should be tagged as "synthetic-DEM".

**Suggested next steps**:
1. Register with NGII (https://map.ngii.go.kr/). Korean residence is
   ideal; foreign researchers can apply via 국제협력.
2. Download 1:5000 contour vector tiles for each validation region.
3. Implement the rasterise-to-EPSG:5179 path in `load_dem(source='ngii')`.
4. As an interim, NASA SRTM 30 m global is free and adequate; implement
   `load_dem(source='srtm')` first.

### 7. KFS 임상도 access is not yet wired up

**What's needed**: KFS 임상도 v1.4 (forest type map) for each validation
region.

**Why**: synthetic fuel-type raster assumes 100 % Korean Pinus
everywhere, which is correct in the Pinus belt but wrong in mixed
hardwood stands. Real validation requires the actual fuel type at each
cell — Pinus densiflora → KP_PINE, Quercus → FM9, mixed → FM10.

**Expected impact**: Yeongdeok and Uljin are predominantly Pinus, so the
synthetic fallback is qualitatively OK there. For mixed-stand Round 2+
regions (Central Mountain Belt) the synthetic is wrong.

**Suggested next steps**:
1. Register at https://map.forest.go.kr.
2. Download 임상도 v1.4 vector for each validation region.
3. Implement the species-code → fuel-model lookup in
   `load_fuel_type(source='kfs_impsangdo')`.

### 8. KOSIS / KFS / MOIS data for real vulnerability scoring

**What's needed**: the three sub-score inputs that drive
`vulnerability_score()`:

- KOSIS 시군구별 65세 이상 독거노인 통계 (rural elderly).
- KFS 시군구별 산불발생 건수 2010-2024 (fire frequency).
- MOIS 시군구별 대피소 시설 현황 (shelter density / response time).

**Why**: Session 2 uses placeholder values (clearly tagged as such with
`placeholder=True` on every `VulnerabilityScore`). The deployment-target
list `WILDFIRE_VULNERABLE_COUNTIES` is therefore plausible but not
authoritative.

**Expected impact**: low priority for the scientific defence (the
framework is what matters, not the exact numbers); high priority for
making concrete claims about "% of vulnerable Koreans covered" in the
submission narrative.

**Suggested next steps**:
1. Pull KOSIS aggregated 시군구별 인구통계 via OpenAPI.
2. Pull KFS 산불통계 annual reports.
3. Pull MOIS 안전지표 통계.
4. Replace `_PLACEHOLDER_SCORES` in `src/wildfireguardian/utils/vulnerability.py`.

### 9. KMA AWS access — synthetic reconstruction in place, real data pending

**Status update (Session 3)**: `data_io.weather.load_aws_wind` now exists
with a `synthetic_historical` path that reconstructs the March 2025
Yeongdeok 양강지풍 wind regime from PUBLIC reporting (clearly tagged
`synthetic=True`). The real KMA Open API path raises NotImplementedError
because no API key is configured.

**What's still needed**: KMA AWS hourly wind / RH / T data for March 2019,
March 2022, March 2025 within the validation-case bboxes, plus a spatial
interpolator (the current `WindField` is uniform).

**Expected impact**: medium-high. Wind matters a lot for Rothermel; the
synthetic reconstruction captures the qualitative pattern (sustained
westerly 양강지풍) but is not the actual time series. This is the largest
remaining model-vs-observed discrepancy after the fuel raster.

**Suggested next steps**:
1. Register at https://data.kma.go.kr/, request a service key; set the
   `WILDFIREGUARDIAN_KMA_API_KEY` env var.
2. Implement the HourlyObservation endpoint in `load_aws_wind(source='kma')`.
3. Add an IDW/kriging interpolator → spatial `WindField` subclass.

### 10. Korean fuel parameters are still analog values

**What's needed**: published Korean field-measured fuel-load and SAV
data for Pinus densiflora stands.

**Why**: the `KOREAN_PINUS` model in
`src/wildfireguardian/spread_model/rothermel/fuel_model.py` uses values
adapted from FM10 + qualitative Pinus densiflora morphology. They are
flagged as analog in `docs/methodology/korean_fuel_model.md`.

**Expected impact**: low to medium. Order-of-magnitude spread rates are
right; absolute values may shift by ±30 % once real Korean field data
replaces the analog.

**Suggested next steps**:
1. Search KFRI (Korea Forest Research Institute) publications for Lee et
   al. 2002 fuel-load surveys.
2. Search KIFM (Korean Institute of Fire Mathematical Modeling) for
   stand-level Pinus densiflora fuel parameter tables.
3. Replace the analog values in `_make_korean_pinus_fuel()`.

---

## New in Session 3 — Round 2 (August) data blockers

### 11. KFS 임상도 fuel-type raster (carried from BLOCKERS-7)

Still pending. The Yeongdeok validation uses a synthetic 100%-Korean-Pinus
fuel raster. Real KFS 임상도 stand classification is needed to assign
mixed-stand fuel models. See BLOCKERS-7 above.

### 12. Sentinel-1/2 + MODIS for real LFMC retrieval

**What's needed**: Sentinel-1 GRD (VV/VH), Sentinel-2 L2A (NDVI/NDMI/NBR),
MODIS NDVI, and Globe-LFMC 2.0 + Korean field LFMC labels.

**Why**: Session 3 implemented the LFMC retrieval scaffold
(`lfmc_model.retrieval`) but trains it on a CLEARLY-LABELLED synthetic
dataset. The trained model is tagged `do_not_use_for_production=True`.

**Expected impact**: medium. Currently LFMC is a manifest-supplied
constant (40 % for the Yeongdeok case); a real retrieval would give a
spatially-varying LFMC field.

**Suggested next steps**: see `docs/methodology/lfmc.md` Round-2 plan.

### 13. HYSPLIT / CMAQ coupling for production smoke

**What's needed**: a real atmospheric transport model for the smoke
dispersion module.

**Why**: Session 3 implemented a Gaussian-plume (Pasquill-Gifford) smoke
model (`smoke_dispersion.gaussian_plume`) as an ARCHITECTURE DEMONSTRATION.
It is not validated science — it uses textbook dispersion coefficients and
a coarse area×emission-factor source model.

**Expected impact**: low for the June 13 submission (smoke is a secondary
output); higher for the routing-penalty raster that depends on PM2.5.

---

## Genuine blockers

**None.** Session 3 Tier 1 + Tier 2 complete; all 208 unit tests pass.
The Yeongdeok validation runs end-to-end on REAL SRTM terrain and produces
honest IoU/Dice numbers vs two baselines. The remaining gaps (real KFS
perimeter, real KMA wind, real KFS fuel, Korean field fuel parameters)
are data-ingestion tasks deferred to Round 2 (August), not code blockers.
