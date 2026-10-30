# Independent read-only blind-tool review

The reviewer inspected source only, no heldout outcomes, and made no edits.
The initial tool is retained verbatim in BLIND_TOOL_V1.txt. It was never used
for a scientific evaluation and did not make the draft registration ready.

Concrete findings: registry selection and comparator pins were insufficient;
a relocated model root could verify one source tree while executing another;
declared year did not establish 2026 timestamps or consecutive source pairs;
prepared scoring masks could select arbitrary subsets; unhashed additional
NPZ files could enter scoring; missing cases had inadequate receipts; output
fire count alone did not establish completeness; and the primary comparison
and calibration decision were not computed. The whole-fire bootstrap's error
sum/count resampling was confirmed correct and is retained.

The repaired producer must derive references from hashed source arrays, derive
and compare the full eligible cohort, use exactly the verified source tree,
pin the model set and c651 identity, produce per-case receipts, reconcile the
exact file set, and expose every criterion before registration readiness.
