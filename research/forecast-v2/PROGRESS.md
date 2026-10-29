# Track 1B progress log

One line per deliverable. Headline number, then commit. Host: Linux cloud container, 4 vCPU shared with two other track agents, at most 2 threads used.

- 2026-10-29: SPLIT.json committed before any fit: 23 US fit fires 2020 to 2022 (3 leave-one-year-out folds); held out are 6 US 2024 fires and 4 Korean 2025 fires (commit b0eba9d).
- 2026-10-29: 1B-1 code: mean-field propagation (`forecast/wildfire/meanfield.py`). For binary states, one step matches `new_burn_probability` to within 1e-9 (float64). The validity envelope equals rollout coverage exactly (tests in `forecast/tests/test_meanfield.py`). The measured mean-field versus Monte Carlo error still needs the environmental data tree (commit f68d6ef).
- 2026-10-29: Code for 1B-2 to 1B-4 is in place (survival fitting, burnout, D4 and wind frame, Anderson ellipse, spotting, baselines, fire-paired bootstrap). In a fresh venv, the forecast suite gives 2865 passed, exit 0. NIROPS perimeters are rasterized for all 29 fires: 273 held-out intervals of 48 h or less, about 1,300 fit intervals.
- 2026-10-29: 1B-5 pre-registration draft written (`forecast/documents/preregistration_blind_test.md`). Candidate checkpoint hashes are filled from RESULTS.json after the final fits.
