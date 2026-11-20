* 20 Nov 2026 09:13:24-09:13:27 UTC: a git commit and push (a few seconds, other cores) ran while `old_warm | YD 03-25 23Z | repeat 1` was in progress
  (about request 78 of 200). This is the only push so far that overlapped a timed block; requests started in that window can
  be flagged in the analysis by their timestamps. It was done on the stop hook's request, not at a task boundary.
* 20 Nov 2026 09:14:41-09:14:42 UTC: `git merge origin/Main` (about 1 second, other cores) while `old_warm | YD 03-25 23Z | repeat 1` was
  running (about request 80 of 200). PRs #219 (this study, as of its merge at 23:06 UTC on 19 Nov) and #228 (a separate
  Mac benchmark, now in `research/kcf-bench-mac/`) are in Main. The harness files (common.py, driver.py, run_field.py,
  run_old.py, make_cases.py) are byte-identical before and after (checked by blob hash), so the driver's hash check is unaffected.
* 20 Nov 2026 ~09:25 UTC: container restart on the SAME machine class (2.10 GHz, kernel v726), found at 09:30:57 (uptime 0 min) after
  about 15 minutes of idle session (the idle shutdown described in the 2.30 GHz event log). `old_warm | YD 03-25 23Z | repeat 1`
  had 103 of 200 requests saved; they are KEPT and the block is resumed (amendment A2), so this block straddles a restart.
  After this boot the fixed CPU probe was noisy for the whole 3 minutes it was watched (22 readings, 0.059 to 0.143 s, median
  about 0.078 s) instead of settling at 0.073-0.076 s: a busy neighbour on the shared host is likely. The run was restarted
  anyway; tasks whose probe_before_s or probe_after_s is high are to be flagged in the analysis.
