# Handoff: continuing wfglink with a fresh agent (2026-10-15)

Paste the prompt below into the new agent. The repository holds everything else.

---

You are taking over an in-progress project in the GitHub repo `Sparkxt-0318/wildfireguardian`, branch `claude/practical-rubin-5vu12u`. A draft PR to main is open on it (Sparkxt-0318/wildfireguardian#53). The project is **wfglink**, which lives entirely in the `wfglink/` folder. It is a booth exhibit for Korea Code Fair 2026 that measures glowing wildfire embers in ordinary video. It has two modes: fire mode, where approved clips play in real time and are analysed live, and the "Become an ember" mode, where a camera tracks visitors' phones showing a glowing ember web page. The target date is **Monday 19 October 2026**, and the booth must always be demo-ready.

## Read first, in this order
1. `wfglink/docs/PROMPT.md`: the user's original prompt and every later decision, verbatim and dated. These are the requirements; later entries override earlier ones.
2. `wfglink/PLAN.md`: the current plan. Read the decisions list near the end, starting with "Booth limits and the dashcam camera".
3. The last five entries of `wfglink/LOG.md`.
4. `wfglink/README.md`, `wfglink/docs/METHODS.md`, `wfglink/booth/BOOTH_RUNBOOK.md`, `wfglink/docs/SITTING1.md` and `wfglink/docs/SITTING2.md`.
5. `wfglink/DEMO_BUILDS.md`.

## Hard rules (from the user; do not break them)
- **Scope**
  - Work only inside `wfglink/`. Never create, edit, move or delete anything outside it, including root files such as README, .gitignore or requirements, and the untracked `.claude/` folder at the root. Reading the rest of the repo is fine.
  - Do not modify or import the repo's forecasting, routing or monte-carlo code.
- **Git**
  - Stay on `claude/practical-rubin-5vu12u`. Never switch branches, stash, rebase, reset or force-push.
  - Stage with `git add wfglink/` only, never `git add -A` or `git add .`.
  - Run `python scripts/check_staged.py` (from `wfglink/`) before every commit. It blocks videos and files over 5 MB.
  - Start every commit message with `[wfglink]`. Commit at meaningful checkpoints and push to the same branch.
- **Data**
  - Never commit raw video; `data/raw/` is git-ignored.
  - No YouTube downloads.
  - Never use the held-out mismatch or coverage suites for tuning.
- **Writing**
  - Plain English, with no em or en dashes (U+2014 and U+2013).
  - `LOG.md` is append-only, one entry per significant run, with timestamps in Asia/Shanghai (+08:00). Each entry has Goal, Commands, Parameters, Results, Decisions and Next. Failures get logged too.
  - Every number in a LOG "Results" bullet, and in the README's "Current status", needs an `<!-- n:KEY -->` tag that points to `results/NUMBERS.json`. Record numbers with `wfglink.provenance.record_number`.
  - Run `python scripts/check_docs.py` before every commit; it must print OK.
- **Honesty:** state every missed goal and limit plainly. On-screen numbers carry their "estimate" or "uncalibrated" tags.

## Environment
- Linux container, Python 3.12, venv at `wfglink/.venv`. If the venv is missing, create it and run `pip install -r wfglink/requirements.txt`.
- Run commands from `wfglink/` as `.venv/bin/python -m wfglink ...`.
- Qt runs headless with `QT_QPA_PLATFORM=offscreen`.
- Tests: `.venv/bin/python -m pytest -q`. The full suite takes about 8 minutes; at the last full run there were 450 passed and 1 skipped.
- Clips are fetched into `data/raw/` with `python scripts/fetch_clips.py --only C5_nist_emberometer C6_nist_dragon`, from Wikimedia and NIST, one file at a time. Wait 10 minutes after any HTTP 429.

## State at handoff (HEAD 55678b8 plus this handoff commit)
- **Built:**
  - fire-mode detector, tracker, velocity, gate counts and the ember field;
  - the booth UI, with keys A (raw or analysed), M (mode), L, I, Space, and Esc twice to quit;
  - playlist playback; supervisor `booth/booth.sh`; soak; doctor; placards;
  - the ember mode: camera chosen by name, phone page at `booth/ember/index.html`, A4 calibration, record, `validate --suite ember`;
  - the demo gate, `python -m wfglink demo-gate --seconds 60`.
- **Latest user decisions, all implemented:**
  - Ember mode tracks at most 3 phones (`ember.max_tracks: 3`), with a small "max 3" note on screen.
  - A dashcam in USB "PC camera" (UVC) mode is a USB camera like any webcam; `camera.mask` blanks a burned-in timestamp or logo.
  - Fire mode already analyses C5 at about half resolution (`live.analysis_max_pixels`), so no half-resolution clip copies are needed.
- **Last tagged working demo:** `wfglink-demo-20261015-3`, at commit 161612e. Tag pushes return HTTP 403, so demo builds are recorded in DEMO_BUILDS.md with `scripts/tag_demo.sh`.

## Open work, in priority order
1. **Demo gate fails on the ember count.** In ember mode the gate counted more embers than its scene's 3 phones in 3.6% of frames, and in 7.4% during the run that presses the keys. Everything else passes.
   - Cause (LOG 2026-10-15T19:20): when analysis runs below the full frame rate, a phone sweeping past the scene's desk lamp hands its ember to the lamp. The stuck ember then lasts until `ember.track.light_rest_s` (1.0 s) ends it. At the full rate this never happens.
   - Fix in `src/wfglink/ember/track.py`: refuse to assign a moving, shown ember to a blob on the light map (`blobs.light >= ember.background.light_frac`) when its predicted speed is well above zero. Leave the static-light track to take that blob instead.
   - Reproduce by replaying the booth scene with `phone_scene_source(cfg, realtime=False)` through `EmberPipeline`, analysing every 2nd and 3rd frame, with `cfg["ember"]["max_tracks"] = 6`.
   - Then run `validate --suite ember`; its numbers must not get worse (these synthetic scenes are a tuning set and are labelled as such). Run the demo gate, and when it passes, run `scripts/tag_demo.sh` and commit the DEMO_BUILDS row.
2. **Full test suite** on HEAD (not run since 2d87bf3). Fix anything red. One timing test, `tests/test_booth_app.py::test_space_pauses_and_esc_twice_quits`, has been flaky under heavy machine load.
3. **File-mode scale fix for 4K clips.**
   - At native 4K, file mode misses the large, near, defocused embers on C5.
   - Three approaches were built and judged (a resolution cap, multi-scale detection, and a "wide-ember pass"); multi-scale won. Its verification was still running at handoff.
   - The verifier's tree is saved as `docs/handoff/multiscale_unverified.patch` and applies cleanly to HEAD. It adds `src/wfglink/detect/multiscale.py`, `tests/test_multiscale.py` and `configs/suites/hires.yaml`, plus `configs/synth/hires/*`, and edits the pipeline, process, candidates, config, METHODS and PLAN.
   - Scratch results on the 20 blind-labelled C5 frames (`results/labels/C5/`), before and after: true positives 11 to 28, misses 33 to 16, false positives 143 to 163.
   - To finish it:
     1. Apply the patch.
     2. Review it, and run its tests and the full suite.
     3. Check that the booth path (720p, C6, live) is unchanged.
     4. Re-record the core-suite numbers if they changed, with `scripts/run_suite.py`; see the LOG entries about re-recording.
     5. Score C5 with `python -m wfglink label-score`, record the numbers, and add a LOG entry.
     6. Delete the patch file once it is merged.
4. **Inspect C10's overlay** (sparkler, tracking only), then the real-clip plausibility checks (task 14 in the plan).
5. **Mismatch and coverage suites, run once each** for the headline numbers. They are never tuned on. Update the README "Current status" with tagged numbers.
6. **Daily demo build** once the gate passes. Keep README, PLAN and LOG current.

## When the user pastes a sitting report
The user runs `scripts/sitting1_tonight.sh` on a MacBook (built-in camera plus an iPhone showing the page) and pastes `~/wfglink-sitting1/report.txt`. Analyse it, fix what it shows, and log it. They may later use a dashcam in UVC mode; the runbook has a section for that.

## Style of work
- Verify before you claim: run the tests and look at rendered screenshots.
- Keep each change minimal, and match the surrounding code's style and comment density.
- Report outcomes plainly, including failures.
