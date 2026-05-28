"""Smoke tests — verify the package and its subpackages import cleanly.

These tests intentionally do nothing scientific. They exist so that a
fresh clone with `pip install -e .` and `pytest` immediately reports the
state of every module's import surface, before any algorithmic test runs.
"""

from __future__ import annotations

import importlib

import pytest

PACKAGE_TREE: list[str] = [
    "wildfireguardian",
    "wildfireguardian.fire_detection",
    "wildfireguardian.spread_model",
    "wildfireguardian.spread_model.rothermel",
    "wildfireguardian.spread_model.cellular_automaton",
    "wildfireguardian.lfmc_model",
    "wildfireguardian.lfmc_model.retrieval",
    "wildfireguardian.smoke_dispersion",
    "wildfireguardian.smoke_dispersion.gaussian_plume",
    "wildfireguardian.routing",
    "wildfireguardian.delivery",
    "wildfireguardian.validation",
    "wildfireguardian.validation.metrics",
    "wildfireguardian.validation.harness",
    "wildfireguardian.validation.baselines",
    "wildfireguardian.validation.robustness",
    "wildfireguardian.data_io",
    "wildfireguardian.data_io.raster",
    "wildfireguardian.data_io.weather",
    "wildfireguardian.utils",
    "wildfireguardian.utils.units",
    "wildfireguardian.utils.regions",
    "wildfireguardian.utils.vulnerability",
]


@pytest.mark.parametrize("module_name", PACKAGE_TREE)
def test_module_imports(module_name: str) -> None:
    """Every documented module is importable from a clean process."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_version_is_pep440_ish() -> None:
    """Package exposes a `__version__` string."""
    import wildfireguardian

    v = wildfireguardian.__version__
    assert isinstance(v, str) and len(v) > 0
    # Loose check: must start with a digit.
    assert v[0].isdigit()


def test_unit_constants_are_self_consistent() -> None:
    """Cross-check unit conversions in :mod:`wildfireguardian.utils.units`."""
    from wildfireguardian.utils import units as u

    # M_PER_FT and FT_PER_M are reciprocals.
    assert abs(u.M_PER_FT * u.FT_PER_M - 1.0) < 1e-12
    assert abs(u.FTMIN_PER_MS * u.MS_PER_FTMIN - 1.0) < 1e-12

    # 1 m/s should be 60 * 3.281 = 196.85 ft/min.
    assert abs(u.FTMIN_PER_MS - 60.0 * u.FT_PER_M) < 1e-6
