"""K-SPREAD-2025 benchmark helpers (protocol: ``docs/benchmark/K_SPREAD_2025.md``).

Modules here are imported BY STEM, not as ``benchmark.<module>``: every script in
this repository already puts ``scripts/`` and its own directory on ``sys.path``,
and ``scripts/check_declared_deps.py`` treats a ``.py`` stem anywhere under
``scripts/`` as first-party while a package name that is only a directory is not.
So ``from kspread_truth import ...`` is the importable spelling; this file exists
to make the directory a package for tooling that walks it.
"""
