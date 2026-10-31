# Independent known-footprint contact adapter review

Immutable source: `fd8bf2e78532b76d2dd2cfd094d3499def90fc23` at `work/audit-1c`. **Repair/recheck before clearing the proposed 320-record K study.** Three additional tiny API controls expose one source-admission defect and two exact-clock/claim defects despite all 47 existing fixture tests passing.

## Confirmed findings

### P1: known active fire outside known burned support is silently dropped

`experimental/sipp-routing/src/wfg_sipp/known_footprint.py:98-107` checks binary values, remaining durations and trajectory/cutoff agreement, but omits the original raw-state consistency check that known active burning must lie inside known burned support. Subsequent current-fire construction intersects activity with known burned support and thus removes contradictory active fire.

Starting from the ordinary admitted 3x3 fixture, set one road-interior cell to known active probability 1 and remaining duration 100 seconds while leaving its known burned value 0 and first-burn values -1. The new constructor admits it, sets `R=0` and `current_native=False` there, and both planners return `CHECKED_CONTACT_ROUTE_WITHIN_KNOWN_FOOTPRINT`; the independent raw checker also passes because it repeats the same intersection. The unchanged original `bridge_v2.construct` rejects the identical raw fields with `ContractError: RAW_ACTIVE_OUTSIDE_KNOWN_BURNED`.

Restore this fail-closed source consistency invariant before producing either search intervals or independent certificates. It is not a requirement to fill unknown cells or restore whole-domain unknown-mask refusal. Retain a valid known-current-fire control and a contradictory active/unburned negative control.

### P2: rounded search clock can support an incorrect earliest-arrival claim

The constructor permits fractional `member_valid_until_s`, but `known_footprint.py:360-371` floors the complete search horizon and applies that floored value to destination dwell. This changes the admitted contact problem when dwell is fractional, rather than merely limiting lattice arrival times.

Synthetic all-known example: source support ends at 2.5 seconds, destination b has arrival 1 and dwell 1.5, and destination c has arrival 2 and dwell 0. The raw checker admits b, including its exact finish 5/2. Both planners instead search with horizon 2, discard b and return c at 2 with `EARLIEST_CONTACT_ARRIVAL_WITHIN_SUPPORT_RESTRICTION`. The ordinary full-horizon control returns b at 1 for both methods.

Either preserve the exact finite finish/dwell bound while bounding lattice arrivals, explicitly reject a narrower unsupported timing contract, or name optimality only for the additionally rounded problem. Integer exclusive terminal bounds combined with fractional dwell deserve the same distinction. A checked returned witness remains contact-safe in this example; the problem is loss of a valid earlier witness and the overly broad restricted-optimality label.

### P2: timestamp precision is silently truncated during exact cutoff binding

`known_footprint.py:32-36` uses `datetime.fromisoformat`, which silently discards fractional digits beyond microseconds. Therefore `_validate_binding` at lines 198-199 accepts source cutoff `2025-01-01T00:00:00.000000001Z` as equal to request as-of `2025-01-01T00:00:00Z`. Both planners produce a checked result for this mismatch.

Reject nonrepresentable timestamp precision or compare exact instants without truncation. This does not show that the fixed native source timestamps have this problem; it contradicts the adapter's stated exact source/request clock-binding contract for inputs currently accepted by its API.

## Independently checked controls and retained strengths

- All **47 existing tiny known-footprint fixture tests passed**. This includes forged support/empty-flame views being rejected by the raw checker, strict/default/full-policy misuse refusal, turns/incoming context, closed chord/cut-point support, waits, dwell, terminal equality, unchanged original request/history, full-grid timing/prefix/window controls and frozen reference hashes.
- Every added negative/boundary probe started from an admitted all-known positive fixture. `api_boundaries_fd8bf2e7.py/.json` preserve the exact observed results, including comparison with the unchanged raw bridge admission.
- The independent checker reconstructs its own route structure, exact original geometry, issue contact, waits, full dwell, raw unknown cells and original-identity timing. It does not trust the derived support flags or cached flame intervals. The P1 finding arises before that independence boundary, in shared source semantics.
- Unknown occupied cells and finite-clock violations remain refusals. Restricted exhaustion is mapped to unresolved, with original-domain refusal/optimality unresolved and thermal/risk/full-policy status unknown. Public history is retained; the private history omission keeps position, incoming edge, departure and as-of unchanged and is explicitly labeled, without rebinding old thermal histories.
- Both solvers receive the same static support barriers and represented contact intervals. The copied sweep adds issue/EDGE/WAIT/destination support guards; the original frozen sweep and geometry stay unchanged. No dense fake-flame representation of unknown support was introduced.
- Receipt metadata checks verified 23 declared source hashes and two timing-reference source hashes. All **35 preserved evidence paths have identical Git blob IDs before/after this commit**. This checked Git metadata only; prior native graphs, NPZ trajectories and planner records were not opened. `receipt_checks.json` records this scope.

## Reproduction and review boundaries

From the task directory:

```
PYTHONDONTWRITEBYTECODE=1 work/venv-routing/bin/python work/contact-adapter-review/api_boundaries_fd8bf2e7.py
PYTHONDONTWRITEBYTECODE=1 work/venv-routing/bin/python work/contact-adapter-review/check_receipt_metadata.py
```

`targeted_tests.log` records the 47-test run. These are ordinary tiny software checks, not solver timing evidence. The owner-reported 91-pass/4-skip overlay regression was not rerun in full. Only `work/contact-adapter-review/` was written; source checkouts remain read-only. No real graph or trajectory array, native planner panel, new K study, HEAVY job, simulation, hardware or physical validation was accessed or run.

Graph project `wfg-next-1c-audit-fd8bf2e7-20261030`, generation `2026-10-30T07:47:04Z`, was confirmed ready. Relevant symbols, snippets and both-direction depth-one planner/checker traces were inspected with no remaining pages. Cited source/test/receipt/plan paths had metadata-matching coverage with no recorded gap. The excluded contact-mode documentation was read directly in full. Dynamic checker dispatch was verified from `adapter.install` and the actual checker source; spurious generic graph edges were not used as evidence. Coverage signals remain best effort.

This review is conditional on the supplied model arrays, geometry, clocks and pinned campaign construction. The API does not authenticate caller identity strings; a future controller must pin original files, rows, member identities, settings and clocks. No whole-policy, physical, original-domain no-route/optimality, thermal history or scientific-risk clearance is implied. The fixed source H=3600/T>H settings and contact-only scope remain distinct from the defects above; no old mask-only admission evidence has been relabeled as a timing result.
