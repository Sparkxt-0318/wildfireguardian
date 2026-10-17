"""Provenance carried by every response: package, kit, checkpoint, git commit, input hashes and scenario ids."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import subprocess
import threading
from pathlib import Path

from . import API_VERSION
from .config import KIT_ROOT, RELEASE_IDENTITY_PATH, REPO_ROOT

CLOCK_DEFINITION = ("external_launch_to_completion_wall_s of the kit controller (wfg_controller.run_attempt): "
                    "time.perf_counter() immediately before launching the worker to its reaped completion; includes cold "
                    "graph preparation, search, the mandatory whole-road check and publication (same clock as the experiments)")
APPROXIMATION_NOTE = "approximation, requires expert review"

_lock = threading.Lock()
_sha_cache: dict[tuple, str] = {}


def sha256_file(path) -> str:
    """SHA-256 with a (path, size, mtime_ns, inode) content-check cache; any file change forces a full re-hash."""
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_size, st.st_mtime_ns, st.st_ino)
    with _lock:
        hit = _sha_cache.get(key)
    if hit is not None:
        return hit
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    digest = h.hexdigest()
    with _lock:
        _sha_cache[key] = digest
    return digest


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _git(*args, root: Path = REPO_ROOT) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def git_identity(root: Path = REPO_ROOT) -> tuple[str, bool | None]:
    """(commit, dirty) of ``root``. Git is trusted only when ``root`` is the top of its own work tree: a copy without
    .git that sits inside another checkout would otherwise report that checkout's commit and a clean tree.
    WFG_API_GIT_COMMIT is the fallback for a copy without git metadata; dirty is then unknown (None)."""
    top = _git("rev-parse", "--show-toplevel", root=root)
    own = top is not None and Path(top).resolve() == Path(root).resolve()
    head = _git("rev-parse", "HEAD", root=root) if own else None
    status = _git("status", "--porcelain", "--untracked-files=no", root=root) if own else None
    return head or os.environ.get("WFG_API_GIT_COMMIT") or "unknown", None if status is None else bool(status)


class Identity:
    """Static identities, read once at start-up from the repository (never invented)."""

    def __init__(self):
        rel = json.loads(RELEASE_IDENTITY_PATH.read_text())
        software = rel["software"].split()            # "wfg_latest 1.0.0"
        self.package = software[0]
        self.package_version = software[1]
        self.kit = rel["kit"]
        self.checkpoint = rel["checkpoint_sha256"]
        import wfg_latest
        import wfg_latest.contract as CT
        if wfg_latest.__version__ != self.package_version:
            raise RuntimeError("wfg_latest version %s differs from release identity %s" % (wfg_latest.__version__, self.package_version))
        if CT.CHECKPOINT_SHA256 != self.checkpoint:
            raise RuntimeError("checkpoint identity differs between contract.py and RELEASE_IDENTITY.json")
        self.package_path = str(Path(wfg_latest.__file__).resolve().parent)
        manifest = json.loads((KIT_ROOT / "CANDIDATE_MANIFEST.json").read_text())
        self.kit_candidate_id = manifest.get("candidate_id")
        self.git_commit, self.git_dirty = git_identity()

    def base(self, **extra) -> dict:
        out = {"api_version": API_VERSION, "package": self.package, "package_version": self.package_version,
               "kit": self.kit, "kit_candidate_id": self.kit_candidate_id, "checkpoint": self.checkpoint,
               "git_commit": self.git_commit, "git_dirty": self.git_dirty, "region": None, "input_time": None,
               "graph_id": None, "input_hashes": {}, "scenario_set_id": None, "scenario_ids": [],
               "fire_input_type": None, "policy": None, "evaluated_configuration": None, "approximation": None,
               "clock": None, "host": host_info(), "generated_at": utc_now()}
        out.update(extra)
        return out


def host_info() -> dict:
    return {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
            "cpu_count": os.cpu_count()}
