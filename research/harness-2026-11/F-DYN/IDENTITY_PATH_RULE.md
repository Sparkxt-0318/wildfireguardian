# Host-independent packet identity: the radiation module path (rule; fixed before any code or rebuild)

Finding by Mira, relayed by the orchestrator on 2026-11-12. Thomas confirmed it independently with content digests
(16 of 16 equal).

## What differs

- v3.4 `HAZARD.json`, `REPORT.json` and `NATIVE_METADATA.json` differ between checkouts in **exactly one field**:
  `provenance.identity.radiation_operator.module`. In REPORT and NATIVE_METADATA it sits at
  `identity.radiation_operator.module`.
- That field is the absolute filesystem path of the vendored radiation module `wildfire/heat.py`.
- `constructed_arrays.npz` is byte-identical across checkouts.

## Where it comes from

- The field is set by `bridge.radiation_operator_identity()`, which returns `{"module": H.__file__, "sha256": …}`.
- `bridge.py` is **frozen** (FROZEN_GIT_BLOBS, LATEST_INPUT_FREEZE), so it is not edited.
- The F-DYN packet child already replaces `bridge.draw_ignitions`, `bridge.settings_for` and `bridge.construct`, in
  its own process only. The fix uses the same mechanism.

## Rule

1. **Replacement.** In `fdyn/_packet_child.py` only, `bridge.radiation_operator_identity` is replaced, before the
   writer runs, by a function that returns:
   - `module`: the path of `wildfire.heat.__file__` **relative to the repository root**, POSIX separators
     (e.g. `integration/src/wfg_latest/radiation/heat.py`);
   - `sha256`: unchanged, `bridge.sha256_file(H.__file__)`;
   - `module_path_form`: `"repo-relative (F-DYN IDENTITY_PATH_RULE.md)"`.
2. **Hard failures.** The build fails if:
   - the module does not resolve under the repository root (`RADIATION_MODULE_OUTSIDE_REPO`);
   - its sha256 is not the vendored pin `f52b4c31…` that `build_packet.py` checks (`RADIATION_MODULE_NOT_PINNED`);
   - the replacement is not called exactly once (`RADIATION_IDENTITY_INJECTION_NOT_USED`).
3. **What does not change.** The construction id hashes the settings digest, the export, the cutoff, the bridge
   source and the graph. It does not hash the radiation identity, so these are unchanged:
   - construction id and scenario ids;
   - breakpoints, flame, flux and support;
   - every array and the settings digest.

   Only the `module` string changes, and the `module_path_form` key is added.
4. **Tests (acceptance).**
   - (a) **Two checkouts.** The same manifest entry is built in two checkouts of the same commit, at different
     absolute paths. `HAZARD.json`, `REPORT.json`, `NATIVE_METADATA.json` and `constructed_arrays.npz` must have
     identical sha256. This runs for one sample per variant (4 packets).
   - (b) **Against v3.4.** Each v3.5 sample is compared, as parsed JSON, with its v3.4 counterpart. The only
     differences allowed are the `radiation_operator.module` value and the added `module_path_form`, in the three
     JSON files. The npz must be byte-identical.
   - (c) **Unit test.** The injected identity is repo-relative and has the pinned sha.
5. **Manifest.**
   - New file: `MANIFEST_v3_5.json` (`wfg.fdyn.manifest/6`), with packets under `packets_v35/`.
   - v3.4 is listed as superseded: "content-identical; differs only in the absolute radiation module path".
   - The builder self-check counts and the variant set are carried over.
   - The pinned v3.4 file is not edited.
6. **Verification.** Nora re-verifies.
