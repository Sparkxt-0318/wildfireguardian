# P-PROTO checkpoint 1 — built in the repo only; NOT published or deployed anywhere

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
- All 531 real + 600 synthetic origins: time only for leave_by, always with replay date + mark; nothing else timed;
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
