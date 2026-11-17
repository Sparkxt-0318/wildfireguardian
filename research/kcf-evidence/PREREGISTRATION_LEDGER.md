# PREREGISTRATION LEDGER (Main at a697d145, PR #189)

Method: freeze = first git commit containing the rule text; result = first commit (or recorded fetch/run time) of what it governs. Times are Asia/Shanghai, 2026, author date = committer date everywhere checked. **Limit: git times are self-reported and unsigned; `FREEZE_HANDOFF.json` says `external_OSF_registration: false`. Nothing here is externally timestamped.** Rule edits were read from diffs, not commit messages. Where the ordering exists only on an unmerged branch, it is marked *branch*.

## A. Freeze and first result

| Rule | File | Freeze | First result | Gap | Precedes? |
|---|---|---|---|---|---|
| kcf-margin PROTOCOL | `kcf-margin/PROTOCOL.md` | 746d0050 17 Nov 06:54:07 | 0ead8913 07:10:21 | 16m14s | yes |
| margin amendments 1-4 | same | in 0ead8913 07:10:21 | 0ead8913 | **0** | **no** |
| kcf-replay HOTSPOT_RULE | `kcf-replay/HOTSPOT_RULE.md` | 796e91c1 06:55:32 | 420ec724 08:02:32 | 1h07m | yes, never edited |
| replay MEASURED_RULE | `kcf-replay/MEASURED_RULE.md` | a4ff4f1c 10:00:51 | 54b3f96c 10:42:42 | 41m51s | yes |
| replay MEASURED amendment 1 | same | 3628d7a8 17:47:28, text replaced f71428e1 17:48:28 | KMA fetch 17:50:34; arm e912bfcf 17:59:42 | 2m06s / 11m14s | yes |
| kcf-gust PROTOCOL | `kcf-gust/PROTOCOL.md` | a4ff4f1c 10:00:51 | ERA5 fetch 10:01:17; 06d5a088 10:04:25 | 26s / 3m34s | yes |
| gust amendment 1 | same | 3be97228 10:46:16 | fetch 10:46:28; 890c2646 10:47:27 | 12s / 1m11s | yes |
| gust amendment 2 | same | 3628d7a8 17:47:28 | first KMA hourly call 17:50:34 | 3m06s | yes |
| gust amendment 3 | same | 7f74c9e0 17:53:14, **same commit as the data** | dbd97380 17:54:24 | 1m10s | class result only |
| kcf-heat | none (no protocol file) | none | 934db92d 08:32:44; c3fab072 20:36:54 | n/a | **no freeze** |
| F-3.1 DESIGN §5 | `F-3.1/DESIGN.md` | *branch* 58fcdf3a 12 Nov 17:06:15 | c8247d23 18:24:05 | 1h18m | yes |
| F-3.1 MULTIHOUR_HEADLINE | `F-3.1/MULTIHOUR_HEADLINE_RULE.md` | *branch* 53def3bb 13 Nov 00:00:40 (8 edits to 03:15:52) | 54bcb96e 12:19:42 | 9h04m | *branch* only |
| F-3.1 NOREENTRY2_ACCEPTANCE 6-8 | `F-3.1/NOREENTRY2_ACCEPTANCE_RULE.md` | *branch* ed87b5bb 06:33:40 | 2e4275b1 08:22:59 | 1h49m | *branch* only |
| F-3.1 NOT_EVALUATED_LABEL | `F-3.1/NOT_EVALUATED_LABEL_RULE.md` | *branch* da167134 12:24:41 | 54bcb96e 12:19:42 | **-4m59s** | **no** |
| F-3.1 WAITING_SENSITIVITY | `F-3.1/WAITING_SENSITIVITY_RULE.md` | *branch* 28251caf 04:08:22 | 70b4cd80 08:43:19 | 4h35m | yes (edited 08:12) |
| F-3.1 SPOTTING_NR2_ACCEPT8 | `F-3.1/SPOTTING_NR2_ACCEPT8_RULE.md` | *branch* bfc67ae4 12:22:18 | 0b8b9725 14:04:12 | 1h42m | yes |
| F-3.1 SUPPORT_READ + Amend 1, 2 | `F-3.1/SUPPORT_READ_RULE.md` | *branch* 51d3feee 16:28:27; A2 5ad24702 17:00:23 | 53ccd5ae 16:53:28 | 25m; A2 after code | **A2 no** |
| F-3.1 BORDER_TOUCH + Amend 1 | `F-3.1/BORDER_TOUCH_RULE.md` | *branch* 472b83cf 12:39:20 | 94795496 17:15:03 | 4h36m | yes |
| F-3.1 on Main (all of the above except DESIGN) | | rule file in **same commit** as result: 7a8d7f6b 13 Nov 12:38:18; 37e96645 17:34:35 | same | **0** | not provable on Main |
| F-9.3 support_mask | `F-9.3/` | f780cb13 12 Nov 22:49:07 | fa49b53b 23:04:27 | 15m | yes; A1 below |
| F-BASE frozen rules | branch | 85747d3c 19:05:17 | 676fc721 19:14:07 | 9m | yes, never edited |
| kit v2 G6 rule, G6A_SAMPLE | `experimental/window-routing-v2/G6_RULE.md` | a7d7617f 13 Nov 00:12:48 | first comparison 20:22:32 (Main d63eb16a 21:58:45) | 20h10m | yes; sample unchanged |
| W-KIT jurisdiction pass rule | `W-KIT/JURISDICTION/DESIGN.md` | baadd818 12 Nov 23:24:15 | 9b09bcd6 13 Nov 01:12:28 | 1h48m | yes |
| COMPREHENSION v2.3 | `COMPREHENSION/` | 861aa9a1 13 Nov 01:11:24 | none, no person tested | n/a | n/a |
| S-D9 A1 (rev 24) | `S-D9/PREREGISTRATION_ADDENDUM.md` | FREEZE.json e6761b19 12 Nov 19:28:13 | no sealed-part result exists on Main | n/a | **A1 still "DRAFT ... not frozen" at HEAD** |
| S-D9 amendment 1 | `S-D9/FREEZE_AMENDMENT_1.json` | 6954c37a 19:38:12; d4b90679 19:48:18 | 10a49081 19:38:53 | 41s | yes |
| S-D1 band rule (4 km) | `s-d1/` | 3eb31a38 17:06:57 | 07ab78f7 17:12:00 | 5m | yes |
| S-D1 NIROPS split | | e41fe337 17:14:26 | bba8d00d 17:15:09 | 43s | yes |
| S-D1 / S-D9 Gate 1, CMC 0.05 | | none | a902678d 17:26:24 (same commit) | 0 | **no** |
| forecast-v2 SPLIT / RUN_PROTOCOL | `forecast-v2/` | 7eb120e9 30 Oct 10:21:13; 38f0ce46 10:33:49 | 94923451 10:36:17; 353df859 10:39:06 | 15m; 2m28s | yes |
| forecast-v2 selection/registry | | 6887dc61 21:13:08 | held-out e9259dac 21:54:00 | 41m | yes |
| forecast-v2 extensions 1-12 | `RUN_PROTOCOL_EXTENSION_*.json` | 10:36 to 20:07 | see V12 | | all before held-out; 2, 3, 6, 10 not before dev results |
| sipp K-campaign | `research/sipp-routing` | 095b8d17 30 Oct 16:26:27 | 06ad9fe9 16:37:10 | 10m43s | yes |
| camera-arrival gate | `camera-arrival/` | 9ddee74a 11 Nov 23:14:54 | same commit | **0** | **no** |

## B. VIOLATIONS (none softened)

1. **V1 margin amendments 2-4 written with the results** (0ead8913). Amendment 2 changed NIROPS from R at round(g) to interpolated R. Amendment 3 is labelled post hoc. Amendment 4 dropped the gust class. Amendment 1 ("before any score was viewed") has no commit; unverifiable.
2. **V2 margin PROTOCOL.md edited after results**: c7b433c4 07:10:29, 8 s after 0ead8913. Wording only ("not a per-hour or per-fire guarantee" to "holds neither per hour nor per fire"), outside the Amendments section.
3. **V3 margin "before any reach score"**: the priors come from "a rough pass" with no commit in `kcf-margin`; the only earlier GOFER reach numbers are `s-d1` a902678d (12 Nov).
4. **V4 gust amendment 3 reverses amendment 2 after the data were read.** Amendment 2: -9 is "dropped, not zeroed", holes "reported". Amendment 3 (same commit as the data) reads -9 as class <10, "inferred". Read as a hole, the 5 h result "12 of 23 held" would be 4 of 15 (8 hours unscored); 8 h "8 of 20" would be 3 of 15 (computed from the committed table). `RESULTS.md` says all amendments were committed "before the values they cover were read"; false for amendment 3. ERA5 results (10:04) were also known before amendments 2-3.
5. **V5 replay KMA arm** depends on amendment 3 (no record = <10), which `MEASURED_RULE.md` never cites.
6. **V6 kcf-heat has no freeze.** Thresholds (q* 10 and 2.5 kW/m2; 92/105/290 TDU) and the closure rule were committed with their results. The only gate (factor of three, `01A` prompt, 00f33f8d 30 Oct) was **not applied to the replacement law**: the closed form fails it against FDS (6.6x to 109x) and was adopted anyway as a "screening law" (934db92d).
7. **V7 camera gate** first appears in the results commit; "the plan required a gate first" but the plan is not in the repo. 466f9267 held inventories only, so no visibility number preceded it.
8. **V8 F-3.1 on Main:** every rule file arrives in the same commit as its result. Rule-first ordering exists only on `origin/claude/f31-deadline-field`, unmerged and unverifiable.
9. **V9 NOT_EVALUATED_LABEL_RULE written 4m59s after the result** and used to relabel it: 1,074 "origin in flame" + 40 became 1,114 "not evaluated"; old unsplit key remains in the summary JSON.
10. **V10 F-3.1 changes after seeing output:** headline arm moved /1 to /2 (adf1892c 03:15:52) 2m23s after the spotting table; acceptance 6c narrowed 6m15s after being written (763b2290); "pessimistic variant in every band" replaced by a label (0e43eb66) after 99.28% / 68.39% of edges proved blocked; SUPPORT_READ written 1m48s after a failing pre-test, Amendment 2 after code; border-touch count 0 is vacuous (all nodes lie inside the grid).
11. **V11 F-9.3 A1** (rel 1e-9 OR abs 1e-12) proposed "post hoc" 4m42s after the regression failed 14/15 (7e8420ea); adopted going forward (24cba3bb); FAIL kept of record.
12. **V12 forecast-v2:** extensions 2, 3, 6 are in the same commit as results they govern; ext 10 (15:37:33) redefines the spotting variant after its dev and final results existed and reverses ext 9; ext 12 was written after the fit-coverage gate failed (f7221c58 18:44:44) and the auditor was patched (b8039a42) to pass. No split, selection rule or gate threshold moved; `REQUIREMENTS_STATUS.json` rewritten after results (41 of 125 statuses changed, text not diffed).
13. **V13 kit v2 G5 memory gate:** 12 of 20 missions failed (+40% to +78%); the measure was changed to family PSS (172546f1, amendment F), declared, after the failure.
14. **V14 kit v2 G6a:** G6A_RUN.md edited at a8112b96 13 Nov 18:44:40, after both PARENT runs and after V2 began. 17 failures known 20:22:32; a wider time-cap ruling (G6A_RULING, 20:23:58) was written 86 s later, "G6b only"; G6a stays FAIL AS WRITTEN. G6b has no result.
15. **V15 S-D9:** FREEZE.json rewritten in place (505788fa, 6m44s after e6761b19) though A1 says "never rewritten"; its pinned hashes for ACCESS_CONTROL and WSTS_DESIGN are stale at HEAD; sealed-part metadata (survey times, discovery dates, per-incident counts) was read, some after the freeze (parta_price.py, disclosed 22:04:12); `apply_filters.py` rules and COHORT_FINAL changed after first output (f91cf824, 2d40d170); c651 gate reference replaced after `exact_match: false` (A1 f2bf9721); H tolerance rule fitted on the 28 fires it governs; S-D1 `RESULTS.md` on Main still says "parts b-d ... never read".
16. **V16 F-3.2:** BOUND renamed LABELS_MATCH 22 min after "20/20 BOUND ACCEPT" (1284bddb); NR2 erratum 1 declared 168 certified rows "out of scope".
17. **V17 F-C1:** C1b Amendment 1 written after a computation had started (a285c670); verdict text committed 35 s before its script.
18. **V18 radiation (30 Oct, unmerged branch):** gate failed 56ae42cb (2.9x, 5.1x, 6.7x); emissive power then fitted to the same data; routing replay committed 5 min after the failure. On Main the gate is UNRESOLVED after the same data were relabelled INCOMPARABLE (4 of 9 rows >3x).
19. **V19 COMPREHENSION v2.3** loosened scoring 15 min after an AI-agent rehearsal returned "NOT MET" (coder agreement 7 to 9 of 12). Before any person.
20. **V20 corridor router:** native-support default (845a07d5, 15 Nov 20:22) changed after the 163/189 result was seen; not preregistered; both reported.
21. **V21 Gate 1 / CMC 0.05:** no numeric threshold precedes its result.
22. **V22 kcf-margin / replay RUNNING stand-in** (8.2 km/h) comes from reports of this same fire; frozen, but not independent of what it scores.

Not verified: branch back-dating; "before any V2 row is read"; ledger rows cited by the repo (not on Main); whether heldout NPZ timestamps were inspected before the forecast freeze. Long notes: scratchpad `audit_sd.md`, `audit_f31.md`, `audit_kit.md`, `audit_fcst.md` (not in repo).
