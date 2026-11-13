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

- **Burnset vs kriged_mean and firms_early.** At the same origin and departure, no burnset arrival is earlier. A
  NO_ROUTE counts as +∞. Most pairs are decided by burnset NO_ROUTE alone. Only Yeongdeok has pairs with two finite
  arrivals: **54** against each comparator, 52 of them with equal T.

  | Start | vs | Pairs | Both finite | Burnset NO_ROUTE, other ROUTE | Both NO_ROUTE | Burnset earlier |
  |---|---|---|---|---|---|---|
  | Uiseong | kriged_mean | 168 | 0 | 102 | 66 | 0 |
  | Uiseong | firms_early | 168 | 0 | 94 | 74 | 0 |
  | Yeongdeok | kriged_mean | 180 | 54 | 126 | 0 | 0 |
  | Yeongdeok | firms_early | 180 | 54 | 94 | 32 | 0 |

  `nr2_summary.py` asserts this ordering as a standing check. Any burnset-earlier pair fails the summary.
- **Same claim at 0 s and 7200 s.**
  - Uiseong: every origin in all three variants.
  - Yeongdeok: kriged_mean 90/90, burnset 90/90, firms_early 76/90.
  - In Yeongdeok firms_early, 14 origins are ROUTE at 0 s and NO_ROUTE at 7200 s, and none goes the other way. This
    is why the two departures are separate results. No origin here shows the reverse case (NO_ROUTE at 0 s, ROUTE at
    7200 s) that §4 allows under dead-end-only waiting.

## Identity of the packets

The gate record's `hazard_sha256` is host-specific: HAZARD.json embeds absolute paths, so an identical rebuild on
another host has a different hash. It records this host's file; it is not an identity. Identity is the npz sha256, the
writer sha and the bound digests (I, G, A, W, Q), and those match an independent rebuild (verification ledger 136).

## Not covered

- Radiation, dose and peak; the 360 other packets; h8; and the kit's whole-road model. For that model, see
  DOMINANCE_RULE; no kit run is compared here.
- The gates (G-C) are a single implementation.
- Every row's certificate is checked by two checkers and by O2. The generator's instance (`build_instance`) and O2's
  (`derive_instance.derive`) are separate code paths, but both were written by the author. O2 agreement is therefore
  not an independent derivation of the instance from the packet.
