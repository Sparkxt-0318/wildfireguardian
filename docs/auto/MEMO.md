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
- 2026-09-03 · dev · **A test that guards on a path must guard on the file it
  needs, not on the directory that holds it.** `test_osm_cache_isolation.py`
  skipped on `data/cache/osm/yeongdeok_2025/` existing — but one file in that
  directory is force-added past `.gitignore`, so the directory exists in every
  clone and the graphs exist in none. The test could therefore never pass
  anywhere but the author's laptop, and read as a failure rather than as an
  absent input. **Gate for the next lap:** when a skip guard and its assertions
  name different paths, that is the bug. Evidence: `docs/clean_clone_gates.md`.
- 2026-09-03 · dev · **When one test asserts both "derived from data" and
  "never hard-coded", the data-free half dies with the data.** Splitting
  `test_weather_basis_is_derived_from_committed_data_not_a_literal` kept the
  anti-hard-coding guard alive on clean clones — which is exactly the
  environment where somebody would be tempted to type the date in. **Anti-pattern:**
  a `skipif` over a test whose assertions do not all need the absent input.
