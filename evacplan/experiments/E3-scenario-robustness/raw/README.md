# E3 raw records (SYNTHETIC)

Copies of the main compute run's records from `evacplan/runs/E3-scenario-robustness/` (git-ignored there), added in
the batch-1 review (2026-11-01). They are kept because E3's B2 plans cannot be regenerated (B2's search depth depends
on machine load) and the run folder exists only on this VM. Every record in the plans, checks, support and runs files
carries compute commit `11817858` and host
`vm (Linux x86_64, Intel(R) Xeon(R) Processor @ 2.80GHz, 4 cpu, python 3.12.3, vm boot ff671362)` (`members.json` has
no such stamp). SYNTHETIC dev instances only: no test instance, no real data.

| file | what it is |
|---|---|
| `plans.jsonl.gz` | 198 plans (190 B1, 8 B2), one per (instance, plan): arm, K, planning members, the solution (itineraries), per-trip in-sample state, residents and safety slack, B2 search diagnostics. `gzip -9` of `plans.jsonl` (2 065 399 bytes, 198 lines). |
| `checks.jsonl.gz` | 7 112 out-of-sample oracle checks, each one plan against one fresh member: instance, plan, check member `c` (hazard member 40 + c), per-trip states (`0` = checked; any other state of a trip delivered in-sample is a violation), causes. `gzip -9` of `checks.jsonl` (2 055 482 bytes, 7 112 lines). |
| `support.jsonl` | 34 support sets from greedy removal: instance, plan, K, support members, s*, number of B1 runs. |
| `members.json` | per instance: members regenerated (296), how many of the first match the instance's members bit for bit (8), seconds, the instance's split fingerprint. |
| `runs.jsonl` | the compute run: commit, host, boot id, elapsed time and budget, tiers reached, instances. |

Not copied: the smoke run (`smoke/`) and the logs.

Re-run the analysis on these records from the worktree root (inside the bench lock, program rule 6):

```sh
R=evacplan/experiments/E3-scenario-robustness/raw
gunzip -k $R/plans.jsonl.gz $R/checks.jsonl.gz     # keeps the .gz files; do not commit the unpacked copies
.venv/bin/python program/benchlock.py --label E3-analyze -- \
    .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_analyze.py \
    --runs-dir $R --out-dir <scratch folder> --diagnostics
```

Without `--out-dir` the CSVs and figures in the experiment folder are overwritten. The unpacked copies are untracked
files, so `analysis_commit` gets `+dirty` while they exist; delete them afterwards. `--diagnostics` regenerates the dev
instances' hazard members for `diagnostic_arrivals.csv`. `margin_cost_baselines.csv` comes from the harness rows of the
host that runs the analysis, not from these records. In the batch-1 review the analysis on the original records
reproduced every committed CSV with 0 field differences (`analysis_commit` aside), except `margin_cost_baselines.csv`
(empty when E3 ran; 50 rows from this host's harness rows at `18841678`).
