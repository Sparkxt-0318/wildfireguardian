# Note 2 (13 Nov 2026, 03:45Z): one pinned file carries a wall-clock timestamp

Found by Owen, when he rebuilt US2024 with `rebuild_us2024_pinned.sh` @12fc6e7b. His result was 346 of 347 pins equal.

**Cause.** `environment/biome_validation.json` contains `"checked_utc"`. `forecast/wildfire/environment.py:984` sets that field to `pd.Timestamp.now(tz='UTC')` every time the biome stage runs. A faithful rebuild therefore never reproduces this file's bytes.

**Correction.** `rebuild_us2024_pinned.sh` says "Exit 0 only if all 347 pins match exactly". That claim is wrong for this one file, and the script will exit 1 on a correct rebuild. I have not edited the script or the pins.

**Scope.** I checked every text-type pin for wall-clock fields. In both pin sets, `biome_validation.json` is the only pin that carries one:

| pin set | text pins | pins with a wall-clock field | `checked_utc` in the pinned copy |
|---|---|---|---|
| US2024 `286f4c47` | 53 | 1 (`environment/biome_validation.json`) | `2026-11-12T09:43:38.262390+00:00` |
| part-a `f70e52b0` | 2,944 | 1 (`environment/biome_validation.json`) | `2026-11-12T14:54:31.848341+00:00` |

**Checker.** `check_pins_normalised.py MANIFEST DATA_ROOT` checks every pin as follows:
- Every pin must match sha256 exactly, except `biome_validation.json`.
- For that one file, there must be exactly one `"checked_utc"` field. Substituting the pinned value into it must make the file's sha256 equal the pin.
- Nothing else is normalised.

The checker was tested on three cases:
- on the pinned US2024 workspace itself: exact 347;
- on a copy whose only change is `checked_utc`: 346 exact plus 1 normalised, exit 0;
- on a copy with one other byte changed in that file: MISMATCH, exit 1.

**Not decided here.** Whether this one-field normalisation is acceptable for custody or verification is Hannah's ruling.
