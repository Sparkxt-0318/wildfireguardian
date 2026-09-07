# CRITIC_LATEST — critic #31, 2026-09-07T0206Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `3f881f6`. Window: `de7bd0a..3f881f6`, the
24 h to 2026-09-07T02:00Z.*

**Critic #30's two falsifiable tests, answered first, because both were about the dev lap.**

1. **「If the next dev lap clears WFG-148 and does not also claim WFG-134 in the same lap, then
   『clear the item, then take the next row』 does not fit in one lap and the fix is to the
   cadence.」** It fits. The 01:09Z lap closed **four** rows — WFG-148 at `786318c`, then WFG-140 +
   WFG-134 + WFG-130 at `590c29a`, plus the reviewer's three repairs at `d0a739e`. No cadence
   finding.
2. **「If WFG-134 ships without WFG-140 going red on the pre-rebuild tree first, the freshness gate
   is green by construction and the drift series reaches five.」** It went red first, and the lap
   quoted the failure text. I re-hashed all five `SOURCES` against the tree here in one process and
   every one matches. **The series is over.** No finding.

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-151 — the booth kit shipped yesterday and the release bundle a judge would be handed still
does not contain it, because the one place R9's contents were written into code transcribed four of
R9's five names and dropped the fifth.**

Measured at `3f881f6`, not read:

- `release/kcf-finals-2026/MANIFEST.json` lists **17 files** and not one of them is a printable.
- `scripts/build_finals_bundle.py:57` `PAYLOAD` names the four screens, `web/assets`,
  `web/demo-media`, `CITATION.cff`, `LICENSE`, `check_bundle_copy.py`. No PDF.
- `docs/auto/KCF_READINESS.md` **R9** asks for 「`web/` whole, **printables**, `README_KO.md` …」,
  and R9's own cell names 「the printables the line names (R7 / WFG-007 — none exist)」 as one of the
  two reasons it cannot tick. **They exist now.**
- The first kit was built at `3e92b69`, 2026-09-06T06:51Z. The bundle manifest was rebuilt **2 h
  43 m later** at `1ec1d06` (09:34Z) and gained only a new `web/finals.html` hash. `d0a739e` built
  `WFG_printables_20260907T0059Z.pdf` (33 pages, sha256 `a4970b12cdd1…`, tracked) and the bundle
  did not move again.

**Why no gate said so, and this is the part that matters more than the omission.**
`tests/test_finals_bundle.py:41` `test_the_manifest_is_committed_and_covers_every_planned_file`
compares the committed manifest to `bfb.plan()` — **the builder's own plan** — so the manifest and
the builder can agree with each other forever while both omit the same file. And `:74`
`test_the_bundle_carries_the_four_screens_the_booth_opens`, whose docstring says 「R9 names `web/`
whole」, is the **only** place R9's list is transcribed into code; it asserts the four screens, the
fonts, `CITATION.cff`, `LICENSE` and `README_KO.md`, and never the printables. That is WFG-140's
defect — a manifest read against itself — living in a second directory, one day later.

**Done when.** (a) the newest-stamp printables PDF and its manifest are in `PAYLOAD` and in the
committed `MANIFEST.json`, and `make finals-bundle` still rebuilds byte-identically; (b) a test
binds R9's **named contents** to the plan in the `R7_ITEMS` shape WFG-130 used — R9's names
resolved to paths, a written reason for anything deliberately excluded — and it is **graded red**
by removing the printables entry before the fix makes it green; (c)
`release/kcf-finals-2026/README_KO.md` says in one line what the paper in the folder is and that
the manifest carries its sha256.

**Constraints.** ⚠ No new committed bytes: `release/kcf-finals-2026/web/` is git-ignored
(`.gitignore:439`), so this does not breach DIRECTION's 「do not commit the bundle payload」. ⚠ Do
not overwrite `WFG_printables_20260906T0620Z.pdf`, `…T0032Z.pdf` or any manifest (CHARTER §3.2);
the bundle carries the **newest stamp**, and `docs/printables.md` already says why the `0032Z`
build must not be printed. ⚠ Do not edit `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`
or `docs/auto/finals/BOOTH_SETUP.md` in the same lap without rebuilding the kit (**WFG-152**).

**Then take WFG-026**, which is this lap's one row move (P1 → P0) and is the sole remaining blocker
of R7. Both are small; neither has ever been anyone's item; between them they are the whole reason
`docs/auto/KCF_READINESS.md` reads 4 of 11 for an eighth consecutive critic lap after a dev lap
that closed four rows.

## The root objection

**Every gate this loop writes compares the artifact to its own description, and the loop keeps
discovering that one directory at a time instead of once.** Three instances in three consecutive
days, one shape: `tests/test_printables.py` read the manifest against itself until WFG-140 hashed
the sources against the tree (fixed yesterday); the reviewer's `sum(pages_per_source) == pages`
found four surfaces carrying wrong numbers under the true sentence 「re-derived from the manifest
rather than retyped」 (fixed yesterday); and `tests/test_finals_bundle.py:41` compares the committed
manifest to the builder's plan, **today**.

**The cheapest test is one grep** — every test that compares a committed manifest to a builder's
plan or to itself rather than to the tree — and its first hit is WFG-151.

## Everything else this lap checked, and found clean

- `gates.py --mode full` **ALL GREEN** at `3f881f6`, exit 0 (`1632 passed, 62 skipped, 2 xfailed`,
  **cold**, 349.5 s). `--assert-head` exits 0. `--assert-reported --base de7bd0a` exits 0 over the
  whole window: 52 substantive paths, all carried by reports.
- `auto-gates` runs **171 to 190** on `auto/dev`, through the GitHub MCP: **18 `success`, 2
  `cancelled`, zero `failure`**. Run **190** at this head is `success`. No CHARTER §4b finding.
- Every **dev** report in the window carries `Reviewed by:`. The research report does not
  (**WFG-147**, unchanged).
- No author reply on either channel: 80 Gmail threads, every one a single message this loop sent;
  PR #31 has no comments. `decisions.py` was not called because there was nothing to call it on.
- Clone unshallowed before any measurement (`is-shallow-repository` = `false`, 517 commits).

## The falsifiable tests for critic #32

1. If WFG-151 ships and `MANIFEST.json` gains a printable **without** a test that goes red when
   R9's named contents are dropped from the plan, then the fix was to the omission and not to the
   shape, and the shape will produce a fourth instance.
2. If the next lap takes WFG-026 and the kit is **not** rebuilt in the same lap, WFG-152's rule
   needs to be a gate and not a sentence.
