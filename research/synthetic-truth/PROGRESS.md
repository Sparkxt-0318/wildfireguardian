# Track 1C progress log

One line per finished deliverable or gate, newest last. The orchestrator copies these lines into `docs/NEXT_PLAN.md`.

- 2026-10-29: reading notes and plan written (`research/synthetic-truth/PLAN.md`); branch `track/1c-routing-v2` created.
- 2026-10-29 (1C-2): SIPP matches the frozen contact sweep on 20/20 Korean missions in both repetitions (40/40 pairs), 81/81 member-scaling pairs, 10,000/10,000 random instances against brute force and 2,000/2,000 geometric instances against the frozen sweep; planner time SIPP/sweep median 0.39 (40/40 faster, Linux host-specific). Commit b38c36e.
- 2026-10-29 (1C-3): campaigns C1 to C4 done: C1 K = 4 trajectory members false-safe 11/2,000 (0.55%, Wilson 0.31% to 0.98%), equal to frozen v1 members, all from 2 of 20 missions, 0 false refusals, 0 unresolved; C4 reconstructed arrival: frozen members 0 false-safe on 20 missions, forecast-ignoring policy 1. Commit c905585.
- 2026-10-29 (1C-1, export v3): Contract A replay export for all 15 Korean cutoffs (N = 1,024, seed 0); replay equals model mode exactly on a FIXTURE data root with the real c651 checkpoint. Commits 31c6650, 10e8669.
- 2026-10-29 (extended-horizon exploratory panel, not frozen missions): derivation of 40 missions (20 x {3 h, 6 h}) with source request hashes; FIXTURE run only (real data tree pending). Commit 61b86d2.

## Gate run (fresh virtual environment), 2026-10-29

```sh
/usr/bin/python3.12 -m venv /home/user/venvs/1c-gate
/home/user/venvs/1c-gate/bin/pip install -c constraints-routing.txt "./integration[packets]" \
    -r experimental/scenario-members/requirements-test.txt -r experimental/sipp-routing/requirements-test.txt \
    -r experimental/synthetic-truth/requirements-test.txt                                   # exit 0
/home/user/venvs/1c-gate/bin/python -m pytest -q experimental/scenario-members/tests      # exit 0: 25 passed, 1 skipped (PyTorch tests)
/home/user/venvs/1c-gate/bin/python -m pytest -q experimental/synthetic-truth/tests       # exit 0: 10 passed
/home/user/venvs/1c-gate/bin/python -m pytest -q experimental/sipp-routing/tests          # exit 0: 12 passed (10,000 + 2,000 property cases)
/home/user/venvs/1c-gate/bin/python tools/verify_release.py                               # exit 0: PASS, 367 hashes
# forecast environment (python3.12 venv, torch 2.5.1 CPU, pip install -e ./forecast pytest==8.3.4 hypothesis)
python -m pytest -q forecast/tests/test_rollout_trajectory_callback.py forecast/tests/test_rollout.py \
    forecast/tests/test_rollout_cache.py forecast/tests/test_cumulative.py forecast/tests/test_cumulative_api_integration.py
                                                                                            # exit 0: 208 passed
python -m pytest -q experimental/scenario-members/tests/test_export_v3.py                  # exit 0: 7 passed
```

Installed versions in the gate environment: numpy 1.26.4, pyproj 3.7.0, pytest 8.3.4, hypothesis 6.170.13, matplotlib 3.11.2.
