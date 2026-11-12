# FIRE verification ledger (verifier: Nora)

Independent verification of FIRE routing streams (F-3.1 Richard, F-3.2 Thomas,
F-4.2 / F-3.4 Priya, F-C1 / F-9.3 Leo). Each row is one verdict on one pushed SHA,
re-run in a clean worktree from the stated command. The last PASS row for a
stream is its return point after a FAIL.

Environment: Python 3.12.3 `.venv` from `make api-setup` at Main 35bd351,
plus planner/tools/requirements.txt, GNU time installed.

| # | Date | Stream | Worker | SHA | Claim | Command | Verdict | Notes |
|---|------|--------|--------|-----|-------|---------|---------|-------|
| 1 | 2026-11-12 | F-C1 | Leo | df3cb3df30e5 | C1 522 cases/174 places; deadline classes grid_end 354, window 132, fire_or_limits 15, none 21 | `python3 research/harness-2026-11/F-C1/seebefore/feasibility.py` | PASS | Re-ran in clean worktree: exact counts. 132/147 and 15/147 match solve2027-impact/NUMBERS.json. Reproduced with Leo's extract (reuses wfg_impact), not re-derived from scratch. |
| 2 | 2026-11-12 | F-C1 | Leo | df3cb3df30e5 | C2 horizon 3600 s everywhere; 0-9 new cells/member/h; present fire full grid 30/18/1505/1443/160/40, inside packet 28/10/466/240/48/12 | same + `verification/nora_fc1_check.py` | PASS | Independent re-derivation (own npz/HAZARD reader, geometric inside test, not flame-mask intersection) gives identical counts. All 4 members have identical t=0 flame masks, so "466 of 1,505" holds for every member, not just some. Packet grid aligned to export grid (offset 0,0). |
| 3 | 2026-11-12 | F-C1 | Leo | df3cb3df30e5 | C3 flame masks row-major, row 0 = south; t=0 match 240/240, 466/466 vs 9/240, 44/466 row0=north | `verification/nora_fc1_check.py` | PASS | Own check: south 28/28,10/10,466/466,240/240,48/48,12/12; north 0,0,44,9,3,0. |
| 4 | 2026-11-12 | F-C1 | Leo | 30b0bdb44b2d | C4 cropped burning cells 2/8/1039/1203/112/28; 0 contain a routed road; no graph node outside packet; omitted flux peak bound <=0.703, centre-model max <=0.0047 kW/m2 | `python3 research/harness-2026-11/F-C1/seebefore/crop_roads.py` + `verification/nora_fc1_check.py` | PASS WITH NOTES | All numbers reproduced; road hit re-derived with exact shapely segment/square intersection (Leo densifies at 10 m): 0 everywhere. NOTE 1: graph bbox equals packet bbox (graph revision "G2window"), so "0 routed roads in cropped cells" and "0 nodes outside" hold by construction and say nothing about real roads beside the cropped fire. NOTE 2: nearest routed road to a cropped cell is 348/363/374 m at the three big inputs (5,5,4 cells within 1 km) - i.e. fire sits just across the domain edge. NOTE 3: BUILD_SUMMARY also omits 11-16 new ignitions per member outside the domain during the hour (17-22 intervals); C4 does not mention these. Dose bound up to 2531 kJ/m2 (centre model ~17). |
