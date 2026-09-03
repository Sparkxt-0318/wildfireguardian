# KCF readiness — the final product's definition of done

The critic lap ticks every line daily with a commit or file as evidence, in the
`evidence` column; an unticked line is a finding, and the product is not ready
until every line is ticked. The dev laps work WFG-036 until it is. Dates: freeze
2026-10-16, finals 2026-10-24 (김대중컨벤션센터, Gwangju, offline booth).

| # | ready when | evidence | status |
|---|---|---|---|
| R1 | `web/finals.html` opens from `file://` with Wi-Fi off, all four acts advance, every on-screen number maps to a `docs/NUMBERS.json` key (mapping table committed) | | ☐ |
| R2 | The finals screen shows the evidence cards that exist today: operating point (WFG-019), reconciliation (WFG-018), detection floor (WFG-021), horizon grounding, refuge placement; rebuilt with `--verify` | | ☐ |
| R3 | `make all-checks` green on a clean clone (CI) and on the booth laptop recipe in `docs/auto/finals/BOOTH_SETUP.md` | | ☐ |
| R4 | A 5-minute demo script in Korean with per-act timings and the sentence for each judge type's interruption (`docs/auto/DEMO_SCRIPT_5MIN.md`) | | ☐ |
| R5 | Judge Q&A bank v2 complete: every T0 answer cites a file; no purged phrasing remains (`tests/test_judge_qa_bank.py` green) | Invariants met: `docs/auto/JUDGE_QA.md` 33 questions, tiers 14/13/6, 18 tests green in `gates.py --mode full` at `1113388`, WFG-002 `done(20260903T1536Z)`. **Not tickable:** §0 line 46 still states the repository was wrong about "6 → 34" (the superseded 452-series bracket; canonical is 6 → 66), which the SSOT audit disproved (CRITIC F1). A bank whose first section is false is not ready, whatever the invariants say | ☐ |
| R6 | 제출본 대비 정본 reconciliation sheet exists, in Korean, one page, and JUDGE_QA links to it | `docs/submission_reconciliation.md` (Korean, 11 rows, spoken lines); `JUDGE_QA.md:34` links to it; WFG-018 `done(20260903T0653Z)`; row 8 corrected by WFG-004 at `6a2c8a3` | ☑ |
| R7 | Printables as PDF under `docs/auto/finals/`: evidence sheet (A4), reconciliation sheet, related-work and SFTD059T differentiation panel, booth checklist, 29 dispatch sheets sample | | ☐ |
| R8 | `README.md` has a Round-4 section and the English abstract draft; forbidden-string and collision gates green | | ☐ |
| R9 | The release bundle `release/kcf-finals-2026/` (WFG-036) exists: `web/` whole, printables, `README_KO.md` with the 10-line run recipe, `CITATION.cff`, and `make finals-bundle` rebuilds it byte-identically | | ☐ |
| R10 | AI ledger current: `docs/auto/AI_DISCLOSURE.md`, `ROUTINE_PROMPTS.md`, `FORM_2A_DRAFT.md` agree with `git log` | | ☐ |
| R11 | `docs/HANDOFF_ROUND3.md` §5.1 and every date in `docs/auto/` say `auto/dev`, 10-16 and 10-24 | Fails today on three live lines (CRITIC F7): `CHARTER.md:11` "until 2026-10-18", `RUBRIC.md:20` "당일 10.18", `NEEDS_HUMAN.md:72` "the 10-10 freeze". The `research/sweeps_2026-09-03/*` files predate the NH-006 decision and keep their text as dated records | ☐ |
| R12 | The author has run the booth recipe on the actual laptop once and closed NH-014 | | ☐ (author) |
