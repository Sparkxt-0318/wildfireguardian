# kcf-robust: does the margin field improve an outcome?

**Model output on synthetic or reconstructed inputs. Not what happened to people.**

Rules: [PROTOCOL.md](PROTOCOL.md) (committed before any result; amendments dated in its section 9).
Results: [RESULTS.md](RESULTS.md).

| file | what |
|---|---|
| `make_r50.py`, `r50.json` | central reach curve R50 (kcf-margin's own calibration at alpha 0.5) |
| `lib.py` | lattice, known-area distance, reach curves, closure rasters, dilation, shift, the product run |
| `reachpass.py` | compiled latest-departure pass over many closure levels (exact for permanent closures) |
| `twin.py` | twin experiment: rasters, product runs, curves, equal-caution calibration, rules b and c |
| `replay.py` | 25 March 2025: Step 1 tolerance on the product raster, the five rules, reconstructed truth |
| `score.py` | failed evacuations, missed and false cut-offs, lead time given up, cluster bootstrap |
| `official.py` | order and timing of each rule's cut-offs against the official alert and closure times |
| `fragility_table.py` | the 174-place fragility table with the product's `--fragility` code, checked against the research pass |
| `tests/` | brute force on random instances, real-instance checks against the unchanged engine, margin field check |
| `out/` | every number in RESULTS.md |

## Reproduce

From the repository root, Python 3.11+, numpy, scipy, pandas, numba (optional, for speed), and for `official.py`
pyarrow, shapely, pyproj, tifffile. Road graphs: `python3 tools/fetch_routing_inputs.py` then
`python3 product/wfg-roadlayer/roadlayer.py setup --data-routing data/routing`.

```bash
python3 -m unittest research/kcf-robust/tests/test_reachpass.py
```

```bash
python3 research/kcf-robust/tests/check_real.py && python3 research/kcf-robust/tests/check_real.py wide
```

```bash
python3 research/kcf-validate/twin/run_twin.py make WORK
```

```bash
cd research/kcf-robust && python3 twin.py phase1 WORK out && python3 twin.py calibrate WORK out && python3 twin.py phase2 WORK out && python3 score.py twin out
```

```bash
cd research/kcf-robust && python3 replay.py phase1 out && python3 replay.py calibrate out && python3 replay.py phase2 out && python3 score.py replay out
```

```bash
cd research/kcf-robust && python3 official.py out OVERTURE_DIR && python3 fragility_table.py out
```

`OVERTURE_DIR` holds `divisions.parquet` (type `division_area`) and `segments.parquet`, fetched with
`research/kcf-roadcut/overture/fetch_overture_theme.py`.
