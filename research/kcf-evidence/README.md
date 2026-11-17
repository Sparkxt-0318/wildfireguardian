# kcf-evidence

Evidence pack for the deadline field (F-3.1) and the corridor router. Every number names the file it came from; the figures' numbers are listed one by one in `figures/FIGURE_NUMBERS.json`.

| item | file | status |
|---|---|---|
| 1. Clean timing, six caches | this README (below), `TIMING_linux_container.json`, `TIMING_RUN.sh`, `summarize_timing.py` | **Measured on a Linux container, not on the evaluated Mac.** Mac run still to do (one command below). |
| 2. Figure A | `figures/FIGURE_A_one_backward_pass.{svg,png}` | done |
| 3. Figure B | `figures/FIGURE_B_corridor_router.{svg,png}` | done |
| 4. Assumptions | `ASSUMPTIONS.md` | done (10 rows) |
| 5. Algorithm appendix | `ALGORITHM_APPENDIX.md` | Part 1 (deadline field, 10 steps, 6-node example) done. **Part 2 (calibrated reach rule) not written: I could not find the rule in `Main` or `codex/experimental-corridor-router-v8`.** |

`make_figures.py` rebuilds the figures from `research/harness-2026-11/F-3.1/results/SUMMARY_final_70f70d7.json` and the copied corridor evidence in `sources/corridor-router-v8/` (byte-for-byte from branch `codex/experimental-corridor-router-v8`, evidence/ directory; its own `SHA256SUMS` is included). `toy_example.py` runs the repository's field code and the brute-force oracle on the appendix's 6-node example.

## 1. Timing

**One sentence.** Same answers (0 disagreements on all 9,722 checks), about **35 times less compute** (4,393 s of single-process field time against 156,212 s of recorded per-check compute), **but not the same machine**: the recorded compute is from the evaluated Mac and the field was timed on a 4-core x86 Linux container, so the "same machine" claim cannot be made from this run.

What was run: `python3 -m deadline_field.reproduce <cache> --timing-only` once per cache, one process at a time, on an otherwise idle container (Linux 6.18, x86_64, 4 vCPU, Python 3.13.18, numpy 2.5.3), code at the checkout of this branch, inputs from `tools/fetch_routing_inputs.py` (SHA-verified). `--timing-only` skips the certificate check and the full-checker witness verification. It builds the three fields per destination set (`router`, `cert`, and the fire-free control `free`) and reads every job off them. Source: `TIMING_linux_container.json` (`timing_s` per cache in the run outputs).

| cache | jobs | recorded compute, s | field, all three variants, s | field, router + cert, s | field, cert only, s | peak RSS, MiB |
|---|---:|---:|---:|---:|---:|---:|
| Uiseong–Andong 03-23 01Z | 1,523 | 16,006 | 97 | 69 | 36 | 458 |
| Uiseong–Andong 03-24 09Z | 1,518 | 14,749 | 749 | 712 | 359 | 702 |
| Uiseong–Andong 03-25 17Z | 1,557 | 23,624 | 359 | 322 | 163 | 850 |
| Yeongdeok 03-25 19Z | 1,810 | 40,527 | 1,033 | 681 | 343 | 1,133 |
| Yeongdeok 03-25 23Z | 1,673 | 32,177 | 1,052 | 691 | 349 | 698 |
| Yeongdeok 03-26 08Z | 1,641 | 29,128 | 1,103 | 737 | 372 | 736 |
| **total** | **9,722** | **156,212** | **4,393** | **3,212** | **1,622** | max 1,133 |

Ratios (recorded ÷ field): **35.6×** against all three variants (the figure used in the sentence, the most conservative, includes the fire-free control that deadlines do not need); 48.6× against router + cert; 96.3× against cert only.

Three things to know before quoting this:

1. **The 147,900 s does not cover 9,722 checks.** `F-3.1/RESULTS.md` §5 attaches it to "the 9,722 recorded checks", but it is the sum of `compute_s` over the 9,443 planner *attempts* (`recorded_compute_s_sum` in `F-3.1/results/SUMMARY_final_70f70d7.json`, 147,900.1 s). All 9,722 route-check jobs in `planner/cache/*/*.json` sum to **156,212 s**. The field reads off all 9,722, so the matching denominator is 156,212 s. Against 147,900 s the ratio is 33.7×.
2. **Not same machine.** Recorded: macOS arm64, 15 CPUs (`planner/cache/INDEX.json`), 13 workers in parallel (`F-3.1/RESULTS.md` §5), so each `compute_s` includes contention. Field: one process, 4 vCPU Linux. `RESULTS.md` records this host as about 2.6 to 2.8 times slower than the Mac for the kit (a measurement I did not repeat), which would make the Mac's field time shorter and the ratio larger. That is an expectation, not a measurement. To get the same-machine number, run on the Mac from the repository root:

   ```bash
   bash research/kcf-evidence/TIMING_RUN.sh /path/to/new/empty/run_dir
   ```

   ```bash
   python3 research/kcf-evidence/summarize_timing.py /path/to/new/empty/run_dir research/kcf-evidence/TIMING_mac.json
   ```

3. **The earlier note about inflated timings is not supported.** `RESULTS.md` §5 says the Uiseong–Andong 03-24 and 03-25 field times (379 s, 235 s) were inflated by a concurrent numpy build. In this clean run the cert-only times are 359 s (03-24, recorded 379 s: reproduced) and 163 s (03-25, recorded 235 s: lower, not explained here). The 03-24 slowness is therefore not a build artefact. In both caches the slow phase is `issue_and_witness` (about 320 s and 130 s for each of router and cert), against 1 to 2 s for the first cache.
