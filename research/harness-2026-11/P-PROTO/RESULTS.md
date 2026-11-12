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
