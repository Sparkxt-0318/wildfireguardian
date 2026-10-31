# Preserved numerical reference

`f9fa03290/` preserves prior tables, figures, test output and source identities from commit `f9fa03290d57dc3d226543833f612640fd9f414a`. Its source manifest binds that prior Git tree, not the current implementation. The old standalone polygon routine is retained as `solidflame_f9fa03290.py` so `../run_bounds_evidence.py` can reproduce its cancellation error without importing the current evaluator.

Historical CSV files are losslessly compressed as `.csv.gz`, preserving their original bytes and line endings. The comparison script decompresses them before parsing. Current CSV output uses LF line endings; this formatting change does not alter its values.

These files are historical reference evidence. Their former point values and coarse bounds are not silently replaced by the repaired implementation. Current tables and source hashes live in the parent evidence folder and the current experimental source manifest. The exact counterexample, table changes and figure-byte comparisons are generated into `../BOUND_RESULTS.json`.
