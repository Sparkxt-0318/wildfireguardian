"""Process-isolated access to full, separately extracted research deliveries.

No sys.path changes in the calling application; original backends are unchanged.
Process startup and JSON/file work add overhead. No cross-call cache is promised.
"""
from pathlib import Path
import json
import math
import subprocess
import sys
import tempfile
import time


class BackendError(RuntimeError):
    """Launch/input failure, distinct from a valid unresolved routing result."""
    def __init__(self, message, *, returncode=None, stdout="", stderr=""):
        super().__init__(message)
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class BackendTimeout(BackendError):
    """Outer process deadline exceeded; does not prove route infeasibility."""


def _timeout(value):
    if value is not None and (not math.isfinite(float(value)) or float(value) <= 0):
        raise ValueError("process_timeout_s must be positive and finite, or None")
    return None if value is None else float(value)


def _run(command, *, cwd, process_timeout_s):
    begin = time.perf_counter()
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                   timeout=_timeout(process_timeout_s), check=False)
    except subprocess.TimeoutExpired as exc:
        raise BackendTimeout("Backend process timed out; outcome is unresolved") from exc
    except OSError as exc:
        raise BackendError("Cannot launch backend interpreter") from exc
    if completed.returncode:
        raise BackendError("Backend failed; inspect stdout/stderr", returncode=completed.returncode,
                           stdout=completed.stdout, stderr=completed.stderr)
    return completed, time.perf_counter() - begin


class ReleaseRuntime:
    """A full extracted release, not the GitHub routing-review source subset.

    The caller must obtain the trusted archive and verify its checksum/manifest.
    Methods preserve backend status fields. Use separate instances for different
    releases. Paths resolve absolutely, independent of the current directory.
    """
    def __init__(self, release_directory, *, python_executable=None):
        self.directory = Path(release_directory).expanduser().resolve()
        self.python_executable = str(python_executable or sys.executable)
        if not (self.directory / "candidate/hourly.py").is_file():
            raise FileNotFoundError("Expected a full extracted release with candidate/hourly.py")

    def run_hourly(self, output_directory, *, mode="strict", native=False, repeats=1,
                   graph=None, snapshot=None, metadata=None, request=None, config=None,
                   input_snapshot=None, checkpoint=None, origin=None,
                   save_hazard=False, process_timeout_s=None):
        """Return the original integration REPORT plus measured outer process time.

        Strict is the default. Research must be explicitly requested. Native=True
        reruns original inference; False uses saved forecast outputs. Supply the
        constructor configuration as a JSON file. Refuse existing output folders.
        """
        if mode not in {"strict", "research"}:
            raise ValueError("mode must be strict or research")
        if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
            raise ValueError("repeats must be a positive integer")
        _timeout(process_timeout_s)
        if native and (snapshot is not None or metadata is not None):
            raise ValueError("native inference writes its own snapshot/metadata; use input_snapshot")
        if not native and (input_snapshot is not None or checkpoint is not None):
            raise ValueError("input_snapshot/checkpoint require native=True")
        output = Path(output_directory).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(exist_ok=False)
        command = [self.python_executable, "-B", str(self.directory / "candidate/hourly.py"),
                   "native-run" if native else "run", "--mode", mode,
                   "--repeats", str(repeats), "--output-dir", str(output)]
        for flag, value in [("graph", graph), ("snapshot", snapshot), ("metadata", metadata),
                            ("request", request), ("config", config), ("input", input_snapshot),
                            ("checkpoint", checkpoint)]:
            if value is not None:
                command += ["--" + flag, str(Path(value).expanduser().resolve())]
        if origin is not None:
            command += ["--origin", str(origin)]
        if save_hazard:
            command += ["--save-hazard"]
        completed, elapsed = _run(command, cwd=self.directory, process_timeout_s=process_timeout_s)
        report_file = output / "REPORT.json"
        if not report_file.is_file():
            raise BackendError("Backend returned no REPORT.json", stdout=completed.stdout, stderr=completed.stderr)
        report = json.loads(report_file.read_text())
        report["api_process_wall_s"] = elapsed
        return report

    def check_fixed_route(self, case_directory, graph, request, legs, destination, *,
                          wall_s=30, settings=None, expected_graph_revision=None,
                          expected_graph_sha256=None, process_timeout_s=None):
        """Use optional HybridChecker on a complete route under its declared law.

        Requires the hybrid checker release and a constructed case directory with
        REPORT.json/constructed_arrays.npz. Each call is a cold owned checker epoch.
        This does not search for a route, certify global optimality, or assure safety.
        Outer process time is supplemental; the backend's existing cap is retained.
        """
        if not (self.directory / "candidate/hybrid_checker.py").is_file():
            raise FileNotFoundError("Fixed-route API requires the hybrid checker release")
        if not math.isfinite(float(wall_s)) or float(wall_s) < 0:
            raise ValueError("wall_s must be nonnegative and finite")
        _timeout(process_timeout_s)
        payload = {"case_directory": str(Path(case_directory).expanduser().resolve()),
                   "graph": graph, "request": request, "legs": legs, "destination": destination,
                   "wall_s": wall_s, "settings": settings,
                   "expected_graph_revision": expected_graph_revision,
                   "expected_graph_sha256": expected_graph_sha256}
        # NaN, object arrays and custom Python objects cannot cross this JSON API.
        encoded = json.dumps(payload, allow_nan=False)
        with tempfile.TemporaryDirectory(prefix="wfg-check-") as temp:
            incoming, outgoing = Path(temp)/"input.json", Path(temp)/"output.json"
            incoming.write_text(encoded)
            command = [self.python_executable, "-B", str(Path(__file__).with_name("_checker_worker.py")),
                       str(self.directory), str(incoming), str(outgoing)]
            completed, elapsed = _run(command, cwd=self.directory, process_timeout_s=process_timeout_s)
            if not outgoing.is_file():
                raise BackendError("Checker returned no JSON", stdout=completed.stdout, stderr=completed.stderr)
            result = json.loads(outgoing.read_text())
        result["api_process_wall_s"] = elapsed
        return result
