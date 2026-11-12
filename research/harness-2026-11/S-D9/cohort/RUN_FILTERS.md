# Applying A1 §1.2 items 8–12 and §1.3 (metadata only)

```sh
git show 259ef5b4:research/harness-2026-11/data-fetch/incident_metadata.csv > raw.csv   # sha256 5246ce8f…
# The split input is pinned to daniel/data-fetch 3129ad59, because later commits changed the file:
# git show 3129ad59:research/harness-2026-11/data-fetch/nirops_incidents.csv > n.csv   # sha256 f2aae4b8…; then select_cohort.py
python3 cohort/prepare_meta.py --raw raw.csv --outdir F
python3 cohort/apply_filters.py --split cohort/COHORT_SPLIT.csv --meta F/meta.csv --ref F/ref.csv --out cohort/COHORT_FINAL.csv \
  --ledger-id CA-ENF-024030_Caldor --ledger-id CA-SCU-005740_SCULightning \
  --ledger-id CA-LNU-013407_LNULightningComplex_Hennessey --ledger-id CA-LNU-013407_LNULightningComplex_Walbridge \
  --ledger-id CA-TIA-003058_Windy --ledger-id CA-NOD-004727_W5ColdSprings --ledger-id CA-SHF-001175_McFarland \
  --ledger-id CA-LPF-002428_Dolan --ledger-id CA-KNF-007084_Devil \
  --opened NM-LNF-000227_Blue2 --opened OR-WIF-240214_MossMountain_Chalk --opened OR-UPF-240311_Homestead_Salmon33
```

- The expected COHORT_FINAL.csv sha256 is d5ae66f4208f9936fd6379000aae7ba3b2afbdf04ef09b6a6b4b09044f6452eb.
- Kept: a 490, b 30, c 30, d 31. Excluded: a 96, b 5, c 8, d 14. Replacements into b or c: 13. Missing metadata: 9 incidents, all in part a.
- `PART_A_ALLOWLIST_FINAL.csv` holds the kept part-a incidents (490), sha256 7db3cc0ef084d4ed09624a0b2ad14ffebc90a94fe7efb94cab8dd2d4f09f85cd.
- **Correction (Hannah FAIL, verified at 6fabb4bd).** CA-KNF-007084_Devil is GOFER "Slater and Devil" (inspected by S-D1) and had been kept in part c as a replacement. It is now a ledger exclusion. Its part-c slot goes to ID-SCF-022091_WolfFang. Its sibling CA-KNF-007035_Slater (part a) is no longer near any test incident, so it returns to the training pool. The earlier hash 13078990… is superseded.

**Ledger IDs.**
- Caldor 2021 is in the ledger (INSPECTED, routing perimeters).
- The other 8 are NIROPS incidents whose names match GOFER fires. Devil was added after Hannah's check; she name-matched all 28 GOFER names against b, c and d and found no other miss. All 28 GOFER fires had aggregate label statistics inspected by S-D1 (ledger, ACCESS_CONTROL.md).
- The name match was done by hand on incident names only and is listed here in full.
- GOFER-matched incidents in part a stay in the training pool.

**Opened.** These are the three pilot fires built by Daniel (daniel/data-fetch 60a94974). Their perimeters were opened.

**Disclosure.** The first filter run omitted `--ledger-id` and `--opened`. That run placed Caldor into part c as a replacement and kept Homestead_ReynoldsButte in part b. Only the run's metadata output was viewed (incident names and reasons), not any perimeter or outcome.
