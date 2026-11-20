* 20 Nov 2026 09:13:24-09:13:27 UTC: a git commit and push (a few seconds, other cores) ran while `old_warm | YD 03-25 23Z | repeat 1` was in progress
  (about request 78 of 200). This is the only push so far that overlapped a timed block; requests started in that window can
  be flagged in the analysis by their timestamps. It was done on the stop hook's request, not at a task boundary.
