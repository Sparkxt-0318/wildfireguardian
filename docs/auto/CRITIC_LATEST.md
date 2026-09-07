# CRITIC_LATEST — critic #33, 2026-09-07T0800Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `2896c9c`. Window: `b70e464..2896c9c`, the
24 h to 2026-09-07T08:00Z, 58 commits.*

⚠⚠ **READ THIS BEFORE YOU RUN THE BASELINE GATE.** `gates.py --mode full` is **RED** at this head in
the routine's default clone, and the red **is** this lap's item. It is diagnosed below. Do **not** read
it as CHARTER §4 step 2's 「red baseline, do not build」 and stop; do **not** make it go away by running
`git fetch --unshallow` and moving on, which is what the last lap did. Clearing the item clears the red.

**Critic #32's two falsifiable tests, answered first, because both were about the dev lap.**

1. **「If the next lap takes WFG-026 and pushes without `WC-006` in `withdrawn_claims.json`, then §3.5c is
   advisory in practice.」** **It is not advisory.** The lap took WFG-026, and
   `docs/auto/withdrawn_claims.json` holds `WC-001 … WC-006`, read here. §3.5c held under its first real
   test, and the kit's `what_this_does_not_show` now states the true exclusion reason (33 clusters, 3
   committed PDFs, regenerable) instead of the retired one.
2. **「If WFG-153(a) is fixed only in `build_printables.py` and R7's definition cell keeps 「29 … sample」,
   the vacuous binding in WFG-156 is what let it.」** Also answered in the lap's favour: WFG-156 shipped
   with an occurrence-level exemption, and R7's cell is correct at this head.

## What is green, verified rather than read, all at `2896c9c`

- **`docs/auto/KCF_READINESS.md` R7 is TICKED. 6 of 11 (R2, R4, R5, R6, R7, R9), a second consecutive lap
  with a line moving.** Kit `20260907T0705Z`: six `SOURCES` re-hashed against the tree, all six match; PDF
  sha256 matches its manifest (`d54aa6dd7802…`); `pages_per_source` sums 5+6+17+3+2+3 = **36** = `pages` =
  the PDF's own `/Type /Page` count; the stamp is in the 19-file `release/kcf-finals-2026/MANIFEST.json`;
  and the three committed `dispatch_a4.pdf` sample sheets were opened on disk. The call the 0711Z lap left
  to the critic is answered on R7's row, with its ground and its falsifiable alternative.
- `gates.py --assert-reported --base b70e464` over the whole window exits **0**: 56 substantive paths.
- GitHub Actions, through the MCP (`curl` is 403 here, WFG-119): `auto-gates` runs **182 to 201** on
  `auto/dev` are **17 `success`, 3 `cancelled`, no `failure`**; run **201** at this head is `success`.
  **No CHARTER §4b finding.**
- `verify`, `snapshot-verify`, `env-check` PASS. `baseline-verify` WARN is the documented §3d state.
- Every **dev** report in the window carries `Reviewed by:`. The research report still does not (WFG-147).
- No author reply on either channel: the Gmail search returns threads that are every one a single message
  this loop itself sent, and PR #31 has no comments. `decisions_seen.json` is unchanged.

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-119 (P1 → P0) — the gate is red on a correct tree because the finals screen's build stamp has aged
out of the sandbox's clone, and this repository wrote that sentence down before it happened.**

Eligible under §14b twice over: it is **a red gate**, and its subject is **`web/finals.html`, the finals
screen**, which §14b names as a judge-facing surface.

Measured at `2896c9c`, not read:

- The routine's default clone: `git rev-parse --is-shallow-repository` = **`true`**,
  `git rev-list --count HEAD` = **50**.
- `gates.py --mode full` exits **1**: `2 failed, 1646 passed, 62 skipped, 2 xfailed`, cold, 247.0 s. Both
  failures are `tests/test_finals_screen.py`:
  `test_the_integrity_panel_names_a_commit_this_repository_has` and
  `test_the_escape_this_gate_cannot_close_is_still_open`. Both say `web/finals.html` names commit
  **`62b58e1`**, which is not an object in this repository.
- `62b58e1` is **55** commits behind `HEAD` and was built at **2026-09-06T09:21Z**. After
  `git fetch --unshallow` (531 commits) both tests pass, the object resolves, and
  `git merge-base --is-ancestor 62b58e1 origin/auto/dev` exits 0. **Nothing is corrupt. The stamp is old.**
- GitHub run **201** at this exact head is `success`, because `.github/workflows/auto-gates.yml:22` checks
  out at `fetch-depth: 0`.
- The crossing point: at `0fc6130` the stamp was **49** back, inside a depth-50 horizon, and critic #32
  reported ALL GREEN. At `f6d8246` (2026-09-07T05:22Z) it reached **50**. Every default-clone gate run
  since has been red.

**WFG-119 predicted this, in these words:** 「once a stamp ages past 50 commits without `make finals` being
re-run the ancestry test goes RED in every sandbox while staying GREEN in CI, which checks out at
`fetch-depth: 0`」. It was filed P1 and 「parked behind R1, R3, R7, R8 and R9 by CHARTER §14b」. It fired
while parked.

**The gate is right and the tree is wrong, and this is the half two laps have now got backwards.**
`_needs_git_history` (`tests/test_finals_screen.py:526`) deliberately does not skip on a shallow clone, and
its docstring argues the residual is 「a red gate asking for a rebuild, not a wrong screen shipped」. That
argument holds. The screen a judge opens reports a build **55 commits and 23 hours stale**; `make finals`
is the remedy the failure text itself prints; and this gate is the only thing in the repository that
noticed. The 0711Z dev lap hit these identical two failures, ran `--unshallow`, wrote 「They passed once the
clone was complete; nothing in the tree was wrong」 and filed nothing.

**Done when** (all three, in one lap):

1. `make finals` is re-run on the commit being pushed, so `web/finals.html`'s `git` stamp names a **pushed**
   commit well inside the shallow horizon. Reproduce both failures **red first**, show them green after, and
   quote both in the report.
2. **The recurrence is closed rather than reset.** The branch takes on the order of 40 commits a day, so a
   rebuild alone buys about 1.3 days. Critic #26 already watched this counter reset 29 → 6 and read that as
   the row being handled. Two shapes; pick one and give the reason in the report: a gate that fails when the
   stamp is more than N commits behind `HEAD` with N comfortably under 50, catching it **before** it crosses;
   or `make finals` folded into the push path so the stamp cannot age.
3. The `_needs_git_history` docstring's premise is corrected: it says 「the cloud sandbox clones shallow (294
   commits deep, but flagged shallow)」 and this sandbox cloned at **50**.

**Constraints.** `web/finals.html` is a tracked judge-facing artifact: read CHARTER §3.2 before rebuilding
and run `scripts/check_screen_assets.py`. **Do not weaken, skip or shallow-guard either test to get green** —
that is the hole the docstring was written to refuse, and §3.9 forbids it anyway.

## The other findings, filed and not carried

- **WFG-146 is no longer a knowledge-note typo; it is printed in the booth kit** and its 「done when」 list
  no longer names every place it lives. `docs/related_work.md:104`/`:187` and
  `docs/auto/finals/RELATED_WORK_PANEL.md:43` date the 사이언스타임즈 article **2026-02-12**. I re-fetched
  the page: its byline and its 저작권자 line both read **2026-02-13**, twice; the three `2026/02/12` strings
  on it are 연합뉴스 image CDN paths and the wire id `AKR20260212072300063`, the **original's** date, which
  사이언스타임즈 republished a day later. The repository has paired one publisher with another's date, which
  CHARTER §3 rule 5b makes load-bearing. The panel is `SOURCES[5]` of the current kit, 3 of its 36 pages,
  and it is on the stick. ⚠ **This now needs a lap that rebuilds the kit** (WFG-152), so no critic or
  research lap may take it. Row updated with the measurement and the extended surface list, not duplicated.
- **WFG-144's value changed shape.** The printed panel now answers 「산림청·경기도가 이미 산불확산예측을
  하고 있는데 무엇이 다릅니까?」 in three pages; `docs/auto/JUDGE_QA.md` still has no card for it (re-run
  here: the only `산림청` hits are the two burned-area lines at `:399` and `:996`). So the student has no
  rehearsed answer while standing beside a panel that invites the question. Fifth lap measured. Still P1,
  because §14b allows one move and it went to the red gate. **If the author promotes one row, it is this one.**
- **WFG-139 unrepaired, sixth consecutive measurement.** `data/raw/` held only `.gitkeep`, `README.md` and
  the KFS CSV before the gates here; the cold run is `1646 / 62` against the 0711Z lap's warm `1654 / 56`.

## Falsifiable tests for critic #34

1. If a lap runs `make finals`, pushes, and files nothing about recurrence, WFG-119 has been **reset** and
   not closed, and the same red returns inside two days.
2. If WFG-146 is fixed in `docs/related_work.md` and not in `RELATED_WORK_PANEL.md`, the printed page keeps
   the wrong date and the propagation shape has completed a second lap.
