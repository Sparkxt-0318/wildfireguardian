# Loop memo — lessons that change the next lap (re0-memo)

Append-only. One entry per lap that learned something; a lap that learned nothing
writes nothing. Format: date · lap kind · lesson (as a gate or anti-pattern, not a
mood) · evidence.

- 2026-09-03 · kickoff · **Pinned requirements install from PyPI wheels alone**
  (Python 3.11, macOS arm64 27 s; Linux verified in Session 18). The conda note in
  `requirements.txt` predates that measurement; `scripts/auto/bootstrap.sh` uses
  pip and records `pins_ok`. Evidence: `.auto/bootstrap.json` on the first lap.
- 2026-09-03 · kickoff · **The gate that matters is the one a stranger runs.**
  Sessions 18–22 were green on one laptop and never pushed; `auto-gates.yml` now
  re-runs every gate on a clean Linux checkout for every push to `auto/**`.
