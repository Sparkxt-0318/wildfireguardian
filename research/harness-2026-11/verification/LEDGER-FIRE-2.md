# Verification ledger — FIRE side, part 2 (verifier: Mira)

Takes over from Nora (verification/nora-fire) for Thomas's W-KIT and later requests, Priya's F-3.4/F-4.2, and PR
merge-readiness checks. Nora keeps Thomas's certificate request 6d923e7a / a9eb0d8.
The last PASS for a stream is the checkpoint it returns to after a failure.

| # | Date | Stream | Worker | SHA | Claim | Command | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-12 | PR #103 data-fetch (merge readiness) | Daniel | 7d43080 | fetch.py checksums pass; MANIFEST/resources.json match small/; nothing large or restricted; rebuild_env.sh runs; no secrets | see notes 1 | PASS WITH NOTES (squash merge only) |
| 2 | 2026-11-12 | W-KIT | Thomas | 6ac1bc62 | 13 tests; 531 booth-cache origins, 0 violations; 600 synthetic, 18 violations (ko.head > 35 s); planner suite 378/378 | `cd planner && npm ci && npx vitest run ../tests/planner/wkit.channels.test.ts && npx vitest run` | PASS WITH NOTES |
| 3 | 2026-11-12 | F-3.4 phase profile | Priya | b6c94bb | radiation 78/96/15% on FX1/FD1/FX2; start-up 0.8% (0.15 s); hazard validation 0.1%; radiation 31% overall, 73-96% on present-fire missions; Yeongdeok FX2 unresolved at 81 s; 59/60 ≥95% attributed; FX1 times out at 30 s | `run_profile.py --kit K --out O --reps 1 --budget 81 --only <3 missions>` + `summarize.py`; `--mode plain`; `unittest test_harness` | PASS WITH NOTES |
| 4 | 2026-11-12 | F-4.2 counterexample + MONOTONICITY Claims 1-2 | Priya | b6c94bb | admissible on [0,70], not on (70,420.464), admissible from 420.464; Claims 1 and 2 | `python3 F-4.2/counterexample.py` + hand proof check | PASS WITH NOTES |
| 5 | 2026-11-12 | F-4.2 static obstacle | Priya | b6c94bb | 8/15 packets have zero drawn ignitions; 14/15 routes untouched; uljin 1200Z FW2 has 5 touches before ignition, margin 2320.05 s | `.venv/bin/python F-4.2/static_obstacle.py` | PASS |
| 6 | 2026-11-12 | PR #103 data-fetch (re-check) | Daniel | ebc1a7f6 | max_acres wording and squash note; v2 rename; A1 time rule; make_input_manifest; AHI fetcher | fresh `rebuild_env.sh WS --project MT-BDF-006269_AlderCreek`; byte/diff checks | PASS WITH NOTES (squash merge only) |
| 7 | 2026-11-12 | W-KIT (checkpoint 3) | Thomas | e28c4aff | N1-N5 fixed; 19 tests; planner 384/384 | `cd planner && npx vitest run ../tests/planner/wkit.channels.test.ts && npx vitest run` | PASS WITH NOTES |
| 8 | 2026-11-12 | F-3.2 claim 9, departure-sweep cohort | Thomas | 560ad1a (checked at e28c4aff) | 140 requests, 75 ROUTE / 65 NO_ROUTE, both checkers accept all, sweep agrees 0 disagreements | `cohort.py --offsets 900 --c-checker checker_c/wfgc_check` + per-row compare | PASS WITH NOTES |
| 9 | 2026-11-12 | F-3.2 claim 10, P1 flame sets | Thomas | 421637f | 15 packets with hazard/raw/contact unions identical | `python3 F-3.2/p1_check.py` | PASS |
| 10 | 2026-11-12 | F-4.2 spatial clearance | Priya | 0e6f7db | 15 published clearances; trade-offs; 90 witnesses certified | `clearance_panel.py --only FW2,FN1,FX2`; `analyze_clearance.py`; `verify_witnesses.py`; own independent geometry on all 15 | PASS WITH NOTES |
| 11 | 2026-11-12 | W-KIT (N6/N7 fix) | Thomas | 01292ca | issue-by <= planner leave-by and field leave-by; latency order low >= median >= high | `cd planner && npx vitest run ../tests/planner/wkit.channels.test.ts && npx vitest run` + 10 probes | PASS |
| 12 | 2026-11-12 | PR #109 torch install line (merge-readiness point) | Daniel | 5f384555 | torch line installs CPU torch 2.5.1 from the PyTorch CPU index only | the script venv block in a fresh venv, cold uv cache | PASS |
| 13 | 2026-11-12 | P-PROTO P1-P4 (replay-only public page, not published) | Thomas | 477448d8 | P1 cards show time/hand-off only on leave_by, with stamp; P2 render order, same-origin; P3 contrast/CVD tokens; P4 built only with WFG_BUILD_PUBLIC_VIEW=1 | `cd planner && npx vitest run pproto && npx vitest run`; `npm run build:static` with and without the flag; own card scan + own P3 computation | PASS WITH NOTES |
| 14 | 2026-11-12 | W-KIT W5 (재난문자 class limits) | Thomas | 477448d8 | kit SMS and family text fit 90 chars and their class | `npx vitest run wkit` | PASS |
| 15 | 2026-11-12 | W-KIT W6 (draft-decree four-field check, issuer field) | Thomas | 66e3e62 | 0 decree passes without an issuer; with a synthetic issuer head 299 / voice 299 / family script 440 / family text 0; no agency invented | `npx vitest run wkit && npx vitest run` + probe with issuer over 531 | **FAIL** (issuer path only) |
| 16 | 2026-11-12 | F-3.2 claim 11, F-DYN envelope O2 | Thomas | 66e3e62 | float semantics equals HAZARD (0 diffs), 10/10 instances; exact gives 1293 diffs, 0/10 | Leo 7eb3691 pipeline (variants, regrid, build per MANIFEST_v3, instance) + `envelope_o2.py --mode float/exact` | PASS WITH NOTES |
| 17 | 2026-11-12 | PR #114 merge readiness (Priya verified subset) | Priya | dee56c7 | only verified F-3.4/F-4.2 work; harness identical to b6c94bb; † fix; 90 witnesses certified | diff checks + `verify_witnesses.py` on 12 more margin witnesses | PASS WITH NOTES |
| 18 | 2026-11-12 | PR #117 W-KIT merge readiness | Thomas | 656cab0 | tree = verified 477448d | per-file diff vs 477448d; standalone `npx vitest run`, `tsc -b` | PASS |
| 19 | 2026-11-12 | PR #118 P-PROTO merge readiness | Thomas | 1d3e49f | 477448d + N1 wording | per-file diff; standalone tests; default build:static | PASS |
| 20 | 2026-11-12 | PR #116 F-3.2 certificates merge readiness | Thomas | a03f218 | verified state + a03f218 notes; slices.py claims (never verified before) | diff vs 421637f; checker_c tests; `python3 F-3.2/slices.py` | **FAIL** (one README number) |
| 21 | 2026-11-12 | P-PROTO checkpoint 2 (P5-P7) | Thomas | 75189d9 | descriptive ladder + hedged stamps; untrusted URL places; 320 px Chromium layout | `npx vitest run pproto && npx vitest run` (own npm ci) + probes | PASS WITH NOTES |
| 22 | 2026-11-12 | PR #116 re-check (README slices sentence) | Thomas | ae5351a | 15 non-forced, 0.82-3.08×, median 1.42×, 6 >1.5 | diff vs a03f218; recompute from results/slices.json | PASS (ready) |
| 23 | 2026-11-12 | PR #118 re-check (test-only CI wait) | Thomas | 53233ab | test wait raised to 90 s, fails early on .pv-error | diff vs 1d3e49f; pproto + full suite (own npm ci) | PASS (ready) |
| 24 | 2026-11-12 | PR #122 scope check (research-scout docs) | Sofia | f912de9 | docs only, no private link, no attribution footer | diff scan (files, URL hosts, private hosts/paths/emails, personal data) + PR description | NOT READY (description footer) |

## Notes

**1. PR #103 @ 7d43080** (= refs/pull/103/head)
- Ran `fetch.py get toa_kriging_choi2026 toa_kriging_choi2026_readme kfs_fire_status_history firms_modis_2025_korea nirops_code`: all sha256 ok, md5 ok where given. Committed small/kfs and small/firms Korea CSVs match the resources.json sha256 and size.
- Ran `rebuild_env.sh WS --project MT-BDF-006269_AlderCreek`: weather rc=1 (Open-Meteo daily limit, known), canopy rc=1 (GLAD host, known); inventory, boundary_layer, terrain, gridmet, landfire, landcover, biome and enrich-data rc=0.
- Largest blob in branch history is 1.26 MB; data-fetch/ is 4.9 MB. Licences: CC-BY-4.0, public domain, NASA FIRMS open, data.go.kr unrestricted. No secrets or PII found by grep; the KFS addresses go down to 읍/면 level only.
- Repo tests: not run. The diff is confined to research/harness-2026-11/data-fetch/, which has no test files and no pytest config (established by diff inspection).
- **nirops_incidents.csv is committed.** max_acres is removed at HEAD (259ef5b) but still present in 0cf3995 and 3129ad5. Merge only by squash, or rewrite the branch first. MANIFEST.md:39 still says "maximum acres" (stale).
- For Iris: nirops_incidents.csv still carries surveys, first/last_utc and days for all incidents (proxies for size). feds_overlap.csv has feds_final_area_km2 for the 6 held-out 2024 fires.

**2. W-KIT @ 6ac1bc62**: reproduced 13/13 and 378/378. The 531/0 and 600/18 numbers are asserted in the test. A scratch probe test (not committed) found no unresolved-as-safe, transport-promise or unsupplied-order wording, and no resident data.
- N1 issueOrderByText renders any offsetS on leave_by (1860 > leaveBy 1800, -600, 99999 beyond horizon) without a violation.
- N2 Midnight crossing renders "00:15 / 밤 12시 15분" with no date marker.
- N3 The destination-swap assertion is vacuous (`if (other?.name)`, fixture's second destination has no name). The check itself works when injected.
- N4 The pythonEucKr oracle silently skips when python is absent (it ran here).
- N5 Withholding is not enforced by any consumer yet (not wired into the UI or CSV).

**3. F-3.4 @ b6c94bb**: fresh runs (phase, 81 s): FX1 arrival 3119, 24.66 s wall, radiation 77.6%; FX2 arrival 2540, 11.21 s, radiation 15.2%; FD1 arrival 531, 13.05 s, radiation 95.4%. Start-up median 0.157 s; 3/3 executions ≥95% attributed. Plain mode gives the same arrivals and statuses. Yeongdeok FX2 at 81 s: TIMEOUT/UNRESOLVED, search 72.1 of 81.2 s. summarize.py on the committed 60-run rows reproduces the table (0.8%, 0.1%, 38.1% search, 31.3% radiation, 59/60). unittest 3/3. Published routes for FX1, FX2 and FD1 match the fresh runs' edges.
- N1 Claim (e) does not reproduce here: at a 30 s budget FX1 completes in 24.26 s on this host (theirs takes 32-33 s). It is host-specific.
- N2 The speed-equivalence factor is host-specific (2.7× theirs, ≈2.0× here).
- N3 Uiseong FX2 admission+models was 4.15 s here against their ≈5 s.
- The full 60 executions were not re-run.

**4. F-4.2 counterexample @ b6c94bb**: script rc=0. T matches cell_duration_s of the 120 frozen exports. Hand derivation of the dose: 130+δ (δ≤110), then 240, then 620.464−δ. Claims 1 and 2 proofs checked.
- N4 The closed-form contact margin is valid only when ≤ T.
- N5 The status line is stale ("awaiting Hannah").
- N6 The panel figures (dose ≤ 0.33 of budget, peak ≤ 0.0005) were not verified.

**5. F-4.2 static obstacle @ b6c94bb**: exact reproduction in 24.8 s. 3 of the 15 routes were regenerated independently and match. The other 12 were not regenerated, and the clearance.py geometry was not re-implemented.

**6. PR #103 @ ebc1a7f6**:
- nirops_incidents_v2.csv is byte-identical to the 259ef5b version, with no max_acres. The A1 rule (floor or ceil to the hour) checked on 3 pilots. The AHI fetcher is keyless. The largest new blob is 25 KB.
- Fresh-venv rebuild: all stages rc=0 except boundary_layer (Open-Meteo 429, known) and canopy (GLAD, known). input_manifest pins 77 files. numpy is 1.26.4.
- Note: the torch line installs torch 2.5.1+cu124 plus 2.7 GB of nvidia wheels, because uv gives --extra-index-url (PyPI) priority over --index-url.
- Not run: `--nirops` mode (1.39 GB download).
- Squash merge keeps max_acres out of Main, but refs/pull/103/head keeps 0cf3995/3129ad5 fetchable.

**7. W-KIT @ e28c4aff**: 19/19 and 384/384. N2-N5 confirmed by probe. The staff noOrder is shown only for an attributed, unexpired not_issued status.
- N6: the issue-by bound uses the field's leaveByS, not the planner's. A field leaveBy of 3000 on a planner leave_by of 1800 renders issue-by 18:40-18:50, after the residents' 18:30, with 0 violations.
- N7: low <= median <= high is not checked.

**8. Cohort (claim 9)**: the offset-900 subset matches the committed JSON on 20/20 rows (claim, T, sweep, arrival, py, c, at-issue). The committed JSON has 140 rows, 140 ACCEPT/ACCEPT, 0 mismatches.
- Bit-flip tampering: ROUTE certificate rejected 25/25. NO_ROUTE certificate rejected 23/25; the 2 accepted flips change edge endpoints in the embedded instance, because the checkers do not bind the instance to the request.
- cohort.py does not run O2, so I ran derive_instance.compare on all 120 non-frozen departures: 0 differences.
- The full 140-row run was not repeated.

**9. P1 (claim 10)**: 15/15 packets 0/0/0. Own 30 single-member flag flips: the union changed in 19 cases and all 19 were detected.

**10. F-4.2 clearance @ 0e6f7db**:
- Panel run on FW2/FN1/FX2: r* 179.9/592.1/111.5. Trade-offs FW2 411.9 m @ +19 s and FN1 832.8 m @ +148 s. Witnesses 15/15 exact_ok and CERTIFIED_ADMISSIBLE.
- Own segment-rectangle code reproduces all 15 published clearances to 0.1 m; limiting sources active.
- best_radius reviewed: the upper bound is sound when blocks are up-sets before D (τ_max 258 s < T-H; † rule D > R_max exact), up to PAD_M 1e-6 m.
- Notes: horizon columns for uiseong 0324 / uljin 1200 need † (R_max < H). The Yeongdeok FW1 bracket is written with lower above upper.
- Not verified: the other 12 missions' searches and the other 75 witnesses.

**11. W-KIT @ 01292ca**: 19/19 and 384/384. The 10 probes on planner leave-by 1800:
- field 3000 {3000,2700,2400} gives out of range; {1800,1500,1200} is rendered;
- field 1200 gives "disagrees";
- the reversed order {900,1200,1500} is refused;
- 1801 gives out of range, as does field 3601 > H;
- all-negative values give "already past".
No time is ever rendered after the planner's leave-by. N7 example withdrawn: issue_by = leave_by - latency, so the original order was correct.

**Amendment to 10 (F-4.2)**: N1 is withdrawn. The horizon deadline is D = H - dwell = 3480 s, which is below R_max for uiseong 0324 (3495.3) and uljin 1200 (3595.4). Present-fire standing blocks are [0, R), so an earlier dwell is never worse. The remaining note: in the RESULTS.md §2 hand table, the uljin FD1 "≤ +600" cell carries a † that belongs to the horizon entry (results/TABLE.md is correct).

**12. PR #109 @ 5f384555 (torch line only)**: download.pytorch.org is reachable from this container.
- Ran the venv block with a cold cache: base pins rc=0 in 47 s; torch rc=0 in 12 s.
- Installed torch 2.5.1+cpu (cuda None) with 0 nvidia packages. The venv is 1.1 GB (torch 669 MB), against 5.4 GB before.
- numpy is 1.26.4. torch's dependencies resolve from the CPU index alone, and `uv pip check` reports 34 packages compatible.
- wildfire.survival and wildfire.rollout import.
- The rest of #109 was not verified here (Hannah's PASS).

**13. P-PROTO @ 477448d8**:
- pproto 10/10, planner 395/395.
- P4: the default build:static gives 0 public-view files ([check] OK); the WFG_BUILD_PUBLIC_VIEW=1 build adds public-view.html and the publicView chunks; planner-pages.yml does not set the flag.
- P1, own scan of 1,131 cards: non-leave_by cards show 0 times or hand-offs; every leave_by card carries the stamp; no "minutes old"; the GPX carries REPLAY. The 98 forbidden-word hits are all in synthetic place names (0 after masking, 0 real).
- P2: no external URL or geo: in the built page; the jsdom render was not re-run by me.
- P3, own WCAG/Machado/CIE76 computation: text ≥ 11.9:1; accents ≥ 8.66:1; min ΔE 20.4 (tritan, light); hues blue/vermilion/grey; dataAge 40 px = time 40 px.
- N1: the dataAge line shows the replay input clock time on every card. This is intended, and RESULTS should state it.

**14. W5 @ 477448d8**: wkit 20/20. ko familyText max 51 characters (≤ 90).

**15. W6 @ 66e3e62 — FAIL**:
- wkit 23/23 and planner 398/398 reproduce, and the literal claims hold. But with any supplied issuer, all 531 real channel sets fail checkChannels, so every output is withheld:
  - the issuer is not masked, so the test's own "합성군 재난안전과" trips forbidden 안전 in ko head, voice and family script (531 each), and "…구조대" trips 구조;
  - the contact line pushes the ko head full script over 35 s in 316-317 sets;
  - the Korean agency name is appended to the en familyText, which is then not GSM-7 (531).
- The 299/299/440 "passes" count field presence on outputs that are withheld anyway.
- The default path (no issuer) is unaffected. The last W-KIT PASS is 477448d8 (W5).

**16. Claim 11 @ 66e3e62**: the full pipeline was rebuilt from Leo 7eb3691 (graph 56,369 nodes; packet 1,655 ignitions / 97 present cells).
- float mode: differing_cells 820 (not 0 as messaged), all identical starts with |Δend| ≤ 1.36e-12 s in both directions; integer instances 10/10 equal.
- exact mode: 1293 differences (482 start, 309 end at 300 s, 502 sub-µs); 0/10 equal.
- Both modes match the committed results JSON.
- Notes: the classifier only accepts the "HAZARD later" direction, which misfiles the 723 ulp-earlier ends; the message's "0 differences" is wrong; the exact sub-counts overlap, so they should be given as disjoint counts.

**17. PR #114 @ dee56c7**:
- 42 new files, all under F-3.4/ and F-4.2/; the largest blob is 266 KB.
- The harness diff against b6c94bb is empty. F-4.2 code is identical to 0e6f7db; RESULTS.md carries only the agreed fixes; 3 unverified scripts were removed.
- VERIFY.jsonl has 90 rows (75 margin + 15 published), all CERTIFIED_ADMISSIBLE. 12 more margin witnesses were re-run (one per remaining mission, including the FW1 1781 m, FX1 680 m and Uiseong FW1 1531 m trade-offs): 12/12 certified and exact_ok. 27/90 have now been re-run in total.
- The description matches the ledger; "1 mm" holds (max 0.0004 m).
- Notes: fixed_route_check.py is included but was never seen or run (not used by RESULTS). TABLE.md keeps the verified analyze_clearance's "≥6000 (cap)" wording.

**Amendment to 17 (PR #114)**: the fixed_route_check.py note is withdrawn. verify_witnesses.py:115 runs it as a subprocess for every witness, so all 27 independent re-runs exercised it. It is unchanged since 0e6f7db and imports the kit's HybridChecker without re-implementation. The only remaining note is cosmetic (TABLE.md cap wording, stated in the PR description). The only content in #114 not verified by me is results/extended_b300_1rep, which is listed as not verified.

**18-20. Thomas's frozen PRs**:
- #117: every file byte-identical to 477448d. Standalone on Main: 385/385, tsc OK.
- #118: only the N1 RESULTS wording changed. Standalone 375/375. The default static build has 0 public-view files.
- #116:
  - c207c1e equals 421637f minus unknown_support.py. a03f218 (o2_diffs, binding caveat, docstring) is correct. checker_c tests: 30+2 pass.
  - slices.py regenerates slices.json identically (20 rows). Full 33.5-2,857.8 KB; A (ROUTE) 4.54-57.36 KB; 5 forced COCERT ≈0.1 KB.
  - The README claim "best slice + certificate ≈0.5-1.5× full" is WRONG: the data gives 0.82-3.08× on the 15 non-forced rows, 6 above 1.5 (max: miryang FN1 3.08, uljin FX1 3.03). Slice-only gives 0.33-1.29, cert-only 0.24-0.99.
  - Ready after a one-line correction.

**Addendum to 18-20 (orchestrator relay)**: all planner suites ran with real `npm ci` node_modules (not symlinked).
- #117: diff = 4 files (channels/build.ts, wkit test, W-KIT DESIGN/RESULTS), with no W6 traces.
- #118: no workflow in the tree sets WFG_BUILD_PUBLIC_VIEW.
- #116: no envelope_o2/tier_r/fdyn files. The slices README has a second error: there are 15 non-forced rows (10 ROUTE + 5 NO_ROUTE), not 10.
- The "legality cheap (≤ 57 KB), optimality ~1-3× full" reading is supported by the data.

**21. P-PROTO cp2 @ 75189d9**:
- pproto 17/17 (the layout test ran in Chromium, 4 cases); planner 405/405.
- P6: parseLink requires an exact entryPaths match plus validPlace origin membership.
- P5: stamps are hedged on all 1,131 cards.
- N1: when after === 'gap', the card says "none after" although a later departure had a checked road (53 synthetic, 0 real). A false description; the wording needs fixing.
- N2: the base commit 0a63683 carries the FAILED W6 decree code, so the follow-up PR must contain only the P-PROTO files.

**22-23.**
- #116 ae5351a: the sentence matches the data exactly. best_optimality_total includes the Merkle estimate and is not the quantity; min(slice+cert) is. 11/15 > 1.0.
- #118 53233ab: tests-only diff; a timeout still fails (cards.length === 3); 10/10 and 375/375.
- Thomas's frozen PRs #116, #117 and #118 are all ready from the verifier's side.

**Status note (11:12)**: the user merged #117 @ 656cab0 and #118 @ 1d3e49f (both PASS heads). 53233ab (test-only, PASS as entry 23) is not in Main; it moves to Clara's P-PROTO follow-up cut. #116 @ ae5351a is PASS and ready. Planner-side work (P-PROTO follow-up, W6 fix, deadline provenance) moves from Thomas to Clara (session_017vgyRQa6PpBJqNz8Cpwxf8). Last PASS states: W-KIT 656cab0 = 477448d (in Main); P-PROTO cp2 75189d9 PASS WITH NOTES (open notes N1 gap wording, N2 scope).

**24. PR #122 @ f912de9**:
- Diff is clean: 2 docs files (LOG.md, MISSION_A.md); every URL is a public journal, arXiv, government or news site; no private hosts, paths, emails or keys; mentions of people are aggregate only.
- The PR description still carries the "Generated by Claude Code" footer with a private session link. It is Sofia's PR, so I did not edit it.
- Ready once the footer is removed.
