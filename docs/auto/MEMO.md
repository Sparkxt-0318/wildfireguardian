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
- 2026-09-03 · dev · **A directory is not a proxy for the files a test needs.**
  `data/cache/osm/yeongdeok_2025/` is TRACKED — it holds `vegetation.geojson` —
  while the four graphs inside it are git-ignored. So `if not d.exists(): skip`
  never fired in a clean clone and two tests failed instead of skipping. Gate on
  the files the test actually opens, and skip only when they are ALL absent, so a
  partially-populated cache still fails loudly. Evidence:
  `tests/test_osm_cache_isolation.py`, and this lap's `.auto/gates.json`.
- 2026-09-03 · dev · **An absent input should skip, never error.** Seven
  `test_photo_exif` tests reported as ERRORS because the module-scoped `client`
  fixture built a runner that opens a git-ignored DEM. An unguarded fixture turns
  one missing file into a suite that looks broken, which is indistinguishable
  from a real regression at a glance. Guard the fixture, not each test.
- 2026-09-03 · kickoff (human-run lap) · **A gate's exit code must be the thing
  the push depends on, even in an ad-hoc shell.** The kickoff session ran
  `gates.py --mode quick | tail -2 && git push`: the pipe returned tail's zero,
  the gate was RED (one collision-check hit in the new JUDGE_QA.md), and the
  push went through; fixed within minutes, but it is the Session 10 mistake
  again, made by the same tooling this repository was built to stop.
  `check_gate_invocations.py` cannot see a command typed into a session.
  Gate: capture `gates.py` into a file, read `$?`, and push only on 0; never
  pipe it. Evidence: commits `14f6870` (red) and `953eb6c` (fix).
- 2026-09-03 · dev · **`git fetch` at step 0 is a snapshot, not a lock — re-fetch
  before you build.** Two dev laps fetched `auto/dev` at `017c9ec` minutes apart
  and both fixed the same five tests; the second discovered the first's
  `c42287e` only when it checked GitHub Actions, after a full build and two
  20-minute gate runs. **Gate for the next lap:** re-run `git fetch origin` and
  compare `origin/auto/dev` immediately BEFORE claiming a row and again before
  the first commit — a row marked `in-progress` by a lap that has already ended
  is not a reservation, and the remote is the only reservation there is.
  Evidence: `auto/lap-b1989d5-superseded`, and BACKLOG WFG-001's lap notes.
- 2026-09-03 · dev · **A module-level `importorskip` is a COLLECTION-time skip:
  one reported outcome standing in for every test in the file.** That is the
  whole of the sandbox-vs-laptop 1116/1120 gap the previous lap left open —
  `tests/test_empirical_interaction.py` holds five tests behind one line-12
  guard. **Anti-pattern:** reconciling suite counts by comparing pass totals.
  Compare `--collect-only` counts, then add the collection-level skips back.
  Evidence: `docs/clean_clone_gates.md` §"The four missing outcomes".
- 2026-09-03 · dev · **A `skipif` belongs on a test whose assertions ALL need
  the absent input.** `test_weather_basis_is_derived_from_committed_data_not_a_literal`
  asserted both that the basis is derived (needs the git-ignored archive) and
  that it is never typed into the source (needs nothing); one `skipif` took both
  out of every clean clone, which is exactly where hard-coding the date is the
  tempting fix. Split, and the guard survives. Evidence:
  `tests/test_live_pipeline.py::test_the_weather_basis_is_never_typed_into_the_source`.
- 2026-09-03 · dev · **A registry KEY NAME is part of the gate, not a label.**
  `check_number_collisions.py` builds its anchors from the words in a key, so
  registering `farband_pooled_auc_committed` armed the words "committed",
  "pooled" and "auc" against the whole tree and turned three unrelated lines
  red — lines discussing a different pooled AUC entirely. Renaming it to
  `farband_pooled_auc_precorrection` (named for what *distinguishes* it, with
  no generic word in it) cleared all three without annotating one document.
  **Gate for the next lap:** before adding a key, read it as a set of anchor
  words and ask what else in the tree carries three of them; prefer a
  distinguishing noun over a generic one (`precorrection`, not `committed`).
  Evidence: this lap's `check_number_collisions.py` runs, and the entry's own
  `notes`.
- 2026-09-03 · dev · **A registry `json_path` cannot address a JSON key that
  contains a dot.** Both `build_numbers.dig` and `verify_numbers.dig` split the
  path on `.`, so `field.cells_ge_0.5.0` resolves to `field["cells_ge_0"]` and
  raises `KeyError`. The canonical field's core-cell counts (249 → 1,036) are
  stored under `cells_ge_0.5_per_slice` and are therefore **unregisterable as
  written** — the growth percentage beside them registers fine. Anti-pattern:
  assuming any artifact value can be registered on demand; check the key
  spelling before promising a number a home. Evidence:
  `canonhaz_core_growth_pct`'s caveat.
- 2026-09-03 · dev · **`scripts/build_numbers.py` no longer builds the
  registry, and running it would destroy most of it.** It defines 65 entries
  and ends with an unconditional `OUT.write_text(...)`; the tree holds 278.
  Every entry since roughly Session 12 was added to `docs/NUMBERS.json`
  directly, gated by `verify_numbers.py`'s `check` blocks rather than by a
  builder. The CHARTER §3 rule "registered through `scripts/build_numbers.py`"
  describes a path that is now a landmine. **Do not run it.** Add entries to
  the JSON with a `check` block and let `make verify` be the gate. Filed for a
  fix as part of the next infra row.
- 2026-09-03 · dev · **"An absent input skips" applies to git-IGNORED inputs
  only; on a git-TRACKED artifact a skip hides a defect inside a green summary
  line.** WFG-019's test file guarded its module-scoped `artifact` fixture with
  `pytest.skip` out of habit from the earlier lesson. One full-suite run then
  reported **1,071 passed / 60 skipped** where the three runs around it — same
  tree, same commit, same flags — reported **1,077 / 54**; the delta was exactly
  the six tests behind that fixture, and the gate stayed GREEN through it. The
  cause of the momentary absence was never reproduced, which is the point: a
  skip made it unfalsifiable. **Gate for the next lap:** a `skipif`/`pytest.skip`
  guard is legitimate only when `.gitignore` actually excludes the file. If the
  path is tracked (or has an explicit `!` negation), `assert path.exists()` with
  the regeneration command in the message. Evidence:
  `tests/test_operating_point_evidence.py::artifact`, and this lap's four
  pytest readings.
- 2026-09-03 · dev · **Sibling registry keys collide with each other when a
  document lists key and value on one line.** WFG-019 registered 17 keys whose
  names necessarily share anchor words (`optpoint_*_fnr_advance_cut` ×3,
  `lofocal_*_flagged_share_*` ×4), and the doc's 출처 table put each key beside
  its number — so every row carried 3+ anchors of its siblings and 12 false
  collisions appeared at once. The MEMO's earlier lesson was about a key
  colliding with the REST of the tree; this is the same gate firing *within one
  new key family*. Fix was not pragmas: the 출처 table's value column was
  redundant (the values already live in the document's own result tables), so
  removing it left one home per number and cleared 12 of 13 hits. **Gate:** a
  key-listing table lists keys, not keys-and-values; one number, one home.
  Evidence: `docs/operating_point.md` §5, this lap's collision runs.
- 2026-09-03 · dev · **`report.py` and `dashboard.py` were both unparseable on
  Python 3.11, so no lap could have written a report.** Python 3.11 rejects a
  backslash anywhere inside an f-string *expression*; PEP 701 relaxed that in
  3.12. Commit `94937ab` added an `"...\n\n..."` fallback string inside a body
  f-string in `report.py` and an escaped-quote chip inside one in
  `dashboard.py`. Both parse on a 3.12+ machine and neither parses in the
  sandbox or on the `auto-gates` runner — a `SyntaxError` at import, before any
  logic runs. This lap was the first to call them and lost the report step to
  it. **What made it invisible:** no gate imports `scripts/auto/*`. `make
  verify` reads them as text, `pytest` never collects them, and
  `check_declared_deps` parses with `ast` but tolerates a file it cannot
  parse. So the loop's own reporting tooling is the one code path in this
  repository with no gate on it. **Gate for the next lap:** add a test that
  `ast.parse`s every file under `scripts/auto/`, or better, one that runs
  `report.py --kind dev` against a fixture summary in a tmp dir. Until then,
  byte-compile them (`python -m compileall -q scripts/auto`) before relying on
  a lap's report. Evidence: this lap's first `report.py` invocation, and the
  two hoisted-variable fixes.
