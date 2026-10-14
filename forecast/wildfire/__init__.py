"""Hourly wildfire prediction and expected incident radiant heat.

Public objects load on first access; importing wildfire alone loads no data,
machine learning dependencies, or command workflows.
"""
from importlib import import_module

__version__ = "0.1.0"

_EXPORTS = {
    **dict.fromkeys(("TrainingConfig", "WildfireModel", "load_model", "train_model"), "api"),
    "Prediction": "prediction",
    "CumulativePrediction": "cumulative",
    "evaluate_cumulative": "cumulative_evaluation",
    "prepare_training_data": "prepare",
    **dict.fromkeys(("available_events", "available_cutoffs"), "catalog"),
    **dict.fromkeys(("plot_matrix", "plot_comparison"), "plotting"),
    **dict.fromkeys(("load_data", "select_time", "WildfireSequenceDataset", "collate_fire_sequences"), "data"),
    **dict.fromkeys(("BurnProbability", "EnvironmentConditionedConvolution", "new_burn_probability",
                    "LearnedNonnegativeKernel", "build_kernel_model", "kernel_model_configuration",
                    "initialize_kernel_rate", "KERNEL_ARCHITECTURES", "MixedNonnegativeKernel",
                    "build_mixed_kernel_model", "mixed_model_configuration", "initialize_mixed_kernel_rate",
                    "NeuralMixedNonnegativeKernel", "build_neural_mixed_kernel_model",
                    "neural_mixed_model_configuration", "initialize_neural_mixed_kernel_rate",
                    "PatchRandomForest", "BayesianBurnModel", "bayesian_model_weights"), "models"),
    "fit_bayesian_model": "train",
    **dict.fromkeys(("TrainedBurnModel", "load_trained_model", "load_mixed_trained_model",
                    "load_neural_mixed_trained_model", "load_bayesian_trained_model"), "inference"),
    **dict.fromkeys(("AffineGrid", "CombustionParameters", "ExpectedHeatFluxModel", "HeatFluxResult",
                    "integrate_heat_flux", "EcologicalFuelMaps", "FCCS_TONS_PER_ACRE_TO_KG_M2",
                    "BurningOccupancy", "ignition_to_active_probability", "initial_active_occupancy",
                    "BurningState", "burning_state_from_arrival",
                    "FlameResidenceTime", "ActiveFlameMap", "ActiveFlameForecast", "FlamePositions",
                    "active_flames_from_arrival", "forecast_active_flames", "IntegratedHeatPrediction",
                    "WildfireHeatModel"), "heat"),
    **dict.fromkeys(("RadiativeFractionEstimate", "HomogeneousAtmosphere", "AttenuatedCellTransfer",
                    "attenuated_cell_transfer"), "heat_transfer"),
    **dict.fromkeys(("heat_content_from_fbfm40", "BTU_IT_PER_LB_TO_J_PER_KG"), "heat_parameters"),
    "CellBurningDuration": "heat_duration",
    "DEFAULT_FRONT_SPREAD_RATE_M_S": "heat_duration",
    **dict.fromkeys(("constant_hazard_occupancy", "infer_ignition_rate",
                    "constant_hazard_unknown_occupancy_upper"), "heat_timing"),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("." + _EXPORTS[name], package=__name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
