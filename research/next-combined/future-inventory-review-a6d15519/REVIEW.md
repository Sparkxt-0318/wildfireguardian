# Independent future-inventory adapter review

Immutable source: `work/audit-1b` at `a6d1551926ad9d830836e4b0d77ee9a7b8e9cd0d`; adapter SHA256 `f9b8e7d165b0a6713e2ac0e0c50d0f439b77db3d890aa4cbfc2d06b5fa14bd8c`. This review read the entire 494-line adapter and 446-line synthetic test file, plus the relevant `survey_states` and environmental loader dependency methods. Only generated synthetic fixtures were executed. No real raw archive, 2026 study data, heldout data, forecasts, or heavy/timed experiment was accessed or run.

**Recommendation: repair the three confirmed fail-closed gaps before adopting or wiring this adapter into a preregistration command.** The module correctly continues to emit `NOT_READY_FOR_2026_EXECUTION`; none of the findings establishes permission to access future study data or relax external documentary gates.

## Confirmed findings

### P1: directory symlinks defeat environmental snapshot pinning

`research/forecast-v2/scripts/blind_inventory.py:117-127` enumerates environment files with `Path.rglob`, which does not descend into directory symlinks. `_inside` at lines 87-93 only requires resolved source targets to remain somewhere under `input_root`. Later `_availability` and `load_data` follow explicit source paths through such symlinks.

Reproduction: move the synthetic `environment/regions/SYNTHETIC_A` directory to `input_root/borrowed-region`, then symlink the former directory to that target and pin the environmental snapshot. The resulting pins contain only `environment/events.json` and `environment/biome_classes.json`; no raster or weather metadata is pinned. Validation nevertheless admits two cases. Rewrite the slope raster from ones to 99 without changing the pinned manifest: validation still admits two cases with `LOCAL_INVENTORY_VALIDATED_EXTERNAL_RELEASE_UNVERIFIED`. The source hash changes from `447a01c12b34c5641f5e9bc28ac4e6092928541e32a1aa5e2bcb777305072b1d` to `6d2eeea3dfbc1b296879944ec44f07d645352957dfe16f3570a9bba5489990ee`.

This undermines the stated complete environmental custody closure. Reject symlinks in the environmental tree and canonical source-path components, or deliberately traverse and pin the full resolved dependency closure with cycle/alias handling. A synthetic regression should mutate a source reached through an internal directory symlink without repinning and require refusal.

### P2: trailing DBF records are silently ignored

At `research/forecast-v2/scripts/blind_inventory.py:204-209`, the check requires `header + count * record_size <= len(dbf)`, so arbitrary trailing bytes pass. Record iteration at lines 219-252 uses only the declared count. Unlike the SHP trailing-byte check at lines 253-254, DBF has no corresponding exact-consumption check.

Appending one complete 221-byte record to the synthetic DBF while retaining header count three, then pinning the whole archive, is accepted. The report contains raw record count three, no record failures, and two admitted cases. The extra DBF record has no indexed SHP counterpart, so this is a malformed/inconsistent bundle that should fail closed rather than be silently accepted.

Require exact DBF header/payload consumption, allowing only explicitly supported optional DBF EOF termination. Preserve a synthetic appended-record and appended-garbage negative control.

### P2: the nested-source blocklist misses common archive wrappers

`research/forecast-v2/scripts/blind_inventory.py:183-187` rejects `.zip`, `.tar`, `.gz` and several other suffixes, but accepts `.tgz`. The whole member is hashed, so this is a semantic inventory gap rather than missing ZIP member custody.

A valid pinned `other/archive.tgz` containing a complete second SHP/DBF/SHX/PRJ/CPG bundle with three `SYNTHETIC_B` records is accepted. The report inventories only the three direct `SYNTHETIC_A` records, never detects B's missing catalog entry, and admits two A cases. The existing `other/archive.zip` negative control does not exercise this case.

Adopt an explicit admissible-member/source-format contract and reject unknown source payloads or unresolved wrappers. At minimum, detect/refuse common alternate nested archive formats such as `.tgz`, rather than relying on the current incomplete suffix list. A complete ZIP hash does not establish complete incident enumeration inside unparsed members.

## Checks that remain sound within the reviewed scope

- Archive and manifest bytes, direct non-directory ZIP member sets/hashes, duplicate/case-colliding names, required direct SHP components, deleted DBF records, sequential SHP offsets and trailing SHP bytes are checked.
- Failed geometry/membership/time admission aborts cohort admission rather than silently excluding a problematic record. All direct SHP records, including same-time and unsorted records, feed the inventory before eligibility.
- Within the declared pinned policy, eligibility uses operational first-survey year, catalog nominal year, strictly consecutive positive intervals at most 48 hours, and source availability/alignment. No growth or environmental-value filter selects the cohort. Entirely unknown values do not remove cases.
- Reference comparison reconstructs cumulative mapped survey states from all admitted direct raw records at every distinct survey time; it compares exact full-grid shape, dtype, values, and ordered timestamps. Extra prepared masks do not select reference cells. The grid remains the caller's declared catalog grid; this does not independently establish its authoritative extent.
- Environmental availability verifies the fixed six source channels at the cutoff floored to a UTC whole hour via source band metadata, full grid alignment and label-free loading. The exact survey cutoff/endpoint timestamps remain in case records. This review found no additional clock/reference defect in that declared convention; future scorer wiring must preserve it.
- Caller release attestations are explicitly labeled unverified, and all successful and failed controls retained `NOT_READY_FOR_2026_EXECUTION`.

## Reproduction and limitations

Run from the task directory:

```
PYTHONDONTWRITEBYTECODE=1 work/venv-forecast/bin/python work/future-inventory-review/reproduce_candidates.py
```

`reproductions.json` records all three observed acceptances. The script constructs only tiny synthetic 3x3 inputs beneath `work/future-inventory-review/` and is repeatable. The audited checkout remained clean. The owner's 37-test suite was read but not independently rerun; the three missing negative controls above were executed independently.

Graph project `wfg-next-1b-audit-a6d15519-20261030`, generation `2026-10-30T05:05:54Z`, was confirmed ready. Test discovery returned all 45 indexed entities with no further page. Tests and the two inspected loader/reference dependency files were metadata-matching with no recorded gap. The entire adapter was excluded by the scripts subtree and was therefore read directly in full. Coverage metadata is a best-effort signal, not proof of completeness.

This software/protocol review does not authenticate a publisher, release version, first public release, release time, real archive completeness, pre-access registration chronology, dependency closure, upstream environmental availability, or physical ignition year. Those remain independent documentary requirements. Even after software repair, the module's execution status must remain NOT_READY until the separately registered gates are discharged.
