# Prepared independent MF/MC reconciliation

Prepared without opening any actual comparison case, receipt, aggregate, prediction field, model or data/cache array. The actual reconciliation has NOT RUN and requires root authorization after all 12 jobs, the aggregate and its final receipt exist.

The bounded source contract confirms 12 frozen cutoffs and 66 rows: six Korean cutoffs across three reconstructed events, each at 1/3/6/12/24 hours; six distinct US fit-fire cutoffs, two from each 2020/2021/2022 development fold, each at those five horizons plus its fractional next-survey endpoint. Korean references are reconstruction labels; US fixed horizons have no reference score and only US survey rows have mapped-extent labels.

The checker validates exact source/protocol/SPLIT custody, all 61 source hashes and their lossless code snapshots, all 12 successful immutable case receipts, output/log hashes, executed command arguments, CPU-source provenance, pinned runtime versions and host metadata, checkpoint SHA assertion, row identities/order, known counts and null/unavailable statuses, finite/ranged RMSE/Brier values, several necessary arithmetic consistency bounds, fixed-call shared timing, distinct survey costs, aggregate equality to the exact concatenated per-case rows, all aggregate receipt pins and both per-case/aggregate CSV values. It never substitutes zero for unavailable metrics. It derives descriptive support-count summaries from the saved values without claiming to replay their masks.

The source writes per-case JSON/CSV metric summaries, not per-cell comparison arrays. No field arrays were available to or opened by this preparation. The checker cannot recompute raw-field RMSE/Brier or establish actual support masks from these summaries. It does not rerun Monte Carlo or load weights. The checkpoint value is checked against the pinned producer's constant assertion; it does not independently rehash the actual checkpoint bytes. Existing separate checkpoint/input custody evidence remains necessary.

Each cutoff has one joint 24-hour MC call and one joint mean-field call shared by five fixed-horizon rows. The checker counts each call once, then separately includes the US fractional-endpoint calls. Summing all five repeated row costs as independent runtimes would be wrong. This tool makes no promotion, field-validation or speed claim. Six Korean cutoffs are three reconstructed events, not six independent fires.

Synthetic verification: 24/24 controls pass, including one full synthetic 12-case/66-row positive fixture with an honest unavailable row, and 23 meaningful corruptions covering omissions/order/identity, N/seed, metrics/counts/nulls, reference leakage, command/source/checkpoint custody, runtimes, CSV/JSON, missing receipts, code snapshots and nonfinite values. Only synthetic source placeholders, JSON, CSV, logs and compressed code snapshots were read. `SYNTHETIC_RESULTS.json` and `SYNTHETIC_TESTS.log` retain exact results.

Exact future command, after root authorization:

```sh
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 \
  /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/mfmc-final-independent-review/reconcile.py \
  --repo /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b \
  --run /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/track-1b/forecast/runs/20261030_perimeter_trained/execution_v3 \
  --contract /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/mfmc-final-independent-review/SOURCE_CONTRACT.json \
  --attempt 6 \
  --out /Users/jp/Documents/Codex/2026-10-30/work-in-the-wildfireguardian-repository-on/work/mfmc-final-independent-review/ACTUAL_RECONCILIATION.json
```

`SOURCE_CONTRACT.json` pins the exact inspected source phase at d2512cbc, including pipeline SHA 88d376d219993e72832f21c86df5f90140dc894f876b3bb9cd37688520c92d67 and audit-fit helper SHA 1753cf31b21be093e13d61a107e407cf41542e9ec6dbe4c8ced924f5a5320cf4. It is a custody manifest for 61 files, not a claim that all 61 were semantically reviewed. Material source ranges read: pipeline.py 578-733, run_campaign.py 40-111 and 210-235, audit_fit_coverage.py 162-174, plus complete frozen RUN_PROTOCOL and SPLIT metadata. No call-chain completeness claim is made.

Graph Tier 2 project wfg-next-1b-audit-d2512cbc-20261030 is ready at generation 2026-10-30T10:03:04Z. The parent query found zero comparison nodes because the scripts subtree is excluded. Coverage confirms excluded/not-tracked script paths; their exact material ranges were read directly. Frozen JSON metadata coverage is current with no recorded issue. Coverage remains a best-effort signal.
