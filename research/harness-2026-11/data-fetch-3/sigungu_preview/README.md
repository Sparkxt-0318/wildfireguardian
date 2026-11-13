# PREVIEW ONLY: county labels from Clara's label_sigungu.py (c79d4e4) on the owner's boundary file

This is NOT the file to commit as final. Its `source` line is WRONG: the script hard-codes
"국토교통부 (센서스경계)시군구경계 2025-01-20", but the file actually used is BND_SIGUNGU_PG
(BASE_DATE 2025-06-30, EPSG:5186, SGIS code numbering), supplied by the owner.

Clara will fix the script. The final labels are then re-run by Daniel with the fixed script, so they come straight from the script.

## Run details

- Python 3.12.3, with pyshp 2.3.1, shapely 2.0.6 and pyproj 3.7.0. Clara's 9 tests pass.
- Margin: 50 m.
- Result: 177 of 177 places established at 0, 25, 50 and 100 m. The minimum boundary distance is 189.1 m.
- `labels_PREVIEW_wrong_source_line.json` is a byte copy of the run output (sha256 bac2ce3e…2c09).

The boundary file itself is private and is not committed. Its member sha256 values are recorded inside the JSON.

## Run 2 (final, as delivered): `labels_run2_script_92757b2e.json`

- Script: clara/wkit-jurisdiction 92757b2e (`label_sigungu.py` sha256 534fee03…5d06). All 12 tests pass.
- Run with `--margin 50`, `--archive-sha256 bafb7ef2…5b41` and Clara's `--source` string. The source string's wording is still awaiting Sofia's check and the owner's confirmation.
- Output: sha256 8eaa76b67587b1e9627659676c58b8426197af35b0e9615926f58f91c095a202, 66,584 bytes. It reads EPSG:5186 (KGD2002 / Central Belt 2010) from the file, and its base date is 2025-06-30.
- Counts are identical to run 1: 177 of 177 established at 0, 25, 50 and 100 m. 의성군 48, 안동시 38, 영덕군 82, 청송군 4, 영양군 5.
- Clara commits this file as delivered. The preview above is superseded.

## Run 3 (FINAL, as delivered): `labels_run3_script_92757b2e_final_source.json`

- Same script (92757b2e) and the same command as run 2. Only `--source` changed, to Sofia's revised Korean source line.
- Output: sha256 0896957b8c23f1abafcf0652bd3b57d2c1c6013e050d2fc1edbc8a231c5be52c, 71,746 bytes.
- Every label is identical to run 2 apart from its `source` string, and the counts are identical: 177 of 177 established.
- Clara commits this file as delivered. Runs 1 and 2 are superseded.

## Run 4 (FINAL, as delivered; 13 Nov): `labels_run4_script_92757b2e_vworld_source.json`

- Run on the orchestrator's decision, under the owner's delegation. The source line drops "출처 확인 중".
- Same script (92757b2e, sha 534fee03…), same archive (sha bafb7ef2…), `--margin 50`, same `--archive-sha256`. Only `--source` changed, to Sofia's final string, used verbatim.
- Output: sha256 a907184e1e3de9c10c11d0a2be5dee58ec0ecbc4c47a0fbc9b5af824cacfae36, 63,736 bytes. 177 of 177 established at 50 m.
- Programmatic check (`diff_runs.py` against run 3, output in `DIFF_RUN3_RUN4.txt`): 178 differing leaves, and the only differing key is `source` (177 labels plus the top-level field). "ONLY source differs: True".
- Run 3 is superseded.
