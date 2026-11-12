"""Render outputs/hpwren_archive_probe.md from the probe JSON files (no network).
Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hpwren_common import ROOT
O = ROOT / "outputs"
main = json.load(open(O / "hpwren_archive_probe.json"))
rows = "\n".join(
    f"| {r['date']} | {r['cam']} | {r['note']} | {r['list_status']} | {r['n_listed']} | {r['image_status'] if r['image_status'] else '-'} | {r['video_status']} | {r['video_storage_class'] or '-'} |"
    for r in main)
txt = f"""# HPWREN archive reachability probe

Data courtesy of HPWREN (hpwren.ucsd.edu), UC San Diego. Run date: 2026-11-11 (so the 90-day window starts ~2026-08-13).
Scripts: `src/hpwren_archive.py` (URL builders, `archive_exists`), `src/s0_archive_probe.py` (table below), `src/hpwren_common.py` (throttle + cache).
~96 probe requests to cdn.hpwren.ucsd.edu, ~12 to www.hpwren.ucsd.edu; sequential, >= 1.2 s apart, UA `research-poc-camera-arrival/0.1`; only HEAD requests and tiny list GETs; no image/video bytes downloaded. Raw per-request log: `cache/request_log.jsonl` (uncommitted); machine-readable results: `outputs/hpwren_archive_probe*.json`.

## URL templates (from the cameras page JS)

| item | template |
|---|---|
| site/camera metadata | `https://www.hpwren.ucsd.edu/cameras/sites.js` |
| image list (3 h block) | `https://cdn.hpwren.ucsd.edu/hpwren-cameras/<cam>/<YYYY>/<YYYYMMDD>/<YYYYMMDD>_<cam>_Q<q>.txt` |
| image (full res, "large") | `https://cdn.hpwren.ucsd.edu/MTA/<cam>/large/<YYYYMMDD>/Q<q>/<epoch>.jpg` |
| 3 h video | `https://cdn.hpwren.ucsd.edu/hpwren-cameras/<cam>/<YYYY>/<YYYYMMDD>/Q<q>.mp4` |

* `<cam>` = camera id key from `sites.js` (e.g. `cp-e-mobo-c`). `<q>` = 1..8 = 3-hour blocks 00-03 ... 21-24 **Pacific local time**; the date in the path is the Pacific date (verified: first epoch of 20240703 Q1 = 1719990029 = 2024-07-03 07:00:29 UTC = 00:00:29 PDT).
* `<epoch>` = Unix epoch seconds UTC. Cadence: one image per minute (median spacing 60.0 s, range 58-62 s; 180 images per block).
* List format: new lists = one `<epoch>.jpg` per line. Older lists (seen 2023-01-04 and 2023-07-01) = an `echo Metadata: ...` line then `00001 <epoch>.jpg captured YYYYMMDD_HHMMSS-0700` lines. `hpwren_archive.get_list` parses both.
* Image size: 2026-08-16 sample `cp-e-mobo-c` Q5 first image = 482,607 bytes, `image/jpeg` (HEAD only; pixel dimensions not measured because no image bytes were downloaded; to be measured in Step 1). MP4 sizes: 10.9 MB (2024-07-03 Q1, night) to 63 MB (2026-11-05 Q4, day) per 3 h block.
* Video request in the JS uses the same `baseVideoUrl`; there is also a Lambda image-list endpoint for data < 6 h old (POST with an API key embedded in the page); NOT used here (real-time data needs a licence for automated retrieval, see access notice).

## Results (Q5 = 12-15 PT for every row; list = GET, image = HEAD of first listed image, video = HEAD)

| Pacific date | camera | why | list HTTP | #listed | image HEAD | video HEAD | video storage class |
|---|---|---|---|---|---|---|---|
{rows}

Extra probes (all HEAD unless noted; `outputs/hpwren_archive_probe_extra*.json`):

| URL (path on cdn.hpwren.ucsd.edu) | HTTP | storage class |
|---|---|---|
| list cp-e-mobo-c 2022-10-01 / 2022-12-15 / 2023-01-01 | 403 / 403 / 403 | - |
| list cp-e-mobo-c 2023-01-04 / 2023-01-08 / 2023-01-15 / 2023-02-01 / 2023-03-01 | 200 each | - |
| video cp-e-mobo-c Q5 2018-07-01 / 2019-07-01 / 2020-07-01 | 403 / 403 / 403 | - |
| video cp-e-mobo-c Q5 2021-08-15 | 200 | DEEP_ARCHIVE |
| video wilson-s-mobo-c Q5 2017-07-01 / 2018-01-15 / 2018-07-01 / 2018-10-01 | 403 each | - |
| video wilson-s-mobo-c Q5 2018-11-01 / 2018-12-01 / 2019-01-15 | 200 each | DEEP_ARCHIVE |
| video wilson-s-mobo-c Q5 2020-08-01 / 2020-09-06 / 2020-12-03 | 200 each | DEEP_ARCHIVE |
| video 69bravo-e-mobo-c, lp-e-mobo-c, sm-e-mobo-c Q5 2020-12-03 | 200 each | DEEP_ARCHIVE |
| video sm-e-mobo-c Q5 2019-10-10 | 200 | DEEP_ARCHIVE |
| video lp-e-mobo-c Q5 2019-01-15; stgo-e-mobo-c 2020-09-06, 2020-12-03(see above), 2021-01-15, 2021-08-15 | 403 | - |
| **GET with `Range: bytes=0-0`** on wilson-s-mobo-c 2020-09-06 Q5 video | **403 AccessDenied** (`<Error><Code>AccessDenied</Code>`) | object is DEEP_ARCHIVE |
| list with no year folder (`/hpwren-cameras/cp-e-mobo-c/20200906/20200906_cp-e-mobo-c_Q5.txt`) | 403 | - |
| MTA directory-style URL `/MTA/wilson-s-mobo-c/large/20200906/Q5/` | 403 | - |

## Findings

1. **Images (MTA/.../large/*.jpg) are retrievable only for the last ~90 days.** Boundary measured with cp-e-mobo-c: 2026-08-16 (87 days old) image = 200; 2026-08-10 (93 days old) image = 403, although the list for that date still exists. Matches the page/help text ("images are deleted after 90 days").
2. **Image lists (.txt) persist much longer but start only in early January 2023** (cp-e-mobo-c: 2023-01-01 = 403, 2023-01-04 = 200). For 2019-2022 every list probed returned 403 AccessDenied (S3 returns 403, not 404, for missing keys, so 403 alone cannot tell "missing" from "forbidden"). A list for an old date is only a list of file names; the JPEGs it names are gone (403).
3. **3-hour MP4 videos exist for much older dates, but are in S3 storage class DEEP_ARCHIVE.** A HEAD succeeds (200, Content-Length given, `x-amz-storage-class: DEEP_ARCHIVE`) while an actual GET returns 403 AccessDenied. HPWREN's help page: after 90 days "the corresponding 3h videos are archived in S3 Glacier. Retrieval from Glacier is done on request and takes about 1 day" - i.e. a request to HPWREN (the page says "contact us") is required. We did not and could not restore anything.
4. **Video presence per camera is uneven**: wilson-s-mobo-c: first positive 2018-11-01 (2018-10-01 and earlier = 403); cp-e-mobo-c: 2020-07-01 = 403, 2021-08-15 = 200; sm-e-mobo-c: 2019-10-10, 2020-09-06, 2020-12-03 = 200; lp-e-mobo-c: 2019-01-15 = 403, 2020-09-06 and 2020-12-03 = 200; 69bravo-e-mobo-c: 2019-10-10, 2019-10-24, 2020-12-03 = 200; stgo-e-mobo-c: 2020-09-06, 2020-12-03, 2021-01-15, 2021-08-15 = 403 but 2022-07-01 = 200; rdmrc-n-mobo-c and marion-w-mobo-c 2020-08-01 = 403 (rdmrc-n also 2020-09-06 = 403). A 403 may mean the camera did not exist or recorded nothing that day, or the key is absent - not distinguishable.
5. For GOFER fire periods probed (all HEAD 200, DEEP_ARCHIVE): Saddleridge 2019-10-10 (wilson-s, 69bravo-e, sm-e), Tick 2019-10-24 (wilson-s, 69bravo-e), Lake 2020-08-13 and Apple 2020-08-01 (wilson-s), Valley/Bobcat/El Dorado 2020-09-06 (lp-e, sm-e, wilson-s), Bond 2020-12-03 (wilson-s, 69bravo-e, lp-e, sm-e). Only Q5 (12-15 PT) was probed per date; other blocks are expected but unverified.
6. **Alternate path variants tried found nothing new** (no-year list path, MTA directory URL). The JS references only the three templates above. The old host c1.hpwren.ucsd.edu is unreachable from this network (not retried).

## Bottom line (as of 2026-11-11, from this network)

* Directly downloadable JPEGs at 1-minute cadence: only dates within ~90 days of today (from about 2026-08-13). **No 2019-2021 imagery is downloadable from here.**
* Earliest image *list* retrievable: ~2023-01-02..04 (cp-e-mobo-c). Earliest *video object that exists* (HEAD 200): 2018-11-01 for wilson-s-mobo-c (as probed), but videos are DEEP_ARCHIVE and not retrievable without a restore requested from HPWREN (~1 day turnaround, per their help page).
* Therefore for the GOFER fires (2019-2021) the archive is *located* but not *readable*. Next action needs a human: request Glacier restore of the specific 3 h MP4s from HPWREN (contact via https://www.hpwren.ucsd.edu/cameras/help.html), then extract frames (video frame times are standardised 3 h Pacific blocks; per-frame epoch can be derived from the block start + frame index at 1 frame/min, to be verified on the delivered file).

## Caveats
* 403 is ambiguous for missing vs forbidden. * Only a handful of cameras and one block per date were probed. * Per-camera video start dates are lower bounds from sparse probes, not exact.
"""
(O / "hpwren_archive_probe.md").write_text(txt)
