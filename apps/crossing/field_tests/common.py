"""Shared helpers for field tests A-F: paths, the risk-assessment gate, run metadata, CSV / Markdown / PNG output
with SIMULATED watermarking, and small statistics helpers.

Honesty rules enforced here (used by every analysis script):
- Any output built from simulated input carries "SIMULATED" in the PNG (diagonal watermark + title), in every CSV
  row (`simulated` column) and at the top of the Markdown snippet.
- Every Markdown snippet ends with DISCLAIMER: results as measured, limits are placeholders, no readiness claim.
- Flux-disc stop (user, 2026-11-17: the copper disc sits on printed PETG tabs): every record script stops a run and
  warns at a disc (tc_plate) temperature >= DISC_MAX_C (70 C, crossing.yaml `flux.disc_max_c`, USER-SET, not a
  placeholder), and also when the disc temperature is missing / faulted for > 2 s while the run needs it
  (recordkit.DiscGuard). The run directory records `stop_reason` (DISC_OVER_70C / DISC_TEMP_UNKNOWN) in trial.json
  and a `disc_stop` mark; every analysis reports such runs as measured ("STOPPED: disc 70 C"), never drops them.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

PKG = Path(__file__).resolve().parent                    # apps/crossing/field_tests
APP = PKG.parent                                         # apps/crossing
REPO = APP.parents[1]
VU_ROOT = REPO / "hardware" / "vehicle-unit"
RECORDS = APP / "records" / "field_tests"                # git-ignored runtime data
EXAMPLES = PKG / "example_outputs"

for _p in (APP, VU_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DEFAULT_PI_URL = "ws://10.42.0.1:8770/stream"
DEFAULT_APP_URL = "ws://127.0.0.1:8781/ws"

DISCLAIMER = ("Results are reported as measured, including failures. Verdicts are advisory for trained crews and "
              "every limit is a placeholder for a fire service to set. These results do not show operational "
              "readiness.")
SIM_BANNER = ("SIMULATED DATA: these numbers come from field_tests/simulate.py, not from hardware. They only "
              "exercise the analysis; they are not a measurement.")

RISK_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic")
_RISK_MAGIC = (b"%PDF", b"\x89PNG", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*")


# ---------------------------------------------------------------------------------------------- flux-disc limit
DISC_MAX_C_DEFAULT = 70.0          # user-set (PETG tabs under the copper disc), not a placeholder
STOP_DISC_OVER = "DISC_OVER_70C"
STOP_DISC_UNKNOWN = "DISC_TEMP_UNKNOWN"
STOP_LABELS = {STOP_DISC_OVER: "STOPPED: disc 70 C", STOP_DISC_UNKNOWN: "STOPPED: disc temperature unknown"}


def disc_max_c(config_path=None) -> float:
    """The flux-disc limit from crossing.yaml (`flux.disc_max_c`, validated 40..70 by crossing.config); 70 C (the
    user's value) when the config cannot be loaded (a warning is printed). Never above 70 C (cap_disc_max_c)."""
    try:
        from crossing.config import load_config
        return cap_disc_max_c(load_config(config_path).flux.disc_max_c)
    except Exception as exc:  # noqa: BLE001 - never run without a limit: fall back to the user's 70 C
        print("WARNING: could not read flux.disc_max_c from crossing.yaml (%s); using %.0f C"
              % (exc, DISC_MAX_C_DEFAULT), file=sys.stderr)
        return DISC_MAX_C_DEFAULT


def cap_disc_max_c(v) -> float:
    """A disc limit capped at the user's 70 C (PETG tabs): above 70, non-finite or <= 0 -> 70 with a warning."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = float("nan")
    if not math.isfinite(f) or f <= 0 or f > DISC_MAX_C_DEFAULT:
        print("WARNING: flux-disc limit %r refused (the user's limit is %.0f C, PETG tabs); using %.0f C"
              % (v, DISC_MAX_C_DEFAULT, DISC_MAX_C_DEFAULT), file=sys.stderr)
        return DISC_MAX_C_DEFAULT
    return f


def stop_label(trial: Optional[dict]) -> str:
    """'STOPPED: disc 70 C' / 'STOPPED: disc temperature unknown' for a run the disc guard stopped, else ''."""
    r = (trial or {}).get("stop_reason")
    if not r:
        return ""
    lab = STOP_LABELS.get(str(r), "STOPPED: %s" % r)
    lim = (trial or {}).get("disc_max_c")
    if r == STOP_DISC_OVER and lim is not None and float(lim) != 70.0:
        lab = "STOPPED: disc %.0f C" % float(lim)
    return lab


def stopped_lines(runs: Iterable[Any]) -> List[str]:
    """Markdown lines listing runs stopped by the disc guard (objects with .run_id and .trial, or (id, trial))."""
    out = []
    for r in runs:
        rid, trial = (r if isinstance(r, tuple) else (getattr(r, "run_id", "?"), getattr(r, "trial", {}) or {}))
        lab = stop_label(trial)
        if lab:
            det = trial.get("stop_detail") or ""
            out.append("- %s: %s%s (run kept, reported as measured)" % (rid, lab, (" - " + det) if det else ""))
    return out


# ---------------------------------------------------------------------------------------------- risk gate
class RiskGateError(ValueError):
    """Raised when a test that involves a flame is started without a signed risk assessment and a supervisor."""


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def risk_gate(risk_assessment: Optional[str], supervisor: Optional[str]) -> Dict[str, Any]:
    """Check the flame-test preconditions and return the metadata block to store with the run.

    Refuses (RiskGateError) unless `risk_assessment` is an existing, non-empty file that looks like a scan or PDF
    (extension in RISK_EXTENSIONS or PDF/PNG/JPEG/TIFF magic bytes) and `supervisor` is a non-blank name of the
    adult supervisor who signed it. The file itself is not copied; its absolute path, size and SHA-256 are stored
    so the run can be tied to the exact signed document.
    """
    if not supervisor or not str(supervisor).strip():
        raise RiskGateError("refusing to run: --supervisor NAME (the adult supervisor who signed the risk "
                            "assessment) is required for any flame test")
    if not risk_assessment:
        raise RiskGateError("refusing to run: --risk-assessment PATH (scan or PDF of the signed risk assessment) "
                            "is required for any flame test")
    p = Path(risk_assessment).expanduser()
    if not p.is_file():
        raise RiskGateError("refusing to run: risk assessment file not found: %s" % p)
    size = p.stat().st_size
    if size == 0:
        raise RiskGateError("refusing to run: risk assessment file is empty: %s" % p)
    with open(p, "rb") as fh:
        head = fh.read(8)
    if p.suffix.lower() not in RISK_EXTENSIONS and not any(head.startswith(m) for m in _RISK_MAGIC):
        raise RiskGateError("refusing to run: %s does not look like a scan or PDF (expected one of %s)"
                            % (p, ", ".join(RISK_EXTENSIONS)))
    return {"risk_assessment_path": str(p.resolve()), "risk_assessment_bytes": int(size),
            "risk_assessment_sha256": sha256_file(p), "supervisor": str(supervisor).strip(),
            "gate_checked_utc": utc_now()}


def add_risk_args(parser, required_note: str = "required") -> None:
    parser.add_argument("--risk-assessment", metavar="PATH",
                        help="scan/PDF of the adult supervisor's signed risk assessment (%s)" % required_note)
    parser.add_argument("--supervisor", metavar="NAME",
                        help="name of the adult supervisor who signed the risk assessment (%s)" % required_note)


def gate_or_exit(args) -> Dict[str, Any]:
    """CLI wrapper: print the refusal and exit with status 2."""
    try:
        return risk_gate(getattr(args, "risk_assessment", None), getattr(args, "supervisor", None))
    except RiskGateError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)


# ---------------------------------------------------------------------------------------------- metadata / IO
def utc_now(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + ".%03dZ" % int((ts % 1) * 1000)


def utc_stamp(ts: Optional[float] = None) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time() if ts is None else ts))


def base_meta(test: str, argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    from . import __version__
    return {"test": test, "created_utc": utc_now(), "field_tests_version": __version__,
            "python": platform.python_version(), "argv": list(sys.argv if argv is None else argv)}


def _json_default(o):
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError("not JSON serialisable: %r" % type(o))


def clean(obj):
    """NaN/inf -> None recursively (JSON has no NaN)."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return float(obj) if math.isfinite(float(obj)) else None
    return obj


def write_json(path, obj) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), indent=2, default=_json_default, allow_nan=False))
    return path


def read_json(path) -> dict:
    return json.loads(Path(path).read_text())


def fmt(v, nd: int = 3) -> str:
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        if not math.isfinite(float(v)):
            return "nan" if math.isnan(float(v)) else ("inf" if v > 0 else "-inf")
        return ("%%.%dg" % max(nd, 1)) % float(v) if abs(float(v)) >= 1e4 or (0 < abs(float(v)) < 1e-3) \
            else ("%%.%df" % nd) % float(v)
    return str(v)


def write_csv(path, rows: List[Dict[str, Any]], columns: Optional[Sequence[str]] = None,
              simulated: bool = False) -> Path:
    """CSV with a leading `simulated` column on every row (so a copied row keeps its label)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(columns) if columns else sorted({k for r in rows for k in r})
    cols = ["simulated"] + [c for c in cols if c != "simulated"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["true" if simulated else "false"] + [_csv_cell(r.get(c)) for c in cols[1:]])
    return path


def _csv_cell(v):
    if v is None:
        return ""
    if isinstance(v, (float, np.floating)):
        return "" if not math.isfinite(float(v)) and math.isnan(float(v)) else repr(float(v))
    if isinstance(v, (bool, np.bool_)):
        return "true" if v else "false"
    if isinstance(v, (list, tuple, dict)):
        return json.dumps(clean(v), default=_json_default)
    return v


def md_table(rows: List[Dict[str, Any]], columns: Sequence[str], headers: Optional[Sequence[str]] = None,
             nd: int = 3) -> str:
    hd = list(headers) if headers else list(columns)
    out = ["| " + " | ".join(hd) + " |", "|" + "---|" * len(hd)]
    for r in rows:
        out.append("| " + " | ".join(fmt(r.get(c), nd) for c in columns) + " |")
    return "\n".join(out)


def md_snippet(title: str, simulated: bool, body: Iterable[str]) -> str:
    lines = ["### %s" % (("SIMULATED: " + title) if simulated else title), ""]
    if simulated:
        lines += ["> **%s**" % SIM_BANNER, ""]
    lines += list(body)
    lines += ["", "_%s_" % DISCLAIMER, ""]
    return "\n".join(lines)


def out_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------------------------- plotting
def pyplot():
    """matplotlib.pyplot with the Agg backend and a writable MPLCONFIGDIR."""
    if not os.environ.get("MPLCONFIGDIR"):
        os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "mpl")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def finish_figure(fig, path, title: str, simulated: bool) -> Path:
    """Title, SIMULATED watermark when needed, save at 110 dpi, close."""
    plt = pyplot()
    fig.suptitle(("SIMULATED - " + title) if simulated else title, fontsize=11)
    if simulated:
        fig.text(0.5, 0.5, "SIMULATED", transform=fig.transFigure, rotation=28, fontsize=64, color="red",
                 alpha=0.16, ha="center", va="center", zorder=1000, fontweight="bold")
        fig.text(0.99, 0.005, "simulated input - not a measurement", transform=fig.transFigure, fontsize=7,
                 color="red", ha="right", va="bottom")
    else:
        fig.text(0.99, 0.005, "as measured; advisory; limits are placeholders", transform=fig.transFigure,
                 fontsize=7, color="0.4", ha="right", va="bottom")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------------------------- statistics
def finite(xs) -> np.ndarray:
    a = np.asarray([np.nan if v is None else v for v in xs], dtype=float) if not isinstance(xs, np.ndarray) \
        else xs.astype(float)
    return a[np.isfinite(a)]


def summary(xs) -> Dict[str, float]:
    a = finite(xs)
    if a.size == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "min": float("nan"), "p50": float("nan"),
                "p95": float("nan"), "max": float("nan")}
    return {"n": int(a.size), "mean": float(a.mean()), "std": float(a.std(ddof=1)) if a.size > 1 else float("nan"),
            "min": float(a.min()), "p50": float(np.median(a)), "p95": float(np.percentile(a, 95)),
            "max": float(a.max())}


def is_simulated(*flags) -> bool:
    """True if any input flag says simulated (mixed inputs are labelled SIMULATED)."""
    return any(bool(f) for f in flags)
