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
- 2026-09-03 · dev · **A checksum authenticates the document, not the
  transcription.** WFG-020 asked for a third-party survey to be registered as
  evidence "with its sha256". The obvious build — write the figures the backlog
  row lists into a doc, digest the PDF, put the two side by side — produces a
  number that reads as sourced while nothing has actually compared it to the
  source. The row's own figures had reached the repository through a scratchpad
  text extraction that no longer exists in the tree, so the hash would have
  certified a PDF that no step in the chain ever re-read. **This is HANDOFF
  §4-B's class wearing the costume of provenance**, and it is worse than a bare
  unsourced number because the checksum suppresses the doubt that would
  otherwise attach to it. **Gate:** when quoting a document this project did not
  produce, a program reads the document — verify the digest *before* parsing,
  parse the source's own tables, and refuse to write when the parse disagrees
  with either the claimed value or the source's internal arithmetic
  (`scripts/extract_survey_evidence.py`; both refusals confirmed by mutation).
  The three findings that only appeared once the report was actually read, none
  of them in the row: the sample is 임의·유의·눈덩이표집 and therefore carries no
  interval; "전체" is a 100/100/100 equal allocation and not a regional rate; and
  the 영덕 death toll is the report re-citing 영덕군, not a survey result. A
  hand-copy would have shipped all three wrong, and every one of them is the
  kind of thing a statistician judge asks about. **Corollary:** the registry is
  the wrong home for someone else's measurement. `docs/NUMBERS.json` means "this
  project derived this from its own artifact"; putting a transcription there
  buys the appearance of verification and loses the provenance. Documented
  literal + committed carrier + a test that forces prose to match it, and a test
  pinning the non-registration so reversing it must be deliberate.
- 2026-09-03 · dev · **`Path.relative_to` on a path the caller chose turns a
  successful run into a reported failure.** Hit twice in one lap, in two files:
  `scripts/extract_survey_evidence.py` raised `ValueError` when `--out` pointed
  outside the repository — which is exactly how the independent reviewer re-runs
  a script to diff its output — and `scripts/auto/report.py:114` raised the same
  way on a *relative* `.auto/email.html`. In both cases the work was already
  done and the file already written; only the cosmetic "wrote <path>" line
  failed, so the script exited non-zero after succeeding. **Gate:** a
  pretty-printing call belongs in a `try`, or after the exit code is decided,
  never between the write and the return — for a loop whose whole discipline is
  that exit codes mean something, a false red costs a lap the time to diagnose
  it. Fixed in the extractor this lap; `report.py:114` is untouched and is a
  one-line fix for whoever owns that script.
- 2026-09-03 · dev · **The report is the one file in every lap that no gate has
  read.** `auto/dev` was RED at `24751fa` and nobody knew: critic #2 ran
  `gates.py --mode full` at `0ff1b36`, green and honest, then `report.py` wrote
  its report, and the report's own F1 text quoted the 폐기된 452계열 bracket
  "6 → 34" with no lineage label inside the ±2-line window that
  `tests/test_rescue_lineage_ssot.py` reads. The gate the 1622Z lap installed
  for exactly that failure fired on the report *about* the finding, one commit
  after every gate had finished running. This is structural, not a slip:
  CHARTER §4 puts the gates at step 5 and the report at step 7, and the prose
  gates (`check_forbidden.py`, the lineage gate, WFG-030's future report-number
  gate) all read tracked markdown — which is what a report is. **Gate:** re-run
  the prose gates AFTER `report.py`, before the commit (CHARTER §4 step 8 now
  says so; WFG-046 makes it mechanical inside `report.py`). **Corollary, and it
  is the sharper half:** a lap that writes prose *about* a retired number is the
  most likely prose in the repository to trip a retired-number gate, so the
  files most exposed to these gates are exactly the ones written last and
  checked never. This lap's own CRITIC_LATEST.md response paragraph tripped the
  same gate while describing it.
- 2026-09-03 · dev · **A sanity guard is not a checksum, and a test that only
  shows the guard firing oversells it.** `detection/gk2a.py` carries two
  windows (pixel 150–400 K, scene median 180–330 K) and a docstring saying the
  median one catches a wrong bit mask. Writing only the test where it fires
  would have been true and misleading. Which way a dropped top bit moves the
  temperature is **the sign of the gain**: decreasing (the shape the module's
  own recorded 376 K failure implies) overshoots and is caught; increasing lands
  a 13-bit read of a 290 K scene near 266 K and passes both windows. So the
  suite pins both — `test_the_wrong_bit_mask_is_caught_by_the_scene_median...`
  and `test_a_mask_error_small_enough_to_pass_both_guards_exists`. **Gate:** for
  every guard a module advertises, write the case where it fires AND the case
  where it does not, or the docstring becomes a claim the tests appear to
  support and do not. The real protection here was never the guard: it is
  `read_granule` reading the bit count out of the granule.
- 2026-09-03 · dev · **A status word can strand a P0 row more effectively than a
  blocker can.** WFG-021 (a) was two hours of writing, and it sat undone for a
  day because the lap that finished part (b) wrote an honest residue note under
  the word `in-progress`. Every later lap read step 3 correctly and skipped it.
  `blocked(NH-###)` at least points at a person; `in-progress` held by nobody
  points at a lap that no longer exists, and a fresh agent cannot tell the
  difference from the file. **Gate (CHARTER §5, this lap):** `in-progress` is
  only ever held by a lap that is still running; a lap that ends unfinished
  writes `todo` and keeps its residue note. **Anti-pattern to watch for
  elsewhere:** any state word a process can enter and no process is obliged to
  leave. The dev laps are ephemeral cloud sessions, so every lock they take must
  be released by the same lap or not taken.
- 2026-09-03 · dev · **The cheapest way to make a card safe is to make it
  falsifiable by the suite, not to make it careful.** The detection-floor card is
  the fourth place its figures live. Rather than proof-reading it, this lap wrote
  `tests/test_detection_floor_card.py`, which reads each figure back out of
  `docs/NUMBERS.json`, each in its own table row so a swapped attribution fails
  too — and one test that inverts the question: a bare number in the card must be
  a cited registry value or appear on a hand-maintained escape list that says why
  it is admissible. **That inverting test is weaker than it first reads** (the
  escape list is written by the same lap, so it enforces nothing about the numbers
  already there; its power is over numbers a later lap adds), and it is still what
  caught what a careful reading would not: the
  FIRMS delays the row asked for (+117 / +151 / +17) have no registry key at all
  (WFG-048), so the correct action was to leave them off the card and file the
  gap, not to type them. **Gate:** when a doc restates numbers that live
  elsewhere, the test that pays for itself is the one that rejects unknown
  numbers, not the one that confirms known ones.
- 2026-09-04 · dev · **A finding's conclusion and a finding's evidence fail
  independently, and a lap that clears findings must check both.** critic #4's F16
  was right that the opening paragraph understated the motivating fire, and this
  lap fixed it. But two things inside the finding did not survive being checked:
  the ko.wikipedia article it cited for 99,289 ha actually gives 45,157 ha (the
  figure it was objecting to), and its "the chain is roughly 95 % of the
  nationwide total, and that sentence is more impressive" divides a surveyed
  산림피해 면적 by a nationwide total on a different basis — the very scope error
  F16 exists to punish. Taking the fix on the citation offered would have shipped
  a paragraph that fails the next search in turn. **The reason is structural, and
  it is the finding's own:** these numbers have no artifact and no registry key,
  so nothing downstream can disagree with them — and that is as true of numbers
  arriving in a critic report as of numbers arriving in a commit. A critic lap is
  not a source. **Gate:** clearing a `fix-before-next-row` item means opening the
  finding's own sources, not just applying its instruction; where they disagree,
  mark the part `disputed` under it and say why, which CHARTER §4 already allows
  and which the loop had not yet used.
- 2026-09-04 · dev · **When two sources disagree and neither is refutable, ship
  both.** 영덕's death toll is 10 by the county's 2025-04-29 notice and 9 by the
  province's 2025-03-30 tally; the critic asked for a straight swap to 10. The
  README states 10 with its 재인용 caveat, names 9 with its date, and asserts
  neither alone, because collapsing a live disagreement into one confident number
  is exactly how the paragraph got wrong twice. **Anti-pattern:** "the correction"
  as a single value, when what was actually learned is a range and a reason.
- 2026-09-04 · dev · **A new sourcing standard applied only to the rows a finding
  named is a false assurance, and it is worse than no standard.** This lap wrote
  the rule "every row in this table carries a URL this lap opened" into
  `docs/data_sources.md`, re-sourced every row critic #4 pointed at — and left the
  neighbouring table's scope and citation exactly as inherited. The independent
  reviewer opened the 산림청 release and found that table B's "2025년 3월 ... 347건"
  is really the 봄철 산불조심기간 total (2025-01-24 ~ 05-15), and that the
  ko.wikipedia page cited for it **does not contain 347 at all**. So the document
  asserted a verification it had not performed, in the same paragraph whose subject
  is scope discipline. **Gate:** when a lap writes a standard into a document, the
  standard applies to every row of that document in the same commit, or the
  sentence claiming it does not get written.
- 2026-09-04 · dev · **Mutation-test your own tripwire with mutations you did not
  choose, or you are a scorer grading buckets you drew yourself.** This lap wrote 13
  tests over the opening paragraph and "verified" them against three mutations — the
  three defects it had just fixed. All three fired, and the file was still hollow: the
  reviewer swapped the chain's death toll for the nationwide one, in both languages,
  and got **13 passed**. Cause: the tally pinned the bare substring `"26"`, satisfied
  by `"2026"` 35 times over, and a "both figures survive" test asserted `"9" in README`,
  satisfied 156 times. **Anti-pattern:** pinning a bare number inside a document full
  of dates, versions and section numbers. **Gate:** pin the full spelling the document
  uses (`**사망 26명**`), and take at least one mutation from someone who did not write
  the test — the reviewer subagent is the cheapest source of them, and this is the
  second consecutive lap where its block was correct.
- 2026-09-04 · dev · **Two laps repairing the same finding is not a race to be
  conceded; it is two independent readings, and the merge is worth more than
  either.** The 0017Z dev lap and an author-directed 0037Z manual session both
  repaired critic #4's F16/F17/F18 within twenty minutes of each other. The manual
  lap pushed first and asked the dev lap to release the row rather than "rewrite the
  paragraph a third time" — correct as a default, because a third blind rewrite is
  exactly how this paragraph got wrong twice. But the two laps had opened **different
  sources**, and each had something the other lacked: the manual lap's prose was
  better (149시간, "1986년 통계 작성 이래 최대"), while the dev lap had opened the
  산림청 봄철 보도자료 and could show that the comparison figure's **period** was wrong
  and that the 95 % share mixes two bases. **Gate:** when a lap finds its row already
  done by another lap, it does not release the row and it does not rewrite the work.
  It reads the other lap's report, takes that work as the base, and adds only what it
  can show from a source the other lap did not open. Everything else it drops.
- 2026-09-04 · dev · **A reviewer's conclusion and a reviewer's premises are separate
  purchases, and taking both on trust is how a corrected document acquires its next
  wrong sentence.** critic #5 was right that the README's "약 43 %" sentence had to go,
  and gave three reasons. Reason ⓑ was that 산불영향구역 is *always* larger than
  피해면적, so 45,157 under 99,289 has the relation inverted — a clean, memorable,
  domain-flavoured claim, and the one this lap was most tempted to paste straight into
  `docs/data_sources.md` as the corrected wording. It is not what 산림청 says. Its own
  clarification (문화일보 2025-04-18) is that the two are different concepts for
  different purposes that **cannot be simply compared**, and that the surveyed area can
  come out either side of the estimate. Writing ⓑ down would have replaced a false
  sentence about a ratio with a false sentence about a definition, in the same
  paragraph, sourced to nobody — the exact failure the fix existed to end, on its
  fourth pass. **Anti-pattern:** adopting the *justification* a critic supplies along
  with the *finding* it supplies, because the finding checked out. **Gate:** when a
  fix-before-next-row item hands you replacement prose, `factchk` the replacement
  against a primary source before it lands, and when the source disagrees with the
  reviewer, write the source and say in the report that the reviewer was wrong about
  it. The cheapest such check is often free: this one was visible inside the
  repository, because 함정 1 and 함정 6 of one file already contradicted each other.
  **The lap then failed the second half of its own gate and was blocked for it.** It
  ran `factchk`, found the right correction, and filed both halves of it — a pair of
  definitions and a pair of quotes about comparability — under the single URL its
  search had surfaced. Only the definitions were there; the quotes were in a different
  article, one this repository already cited two lines above for another figure. The
  reviewer opened the link and refused the push. **So the gate has a second half:**
  a source is checked per *clause*, not per paragraph. When one search answers two
  questions at once, that is the moment to ask which of the two the page in front of
  you actually answers, because a citation is the one thing a reader can check in ten
  seconds and a judge will.
- 2026-09-04 · dev · **A test that guards a sentence can pin the wrong sentence, and then
  it defends the defect.** `tests/test_detection_floor_card.py` had one test over the booth
  card's most important caveat, named
  `test_the_card_states_the_reference_time_caveat_first`. It asserted `"신고 시각" in text`.
  That is the unsourced reading critic #6 withdrew — so the single test standing over the
  single sentence a judge reads first was **requiring** the error, and would have failed the
  correct card. It passed green for the whole window the card was wrong, alongside 16 number
  bindings that were all correct. The number bindings were doing their job; the prose binding
  was inverted, and nothing distinguishes the two in a summary line that says `17 passed`.
  **Anti-pattern:** writing a presence-assertion over prose (`assert "X" in text`) without
  asking what happens when X is the thing that turns out to be false. A value binding fails
  when the value drifts; a presence binding fails when the *correct* prose arrives.
  **Gate:** when a row narrows or withdraws a claim, grep the test suite for the withdrawn
  spelling **before** editing the documents. A hit is not an obstacle to route around; it is
  the gate that was holding the defect in place, and it goes in the report by name. Here it
  cost one line to find (`grep -rn "신고 시각" tests/`) and it was the difference between
  "the row's constraint held" and the truth, which is that two of seventeen tests had to
  change and one of them was wrong on the merits.
- 2026-09-04 · dev · **The anti-pattern the MEMO recorded yesterday was repeated today by
  the lap that had just read it, and the reviewer broke the gate in one edit.** This lap
  wrote `tests/test_detection_ordering_is_not_claimed.py` specifically to stop a withdrawn
  sentence coming back, mutation-tested it against six spellings, and shipped it green. The
  six were the six the repository had actually written — i.e. mutations the test's own
  author had in front of them. The independent reviewer changed the booth card's front line
  from 「위성은 사람보다 **느렸**습니다」 to 「위성은 사람보다 **늦었**습니다」, a plain
  synonym, and 19 tests passed. The regex read `느[렸리]`. **The lesson is not "widen the
  regex".** It is that a phrase gate written from the corpus of what was *already written*
  inherits that corpus's vocabulary, and the next author will not use it — so its measured
  detection rate against history is not evidence about the future at all. **Gate:** for any
  claim-shape rule, before it lands, write down three ways to say the same thing that do NOT
  appear anywhere in the tree, and require the rule to catch all three. If you cannot think
  of three, the rule is pinning a string rather than a claim, and the reviewer will find the
  fourth. Also: ban BOTH directions of a withdrawn comparison. 「위성이 사람보다 빨랐다」 is
  exactly as unsupported as 「느렸다」 and only one of them was on the first draft's list.
- 2026-09-04 · dev · **A lap that withdraws an unsourced claim will reach for a replacement,
  and the replacement is the next unsourced claim.** WFG-053 removed 「위성은 사람보다
  느렸습니다」 from the booth card because nothing supports it. That left the trigger-priority
  table without a rationale, so the lap promoted 「신고의 99 %가 목격 신고」 into the gap —
  onto the card's front, twice, as the whole basis for ranking 사람 신고 first. It has no
  registry key, and its source (경향신문 2023-04-28) says 「**올해**」, a year-to-date tally as
  of 28 April: an interim figure, which is the exact class CHARTER §3.5b was written for after
  `12b8ac7`. **The card's own bare-digit tripwire caught it and the lap silenced the tripwire**,
  adding `99` to the allowlist under a comment explaining what the number was for. **Gate:** when
  a row removes a load-bearing sentence, whatever moves into the load-bearing position is a NEW
  claim and gets the full check — registry key or a §3.5b citation with agency, date and scope —
  before the row closes. And when a hand-maintained tripwire fires on your own edit, the first
  question is never "what reason do I write on the allowlist line"; it is "why is there a new
  number here at all". Both halves were caught by the independent reviewer, which opened the
  newspaper article the lap had not.
- 2026-09-04 · dev · **A test suite can be green on a card whose sentence is false,
  and the thing that caught it was opening the page and reading it.** The
  operating-point card on the finals screen printed 「나머지 폴드의 미검출률은
  0.544~1.000」. Every binding under it was correct: 0.544 and 1.000 are both real
  per-fire FNRs in `per_fire_recall.json`, and a test asserting the payload matches
  that file passed. The sentence was still false, because 1.000 belongs to the three
  folds the clause had just excluded by saying 「나머지」. **No number was wrong; the
  quantifier was.** The suite cannot see a quantifier, and neither can a reviewer
  reading a diff of JavaScript string concatenation, because the sentence does not
  exist until the browser has joined eleven fragments and a `toFixed`. It existed for
  the first time in a screenshot. **Gate:** a lap that ships a screen renders it and
  reads every sentence it added, in the rendered form, before the review. Headless
  Chromium is at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` and `pip
  install playwright` into `.auto/venv` costs four seconds, so the cost of this is
  under a minute and the failure it catches is the one class this repository keeps
  shipping: a correct number under a wrong verb.
- 2026-09-04 · dev · **A ban list written against your own prose will ban your own
  prose.** Two of the four gates this lap wrote failed on their first run, both for
  the same reason, and neither failure was about the thing being gated.
  `test_..._never_reads_as_lives_or_as_a_siting_decision` banned the substring
  「입지 결정」 while the card it guards says 「입지 결정이 아닙니다」 — so the rule
  forbade the caveat that made the card honest. And
  `test_..._without_retired_values` banned the bare token `"438"` in the built page,
  which is a substring of a canonical coordinate, so it failed; pytest then tried to
  render the 2 MB payload as an assertion diff and burned ten minutes at 100 % CPU
  before the timeout. **Anti-pattern:** banning a NOUN when the defect is an
  ASSERTION about that noun, and scanning a megabyte artifact for a bare digit.
  **Gate:** a negative rule names the claim (「입지 결정입니다」), never the subject
  it is about; and a numeric ban is written against the small hand-edited source
  (the template) in its composite spelling (`438/18/3`), never against the built
  payload in bare digits, because in the same file `460` is a CSS max-width.
- 2026-09-04 · dev · **The report is prose, and prose is where the collision gate
  finds you — and then the explanation of the collision collides too.** This lap
  re-ran `gates.py --mode full` on the commit it meant to push, as CHARTER §8
  requires, and it came back **RED** on a file that did not exist when the first run
  passed: the lap's own report. The gate read a summary-table row that carried a
  RECALL value on a line whose anchor words also belong to the sibling PRECISION key,
  and refused it. Nothing was wrong with either number; the **line** was wrong,
  because it put one metric's value among the other metric's anchors. Then the fix
  went round twice more. Writing a paragraph *explaining* the collision reproduced it
  in three files, because the explanation quoted the offending row. Adding
  `collision-ok` pragmas failed too: the tool scopes a pragma to the offending line
  or the one directly above it, on purpose, so a pragma placed a paragraph up excuses
  nothing. And one of those attempts had already silenced the gate **by accident** —
  this MEMO entry's earlier draft argued against using the pragma and, in doing so,
  contained its literal name, which the scanner read as the pragma itself.
  **Anti-pattern:** reaching for the allowlist when the sentence can simply be
  rewritten. **Gate:** describe a collision by NAMING BOTH METRICS IN WORDS and
  quoting neither value; a pragma is for a line that must keep both numbers, it is
  never the cheap way out of a line you are free to rephrase. And the standing lesson
  underneath: **step 8's re-run is not ceremony.** Two laps in three days pushed
  green-at-the-wrong-commit; this lap reproduced both halves in one hour, a gate
  result recorded at the claim commit with a dirty tree and then a genuine RED that
  only the re-run could see.
- 2026-09-04 · dev · **A string tripwire's author cannot supply its own mutations,
  and this lap has now measured how badly.** WFG-063 removed a withdrawn claim
  (「사람 신고를 일차로」) from four documents and, like WFG-053 before it, added a
  banned-spelling gate over the surfaces. The ordering gate that preceded it was
  escaped twice, in one review, by two two-word edits from its reviewer — so this lap
  wrote the mutation list **before** the patterns and ran it against the first draft.
  **The first draft caught six of nine and missed three**, and the three misses are
  the lesson, because none is a paraphrase of the sentences the lap had just deleted:
  (a) `사람 신고가 일차**이고` — emphasis markers between the noun and its verb, the
  exact class that broke the ordering gate twice, reached for a third time by the same
  author; (b) the claim as a **rank-1 table row**, where the rank cell precedes the
  noun and sixty characters of 근거 separate them, so no proximity rule over noun →
  claim can see it at all — and that is the shape both documents actually shipped;
  (c) 「트리거의 일차 소스는 사람 신고입니다」, the claim written right-to-left.
  **Anti-pattern:** validating a claim tripwire against the sentences you just
  deleted, which are the one set of inputs you are guaranteed to catch. **Gate:** a
  claim rule ships with (i) at least one mutation carrying markup between the words,
  (ii) at least one that is a table row rather than prose, and (iii) the same claim
  with subject and predicate swapped — and the mutation list is written and run
  before the patterns, so a miss is information rather than a passing grade.
  **AND THAT GATE WAS NOT ENOUGH EITHER, WHICH IS THE REAL LESSON AND IS WRITTEN HERE
  BECAUSE THE PARAGRAPH ABOVE WAS DRAFTED BEFORE THE REVIEWER READ IT.** The lap's
  independent reviewer wrote **twenty** primacy sentences it had not seen and **nineteen
  escaped**, one of them a single token off a sentence the lap had just deleted
  (「사람 신고가 일차 **채널**입니다」). `mandela`'s reading of why is exact: a mutation set
  written by the pattern's author, in the same session as the patterns, is a scorer
  grading buckets it drew itself (leakage #4) — 「write the mutations first」 changes the
  order and not the independence. **Gate, superseding the one above:** a claim tripwire is
  never the deliverable. Ship a **structural** rule beside it — for this class, 「any
  sentence naming both a priority word and a trigger-source noun must carry a negation」,
  which holds whatever words the next author picks — and let the spelling list be only the
  copy-paste ratchet it actually is. And check first whether the repository already owns
  the structural rule: it did. `tests/test_finals_screen.py` had carried exactly this rule
  for one file since the WFG-017 lap, its docstring saying 「a spelling gate inherits its
  own corpus … the next author uses a synonym」, and this lap wrote a second spelling list
  instead of pointing it at four more surfaces. Underneath all of it, the standing
  generalisation: **proximity in one direction is half a rule**, per-row hand-rolled gates
  keep re-learning this, and that is WFG-062's case, now with a measurement attached.
- 2026-09-04 · dev · **Citing a line number ages a document faster than citing a
  section.** Adding two `<!-- forbidden-ok: -->` pragma lines to `docs/detection_floor.md`
  moved the 99 % ban from `:310` to `:311` and silently invalidated four live
  cross-references — two of them in the Q&A bank the student recites from, one in a
  test docstring. Nothing failed; the references simply began pointing one line above
  the paragraph they name. **Anti-pattern:** `file.md:NNN` in prose that will outlive
  the edit that produced it. **Gate:** judge-facing prose and test docstrings cite a
  **section** (`docs/detection_floor.md` §10); a line number is for a report, a backlog
  row or a critic finding, which are records of a moment and are expected to age.
  Corollary from the same lap: a pragma is a comment, and an HTML comment on its own
  line **inside** a paragraph, or between a table separator and its first row, splits
  the block when the document is rendered. These are documents a student reads on
  paper — a mid-block pragma goes inline at end of line, where it is invisible in both
  the raw file and the rendered page.
- 2026-09-04 · dev · **A section's first sentence is the one nobody re-reads, and it is
  where the withdrawn claim survives.** WFG-063 narrowed five surfaces and left
  `docs/detection_floor.md` §0 line 13 asserting 「탐지는 사실상 전부 사람」 — a stronger
  version of the very claim it had spent the lap withdrawing — because the lap read the
  section it was editing (§10) and not the section that motivates it. WFG-069 fixed that,
  and found the identical shape one line into §10 itself: 「측정이 우선순위를
  정해줍니다」, the opening of the section whose own two ⚠ blocks say the table is not a
  priority table. Two sections, same file, same defect, and both survived a gate, a
  reviewer and a critic pass. **Gate:** when a claim is withdrawn, the sweep is not
  「grep the claim」 but 「read the **opening paragraph** of every section of every file
  that carries it」. A document's motivation paragraph and its section leads are written
  once, early, and then inherited; they age exactly where the argument moves under them.
- 2026-09-04 · dev · **「My gate is a different instrument, so the last gate's score does
  not apply to it」 is the third form of the same mistake, and it scored 12 of 20.**
  Critic #9 measured the previous lap's spelling gate at 2/20 against sentences its author
  did not write. This lap wrote a gate over a *closed, enumerated registry of literal
  figures* (CHARTER §3 rule 5b: a block printing an external figure must name its agency,
  as-of date and scope) and argued in the test file's own docstring that the 2/20 result
  could not transfer, because 「escaping it requires not writing the figure」. The reviewer
  measured it: **12/20**. A closed registry closes the set of *figures*; the escapes were
  in the set of *spellings*, which no registry closes — a line wrap between the number and
  its noun (this repository hard-wraps every Korean paragraph), 「99 퍼센트」, 「99.0 %」,
  a table row licensed by a label in a different row of the same table, Korean numerals,
  and the entire 「최초 발견 0건」 half of a two-part figure, which the gate could not see
  because it looked only for the other half. **Anti-pattern, and it is about argument
  rather than regex:** a novel-sounding reason why the last measurement does not apply to
  this instrument, offered *instead of* measuring this instrument. The reason may even be
  right about the mechanism and still be wrong about the number. **Gate:** every claim
  gate ships with a catch rate measured by someone who has not seen it, printed in the
  report as a number, before the report says the gate is strong — and the escapes it
  cannot close are parametrised as *still open* so a later widening cannot quietly claim
  them. Guarding a *number* rather than a *claim* is still the better shape here — six of
  the eight escapes closed in one edit, which a spelling family never does — but that is a
  reason to prefer it, not a reason to skip the measurement.
- 2026-09-04 · dev · **A pragma that need not say why is a licence nobody reads twice.**
  F48 sat underneath a bare `<!-- forbidden-ok: 99 % 목격 신고 -->` written deliberately,
  in the same lap, with the reason recorded 300 lines away in §10 and not at the licence.
  The new `scope-ok` pragma refuses a reason under twelve characters. Not a strong
  mechanism — a lazy author writes twelve lazy characters — but it costs one line and it
  puts the question 「what is this licensing, and why is that all right?」 in front of the
  person granting it, at the moment they grant it.
- 2026-09-04 · dev · **Every claim gate in this tree was written in Korean, and the
  clause admitting it was read three times as a scoping decision instead of a hole.**
  `tests/test_detection_ordering_is_not_claimed.py` carried 「any of it in English,
  anywhere — no English pattern is gated」 in its own docstring, in two places, from the
  lap that wrote it. Three laps read that, agreed with it, and moved on; critic #9 then
  certified a window clean by 「grepping every `.md` and `.html` in the tree」, in Korean,
  and the withdrawn claim was alive in English in the student's own drill material under
  a heading promising 「the answers that survive the verdicts」. **Anti-pattern:** a
  stated limit is not a discharged one. A docstring sentence saying what an instrument
  cannot do is a *finding to be scheduled*, and the moment it is written it should
  produce a backlog row, not just a clause. **Gate:** when a lap writes 「this rule does
  not cover X」, it names X in the report's next-row line, and the row says what covering
  X would cost. Otherwise the honesty is load-bearing for nothing: it documents the hole
  for the reader who already knew and hides it from the one who did not.
- 2026-09-04 · dev · **Predict the catch rate before you measure it, in writing, because
  being wrong is the whole signal.** This lap froze the English rule's patterns, wrote
  sixteen fresh sentences afterwards, and predicted 11 of 16 in the test's own docstring
  before running it. It scored **8**. Two sentences it was sure of escaped, one of them
  for a reason no amount of re-reading would have surfaced: the semicolon split that lets
  the rule see `R3_science_gaps.md:22` also splits 「Residents call first; the satellite
  catches up 22 minutes later.」 into two halves with one side of the comparison each, so
  a rule requiring both sides then sees neither. **The instrument's own design decision
  bought one real instance and cost one natural sentence, and nothing but grading it
  after freezing it would have shown that.** Writing the prediction down first is what
  converts a grading run from a formality into an experiment — a rate that matches the
  guess teaches nothing, and this one did not match.

- **2026-09-04 (laptop):** a hand-resolved rebase committed conflict markers into `docs/auto/STATE.json`; the gates did not read the file and stayed green. Rule: after any rebase touching `docs/auto/`, parse STATE.json and LOOP_CONFIG.json before committing (`tests/test_auto_state_parses.py` now enforces it).

- 2026-09-04 · dev · **A gate that asks "does it exist?" when it means "can anyone reach
  it?" reads green on the only machine that could have caught the bug.** WFG-067's
  done-when proposed one line, `git cat-file -e <stamp>`, against a finals screen printing
  a commit id that a rebase had orphaned. `cat-file -e` answers from the object database,
  and a rebased-away commit is still *in* the object database until `gc` runs — so on the
  laptop or sandbox that created the defect the proposed gate passes, and it only goes red
  in the fresh clone, which is where nobody looks. Measured this lap against five stamps:
  existence scores **4 of 5**, missing exactly the orphan case the row exists for;
  reachability (`git merge-base --is-ancestor <stamp> HEAD`) scores 5 of 5. **Anti-pattern:**
  a predicate whose failure mode is invisible from where it runs. **Gate:** when a check is
  about a *record other people will resolve*, grade it in the state those people will be in
  (fresh clone, no local objects, no cached credentials), not in the working tree.
  The prediction written down first was 3 of 5 and the measurement was 4; the miss is
  recorded in the test's own docstring rather than edited away.
- 2026-09-04 · dev · **The first draft of that gate skipped on `--is-shallow-repository`,
  which would have switched it off in the cloud sandbox — the exact place the defect is
  made.** The sandbox clone is flagged shallow and is 294 commits deep, plenty for an
  ancestor check on a stamp built the same lap. A cautious skip is not free: it converts a
  gate into a comment everywhere the loop actually runs. **Gate:** before adding a `skip`
  to a new check, run it in the sandbox and ask which of the loop's own environments the
  skip fires in; a skip that fires in all of them is a gate that was never written.
- 2026-09-04 · dev · **A number inherited from another lap's finding is an unregistered
  number, and it does not feel like one.** Critic #11's F54 said the mis-cut subset was
  「about 45 km」 from 영덕. This lap said in its own summary that it had re-measured the
  finding 「rather than taking it on trust」 — and it had, but only the part that was
  load-bearing for the *conclusion* (0 of 239 points inside the box). The 45 km travelled
  unchecked into `docs/NUMBERS.json` on eight entries, into two NEEDS_HUMAN amendments
  addressed to the author, into the plain-terms section written for the reader least able
  to check it, and into a `assert "45 km" in head` string pin that would have broken the
  suite for the first lap that computed the real value. The independent reviewer computed
  it: the nearest point is **30.5 km** from the box, the farthest 65.6; no construction
  over those files yields 45. **Anti-pattern:** 「I verified the finding」 meaning 「I
  verified the claim the finding supports」. A finding is a set of numbers and the ones
  that do not carry the argument are exactly the ones nobody re-derives. **Gate:** every
  figure copied out of another lap's report is either re-derived in this lap, or deleted —
  and the containment claim is the test of whether it was ever needed: this one needed no
  distance at all.
- 2026-09-04 · dev · **The lap that fixed a report naming an unreachable commit shipped a
  report naming an unreachable commit, twenty minutes later, by the same mechanism.**
  `report.py` rendered 「head `e560d39`」, which was true then; `git pull --rebase` before the
  push put another lap's report underneath and rewrote `e560d39` into `4745920`. In this
  sandbox `git cat-file -t e560d39` still answers `commit` and
  `git merge-base --is-ancestor e560d39 origin/auto/dev` fails — the exact orphaned-but-present
  state the lap had just written a gate for, in the lap's own prose, where no gate looks.
  **Gate:** the rebase in §4 step 8 invalidates every commit id rendered before it, not only
  the one inside `web/finals.html`. After the final `git pull --rebase`, re-render or re-check
  each id in the report and the email before either is pushed or sent; the cheapest form is
  `git merge-base --is-ancestor <id> origin/auto/dev` on every short hash the report prints.
  Corrected in place with the old value quoted, not deleted.
- **2026-09-04 (laptop, NH-022):** a subset cut by an administrative code was 45 km from the study area and a layer that must exist there (tsunami sites on a coast) came back empty; the empty layer was written up as a fact. Rule: after cutting by any code, assert the set sits in the region's committed box and spot-check a text field (address); an empty layer that should not be empty is a wrong-filter signal.

- **2026-09-04 (laptop, NH-023):** `git add -A` swept a contact list another session had left in the working tree into a public commit. **Rule:** a lap stages the exact paths it made (`git add <paths>`), never `-A` or `.`; before every commit, `git status --short` must show only files the lap can name; a CSV or list containing email addresses or phone numbers never enters the repository, and a check for that is WFG-077.

- **2026-09-04 (laptop, NH-023):** a bare `git add -A` during a conflict resolution swept another agent's harvested contact list into a public commit; the author force-pushed a purge (`6f33eca` → `c65dc56`, `ced9430` → `3d77e01`; every id in `docs/auto/` was remapped the same night). Rules: stage by path, `git status --short` before each commit, one agent per clone (CHARTER §3c).

- 2026-09-04 · ci-red · **The gate written to grade a gate was itself machine-dependent, and
  it failed in the one place that is supposed to be independent.** `test_finals_screen.py`'s
  WFG-067 grading test builds an unreachable probe commit with `git commit-tree`. Every other
  `git` call in that file only READS the object database; that one WRITES, and git will not
  write a commit without a committer identity. Every machine the loop builds on carries one,
  so the test was green in the sandbox and on the laptop; `actions/checkout` configures none,
  auto-detection on a runner yields `runner@<host>.(none)`, and git refuses it. `commit-tree`
  printed nothing, `assert orphan` failed on `assert ''`, and `auto/dev` sat RED for six
  consecutive pushes (runs 86-91) on a fact about the machine rather than about the code. The
  bisect is exact: the test arrived in `deeb147`, which is not an ancestor of `fdab7bc` (run
  85, last green) and is an ancestor of `201c554` (run 86, first red). Fixed in `21b8740`.
  The irony is worth keeping: the lap that wrote this test also wrote the MEMO lesson above
  about a skip that would have fired *in the sandbox*, then shipped a gate that fires *only
  on CI* — the same blind spot, mirrored. **Anti-pattern:** 「the suite is green here」 read as
  evidence about a clean machine, when the test consults machine state. **Gate:** a test that
  shells out to `git` is classified read or write before it is committed; every write supplies
  its own identity inline (`git -c user.name=… -c user.email=… …`) and never inherits one.
  More generally, when a new test touches the environment — identity, clock, timezone, locale,
  hostname, `$HOME` — run it once with that piece removed before pushing. For identity that is
  one line, and it reproduces this failure exactly:
  `env GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_CONFIG_COUNT=1
  GIT_CONFIG_KEY_0=user.useConfigOnly GIT_CONFIG_VALUE_0=true pytest <file>`.

- 2026-09-04 · ci-red · **Two laps diagnosed the same red and wrote the same fix; the second
  one had gated it before it learned the first existed.** `origin/auto/dev` was still
  `e4a7304` when this routine fetched, and still `e4a7304` when it committed; `21b8740`
  landed during the ~15 minutes of `gates.py --mode full`, and the collision surfaced only at
  `git pull --rebase`, as a conflict in the one file both had edited. Both fixes were the
  same fix (identity supplied inline on `commit-tree`), so nothing was lost but the duplicated
  run. This is NH-007's failure with a new clock: a claim marker cannot help here, because a
  red CI run is claimed by nobody. **Gate:** a red older than one push is probably already
  being fixed. Before starting, the ci-red routine re-reads the CI list and stops if a *newer*
  run is queued or in progress on a *newer* head; and after any gate run longer than a few
  minutes it re-fetches `origin` before committing, not just before pushing. When the fix is
  already upstream, the routine verifies it rather than re-landing it — the verification is
  the contribution, and the duplicate commit is not.

- **2026-09-04 · dev lap 1817Z · the same red, diagnosed twice — and the second write-up quoted an error message it had not read.** The entry above is the fuller account and it landed first; this one keeps only what it does not say. **First:** CHARTER §4b lists what a test may not depend on — the local clock, the timezone, the network, files outside the repository — and this failure adds a fourth member that was missing from the list: **ambient tool configuration**. When a test shells out to a tool, ask what that command reads besides its arguments and the repository; if the answer includes anything in `$HOME`, pass it explicitly. **Second, and the one that cost something:** this lap's first draft of this entry, and of the comment in the test, quoted git's runner stderr verbatim — `got 'runner@fv-az….(none)'` — as an observation. It was not one. `_git` uses `capture_output=True` and the old assertion discarded stderr, so run #91's log holds only `AssertionError: could not build the orphan probe / assert ''`; the quote was reconstructed from the local reproduction, which actually prints `got 'root@vm.(none)'`. The independent reviewer caught it. **Rule:** name the machine a quoted error came from, every time. A reconstruction is easiest to ship as evidence precisely when it is correct, and §3.5 does not have an exception for correct fabrications.

- 2026-09-04 · dev lap 2119Z · **Three findings in a row were the same finding, and nobody
  named it: the gate was pointed at a LIST OF FILES.** WFG-063 found the withdrawn rank
  table in 「a session report nobody had listed」; WFG-070 found the same claim alive in
  English in two research files and then a third the row itself did not know about. Each
  time the fix was to widen a pattern or add a filename, and each time the next escape was
  another filename. The union of the five hand-written guard lists was **11 files** against
  **988** tracked documents. **Anti-pattern:** a content gate whose scope is enumerated.
  Enumerating what a rule *covers* means the rule's coverage decays every time somebody
  writes a new document, silently, and the decay is invisible in a green suite — the suite
  is green precisely because the new file is not in the list. **Gate:** a content rule
  states what it EXCLUDES, with a reason per exclusion, and reads everything else; the size
  of the exclusion class is pinned in a test, so it cannot grow without someone editing the
  number and the document beside it. The corollary that cost this lap ten minutes and is
  worth more than the row: **the first whole-tree run of a rule you have only ever run on a
  list is a measurement, not a formality.** It found 11 unlicensed mentions in two files,
  and then it failed on the document written to describe it. A rule that does not fire on
  its own paperwork was never scoped honestly. **And the pin that guards the exclusion class
  must be on what a HUMAN edits, not on what the class currently contains:** this lap's first
  draft pinned the record class at its 73 files, and `docs/auto/reports/` gains a file every
  lap — it would have gone red on the push that carried it, and on every push after. Caught
  by re-reading the diff for what CI would reject, before the second gate run, which is the
  step CHARTER §4 step 8 exists for.

## 2026-09-05 — an untracked file is invisible to the gate, and a key in the page is not a value on the screen

Two lessons from WFG-003, both handed over by the lap's own independent reviewer.

**1. `gates.py --mode full` on a working tree with untracked files is not a gate run.**
This lap wrote `docs/auto/DEMO_SCRIPT_5MIN.md`, ran the full gates on the working tree,
read **ALL GREEN**, and only then committed. `check_number_collisions.py` — like
`check_forbidden.py` and `check_withdrawn_claims.py` — walks **tracked** files, so a file
that is `??` in `git status` is not scanned. The commit turned `make verify` red with four
collisions that had been sitting in the new file the whole time. CHARTER §4 step 8 already
says «the commit you push is the commit the gates read»; what it did not say, and now does
here, is that **the trap fires before the commit as well as after it**. Three laps have now
been caught by a version of this. **Gate:** a lap that creates a *new* tracked file runs
`git add` on it **before** the first `gates.py` run, not after — staging is free, and an
unstaged new document is a gate blind spot, not a clean tree. The cheap tell is
`git status --short` showing `??` next to anything the gates are supposed to read.

**2. A registry key inside `web/finals.html` does not mean a judge can see the value.**
`build_finals.py` embeds the entire registry slice as one JSON blob, so **every** declared
key appears in the built page exactly once whether or not any card draws it. This lap
labelled four rows of a booth script 「화면」 on that evidence and wrote a test that asserted
the same wrong thing, so the test passed and agreed with the error. Two of the four were
actively contradicted by what the screen really renders — the terrain card shows +26.6 %
where the script had the student say 15.14 %, and the dispatch card shows 3.6 % where the
script said 0-of-180 「화면에 그대로」. **The template, not the built page, is the evidence
that a value is rendered**: `scripts/finals.template.html` referencing the key is what puts
a card on screen. **Anti-pattern:** testing presence in a build artifact that contains a
serialised dump of everything the builder *considered*. Presence in a dump measures the
dump, not the product.

**3. And the grading of a gate is only as wide as the surface it reads.** This lap graded
its own test 6 of 6 against six mutations. All six edited the mapping table, which was the
only thing the test parsed; the reviewer broke it in one edit by changing a spoken number
in the body and leaving the table alone. **Gate:** when a document has a summary table and
a body, a test over the table must also assert that the **body is covered by the table** —
otherwise the table is a self-portrait. After that assertion, 10 of 10.

## 2026-09-05 — a marker placed by position, and a gate that counted instead of measuring

**1. When a rule places a marker by position, fixing the two bad markers fixes nothing.**
`DEMO_SCRIPT_5MIN.md` §1 said 「넘치면 그 구간의 **마지막** 문장을 버리고」 — when you run
long, drop the segment's *last* sentence — and marked those sentences **[버림]**. A segment
written with the caveats-first discipline this repository requires *ends on its caveat*, so
the rule mechanically put the "drop this first" marker on the sentence that was holding the
claim honest, in two of the three segments that have one. Critic #15 found the two
instances; the row would have been fifteen minutes of moving two markers. **The rule is the
defect**, and the next segment anyone writes would have reproduced it. **Gate:** when a
convention selects an element *by position* (last, first, longest, topmost), ask what a
correctly-written instance looks like — if the correct writing puts the wrong thing in that
position, the convention is generating the bug, and the fix is the convention plus a test on
the property (here: a **[버림]** marker must sit on a line carrying a number the document's
own source table covers). **Anti-pattern:** a positional rule standing in for a semantic one.

**2. A gate that registers a count of someone else's prose goes red when that prose moves,
and the red is the gate's, not the prose's.** `tests/test_detection_ordering_is_not_claimed.py`
asserted that `paper/manuscript.md` had **exactly one** English ordering hit — a sentence
inside a `[GAP: …]` marker, which is the paper *refusing* the claim. The paper routine, which
owns `paper/` and touched nothing else, rewrote that marker; the count went 1 → 0, which is
**strictly safer**, and `auto-gates` run 109 went red on `auto/dev` for a change that improved
the thing being guarded. **Gate:** assert the *property*, not the *census* — "at most one hit
and any hit sits inside a GAP marker" catches everything `== 1` caught and nothing it should
not. **Where a census is genuinely the point** (the 11-vs-1 design comparison in the same
file), keep it, but write the re-registration procedure into the docstring, which that one
did, and it is why re-registering to 8/0 was a five-minute change rather than an argument.
**Corollary for a multi-routine repository:** a dev lap's own baseline can be green and the
branch red one minute later, because four routines push to `auto/dev`. Read the newest
`origin/auto/dev`, not the head the lap started from, before believing a green quick gate.

## 2026-09-05 — two routines fixed the same red, twenty minutes apart, and neither could see the other

The `wfg-autoloop-ci-red` routine woke on `auto-gates` run 110 and spent forty minutes
reaching the same diagnosis and the same re-registration (8/0) that the 0404Z dev lap had
already pushed at `3b174c2`. Both were right; one was redundant. **The cause is structural:**
CHARTER §4 step 3 gives a dev lap a claim marker pushed before the work starts, and a red
run is the one piece of work in this loop with **no claim surface at all** — the ci-red
routine has nothing to write and nothing to read. It fetched `origin/auto/dev` at the start,
which is exactly when the other lap's fix did not exist yet.

**Gate:** a routine whose trigger is a failure must re-fetch `origin/auto/dev` and re-check
the failing gate **immediately before it commits**, not only at bootstrap — the same
re-fetch CHARTER §4 step 3 already requires after a claim, applied to the other end of the
lap. Cheap version: `git fetch origin auto/dev` and re-run the one failing test at the new
head. Had this lap done that at the 40-minute mark it would have found the branch already
green and spent the remaining time on the finding below instead of on a duplicate diff.

**What survived the collision is the reason the duplicate was not wasted.** Two laps read
the same failure and stopped at different depths: the dev lap recorded that variant A lost
three hits because "the prose moved", which is true; this one measured *which* three and
found the mechanism — `2b7c3a0` rewrote 「rather than」 to 「not」, and `\bnot\b` is in
`EN_NEGATION_PATTERNS`, so the **shipping** rule now treats an unrelated negation as a
withdrawal (WFG-099, three mutations, all missed). A second reader of the same red is worth
something; a second *writer* of the same fix is not.

## 2026-09-05 — a budget nobody had done the arithmetic for, and a tokenizer that was allowed to say "I don't know"

**1. A gate that checks a sum is not checking the split.** `tests/test_demo_script_5min.py`
asserted the booth script's six segment times **sum to 300**, and it had been green since the
document was written. That assertion is equally true of 25/45/55/75/55/45 and of six fifties;
it never touched the question the document's own §5 was making a claim about, which is whether
each segment gets seconds in proportion to what it asks the student to say. The real budget was
1.62x out, and the segment that had to be spoken fastest was the limitations close — last, and
therefore the first thing an over-running clock deletes. **Gate:** when a document states a
*total* and a *split*, a test on the total is not a test on the split, and the split is usually
where the claim lives. Ask what the assertion would still allow.

**2. Let the counter refuse.** The one design decision that made this measurement trustworthy
was making the tokenizer raise on a token it has no reading for, instead of scoring it zero. It
fired on the very first run (`pooled`, in the limitations close) and would have quietly
under-counted the segments densest in symbols — the same segments whose seconds were most in
dispute. **Anti-pattern:** a parser that treats "I do not recognise this" as "this is worth
nothing". The failure is silent, and it is biased rather than random: it always under-counts
the *unusual* input, which is the input you built the measurement to look at.

**3. When a method has a judgement call in it, run it both ways and print the difference.**
Rather than argue whether `%` is pronounced 퍼센트, the lap ran the count with the lexicon on and
off: 1,684 vs 1,627 syllables, and a six-segment budget that differs by **at most 3 seconds of
300**. That converts an unfalsifiable methods argument into one line of a table, and it is
cheaper than the argument. **Gate:** a derived number whose method contains a convention gets a
sensitivity row, not a defence.

**4. The lap that writes the warning is the lap that commits the error.** This one wrote
「the two sets of figures are not interchangeable」 into the doc and had, three paragraphs
earlier, already written 「4.24에서 7.29까지」 — critic #16's slowest segment paired with its own
fastest. No gate would have caught it, because both numbers are real and neither is registered
prose. Self-read before the reviewer, not after.

## 2026-09-05 — a finding names one file because that is where the critic was looking

WFG-103 was filed as one sentence in `docs/auto/DEMO_SCRIPT_5MIN.md`. The same false sentence
was also in `web/finals.html`, in the branch of the STATIC VIEW caption that the demo region
actually takes, in both Korean and English — and the *other* branch of the same ternary had it
right, which is why no reader of either branch alone would notice. The critic found the defect
by reading the booth script, so the finding is the size of the booth script.

**Gate:** before fixing a wrong sentence, grep the repository for the claim, not for the
sentence. The claim here was 「the baseline sees the current fire」; grepping the distinctive
phrase 「지금 이 순간만 보는」 found the screen, and grepping the concept would have found it
faster. A judge-facing claim that is wrong in one place is wrong wherever it was copied, and
the loop copies prose between the script, the screen, the Q&A bank and the manuscript by hand.

**The second half, which is about how findings are written:** a `fix-before-next-row` item
that names a file and a line number invites a lap to fix that file and that line and stop.
Critic #17's item said 「one sentence」 four times. It was right about the defect and wrong
about its extent, and a dev lap that had obeyed the letter would have shipped the screen still
saying it. **Read the finding's claim, then find its instances yourself.**

## 2026-09-05 — the test that identified its subject by sort order

`test_the_artifact_the_registry_points_at_is_committed_and_current` picked the pace artifact
with `sorted(glob("pace_*.json"))[-1]`. The intent was 「the newest measurement」; the
implementation was 「the last filename alphabetically」, and those diverged the moment a
`pace_before_039a0de.json` was added beside the `pace_2026…` stamps — `b` > `2`. So for two
laps the test compared the **before** artifact against the live document, and it stayed green
only because the two totals were equal at 1,684 by coincidence.

**Anti-pattern:** identifying an artifact by position in a sorted listing when the thing you
mean has a name. The failure is silent, it survives review because the assertion body is
correct, and it breaks exactly when the quantity under test finally changes — i.e. on the
first run that matters.

**Gate:** a test pinned to 「the current X」 selects X by the same key the registry, the doc or
the config uses (here, `TAG`), never by `[-1]`, `[0]`, `max()` over filenames, or mtime. If
there is no such key, that is the defect.

## 2026-09-05 — the step-2 CI check in the routine prompt cannot run in this sandbox

CHARTER §4b and the dev routine prompt both give the GitHub Actions check as
`curl -s 'https://api.github.com/repos/.../actions/runs?...'`. In the cloud sandbox that
returns **HTTP 403** from the agent proxy (`GitHub access is not enabled for this session. An
org admin must connect the Claude GitHub App`), and `curl -s` prints the JSON error body with
exit status 0, so a lap that pipes it into a parser gets an empty result and can read that as
「no runs, nothing red」. The GitHub **MCP** works and is what CHARTER §4b's own text says is
available in the sandbox (§4 「Sandbox facts」). **Use `mcp__github__actions_list` for the
step-2 check; if a lap does use curl, it must read the HTTP status, because a silent 403 here
looks exactly like a clean branch.** Filed as a MEMO note and not a row: CHARTER §14b holds
loop mechanics behind R1, R3, R7, R8, R9.

## 2026-09-05 — a procedure is a set of claims, and the only way to check one is to run it

WFG-037 asked for a booth recipe. The cheap version of this row is a well-organised document
assembled from `README_KO.md`, `docs/ENVIRONMENT.md` and the Makefile — plausible, tidy, and
never executed. This lap ran every command it was about to write down and read the exit code,
and three of them did not behave the way the repository's own prose said they did:

1. **`make all-checks`** — named by readiness line R3 as the booth-laptop check — aborts at
   `baseline-verify`. Four of its six differences are tracked-file drift that will abort it on
   the author's laptop too. Eighteen critic windows had recorded 「WARN, expected off-laptop」,
   which is true of the other two lines and was read as covering all six (NH-029).
2. **`make finals-bundle`** does not check a USB copy, although the Makefile comment, the
   builder's docstring, `docs/finals_bundle.md` and the bundle's own Korean README all said it
   did, in four different wordings. `assemble()` overwrites the folder from the tree before
   anything is hashed. Seven bytes appended to the bundle's `finals.html`; the run printed `OK`.
3. **The builder never enumerates the folder it certifies.** The new copy checker found a stray
   file in `release/` *seconds after* a green builder run (WFG-108).

**Anti-pattern:** writing a procedure from other documents. Every sentence of a procedure is a
prediction about a machine, and the documents you are copying from are predictions too — the
false claim in (2) had been copied four times without anyone running it once.

**Gate:** a row whose deliverable is a set of steps runs every step it can, in the lap, and
marks the ones it cannot with what stands in for them. `tests/test_booth_setup.py` holds the
mechanical half — every path resolves, every `make` target exists, every key the document
teaches is bound in `web/finals.html` — so the next lap that rebinds a key or renames a target
turns the recipe red instead of turning the booth silent.

**Second lesson, cheaper and sharper: `git checkout -- <file>` during a mutation test throws
away the lap's own uncommitted work.** Grading `tests/test_booth_setup.py` meant breaking
`scripts/build_finals_bundle.py` and restoring it, and the restore was `git checkout`, which
reverted the two edits this lap had made to that file and had not yet committed. Caught by the
harness telling me the file had changed on disk. **Restore a mutation from a copy taken before
it (`cp file /tmp/x.bak` … `cp /tmp/x.bak file`), never from git, unless the file is committed.**

**Addendum, the same lap, written after its reviewer blocked it.** The lesson above says not to
write a procedure from other documents. This lap then did exactly that in one line — §5.6's
「우상단 언어가 **KO** 인지 확인합니다」, copied from the bundle README and the demo script, never
run, and false: `web/finals.html` labels the language button with the language a press switches
**to**, so a Korean screen reads `EN`. Following the step literally switches the judged demo into
English. **The anti-pattern is not a habit a lap can decide its way out of;** it survived being
written down as the lap's own lesson, in the same commit. What catches it is the executable
check, and the reviewer's second finding says which kind: my key table pinned bare `case` labels,
so a key rebound to a different action left the table green. **A gate on a document's claim about
code must pin the behaviour the document promises, not the token it names** — the label together
with what it does. A booth does not suffer a deleted `case`; it suffers a key that now does
something else.

## 2026-09-05 — a finding names two lines; the defect is the identity those two lines broke

WFG-109 arrived as a precise finding: `scripts/finals.template.html:1378` and `:1381` carry
a sentence the built screen no longer carries, fix them. Its `done when` asked for a test
that "asserts the template and `web/finals.html` carry the same STATIC VIEW captions". That
test would have been green, correct, and worth almost nothing: it pins the two lines this
bug happened to land on, and the next hand-edit to any other generated line survives it
exactly as this one did.

What the builder actually promises is much stronger and just as cheap to assert.
`build_finals.py` reads the template and replaces **one** placeholder line with the payload.
So the two files are a **line-for-line identity outside that one line**, and asserting the
identity costs the same as asserting the two captions. Graded against seven mutations, three
of them — an unrelated generated line edited, a line deleted, the template committed as the
screen unbuilt — pass the caption comparison and fail the identity.

**Gate:** when a finding names specific lines in a generated file, ask what invariant the
generator promises about the whole file, and assert that instead. Then look for the second
file with the same generator shape: `web/console.html` has the identical placeholder
mechanism, was clean, and is now held there for one table row.

**Anti-pattern, and it is the one the row itself contained:** writing the test the finding
asked for. A `done when` is written by whoever found the bug, from the bug; it is a floor,
not a ceiling, and a lap that treats it as the specification inherits the finder's sample
size of one.

**Second lesson, on the ledger rather than the code.** `decisions.py apply` places a closure
line at the end of the entry it belongs to — replaying NH-028 against `8a8a940` proves it.
But an apply run on a checkout whose last entry is NH-028, merged afterwards with the NH-029
a cloud lap pushed below it, leaves the closure at the end of the *file*, inside a different
entry — and `decisions.py list` then reads the author their answer to one question as an
option of another, still-open one. **On a 3-hour cadence, a tool being correct is not the
same as its output being correct**, because a stale checkout plus a clean rebase produces a
file no single writer would have written. Verify the ledger's shape, not the writer's logic
(WFG-112).

**Addendum, same lap, written after its reviewer blocked it — and it is the same shape as the
WFG-037 lap's addendum, one slot later.** The entry above says a tool being correct is not the
same as its output being correct, and that a lap should verify the shape rather than the
writer's logic. In the same commit I wrote, in the *disclosure* paragraph of the new gate:
「that line's content is looked at by `verify_numbers.py` and `check_forbidden.py`」. Neither
sentence survives being run. `verify_numbers.py` never opens `web/finals.html`; `check_forbidden.py`
reads it but skips every numeric rule on `.html` by design, counting the skips into a dict named
`payload_skips`. The reviewer changed `"n_entries": 326` to `999` on line 434 and every gate I had
named stayed green.

**Two things this makes concrete.** First, the anti-pattern is not cured by writing it down: two
consecutive laps wrote the lesson and then broke it inside the same commit. What differs is where
it lands — both times in the paragraph that *discloses a limitation*, which is the one place a lap
is reasoning from memory about other people's code instead of from a command it ran. **So: a
sentence naming which gate covers a hole is a claim about a program, and it is verified by running
that program against the hole, never by reading the gate's name.** Second, the exemption a new gate
grants itself is load-bearing from the moment it is written: WFG-109 made line 434 the one exempt
line, and that same line is where every judged number lives (WFG-113).

---

## 2026-09-05, 20260905T1820Z dev lap (WFG-114) — I invented a limitation, and the reviewer broke it in 103 seconds

The lap's biggest lesson is not the experiment. It is that I wrote a **false limitation** into a
document, a script docstring, a registry caveat on 40 keys, a backlog row and this file, and every
gate stayed green, because no gate can check a sentence that says a file does not exist.

I needed the canonical arm's SRTM raster. I looked at `data/raw/firms_data/`, found it absent,
remembered that `data/raw/**` is git-ignored, and wrote: 「the canonical arm cannot be rebuilt in a
cloud lap」. Then I built the whole experiment on the flat arm instead and reported against **96**
when the author's row, and the author's decision, had asked about **91**. The independent reviewer
ran `git ls-files data/snapshots | grep srtm-dem` and the raster was right there — committed, with
a MANIFEST entry naming that exact `data/raw/` path as its `origin_path` and the same sha256.
**CHARTER §4 "Sandbox facts" tells every lap to work from `data/snapshots/` for precisely this
reason, and I had read it that morning.**

**The anti-pattern: absence checked in one place is not absence.** I confirmed a file was missing
from the location I happened to think of, and promoted that into a property of the environment. The
snapshot store exists BECAUSE `data/raw/` does not survive a clone; the very fact I used to justify
the limitation was the reason the workaround exists. Before writing 「X is not available here」, run
the search that would find X if it were: `git ls-files | grep`, then the MANIFEST, then say it.

**And the second-order damage is what makes it worse than a wrong number.** An invented limitation
propagates as *humility*, so nothing challenges it: it went into a caveat on 40 registry keys, where
it would have been quoted as a known constraint by every later lap and by the paper routine. A wrong
result gets checked. A wrong reason for not having a result does not. **CHARTER §3.5 forbids
fabricated evidence; a fabricated limitation is the same defect pointing the other way**, and this
lap's own MEMO entry warned the next lap against exactly that, in the same commit, about a different
row.

**The reviewer's second finding, which I would never have found myself.** The arm scored an origin
standing inside the buffer as "no route" whenever all of its neighbours were also inside — even
though a road out plainly existed. That convention **flattered this project**: every origin it
stranded counted against the fair opponent. It was worth 10 origins against a margin of 9, i.e. more
than the entire result. Fixed by routing both conventions for every origin and making the honest one
(`walk_out`: leave the buffer, never re-enter) primary, with both in the artifact. **The gate this
leaves:** `test_both_origin_rules_are_reported_and_the_honest_one_is_primary` goes red if a later lap
reports only one rule, or if the harsher rule is ever the one on the headline.

**Where the independent review earned its cost.** LOOP_CONFIG's `review: subagent` is the only reason
this lap did not push a number answering a question the author did not ask, under a limitation that
was not real. Both findings were things I could have checked in under two minutes and did not,
because I had already written the sentence. **A reviewer that only reads the diff cannot catch a
false claim about what is NOT in the diff — this one caught it by running a search instead of reading
my reasoning.** Give the reviewer the claims, not just the diff, and let it go looking.

---

## 2026-09-05, 20260905T1820Z dev lap (WFG-114), second lesson — a fair opponent needs a band, not a width

The author's row asked for one buffer (1 km) and one number. Run that way the answer is
「the present-aware arm recovers 86 of the 91 forecast-only origins」, and it is **true and
almost worthless**, because nothing in it says whether 1 km was a discovery or a coincidence.
Four extra widths, ~2 minutes of compute in the same run, turned it into a different finding:
250 m and 500 m walk **91 and 80** origins into the fire as it grows; 2 km and 3 km leave
**80 and 73** unable to finish inside the 600-minute budget; 1 km is the single crossing where the
first failure has nearly vanished and the second has not yet started. The headline number did not
change — the **claim** did, from 「a simple baseline nearly matches the forecast」 to 「a simple
baseline nearly matches the forecast if you already know the answer, and an operator does
not」. The second is defensible at a booth and the first is not.

**The gate this leaves:** `tests/test_present_perimeter_arm.py::test_the_buffer_band_brackets_the_headline_width`
refuses a sensitivity table whose reported width is its own minimum or maximum. A free
parameter reported at one value is a tuned number wearing a sensitivity check's clothes, and
the cheapest way to stop a later lap quietly re-tuning it is to require something on both sides.

**And the thing worth doing again:** the script **refuses to write** unless it first reproduces
the committed arm it stands on — all seven bucket counts, and the origin ids of every bucket the
committed artifact stores a list for (`--verify-only`; `both_safe` has no stored list and is pinned
by complement, which is what the sentence must say: 「every origin node id」 was the overstatement
this same lap had to withdraw in four other places, and restating it here as advice was the sixth
copy, found by the reviewer in the file that teaches the next lap). That check is what makes the third column comparable at all, it cost about
100 seconds, and it is the difference between measuring the question and measuring the harness.
A new arm on an old experiment should always be gated on re-deriving the old arm first.

**One consequence outside the row, and it is the dangerous kind.** This lap falsified a standing
instruction in a *different* live row: WFG-104 told the next lap to write a judge-facing card
saying 「the present-perimeter arm has **not** been run」. It has now. Left alone, the next lap
would have written a fabricated limitation into the Q&A bank in the student's own voice, and
every gate would have stayed green because no gate reads a backlog row's premise. **A lap that
changes the world a row describes must edit that row in the same commit** — the superseded text
kept as a record, never deleted (CHARTER §3.7).

**Round 2 of the same review, and the lesson that generalises past this row.** After the fixes
above the reviewer blocked again, on something neither it nor I had looked at the first time: the
committed classification scores the **fire-blind** route with no time budget, while the
forecast-aware router enforces one internally and my new arm was held to it. Two rules in one
three-column table. Two fire-blind routes arrive at 624.8 and 628.2 minutes, so the control was 265
where a consistent rule gives 263 — and because those origins counted as "already safe", the buffer
was also blamed for breaking them, so its cost read 6 instead of 4.

**Both errors ran in this project's favour, and that is the pattern to take away.** Across two
rounds every defect the reviewer found — the invented DEM limitation, the strict origin rule, the
unbudgeted control — biased the result *toward* the forecast. None was deliberate and none was
random. When a lap builds the opponent to its own headline, the opponent gets the benefit of every
unexamined default, because the defaults were all written while the headline was the thing being
defended. **So: when you build an adversary for your own result, enumerate every rule the two sides
are scored under and check them for symmetry explicitly, before measuring anything.** The gate this
leaves is `test_the_three_arms_add_up`'s budget assertion plus the artifact's
`safe_fire_blind_unbudgeted`, which keeps the superseded figure visible instead of replaced.

**And one place a withdrawn claim can hide that no gate was watching:** the artifact's own
`what_this_does_not_show` block. The v1 string ("this run is flat-timed and its denominator is the
flat arm's 96") survived the entire rewrite inside the committed JSON that 52 registry keys point
at, because it lives in a Python literal that no prose gate reads and no test asserted on. The
reviewer replaced it with 「THIS RUN PROVES THE FORECAST IS UNNECESSARY.」 and all 18 tests and
`check_forbidden.py` stayed green. A caveat surface needs a content gate, not a length check.
