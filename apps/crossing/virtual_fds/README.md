# virtual_fds: a virtual vehicle unit in the FDS C064 fire (step 8)

**Everything here is simulated.** The sensor readings are computed from FDS 6.11.1 model fields of the CSIRO C064
grass fire (1 m cells) through stated sensor physics. FDS is a model, so agreement with it is not validation. None
of this has been run on hardware. Results and assumptions are in [REPORT.md](REPORT.md).

## What it does

1. **Truth.** Front metrics per frame from `research/kcf-heat/kcf_heat/voxel.py` (loaded by path), taken at
   HRRPUV edges of 5, 20 and 100 kW/m3. It also computes a ground-level (z < 2 m) edge and the spread rate.
2. **Virtual unit** on the centreline at 10, 20 and 30 m ahead of the leading edge. The camera and radar sit at
   2.5 m and face the fire (-x).
   - **TC001 camera** (`lwir.py`): 8-14 um ray-marched radiance from soot and a placeholder hot-gas term, with the
     ground taken as a surface. Apparent temperature is capped at 550 C.
   - **Flux plate** (`plate.py`):
     - FDS radiometers at the same d;
     - the closed form via `crossing.heat`;
     - `voxel_flux`;
     - a copper-plate energy-balance round trip through `crossing.flux.FluxEstimator`.
   - **60 GHz radar paths** (`radar_path.py`): two-way excess phase from the dry-air refractivity of the 1 s
     temperature fields, to a virtual corner reflector 5 m beyond the trailing edge and to ground clutter in
     every bin. The synthetic frames go through `crossing.radar_flame`. Main case: bins, spacing, IF-limited range
     and wavelength read from the unit's default `config/iwr6843aop_vu.cfg` (128 x 0.468 m, echoes to 54 m), with
     clutter per bin scaled by bin length. Labelled side cases: wet refractivity, reflector only, unscaled clutter,
     `iwr6843aop_vu_long_fine.cfg`, `iwr6843aop_vu_short.cfg` (22.5 m) and the earlier virtual 60 m x 0.0488 m.
3. **Laptop pipeline** (`pipeline.py`):
   - `crossing.thermal` flame mask;
   - `crossing.geometry` near edge and flame height, on a zero-grade IMU-plane profile;
   - `crossing.depth` estimators a-e and `combine`, for C064_GRASS.

## Data (outside the repository, read-only, never copied into git)

* `csiro-volume-dt5-120.npz`: whole domain, 5 s frames.
* `c064-roi1-full.npz`: x 30-70 m, 1 s frames.

Both files are in the C064 refinement-study `fire-data` folder. The default path is set in `fields.py`
(`DEFAULT_FIRE_DATA`). Override it with `--fire-data DIR` or the `C064_FIRE_DATA` environment variable. The paths
and sha256 hashes are recorded in `outputs/results.json` and REPORT.md.

In-repo inputs:

* `research/kcf-heat/data/fds_rerun/C064_kcf_radiometers_devc.csv`
* `research/kcf-heat/data/b2_fds_compare.json`

## Reproduce

```sh
cd apps/crossing
MPLCONFIGDIR=$TMPDIR/mpl .venv/bin/python -m virtual_fds.run            # about 3 minutes on this Mac (measured 154 s)
MPLCONFIGDIR=$TMPDIR/mpl .venv/bin/python -m virtual_fds.run --quick    # one decision time, no optics sensitivity, ~1 min
.venv/bin/python -m pytest tests/test_virtual_fds.py                    # synthetic tests; the real-data test skips without the npz
```

The full run writes the following to `virtual_fds/outputs/`:

* `results.json`: everything, plus provenance.
* `results.csv`: long format, one row per quantity.
* `fig_thermal.png`, `fig_flux.png`, `fig_plate.png`, `fig_radar.png`, `fig_depth.png`.
* `thermal_frames.npz`: virtual TC001 frames at t = 60 s, float16 C.

The run is deterministic: every random draw (radar receiver noise, clutter phases, plate thermocouple noise) is
seeded.
