# F-DYN clearance margins (non-evaluated; kit and test-kit routes labelled, never pooled)

**Setup.** `fdyn_clearance.py`, the same computation as `clearance_panel.py`, run on F-DYN 5 h requests whose route
was published.

**Two route sources, reported separately:**
- **KIT:** the unmodified request-window kit at 900 s, guard 3,072 MiB (`fdyn_b900`). Two routes. This is the kit
  figure.
- **TESTKIT:** the modified test kit of FDYN_PLAN A3(b), with all three memory gates at 12 GiB, at 450 s. Five routes.

**Packets.** v3.1 (`kriged_mean`; `firms_early` = bracket-start). Activity: present fire on [0, R_max); future cells on
[birth, birth + T).

| Label | Request (Yeongdeok 0325T23) | Arrival | Clearance r* | Limit | Domain dist. | Margin r_lo at a0 + {0, 60, 300, 600} s |
|---|---|---|---|---|---|---|
| KIT | firms …207 | 59 | 12,082 m | CROP | 2,544 m | 5,999 at all four (search cap r_hi = 6,000 reached; censored) |
| KIT | firms …168 | 274 | 5,118 m | CROP | 4,653 m | 5,117 at all four |
| TESTKIT | kriged …207 | 59 | 12,082 m | CROP | 2,544 m | 5,999 at all four (censored) |
| TESTKIT | firms …168 | 274 | 5,118 m | CROP | 4,653 m | 5,117 at all four |
| TESTKIT | kriged …168 | 274 | 5,118 m | CROP | 4,653 m | 5,117 at all four |
| TESTKIT | firms …166 | 3953 | **4.4 m** | FIRE | 8,039 m | not computed: `search(0)` found no route (witness-search limitation; NOT_FOUND_WITNESS_SEARCH) |
| TESTKIT | kriged …166 | 3953 | **4.4 m** | FIRE | 8,039 m | not computed (same) |

**Correction (Mira, REQUEST 12 N1, ledger 84). The 3,953 s route's "4.4 m" understates its exposure.**
- The limiting segment is `w545751967:s46:f` (12.8 m), traversed over [3948, 3950] s.
- CURRENT cell 5173 is active on [0, 3948.10) s.
- The segment **enters that cell's rectangle (0.0 m)** and lies inside it from t ≈ 3948.94 s to 3950 s, on both packets.
- So the route drives through the footprint of the limiting cell **about 0.84 s after its modelled burnout (R_max)**.
- The 4.4 m figure applies only to the 0.1 s active window before burnout.
- **The real margin is sub-second in time and 0 m in space,** and it rests entirely on the modelled burnout time. That
  is the quantity the burnset P1 issue (ledger 65) concerns.
- Any quotation of this route must state it this way. "Spatial margin about 4 m" is withdrawn.

**Reading.**
- **The short routes are crop-limited.** Their clearance is at least the stated value within the packet domain; a
  fire outside the domain could be nearer.
- **Extra travel time buys no margin** on these routes: +60 to +600 s gives the same r_lo.
- **The long 3,953 s route passes 4.4 m from an active flaming cell rectangle,** on both packets. It is certified
  contact-free by the kit's checker, but see the correction above: it enters a cell footprint 0.84 s after that cell's modelled burnout.
- **The clearance search's witness stage did not find a route there**, although the kit did. That is a limitation of
  `clearance.search` on long multi-hour routes, not a result about margins.

**Published routes** (Mira N2): now committed in `published_routes/`, one file per route, with its request and its graph/packet paths, so r* can be recomputed from the repo.

**Verification.** All 20 margin witness routes (`margin_routes.tgz`; 4 deadlines × 5 routes with a0) were re-checked:
- **the unchanged frozen whole-road checker:** 20/20 CERTIFIED_ADMISSIBLE;
- **exact rational clearance above r_lo:** 20/20. In 8 of them no active source lies within r_lo + 50 m of the route.

`fdyn_verify_margins.py`; files `VERIFY.jsonl` and `VERIFY.txt`.
