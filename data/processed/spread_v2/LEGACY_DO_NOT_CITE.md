# ⚠ LEGACY BUILD — DO NOT CITE ANY NUMBER IN THIS DIRECTORY

Everything in `data/processed/spread_v2/` is output from **Build A**
(`src/wildfireguardian/spread_v2_xgb/`, seed **42**), which is **superseded and
abandoned**. It is kept because deleting evidence is worse than labelling it —
not because it is quotable.

**The canonical artifact is [`../spread_v2_lofo.json`](../spread_v2_lofo.json)
(seed 20250603).** Every reportable number lives in
[`docs/NUMBERS.json`](../../../docs/NUMBERS.json).

## The trap this directory sets

Both builds produce a file called `lofo_metrics.json`, both report a
"mean fold AUC" and a "pooled AUC", and the two sets of numbers are close enough
to look like rounding differences. They are not. They are different models
trained on a different fire set.

| | **canonical** (Build B) | **legacy** (Build A, this directory) |
|---|---|---|
| file | `data/processed/spread_v2_lofo.json` | `data/processed/spread_v2/lofo_metrics.json` |
| model | sklearn `HistGradientBoostingClassifier` | XGBoost (superseded Build A) |
| seed | 20250603 | 42 |
| mean-of-folds ROC-AUC | **0.890** ± 0.107 | 0.8309 <!-- forbidden-ok: 0.8309 --> |
| pooled OOF ROC-AUC | **0.905** | 0.8337 <!-- forbidden-ok: 0.8337, 0.834 --> |
| fire set | includes `gangneung_2023` | includes `gangneung_donghae_2022` |
| rows / positives | 151,904 / 2,989 | different |
| status | **REPORT THIS** | **DO NOT REPORT** |

The fire sets differ, so the two AUCs are not comparable even in principle — one
is not "the older estimate" of the other.

`scripts/check_forbidden.py` treats the legacy values as HARD violations
everywhere in the repository. The two occurrences in the table above carry line
pragmas because this document's job is to name them.

## Files here

| file | what it is |
|---|---|
| `lofo_metrics.json` | Build-A leave-one-fire-out metrics. **Superseded.** |
| `comparison_metrics.json` | Build-A ablation (distance-only / no-weather / with-weather). **Superseded.** |
| `importance_metrics.json` | Build-A permutation importance. **Superseded.** |
| `class_balance.json`, `audit.json`, `spread_sequences.json` | Build-A dataset diagnostics. |
| `features.csv.gz` | Build-A feature matrix (17 MB). |
| `weather_decomposition.json` | Build-A weather decomposition. |

## If you are writing a document

Do not open these files. Read `docs/NUMBERS.json`, or run:

```bash
make verify
```

## Why not just delete it

The Round-2 postmortem found the same quantity existing in two pipeline layers
with different values, and no marker saying which was authoritative. Deleting
Build A would remove the evidence that the problem existed and make the
correction unauditable. Labelling it costs one file and keeps the record intact.

See also [`../../../docs/SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md`](../../../docs/SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md).
