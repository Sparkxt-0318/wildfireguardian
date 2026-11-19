"""Paths into the rest of the repository, and loaders for repo code reused without copying.

- ``vu()`` makes ``hardware/vehicle-unit`` importable so the laptop shares ``wfgvu.protocol`` (and, for tests and
  replay, ``wfgvu.replay`` / ``wfgvu.synth``) with the sensor head instead of keeping a second copy.
- ``kcf_law()`` loads ``research/kcf-heat/kcf_heat/law.py`` by file path. That module is stdlib-only; importing the
  ``kcf_heat`` package instead would be the same code, but its sibling ``exposure.py`` pulls in the repo root.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

APP = Path(__file__).resolve().parents[1]                 # apps/crossing
REPO = APP.parents[1]                                      # repository root
VU_ROOT = REPO / "hardware" / "vehicle-unit"
KCF_HEAT = REPO / "research" / "kcf-heat"
KCF_LAW = KCF_HEAT / "kcf_heat" / "law.py"
B2_FDS_COMPARE = KCF_HEAT / "data" / "b2_fds_compare.json"
C064_DEVC = KCF_HEAT / "data" / "fds_rerun" / "C064_kcf_radiometers_devc.csv"


def vu() -> Path:
    if str(VU_ROOT) not in sys.path:
        sys.path.insert(0, str(VU_ROOT))
    return VU_ROOT


@lru_cache(maxsize=1)
def kcf_law():
    spec = importlib.util.spec_from_file_location("kcf_heat_law_by_path", KCF_LAW)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod                           # dataclasses look the module up while decorating
    spec.loader.exec_module(mod)
    return mod
