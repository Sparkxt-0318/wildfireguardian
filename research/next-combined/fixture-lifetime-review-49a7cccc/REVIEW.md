# Independent fixture catalog lifetime review

Scoped PASS at commit `49a7ccccc92b567e2c52ca91f92ae1efd88898ec`. No actionable defect found in the two-file test harness change. This is test fixture lifetime assurance, not actual coverage, model selection, registration, or heldout evidence clearance.

The catalog entry is copied inside the original metadata-patch context before later fixture mutations. The inner context then restores its temporary metadata mocks. The copied catalog alone is registered through the caller's pytest monkeypatch and is removed or restored at that test's teardown. All nine call sites supply the required keyword argument.

The independent tiny synthetic probe passed 52 of 52 checks. These include correlated pin and call-site bookkeeping predicates, not 52 independent experiments. It directly checked:

- The retained entry, current-source map, version map, and nested phase list are separate objects. Mutating the captured original entry leaves the retained snapshot unchanged.
- The temporary comparator SHA and verifier monkeypatches have already been restored when `build_fixture` returns.
- The unchanged synthetic fixture closure passes the test boundary. Mutating its pipeline source after freezing is refused, and the frozen catalog stays unchanged.
- The production version catalog and baseline map are restored after both successful verification and refusal.
- A freshly loaded unwrapped production F65 auditor refuses the synthetic source closure even while the test catalog is registered.
- Teardown restores the global fixture dictionary exactly, removes this fixture's key, and the same synthetic source closure then receives no admission.
- The two modified test sources match the pinned Git blobs. Production F65 and report.py are byte-identical to the parent commit, and the supplied source/package pins remain unchanged after the probe.

## Source and package pins

| Item | SHA256 |
| --- | --- |
| `forecast/tests/test_report_readiness.py` | `2b76b959738ee702bca38466da2b5d43882bcdd87eff72c947022aa6de905e6a` |
| `forecast/tests/test_report_ablation.py` | `8e249210abb5ed2111e3be86fcba0500e06355ebd593ed0668b9383fd5d2581f` |
| Production F65 `audit_fit_coverage.py` | `65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536` |
| Production `report.py` | `56e7769084481167cc57d2d62510eef37cb4f7657826e9737985b77d9dd7dfc7` |
| Author `FIXTURE_LIFETIME.patch.gz` | `6d737af2b9801ac97e6ccd94b7d7bca6ec65308708ad61f1869fa2e264a8157c` |
| Author `MANIFEST.json` | `52631a932ec62945b021c464ad40fea8a212445b5c8fa49353bd200b4b743285` |

The compressed patch also decompresses to the author's declared patch SHA `266e4b475d2169f9bc5a66f22f88f8a2df991de073c81a79064643f0bef994f3`. The author's 118 combined targeted tests were read as saved evidence and were not rerun.

## Evidence method and limits

Graph Tier 2 project `wfg-next-1b-fixture-49a7cccc-20261030` was ready with generation `2026-10-30T12:52:57Z`. Search found the exact fixture and new lifetime test with no remaining page. The fixture snippet and depth-one inbound and outbound trace were reviewed. All nine inbound callers are present. Outbound edges include heuristic name matches, so those edges are not relied on as runtime resolution evidence.

Coverage for the two changed test files and `test_blind_forecast_protocol.py` is metadata_match with no recorded gap, a best-effort signal. Production auditor scripts are excluded and not tracked by this graph. Direct source was read for `_verified_producer_version`, its current baseline restoration boundary, the synthetic test wrapper, `freeze_inputs`, the changed fixture function, the new lifetime test and the complete focused diff. Exact production F65 bytes were pinned rather than inferred from missing graph results.

Only tiny synthetic fixture data and dummy checkpoint byte strings were constructed under this reviewer's scratch directory. No track files were modified. No plotting, full suite, fitting, actual input arrays, actual model or checkpoint loading, forecasts, heldout outputs, live canonical audit, selection, or registry operation was performed. The concurrently running full-suite gate was not duplicated or interrupted.

The separate actual coverage review must use its own authorized final receipt and source-window pins.
