"""Hourly burned-area data, PyTorch loading, and fitted probability models.

Import the needed component from ``pytorch_loader`` or ``probability_model``.
Importing this package alone does not load data or optional dependencies.
"""

__version__ = "0.1.0"

__all__ = [
    "TrainingConfig", "WildfireModel", "load_data", "load_model",
    "WildfireSequenceDataset", "collate_fire_sequences",
]


def __getattr__(name):
    """Expose the public API without importing dependencies on a plain import."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = ".pytorch_loader" if name in ("WildfireSequenceDataset", "collate_fire_sequences") else ".api"
    value = getattr(import_module(module, package=__name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
