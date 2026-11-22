# Leakbound L/L2 step 2 run outputs (part a, 490 fires)

Copied byte-for-byte from the run directory, unedited. Run from worktree cacfd9aed70ac8e01cdf993f08450df4bc099e91 with run_leakbound_L.py sha256 679b80730c1eb8e3ecfd1d037e2819b89317aed6d54e6fe437200672f001f47a; coverage_report.py sha256 d3a4183dae09ae75a77e061fa289b7ec3723d48ebd74e3e9df923918f63d6b51.
Exit codes: check_refit_env 0, run_leakbound_L 0, coverage_report 0. Peak RSS 1402552 kB (getrusage, children). Finished 2026-11-13T14:56:15Z after one tracked restart (see RESTART_LOG.txt; resume receipts confirm the six input shas unchanged).

Per-fire and per-fold aggregates and receipts only: no cell data. The feature cache, work/ and fold_*.pkl are not committed and stay in the run container until verification is done.

```
47bfbcc4faee130be7c4eb4609aafcd0060196a9cdea77c84df50a19343316a5  LEAK_BOUND.json
9932b7f30770f5ca26880c6ca13c36869b818d9e765e25f19b5294de10b223c6  LEAK_BOUND.md
c1fd8271dfad6acfc2b3fe15247180b77d6fb3c1a93d42078d360a7c33abbe2b  COVERAGE.json
636fad2e1bf1e57566011c6c5aa48fb5944e0c68ea2503ade71a538d3a6f477a  RECEIPT_START.json
b767418c257d62924b9bfabd494ab3b83c594ec343792c004675ea6644d9f09c  RECEIPT_RESUME_1.json
8a21806b944bcc553278c10efff032537ee46750bc512fd2a75a1a3d89459892  RECEIPT_RESUME_2.json
1b00119c9ba70f8229a96ab2cc2400925c4d79b124e04ea9ae7cd58a55238c30  RESTART_LOG.txt
56bf3784daa01c1c51d5ed5e236967c81696d47b393b71df662f69fbff0bc15b  REFIT_ENV_CHECK.json
a5ba17b417ca7b05fc52525c3b7173a2f068ef2ac53b20585fd7c41aaaedf6a5  fold_0_agg.json
6cd5e4bb405273ac26520080484c2d4ec5876a3092a483a14fb4ad649a571a80  fold_1_agg.json
f18d34d596ca93075828f68a97fcc85cc265670408a18826c4a8225d9bc71995  fold_2_agg.json
094629296029123b83102dfb1299347b5e9975c40fe8c45e6dd5e4e168f97ff7  fold_3_agg.json
d79c00f96f1ef21acc39fa9dbc1969daab48b6b3825f15e82e17f7754a6cef41  fold_4_agg.json
```
