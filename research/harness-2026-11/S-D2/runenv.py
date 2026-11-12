"""Record the library versions of a run, and refuse to run outside the pinned refit environment.

The pins are those of harness/s-d1-next research/harness-2026-11/s-d1/refit/requirements-refit.txt (sha256 1972d6e7…;
Python 3.12) plus torch 2.5.1. Only packages imported by S-D2 numerics are checked here.
"""
from __future__ import annotations

import platform
from importlib import metadata

PINS = {"numpy": "1.26.4", "scipy": "1.13.1", "pandas": "2.2.3", "scikit-learn": "1.5.2"}
PYTHON = "3.12"


def info() -> dict:
    out = {"python": platform.python_version()}
    for name in list(PINS) + ["torch"]:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    out["pinned"] = not mismatches(out)
    return out


def mismatches(i: dict | None = None) -> list[str]:
    i = i or info()
    bad = [f"{k}: want {v}, have {i.get(k)}" for k, v in PINS.items() if i.get(k) != v]
    if not str(i["python"]).startswith(PYTHON + "."):
        bad.append(f"python: want {PYTHON}.x, have {i['python']}")
    return bad


def require_pinned():
    bad = mismatches()
    if bad:
        raise SystemExit("NOT THE PINNED ENVIRONMENT: " + "; ".join(bad))
