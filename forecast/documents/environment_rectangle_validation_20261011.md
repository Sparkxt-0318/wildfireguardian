# Environmental rectangle verification — 2026-10-11

The environmental acquisition and default loader already retain the complete
original rectangle for each event. No environmental crop to the finite arrival
footprint was found, so no acquisition or prediction calculation was changed.
The examples now explicitly request `patch_size=None`, and the probability
demonstration checks the loaded rectangle and environmental coverage.

## Original-grid verification

All 44 catalog events retain their original arrival-raster height, width,
affine transform and coordinate reference system. All 2,743 regional and
quality-flag raster headers checked match those event grids; there are no
alignment mismatches. These header checks verify the spatial rectangle, rather
than asserting that every source has a valid value at every cell or time.

Acquisition uses rectangular source subsets with margins and reprojects into
the complete reference rectangle. Terrain temporarily adds a computational
halo and removes only that halo when writing the full reference grid. Neither
acquisition nor loading applies the arrival availability mask to environmental
features. Selecting known target neighborhoods for training rows does not
alter the stored environmental rasters.

## FishCreek input and prediction coverage

At the demonstration cutoff `2024-08-23T00:00:00Z`, event
`WY-BTF-002416_FishCreek` retains its original 103-row by 73-column grid,
with 375 m cells and EPSG:5070. Its physical support contains all 7,519 cells.
The loaded feature shape is `[1, 19, 103, 73]`.

All 19 channels required by the default checkpoint are valid at all 7,519
cells. Reconstructed arrival labels are valid at 2,642 cells. The other
4,877 cells still have complete required environmental inputs. Missing arrival
labels therefore do not remove or mask the environmental rectangle.

The following separate coverage probe uses one trajectory because its purpose
is to check deterministic validity masks, rather than probability accuracy.
It initializes unavailable cutoff burned states as unburned inside physical
support. The number of trajectories does not determine the coverage envelope.

| Horizon | Environmental cells available | Predictions available, `boundary="unknown"` | Predictions available, `boundary="zero"` |
| --- | ---: | ---: | ---: |
| 1 hour | 7,519 | 6,831 | 7,519 |
| 3 hours | 7,519 | 5,551 | 7,519 |
| 6 hours | 7,519 | 3,871 | 7,519 |

For this complete-input example, the unknown-boundary validity mask exactly
matches removal of an edge band of width `2 * hours` from the available output
coverage. The default checkpoint has a 5-by-5 neighborhood, with radius two.
Thus its valid rectangles have respectively 99 by 69, 91 by 61 and 79 by 49
cells. The input and output tensors keep the full 103-by-73 spatial shape at
every horizon; only output validity changes.

These edge bands are required-neighborhood coverage under
`boundary="unknown"`. They are not cropped or missing environmental pixels
inside the original rectangle. `boundary="zero"` explicitly assumes zero
outside-grid contributions and zero environmental values in the model input
space; it does not retrieve exterior observations. The default boundary policy
was retained.

Other event or channel selections can contain genuine source NoData,
source-quality failures, unknown categories or undefined terrain directions.
Those environmental values remain unavailable under the user's confirmed
policy. Spatial or temporal padding remains excluded as well.

## Evidence

The machine-readable grid audit and coverage probe are saved in
`environment_rectangle_validation_20261011.json`. The updated demonstration
has explicit full-rectangle diagnostics and is executed separately under
`demonstration/environment_rectangle/20261011/`; earlier recursive validation
artifacts are preserved with their original recorded sources.

The updated notebook passed all six code cells in 24.35 seconds. Its diagnostics
verify the original and loaded shapes, full physical support, all-channel
availability, and availability outside the arrival mask. Its source remained
unchanged by execution and retains empty saved code outputs. The executed copy
and validation record are in the new artifact directory above.

The final full regression run passed **1,933 tests**, with zero failures,
errors or skips, in 85.51 seconds. It includes four new rectangle regression
cases that check exact retained values and coordinates outside arrival coverage,
genuine environmental NoData, outside-grid prediction dependencies, explicitly
requested patches, and padding. The log and JUnit record are
`environment_rectangle_tests_20261011.log` and
`environment_rectangle_tests_20261011.xml`. Recorded runtime and changed-source
hashes still matched after the run.
