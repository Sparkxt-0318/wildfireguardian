#!/usr/bin/env python
"""Gate — every third-party module imported at runtime must be DECLARED.

Round 2 shipped a ``requirements.txt`` that declared packages nobody imported.
This is the opposite failure and the one that actually breaks a booth demo: a
package that is imported at runtime, is installed on the machine the work was
done on, and appears in NO declared dependency list. On a fresh clone the
import raises ``ModuleNotFoundError`` and the demo does not start.

The check is MECHANICAL. It parses every tracked ``.py`` file with ``ast`` and
collects:

  * ``import X`` / ``import X.Y`` / ``from X import ...`` at ANY nesting depth,
    so the lazy imports inside ``main()`` and inside test helpers are caught —
    those are exactly the ones a smoke run misses; and
  * ``importlib.import_module("X")`` with a literal string argument.

It then classifies each root module as stdlib (``sys.stdlib_module_names``),
first-party (a package under ``src/``, a sibling module in the same directory,
or a top-level repo directory), or third-party, and requires every third-party
module to map to a distribution named in ``requirements.txt`` or in
``pyproject.toml``'s dependencies (including every optional-dependency group).

⚠ WHAT THIS DOES NOT CATCH. A dependency that is imported only through a string
built at runtime, or pulled in by a plugin mechanism, is invisible to a static
walk. It also cannot tell whether a declared PIN matches what is installed —
``scripts/env_check.py`` is the gate for that. And a module that is a transitive
dependency of something declared will still be reported here if it is imported
DIRECTLY, which is intended: importing a transitive without declaring it is a
real hazard, because the intermediate package is free to drop it.

    python scripts/check_declared_deps.py            # gate: exit 1 on any gap
    python scripts/check_declared_deps.py --report   # full inventory, exit 0
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Directories walked. Anything executed by a demo, a gate, a test or the app.
ROOTS = ("src", "scripts", "tests", "web", "demo", "config", "configs")

#: import name -> PyPI distribution name, where they differ.
IMPORT_TO_DIST = {
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "PIL": "pillow",
    "dateutil": "python-dateutil",
    "cv2": "opencv-python",
    "mpl_toolkits": "matplotlib",
    "pkg_resources": "setuptools",
    "attr": "attrs",
    "OpenSSL": "pyOpenSSL",
    "serial": "pyserial",
    "netCDF4": "netCDF4",
    "h5netcdf": "h5netcdf",
    "h5py": "h5py",
    "affine": "affine",
    "cdsapi": "cdsapi",
}

#: Modules that are part of the project itself, not dependencies.
FIRST_PARTY_EXTRA = {"wildfireguardian", "conftest"}

#: STRING-DISPATCHED BACKENDS — the class of dependency a static import walk
#: CANNOT see, and the one that broke this repo's clean-clone boot.
#: ``xr.open_dataset(path, engine="h5netcdf")`` imports h5netcdf at call time
#: without the name ever appearing in an import statement, so the package is
#: absent from a fresh install and the failure surfaces only when that code path
#: runs — which for this repo is the demo's ERA5 read, not any import.
#: Keyword value -> distributions that must be installed for it to work.
ENGINE_TO_DIST = {
    "h5netcdf": ("h5netcdf", "h5py"),   # h5netcdf drives the HDF5 reader h5py
    "netcdf4": ("netCDF4",),
    "zarr": ("zarr",),
    "cfgrib": ("cfgrib",),
    "pyogrio": ("pyogrio",),
    "fiona": ("fiona",),
    "openpyxl": ("openpyxl",),
    "pyarrow": ("pyarrow",),
    "fastparquet": ("fastparquet",),
    "rasterio": ("rasterio",),
    "scipy": ("scipy",),
    "pydap": ("pydap",),
}

#: Keyword names whose literal string value selects a backend package.
DISPATCH_KEYWORDS = ("engine", "driver")


def _declared() -> dict[str, set[str]]:
    """Distribution names declared in each file, lower-cased."""
    out: dict[str, set[str]] = {"requirements.txt": set(), "pyproject.toml": set()}

    req = REPO / "requirements.txt"
    if req.exists():
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name = re.split(r"[<>=!~\[]", line, 1)[0].strip()
            if name:
                out["requirements.txt"].add(name.lower())

    pp = REPO / "pyproject.toml"
    if pp.exists():
        text = pp.read_text(encoding="utf-8")
        # Every quoted requirement inside any dependencies list. Deliberately
        # crude and deliberately GENEROUS: over-collecting here can only make
        # the gate quieter, and the gate's own report prints what it found.
        for block in re.findall(r"dependencies\s*=\s*\[(.*?)\]", text, re.S) + \
                     re.findall(r"^\s*\w[\w.-]*\s*=\s*\[(.*?)\]", text, re.S | re.M):
            for q in re.findall(r"[\"']([^\"']+)[\"']", block):
                name = re.split(r"[<>=!~\[;]", q, 1)[0].strip()
                if name and not name.startswith(("http", ".", "/")):
                    out["pyproject.toml"].add(name.lower())
    return out


def _first_party() -> set[str]:
    names = set(FIRST_PARTY_EXTRA)
    src = REPO / "src"
    if src.is_dir():
        for p in src.iterdir():
            if p.is_dir() and (p / "__init__.py").exists():
                names.add(p.name)
            elif p.suffix == ".py":
                names.add(p.stem)
    # sibling modules importable because a script inserts its own dir on path
    for root in ROOTS:
        d = REPO / root
        if d.is_dir():
            for p in d.rglob("*.py"):
                names.add(p.stem)
            names.add(d.name)
    return names


def _imports_in(path: Path) -> set[str]:
    """Every root module name this file imports, at any nesting depth."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(a.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:       # skip relative imports
                found.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name) else None)
            if name == "import_module" and node.args:
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                    found.add(a0.value.split(".", 1)[0])
    return found


def _engines_in(path: Path) -> set[str]:
    """String-dispatched backends: ``engine="h5netcdf"`` and friends."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg in DISPATCH_KEYWORDS and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                v = kw.value.value.lower()
                if v in ENGINE_TO_DIST:
                    found.add(v)
    return found


def inventory() -> dict:
    first = _first_party()
    std = set(sys.stdlib_module_names)
    declared = _declared()
    all_declared = declared["requirements.txt"] | declared["pyproject.toml"]

    where: dict[str, set[str]] = {}
    engines: dict[str, set[str]] = {}
    n_files = 0
    for root in ROOTS:
        d = REPO / root
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            n_files += 1
            rel = str(p.relative_to(REPO))
            for mod in _imports_in(p):
                where.setdefault(mod, set()).add(rel)
            for eng in _engines_in(p):
                engines.setdefault(eng, set()).add(rel)

    third: dict[str, list[str]] = {}
    for mod, files in where.items():
        if mod in std or mod in first or mod.startswith("_"):
            continue
        third[mod] = sorted(files)

    undeclared = {}
    for mod, files in sorted(third.items()):
        dist = IMPORT_TO_DIST.get(mod, mod)
        if dist.lower() not in all_declared:
            undeclared[mod] = {"distribution": dist, "imported_by": files,
                               "how": "import statement"}
    for eng, files in sorted(engines.items()):
        for dist in ENGINE_TO_DIST[eng]:
            if dist.lower() not in all_declared:
                undeclared.setdefault(f'engine="{eng}" -> {dist}', {
                    "distribution": dist, "imported_by": sorted(files),
                    "how": "string-dispatched backend (no import statement)"})

    return {
        "n_python_files_scanned": n_files,
        "n_third_party_modules": len(third),
        "declared": {k: sorted(v) for k, v in declared.items()},
        "third_party_imports": {k: v for k, v in sorted(third.items())},
        "string_dispatched_backends": {
            k: {"requires": list(ENGINE_TO_DIST[k]), "used_by": sorted(v)}
            for k, v in sorted(engines.items())},
        "undeclared": undeclared,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true",
                    help="print the full inventory and exit 0")
    ap.add_argument("--json", type=Path, default=None,
                    help="also write the inventory to this path")
    a = ap.parse_args()

    inv = inventory()
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")

    if a.report:
        print(f"scanned {inv['n_python_files_scanned']} python files under "
              f"{', '.join(ROOTS)}/")
        print(f"third-party root modules imported: {inv['n_third_party_modules']}")
        for mod, files in inv["third_party_imports"].items():
            mark = "  UNDECLARED" if mod in inv["undeclared"] else ""
            print(f"  {mod:<20} {len(files):>3} file(s){mark}")
        return 0

    if inv["undeclared"]:
        print("UNDECLARED RUNTIME IMPORTS — a fresh clone will fail to start:\n")
        for mod, d in inv["undeclared"].items():
            print(f"  {mod}  (distribution: {d['distribution']})")
            for f in d["imported_by"][:6]:
                print(f"      {f}")
            if len(d["imported_by"]) > 6:
                print(f"      ... and {len(d['imported_by']) - 6} more")
        print("\nAdd each to requirements.txt with the version that is installed "
              "now (pip show <dist>), and to pyproject.toml. Upgrade nothing.")
        return 1

    print(f"OK — {inv['n_third_party_modules']} third-party modules imported "
          f"across {inv['n_python_files_scanned']} files; all declared.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
