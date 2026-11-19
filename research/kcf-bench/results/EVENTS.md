# Events during the run (append only)

* 19 Nov 2026 ~13:28 UTC: the container restarted (uptime 3 min at 13:31; the driver and all processes were killed). Files on disk
  survived. The block `old_cold | UA 03-23 | repeat 1` was interrupted after 18 of 200 requests; its partial output was
  discarded and the block is re-run from the start. Six earlier tasks of repeat 1 (field, field_dec, field_sample,
  field_check, margin1, margin10 of UA 03-23) completed before the restart and are kept. CPU model, kernel, Python and numpy
  are unchanged and the fixed CPU probe reads the same before and after (0.063 s). Driver restarted at the time of the next
  ledger entry.
* 19 Nov 2026 ~14:38 UTC: the container restarted a second time (uptime 41 min at 15:19; the driver was killed during
  `field_sample | UA 03-24 | repeat 1`, which had not written a result; it is re-run). All earlier ledger entries are kept.
  Detected at the 15:19 check-in, so about 40 minutes of run time were lost. Same CPU model, kernel, Python and numpy; probe
  checked after restart below.
* 19 Nov 2026 ~15:35 UTC: third container restart (uptime 0 min at 15:35:54), noticed at once through the MCP reconnect
  event. The driver was killed during `old_cold | UA 03-24 | repeat 1` after 25 of 200 requests; the partial output is
  discarded and the block re-runs from the start. Restarts so far: about 13:28, 14:38, 15:35 UTC (roughly hourly). Machine
  identical (CPU model, kernel, Python, numpy; probe below).
* 19 Nov 2026 ~15:48 UTC: fourth container restart (only 13 min after the third; uptime 0 min at 15:48:29), killing
  `old_cold | UA 03-24 | repeat 1` after 35 of 200 requests. Because of the frequency, plan amendment A2 (resume OLD blocks at
  the next request) was made; those 35 requests are KEPT and the block is resumed. This block straddles a restart.
* 19 Nov 2026 ~16:22 UTC: fifth container restart (uptime 0 min at 16:22:55), found at the scheduled check-in. The driver was
  killed during `old_warm | UA 03-24 | repeat 1` after 39 of 200 requests; those requests are KEPT and the block is resumed
  (amendment A2). This block straddles a restart. Restarts so far: about 13:28, 14:38, 15:35, 15:48, 16:22 UTC.
