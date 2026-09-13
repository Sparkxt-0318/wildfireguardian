# Data verification report: the six external acquisition items

Written 2026-09-13 by a verification session working from the author's laptop over the
desktop bridge, with the author answering in session. Scope: the six items the author was
asked to obtain (KMA API Hub key, KMA bulk ASOS/AWS files, 산악기상관측망 data, 임상도
1:5000 경상북도, 산림청 fire API key, 정보공개청구 to 국립산림과학원).

## Headline

**All six items fail. None of the six was obtained.** Nothing was found on disk, no key is
stored anywhere, and the author confirmed in session on 2026-09-13, through four direct
questions, that no KMA API Hub key was ever obtained, no data.go.kr 활용신청 was ever filed,
none of the three bulk datasets was downloaded, and the 정보공개청구 has not been filed.

**No key appears anywhere in this report, because no key was found to exist.** Nothing was
written to `~/.config/wildfireguardian/`; that directory does not exist on the author's
machine and was deliberately left absent, because an empty or placeholder key file is worse
than no file. No raw data was placed under `data/raw/`, and neither
`data/raw/forest_type_map/MANIFEST.json` nor `data/raw/foia_nifos/MANIFEST.json` was written,
because there is nothing to manifest. Those two directories were not created.

What this report adds beyond six failures: for every item, the exact acquisition route was
verified against the live source this session, so the redo instructions below name real
endpoints, real dataset ids and real field names rather than a description of where to look.
Two of those checks found that an acceptance test as written would still fail after the
author obtains the item, which is the part worth reading (items 2 and 5).

## How the search was done

The author's `~/Downloads` (1,669 entries), `~/Desktop` and `~/Documents` were granted to
this session and searched four ways.

1. **By name**, recursively: `임상*`, `forest*`, `ASOS*`, `AWS*`, `apihub*`, `kma*`, `기상*`,
   `산악*`, `nifos*`, `산림*`, `FGIS*`, `정보공개*`, `foia*`, `data.go*`, `datago*`, `영덕*`,
   `의성*`, `yeongdeok*`, `uiseong*`. Every hit was this repository, one of its copies
   (`~/Downloads/wildfireguardian-claude-dreamy-knuth-NlgfH`, `~/Desktop/Korea Code
   Fair/제출/`, `~/Desktop/Korea Code Fair/backup korea code fair/`,
   `~/Documents/Codex/2026-09-13/.../source/`), or unrelated (a Climate Note article folder
   named "Forests & Land Ecosystems", a `.ans` file called "forest spirits").
2. **By type**: every `.shp`, `.gpkg`, `.gdb`, `.geojson` in the three trees. The only
   shapefiles present are this repository's own 도로명주소 (`juso`, `juso_buildings`) and
   민원행정기관 layers. No 임상도. Every `.zip` newer than 2026-01-01 was listed; the Korean
   ones are 도로명주소 건물 경북, 사물주소도형 경상북도 and 민원행정기관전자지도, none of
   them forestry or weather.
3. **By content**: `grep -rI` for `apihub`, `data.kma`, `mw.nifos`, `forestStus`, `3070842`,
   `serviceKey`, `authKey`, `인증키`, `API_KEY` across `.txt`, `.md`, `.json`, `.rtf`,
   `.env`, `.yaml`, `.yml`, `.csv`, `.html`, `.py`. Every hit outside the repository copies
   was prose describing these sources, never a stored key.
4. **Key-shaped files**: every `*.key`, `*key*.txt`, `*api*key*`, `*.env`, `*secret*` in the
   three trees. Three `.env` files exist (this repository, and two Climate Note copies) plus
   an unrelated recovery-key text file and a Keynote document.

This repository's own `.env` (untracked, git-ignored) was read for **variable names and
value lengths only**; no value was printed, logged or copied. It defines ten variables:
`OPENTOPOGRAPHY_API_KEY`, `FIRMS_MAP_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (empty),
`TWILIO_FROM_NUMBER`, `DEMO_PHONE_NUMBER`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
`DEMO_RECIPIENT`, `VWORLD_API_KEY`. **There is no KMA key and no data.go.kr key.**
`.env.example` carries a `KMA_API_KEY` slot the real `.env` never fills.

`~/.config` was also granted and listed: it holds `agents`, `amp`, `Autodesk`, `devin`, `gh`,
`git`, `openresearch`, `openscience`, `Seamly2DTeam`. There is no `wildfireguardian`
directory, so no key was ever stored at the two paths the brief specifies.

⚠ One limit on the search, stated rather than papered over: only `~/Downloads`, `~/Desktop`,
`~/Documents` and `~/.config` were granted. A key living in the author's email, in a browser
password manager, in Notes, or on another machine would not be visible here. The author's
in-session answer, not the disk search, is what makes these failures definite.

## A note on the environment, because it changes how the gates were run

The brief says to use `.auto/venv/bin/python`. On the author's laptop that path is a symlink
to `/Users/jp/miniforge3/envs/wfg311/bin/python`, a macOS arm64 binary. The desktop bridge
executes commands inside a Linux VM that mounts only the granted folders, so the symlink does
not resolve and the interpreter could not be executed there; the VM's own `python3` is 3.10
and lacks `pytest`, `scipy`, `shapely`, `pyproj`, `geopandas`, `sklearn` and `networkx`.
`git fetch` over SSH also fails from that VM (no direct TCP), which is why the brief's
`insteadOf` rewrite to HTTPS is necessary.

The gates were therefore run on a clean Linux clone of `origin/auto/dev` in this session's
cloud container, bootstrapped with `scripts/auto/bootstrap.sh` (`pins_ok: true`,
`stack_ok: true`, Python 3.11.15). Everything that touched the author's files was done on the
author's machine; everything that needed the repository's pinned stack was done on the clone.

---

## Item 1. KMA API Hub key (https://apihub.kma.go.kr)

**Found at:** nowhere. No key on disk, no `~/.config/wildfireguardian/kma_apihub.key`, no
`KMA_API_KEY` value in `.env`.

**Acceptance result: FAIL, all three tests.** None of (a), (b) or (c) was run, because there
is no key to run them with. There is no "probably fine" here and no partial pass:

- (a) AWS 1-minute observations for a 경북 station, 2025-03-25 14:00-15:00 KST: **not run.**
- (b) 초단기예보 or 단기예보 for a grid point in 영덕: **not run.**
- (c) whether an archived forecast issued 2025-03-25 can be retrieved: **not answered by
  test.** See below for what was established without a key, which is less than an answer.

**Evidence.**

1. The author answered "No, never got one" to the direct question in session on 2026-09-13.
2. `docs/auto/NEEDS_HUMAN.md:234-238` already records this. NH-012 asked for, among other
   things, "(c) a KMA API Hub key", and is marked **CLOSED 2026-09-04 by the author**, verbatim:
   「Deferred - keep (b) the national shelter file and (c) the KMA API Hub key under a later
   priority (post-finals); re-open when there is time.」 So the item was not missed; it was
   consciously deferred nine days ago and the brief re-opened it without that being noticed.
3. `https://apihub.kma.go.kr/` answers HTTP 200 from both the cloud container and the
   author's machine, so nothing is blocked; the only missing thing is the key.
4. The hub's own terms, read this session at `https://apihub.kma.go.kr/apiInfo.do`, state
   that an 인증키 is issued only on 회원가입 and is visible afterwards in 마이페이지, that it may
   not be transferred or lent, and that the API service is free.

**What was established without a key** (agency: 기상청; as-of: read 2026-09-13; scope: the
public API Hub service-list pages, no login):

- The AWS 1-minute product the brief wants exists and is named **K10. 자동기상관측장비(AWS)
  매분자료**, described on the 지상관측 page as roughly 600 stations nationwide with 분, 시간,
  일, 월 and 연 production cycles and holdings from 1997 (station-dependent). That is the
  right product for test (a).
- The one endpoint whose full URL is published without login is the ASOS one:
  `https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php?tm=YYYYMMDDHHmm&stn=0&help=1&authKey={인증키}`,
  with `tm` = KST timestamp, `stn` = station number (`0` or absent = all stations), `help=1`
  = append field descriptions. The AWS 매분 endpoint path sits behind the AWS tab of the same
  page and did not render without a session, so **this report does not name it**; the author
  will see it on the AWS tab after logging in. Inventing a plausible `.php` name here would
  be exactly the kind of unsourced detail CHARTER §3.5 forbids.
- 단기예보 and 초단기예보 are listed under the 예특보 category (category 9 of 13).
- On (c): the 기상자료개방포털 (`https://data.kma.go.kr`) publishes 동네예보 products as
  파일셋 as well as OPEN-API, and its 초단기실황 page states 「2010년 6월부터 조회일 기준 전월
  자료까지 제공」. That establishes that **an archive of the 동네예보 실황 product exists back to
  2010**. It does **not** establish that a *forecast issued at a particular past time* on
  2025-03-25 is retrievable, which is what (c) actually asks, and this session did not
  establish that either way. Both routes need a login the author does not have.

**What the author must redo.**

1. Register at `https://apihub.kma.go.kr` (회원가입), then read the 인증키 from 마이페이지.
2. Store it, and only there:
   ```
   mkdir -p ~/.config/wildfireguardian
   printf '%s' '<the key>' > ~/.config/wildfireguardian/kma_apihub.key
   chmod 600 ~/.config/wildfireguardian/kma_apihub.key
   chmod 700 ~/.config/wildfireguardian
   ```
   Never into `.env`, never into this repository, never into a commit.
3. Then the three tests can run. For (a) use a 경북 AWS station near the fire; for (b) the
   동네예보 grid cell containing 36.45 N, 129.40 E; for (c) try the 단기예보 service with a
   past 발표시각 and, if it refuses, the 기상자료개방포털 파일셋 for 2025-03, and record which
   endpoint was tried and what it answered. Record every request URL with the key replaced by
   `<REDACTED>`.

---

## Item 2. KMA open-data bulk files (https://data.kma.go.kr)

**Found at:** nowhere. No ASOS or AWS file for March 2025, or for any month, exists in
`~/Downloads`, `~/Desktop` or `~/Documents`.

**Acceptance result: FAIL, for absence.** Every sub-check fails because there is no file:
date coverage 2025-03-22 to 2025-03-28 (no file), stations 영덕(277), 안동(136), 의성(278),
울진(130) (no file), wind speed / direction / maximum instantaneous wind columns (no file).
**The 영덕 maximum gust on 2025-03-25 and its timestamp cannot be reported.** The brief's
expectation that it is 20 m/s or more is neither confirmed nor contradicted by anything in
this session, and this report does not repeat it as though it were a finding.

**Evidence.** The author answered "None of them" when asked which of the three bulk datasets
had been downloaded. The four zero-byte `downloadResourceFile (2..5).txt` files in
`~/Downloads` dated 2026-09-12 are the only download-shaped artefacts near the right date;
they are empty, carry no recoverable source URL through the bridge mount, and the author did
not claim them. They are recorded here as an observation, not as evidence of an attempt.

**What the author must redo.**

1. `https://data.kma.go.kr` requires 회원가입 and login for bulk downloads. The products are
   종관기상관측(ASOS) and 방재기상관측(AWS) under 데이터 > 기상관측 > 지상, each with a
   자료형태 of 시간자료 or 매분자료 and a 기간 selector.
2. Request **2025-03-20 to 2025-03-31** rather than 03-22 to 03-28, so the window has a day
   of margin on each side for the gust analysis.
3. ⚠ **Station numbers, before downloading.** 영덕 and 의성 need checking against the
   지상관측 지점정보 table on the portal, because the ASOS network is 96 stations and several
   경북 sites the project cares about are AWS rather than ASOS. Download the 지점정보 table in
   the same session and keep it beside the data. A file that turns out to contain only the
   ASOS subset will not carry 영덕 at all, and that is the most likely way this item fails a
   second time.
4. Gust: the column to look for is 최대순간풍속, with its own 최대순간풍속시각. If the download
   carries 풍속 and 풍향 but no 최대순간풍속, that is a fail with the field named, not a pass.

---

## Item 3. 산악기상관측망 data (mw.nifos.go.kr or data.go.kr)

**Found at:** nowhere. No API key and no files.

**Acceptance result: FAIL, for absence.** No station within 30 km of 영덕읍 was identified, no
10 m wind series at 1- or 10-minute steps for 2025-03-25 was obtained, and no record count
can be reported.

**On the explicit question the brief asks** ("If only a current-conditions API exists with no
history, say so explicitly"): **the honest answer is that this is not settled, and the
evidence points slightly the other way.** The service description is a real-time one, but the
request specification includes a past-timestamp parameter. Stating flatly "current conditions
only" would be a claim beyond what was read.

**Evidence** (agency: 산림청 국립산림과학원; as-of: dataset page read 2026-09-13; scope: the
data.go.kr 오픈API 상세 page, no login, no call made):

- The dataset is **산림청 국립산림과학원_산악기상정보**, data.go.kr id **15084696**, registered
  2021-08-24, 수정일 2025-08-20, 833 활용신청, free, 자동승인 at both 개발 and 운영 stages,
  개발계정 quota 10,000 calls/day.
- Endpoint: `https://apis.data.go.kr/1400377/mtweather/mountListSearch`.
- Description: 「국내 주요 산악지역의 기상을 **실시간으로** 관측하고 수집하여 ... 풍향, 풍속,
  온도, 습도, 기압, 지면온도, 강수량을 지면으로부터 **10m와 2m 높이에서** 관측한 데이터를
  제공합니다」, with a note that some locations are withheld for security reasons.
- Request parameters: `ServiceKey` (required), `pageNo`, `numOfRows`, `_type`, `localArea`
  (지역코드), `obsid` (지점번호), and **`tm` (관측시간), sample `202106301809`, optional**.
- Response fields include `wd10m` (10 m 풍향), `wd10mstr` (10 m 풍향방위), `wd2m`, and the
  wind-speed and temperature/humidity fields at both heights (`tm10m`, `tm2m`, `hm10m`,
  `hm2m`), plus `obsid`, `obsname` (산이름), `localarea`, `tm`, `pa`, `ts`, `rn`, `cprn`.
- **So 10 m wind is served, and `tm` accepts a minute-resolution past timestamp.** What the
  page does **not** show is any 기간 (range) parameter, and it does not state how far back
  `tm` is honoured. Whether `tm=202503251400` returns a row is exactly the question a single
  call with a key would settle, and it was not settled here.
- One consequence worth planning for: with no range parameter, a full day at 10-minute steps
  for one station is 144 calls, and at 1-minute steps 1,440 calls against a 10,000/day
  개발계정 quota. Four stations at 1-minute steps would exceed it.
- 산악기상 also appears as two file datasets: **15112026** (여분산·추월산 only, which is not
  경북 영덕) and 국립공원공단's own AWS listing (**15090545**, a different network).
- `http://mw.nifos.go.kr/main.do` is reachable (HTTP 200 with a browser user-agent; it
  returns 400 to a default curl agent) and is a map console, not a bulk download.

**What the author must redo.**

1. Apply at `https://www.data.go.kr/data/15084696/openapi.do` (활용신청, 자동승인) and store
   the key at `~/.config/wildfireguardian/datago.key` with mode 600. The same data.go.kr
   인증키 serves item 5, so this application and item 5's give one key, not two.
2. First call to make, before anything else, is the history probe: one request with
   `tm=202503251400` and no `obsid`. If it returns rows, the network has history and the
   item is alive; if it returns only current conditions or an empty body, **that** is the
   moment to write "current-conditions only, no history" into this report as a settled fact.
3. Then the 30 km question. 영덕읍 at 36.415 N, 129.366 E is EPSG:5179 x 1,167,301,
   y 1,825,782, inside the canonical box. The station list with 경도/위도/고도 is in the
   dataset's 기술문서 `03_산악기상정보_기술문서_v1.5(수정본).docx`, downloadable from the
   dataset page without a key; get that first and compute the distances before spending
   quota.

---

## Item 4. 임상도 1:5000, 경상북도

**Found at:** nowhere. No shapefile, GeoPackage or file geodatabase of 임상도 exists in the
three searched trees.

**Acceptance result: FAIL, for absence.** CRS not checked (no file). Attribute presence of
임종, 임상, 수종, 영급, 경급, 수관밀도 not checked (no file). Polygon count inside the canonical
영덕 box not computed (no file). Top ten 수종/임상 codes by area not computed (no file).
`data/raw/forest_type_map/` was not created and no `MANIFEST.json` was written.

**Evidence.** The author answered "None of them". The `.shp`/`.gpkg`/`.gdb`/`.geojson` sweep
across all three trees returned only this repository's 도로명주소 and 민원행정기관 layers and
`pyogrio` test fixtures inside two virtualenvs.

**The one thing this item's acceptance test that could be verified, was.** The canonical box
the brief quotes is correct. `data/processed/routing_demo_canonical.npz` carries
`grid_extent = [1126514.9285714286, 1789870.4642857143, 1204514.9285714286,
1880370.4642857143, 500.0]`, that is x from 1,126,515 to 1,204,515 and y from 1,789,870 to
1,880,370 in EPSG:5179 at 500 m resolution, 78.0 km by 90.5 km, 156 by 181 cells, matching
`haz_stack` of shape (5, 181, 156). In WGS84 the corners are SW 36.09758 N 128.90542 E,
SE 36.08429 N 129.77141 E, NW 36.91320 N 128.92024 E, NE 36.89951 N 129.79535 E. The
committed ignition point `ign_xy` sits at 36.43000 N 129.05000 E. Nothing in the npz was
modified; it was opened read-only.

**What the author must redo** (agency: 산림청; as-of: dataset page read 2026-09-13):

1. The data.go.kr entry **15093362, 산림청_임상도(산림공간정보 1:5000)**, is a pointer, not a
   download: 제공형태 is 「기관자체에서 다운로드」 and the URL it gives is FGIS,
   `https://www.forest.go.kr/newkfsweb/html/HtmlPage.do?pg=/fgis/UI_KFS_5002_020100.html&mn=KFS_02_04_03_04_01&orgId=fgis`.
   확장자 SHP. The page's own description names exactly the attribute family the acceptance
   test asks for: 「임종·임상·수종·경급·영급·수관밀도 등 다양한 속성정보를 제공(축적 1:5,000)」.
   업데이트 주기 연간. 이용허락범위 **공공저작물 제3유형: 출처표시, 변경금지**.
2. ⚠ **제3유형 (변경금지) is a licence constraint this project has to take seriously.** It
   permits use with attribution but bars distributing a modified version. Clipping to the box
   and deriving fuel classes for internal use is normal research use; republishing a modified
   임상도 layer, or shipping one in the finals kit or the release bundle, is not obviously
   inside it. Decide that before the layer reaches any judge-facing surface, and record the
   decision. This is the author's call, not a lap's.
3. Request 경상북도, or 영덕군 alone if the request form allows a 시군 unit; the full 경북 layer
   is large and the box only needs 영덕 and its margins.
4. When the file arrives, put the raw download under `data/raw/forest_type_map/` (git-ignored
   by design, so it never reaches a commit) and write
   `data/raw/forest_type_map/MANIFEST.json` with sha256, source URL, download date and the
   CRS as read from the `.prj`, not as assumed.
5. Expect the attribute names to be coded rather than Korean words. Report the **actual**
   field names from the `.dbf`, and if any of the six attributes is absent under any spelling,
   that is a fail with the field named.

---

## Item 5. 산림청 fire API key (data.go.kr 3070842, `forestStusService`)

**Found at:** no key anywhere. One related artefact does exist: the service's own guide
document, `~/Downloads/OpenAPI활용가이드_산림청_산불발생통계정보_v1.3.docx`, dated 2026-09-12.
It is the 참고문서 offered on the dataset page and can be downloaded without an account, so it
is evidence that the author visited the page, not that a key was issued.

**Acceptance result: FAIL, for absence.** Neither call was made. The current-day call was not
made and the 2025-03-25 call was not made, so nothing can be said about whether the 의성 and
영덕 events come back.

**Evidence.** The author answered "No, never applied". No `~/.config/wildfireguardian/datago.key`
exists, and `~/.config` has no `wildfireguardian` directory at all.

**Two findings that change this item, both verified this session.**

**(i) The service is a quarterly statistics service, not a real-time feed.** The dataset page
for id 3070842 (read 2026-09-13) names it 산림청_산불발생통계(대국민포털) and describes it as
「산불의 발생과 진화 과정을 **분기별로 집계·제공**하는 정보 서비스」. 요청주소
`https://apis.data.go.kr/1400000/forestStusService/getfirestatsservice`, REST, XML, free,
자동승인, 개발계정 10,000 calls/day, 등록일 2014-03-21, 수정일 2026-08-04. Its request
parameters are `ServiceKey`, `numOfRows`, `pageNo`, `searchStDt`, `searchEdDt`, the last two
being 발생시작일 bounds in `YYYYMMDD`. Its response fields are `locsi`, `locgungu`, `locmenu`,
`locdong`, `locbunji` (location, as administrative names and a 지번, **no latitude or
longitude**), `startyear`/`startmonth`/`startday`/`starttime`/`startdayofweek` (occurrence
time), `endyear`/`endmonth`/`endday`/`endtime` (진화종료), `firecause`, and `damagearea`.
So the acceptance test's "a location and an occurrence time" will be satisfiable, but the
location is a place name and a lot number, not a coordinate, and a "current day" call against
a quarterly-aggregated register may legitimately return nothing.

**(ii) The acceptance test as written would fail even with a valid key, and the fix is one
parameter.** This repository already holds the file-dataset sibling of this service:
`data/raw/kfs_fire_statistics/산림청_산불통계데이터_20250911.csv` (data.go.kr id 15121380, CP949,
2,020 rows, covering 2022-01-01 through 2025-09-11), acquired by the author on 2026-08-31 and
documented in that directory's README. Read read-only this session, it says:

- **On 2025-03-25 there is no 의성 event and no 영덕 event.** The nine rows whose 발생일 is
  2025-03-25 are in 봉화, 화성, 당진, 고창, 시흥, 통영, 창녕, 울주 and 포천.
- The 의성 fires are dated **2025-03-22**: 의성 안평 괴산 at 11:24 (성묘객실화추정, 46,575.2 ha),
  의성 금성 청로 at 13:57 (담뱃불실화추정, 134.24 ha) and 의성 안계 용기 at 14:40
  (농산부산물소각(과수원) 추정, 52,707.3 ha), the last two with 진화종료 on 2025-03-23 and
  2025-03-31 respectively.
- **영덕 has no ignition row in March 2025 at all.** The register's 영덕 rows run
  2025-01-12, then 2024-03-15, then 2023 and earlier. This is consistent with 영덕 having been
  burned by the spread of the 의성 complex rather than by its own ignition, which is the
  premise this project already works from, but it means no 영덕 row will ever come back from a
  date query in this register.

⚠ The limit on that evidence, stated plainly: the CSV is the **file** distribution (15121380)
and the acceptance test names the **API** (3070842). They are both 산림청 fire statistics and
are expected to carry the same register, but this session did not call the API and so did not
prove they agree. What is proven is that the file distribution, which this repository already
trusts enough to have ingested, places the 의성 ignitions on 03-22 and has no 영덕 March 2025 row.

**What the author must redo.**

1. Apply at `https://www.data.go.kr/data/3070842/openapi.do` (활용신청, 자동승인, usually
   immediate). The same account and 인증키 also covers item 3's dataset 15084696.
2. Store it at `~/.config/wildfireguardian/datago.key`, mode 600, directory 700. Note that the
   portal issues both an Encoding and a Decoding form of the key; store one, record which, and
   do not URL-encode an already-encoded key.
3. **Change the test.** Call `searchStDt=20250322&searchEdDt=20250331`, not 20250325, or the
   의성 events cannot appear. Expect 영덕 to be absent and report that as the finding rather
   than as a failure of the call.
4. Run the current-day call too, and if it returns an empty `items` block, record that as the
   expected behaviour of a quarterly register rather than as an error.

---

## Item 6. 정보공개청구 to 국립산림과학원 (open.go.kr)

**Not a dataset.** Reporting status only, as the brief directs.

**Status: not filed.** The author answered "Not filed" to the direct question on 2026-09-13.

- **Filing date:** none.
- **접수번호:** none.
- **10-day decision deadline:** not applicable; nothing is running. Under 정보공개법 the
  10-day clock starts from 접수, so it starts whenever the author files and not before.
- **Reply or files received:** none. `data/raw/foia_nifos/` was not created and no
  `MANIFEST.json` was written.

**Related, and worth the author's attention because it is the same institution.**
`docs/auto/NEEDS_HUMAN.md` NH-039 is still open: the NIFoS user guide 연구자료 제1201호 (2026),
an approximately 18 MB PDF at `https://book.nifos.go.kr/library/10130/contents/7732761`, which
the cloud sandbox has never been able to fetch and which is the primary source behind several
narrowed claims (WC-009, WFG-171, WFG-162). That document is **already public** and needs a
download, not a 정보공개청구. If the author is going to spend a filing on 국립산림과학원, the
filing should ask for what is genuinely not published, and the 18 MB PDF should simply be
downloaded on the same afternoon. This session did not attempt that download; it is NH-039's
row, not this report's.

---

## Summary

| # | Item | Result | Why |
|---|---|---|---|
| 1 | KMA API Hub key | **FAIL** | No key exists. Author confirmed never obtained; NH-012 records it deferred 2026-09-04. Tests (a), (b) not run; (c) not answered. |
| 2 | KMA bulk ASOS/AWS March 2025 | **FAIL** | No file exists anywhere in the searched trees. 영덕 gust on 2025-03-25 cannot be reported. |
| 3 | 산악기상관측망 data | **FAIL** | No key, no files. Whether the API serves history is unsettled: a `tm` past-timestamp parameter exists but no range parameter, and no call was made. |
| 4 | 임상도 1:5000 경상북도 | **FAIL** | No shapefile or GeoPackage exists. Canonical box independently confirmed against the npz; everything else unchecked for want of data. |
| 5 | 산림청 fire API key | **FAIL** | No key exists; never applied. The guide docx in Downloads is a public download, not evidence of a key. The test's date also needs changing (see item 5). |
| 6 | 정보공개청구 | **FAIL (not filed)** | Not filed. No date, no 접수번호, no deadline running, no reply. |

**Six of six fail. Zero of six partially pass.**

## What this report did not do

It did not create `~/.config/wildfireguardian/`, write any key file, create
`data/raw/forest_type_map/` or `data/raw/foia_nifos/`, write either `MANIFEST.json`, modify
any committed artifact, or register any number in `docs/NUMBERS.json`. It opened
`data/processed/routing_demo_canonical.npz` and
`data/raw/kfs_fire_statistics/산림청_산불통계데이터_20250911.csv` read-only. The only file
committed by this session is this report.

## Suggested order, if the author has one afternoon

One data.go.kr account unlocks items 3 and 5 together, both on 자동승인, both usually
immediate. That is the cheapest hour and it is the one that makes a real call possible. The
KMA API Hub account (item 1) is a second registration and unlocks items 1 and 2 together, the
API and the bulk portal being separate logins on the same agency's data. The 임상도 request
(item 4) is the long-lead item because FGIS is a request form rather than a download, so it
should be sent first even though it returns last. The 정보공개청구 (item 6) should wait until
the author has decided what is actually not public, given NH-039.
