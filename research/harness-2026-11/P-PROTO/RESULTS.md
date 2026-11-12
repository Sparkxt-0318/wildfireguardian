# P-PROTO checkpoint 1 — built in the repo only; NOT published or deployed anywhere

**Not shipped by default.** The page is built only with `WFG_BUILD_PUBLIC_VIEW=1 npm run build:static`. The default
static build — the one `.github/workflows/planner-pages.yml` deploys to GitHub Pages on a push to Main — contains no
`public-view.html` and no public-view assets (verified: default build 0 files, flagged build 1 page; both pass
`scripts/check_static_dist.mjs`). A merge to Main therefore does not publish it. The Vercel project documented in the
repo serves `planner/research-map/site` only.

Replay-only public prototype: `planner/public-view.html` → `planner/src/features/publicview/` (model.ts pure,
load.ts, PublicView.tsx, tokens.ts). Built as a second page of the static build (`npm run build:static`; same CSP as
the planner: `connect-src 'self'`; the existing static checks pass). Publishing to any URL is the user's decision and
has not been made. Comprehension by older adults is untested; the tests show consistency only.

## Safeguards (Iris, orchestrator)
- Fixed order: replay banner → official-orders slot (always above computed output) → question → cards.
- No bare clock time: a leave-by time is rendered next to the replay date and mark inside the same card; every card
  carries the replay stamp (a cropped card still says replay). Data age = replay date + input time, never minutes.
- No green / all-clear state; unresolved/partial and no-route show no time, destination or hand-off.
- Hand-off: destination only (no waypoints), as text and a GPX file whose file name, track name and description carry
  "REPLAY … NOT REAL"; no geo: link.
- Zero saved places: three labelled examples by a fixed rule, one per state (leave_by, no_route, unresolved).
- Saved places only in localStorage (guarded); the page states they stay on the device; it fetches only its own files.
- Okabe–Ito-derived state colours, no green; contrast ≥ 7:1 for all text in light and dark; base type 20 px; time
  and data age 40 px.

## Tests (`tests/planner/pproto.test.ts`, 10) — full planner suite 23 files / 395 tests pass
- All 531 real + 600 synthetic origins: a leave-by time only for leave_by, always with replay date + mark; no other card
  shows a leave or deadline time (every card's data-age line shows the replay INPUT time, e.g. "자료: 2025-03-24 18:00
  기록 (재현)" — that is the data time, not a violation; Mira note N1);
  no forbidden word (kit NEVER oracle); data age never "minutes old".
- Examples: deterministic, one per state, leave_by first.
- GPX/text hand-off: replay label in file name, metadata name and description; one waypoint; no geo:.
- Tokens: WCAG contrast ≥ 7:1 (text) and ≥ 3:1 (accent vs page); pairwise ΔE*ab ≥ 15 between the three state colours
  under Machado (2009) protan/deutan/tritan simulation; no green accent; data age ≥ time size.
- Full page in jsdom with fetch served from the repository files: order banner → official → cards; every timed card
  has the stamp beside the time; 3 example cards; every request same-origin; no geo: in the DOM.

## Not done
Screen-reader and real-device testing; English native review; waypoint hand-off (destination only by decision);
comprehension testing; any deployment.

## Checkpoint 2 (on thomas/fire-next; UNVERIFIED) — Iris's accepted design delta
- Ladder level 1 worded descriptively ("모델 계산: 이 시각 출발까지 차로 나가는 확인된 길이 있었고, 그 뒤 출발에는 확인된 길이
  없습니다"; when nothing later was requested: "그 뒤 출발은 점검하지 않았습니다"); no official 대피 준비/즉시대피 vocabulary.
- Every replay stamp carries the hedge "모델 추정 / model estimate".
- Places by URL `?scenario=<cache index path>&place=<origin id>`: both untrusted; scenario must equal a committed index
  path (matched, never fetched as given), place must be an origin of that scenario; otherwise the empty state. A shared
  link shows the banner and the in-card stamp. Helper text and the "sharing reveals the place" note.
- Tests (`pproto.test.ts` 13, `pproto.layout.test.ts` 4): parseLink rejects path-like, absolute, unknown, upper-cased and
  markup values; hostile links render three examples, fetch nothing they name, inject no markup; a 320 px Chromium
  layout with the longest place names, longest time string and a cross-midnight time (Pretendard and fallback fonts,
  ko/en): no horizontal scroll, every stamp/time/data age inside the viewport and its card. That test first FAILED
  (scroll width 364–380 px); fixed with `overflow-wrap: anywhere` on the page and break-all in the hand-off text.

## Checkpoint 2 on Main + verifier note (branch clara/pproto-followup)
- Checkpoint 2 was verified PASS WITH NOTES at 75189d9 on thomas/fire-next. Only its P-PROTO files were ported onto Main
  (`publicview/{PublicView.tsx,model.ts,publicview.css}`, `pproto.test.ts`, `pproto.layout.test.ts`, this file). The
  W-KIT, F-3.2 and other work carried on fire-next did not come across. Main's 90 s jsdom wait (53233ab) now lives in the
  shared `mount()` helper. Each page mount stops early on `.pv-error` and fails with that text.
- Verifier note: the leave-by sentence said "none after" (그 뒤 출발에는 확인된 길이 없습니다) also where the
  model found a checked road again after a gap. That description was false. There are now three sentences
  (`LEAVE_BY_WORDS` in `model.ts`), one per kind of what follows T in the sweep:
  - horizon: no later departure was requested → "later departures were not checked";
  - none_checked: every later requested departure has no checked road → "none after";
  - gap (new): the first requested departure after T has no checked road, but a later one has one → "Model: a checked
    road out by car existed for every departure up to this time; right after it, some departures have no checked road"
    / "모델 계산: 이 시각 출발까지는 차로 나가는 확인된 길이 계속 있었고, 바로 그 뒤 출발 중에는 확인된 길이 없는 때가 있습니다".
    The sentence does not mention the later road, so it cannot be read as "leaving later is also fine". The time shown
    stays T. A leave-by plan without an `after` kind fails closed to the time-less card.
- Property test (`pproto.test.ts`, "the leave-by sentence is true of the sweep it describes"): it recomputes each
  sentence's claims from the sweep itself (requested = not window_closed), not from the plan's classification. It
  covers every real and synthetic origin and requires the synthetic set to exercise all three sentences. Measured, with
  the seed and the 600 cases as before:

  | sentence | real (531 origins, 501 leave-by) | synthetic (600) |
  |---|---|---|
  | horizon | 354 | 59 |
  | none_checked | 147 | 178 |
  | gap | 0 | 53 |

  With the old two-way wording the test fails (first failure: `syn:gen:4:origin`).
- Planner suite: 24 files, 403 tests pass. `npm run build:static` passes; the default build ships no public-view file.
- Pending: Iris's review of the gap wording and Sofia's check of the Korean. Comprehension is untested.

## Next cut (branch clara/pproto-next, on the frozen b3df2a3 / PR #124) — UNVERIFIED
Iris's notes on the gap fix, and two items the orchestrator approved from her ranking (based on Sofia's March 2025
vehicle and road cases):
- **Checked step stated.** The leave-by sentences say "at each departure time checked up to this time (every N
  minutes)". N is the sweep's own uniform step (`sweepStepMin`): 10 in all 531 real places, 5–30 in synthetic cases.
  The clause is left out when the step is not uniform. The gap sentence is now exact ("the next departure time
  checked has none"). It still never mentions the later road. The Korean follows Sofia's corrections: present tense,
  "출발 시각마다", no "출발 중에는". "언제 출발하든" is replaced by the stated step because only the grid is checked.
- **"No checked road" keeps both meanings** (model no-route and unresolved) and is never "no road" or "closed" (test).
  An unresolved later departure always renders as none_checked or gap, never as "not checked" (horizon). Later
  requested departures by sentence and verdict:
  - real: none_checked 221 no-route + 2 unresolved;
  - synthetic: none_checked 388 no-route + 96 unresolved; gap 98 no-route + 65 unresolved + 88 checked.
- **One outbound trip.** Every card that shows a time carries `ONE_TRIP` ("This result covers one trip out only. It says
  nothing about going back." / "이 결과는 한 번 밖으로 나가는 길만 확인한 것입니다. 돌아오는 길은 확인하지 않았습니다.").
  It sits directly after the time line inside the same card, so a crop keeps it. It never appears without a time (test).
  The 320 px Chromium layout check covers it.
- **Time first.** In every card the time line comes before the status words and any hand-off, in DOM order (test). A
  hand-off never appears without a time.
- **What this does not include**, a plain list on the page: smoke, narrow roads, queues of cars, embers setting cars
  alight, the way back.
- **Resident/staff split for the gap case.** The public card shows the contiguous time and never the later checked
  departure. Staff see the later one: the planner's own panel shows `latestSafeDepartureS` as its deadline. This split is
  deliberate: information is kept off the resident card, not lost.
- Suite 24 files / 403 tests; build:static OK; the default dist has 0 public-view files. Wording is pending Iris and
  Sofia. Comprehension is untested.
