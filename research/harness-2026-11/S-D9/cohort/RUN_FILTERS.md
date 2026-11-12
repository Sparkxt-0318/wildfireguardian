# Applying A1 §1.2 items 8–12 and §1.3 (metadata only)

```sh
git show origin/daniel/data-fetch:research/harness-2026-11/data-fetch/incident_metadata.csv > raw.csv   # sha256 5246ce8f… (daniel/data-fetch 259ef5b4)
python3 cohort/prepare_meta.py --raw raw.csv --outdir F
python3 cohort/apply_filters.py --split cohort/COHORT_SPLIT.csv --meta F/meta.csv --ref F/ref.csv --out cohort/COHORT_FINAL.csv \
  --ledger-id CA-ENF-024030_Caldor --ledger-id CA-SCU-005740_SCULightning \
  --ledger-id CA-LNU-013407_LNULightningComplex_Hennessey --ledger-id CA-LNU-013407_LNULightningComplex_Walbridge \
  --ledger-id CA-TIA-003058_Windy --ledger-id CA-NOD-004727_W5ColdSprings --ledger-id CA-SHF-001175_McFarland \
  --ledger-id CA-LPF-002428_Dolan \
  --opened NM-LNF-000227_Blue2 --opened OR-WIF-240214_MossMountain_Chalk --opened OR-UPF-240311_Homestead_Salmon33
```

- The expected COHORT_FINAL.csv sha256 is 13078990db5bb673de6e99ada82a3d6e2dd2950fa142cdb8f4d36ee57b9f4a40.
- Kept: a 489, b 30, c 30, d 32. Excluded: a 97, b 5, c 8, d 13. Replacements into b or c: 13. Missing metadata: 9 incidents, all in part a.
- `PART_A_ALLOWLIST_FINAL.csv` holds the kept part-a incidents (489).

**Ledger IDs.**
- Caldor 2021 is in the ledger (INSPECTED, routing perimeters).
- The other 7 are NIROPS incidents whose names match GOFER fires. All 28 GOFER fires had aggregate label statistics inspected by S-D1 (ledger, ACCESS_CONTROL.md).
- The name match was done by hand on incident names only and is listed here in full.
- GOFER-matched incidents in part a stay in the training pool.

**Opened.** These are the three pilot fires built by Daniel (daniel/data-fetch 60a94974). Their perimeters were opened.

**Disclosure.** The first filter run omitted `--ledger-id` and `--opened`. That run placed Caldor into part c as a replacement and kept Homestead_ReynoldsButte in part b. Only the run's metadata output was viewed (incident names and reasons), not any perimeter or outcome.
