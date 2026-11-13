# F-DYN no_reentry/2 certificates, scope (a): result (NR2_CERT_RULE.md + erratum 1 + note 2)

Files:
- `results/nr2_scope_a.json`: per packet, the gate record, rows, claims per departure, verdicts and the PASS/FAIL
  result; the labels; the out-of-scope list.
- `results/nr2_scope_a_rows.jsonl.gz`: all 1,220 merged records (8 gate records + 1,212 rows), each with the bundle
  sha256. The bundles are kept outside git and identified by that sha.

Produced by `xcheck/nr2_certs.py` (sequential to 618 rows, then `--shard k/4`; restarts logged) and merged with
`--merge` (0 duplicate keys; every bundle sha re-checked on disk). Summarised by `xcheck/nr2_summary.py`.

**Label:** "F-DYN no_reentry/2 (person-facing default): relaxation certificates, bound and verified by verify_bound
(both checkers, structure, O2); contact only, no radiation".

**Waiting rule, form (S):** "The trip starts at the stated time. Once moving, a stop is allowed only at a road dead
end (a graph dead-end node), which may be a short detour off the route; waiting is not allowed at any other node,
including the start unless it is itself a dead end. Other departure times are separate results."

## Result: 6 of 6 certified packets PASS; 1,044 of 1,044 rows FULLY_BOUND

| Packet (h5, no_reentry/2) | Gates | Rows | d = 0 s | d = 7200 s |
|---|---|---|---|---|
| Uiseong 0324T09 kriged_mean | PASS (P1 0/0) | 168 | 51 ROUTE / 33 NO_ROUTE | 51 / 33 |
| Uiseong 0324T09 firms_early | PASS (P1 0/0) | 168 | 47 / 37 | 47 / 37 |
| Uiseong 0324T09 envelope_burnset* | PASS (P1 0/0) | 168 | 0 / 84 | 0 / 84 |
| Yeongdeok 0325T11 kriged_mean | PASS (P1 0/0) | 180 | 90 / 0 | 90 / 0 |
| Yeongdeok 0325T11 firms_early | PASS (P1 0/0) | 180 | 81 / 9 | 67 / 23 |
| Yeongdeok 0325T11 envelope_burnset* | PASS (P1 0/0) | 180 | 27 / 63 | 27 / 63 |

\* Burnset rows keep their own label: "envelope_burnset: sound relative to the final mapped burn set; burn set =
kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only); single
implementation, not independently checked". It is a static footprint bound.

- **Departures.** 0 s and 7200 s are separate results, never a leave-by window.
- **Gate-only.** The two h5 `envelope` packets went through the gates only: both GATES_PASS, P1 0/0. Erratum 1: they
  are routable by design under no_reentry/2, not refused as §2 expected.
- **Out of scope, data only.** 168 Uiseong envelope rows (94 ROUTE, 74 NO_ROUTE, all FULLY_BOUND) were certified
  before `--gate-only` existed. They are not results. Their contact field equals firms_early's (all 1,277 cell
  intervals; all 15 arrays element-equal), and so do their claims and T.
- **Uncertified.** The other 360 certifiable packets of MANIFEST_v3_7 no_reentry/2 carry no F-3.2 certificate.

## Observations (measured on these rows; consistency checks, not claims of the rule)

- **Burnset vs kriged_mean and firms_early.** No origin and departure has a burnset arrival earlier than kriged_mean
  or firms_early. 0 of 168 at Uiseong, 0 of 180 at Yeongdeok. A NO_ROUTE counts as +∞.
- **Same claim at 0 s and 7200 s.**
  - Uiseong: every origin in all three variants.
  - Yeongdeok: kriged_mean 90/90, burnset 90/90, firms_early 76/90.
  - In Yeongdeok firms_early, 14 origins are ROUTE at 0 s and NO_ROUTE at 7200 s, and none goes the other way. This
    is why the two departures are separate results. No origin here shows the reverse case (NO_ROUTE at 0 s, ROUTE at
    7200 s) that §4 allows under dead-end-only waiting.

## Not covered

- Radiation, dose and peak; the 360 other packets; h8; and the kit's whole-road model. For that model, see
  DOMINANCE_RULE; no kit run is compared here.
- The gates (G-C) are a single implementation.
- Every row's certificate is checked by two checkers and by O2. The generator's instance (`build_instance`) and O2's
  (`derive_instance.derive`) are separate code paths, but both were written by the author. O2 agreement is therefore
  not an independent derivation of the instance from the packet.
