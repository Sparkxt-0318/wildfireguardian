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
- 2026-09-03 · dev · **The test suite DOWNLOADS an 8.4 MB (gzipped; 25.9 MB on disk) SRTM tile from the
  network mid-run, so its own pass/skip counts differ between the first run in a
  fresh clone and every run after it.** This is the cause of the "unreproducible"
  1,071/60-vs-1,077/54 reading the previous lap logged and could not reproduce —
  and that lap's attribution to its own module-scoped `artifact` fixture was
  **wrong**, or at best a second, distinct instance. The delta is always exactly
  six because it is always the same six tests: `test_srtm_dem.py` ×4 and
  `test_validation_robustness.py` / `test_validation_session3.py` ×1 each, all
  guarded on `data/raw/dem/srtm/N36E129.hgt`. That path is git-IGNORED and absent
  from a fresh clone, so the six skip; then something in the same suite calls
  `data_io.raster._download_srtm_tile`, which fetches the tile from
  `elevation-tiles-prod.s3.amazonaws.com`, and every later run finds it cached and
  passes them. **Evidence, this lap:** `gates.py --mode full` read 1,088/60; three
  later full runs — bare, with `-rs`, and with the gates' own
  `-p no:cacheprovider` — all read 1,094/54; total outcomes were 1,148 in every
  one of them, so nothing was ever lost from collection, six tests simply moved
  skip→pass; and `data/raw/dem/srtm/N36E129.hgt` has an mtime of 16:34:35, inside
  the first run. **Anti-pattern:** comparing suite counts across laps as if they
  measure the same thing. A first-run count and a re-run count on one machine are
  two different quantities, and every baseline recorded so far (1065/51, 1077/54,
  1081/54, 1088/60, 1094/54) is an unlabelled mixture of the two. **Gate for the
  next lap:** state whether a count is a FIRST run or a RE-run in the same
  sentence as the number, and diff the `SKIPPED` lines in `.auto/pytest-full.log`
  — which `run()` already writes in full — rather than reasoning from the totals.
  **This answers the concurrent lap's WFG-038, which recorded the same six-test
  signature and wrote "the identity of the six is open"; its ruled-out
  hypothesis (`data/cache/*.nc`) was the wrong cache.**
  Filed as WFG-039 (make the download opt-in) rather than fixed here: it is a
  change to test network behaviour and belongs in its own row with its own review.
- 2026-09-03 · dev · **A number can be wrong in prose while being right in the
  artifact, and no gate in this repository can see it.** `README.md:731` quoted
  the dispatch-delay bracket `6 → 34` inside a paragraph that was otherwise the
  439-series real-OSM lineage. 34 is not a typo and not unregistered noise: it is
  the superseded pre-flip 452-series baseline's own bracket, in a tracked artifact, quoted
  correctly by two other documents. `check_number_collisions.py` fires only when a
  *registered* quantity appears with a *different* value near its key's anchor
  words; two lineages of one quantity are each correct, so there is nothing to
  contradict and the gate ran green over that line every lap (`UNMARKED
  collisions: 0`, exit 0, at this lap's baseline). **The failure then propagated
  through three documents and got worse at each step:** a research sweep asked the
  right question ("which artifact is 34?") and left it UNRESOLVED; the research
  brief flattened that to "a typo, unregistered"; and the WFG-018 reconciliation
  sheet — the one document whose whole job is lineage truth — hardened it into
  「34는 어느 산출물에도 없습니다」 plus a spoken booth line telling the student to
  say it. A judge could have falsified that with one `grep`. **Anti-pattern:**
  treating "the gates are green" as evidence that prose is right; and inheriting a
  previous lap's diagnosis as a premise instead of re-deriving it from the
  artifacts. **Gate:** a value gate cannot enforce lineage, so lineage needs its
  own test — `tests/test_rescue_lineage_ssot.py` fails when a superseded 452-series value
  appears without a lineage label beside it. It found the two propagated instances
  the moment it was switched on, and two more after the independent reviewer made
  me tighten it. **The tightening is the lesson.** My first version exempted any
  file whose first 20 lines contained "SUPERSEDED" case-insensitively, which
  silently exempted 15 tracked files — including `docs/auto/JUDGE_QA.md` and
  `docs/HANDOFF_ROUND3.md`, the two most judge-facing documents in the repository,
  each on an incidental word — and its label list accepted bare 이전/정본, so a
  sentence MIS-attributing the synthetic bracket to the canonical lineage passed
  *because* it said 정본. **Gate: an exemption must be a named list with reasons
  (a ratchet), never a keyword scan; and a label token must name the thing it
  labels, never be a word the surrounding prose would contain anyway.**
- 2026-09-03 · dev · **A pragma is right when the two numbers are genuinely
  different quantities; a rename is right when the anchor overlap is an accident.**
  The MEMO's earlier lesson ("prefer a distinguishing noun over a generic one")
  cleared 12 false collisions by renaming, and I tried that first here. It cannot
  work for `lofo_rowweighted_pooled_auc`: the two lines it collides with
  (`HANDOFF_ROUND3.md:553`, `MODEL_CARD.md:116`) exist *in order to compare* pooled
  against mean-of-folds, so they necessarily carry lofo + pooled + auc and a third
  number. No key name for the pooled LOFO AUC can avoid them. **Rule:** ask whether
  the colliding line's *purpose* is to hold both quantities. If yes, `collision-ok`
  with the reason is the honest fix and a rename would only hide the overlap; if
  no, rename. Evidence: this lap's four collision runs.
- 2026-09-03 · dev · **The charter mandates two skills a cloud lap cannot invoke.**
  CHARTER §4 step 3 requires `hate` on the plan every lap and the critic protocol
  requires `prism`; both are marked `disable-model-invocation: true` in
  `.claude/skills/`, so they are reserved for a human typing `/hate` and the Skill
  tool refuses them. `factchk`, `mandela`, `ssotize`, `sip`, `shower`, `catchup`,
  `nba`, `readchk` and `re0-memo` all are invocable. Until the charter is reworded,
  a lap should record the *reasoning* those two skills ask for — one load-bearing
  objection and its cheapest test — and say that the skill itself was unavailable,
  rather than silently skipping the step or claiming to have run it.
- 2026-09-03 · dev · **A cloud lap cannot reliably attach the board to its own
  email, and should stop pretending it can.** The routine prompt asks for
  `docs/auto/dashboard.html` attached as base64. The Gmail tool takes attachment
  content only as an inline string, so the agent must hand-copy ~42 KB of base64
  through a tool call, with no way to verify the result afterwards — and one
  wrong character corrupts everything after it, silently. This lap sent the full
  report and a pointer to the committed board instead, and said why in the email.
  **Gate:** attach from an agent turn only what can be verified after sending, or
  what is small enough to re-derive by eye. The deterministic path is the
  `report-email` workflow (NH-001's three secrets), which also could not have run
  until this lap's `report.py` fix. Evidence: this lap's send, and the truncated
  read of the base64 file.
- 2026-09-03 · dev · **The full suite reports two different (passed, skipped)
  pairs on the same commit, and the gate is GREEN for both.** This lap read
  **1,098 passed / 60 skipped** on its first `gates.py --mode full` and
  **1,104 / 54** on the second, third and fourth runs — same tree, same commit
  `682aeb3`, same flags (`-q -p no:cacheprovider --durations=15`), 1,158
  outcomes either way. The delta is exactly six tests moving between passed and
  skipped. This is the **second** sighting: the previous lap recorded
  1,071/60 against 1,077/54 and could not reproduce it. That lap's hypothesis
  (a `pytest.skip` on a module-scoped fixture) is not the whole story, and this
  lap ruled out the obvious successor: the six git-ignored `data/cache/*.nc`
  files are written during the first full run, but moving them aside and
  re-running still gives 1,104/54, because they are regenerated before the
  guarded tests execute. **What is established:** the drift is real, it
  recurs across laps, it appears on the first full run in a fresh container,
  and it is invisible because both readings pass. **What is not:** which six.
  **Anti-pattern:** treating "ALL GREEN" as the reading. A suite whose skip
  count moves by six between two runs of one commit has six tests whose result
  is unfalsifiable, and the summary line is the only place it shows. **Gate,
  filed as WFG-038:** `gates.py` already writes the pytest summary into
  `.auto/gates.json`; make it parse the triple, compare against a committed
  baseline, and WARN when the skip count moves — a drift that is printed is a
  drift somebody can chase. Evidence: this lap's four full-suite readings and
  `.auto/gates.json`.
- 2026-09-03 · dev · **A number inherited from the previous version of a
  document is not a sourced number.** The v1 Q&A bank answered "are any of
  these designated shelters?" with "fifty OSM POIs at Yeongdeok, **46 snapped
  to the network**". The 50 registers (`mr_yeongdeok_shelter_pois`); the 46
  appears nowhere in the tree — the only "46개" in the docs is
  `global_portability.md`'s count of POIs the query *missed*, a different
  quantity. It survived a rewrite because it sat beside a number that was
  true. This is HANDOFF §4-B's class (a citation with nothing on file to match
  against), reached by inheritance rather than by conversation, and no gate
  catches it: `check_number_collisions.py` only fires when a *registered*
  quantity appears with a second value. **Gate for the next lap:** when
  rewriting a document, every number that survives the rewrite gets looked up
  again, not carried. The replacement here was better than the original — the
  committed tag breakdown (33 `leisure=park`, 17 `amenity=shelter` of which 16
  are `shelter_type=gazebo`, `amenity=community_centre` = 0 in two of three
  regions) answers the judge's actual question. Evidence:
  `docs/multi_region.md` §"Split by tag", `docs/auto/JUDGE_QA.md` Q18.
- 2026-09-03 · dev · **A purge list retyped into a test is checked against
  nothing.** WFG-002's row ordered eight phrasings removed from the Q&A bank.
  The lap wrote them into a `PURGED` dict and parametrized a test over it, and
  the test passed — against the same author's own document, with no external
  referent. The independent reviewer found that the dict held eight entries and
  the 40-minute 안동→영덕 factoid was not one of them, while the report claimed
  it was gated. Of the whole purge list that factoid is the single item the
  research brief marks **"(no source)"** — every other entry is a superseded
  number, this one is an event that never happened — so the one item that most
  needed the gate was the one the hand-copy dropped. **This is the same failure
  the same lap had just diagnosed elsewhere** (the unsourced "46 snapped to the
  network", carried across a rewrite instead of looked up again), recurring
  inside the report about the fix, which is the argument for making it
  mechanical rather than resolving to be careful. **Gate:** derive a checklist
  from the committed file that ordered it, never retype it — here,
  `test_the_purge_list_covers_what_the_row_actually_ordered` parses the quoted
  phrases out of `RESEARCH_BRIEF_2026-09-03.md`'s "Deprecated Q&A material" line
  and `BACKLOG_PROPOSAL_2026-09-03.md`'s "Purge:" clause and asserts every one
  is covered. **Corollary:** use regexes, not literals, when a retired phrase
  shares digits with a live one — "40분" is a substring of the legitimate
  "240분", so the literal check that would have been written is the check that
  could not have been written. Evidence: this lap's reviewer verdict, and the
  two mutation runs that fail the purge test and the coverage test respectively.
