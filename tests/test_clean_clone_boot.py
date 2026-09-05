"""Session 18 — the clean-clone boot must not regress.

Two failure modes are pinned here, both found by actually doing it rather than
by reasoning about it.

FAILURE 1 — AN UNDECLARED RUNTIME IMPORT.
``h5netcdf`` and ``h5py`` were reached only through
``xr.open_dataset(..., engine="h5netcdf")``, so no import statement mentioned
them and no dependency file declared them. On a fresh clone the call raised
``ModuleNotFoundError: No module named 'h5netcdf'``. ``affine`` and
``fonttools`` were imported directly and arrived only as transitives of
rasterio and matplotlib — a transitive is not a declaration, because the
intermediate package may drop it in any release.

FAILURE 2 — A STRICT PRELOAD TOOK THE WHOLE SERVICE DOWN.
``data/raw/`` is 1.3 GB and is deliberately not in the repository, so on a
fresh clone every region's DEM is missing. ``ResourceCache.preload`` raised
inside the FastAPI lifespan and ``uvicorn`` never started — meaning the
pre-built console and ``/field``, which need no data at all, could not be
served either. The service now starts and reports which regions are unavailable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


# ------------------------------------------------------------------ FAILURE 1

def test_no_undeclared_runtime_imports():
    """The gate that fails when a new undeclared runtime import appears.

    Run as a subprocess so this test asserts on the GATE's exit code — the same
    thing ``make check-declared-deps`` and a CI run would see — rather than on a
    function this test could accidentally call differently.
    """
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_declared_deps.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, (
        "an import is reachable at runtime but declared in neither "
        f"requirements.txt nor pyproject.toml:\n{r.stdout}{r.stderr}")


def test_the_gate_sees_a_plain_import():
    import check_declared_deps as cdd

    inv = cdd.inventory()
    # numpy is imported all over the tree; if the walker stopped finding it,
    # the gate would be silently vacuous and every real gap would pass.
    assert "numpy" in inv["third_party_imports"]
    assert len(inv["third_party_imports"]["numpy"]) > 50


def test_the_gate_sees_a_string_dispatched_backend():
    """The check that would have caught h5netcdf, and that an AST import walk
    alone cannot: the package name appears in no import statement."""
    import check_declared_deps as cdd

    inv = cdd.inventory()
    assert "h5netcdf" in inv["string_dispatched_backends"], (
        "the engine= scan stopped finding h5netcdf; the class of dependency "
        "that broke the clean-clone boot would now pass unnoticed")
    used_by = inv["string_dispatched_backends"]["h5netcdf"]["used_by"]
    assert any("spread_v2/data.py" in u for u in used_by)
    # and it must map onto BOTH distributions, since h5netcdf drives h5py
    assert set(cdd.ENGINE_TO_DIST["h5netcdf"]) == {"h5netcdf", "h5py"}


def test_h5netcdf_and_h5py_are_declared():
    """Pin the specific packages the clean-clone boot failed on."""
    import check_declared_deps as cdd

    declared = set()
    for names in cdd._declared().values():
        declared |= names
    for pkg in ("h5netcdf", "h5py", "affine", "fonttools"):
        assert pkg.lower() in declared, f"{pkg} is undeclared again"


# ------------------------------------------------------------------ FAILURE 2

def test_preload_is_strict_by_default():
    """A half-successful preload must stay an error for every existing caller.

    ⚠ The type is ``ParameterError``, not ``ResourceError``. A missing region
    fails at ``check_npz`` — the hazard field is looked for before the DEM — so
    the first draft of the non-strict handler caught only ``ResourceError`` and
    did not catch this at all. That is why ``_MISSING_INPUT_ERRORS`` enumerates
    the family rather than naming one class.
    """
    from wildfireguardian.service.params import ParameterError, RoutingParams
    from wildfireguardian.service.resources import ResourceCache

    cache = ResourceCache(capacity=2)
    with pytest.raises(ParameterError):
        cache.preload(["__no_such_region__"], RoutingParams.from_config())


def test_preload_non_strict_records_the_failure_and_continues():
    from wildfireguardian.service.resources import ResourceCache
    from wildfireguardian.service.params import RoutingParams

    cache = ResourceCache(capacity=2)
    out = cache.preload(["__no_such_region__"], RoutingParams.from_config(),
                        strict=False)
    assert len(out) == 1
    assert out[0]["loaded"] is False
    assert out[0]["region"] == "__no_such_region__"
    assert "error" in out[0]
    assert cache.resident_regions() == set()


def test_the_app_starts_and_serves_field_when_no_region_can_preload():
    """THE BOOTH CASE: a laptop with the repo and no 1.3 GB data bundle.

    Before Session 18 this raised inside the lifespan and the service did not
    start, so ``/field`` — a fully pre-built page that needs no region data —
    was unreachable for a reason that had nothing to do with it.
    """
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from wildfireguardian.api.app import create_app

    app = create_app(preload=("__no_such_region__",))
    with fastapi_testclient.TestClient(app) as c:
        h = c.get("/api/health")
        assert h.status_code == 200
        body = h.json()
        assert body["preloaded_regions"] == []
        assert "__no_such_region__" in body["preload_failed_regions"]

        page = REPO / "web" / "field_view.html"
        if page.exists():
            r = c.get("/field")
            assert r.status_code == 200
            assert len(r.content) > 1000
