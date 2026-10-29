# Synthetic-truth validation harness (track 1C-3, opt-in overlay)

**Headline.** On the 20 frozen Korean missions scored against 100 withheld trajectories per window, K = 4 trajectory members are false-safe in 11 of 2,000 cases (0.55%, the same as the frozen independent members), all from 2 missions, with no false refusal and no unresolved outcome. Against the reconstructed arrival of the real fires, the frozen members give 0 false-safe cases on 20 missions; the policy that ignores the forecast gives 1. Full results: `research/synthetic-truth/README.md`.

This package imports track 1C-1 (`wfg_members`: members, reduction, acceptance, decision procedure, cheap checker, mission derivation) and track 1C-2 (`wfg_sipp`: the SIPP planner). It never edits a frozen file.

## Contents

| Path | Role |
|---|---|
| `src/wfg_osse/truth.py` | Truth sources (Contract E): `holdout_trajectory`, `reconstructed_arrival` (Zenodo 10.5281/zenodo.21788344 rasters, hash-checked against the export record, cutoff state checked), `device_offline` (schema `wfg.truth.device-offline/1`, orchestrator decision extending Contract E), `external_simulator` (FARSITE ESRI ASCII arrival grids aggregated to routing cells by earliest arrival). `observed_perimeters` is not implemented: NIROPS covers only U.S. fires outside this panel. |
| `src/wfg_osse/score.py` | Contract E records: `true_contact`, `true_peak`, `true_dose`, `arrival_s`, `clairvoyant_arrival_s`, `false_safe`, `false_refusal` (with `refusal_kind`), `regret_s`; exact clairvoyant shortcut through the present-fire lower bound; unknown-mask rules for device_offline. |
| `src/wfg_osse/harness.py` | Decisions with the SIPP planner and the cheap per-member checker; scoring against many truths with cached clairvoyant results; Brier score of an ensemble. |
| `src/wfg_osse/toa.py` | Standard-library GeoTIFF reader for the strip, deflate, float32 time-of-arrival rasters (identical to rasterio on the four Korean rasters used). |
| `tests/test_harness.py` | A route through a cell burning at traversal time is false_safe; a refusal with a clairvoyant route is false_refusal; the clairvoyant optimum without fire equals the travel-only optimum; the harness reproduces the frozen Uljin verdict (3,119 s) with truth = members and zero false-safe; device_offline unknown cells can neither cause nor clear false_safe, refusals are unscorable when only unknown routes exist, schema enforcement; reconstructed-arrival builder; external simulator loader (synthetic grid and the FARSITE flatland output when present). |

## Radiation law switch

`wfg_members.check.member_reports(..., radiation_law="v1" | "v2")`: v1 scores with the frozen packet flux. v2 (track 1A's `wfg_flamefront`) is not integrated in this track and raises `NotImplementedError("law v2 not available")`; the integration step will enable it.

## Tests

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/synthetic-truth/requirements-test.txt
python -m pytest experimental/synthetic-truth/tests
```

## Scope

Truths are model or reconstruction based, not observed evacuations; results are conditional on the road graph, lattice, horizon and construction law; there is no field validation. A `false_safe` flag means "the checked route meets the truth under the same model semantics", not that a real vehicle would have been harmed.
