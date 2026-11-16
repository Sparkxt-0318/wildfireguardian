# KCF facility brief — 훈련용 시설 이송 브리핑 (오프라인)

> **Fictional exercise material. 연구용 훈련 시안입니다.** No agency has endorsed, reviewed or tested this sheet.
> It contains no resident names, records or contact details, and it rejects inputs that look like them.
> Planner-checked assignment does not show that anyone has boarded a vehicle or arrived at a destination.

A facility manager calls the county during a fictional wildfire evacuation exercise. The second vehicle is late.
The county needs to know what changed, how many people still lack a confirmed transport arrangement, what
assistance is requested, who must confirm it, and which assumptions the route depends on. A map screenshot cannot
answer those questions. This tool turns a **baseline** and a **revised** planner JSON (plus an optional briefing
metadata file) into two Korean views and a one-page A4 handoff:

| View | Leads with |
|---|---|
| **시설 담당자** (facility) | group counts and mobility needs, vehicle status, boarding assumptions, departure/unloading times, the confirmations still outstanding |
| **시군 재난안전 담당자** (county) | what changed, how many people are still unconfirmed, the assistance requested and who confirms it, the three information sources kept apart, and a 30-second spoken handoff |

## Launch (offline)

Open **`viewer.html`** in any current browser by double-clicking it or using `file://`. It is a single file:
CSS, logic and the three example cases are inlined, a Content-Security-Policy blocks all network access, and it
embeds its own Korean font: a regular and bold subset of Noto Sans KR (SIL OFL, ~190 KB each; see
`assets/fonts/README.md`). Printing therefore looks the same on any machine. A rare Hangul syllable outside the
subset falls back to a system Korean font.

- **예시 사례**: choose one of the three contract fixture pairs.
- **기준 JSON / 변경 JSON / 메타 JSON**: load your own files. Each load clears the page and renders it again.
  If validation fails, the previous brief is removed and the errors are shown in its place.
- **시설 담당자 | 시군 재난안전 담당자**: switch views.
- **변경 전(기준)만 보기**: show what the county saw before the change.
- **A4 인쇄**: prints only the selected view on one A4 portrait page.
- URL hash shortcuts: `viewer.html#case=destination_pending&view=facility&before=1`.

## Printable examples (saved)

`examples/<case>/` holds `county_before`, `county_after` and `facility_after` as `.html` and `.a4.pdf`. One preview
PNG, `examples/delayed_vehicle/county_after.png`, is committed; `tools/render_examples.js` regenerates the rest,
plus `handoff_30s_before.txt` and `handoff_30s_after.txt`. `examples/SUMMARY.json` lists the key numbers and input
hashes. `examples/RENDER_REPORT.json` records the page count, horizontal-overflow check, external requests and
Korean glyph count for each PDF.

Main example: **`examples/delayed_vehicle/county_before.a4.pdf` → `examples/delayed_vehicle/county_after.a4.pdf`**.

## Commands (Node ≥ 18; Playwright/Chromium and poppler only for PDF steps)

```bash
node tools/build.js                 # rebuild viewer.html and examples/*.html, handoff texts, SUMMARY.json
node --test tests/core.test.js      # validation, stale-number, view agreement, handoff budget, PII guard
node tools/render_examples.js       # A4 PDF + PNG for examples, one-page check, network blocked
node tests/viewer.e2e.js            # offline browser test of viewer.html (file inputs, toggles, print)
tools/verify.sh                     # all of the above + integration runs; log in qa/verify_log.txt
```

### Integration check against a real planner output

```bash
node tools/integrate.js --baseline <baseline.json> --revised <revised.json> [--meta <briefing_meta.json>] [--out DIR]
```

Any input can be given as `git:TAG:path`. The file is then read from the tagged commit with `git show`, with no
checkout and no worktree change. `tools/check_planner_tag.sh` looks for Chat 1's local tag
`kcf/planner-delay-v1-ready` and lists the JSON files in that commit. Exit codes: integrate `0` accepted /
`1` rejected / `2` usage error; tag probe `0` found / `3` absent.

**What was tested:** this package's contract fixtures, plus **Chat 1's real planner output at commit
`4169ccc`**. The tag never reached GitHub because the tag push was refused, so Chat 1 published the commit as
branch `claude/stoic-davinci-eha5j9`; it was read here by SHA only.
- The first run with adapter 1.0.0 rejected every file.
- Adapter 1.1.0 maps Chat 1's documented result schema.
- The demo delayed-vehicle pair, shuttle and missing-input samples are now accepted. The contract pair is
  rejected because its two files have different `case_id`s.

Details are in `qa/planner-4169ccc/README.md` and `QA.md`. To re-run against the pinned commit:

```bash
node tools/integrate.js --baseline git:4169cccc427e9e19be3851326a1225df89fe96f2:<path> --revised git:4169cccc427e9e19be3851326a1225df89fe96f2:<path> [--meta <file>]
```

## Inputs

See `docs/CONTRACT.md`. In brief:

- **Planner JSON (baseline and revised)** needs the common fields `schema_version, case_id, status, reason,
  final_unload_s, groups_total, people_total, people_with_checked_transport, trips, missing_information,
  assumptions`. `status` must be one of `CHECKED_ROUTE | MODEL_SCOPED_NO_ROUTE | MISSING_INPUT | UNRESOLVED`.
  A `null` time is shown as **모름** (unknown).
- **Briefing metadata** (`briefing_meta.json`, optional but recommended) supplies the facility label, the exercise
  label, the time origin T0, roles, group labels and needs, vehicle and destination labels, the exercise time of
  each update, fictional field reports and road status. Without it, the brief still renders and every missing
  item is marked 미제공.

**Rejected:** inconsistent totals; a numeric `final_unload_s` while people are unconfirmed or the status is not
`CHECKED_ROUTE` (treated as a stale number); unload before departure; negative times; a revised update that is not
later than the baseline; field reports dated after the latest update; a departure before the report time while the
vehicle is still marked waiting or delayed; different `case_id`s; unknown statuses; personal-data-like fields or
values.

## Fixtures

| Case | Baseline → revised | Exercises |
|---|---|---|
| `delayed_vehicle` (KCF-EX-DELAY-01) | 18 people checked, all unloaded T0+34분 → 2호차 delayed, 4 wheelchair users unconfirmed, final unload **모름** | unavailable time, assistance request |
| `unknown_input` (KCF-EX-UNKNOWN-02) | 12 checked → `MISSING_INPUT`, 0 checked, all times unknown | missing input ≠ safe |
| `destination_pending` (KCF-EX-DEST-03) | bed-bound group moved to a hospital awaiting acceptance; final unload T0+35분 → **T0+44분** | updated time, destination confirmation |
| `invalid/` | stale final unload, totals mismatch, unload before depart, reversed update times | rejection |

## Design context

The design follows a Korean precedent described in the task brief. On 10 April 2026, Goesan County (괴산군)
met with county safety staff, fire, police and a forest-adjacent hospital. Its published agenda covered situation
reporting, transport by patient needs, securing vehicles and advance route planning
(<https://www.goesan.go.kr/www/selectBbsNttView.do?bbsNo=213&key=136&nttNo=129228>; not re-fetched in this
session). This sheet is a research exercise and is not connected to that county or meeting. The local manager
packet named in the brief (`/Users/jp/.../korean_manager_handoff/manager/`) was not present on this machine and
was not used.

## What a human manager still has to assess

The tool reports what the planner and the metadata say. It does not assess any of the following:

- Whether anyone has **actually boarded** or **arrived**. "배정 확인" means the calculation only.
- Whether a destination can **really receive** these people: beds, oxygen, staff, wheelchair access.
- **Actual road status**. A modeled fire restriction is not an observed closure, and an unknown road may be blocked.
- Whether the **vehicle types, capacities, securing points and accompanying staff** are realistic. Boarding times are exercise assumptions.
- Whether the **group needs** are correct for the specific residents. Clinical judgement is needed. The tool holds no resident data.
- Whether a **replacement vehicle** exists, who pays for it and who dispatches it. The tool only names who should confirm.
- **Fire behaviour**, heat or smoke exposure on the route, and whether moving people is better than sheltering in place.
- Whether the Korean wording, time origin and layout work for **real practitioners**. Only AI-run checks have been done; no practitioner review.

## Files

```
viewer.html                 offline entry point (built)
src/brief_core.js           validation, adapter, model, Korean rendering (Node + browser)
src/brief.css               screen + A4 print styles
src/viewer_shell.html       viewer template
fixtures/                   contract fixtures (3 pairs + invalid)
examples/                   saved before/after A4 examples, handoff texts, SUMMARY, RENDER_REPORT
tools/                      build, render, integrate, tag probe, verify
tests/                      unit tests + offline browser e2e
docs/CONTRACT.md            input contract and metadata schema
docs/FACILITATOR_GUIDE.md   short facilitator guide, three neutral questions, blank responses
QA.md                       QA record
qa/                         verification records (log, e2e and integration JSON, planner run); screenshots and
                            duplicate prints are regenerated by tools/verify.sh and git-ignored (.gitignore)
assets/fonts/               bundled Noto Sans KR subset (OFL) + licence + rebuild notes
```
