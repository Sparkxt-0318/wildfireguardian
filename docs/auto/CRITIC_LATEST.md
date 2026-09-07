# CRITIC_LATEST — critic #38, 2026-09-07T2319Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `1bca8ed`. Window: the 24 h to 2026-09-07T23:00Z.
⚠ **This clone resolves the window from 00:43Z forward, not the whole of it:** `git rev-list --count HEAD` = **50**,
`git log --since='26 hours ago'` returns exactly 50, and the oldest resolvable commit is `590c29a`
(2026-09-07T00:43Z). The hour before that is outside this clone and I did not read it. Full report:
`docs/auto/reports/2026-09-07T2319Z-critic.md`.*

✅ **The baseline is GREEN on the routine's DEFAULT clone, measured before any deepening, and read unpiped.**
`git rev-parse --is-shallow-repository` = **true**, `git rev-list --count HEAD` = **50**. `gates.py --mode full`
exits **0**, ALL GREEN at `1bca8ed`: `1689 passed, 62 skipped, 2 xfailed`, pytest 212.2 s, **COLD**, and the run
**downloaded 25.9 MB** partway through (finding 3). `verify`, `snapshot-verify`, `env-check` PASS;
`baseline-verify` WARN is the documented CHARTER §3d state. `--assert-head` exits 0; `--assert-reported --base
3426135` exits 0.

✅ **No CHARTER §4b finding.** Through the GitHub MCP (`curl` against `api.github.com` is 403 here, WFG-119):
`auto-gates` runs **204 to 223** on `auto/dev` are **19 `success`, 1 `cancelled` (218), ZERO `failure`**, and run
**223** at this exact head is `success`. Every push in the window carried a report; every dev and critic report
carries `Reviewed by:`; the research report of 2026-09-06T1838Z does not (WFG-147, unchanged, not duplicated).

✅ **WFG-171 closed and closed well.** Critic #37's one item is cleared on both printed surfaces, registered as
`WC-009`, kit rebuilt and bundle re-pointed in the same lap. I read the replacement text rather than grepping for
the absence of the old sentence. **KCF_READINESS holds at 7 of 11**; R9, R7 and R1 all ticked inside this window.

---

## `fix-before-next-row` — ONE item (CHARTER §14b)

### WFG-173 — the judged screen's build stamp is sitting exactly on the staleness limit

`web/finals.html:434` carries `"git":"7308b06"`. `git rev-list --count 7308b06..HEAD` answers **30** at `1bca8ed`.
`tests/test_finals_screen.py:540` sets `STAMP_MAX_COMMITS_BEHIND = 30`; `:732` asserts
`behind <= STAMP_MAX_COMMITS_BEHIND`.

**So the gate is green today at the limit and red on the first commit anybody pushes** — which, on the sprint's
3-hour dev grid with a paper lap and a critic lap between, is the next lap. Critic #37 read the same field three
hours ago at **24** and wrote it up as 「inside the limit, not a defect in this window」. That was true then. Six
commits later it is not, and the difference between the two readings is the whole reason this is an item rather
than a note: at 24 there was room, at 30 there is none.

⚠ **There is a second and worse failure mode 20 commits further on.** When `behind` reaches this clone's own depth
(**50** here) the stamp stops resolving at all and the gate fails as `Not a valid object name`, which the test's own
message says 「reads as corruption rather than staleness」. That is what turned critic #33's lap red on a correct
tree (WFG-119). Drift walks toward it.

⚠ **Nothing on the screen is WRONG today, and this is filed as minutes for that reason.** Critic #37 re-derived all
28 on-screen keys against `docs/NUMBERS.json` with zero misses on either side, and R1 ticks on that work. This is a
liveness defect, not a correctness one.

**Done when** `make finals` has been run **on the commit being pushed**, so `web/finals.html`'s `git` field names a
commit inside the limit; **and** `make finals-bundle` re-points `release/kcf-finals-2026/MANIFEST.json` in the
**same lap** (WFG-152; `newest_printables()` resolves the stamp from the tracked tree, so the bundle build stays
broken until it is rebuilt); **and** `gates.py --mode full` is re-run after both, read unpiped, with `--assert-head`
and `--assert-reported` immediately before the push.

⚠⚠ **Do NOT raise `STAMP_MAX_COMMITS_BEHIND`.** `tests/test_finals_screen.py:754` grades the threshold with two
literals deliberately not derived from the constant, so raising it fails rather than slides past. **NH-043** (open,
due 2026-09-09) is the author's decision about how often this gate should fire; this row does not pre-empt it.

---

## The rest, ranked, and none of them is a `fix-before-next-row` item

2. **WFG-139 — ELEVENTH consecutive measurement, and the first ISOLATED reproduction. The diagnosis in the row is
   right and the fix is minutes.** Ten laps have measured this by watching a 25 MB file appear during a
   200-to-350-second `pytest-full` stage, which proves the suite downloads but not which line does. This lap ran the
   row's own named suspect **alone**. After the COLD gate run left `data/raw/dem/srtm/N36E129.hgt` (25,934,402 B) and
   `N36E129.hgt.gz` (8,473,868 B) at mtime **23:02Z**, I deleted both tiles **and** the cached
   `data/cache/dem_yeongdeok_2025_srtm_500m_80858ae747.nc` they had produced (all git-ignored; `git status --short`
   clean afterwards) and ran exactly
   `pytest tests/test_spread_warmup.py::test_model_config_ignition_radius_increases_initial_burn`.
   **1 passed in 1.54 s, and both tiles were back on disk at 23:06Z.** Control: the same single test with the `.nc`
   cache still present passes in **0.47 s** and downloads nothing, which is why no earlier lap saw it in a re-run and
   why a warm machine can never reproduce it. The test asserts `first_area_ha > 25.0` and
   `metrics_persistence[0].predicted_area_ha > 25.0`, both about the **ignition disc**, and it already runs
   `fuel_source="synthetic"`, so `dem_source="synthetic"` is the smaller of the two repairs the row already
   prescribes and should be tried first. **Grade it** by repeating the deletion above with the network unreachable:
   green at the COLD counts, `data/raw/dem/` still empty.

3. **WFG-174 (new, P1, IEEE) — the manuscript applies one provenance standard to a Korean agency and a laxer one to
   the Western literature, and its own reviewer said so.** `paper/GAPS.md:118-127` and `paper/STATE.json` record that
   **15 of the 29 references are verified 「via the Crossref record」** while §2 characterises six of them
   substantively (`li2017`, `li2019`, `wahlqvist2021`, `cova2003`, `cova2005`, `finney2002`). A Crossref record is a
   catalogue entry, which is the exact standard paper lap 16 applied when it retracted the NIFoS sentence and the
   exact standard WFG-171 has just applied to two booth panels. No claim is false and none may be called false; the
   asymmetry is the defect. Shares its gate half with **WFG-042**, and `check_paper.py:203` cannot see either,
   because it tests only for the substring `verified`.

4. **WFG-175 (new, P1, infra) — a paper lap's findings have no route to the backlog, and today one was lost.**
   `docs/auto/reports/2026-09-07T2112Z-manual.md:124` and `paper/GAPS.md:118` both say the finding above was
   「Filed as a dev-lap row」; `paper/STATE.json` says 「FILED, NOT FIXED」. **No such row existed.** It is not that
   lap's slip: CHARTER §12 confines the paper routine to `paper/` plus its own report, so it is structurally unable
   to write the row it says it filed. The finding survived only because this lap opened `paper/STATE.json` to check
   the word budget and read the field to the end. §14b holds this behind R3, R4 and R8 as loop hygiene.

5. **NH-037 is now binding on FIVE words, and this entry's own worst case has happened twice in one day.**
   `paper/check_paper.py` at `1bca8ed`: `body_words` **8,995** against a hard fail at **9,000**. The same lap
   re-measured the built document with a real renderer at **23 pages** against the author's **25-page** rule. So the
   author's rule has two pages of room and the proxy has five words. Lap 17's three reviewer-mandated corrections
   cost +7 words and were paid for with four one-word syntax compressions. Five laps in a row have now had their
   writing shaped by the proxy rather than by the evidence. Nothing is red; the next mandatory correction of any size
   parks the manuscript, which is correct behaviour under CHARTER §3 rule 9 and is exactly why NH-037 is open.

6. **The author has TWELVE open decisions and two of them are due TODAY (2026-09-08 KST).** `decisions_seen.json`
   still shows `"seen": []`: no decision has ever arrived by email, and the newest applied one is NH-031 from a
   laptop session on 2026-09-06. **NH-032 and NH-034 are due 2026-09-08**; NH-035, NH-038, NH-043 and NH-044 are due
   2026-09-09. Until NH-032 and NH-034 are answered the student is forbidden to say **any** of the three
   fair-opponent margins that exist. This is not a finding against a lap. It is the one thing in this window that no
   lap can clear.

7. **A small one against this routine, recorded rather than hidden.** Critic #37 appended its scorecard row to the
   Track B and Track A tables and **not** to the series table, against `SCORECARD.md`'s own instruction
   (「Append here **and** to the track table you are scoring」). I backfilled its `64f015b` row from those two tables
   verbatim, marked as a backfill, and appended mine below it. Nothing was invented and no row was edited.

## Direction

**No reorder, and none was needed.** DIRECTION's position 1 (WFG-139) is unchanged and is now better specified than
it has ever been; its `fix-before-next-row` (WFG-171) closed inside this window. My one item sits ahead of position 1
and displaces nothing, per §14b. WFG-174 and WFG-175 are both P1 and both go behind the readiness block.

**Readiness lines ticked in the window:** R9 (05:00Z), R7 (08:00Z), R1 (20:00Z). The 「zero across two consecutive
critic laps」 direction finding does not fire.

## `Do NOT edit` notes carried forward

**None, and none written.** Critic #37 left none. The DIRECTION rule that keeps this routine out of `JUDGE_QA.md`,
`DEMO_SCRIPT_5MIN.md`, `BOOTH_SETUP.md` and `RELATED_WORK_PANEL.md` is a standing routine boundary rather than a
`Do NOT edit` note on a file's content, and it names its own mechanism
(`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`, probed and reverted at
`3f881f6`). It is re-checked and re-stated here rather than inherited, and it is why the Q28 repair in finding 2 is
left to a dev lap that can rebuild the kit in the same lap.

---

# ⚠⚠ ADDENDUM, written after the commit: THE PREDICTION IN WFG-173 CAME TRUE IN FOUR MINUTES, AND THIS LAP IS PARKED

**Read this before anything else above.** Everything above was written against a **green** baseline at
`1bca8ed`, and that reading was correct: `gates.py --mode full` exited **0** there. Then this lap committed
its own report, `docs/auto/` only, and that single commit took `git rev-list --count 7308b06..HEAD` from
**30** to **31**.

    tests/test_finals_screen.py::test_the_screen_is_rebuilt_before_its_stamp_ages_out_of_this_clone  FAILED
    AssertionError: web/finals.html was built at 7308b06, now 31 commits behind HEAD (limit 30).
    assert 31 <= 30

So **WFG-173 is no longer a forecast; it is a live red gate**, and it fired on the report that named it.

**The full run on the parked commit, read unpiped and recorded here rather than summarised:**
`gates.py --mode full` at `84796ea` exits **1**, **RED**. `verify` PASS 14.6 s, `baseline-verify` WARN
(the documented CHARTER §3d state), `snapshot-verify` PASS, `env-check` PASS, `pytest-full` **FAIL**:
**`1 failed, 1694 passed, 56 skipped, 2 xfailed`** in 1447.6 s, **warm** (the SRTM tile is on disk from
this lap's WFG-139 reproduction, which is why 56 skipped rather than the baseline's 62, and no download
occurred in this run). **The one failure is the staleness gate and nothing else.**
`gates.py --assert-head` then exits **1** with 「the recorded run did not pass」, which is the mechanism
that stops this from being pushed to `auto/dev`, and it worked exactly as designed.

**Where this lap's work is.** Parked on **`auto/red/2026-09-07T2319Z`** per CHARTER §3.9, with
`origin/auto/dev` left at `1bca8ed`, which is green. Nothing was force-pushed and nothing is lost.

**Why this routine did not simply fix it.** The remedy is one command, `make finals`, printed by the gate
itself. It regenerates `web/finals.html`, an artifact outside `docs/auto/`, and the critic routine's standing
prompt forbids that in those words: 「You change NO code and NO artifact; you write only under
`docs/auto/`」. The routine that met the red is the one routine that may not clear it.

**⚠ The same trap is set for the next lap, whichever routine it is.** `behind` counts commits, not changes.
CHARTER §4 step 3 has the next dev lap claim its row with a commit and push it **before building anything**:
that claim alone takes `behind` to 31 and turns the gate red before the lap has done any work. `auto/dev` is
not broken. It is **closed**, until some lap runs `make finals` and pushes the rebuilt screen.

**What the next lap should do.** Run `make finals` on the commit you are pushing, then `make finals-bundle`
to re-point `release/kcf-finals-2026/MANIFEST.json` in the same lap (WFG-152), then re-run
`gates.py --mode full`. That is WFG-173's 「Done when」 verbatim, and the gate's own message says the same
thing. Then merge or cherry-pick `auto/red/2026-09-07T2319Z` so WFG-173, WFG-174, WFG-175, the WFG-139
reproduction and this `CRITIC_LATEST.md` reach `auto/dev`.

**⚠ This lap deliberately did NOT write a CHARTER §4 step 2 override into this file.** Critic #33 wrote one
and NH-043 records the problem with it: every critic lap rewrites this file, so the override expires within
hours and the question stays buried. Writing another would have buried it again. The escalation is
**NH-045** (BLOCKER, new this lap) and it points at NH-043's option A or B as the fix for the class.

**Do NOT raise `STAMP_MAX_COMMITS_BEHIND` to get past this.** `tests/test_finals_screen.py:754` grades the
threshold with literals deliberately not derived from the constant, so raising it fails rather than slides
past.
