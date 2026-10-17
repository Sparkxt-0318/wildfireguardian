"""Paths, fixed experiment constants and runtime settings. Environment variables override the paths only."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_SRC = REPO_ROOT / "integration" / "src"
KIT_ROOT = REPO_ROOT / "integration" / "kit"
ABLATION_ROOT = REPO_ROOT / "research" / "routing" / "final-input-ablation"
CONTRACT_PATH = REPO_ROOT / "contracts" / "wfg_api_v1.yaml"
RELEASE_IDENTITY_PATH = REPO_ROOT / "docs" / "RELEASE_IDENTITY.json"

# Import the repository copy of wfg_latest (byte-identical to the reviewed package) ahead of any installed copy.
if str(INTEGRATION_SRC) not in sys.path:
    sys.path.insert(0, str(INTEGRATION_SRC))

# ---- frozen experiment constants (never tuned here; they mirror the recorded requests and the kit) -------------
BUDGET_S = 30.0                    # complete request allowance (wfg_latest.api.route_and_check default)
MEMORY_GUARD_MIB = 3072            # sampled process-family guard (route_and_check default)
SNAP_MAX_M = 300.0                 # API rule: reject coordinates more than 300 m from an allowed node
DEFAULT_PEAK_KW_M2 = 10            # recorded requests and packets.py request template
DEFAULT_DOSE_KJ_M2 = 100           # recorded L/W/D requests and packets.py request template
DEFAULT_DWELL_S = 120              # every recorded final-panel mission
REQUEST_LIMITS = {"wall_s": 30, "max_labels": 1000000, "max_expansions": 1000000, "frontier_width": 16384}
REQUEST_CONSTANTS = {"objective": "earliest_arrival", "exposure_scope": "including_dwell", "solver": "baseline"}
MAX_DISPATCH_ORIGINS = 200
INPUT_SET = "latest_inputs_try02"  # the evaluated final input set (data/routing/latest_inputs_try02)

# API policy name -> final-input ablation arm (research/routing/final-input-ablation/POLICY_TRANSFORMS.json).
# "full" runs the unchanged evaluated path (RDA_CAND, rda_worker_v1_1) exactly as the 80-execution comparison did.
POLICY_ARMS = {"travel_only": "A0", "flame_only": "A1", "flame_peak": "A2", "flame_dose": "A3", "full": "A4"}

REGION_NAMES = {
    "uljin_2022": ("울진", "Uljin"),
    "miryang_2022": ("밀양", "Miryang"),
    "hongseong_2023": ("홍성", "Hongseong"),
    "uiseong_andong_2025": ("의성·안동", "Uiseong-Andong"),
    "yeongdeok_2025": ("영덕", "Yeongdeok"),
}


def _physical_cores() -> int:
    try:
        import psutil
        n = psutil.cpu_count(logical=False)
        if n:
            return int(n)
    except Exception:
        pass
    return os.cpu_count() or 1


@dataclass(frozen=True)
class Settings:
    data_root: Path
    runtime_dir: Path
    workers: int
    python: str
    host: str
    port: int

    @property
    def inputs_root(self) -> Path:
        return self.data_root / INPUT_SET


def load_settings() -> Settings:
    data_root = Path(os.environ.get("WFG_API_DATA_ROOT", REPO_ROOT / "data" / "routing")).resolve()
    runtime = Path(os.environ.get("WFG_API_RUNTIME_DIR", REPO_ROOT / "artifacts" / "api_runtime")).resolve()
    default_workers = max(1, _physical_cores() - 2)
    workers = int(os.environ.get("WFG_API_WORKERS", default_workers))
    return Settings(data_root=data_root, runtime_dir=runtime, workers=max(1, workers),
                    python=os.environ.get("WFG_API_PYTHON", sys.executable),
                    host=os.environ.get("WFG_API_HOST", "127.0.0.1"), port=int(os.environ.get("WFG_API_PORT", "8765")))
