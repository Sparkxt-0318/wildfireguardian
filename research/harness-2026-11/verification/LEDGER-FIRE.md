# FIRE verification ledger (verifier: Nora)

Independent verification of FIRE routing streams (F-3.1 Richard, F-3.2 Thomas,
F-4.2 / F-3.4 Priya, F-C1 / F-9.3 Leo). Each row is one verdict on one pushed SHA,
re-run in a clean worktree from the stated command. The last PASS row for a
stream is its return point after a FAIL.

Environment: Python 3.12.3 `.venv` from `make api-setup` at Main 35bd351,
plus planner/tools/requirements.txt, GNU time installed.

| # | Date | Stream | Worker | SHA | Claim | Command | Verdict | Notes |
|---|------|--------|--------|-----|-------|---------|---------|-------|
