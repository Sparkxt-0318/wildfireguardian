* 20 Nov 2026 09:13:24-09:13:27 UTC: a git commit and push (a few seconds, other cores) ran while `old_warm | YD 03-25 23Z | repeat 1` was in progress
  (about request 78 of 200). This is the only push so far that overlapped a timed block; requests started in that window can
  be flagged in the analysis by their timestamps. It was done on the stop hook's request, not at a task boundary.
* 20 Nov 2026 09:14:41-09:14:42 UTC: `git merge origin/Main` (about 1 second, other cores) while `old_warm | YD 03-25 23Z | repeat 1` was
  running (about request 80 of 200). PRs #219 (this study, as of its merge at 23:06 UTC on 19 Nov) and #228 (a separate
  Mac benchmark, now in `research/kcf-bench-mac/`) are in Main. The harness files (common.py, driver.py, run_field.py,
  run_old.py, make_cases.py) are byte-identical before and after (checked by blob hash), so the driver's hash check is unaffected.
