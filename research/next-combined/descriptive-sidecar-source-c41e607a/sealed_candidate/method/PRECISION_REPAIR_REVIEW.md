# Independent development precision harness review

Scoped PASS for the separately versioned checker repair. The original actual-result HOLD is a checker precision inconsistency: one development-score assertion used exact float equality while the same checker already used a finite numerical comparison policy for independently reconstructed floats. No production result, model, cohort, frozen selection, primary rule or track file is changed. The corrected checker has not been run on actual current outputs.

## Source-grounded diagnosis

At frozen B source head `691cc162bf2c0295cecc257a558ae0d583f9018e`, selection's `development_selection` appends each per-fire Brier in fixed SPLIT fold and fire order and computes `sum(scores) / len(scores)`. The report's `ablation` constructs `brier * weight`, groups by variant and fire, divides grouped squared-error totals by weights, then computes a pandas mean in grouped fire order. These evaluate the same equal-fire statistic in real arithmetic but have different floating operations and accumulation order.

An independent development-only reconstruction used all 21 frozen phase result JSONs, with 23 distinct development fires per variant. Every phase file matches both its frozen MODEL_SELECTION identity and the earlier parent V2 development evidence. It imports no production computation helper and reads no current RESULTS.json or current heldout/Korean metrics or prediction arrays. The independent reconstruction exactly reproduces both producing paths and the development-only CSV.

For `d4_wind`:

| Quantity | Value |
| --- | --- |
| Frozen selection, Python sum/SPLIT order | `0.037495116098823784` |
| Reconstructed report grouped/weight-roundtrip mean | `0.03749511609882378` |
| Difference | `-6.938893903907228e-18` |
| Difference in ULPs at frozen value | `-1.0` |
| Frozen float hexadecimal | `0x1.3328f52ceef89p-5` |
| Report float hexadecimal | `0x1.3328f52ceef88p-5` |

The correctly rounded exact rational mean of the binary input floats and the earlier independent parent `statistics.fmean` both equal the frozen selection value. All other six reconstructed variant means are bitwise equal across the two paths. The frozen selection remains `d4_wind` under the exact pre-existing minimum and tie-order rule. This explains floating representation, not a different scientific estimand or selected model.

The development proof passes 256 correlated metadata/arithmetic predicates. These are bookkeeping and consistency controls, not independent scientific observations.

## Minimal checker change

`v2/check_results.py` is copied from original checker SHA `b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8`. Its sole source diff replaces the development `mean_fire_brier == frozen_mean` component with the existing `compare()` helper and retains the null-effect assertion separately. The original source is recovered exactly by reversing that one textual replacement.

The pre-existing unchanged helper requires a finite numeric actual value and `math.isclose(actual, expected, rel_tol=2e-10, abs_tol=2e-12)`. No tolerance constant, model-specific branch, cohort filter or outcome-dependent exception was introduced. That policy predates the actual result review and is already used for independently reconstructed report metrics.

Every other assertion stays byte identical, including exact frozen selection minimum/tie order, report and registry selection identities, all seven checkpoint pointers, model coverage, both cohorts, metrics, bootstrap, primary gate and heldout ablation. All four development paired-effect fields must still be null for every variant. This change does not recalculate or relax model selection.

The current RESULTS.json was deliberately not read during this repair review. The parent's observation of its four null effect fields is not presented as a new independent current-output verification here. Synthetic probes verify that those guards remain effective.

## Tests and preservation

- The unchanged original selftest, copied beside the new checker, passes all 38 synthetic controls.
- All 63 targeted synthetic prefix controls pass. They accept generic adjacent floats for each of the seven means, reject material development-score drift for every variant, reject each of four nonnull effect fields for every variant, reject invalid numeric types and nonfinite values, and reject report selection changes, selection digest changes, frozen selected-variant changes and changes that violate the exact frozen minimum.
- The old checker independently reproduces its rejection on a generic one-ULP synthetic difference. The new comparison helper source is byte identical to the original policy.
- Targeted probes stop before cohort access. The original selftest uses marked synthetic bundles only. No actual corrected checker run was performed.
- Original checker and actual HOLD receipt remain unchanged and are also copied into `original/`. The first local proof harness assumed a named CSV variant column, received a KeyError because this CSV uses an unnamed index column, and was corrected using an explicit header check. Its initial script and log are preserved; this was a local harness issue.

| Artifact | SHA256 |
| --- | --- |
| Corrected `v2/check_results.py` | `87eb9a2467f4e8011e960273ca77a6878a7807173f5869041905363214a297aa` |
| Original checker | `b3fb96f6c42a028b1e8ac67414b60e8b77735f9cf8559f784f546a7ab7929ee8` |
| Original actual HOLD receipt | `a2be36da59998020740f458e82df3df8fcdc282ffa11875b65c9f82970fb1fdc` |
| Exact two-line repair diff | `0c318475683f167f65f65c7b140f0356660639ac61f61477200687c2dfc91b2a` |
| Frozen production report source | `56e7769084481167cc57d2d62510eef37cb4f7657826e9737985b77d9dd7dfc7` |
| Frozen production selection/auditor source | `65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536` |
| Frozen MODEL_SELECTION | `f5e763e7acd7a400d9fcdffec8092651c0cea1df4bcff8df4d05d24a865af73b` |
| Development-only ablation CSV | `0c742fefcb7538fe1033dc9147cab41b0214a11de5336793a927fc8869fe3b6d` |

## Evidence scope and limits

Tier 2 graph project `wfg-next-independent-results-20261030` was ready at generation `2026-10-30T13:27:37Z`; the exact checker `audit` and `compare` symbols and snippets were read. Coverage is metadata_match with no recorded gap for original `check_results.py` and `selftest.py`, a best-effort signal. The B source graph excludes research scripts, so the complete relevant producing functions were read directly and exact frozen source hashes were checked. The new scratch checker is unindexed; its complete focused diff and synthetic behavior are the evidence.

All writes stay under `work/final-result-precision-review/`. No production file or original evidence was modified, and no model, actual cache, raw raster, current heldout/Korean metric or prediction array was opened. No training, inference, heavy job, full production test suite or corrected actual audit was run. This review does not clear final heldout metrics, interval census, figure validity or scientific claims. Those remain subject to separate authorized result audits.
