# P-PROTO — public-facing prototype on replayed data (design draft 1, for Iris)

Status: design only; nothing built. Replay data only; never for live use. Comprehension and usability untested.

## Shape
A second page of the planner's existing **static build** (`vite build --mode static`, same-origin-only CSP, no
server, no install): `planner/public-view.html` → `src/features/publicview/`. It reads the committed booth caches
(the same files and the same fail-closed `MessagePlan` as the last-mile kit) and adds no data and no computation.

## First screen: one question
"대피해야 하나요? 언제까지? / Do I need to leave, and by when?" — answered per **saved place** (a list the person
builds from the cached villages / facilities; stored only in the browser's `localStorage`, wrapped in try/catch; the
page works with an empty list and offers 3 example places from the replay).

Order of every screen, top to bottom (fixed, tested):
1. **Replay banner** (always, not dismissible): "2025년 기록 재현 · 실제 상황 아님 · 실시간 대피에 쓰지 마십시오".
2. **Official orders slot, above any computed output**: there is no live feed, so it always says
   "공식 대피 명령과 재난문자, 이장·읍·면사무소 안내가 이 화면보다 우선합니다" (and, in a replay, that official orders
   at the time are not shown here). Never empty, never below the cards.
3. **One card per saved place**: status = colour + icon + words + (only for `leave_by`) a clock time, with the
   **data age at the same type size as the time** ("자료: 2025-03-26 02:00 기록 · 재현").
   - `leave_by`: "HH:MM까지 차로 출발" (+ day marker across midnight, as W-KIT); icon: clock + arrow.
   - `no_route`: "모델상 차로 나가는 확인된 길 없음 — 공식 지시를 따르고, 위급하면 119"; icon: stop.
   - `unresolved` / `partial`: "확인하지 못함 — 길이 있다는 뜻도, 없다는 뜻도 아닙니다. 공식 안내를 따르십시오"; icon:
     question mark; neutral grey, **never green, never a time, never a destination**.
   No status uses green (no "all clear" state exists in the model).
4. **Where to go and how** (leave_by with a non-varying named destination only): a hand-off, not navigation —
   destination name and coordinates, the checked route's waypoints (a few named turns from the cached route), as
   (a) copyable text, (b) a `geo:` URI, (c) a GPX download generated in the browser. No third-party map call from the
   page; following a link is the user's action. When the destination varies or the kind is not leave_by: no
   destination, "대피 장소는 공식 안내를 따르십시오".

## Accessibility
Base type ≥ 20 px, time and data age ≥ 32 px; contrast ≥ 7:1 (WCAG AAA) for text in both light and dark themes;
colour-blind-safe palette (Okabe–Ito: vermilion for no_route, blue for leave_by, grey for unresolved), always with
icon + words (colour never carries meaning alone); one column at phone width; works without the map.

## Reuse and boundaries
Status mapping and all wording reuse the kit (`plan.ts`, `strings.ts` forbidden list, W-KIT day marker); the page
renders nothing the kit would not say. Korean source + English; English pending native review.

## Tests (planned, properties over every origin of the six caches + the 600 synthetic cases)
banner present and first; official slot above every card; unresolved/partial/no_route never show a clock time other
than the data time, a destination, green, or a forbidden word; data-age element font size ≥ time font size;
contrast ratios computed from the CSS tokens ≥ 7:1; palette pairwise distinguishable under simulated protan/deutan/
tritan (ΔE threshold); static build passes the existing CSP/static checks; GPX/geo outputs only for leave_by with a
named destination; localStorage failure leaves the page working.

## Questions for Iris
1. Saved places: is "pick from cached villages" enough, or must the first screen work with zero saved places (show
   the three examples by default)?
2. Waypoints: the cached route gives road ids; showing named turns needs OSM names that may be missing. Hand off
   destination only when the route has unnamed segments?
3. Is a `geo:` link acceptable at all on a replay page, given it could launch a real navigation app?
