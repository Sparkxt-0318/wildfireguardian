# Events during the run (append only)

* 19 Nov 2026 ~13:28 UTC: the container restarted (uptime 3 min at 13:31; the driver and all processes were killed). Files on disk
  survived. The block `old_cold | UA 03-23 | repeat 1` was interrupted after 18 of 200 requests; its partial output was
  discarded and the block is re-run from the start. Six earlier tasks of repeat 1 (field, field_dec, field_sample,
  field_check, margin1, margin10 of UA 03-23) completed before the restart and are kept. CPU model, kernel, Python and numpy
  are unchanged and the fixed CPU probe reads the same before and after (0.063 s). Driver restarted at the time of the next
  ledger entry.
