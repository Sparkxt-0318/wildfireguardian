# Verification ledger — FIRE side, part 2 (verifier: Mira)

Takes over from Nora (verification/nora-fire) for Thomas's W-KIT and later requests, Priya's F-3.4/F-4.2, and PR
merge-readiness checks. Nora keeps Thomas's certificate request 6d923e7a / a9eb0d8.
The last PASS for a stream is the checkpoint it returns to after a failure.

| # | Date | Stream | Worker | SHA | Claim | Command | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-12 | PR #103 data-fetch (merge readiness) | Daniel | 7d43080 | fetch.py checksums pass; MANIFEST/resources.json match small/; nothing large or restricted; rebuild_env.sh runs; no secrets | see notes 1 | PASS WITH NOTES (squash merge only) |
| 2 | 2026-11-12 | W-KIT | Thomas | 6ac1bc62 | 13 tests; 531 booth-cache origins, 0 violations; 600 synthetic, 18 violations (ko.head > 35 s); planner suite 378/378 | `cd planner && npm ci && npx vitest run ../tests/planner/wkit.channels.test.ts && npx vitest run` | PASS WITH NOTES |

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
