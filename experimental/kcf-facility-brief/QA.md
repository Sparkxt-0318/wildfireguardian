# QA record — kcf-facility-brief v1

Date: 2026-11-11, updated 2026-11-16 (bundled font, trimmed outputs, rebased on Main) · Worktree `wfg-kcf-brief` · branch `kcf/facility-brief-v1` · originally built on `5fa19a2`, rebased onto Main `680f5948c011`
Environment: Linux, Node v22.23.4, pre-installed Playwright Chromium, poppler `pdfinfo` and `pdftotext`.
Command: `tools/verify.sh` → **ALL PASS** (14 steps, including 30 browser checks and 23 A4 PDFs, each one page with the bundled font). The full log is in `qa/verify_log.txt`.
All checks below were run by software written in this session and reviewed by an AI agent. No human or
practitioner has reviewed this tool.

## Which input was tested

- **Contract fixtures** (`fixtures/`): three valid baseline/revised pairs and four invalid variants.
- **Chat 1's real planner output, commit `4169cccc427e9e19be3851326a1225df89fe96f2`** (see `qa/planner-4169ccc/README.md`). The tag `kcf/planner-delay-v1-ready` never reached GitHub because Chat 1's proxy refused the tag push, and it is still absent in this clone. Chat 1 published the tagged commit as branch `claude/stoic-davinci-eha5j9`. This session fetched it read-only, pinned the SHA, and read files with `git show` (no checkout, no worktree change).
  - **First run, adapter 1.0.0: all 4 rejected** because `schema_version` is an integer. The diagnostic pass listed 8 more mismatches.
  - **After adapter 1.1.0** (mapping Chat 1's documented `SCHEMA.md`; no check loosened):
    - demo baseline/revised pair (2호차 +600 s): accepted, final unload T0+35분 → T0+57분, A4 1 page per view;
    - shuttle sample and missing-input sample: accepted;
    - contract normal-vs-delayed pair: correctly rejected, because the two files have different `case_id`s.
  - The demo pair's briefing metadata was written by this session, not by the planner.
- The local manager packet at `/Users/jp/Documents/Codex/2026-11-11/ex/outputs/korean_manager_handoff/manager/` does not exist on this machine and was not used.

## Results

| Check | How | Outcome |
|---|---|---|
| Launches offline | `tests/viewer.e2e.js`: file:// URL, every non-file request aborted and recorded, CSP `default-src 'none'` | PASS, 0 external requests, 0 script errors |
| A4 one page, Korean kept in print | `tools/render_examples.js`: 9 example pages; `tests/viewer.e2e.js`: viewer print of both views | PASS, 9/9 examples and 2/2 viewer prints are 1 page; 657–950 Hangul characters extracted per PDF; exercise label present |
| Korean layout inspected | With the bundled font, looked at PNGs of `delayed_vehicle/county_after`, `delayed_vehicle/facility_after` and `unknown_input/county_after` | Readable. No clipped or overlapping text. `word-break: keep-all` keeps Korean words whole. Long vehicle labels wrap to 2 lines in the trip table (acceptable). |
| Unavailable time cannot leave a stale number | Unit test + e2e: delayed case revised has `final_unload_s: null` | Current fields show **모름**. The old `T0+34분` appears only as a struck-through "이전 … — 무효". before → after → before toggling follows the data each time. A revised file that keeps a number while people are unconfirmed is **rejected** (`fixtures/invalid/stale_final_unload.revised.json`). |
| Updated time replaces the old one | Unit test + e2e: destination case 2100 s → 2640 s | Current fields show `T0+44분 (16:44)`. `T0+35분` appears only under `prev:`. The handoff says 16시 44분, "수용 확인 전 값". |
| Rejection clears the page | e2e: load a different case's revised file through the real file input | Error page appears and no previous numbers remain. Valid files load correctly afterwards. |
| Two views agree | Unit test (all 3 cases × before/after) + e2e (DOM, all 3 cases) | PASS. Every `data-k` field shown in both views (people, checked, unconfirmed, as-of, final unload, each trip's people, depart, unload, status) is identical. Group sums equal the headline totals. |
| Rejects inconsistent totals | Unit tests | checked ≠ trip sum, checked > total, groups ≠ metadata, non-integer counts |
| Rejects impossible timestamps | Unit tests + e2e | unload < depart, negative, revised update not later than baseline, field report after latest update, departure before report while vehicle waiting or delayed, bad T0 clock |
| Rejects cross-case comparison | Unit tests + e2e | baseline and revised case differ; metadata case differs |
| Personal data guard | Unit tests | name/성명 keys, phone-number values rejected |
| 30-second handoff | Unit tests (≤165 syllable units, starts "훈련 상황입니다.", ends "이상입니다.", no `(으)`, `null` or `undefined`) | 133–165 units, about 24–30 s at 5.5 syllables/s. Reading speed was **estimated**, not timed with a speaker. |
| Phone width | e2e at 390 px | no horizontal page scroll |
| Real planner output (4169ccc) | `tools/integrate.js` + unit tests + viewer file inputs | 4 accepted, 1 correctly rejected (cross-case). Views agree. Handoff names the later departure. All 8 A4 pages are 1 page. |
| Integration command | `tools/integrate.js` on the 3 fixtures (accepted, county and facility A4 = 1 page each) and on an invalid fixture (rejected, exit 1) | PASS |

## Known limits found during QA

- Fonts: a regular and bold subset of Noto Sans KR is bundled (`assets/fonts/`). The viewer embeds it; static pages
  link it. Every PDF's font list is checked for it (`RENDER_REPORT.json` `bundled_font_in_pdf`, viewer e2e).
  Layout no longer depends on installed fonts. Different browsers' print engines can still break lines slightly
  differently; only Chromium was tested. A Hangul syllable outside KS X 1001 and outside this package's own text
  falls back to a system font. The checkbox glyph is □ because the font has no ☐.
- One-page fit is measured. The tools re-print at density 0→3 until the PDF is one page, and the viewer lays the
  sheet out off-screen with the print rules at A4 size. Beyond density 3, which is about 7.5 pt type, a long output
  still spills; the tools report the page count and the viewer marks the sheet `data-print-fit="overflow"`. The
  viewer measurement is an approximation of Chrome's print layout and has been tested in Chromium only.
- Chat 1's planner reports no vehicle status, destination status or per-group mobility needs. These appear as
  "확인 안 됨", "미확인" and "미제공", so a person must fill them in.
- Displayed minutes are rounded up. A planner difference of under 60 s can show the same minute before and after,
  although the change line still lists it.
- The planner `reason` field is shown verbatim, so English text from a planner appears untranslated.
- The Korean wording was written and reviewed by an AI agent only. No Korean practitioner has read it.

## What a human manager would still need to assess

See README § "What a human manager still has to assess": actual boarding and arrival, destination capability,
real road status, vehicle and staff realism, clinical group needs, replacement-vehicle dispatch authority, fire and
smoke exposure versus sheltering in place, and whether practitioners find the wording and layout usable.
