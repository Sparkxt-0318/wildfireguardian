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
