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
| R5 | Judge Q&A bank v2 complete: every T0 answer cites a file; no purged phrasing remains (`tests/test_judge_qa.py` green) | | ☐ |
| R6 | 제출본 대비 정본 reconciliation sheet exists, in Korean, one page, and JUDGE_QA links to it | | ☐ |
| R7 | Printables as PDF under `docs/auto/finals/`: evidence sheet (A4), reconciliation sheet, related-work and SFTD059T differentiation panel, booth checklist, 29 dispatch sheets sample | | ☐ |
| R8 | `README.md` has a Round-4 section and the English abstract draft; forbidden-string and collision gates green | | ☐ |
| R9 | The release bundle `release/kcf-finals-2026/` (WFG-036) exists: `web/` whole, printables, `README_KO.md` with the 10-line run recipe, `CITATION.cff`, and `make finals-bundle` rebuilds it byte-identically | | ☐ |
| R10 | AI ledger current: `docs/auto/AI_DISCLOSURE.md`, `ROUTINE_PROMPTS.md`, `FORM_2A_DRAFT.md` agree with `git log` | | ☐ |
| R11 | `docs/HANDOFF_ROUND3.md` §5.1 and every date in `docs/auto/` say `auto/dev`, 10-16 and 10-24 | | ☐ |
| R12 | The author has run the booth recipe on the actual laptop once and closed NH-014 | | ☐ (author) |
