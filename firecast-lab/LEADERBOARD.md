# Track A leaderboard

**No real-data rows exist yet, so there is no leaderboard.** Nothing on this page is a result.

## Why

The Phase 0 harness, the baselines, the decision metric and this aggregator were built and tested on the cloud
host. That host has none of the inputs a real row needs:

- **The data root** (`FIRECAST_DATA_ROOT`: `events.json` plus `regions/<fire>/` arrival, terrain and weather
  rasters) is on Siyeong's Mac only. It holds the Choi et al. 2026 arrival reconstructions, which are the Korean
  and US labels. `forecast/data/environment` in this repo holds `events.json` only.
- **The NIROPS perimeters** (US truth) are on the Mac, and they have no loader yet.
- **PyTorch**, which the c651 baseline needs, is not installed here.
- The Korean router road graphs that the decision metric needs are on this host. Without the data root, though,
  there are no windows to route through.

Every command refuses to run without the data root and never falls back to synthetic data. The tests use SYNTHETIC
data only and write to temporary folders, never here or to `results/`.

## How this page is made (on the Mac)

```bash
export FIRECAST_DATA_ROOT=/path/to/data/environment
for b in persistence dilation calibrated_dilation logistic; do
  python program/benchlock.py --label fl-$b -- firecast-lab run --baseline $b --split dev
done
# c651: time one fire first (firecast-lab time-c651 --fire KFS_02 --members 256), then run it the same way
firecast-lab leaderboard        # firecast-lab/results/*.csv -> this page (+ LEADERBOARD.json)
```

Per country, split, lead, scoring domain and K, the aggregator pools each run's per-window terms. It reports Brier,
Brier skill against persistence and against calibrated best dilation, ECE with the reliability rows, average
precision with the base rate, FSS at 1 to 33 cells, CRPS and fair CRPS on arrival time, the rank-histogram outer
share, and spread-skill with its rows. Each comes with a whole-fire bootstrap interval and the number of fires
(`METRICS.md` §8). The aggregator refuses runs that scored different cells in the same window, and it never writes
SYNTHETIC rows to this page.

The decision metric (`firecast-lab decision`) writes its own report per model (`results/decision_<model>.json`).
None exists yet either.
