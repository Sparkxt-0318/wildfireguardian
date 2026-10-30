# Optical diagnostics and empirical gate

The producing script is `run_physics.py`; root evidence generation calls it from `../run_evidence.py`. Exact values, source locations and source status are in `MODEL_TABLE.csv`, `INCOMPARABLE_DIAGNOSTICS.csv`, `TORNADO.csv`, `SOURCES.json` and `RESULTS.json`. These are deterministic optical model scenarios with the parent evidence seed and host record. The empirical factor-of-three gate is unresolved; no routing-v2 experiment is admitted.

The model table includes finite straight-front calculations using the specified Byram intensity law, the infinite-wall limit with its stated normal, and a centre-aligned ideal-panel model comparison. The latter is model-relative, not a reproduction of measured fire flux. The ground-receiver and centred-receiver geometries are reported separately in the table.

The [Morandini author repository](https://www.research.ed.ac.uk/en/publications/fire-spread-experiment-across-mediterranean-shrub-influence-of-wi/) gives the plot dimensions, but these do not identify instantaneous front width. [Butler's author synthesis](https://ap1.sib.uc.pt/bitstream/10316.2/34306/1/978-989-26-0884-6_147.pdf) describes the quoted vegetation height as shrub height. The retained diagnostic calculations intentionally show sensitivity to several hypothetical widths. They must not be read as validation errors or used to tune an emission constant.

The [primary crown-fire sensor paper](https://www.frames.gov/documents/catalog/spa/butler_cohen_latham_schuette_sopko_shannon_jimenez_bradshaw_2004.pdf) reports in-flame irradiance. It is context for parameter scenarios, not an independently identified uniform-panel exitance. [Frankman's primary abstract](https://research.fs.usda.gov/treesearch/42185) likewise concerns sensor heating under different fuels and fire environments.

The [Cohen primary paper](https://www.frames.gov/documents/catalog/spa/cohen_2004.pdf) distinguishes ideal-panel model values from its experimental measurement table. It documents multiple wall ignitions, with observed flame contact in only one of those experiments. A model-to-model comparison uses its ideal geometry; the experimental ignition findings do not establish a radiation-only vehicle travel threshold.

The requested Pimont numerical bands, original Packham geometry, full Silvani sensor geometry and detailed clinical dose references remain not located or insufficiently identified in this run. The source ledger preserves that status. No row is relabeled as measured validation merely because its ratio is small.

## Figure captions

`fig01_flux_vs_distance`: finite-panel radiation at actual receiver distances for declared intensity and emission scenarios, at ground level, with worst-case per-panel orientation. Each curve is computed by the library. This is an optical model diagnostic without a routing policy or field claim. Both raster and vector figures use the shared scientific styling.

`fig02_parameter_sweep`: snapshot parameter perturbations at fixed receiver distance, including emission, width, receiver orientation, residence labels and sourced wind tilt. Residence does not change a fixed snapshot panel; a time-dependent front calculation would change its trailing geometry. These bars are sensitivity cases, not error bars.

## Scope and limits

No field validation. No measurements were generated or altered. A factor-of-three test is meaningful only after identifying compatible source geometry, sensor geometry, timing and measured quantity. Incomparable hypothetical ratios remain explicitly incomparable. Optical equation checks cannot close unknown source phases, luminous flame geometry, convection, smoke, embers or vehicle shielding. The routed binding/cost figures requested by the track are unavailable because the empirical gate did not pass.
