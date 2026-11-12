# Preprint M548/c651 Wapiti figures: cell-level reproduction (S-D9 step 3)

**Development-only. Wapiti is exposed:** it is a cohort-R fire and c651's SELECTED_ON fire. No sealed fire is read.

The cases come from the owner archive (sha256 b9e000e8…dd65, matched by Daniel): `runs/20261013_observed_stored_validation/cases/`, 25 Wapiti intervals. They are **not committed**, because they are owner data. `M548_REPRO.json` (sha256 8de3447a…) records the sha256 of every input file, together with the per-case counts and Brier.

Reproduce: `python derive/m548_repro.py --cases <extracted cases dir> --out M548_REPRO.json`

**Population.**
- *Cells scored:* cells valid in the reference at both times and in the prediction, and unburned at the cutoff.
- *Label:* the cell is mapped burned at the endpoint.
- *Prediction:* the M548 `probability` from 1,024 trajectories.

| figure | quoted (preprint / docs) | reproduced from cells | committed aggregate record |
|---|---|---|---|
| entries / new-burn positives | 275,961 / 2,525 | 275,961 / 2,525 | 275,961 / 2,525 |
| Brier | 0.008402 | 0.0084024931 | 0.0084024931 (difference 0.0) |
| AP | 0.1461 | 0.14610 | — |
| BSS vs always-zero ("no new burn") | 8.17% | 8.168% | — |
| positives with exactly zero probability | 617 of 2,525 | 617 | — |
| share in the first reliability bin [0, 0.01) | 93.9% | 93.91% | — |
| that bin: observed vs mean prediction | 0.364% vs 0.0131% | 0.364% vs 0.0131% | — |

The committed aggregate record is `forecast/documents/observed_runtime_stored_validation_20261013.json`. For context, FARSITE on the same 275,961 entries has Brier 0.023804.

**Status.**
- **Every preprint figure is reproduced exactly from cell-level data.**
- In S-D9's ten-equal-bin convention, the lowest bin [0, 0.1) holds 97.6% of entries: observed 0.558% vs mean prediction 0.170%. The preprint's 93.9% refers to its own first bin, [0, 0.01).

**Caveats, carried over.**
- The result is not blind: c651 was chosen after inspecting Wapiti.
- The "persistence" in the 8.17% figure is the always-zero new-burn forecast, so its Brier equals the base rate.
- The labels are NIROPS mapped extent, with no survey-coverage mask.
