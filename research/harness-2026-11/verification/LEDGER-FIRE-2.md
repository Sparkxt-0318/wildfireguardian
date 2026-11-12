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
| 24 | 2026-11-12 | PR #122 scope check (research-scout docs) | Sofia | f912de9 | docs only, no private link, no attribution footer | diff scan (files, URL hosts, private hosts/paths/emails, personal data) + PR description | NOT READY (description footer) → READY after footer removal (same head) |
| 25 | 2026-11-12 | FIRE 6.2 radiant screen (parts 1 and 3) | Priya | 79f3271 | 1-hour flux bounds < 1.0 so ceilings change nothing; C-11 view factor; standoffs and route counts | `python3 F-4.2/standoff.py` + own numeric integration and bisection | PASS WITH NOTES |
| 26 | 2026-11-12 | FIRE 6.2 radiant 4a (time inside standoff, fractional dose) | Priya | 12c32af | per-route seconds q>=1, stationary, FD ranges; worst routes FX2/FW2/Hongseong FW2 | `standoff_route.py --part 4a` + own independent recomputation (FX2, FW2) | PASS WITH NOTES |
| 27 | 2026-11-12 | P-PROTO follow-up (port of cp2 + gap wording) | Clara | b3df2a3 | only 6 P-PROTO files on Main; 90 s wait in mount(); 3-way leave-by sentence with sweep property test; 403/403; default build no public-view | fresh `npm ci`; `npx vitest run`; mutation (old 2-way mapping); `npm run build:static` | PASS |
| 28 | 2026-11-12 | FIRE 6.2 radiant 5a (dwell / wait / moving split) | Priya | 49a50b3 | stationary split into dwell and wait; destination inside standoff during stay | `standoff_route.py --part 4a`; cross-check vs own 4a run | PASS WITH NOTE |
| 29 | 2026-11-12 | FIRE 6.2 radiant §6 (literature flame set) | Priya | eda51f2 | reproduces Sofia's standoffs; route-count ranges W100/W3750 × window | `python3 F-4.2/standoff_lit.py` + own code | PASS |
| 30 | 2026-11-12 | W-KIT W6 redo (issuer report-only) | Clara | e69c3d1 | four FAIL points fixed; complete-and-not-withheld 0/0/0/0 → 299/299/0/440; withheld 2,124 → 0 | fresh `npm ci`; `-t W6`; full suite; build:static; own issuer probe (4 issuers × 531) | PASS WITH NOTES |
| 31 | 2026-11-12 | PR #123 scope check (research-scout batch 5) | Sofia | bab9148 | docs only, no private link, no footer | diff vs base a1ce97f + body | READY |
| 32 | 2026-11-12 | FIRE 6.2 radiant §7 (surface vs crown table; distance counts) | Priya | e33256b | 7a standoffs and counts; 7b 4/9/12 clearance, 3/5/7 stationary, FX2 643 s within 1 km | `radiant_s7.py` + own bisection + own per-second distance code | PASS WITH NOTE |
| 33 | 2026-11-12 | F-3.2 W2 envelope O2 classifier (fire-next) | Thomas | b2d9eba (07d4a58) | float: 820 end-only ≤1.36e-12 s (97/723), 0 other, 10/10 | `envelope_o2.py --mode float` on own v3 packet (Leo 7eb3691) | PASS |
| 34 | 2026-11-12 | F-3.2 W3 v3.1 acceptance, samples a/b/c | Thomas | 45a8975 | integer equality 0 mismatches; boundary 102/17, 102 (b), 482/309; 10/10 instances each | own packets at Leo f40e2af (MANIFEST_v3_1 cmds); `--mode v31` (+ `--law scalar` for b); negative control | PASS |
| 35 | 2026-11-12 | PR #127 scope check (research-scout batch 6) | Sofia | 43e418b | docs only, no private link, no footer | diff + body | READY |
| 36 | 2026-11-12 | P-PROTO next cut (step-aware sentences, one-trip, not-in-model) | Clara | 33f672d | 6 files on Main 4e2d150; exclusive/exhaustive sentence property; 403/403; 0 public-view in default dist | fresh npm ci; full suite; -t leave-by; build:static; probes (step, window_closed ≤ T); mutation none_checked→horizon | PASS |
| 37 | 2026-11-12 | F-3.2 W4: Tier R all events + F-DYN certificate batch | Thomas | b2d9eba | Tier R 20/20 identical, tier_r.json byte-identical, 80/80 accepted; F-DYN 3 packets / 528 rows py = c = claim/T, 0 diffs, all 69 NORUN rows ACCEPT by both | own rerun (Choi TOA, FIRMS 2022/23/25; packets rebuilt from MANIFEST_v3 at Leo 7eb3691) | PASS WITH NOTES |
| 38 | 2026-11-12 | F-3.2 W5: Tier R FIRMS-coverage guard | Thomas | cc850f5 (at 25597ac) | 10/10; 3 mutations caught; labels equal the old ones whenever covered; all 4 events covered on all-events data; 2025-only refuses KFS_02/05/11 | tests + mutation + real-data coverage + synthetic wrong-region file | PASS WITH NOTES |
| 39 | 2026-11-12 | sipp acceptance-window regression test (W6R) | Thomas | 25597ac | 6/6 on identity-checked inputs, 6 skip without data; my widening mutation reproduces naive 968/1032/573/1400/776 and FD1 2921; sipp suite 98 passed | pytest + own mutation script | PASS WITH NOTES |
| 40 | 2026-11-12 | PR #128 CI fetch step | Thomas | a8e945c | 1 file +2: one step in next-tracks before SIPP suites; SHA-256 pinned, per-file identity, unsafe members refused; fresh fetch 132 files 1.2 s; junk archive refused, nothing extracted | diff + fresh run + negative control | READY |
| 41 | 2026-11-12 | PR #130 scope check (research-scout batch 7) | Sofia | 712aaadd | docs only, public citations, no private link, no footer | diff + body | READY WITH NOTES |
| 42 | 2026-11-12 | W-KIT W6 single checkpoint | Clara | 344657e | issuer guard passes 18/21 ko + 11/15 en instruction-shaped names, shown in 531/531 real drill sets with 0 violations; all else reproduces (1,131 sets), 415/415 | own adversarial names + e2e probe + independent property probes | FAIL |
| 43 | 2026-11-12 | STAFF-HEADLINE (Iris E) | Clara | b45a94b | own sweep oracle = headline = kit = card in 1,131/1,131; changed syn 131 = 53 gap + 78 first-not-checked; 405/405; static smoke 119/119 | fresh npm ci, oracle, test-diff review, smoke | PASS WITH NOTES |
| 44 | 2026-11-12 | Tier R guard notes delta | Thomas | c11eccd0 | 11/11; US file refused; real coverage unchanged; Fukuoka-only file still covers KFS_02 | tests + synthetic probes | PASS WITH NOTES |
| 45 | 2026-11-12 | F-3.4 REQUEST 8 clean 1-hour profile | Priya | db2c516 | (a)-(e) reproduce from rows; radiation 30.9% by raw timers; search 38.1% stage basis vs 39.9% timers; fresh warm spot hit=True | summarize.py + own recomputation + fresh kit spot run | PASS WITH NOTES |
| 46 | 2026-11-12 | F-3.4 REQUEST 9 option B negative | Priya | db2c516 | snap10 20/20 +8.3%, snap6 19/20 +5.6% from rows; fresh Uljin FX1 3119 both, +22% wall; ADAPTIVE reason not reproduced (wall cap, host-dependent) | own recomputation + fresh base/snap10 runs | PASS WITH NOTES |
| 47 | 2026-11-12 | PR #130 re-check (N1/N2 fixes) | Sofia | 31e8acf | quick check labelled unverified, not a back-test; its numbers reproduce (4-corner VF: 15.0/5.2/2.5 at E 76; 23.3/8.0/3.9 at E 118); log and body agree | diff + own VF | READY |
| 48 | 2026-11-12 | F-3.2 W7 firms_early on v3.1 | Thomas | f5aef10 | own v3.1 build of Yeongdeok 0325T19: 180/180 py = c = claim/T, O2 0, 0 diffs vs his v3.1 and v3; arrays byte-identical to v3, only identity fields differ; his 864 all match v3 | own rebuild (Leo f40e2af) + fresh C checker + packet diff | PASS |
| 49 | 2026-11-12 | W-KIT W6 registry-only issuer | Clara | 9695e26 | 105 adversarial names (mine + registry-name prefix/suffix, ZWSP/ZWJ/NBSP, NFD, look-alike, U+2028) x drill flag x 2 places: 0 non-registry contact lines or numbers; 419/419; build:static OK | own probe with default registry | PASS WITH NOTES |
| 50 | 2026-11-12 | PROV-FLAGS deadline provenance (staff only) | Clara | 79ad132 | split_provenance byte-identical, tampered source refused; own join 473/7/21 + 10 proven-no-route + 9 + 11; cross-cache 0/30 accepted; 415/415; static smoke 119/119 | fresh npm ci, own join probe, cross-file + tamper + bad-kind probes, smoke | PASS WITH NOTES |
| 51 | 2026-11-12 | Tier R coverage = packet grid + tier_r.json regenerated | Thomas | d4564b38 | 12/12; Fukuoka/US files cover no event under packet bboxes; regenerated tier_r.json equals my b2d9eba reproduction in all 20 x 4 tiers | tests + real bboxes + JSON diff | PASS |
| 52 | 2026-11-12 | Pre-cut sign-off (a) coreachable sentinel skip | Thomas | d4564b38 | preds(E)=0 and never enqueued on all 20; same output with/without skip; forced origin-accept: no-skip IndexError, skip gives cert+cocert ACCEPT by both | structural check + forced case | SIGN-OFF |
| 53 | 2026-11-12 | Pre-cut sign-off (b) derive_instance.compare_semantic | Thomas | d4564b38 | 7 mutations behave exactly at legal boundaries (H-D_j, H) | mutation tests | SIGN-OFF WITH NOTE |
| 54 | 2026-11-12 | Pre-cut sign-off (c) unknown_support Augmented + certify_and_check | Thomas | d4564b38 | Augmented(empty) == base; with Tier A extras == hand-merged on 3 missions; 80/80 checker outputs match claim/T | equivalence tests | SIGN-OFF WITH NOTE |
| 55 | 2026-11-12 | Pre-cut sign-off (d) envelope_o2_exact.json | Thomas | d4564b38 | own rerun: 1,293 = 502 sub-us + 791 quantum; 0/10 instances equal (negative result) | own rerun at Leo 7eb3691 | SIGN-OFF WITH NOTE |
| 56 | 2026-11-12 | W-KIT W6 registry delta (시·군 keying, phone shape, no override) | Clara | 1334e47 | 81 names x 17 numbers x 3 en on 2 real places: 0 contact lines for any non-ok status; only 4 registry names render (as registry NFC string); time/date numbers refused; 424/424 | own probe + grep | PASS |
| 57 | 2026-11-12 | PROV-FLAGS delta (fail-closed parse, help sentence, CSV kind only, Sofia wording) | Clara | a79c515 | 10 malformed-record probes fail closed, no throw; bad files refused; no code outside model.ts reads later values; counts unchanged; cross 0/30; 417/417 | own probes + grep | PASS |
| 58 | 2026-11-12 | W-KIT W6 follow-up (mobile refused, override removed) | Clara | 7de2050 | 010/011/016-019 refused, landlines and 1XXX kept; no override under src (vi.mock in the test only); 424/424 | own prefix probe + grep | PASS |
| 59 | 2026-11-12 | PR #141 routing cut, frozen-cut check | Thomas | 0685e03 (f821a43) | 18 paths vs Main; F-3.2 equal to fire-next cedf961 except README + 2 exclusions; cedf961 fixes verified (CLOCK diff, exact ACCEPT rule 80/80 unchanged, envelope JSON keys only); C 30+2, guard 12/12, regression 6/6, router 105/105 | fresh worktree, diffs, probes | PASS |
| 60 | 2026-11-12 | Kit staff provenance line | Clara | 4e65e55 | every kind forced on 1,131 places: resident outputs and other staff fields byte-identical, no clock time, no throw; violations unchanged on deadline places; 447/447 | own probe | PASS WITH NOTES |
| 61 | 2026-11-12 | Kit provenance line N1 guard | Clara | 92c2e51 | timed kinds on no-time places: 0 lines in 1,020 forced cases; present on all 2,373 leave_by cases; violations and other outputs unchanged; 448/448 | own forced-kind probe | PASS |
| 62 | 2026-11-12 | Kit provenance line: mismatch refused and reported | Clara | 60deae8 | 1,020/1,020 forced timed-on-no-time cases give the not-established line in ko and en, no deadline wording or clock time; violations and other outputs unchanged; 448/448 | own forced-kind probe | PASS |
| 63 | 2026-11-12 | W-KIT phone-shape allowlist tidy | Clara | ccbee1a | 35-number probe as intended; all-zero placeholder renders only for drill/replay issuers; 446/446 | own probe | PASS |
| 64 | 2026-11-12 | PR #144 scope check (research-scout batch 8/8b) | Sofia | b750fa7 | docs only (LOG.md +76); no phone numbers, no private links, no personal data; suggestion labelled; no footer | diff + body | READY |
| 65 | 2026-11-12 | envelope_burnset P1 (Thomas's flag; independent check) | Leo (via Thomas) | 4463892 | Uiseong 0323T01 h5: HAZARD 16,176 cells on [0,18000) vs ContactModel 15,781 cells, 0 full, ending at about 4,270 s (or 3,792 s for present fire); 395 cells missing; ContactModel == raw-array T/R law | own build from MANIFEST_v3_3 + p1_check | P1 FAIL CONFIRMED |
| 66 | 2026-11-12 | F-3.4 REQUEST 10 F-DYN multi-hour profile | Priya | 73f29a7 | (1)-(4) reproduce from rows + STAGES; RSS gates confirmed in kit code (road_core.py:752-757, hybrid_checker.py:9/_finish), process-lifetime ru_maxrss vs 3,072 MiB | read rows/STAGES + fresh kit build | PASS WITH NOTES |
| 67 | 2026-11-12 | Envelope impact statement + erratum PR #145 | Thomas | ca4fbfa | merged envelope_o2.py never reads ContactModel/constructed_arrays; own X1 on v3 Yeongdeok 0325T11 envelope: 863 identical / 95 end<1us / 794 other (cell 1040 [5100,18000) vs [5100,9370.46)); certified kriged_mean control 0 other | grep + own X1 | CONFIRMED; #145 READY after one wording fix |
| 68 | 2026-11-12 | Erratum PR #145 wording fix | Thomas | 5a2c628 | README only; header limits my confirmation to the v3 Yeongdeok packet; nothing else changed | diff | READY |
| 69 | 2026-11-12 | P-PROTO jsdom test under the Pages base path | Clara | 2b594dc | old test with /wildfireguardian/: 4 failed in 274 s (base '': 14/14); new: 14/14 in about 5 s under '', '/wildfireguardian/', './'; fail-fast mutation fires; workflow env 446/446, build OK; no assertion changed | reproduce before/after + mutation | PASS |
| 70 | 2026-11-12 | F-3.4 REQUEST 11 F-DYN A3(a)/(b) | Priya | 7e88cfc | plan before runs; (a) 4/4 CERTIFIED_ADMISSIBLE + 4/4 independent ok, checker hashes = fresh unmodified kit; (b) 5/9 Yeongdeok proven, Uiseong 0/4; non-adoption of the pre-registered reading supported by A1 rows (same LO finished, only the checker gate failed) | rows/STAGES/hashes + fresh kit | PASS WITH NOTES |
| 71 | 2026-11-12 | Phone tidy + symmetric provenance guard | Clara | 2776a4f | phone allowlist identical to ccbee1a; unresolved_proven_no_route kept only on unresolved (178), reported not established on leave_by 791 / no_route 84 / partial 78; violations unchanged; guard removal caught; 449/449 | own forced probe + mutation | PASS |
| 72 | 2026-11-12 | P-PROTO empty public page (one no-data line) | Clara | eccec7f | 18/18; mutation (old PublicView) fails all 4 new tests; 453/453; build OK; 0 public-view files and no no-data strings in dist; wording regexes pass the shipped ko/en and catch the earlier draft | fresh npm ci, mutation, dist grep, independent regex check | PASS |
| 73 | 2026-11-12 | PR #151 raw-array guard | Thomas | 53fab56 | own v3.4 envelope packet (marker set, all births NaN): from_raw, tier_r.native_masks, unknown_support.masks raise; ContactModel raises on NaN; v3/v3.1/panel packets accepted; no other F-3.2 array reader; tests OK; panel P1 file byte-identical | own build at Leo faa89c4 + grep + tests | PASS |
| 74 | 2026-11-12 | v3.4 HAZARD.json host dependence (orchestrator question) | Leo (build.py) | faa89c4 | same packet built from two checkout paths: arrays byte-identical; HAZARD differs only in /provenance/identity/radiation_operator/module (absolute path); manifest pins no HAZARD sha | own two-path rebuild + structural diff | FINDING (reproducibility) |
| 75 | 2026-11-12 | W-KIT owner decisions (no English call without an English shelter name; 영덕군 registered, secondary) | Clara | 634f02d | en.voice null iff Korean-only shelter (373/531 real, 91/600 syn, 0 mismatches); 667 remaining en calls clean; 영덕 273/273 gain ko contact, no en contact, violations unchanged; both mutations caught; 450/450; tsc clean | own probes + mutations | PASS WITH NOTES |
| 76 | 2026-11-12 | W-KIT owner-decision delta: staff wording for the dropped English call, staffSummary (Iris, Sofia) | Clara | 08560db | own before/after dump vs Main 994abd7 (every resident output + violations, issuer, 531 real + 600 syn): 373 real / 91 syn differ only in en.voice (interim sentence → null), 158 / 509 identical, violations identical; on all 464 dropped places d.ko is in en head and en familyScript, never in en familyText (no Hangul at all there); ko.voice non-null at all 1,131; staffSummary 373 of 531 (real), 91 of 600 (syn); mutations: old 'owner decision' wording → 1 fail; Korean call dropped too → 5 fails | wkit.channels 50/50; npm test (workflow env) 26 files / 450; tsc -b clean; build:static OK | PASS WITH NOTES (see 76) |
| 77 | 2026-11-12 | W-KIT owner-decision cut, final head (634f02d + 08560db + e519275 + 368da46) | Clara | 368da46 | delta 08560db..368da46: two Korean staff strings (NO_EN_CALL_REPORT.ko, staffSummary ko) + ko summary pinned exactly; RESULTS records the issuer-jurisdiction limitation (row 75 N1) accurately; no logic change, so the row-76 before/after dump stands (only staff strings differ) | npm test (workflow env) 26 files / 450; tsc -b clean; build:static OK | PASS WITH NOTES (see 77) |
| 78 | 2026-11-12 | W-KIT owner-decision cut, FINAL head (634f02d + 08560db + e519275 + 368da46 + 13abf62) | Clara | 13abf62 | delta 368da46..13abf62: N1 direct test (ko.voice at all 464 dropped places non-null and byte-equal to the build with an English shelter name added); N2 'owner decision' gone from code comments and registry source (only the comment explaining why the phrase is avoided remains); N3 single separator. Own mutations: ko.voice altered by one space at dropped places only → the new test fails (1/50); Korean staff double dash restored → 1/50 fails. Resident outputs unchanged since row 76 (only comments, a staff separator and tests changed) | npm test (workflow env) 26 files / 450; tsc -b clean; build:static OK | PASS WITH NOTES (N4 only, optional wording; see 77) |
| 79 | 2026-11-12 | W-KIT owner-decision cut, FROZEN head (… + 13abf62 + 7034fb8) | Clara | 7034fb8 | delta 13abf62..7034fb8: N4 only, two staff strings ('주민용 영어 자료', 'in English resident materials') + RESULTS line; no logic or test change; row-78 checks (N1–N3 mutations) carry over | npm test (workflow env) 26 files / 450; tsc -b clean; build:static OK | PASS (supersedes 78 as the frozen head; N1–N4 closed; row-75 jurisdiction limitation documented, fix deferred) |
| 80 | 2026-11-12 | SUPPORT-OUTCOME fail-closed reader (supportGate; decision (c)) | Clara | 8efdebb (base Main 6babc5e, not 994abd7) | own probes: (A) masked travel-only route check → verdict unresolved, arrival/geometry null, BUT fullPolicy.pass=true, exposure contact=false ×2, withinBudget, dwellEndS kept; RightPanel TravelOnly renders 'Full-policy re-assessment: pass/통과' and per-member 'no contact' for any verdict; (B) panel/timeline use components/format.ts reasonText (i18n), not shared reasonText: shows bare 'UNKNOWN_SUPPORT_NOT_EVALUATED@ab12cd34' / 'WRITER_IDENTITY_MISSING', no label (no reason.* i18n keys); (C) Leo's real identity layout (packet_writer_sha256 sibling of support_writer) → WRITER_IDENTITY_MISSING; nested under identity → null (not masked); (D) non-null non-object support (true, string, array) or support_writer string → null (not masked), contradicting claim 1 'non-null support'; lowercase marker ignored. Gate: own dumps vs 6babc5e byte-identical (6 caches cacheToModel incl. route/travelOnly + reason texts via 3 formatters, 7,401,796 B; kit 1,131 places, 3,344,279 B) | npm test (workflow env) 27 files / 462; tsc -b clean; build:static OK | FAIL (see 80) |
| 81 | 2026-11-12 | SUPPORT-OUTCOME reader, Korean-only delta (Sofia) | Clara | 866f2ad | delta 8efdebb..866f2ad: three ko labels + ko writer suffix in shared/strings.ts, test pins; planner/src/api and components unchanged (git diff), so row-80 FAIL 1/2 and N1–N3 reproduce unchanged | supportGate.test 8/8 | FAIL stands (see 80); Korean wording itself fine |
| 82 | 2026-11-12 | SUPPORT-OUTCOME reader, fixes for row 80 (+ Sofia's Korean 866f2ad) | Clara | 7383cb5 (base 6babc5e) | row-80 repro now: gated travel-only → exposure [], fullPolicy null, withinBudget/dwellEndS/arrival/lb/geometry null; also gated via job.provenance.identity only. Non-object support (true, string, [], 0, '') → masked (WRITER_IDENTITY_MISSING); false/null → unmasked. Leo's identity: flat, {identity}, 3-deep → UNKNOWN_SUPPORT_NOT_EVALUATED@ab12cd34; frozen identity (no support_writer) → unmasked. Markers: case/space-insensitive, inside support block. Panel/timeline (format.ts) ko+en: 'CODE · label · writer/생성 프로그램 sha8'; WRITER_IDENTITY_MISSING / SUPPORT_WRITE_FAILED labelled; TIMEOUT unchanged. Gate: own dumps vs 6babc5e byte-identical (adapter+reasons 7,401,796 B; kit 3,344,279 B). Own mutation: exposure kept on gate → 1/13 fails | npm test (workflow env) 27 files / 467; tsc -b clean; build:static OK | PASS WITH NOTES (see 82) |
| 83 | 2026-11-12 | KIT-V2 Step 0 scaffold (REQUEST 12 A) | Priya | 3617cbb (branch now e26a0ff: + STEP1_ACCEPTANCE.md only) | rebuilt request-window kit + build_kit_v2: manifest b37e0c79… reproduces, 62 files; overlay = 1 file, +3 lines (STATE.kit_identity from KIT_IDENTITY.json); queues differ only in the rda_worker_v1_1.py hash (40 entries); test_build_v2 10/10; parent tests 31/32, only test_18 (seal), only the overlay file differs. Own panel 20 missions × 1 rep, interleaved, 81 s: G1 20/20 identical (incl. FL2 FEASIBLE@1922 both), 0 UNRESOLVED→certified, G3 20/20, G5 wall ratio 0.990, memory OK, kit_identity V2 20/20 / FROZEN 0; G2 14/14 (= 28 over 2 reps) both checkers; G2b (Thomas g2b.py @ e3cc617, C checker built) 19 PASS + FX2 NOT_APPLICABLE_STATUS, 0 violations; g2b fallback crash reproduced (RESULT without decision → TypeError: unexpected kwarg 'graph') | as stated | PASS WITH NOTES (see 83) |
| 84 | 2026-11-12 | F-DYN clearance margins (REQUEST 12 B) | Priya | f35cce0 | rebuilt the two Yeongdeok 0325T23 v3.1 packets from MANIFEST_v3_1 (npz 880345df…/de0d977c… = Priya's; HAZARD differs only by the row-74 host path); rebuilt requests (fdyn_profile logic); own driver: 20/20 margin witnesses CERTIFIED_ADMISSIBLE by the frozen whole-road checker + exact clearance > r_lo, min distances identical to VERIFY.jsonl (8 with no source within r_lo+50). 3953 s route: limiting segment w545751967:s46:f (12.8 m, traversed [3948, 3950] s) vs CURRENT cell 5173 active [0, 3948.10): the segment ENTERS the cell rectangle (whole-segment distance 0.0 m; inside from t≈3948.94 s to 3950, 53% of its length), both packets | own driver | PASS WITH NOTES (see 84) |
| 85 | 2026-11-12 | PR #158 F-3.2 README erratum (proof-carrying slices) | Thomas | 517e0f42 (off Main 2e7b9061; merge-tree clean) | slices.json sha c0410e89… identical at ae5351a, 0685e03, Main, head; recomputed: 15 non-forced rows (10 ROUTE, 5 NO_ROUTE) ratio 0.82 / 3.08 / median 1.42 / 6 above 1.5 ✓; best_optimality_total/full 3.82–11.24 ✓; legality A over 15 ROUTE rows 4.54–57.36 KB ✓; NO_ROUTE A 50–55 B ✓; restored range = ae5351a text ✓. Consequence line overstates: 3/15 ratios < 1 (0.82, 0.85, 0.86) and the 5 forced rows need ≈0.1 KB (README's own previous sentence) | own recomputation | CORRECTIONS NEEDED (see 85) |
| 86 | 2026-11-12 | g2b.py fallback fix (row-83 N1) | Thomas | deeb7c22 (thomas/routing-next) | fresh v2 runs: FX2 0325T19 deadline stop published RESULT WITHOUT a decision this time (natural case) + FN1 with decision stripped; g2b @ deeb7c2: fallback via decision/journey_decision.py (signature-filtered kwargs) → FX2 UNRESOLVED NOT_APPLICABLE_STATUS, FN1 recomputed FULL_MODEL_REFUSAL_PROVEN = the published status, PASS (relax NO_ROUTE); rc 0, 0 violations; test_g2b 12/12 | as stated | PASS |
| 87 | 2026-11-12 | F-DYN margins: row-84 N1/N2 fixes | Priya | eecfb0b | README + RADIANT_PLAN now state: enters cell 5173 0.84 s after modelled burnout, margin sub-second / 0 m, '4 m' withdrawn ✓. 7 published routes committed; own recompute from my rebuilt v3.1 packets: r* 12,081.626 / 5,118.099 / 4.395 m and domain distances 2,543.9 / 4,653.1 / 8,039.2 m match FDYN_CLEARANCE.jsonl exactly on 7/7; limiting segment of the 3953 s route = w545751967:s46:f | own driver | PASS (closes 84) |
| 88 | 2026-11-12 | PR #158 corrections (row 85) | Thomas | cfe003ab | diff from 517e0f42 +5/−4, README only: consequence line = my suggested wording; range 33–2,858 KB (min 33,482 B) ✓; merge-tree vs Main clean | as stated | PASS (closes 85) |
| 89 | 2026-11-12 | KIT-V2 Step 0 frozen cut (REQUEST 13) | Priya | 72541bb (off Main 633a0bf) | branch vs merge-base: 22 files, 0 outside experimental/window-routing-v2; vs 3617cbb: exactly 5 files (A DESIGN_STEP6.md, G6A_SAMPLE.json, G6_RULE.md, results/step0/G2B_all40.json; M PLAN.md, additions only), no code; the other 17 files byte-identical to 3617cbb (row 83); no g6_select.py anywhere in the cut, and G6_RULE says so; DESIGN_STEP6 cites ac80919 as unverified; G2B_all40 = 40 rows, 38 PASS + 2 NOT_APPLICABLE_STATUS; Main 8fdce35..633a0bf touches none of window-routing, integration/kit, F-3.4/run_profile.py, F-4.2/fixed_route_check.py | git only | PASS (docs/data-only delta confirmed) |
| 90 | 2026-11-12 | COMPREHENSION session kit byte identity (relay from Clara via orchestrator; preliminary: final head pending Iris's coding rules) | Clara | 200dd435 (off Main 633a0bf) | branch touches no planner/src or scripts (only COMPREHENSION/kit, PROTOCOL.md, tests/planner/comprehension.kit.test.ts) → no resident wording changed; (1) comprehension.kit.test 1/1 (head, SMS, card, page re-rendered byte-identical; tally 354/147/11/19 = 531, gap/partial/later-window 0); (2) build:static + capture_staff --check: 16 files byte-identical, 4 panel titles ok; (3) build_print.py --check OK; (4) MANIFEST.sha256 all OK. Own check: WFG_BUILD_PUBLIC_VIEW=1 build, real browser (390 px, clock pinned at now_iso), public-view.html?scenario=…&place=… for C1/C2/C4/C5: banner+slot+question+card outerHTML == items/*/page.ko.html and card == card.ko.html on 4/4 once the random object URL is replaced by blob:replay-gpx (it occurs only in the GPX href) | own browser check | PASS WITH NOTES (see 90) |
| 91 | 2026-11-12 | COMPREHENSION kit final candidate (PROTOCOL v2.3) | Clara | 861aa9a1 (fast-forward of 200dd435) | diff 200dd435..861aa9a1: 15 files, none under kit/items, kit/print, CASES.json, capture_staff.mjs or planner/ (empty diff) → row-90 item, page and staff checks stand; test file change = comment only (N1 stated); build_print.py change = column list sourced from score.COLUMNS. Re-run: comprehension.kit.test 1/1; build_print.py --check 16 files; pytest tools/test_score.py 11/11; MANIFEST.sha256 59/59 OK. N1 stated in PROTOCOL Limits (l.173), README §6 and the test comment | as listed | PASS (closes 90's N1; final unless Iris changes the two coding rules) |
| 92 | 2026-11-12 | W-KIT issuer jurisdiction cut (relay from Clara; staff wording DRAFT with Iris/Sofia) | Clara | 9b09bcd6 (off Main 633a0bf) | labels.json sha 0896957b…be52c ✓; apply_sigungu.py --check OK; places.geojson vs Main: only `sigungu` added (86 + 91 features), 0 other changes; 177 real origins all established (의성 48 / 안동 38 / 영덕 82 / 청송 4 / 영양 5). Own probe vs Main, production registry (5 issuers) × 531 real + 600 syn: Main renders every issuer at all 531; head renders only where established sigungu = issuer (531 of 2,655 real pairs, 100 % per county), 0 cross-county/unestablished lines; 2,124 real + 3,000 syn withheld, each = the no-issuer outputs and violations, each with KO+EN staff line, also in the KO decree report (5,124/5,124); matched outputs byte-equal to Main; no-issuer outputs unchanged at all 1,131. Changed tests checked: 영덕군 test 246 + 27 (청송 12, 영양 15) = my probe; inIssuerCounty is test-only (inside helper B); snapshot strip removes only the echoed field and also asserts every real origin is established. Guard: restoring Main's unlabelled places.geojson (= extract_places output) fails 8 tests in npm test, which planner-pages CI runs on every PR touching planner/** | wkit.channels 55/55; npm test (workflow env) 472/472; tsc -b clean; build:static OK; pytest JURISDICTION 13/13 (pinned venv) | PASS WITH NOTES (see 92; re-verify after staff wording settles) |
| 93 | 2026-11-12 | COMPREHENSION kit, Iris's AMBIGUOUS-TIME sentence (freeze head) | Clara | 41cadc50 (fast-forward of 861aa9a1) | 3 files: the same sentence added to the AMBIGUOUS-TIME row of PROTOCOL.md and SCORING_SHEET.html, MANIFEST.sha256 regenerated; no items/print/tools/test/app change. Re-run: MANIFEST 59/59 OK; build_print --check 16 files; comprehension.kit.test 1/1; test_score 11/11 | as listed | PASS (frozen head for the kit PR) |
| 94 | 2026-11-12 | KIT-V2 Step 1 (REQUEST 14) | Priya | 7879702 (branch now 408a27e: + STEP2 docs only) | rebuilt v2 (manifest 5afb464b…): overlay = 5 files (both decision modules: identical +59-line post-step, status asserted unchanged, MISMATCH/route-binding keep frozen reason; road_core +7, zsweep +7 hook-only; worker +46 progress writer). Tests: builder 10/10; parent 30/32, only test_18 + the copy test, on exactly the 5 overlay files; reasons 7/7 unit (3 F-DYN replays skipped, need her folders); progress 2/2 (52 s). Own 1-rep panel with redecide: 40 rows, 0 status differences, G1 20/20, G3 20/20, G5 wall 1.006, memory OK, kit_identity 20/0, no reason change (FX2 finished SEARCH_TIMEOUT before the deadline in both kits); G2 14/14; G2b (deeb7c2) 19 PASS + 1 NA, 0 violations. Rule b on my real deadline-stopped Step-0 V2 FX2 folder: frozen LATE_RESULT → DEADLINE_STOP_DURING_SEARCH with evidence; all other decision fields identical. Harness defect confirmed (run_profile.run_one imports journey_decision_v2_1 by name); redecide loads by path | as stated | PASS WITH NOTES (see 94) |
| 95 | 2026-11-12 | W-KIT jurisdiction, row-92 N1 (docstring + note) | Clara | 671bcbb8 | diff vs 9b09bcd6: extract_places.py docstring (+6, file parses) and one RESULTS line; no code. Docstring claims checked against apply_sigungu.py: it stops when an origin has no label or a label names no origin ✓. Residual: apply_sigungu pins labels to the committed places_input.json sha, not to the regenerated places, so an origin that keeps its id but MOVES would get its old label silently (re-labelling then needs export_places + label_sigungu) | read only | PASS (closes 92 N1; staff wording still pending) |
| 96 | 2026-11-12 | W8: X2, X1 certified + v3.3 control, X1 v3.4 samples, v3.4 burnset certificates, raw/packet guards | Thomas | 70abaa13 (thomas/routing-next) | X2 rerun (seed 20261112, networkx 3.4.2, C checker built): all 4 result files byte-identical (none 0 disagreements, 1,101 ROUTE / 908 NO_ROUTE; perturb 31, wait_admits 207, ignore_eb 285 detected). X1 summaries recomputed from rows: v3+v3.1 15/15 PASS, 2,592/2,592; v3.3 control 3/3 FAIL (395/1,032/3,168 HAZARD-only, 0/168); v3.4 11 PASS (1,908/1,908) + 4 envelope REFUSED, 0 other. Rebuilt v3.4 packets from MANIFEST_v3_4 (Leo faa89c4): X1 on Uiseong 0324T02 h5 burnset PASS 168/168, identical 16,176; routable_contact_model REFUSES the envelope (marker) and accepts the burnset. fdyn_certs on 2 rebuilt burnset packets, dep 0: 174/174 rows equal Thomas's committed rows field for field (claim, T, cert bytes, both checkers ACCEPT, variant, writer); whole-file summary 696 = 108 ROUTE / 588 NO_ROUTE, both accept and agree 696, routes 10–853 s, Uiseong 0 routes. Guards: test_raw_guard + test_tier_r_guard 18 passed + 1 skipped; the skipped e2e passes with WFG_REAL_PACKET = my burnset; every ContactModel.from_packet call is inside p1_check.routable_contact_model | as listed | PASS WITH NOTES (see 96) |
| 97 | 2026-11-12 | W-KIT jurisdiction FINAL head (staff wording settled; moved-origin stop) | Clara | 65a21316 (fast-forward of 671bcbb8; 5 files +76/−15) | build.ts: staff strings only (near_boundary text, mismatch / not-established lines with the base date from the label's source line and the residents sentence); rule, gate and counts untouched. apply_sigungu.py stops when an origin's point / entry node / entry lon-lat differs from places_input.json; own mutation (check → `if False`) → 1 of 14 pytest fails. Rendered lines checked in KO and EN for mismatch, near_boundary and absent label: date clause present when the source has BASE_DATE and dropped otherwise; no '고칠 항목' / 'field to fix' / status code. The residents sentence matches row 92 (withheld = no-issuer outputs) | wkit.channels 55/55; npm test (workflow env) 472/472; tsc -b clean; build:static OK; pytest JURISDICTION 14/14; apply_sigungu --check OK | PASS (frozen head for the PR) |
| 98 | 2026-11-12 | W8 updates: X1 h8 burnset; raw certificate output; burnset label | Thomas | 5d03d878 → ad5ccb8 | x1_v34_samples recomputed from its 16 rows: 12 PASS (4 kriged, 4 firms, 4 burnset) + 4 envelope REFUSED, 0 other, 2,088/2,088; h8 burnset row 16,176 identical, 180/180, raw vs contact 0; run_note discloses the separate rerun. Raw output committed (e252a61, sha256 4e29f3d0…): vs the relabelled file, rows differ ONLY in `variant` (696/696, envelope → envelope_burnset), packets ONLY in `variant` + `writer` (4/4); no verdict, T or byte count touched (closes 96 N3). Label now states the composition (kriged footprint + FIRMS + buffered AHI; 4,940 AHI-buffer-only), answering 96 N2 per Leo | git + recompute | PASS (closes 96 N1 by Thomas's row, N2, N3) |
| 99 | 2026-11-12 | BINDING_RULE.md review (before code) | Thomas | 943a1423 | design review, not a verification: answers to Q1/Q2 and 6 required changes sent (see 99) | read | REVIEW: GO with changes |
| 100 | 2026-11-12 | BINDING_RULE revision 2 review (before code) | Thomas | a4cfb922 | the 6 row-99 points are addressed. Checked his facts: ContactModel.from_packet reads only ignition_time_s and current_active (npz) plus REPORT burning_duration_s / initial_remaining_s / member ids (contact.py); require_routable_arrays also reads the per_cell_law_HAZARD_only marker key; unknown_support.py uses the support channel. Two additions requested (see 100) | read | REVIEW: GO with 2 additions |
| 101 | 2026-11-12 | W9 certificate binding (BINDING_RULE rev 2.1) | Thomas | 70acfe8 (thomas/routing-next) | T10 SHA-256 5/5; test_binding T1–T6 6/6; C suite 30 + 2 on wfgc_check and on the ASan/UBSan build. Own malformed-bundle battery (both checkers, same verdict + exit on all 23 cases): a record or a second INSTANCE block outside the hashed span, a modified INSTANCE before it, BIND twice / after END / missing (with and without --expect), CRLF, END_INSTANCE + space, leading-zero / '+' / 9-word BIND rows, and malformed --expect (upper-case, missing, duplicate, extra, short, empty) → all REJECT; v1 without --expect unchanged; v1 + --expect → BIND_MISSING. bind_panel rerun: summary and per-mission I16 identical to the committed file (20/20 BOUND, generator = consumer 20/20, T7 structure 20/20, O2 0 diffs 20/20, T1 10/10 BIND_Q). bind_completeness rerun: file byte-identical (T8 660/660, T9 437/437). Forgery: FN1's bundle with FX1's G/A/W/Q labels → ACCEPT … BOUND on BOTH checkers; T7 catches it (O2 2 diffs; structure 0) | as listed | PASS WITH NOTES (see 101) |

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

**25. Radiant screen @ 79f3271**:
- The C-11 closed form matches brute-force integration to 6 significant figures; the half-space case gives F = 0.5.
- Own bisection reproduces 312.4 / 116.3 / 49.4 / 957.1 / 398.0 / 312.0 m. The route counts (1-9, 0-4; 0-4, 0-2) were checked by hand.
- Part 1: 0.703 = omitted-source peak cap (packets); the in-domain max_flux is 0.7019 including flame.
- The argument needs the SUM, non-flame 0.0156 + cap 0.703 ≈ 0.72 < 1.0. The 0.0156 figure (Richard's) was not verified by me.
- Part 2 is not computed. Part 3 is exploratory and assumption-driven (disclosed).

**24 update**: the #122 footer was removed through the API, and the head is unchanged at f912de9. The body has no claude.ai or session reference. READY.

**26. Radiant 4a @ 12c32af**:
- The JSON regenerates byte-identically (7.3 s).
- Own code (raw-npz sources, own integer-second sampling, own C-11 view factor and FD): FX2 E100/H20/W3750 gives 617 s / 120 stationary / FD 26.244, identical. FW2 gives 603 s / FD 20.161, identical; stationary 46 vs 47 (the departure second's classification).
- Case counts match the JSON.
- Notes: "0-9 routes with q>=1" should be 1-9 (FX2 is ≥ 6 s in every case). The plan commit is only 62 s before the results commit, so it shows commit order, not computation order. FD (80 TDU, 4/3) and the nearest-source model are assumptions.

**27. P-PROTO follow-up @ b3df2a3 (Clara)**:
- The diff vs Main is exactly the 6 P-PROTO files. Vs 75189d9, page code changed only in LEAVE_BY_WORDS and the after!==null guard; no assertion was removed.
- 403/403 pass. The property test passes and fails under the old 2-way mapping (syn:gen:4:origin). It recomputes claims from the raw sweep and enforces generator coverage; counts 413/325/53 match my own.
- The default build has 0 public-view files.
- Notes N1 and N2 from entry 21 are resolved.

**28. 5a @ 49a50b3**:
- Regenerates identically. FX2 is dwell 120 / wait 0 / moving 497 = 617. FW2's wait 46 equals my own stationary count.
- Note: the ISSUE second is in no split category (FW2 0+46+556 = 602 vs 603).

**29. §6 @ eda51f2** (plan 9a63fbb, 22 s earlier):
- The JSON regenerates identically.
- Own code: 4-corner mid-height receiver; infinite face gives F = 1; closed form = numeric to 6 figures.
- Sofia's 102.5/58.2, 263.8/163.8 and 434.9/273.1 m reproduce. All 8 count ranges match.

**30. W6 redo @ e69c3d1 (Clara)**:
- 3 files vs Main; W6 tests 8/8; planner 403/403; build OK.
- With 4 issuers, the violation lists equal the no-issuer run in 531/531 sets (the old FAIL is fixed). The ko head keeps its contact in 531/531.
- ko familyText 0/531 is expected: base texts use 73-87 of 90 bytes and a contact needs ≥ 20.
- Notes:
  - Head + contact reaches 39.7 s (old total cap 35 s); a policy change for Iris.
  - The agency string is never checked (whole issuer lines masked): "지금 출발하십시오 18:30 안전합니다" shows on a no-route voice text with 0 violations. Suggested guard: clock or departure patterns and an agency suffix.
  - The decree check is report-only (pending Iris).

**31. PR #123 @ bab9148**: 1 file (LOG.md +57); no URLs or private references; event-level news facts only; no footer. READY.

**32. Radiant §7 @ e33256b** (plan 5dbae3c, 42 s earlier):
- The JSON regenerates identically. All 22 standoff rows and their counts are reproduced by own code.
- 4/9/12 is correct. FX2 1 km = 643 s (523 + 120 dwell), confirmed.
- N1: the stationary 3/5/7 count includes departure-only routes; with real wait/dwell it is 2/4/5 (FW2 @0.5 km; Miryang FN1 @1 km; Hongseong FD1 + Miryang FN1 @2 km).
- c49b3f8 (issue field for 4a/5a) resolves entry 28's note, but §7 is not yet split.

**33-34. fire-next**:
- W2 (b2d9eba) and W3 (45a8975): all 3 v3.1 packets were rebuilt by me at Leo f40e2af. a: 142 diff, all end-only; b: 216 single-interval and 31 merged equal; c: 820 end-only. 0 mismatches and 10/10 in each, identical to the committed JSONs.
- Negative control: --law envelope on the firms_early packet gives 198 mismatches and 0/3 instances.
- W1 is withdrawn (superseded by Clara's W6). W4 is pending.
- Clara W6 05fec82 is acknowledged; per the orchestrator, verify once at the head with the agency guard and shelter-name change.

**35. PR #127 @ 43e418b**: 1 file (LOG.md +33); public sources; aggregate statistics only; no footer. READY.

**36. P-PROTO next @ 33f672d (Clara)**:
- 403/403; property counts match my own earlier counts; gap N shown 53/53; default dist has 0 public-view files.
- Probes: step uniform in 501/501 real timed cards (2 synthetic without a step omit the clause); 0 timed cards with a window_closed cell at or before T.
- Mutation none_checked→horizon is caught at real osm:node/415160449.
- DOM order and ONE_TRIP rely on her passing tests; Iris's E is not in this cut.


**37. W4 @ b2d9eba**:
- Tier R: all 20 missions are identical in label, T, cause, claim and accepted (optimistic, A, R1.5, R8.2), and packet info (a)/(b) is equal.
- F-DYN: Yeongdeok 19Z kriged_mean 180 rows (54 NORUN), Uiseong 17Z firms_early 168 (6), Yeongdeok 19Z firms_early 180 (9). O2 diffs are 0 per packet.
- N1: the empty-Python-output failure did not reproduce (0/528); its cause is still unknown.
- N2: the other 1,200 rows were not re-run.
- N3: v3 firms_early is superseded by v3.1 (W7 pending).

**38. W5 @ cc850f5**:
- N1: coverage ignores location; a synthetic US-only file spanning the window counts as covered for KFS_02. Today only Korea exports are supplied.
- N2: tier_label receives b_available (which also needs the TOA raster), so FIRMS without a raster gives not_labelled_no_firms; the fallback cov dict has different keys.
- N3: coverage is the span of detection dates, not the export period (conservative).

**39. W6R @ 25597ac**:
- The widening must use the request horizon: with H = the window end (2861), FD1 stays EXHAUSTED.
- N1: CI never runs this test with data. verified-window-routing.yml:69 runs the tests without fetching; reproduce-linux.yml:92 fetches but runs only tests/api.
- test_sipp_property.py was excluded because hypothesis is missing from my venv (not this change).

**40-41.** #128: the CI run was still queued when checked; the PR body carries the footer (flagged). #130: the body says nothing was run, but the log cites "our own back-test against Morandini"; the body's 15 m wording differs from the log's 50-400 m.

**42. W6 @ 344657e (FAIL)**:
- Passing examples: 구조대 도착 예정 본부, 버스 배차 완료 상황실, 대피 불필요 상황실, 지금 바로 대피 동, 여섯시 출발 상황실, Transport provided Agency, No need to evacuate Office, All clear Division.
- Cause: single-syllable suffixes, a narrow blocklist, Korean numerals not caught, and 구조대/119구조 removed as compounds. Kit NEVER/DEPART catch 4/22.
- Suggested an allowlist or a structural rule.
- PASS parts: contact last; English voice has no Hangul and the pointer appears in 373/373; readerNote iff Hangul name; no Hangul outside the shelter name; smsSegments boundaries (minor: escape and surrogate splits at the 153/67 boundary not modelled); metrics.

**43. STAFF-HEADLINE @ b45a94b**: N1: smoke regenerates 12 tracked screenshots; N2: visual styling not inspected.

**44. c11eccd0**: suggested a packet-grid-bounds check instead of KOREA_BBOX; suggested regenerating tier_r.json or recording that it was produced at b2d9eba.

**45-46. Priya @ db2c516**:
- 45: warm 59.1 s excludes 5 prime runs (73.5 s with them); cold 81 s: 98/100 on time, 5 UNRESOLVED.
- 46: ADAPTIVE reason comes from the hybrid wall cap (hybrid_radiation.py:182-184).
- 46: snap10 FL2 has no shares (not completed); snap10 FX2 reason changes in one rep.
- 46: FL2 varies across runs and modes, not within the plain control.

**47-48.** The staff-headline update (37fb457) was moved to Owen. Clara's dd97b42 was set aside by the orchestrator in favour of a registry-only guard, so I did not verify it. My HAZARD sha differs from Thomas's because the identity includes the absolute module path (known host difference).

**49. 9695e26**:
- N1: the contact number accepts time- or date-like strings ("18-30", "2025-03-25"), which render with 0 violations.
- N2: a caller-supplied agencyRegistry replaces the committed registry, so any name renders. There is no app caller today.
- smsSegments packing was not separately re-verified.

**50. PROV-FLAGS @ 79ad132**:
- N1: an unknown record.provenance makes provenanceText throw, so it does not fail closed.
- N2: T < exact leave_by_s in 501/501, so the label describes the exact bound after T.
- N3 (design call): the CSV gives the present-fire-only value as raw seconds.
- N4: visuals not inspected.

**51-55. Pre-cut** (d4564b38):
- (b) does not assert that the derived dep/H equal the instance's.
- (c) does not compare the checker claim/T with generate's.
- (d) the committed JSON predates --law/--tag (keys missing; values identical), so regenerate it for the cut; it must be presented as a negative result.
- fdyn cocerts are built with legs=[] (sized only, never checked).

**56.** Minor: mobile 010-type numbers accepted (personal-data concern); the test-only override is exported from a production module. Thomas's (a) evidence: panel bundles byte-identical 20/20.

**58.** Optional: 050 (personal safe numbers), 070 (VoIP) and unassigned 012/013 still pass the phone shape. W-KIT PR #138 is frozen at 1334e47 (entry 56).

**59.** The PR body should drop the "not yet verified" line and add this row when marked ready. hypothesis 6.170.13 was installed in the verification venv to run the property tests.

**60.** N1: a timed label forced onto a no-time plan is flagged only in ko (help sentence trips the DEPART scan), not in en. The real join never produces it; suggested a guard in staffProvenanceLine.

**61.** Optional: unresolved_proven_no_route is not dropped when forced onto a leave_by place (the real join never does this).

**63.** Tiny: 00-000-0000 also counts as a placeholder; short call-centre numbers (031-120) and 080 toll-free are refused (conservative).

**65.** The arrays do not implement the static burn-set law: do not certify until they do. Only 0323T01 was checked.

**66.** N1: the 30 s rows are LATE_RESULT, not search TIMEOUT. N2: the g12k run also has 1 FULL_OPTIMUM_PROVEN (not claimed). N3: b900_g12k has 1 row. The optional spot run was not done.

**67. Scope note on my rows 33, 34 and 55 (W2, W3, sign-off d):**
- Those verdicts verified that HAZARD.json implements the stated envelope rule (v3 binary64, v3.1 integer ms).
- They did NOT verify what ContactModel or the router reads; on envelope packets the two disagree (794 cells on v3 Yeongdeok).
- No envelope packet was certified. The #145 erratum's "confirmed by Mira" should be limited to the v3 Yeongdeok packet.

**70.** N1: firms …168 was FEASIBLE (not unresolved) in A1. N2: the Uiseong LO cap is inferred, not recorded. The per-route re-run was not possible (ORIGINAL_REQUEST.json not committed).

**73.** Note: ContactModel does not check the marker (safe today because v3.4 envelope births are all NaN). The end-to-end test skip message should ask for a routable packet.

**74.** Suggest writing the radiation module path repo-relative, or excluding it from the identity, so HAZARD hashes match across hosts.

**75.** N1 (pre-existing): the registry checks the issuer's name, not its jurisdiction; a 영덕군 issuer also renders on 258 non-영덕 place-scenarios. Suggested a staff warning or refusal.

**76.** N1: the claim "the Korean automated call is unchanged" has no direct assertion. It is guarded only indirectly (the Korean-drop mutation fails 5 other tests) and by my dump against Main; RESULTS.md says the test checks "those claims" for all 373 places, which overstates it. Suggested an explicit ko.voice assertion. N2: build.ts code comments still say "owner decision" / "OWNER DECISION" (lines 264, 275, 390, 515, 554, 848, 933); none of these reach staff, but they now contradict the wording. N3 (cosmetic): the Korean staff line renders "영어 자동 음성전화 — 만들지 않음 — 대피장소에…", with two em-dashes (build.ts:849).

**77.** Row-76 notes N1–N3 are unchanged at 368da46: no direct ko.voice assertion, "owner decision" in code comments, and the double em-dash in the Korean staff line. N4 (wording): "영어 자료 가운데 대피장소 이름(한글)이 나오는 것은 이장 방송 대본과 가족 전화 대본뿐" (and the English "only in the village-head script and the family call script") holds for resident outputs. The English staff reader note ("Reader: say the shelter name in Korean: …") also carries the Hangul name; it belongs with the head script, but the sentence could say "resident materials".

**80.** FAIL on the fail-closed property. (A) A gated RouteDetail still carries the full-policy pass and the exposure contact flags, and the TravelOnly panel (RightPanel.tsx:266-300) renders them regardless of verdict. This is reachable when the best attempt is unmasked and the travel-only check is masked; a fully masked plan has no best, so the panel stays empty. (D) Claim 1 says "non-null support", but only object values gate. Fix: on a gate, null fullPolicy, empty exposure, null withinBudget and dwellEndS, and treat any non-null, non-false support or support_writer as masked; add tests for both. Notes: (B) the panel and timeline need reason.* i18n keys, or must split the code in components/format.ts; (C) align with Leo's identity layout (packet_writer_sha256 as a sibling, identity nesting) or pin the wire shape in DESIGN; the base label should read 6babc5e.

**82.** Notes (documented limits, none reachable with today's wire): the walk does not enter array elements ({hazards: [{identity: …}]} → unmasked) and stops below depth 6 (a mask at depth 7 → unmasked). A marker given as an object inside notes/markers ({code: 'SUPPORT_WRITE_FAILED'}) is not seen. If a future wire nests support data in arrays, extend the walk, or refuse unknown nesting.

**83.** N1: Thomas's g2b.py @ e3cc617 crashes in its fallback (decision_from_worker_record has no graph kwarg in this kit) on any RESULT without a decision; that is a tool defect for Thomas. Priya's exclusion is correct, since an UNRESOLVED run makes no claim. N2: my panel ran 1 rep, Priya's 2; G1, G2, G2b, G3 and G5 match per rep.

**84.** N1 (material, wording): "passes 4.4 m from an active flaming cell rectangle … its spatial margin is about 4 m" is true only of the ACTIVE window. The route drives through the footprint of the limiting cell ~0.84 s after its modelled burnout (R_max = 3948.10 s). The real margin is temporal (sub-second), and spatially 0 m. It depends entirely on the burnout time, which is the quantity the row-65 burnset P1 issue concerns. State it that way before the line is quoted. N2: the published routes are not committed, so r* (12,082 / 5,118 / 4.4 m) cannot be recomputed from the repo; I checked the 4.4 m limit geometry from the graph and packet only.

**85.** Corrections: (1) "Optimality and no-route proofs are not smaller than the instance on this panel" is false as written. 3 of 15 are 0.82–0.86×, and the 5 forced-arrival optimality proofs are ≈0.1 KB. (2) "a device can verify route legality only" contradicts the forced-arrival case. Suggested: legality always (4.5–57 KB); optimality only where arrival is forced by the destination opening (5 of 20, ≈0.1 KB); otherwise 0.82–3.08× the instance before completeness authentication (loose bound alone exceeds the instance), so no saving over holding the instance on this panel. Pre-existing nit: the full instance minimum is 33,482 B (33 KB, not 34).

**90.** N1: the page item omits two controls that sit between the question and the card on the real page at phone width: the 'English' language button (y=412) and the '재현할 기록: <region> · <input time>' scenario selector (y=458), with the card at y=545. The test comment says they are 'below or beside it'; they are above the card. That is harmless if deliberate (they are not resident wording), but the selector shows a region and timestamp a participant would see. State the omission in PROTOCOL/README, or include them. Verdict is preliminary: re-verify the delta at the final head Clara names after Iris's coding-rule decisions.

**92.** N1: extract_places.py itself neither keeps nor re-applies the labels, so the guard is the npm test failure (CI on planner PRs), not the tool. Suggest one line in the tool (or its README) pointing to apply_sigungu.py, or have it carry `sigungu` through. N2: label correctness against the archive is Hannah's check, not mine. N3: the staff lines are DRAFT; re-verify the delta at the head Clara names after Iris and Sofia.

**94.** N1: run_one also imports `wfg_controller` by name (run_profile.py:64), so the first kit's controller runs the other kit's jobs. That is harmless now (runner/ is byte-identical in both kits), but redecide.py fixes only the decision. Make run_one per-kit (load by path or subprocess per kit) before any step touches runner/. N2: the progress hook's /proc read and file write are not exception-guarded inside road_core.solve/zsweep. An OSError (disk full, folder removed) would propagate and change control flow, so wrap _prog_hook in try/except. Also, the zsweep calls add a new per-second modulus check rather than reusing an existing bookkeeping point (wording). N3: the 3 F-DYN replay tests were not run (her folders). N4: rule b needs worker_failure=DeadlineStop; a deadline-stopped frozen-worker RESULT lacks it and keeps LATE_RESULT. That is conservative.

**96.** N1: X1 on the Yeongdeok 0325T11 h5 burnset was still running at the verdict (rule 3 is slow at 16,176 cells), and the h8 burnset is pending on Thomas's side. Only the Uiseong burnset X1 is independently reproduced. N2 (for Leo): both regions' v3.4 packets share one 79×237 grid at 375 m (x0 1,085,250, y0 1,815,750). The burnset packets have all 16,158 finite births at t = 0, plus 18 or 97 current cells, giving the same 16,176-cell union (≈2,275 km²) in every region and start. The 2,547 excluded cells are irregular, not a border. Identical-by-construction is therefore expected; whether that area is the intended final burn set is Leo's to confirm. N3: the relabel is verified indirectly on 174/696 rows: all fields, variant and writer included, equal a fresh run of the current code. The other 522 rows were not re-run, and the raw FDYN.json is not available to me. N4: the guard test count is 19 collected (18 + 1 env-gated), not "12/12". N5: PASS_RULES.md (0e2f0d4) precedes the X2 results commit (ecf2230) by 3.5 minutes; git cannot show that no run preceded the rules.

**99.** (1) Q: whole-request vs a field list must be decided, not both. Recommended: a versioned projection listing EVERY request field that build_instance reads (scenario ids, window, limits incl. incurred dose, valid_from/horizon, hazard_version, dwell, departure, origin/destinations, policy), plus a test that mutates each request field and requires that Q changes OR the derived instance is byte-identical. Canonical bytes must be pinned exactly (ensure_ascii, integers vs floats, allow_nan=False, NFC), or use RFC 8785. (2) W all-zero: acceptable only as an exact match (the consumer's own packet also declares none), never a wildcard. Note that W is already inside P (HAZARD provenance.identity). (3) The router reads constructed_arrays.npz, not HAZARD.json, so bind the arrays (an A digest) rather than rely on a per-packet X1 that a consumer may not have run. (4) P is host-dependent today (row 74: an absolute module path in HAZARD provenance), so a consumer that rebuilds the same packet on another host gets a false REJECT. Fix the writer, or bind a canonicalised HAZARD (without host paths). (5) T7 needs byte-identical serialisation from derive_instance; today O2 uses compare / compare_semantic, not a sha. (6) A v1 bundle with --expect must REJECT, never print UNBOUND; and the C SHA-256 tests should add the multi-block and 55/56/64-byte boundary vectors plus the million-'a' vector, since instances are up to MB.

**98 addendum.** Leo (via the orchestrator) rules that the identical 16,176-cell burnset is intended. It is the final mapped burn set of the KFS_01 event on the shared grid: 10,955 kriged + 4,940 AHI-buffer-only + 281 FIRMS-only = 16,176. This is consistent with my row-96 probe, where the burnset ∩ KFS TOA-raster-defined cells was exactly 10,955. Thomas's correction to claim 5 (18 passed + 1 skipped, not 12/12) and the "semantics" key (3437e35, rows untouched) are noted.

**100.** (a) Put `support` in A, yes. F-9.3 masked and optimistic packets are identical in every array except `support` (same ids, flame, flux; DESIGN of #152), so without it A cannot tell them apart, and only W (writer honesty) would. Unknown-support certificates (Tier A/R) read it. (b) Put the HAZARD-only marker in A (its presence and value, or an explicit 'absent'), because the routability guard reads it. A bundle made before the guard existed must not bind to a marker-set packet that has the same two arrays.

**101.** N1: R5's "It proves: … under a graph, routed hazard, writer and request projection equal to the consumer's own" overstates it. G/A/W/Q in BIND are labels the generator writes. R2+R3 prove only that the labels match the consumer's digests and that the instance bytes match I. My forged bundle (FN1 relabelled as FX1) prints BOUND on both checkers, and only T7 rejects it. Reword R5. Either print LABELS_MATCH instead of BOUND, or make every report quote BOUND only together with T7. N2: the rule's 'Fully bound = R2 + R3 + O2' omits T7(a), the structure check that Thomas himself found necessary (O2 checks no EDGES/WAITABLE/FORBID/ORIGIN/START). Update R5. N3: T7 exists only inside the panel harness (bind_panel.py); a consumer needs a standalone tool (bundle + own graph/packet/request → structure + O2 verdict). N4: the F-9.3 masked/optimistic pair and the v3.4 re-emission are not done (as Thomas states).
