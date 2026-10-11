"""Hourly wildfire prediction and expected incident radiant heat.

Public objects load on first access; importing wildfire alone loads no data,
machine learning dependencies, or command workflows.
"""
from importlib import import_module

__version__ = "0.1.0"

_EXPORTS = {
    **dict.fromkeys(("TrainingConfig", "WildfireModel", "load_data", "load_model"), "api"),
    **dict.fromkeys(("WildfireSequenceDataset", "collate_fire_sequences"), "data"),
    **dict.fromkeys(("BurnProbability", "EnvironmentConditionedConvolution", "new_burn_probability",
                    "LearnedNonnegativeKernel", "build_kernel_model", "kernel_model_configuration",
                    "initialize_kernel_rate", "KERNEL_ARCHITECTURES", "MixedNonnegativeKernel",
                    "build_mixed_kernel_model", "mixed_model_configuration", "initialize_mixed_kernel_rate",
                    "NeuralMixedNonnegativeKernel", "build_neural_mixed_kernel_model",
                    "neural_mixed_model_configuration", "initialize_neural_mixed_kernel_rate",
                    "PatchRandomForest"), "models"),
    **dict.fromkeys(("TrainedBurnModel", "load_trained_model", "load_mixed_trained_model",
                    "load_neural_mixed_trained_model"), "inference"),
    **dict.fromkeys(("AffineGrid", "CombustionParameters", "ExpectedHeatFluxModel", "HeatFluxResult",
                    "integrate_heat_flux", "EcologicalFuelMaps", "FCCS_TONS_PER_ACRE_TO_KG_M2",
                    "BurningOccupancy", "ignition_to_active_probability", "initial_active_occupancy",
                    "FlameResidenceTime", "ActiveFlameMap", "ActiveFlameForecast", "FlamePositions",
                    "active_flames_from_arrival", "forecast_active_flames", "IntegratedHeatPrediction",
                    "WildfireHeatModel"), "heat"),
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
