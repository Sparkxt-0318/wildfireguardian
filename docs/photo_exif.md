# PHASE 22 STEP 2 — a coordinate out of a reported photograph

**Status: done 2026-08-07.** `src/wildfireguardian/photo/` (2 modules),
`POST /api/regions/{region}/photo-gps`, the console's upload panel, and
`tests/test_photo_exif.py` (30 tests).

---

## 0. What it is for

A 119 caller frequently cannot give an address. 「산 쪽에 연기가 난다」 is a report
and not a coordinate, and the operator's next several minutes go on establishing
where. A photograph taken at the scene usually already carries one.

So: the reporter's photograph goes in, its EXIF GPS comes out, and that
coordinate enters **the same gate everything else enters**. Nothing new happens
downstream — it is a different way of answering "where", not a different
pipeline.

---

## 1. ⚠ What it deliberately does NOT do

**It does not look at the picture.** No landmark matching, no terrain matching,
no model, no inference from what is in the frame.

That is a decision, not an omission. A location guessed from image content would
need its own accuracy study before anybody could dispatch on it, and this
project's entire stance is that a number nobody can check is worse than no
number. If the EXIF has no GPS, the honest answer is 「이 사진에는 위치 정보가
없습니다」 — not an estimate that looks like a measurement.

**EXIF only.** That is the whole scope.

---

## 2. The processing rules

⚠ These are enforced in code and asserted in tests, not stated as intentions.
The statement below is `wildfireguardian.photo.PRIVACY_KO`, and it is the **one
copy** — the console inlines it at build time and a test asserts the shipped
page carries it byte for byte, the same way the A4 sheet's standing line is
imported rather than retyped.

> 업로드한 사진은 저장하지 않습니다. 좌표(GPS)만 읽고 즉시 폐기하며, 촬영자·기기
> 등 EXIF 의 다른 항목은 읽지도 기록하지도 않습니다. 파일명은 서버로 전송되지
> 않습니다.

| rule | how it is actually true |
|---|---|
| **The photograph is never stored** | the bytes exist in one coroutine and are dropped when it returns. No temp file, no cache, no artifact directory. A test reads five photographs with the working directory in an empty `tmp_path` and asserts the directory is **still empty**; a second test greps the module source for `tempfile`, `.write(`, `.write_bytes(`, `shutil`, `os.rename` and fails if any appears. |
| **Only four EXIF tags are read out** | `GPS_ONLY_TAGS == frozenset({1, 2, 3, 4})` inside IFD `0x8825` — GPSLatitude/Ref, GPSLongitude/Ref. Pinned **by value** in a test, so widening it is a change a reviewer has to approve. A fixture carrying `Make = "ACME Phone Co"` and `Model = "Model X Pro"` is read, and the response is asserted to contain neither. |
| **`GpsReading` has nowhere to put anything else** | its fields are exactly `{outcome, lat, lon, container}`, asserted. The structural guarantee, not a promise. |
| **Nothing is logged** | not a coordinate, not a filename. See §3 for the measurement. |
| **The filename never leaves the browser** | see §3 — it is a consequence of the transport, not a scrubbing step. |

⚠ **An honest limit on "only four tags".** Any EXIF parser must walk the
directory structure to reach the GPS IFD, so Pillow unavoidably *traverses* the
other tags in memory. What is guaranteed is narrower and is the part that
matters: nothing but those four is ever **read out, returned, logged or
persisted**, and `read_gps` has no other exit.

---

## 3. ⚠ Raw bytes, not multipart — the filename cannot leak because it never travels

`POST /api/regions/{region}/photo-gps` takes the file as the **raw request
body**. The console does `fetch(…, {method:'POST', body: file})` and nothing
else: no `FormData`, no `FileReader`, no data URI, no canvas. A test greps the
built console for all six and fails if any appears.

A multipart upload carries the filename in its `Content-Disposition` header.
That header would then be in the request this process handles, and in anything
that ever logs it. Reading the body directly means **there is no field for the
filename to travel in.** `IMG_0042.HEIC` stays on the reporter's machine.

It also means no `python-multipart` dependency, which is a smaller reason and a
real one.

**Measured, because "nothing is logged" is a claim.** `run_api.py` defaults to
`--log-level warning`, so uvicorn's access log is off; but the claim has to hold
when somebody turns it on. Run with `--log-level info` and post a photograph
carrying GPS, a maker and a model:

```
INFO:     127.0.0.1:57608 - "POST /api/regions/yeongdeok_2025/photo-gps HTTP/1.1" 200 OK
```

That is the entire line. Grepping the whole log for the filename, the
coordinate, `ACME` and `Model X` returns **nothing**. The coordinate travels in
the response body only, and never in a query string.

---

## 4. ⚠ One gate. A photograph's coordinate is not special

An EXIF coordinate goes through `service.params.check_in_region` — the same
function a map click goes through and the same one `POST /api/jobs` refuses on.
There is no second rule for photographs.

Consequences, all of them deliberate:

* outside the registered walk bbox is outside it **however the coordinate
  arrived**;
* the refusal is the sentence the service already owns, shown in the same red
  banner a click's refusal uses, and a test asserts the string is `==` to
  `check_in_region(...)["reason_ko"]`;
* the run button is disabled and relabelled exactly as it is after a refused
  click.

A photograph whose coordinate is outside the bbox is a **common** case, not an
exotic one — somebody forwards a photograph taken elsewhere, or the fire is
genuinely outside the mapped area. It gets a full sentence, never a shrug.

**Two sentences, two keys.** The response carries `photo_reason_ko` (did the
photograph yield a location?) and, only when it did, `reason_ko` (may we route
from it?). Written the other way round first, `payload.update(gate_verdict)`
silently replaced the first with the second and the screen lost the only
explanation of why a photograph produced nothing. A test pins them apart.

---

## 5. The failure cases, each with its own sentence

⚠ **Never a silent no-op.** A file that was picked and produced nothing visible
reads as a broken screen, which is worse than a refusal.

| outcome | when | what the operator reads (abridged) |
|---|---|---|
| `no_exif` | no EXIF block at all | 「사진에 위치 정보가 없습니다. EXIF 자체가 없는 사진입니다. **메신저(카카오톡·문자 등)로 전달된 사진은 전송 과정에서 EXIF 가 제거되는 경우가 많습니다.** 원본 사진을 받아…」 |
| `no_gps` | EXIF present, no GPS IFD | 「…EXIF 는 있으나 GPS 항목이 없습니다. **촬영 기기의 위치 서비스가 꺼져 있었거나**, 전달 과정에서 위치만 제거된 경우입니다.」 |
| `gps_zero` | GPS written as 0, 0 | 「측위가 되지 않은 상태에서 촬영된 사진이므로 위치로 쓸 수 없습니다.」 |
| `gps_incomplete` | values without an N/S or E/W reference, or out of range | 「GPS 항목이 불완전해 좌표를 확정할 수 없습니다.」 |
| `unsupported_format` | not JPEG/PNG/HEIF by magic bytes | 「지원하지 않는 파일 형식입니다.」 |
| `malformed` | truncated or corrupt | 「파일이 손상되었거나 전송이 중단된 것으로 보입니다.」 |
| `too_large` | over 24 MiB | refused on the `Content-Length` header, before the body is read |
| `empty` | zero bytes | 「빈 파일입니다.」 |

### ⚠ Messenger stripping is NOT detected. It is named as the likely cause.

The brief asked for it to be mentioned because it is common, and mentioning it
is exactly what happens — **it is not claimed as a detection.** A photograph
re-encoded by KakaoTalk and one from a camera that never wrote EXIF are
byte-indistinguishable after the fact, and no honest check separates them.

What the two sentences do is lead with the *likelier* cause for each shape:
no EXIF at all is usually re-encoding, so `no_exif` names the messenger; EXIF
present with the GPS directory missing is usually location services, so `no_gps`
names that. Both are stated as 「…경우가 많습니다」 and 「…경우입니다」, never as a
finding about this file.

### ⚠ Truncated is not the same as no location

`malformed` exists because the two demand different actions.
「위치 정보가 없습니다」 sends the operator to the map; 「파일이 손상되었습니다」 tells
them to ask for the photograph again. The first version returned `no_exif` for a
truncated HEIC — a quiet failure wearing an honest sentence. Caught in testing
and fixed with `_BrokenContainer`; a test pins all three truncation points.

---

## 6. ⚠ HEIC is parsed by hand, and here is why

HEIC is the iPhone default, so it is not optional.

**Measured first:** Pillow 12.3.0 in this environment reports
`features.check('heif') is False`. It cannot open a HEIC. The usual remedy,
`pillow-heif`, bundles **libheif and an HEVC decoder** as a binary wheel — a
large dependency, outside the pure-Python rule that admitted `fastapi`
([`api_layer.md`](api_layer.md) §3), and one that exists to decode **pixels**,
which is the single thing this module must never need.

So `_heif_exif` walks the ISO base media container directly: `meta` → `iinf`
(which item is the EXIF one) → `iloc` (where it is), then copies that byte
range. It never enters `mdat` for image data and constructs no decoder. About
120 lines, no dependency, and it only ever reads the ~200 bytes it came for.

⚠ **It is verified against a container Apple's own encoder wrote**, not only
against one this repository synthesised — which is the real risk with a
hand-written ISO-BMFF reader. The fixture's provenance is recorded in the test
file: `sips -s format heic` on macOS, from an 8×8 solid colour with the same
EXIF the JPEG test builds. No photograph, no person, no place.

A test asserts `features.check('heif') is False`. If Pillow ever gains HEIF
support, that test fails — so replacing the hand-written reader becomes a
deliberate decision rather than a silent divergence.

---

## 7. The screen

The console's map pane carries a 「신고 사진에서 좌표 읽기」 panel: a file button,
drag-and-drop anywhere on the map, and the processing statement in full.

* On success the crosshair is drawn **exactly as a map click draws it**, and the
  header labels the source 「사진 발화점(EXIF)」 rather than 「클릭 발화점」, so it is
  always visible that the coordinate came from a photograph.
* The projection is done **server-side**. The response carries `x_5179`/`y_5179`
  from the same pyproj transformer every committed coordinate came from; the
  page does no geodesy, for the reason `locate` already documents.
* Click and photograph share one `applyPoint()`, so neither can grow its own
  wording, its own banner, or its own idea of what is servable.

⚠ **An attempt that produced no coordinate clears the previous one.** Found by
uploading a GPS-less photograph after a successful one: the header still read
「사진 발화점(EXIF) 37.5000, 127.0000」 from the *previous* file while the banner
said this photograph had no location. Losing an earlier click costs one click;
running a scan from a coordinate the operator believes came from the photograph
costs more than that.

⚠ **The panel covered the refusal banner at 1366×768.** The banner had a flat
`max-width:640px`; the map pane at that resolution is 847 px and the panel takes
the right 302 of it, so the end of the sentence went **behind** the panel — and
the sentence in question is the one explaining why the live-calculation button
is disabled. Measured, not noticed by eye: banner `16..656`, panel `544..830`,
112 px of overlap. The bound is now `min(640px, calc(100% - 334px))`, giving a
16 px gap at 1366 and leaving 1600 and 1920 untouched at 640.

| viewport | banner width | gap to panel | document scroll |
|---|---|---|---|
| 1920×1080 | 640 | 231 px | 0 × 0 |
| 1600×900 | 640 | 33 px | 0 × 0 |
| 1366×768 | 512 | 16 px | 0 × 0 |

---

## 8. Verified

| | |
|---|---|
| JPEG · PNG · HEIC | all three return **36.46628 N, 129.39961 E** from the same EXIF |
| HEIC path | genuine Apple-encoded container, EXIF item located via `iinf`/`iloc` |
| no EXIF · no GPS · 0,0 · no hemisphere ref · truncated · not an image · empty · oversize | each its own outcome and sentence |
| out-of-bbox photograph | `reason_ko` **==** `check_in_region(...)["reason_ko"]`, same red banner, button disabled |
| device fields | `Make`/`Model` present in the fixture, **absent** from every response |
| files written while reading | **0** |
| access log with `--log-level info` | path only; no filename, no coordinate, no device |
| browser, end to end | HEIC → EXIF → gate → 「완료 · 458개 출발지」, 라우팅 **10.596 s** |
| screen gates | offline 0 · dash 0 · contrast 0 (new panel measured 5.17:1 to 16.32:1) |
| tests | **30** in `tests/test_photo_exif.py` |

---

## 9. Limits, stated

1. **EXIF GPS is what the camera believed**, and it can be wrong — indoors, in a
   valley, or straight after a cold start. It is a starting point for routing,
   not a survey. The screen labels it 「사진 발화점(EXIF)」 for that reason.
2. **No altitude, no direction.** GPSAltitude and GPSImgDirection are not read.
   The photograph says where the phone was, not where the smoke is, and the
   difference is not modelled.
3. **Messenger stripping cannot be detected** (§5), only named as a likely cause.
4. **No EXIF orientation, timestamp or device is used** for anything — including
   sanity checks that might otherwise be tempting, such as "was this taken in
   the last hour?". Reading the timestamp would be reading a field outside the
   four, so the check does not exist.
5. **The hazard field is still fixed.** A photograph moves the routing origin.
   It does not regenerate the pre-computed surface, and the standing yellow
   caution on the console says so for photographs as well as clicks.
