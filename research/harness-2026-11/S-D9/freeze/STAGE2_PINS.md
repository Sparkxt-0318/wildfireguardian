# FREEZE stage 2: pins collected so far (working record, NOT the freeze)

This file records inputs as they are pinned, before the stage-2 FREEZE file is generated.
- Each row says who supplied the pin and who checked it.
- Nothing here is frozen until `make_freeze.py` writes the stage-2 amendment record and Hannah verifies it.
- Part c stays closed until then (A1 §6.1, §9).

| item | value | source | status |
|---|---|---|---|
| refit `--train-events`, **pre-weather** | `TRAIN_EVENTS_preweather.txt`, sha256 `bbedca82b10ff0d7737feac78f7997bb57e26f3af6028eb10516d4cb7c42b55b` (513 = fit-23 + 490 part a) | Marcus, harness/s-d1-next e29524a4 (`s-d1/refit/train_events/`); built from Daniel's part-a pool 982eb71c (data-fetch-3) | Victor checked: the sha matches; the 490 part-a IDs equal PART_A_ALLOWLIST_FINAL (7db3cc0e…) exactly; the other 23 are the fit-23. **Pre-weather: superseded by the final list** |
| refit `--train-events`, **final** | pending | Marcus, after tonight's weather. Same rule (≥ 2 surveys, ≥ 1 interval ≤ 48 h), plus a report of incidents with no usable interval by `Environment.available_at`; nothing is replaced | pending |
| part-a pool build | daniel/data-fetch-3 982eb71c `parta_pool/` (490/490 OK) | Daniel | pin the manifest sha when it is committed |
| weather input-manifest | pending | Daniel (13 Nov) | pending |
| d2_bracket_rebuilt code | `d2_bracket.py` 98d7d6c6…, `run_d2_bracket.py` cc41cc33…, `run_d2.py` e3c0843c… (claude/s-d2-next) | Elena | final head and Owen's verification pending |
