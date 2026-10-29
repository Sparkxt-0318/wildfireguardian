"""Read-only access to the frozen kit, the frozen bridge and the frozen inputs, with pinned source hashes.

Nothing here edits a frozen file. Every frozen module that this overlay imports is checked against the SHA-256
recorded below before it is imported, so a changed kit fails closed instead of silently changing a result.

Import layout (identical to the RDA worker, `integration/kit/phaseB/rda_worker_v1_1.py`):
  * `routing` is the kit package `integration/kit/routing_candidate/baseline/routing-package/routing`
    (its `validation.py` is byte-identical to the vendored `integration/src/wfg_latest/router_validation/validation.py`);
  * `zsweep`, `road_core` come from `integration/kit/phaseB`;
  * `wildfire` is a namespace package pointing at the vendored radiation operator `integration/src/wfg_latest/radiation`
    (exactly as `integration/src/wfg_latest/build_packet.py` installs it), so packet radiation is the operator the
    inherited checkers recompute. Do not import this module in a process that already imported the forecast package.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
KIT = REPO / "integration" / "kit"
SRC = KIT / "routing_candidate"
WFG_LATEST = REPO / "integration" / "src" / "wfg_latest"

PINNED = {
    "integration/kit/phaseB/zsweep.py": "04b7387f670a5999fe267dede15afe3523f4eca6c20b9d1f5053aac25ab74057",
    "integration/kit/phaseB/road_core.py": "cb38001ecd290dd9148baed9a8fb54529969cf8abd8ae2fd5b13d6929814ec34",
    "integration/kit/routing_candidate/baseline/routing-package/routing/core.py": "8a54c615f287fdc4f4a99058bc5542f70f3106f63eedcdc88e97b4bae22857e8",
    "integration/kit/routing_candidate/baseline/routing-package/routing/independent.py": "0633222da8bcc4123bba272f361b06a41cb05efa68840dbd2ebbe71cdbe68492",
    "integration/kit/routing_candidate/baseline/routing-package/routing/validation.py": "ed5f28007aec47eb0b0361fbd0a3bf704c9db5b9e7a5fc8d4dd31db63ce586a3",
    "integration/kit/routing_candidate/baseline/routing-package/routing/__init__.py": "d47c0402213c0bd5b743f8dc4fe3c818fe3d70e79962b9ec88e2f1fef29eb99d",
    "integration/kit/routing_candidate/baseline/routing-package/routing/prepared.py": "1ff08671b2abefcd0ee3bba4de32c5e36c6750c56fb013dbc462cf765a05ad07",
    "integration/kit/routing_candidate/baseline/routing-package/routing/admission_geometry.py": "7d548dee459b7d6c8c08e227a6f32fbfb759bec99648847ef66462265956fa96",
    "integration/src/wfg_latest/bridge.py": "f7466e647bc91ca5d0e7a39c13dedcde96a106620a1382c7662f708e83d3c96b",
    "integration/src/wfg_latest/packets.py": "6b922418b50ae761bcfcdff372fe08346730eca121630a20454f4cd05c4fc5bb",
    "integration/src/wfg_latest/contract.py": "461fb56a058cf15070c1cf3887cccddddbea84d4ef6f110fad2a8b0917c42d42",
    "integration/src/wfg_latest/requests.py": "f1737cafff686a8112e625894c9ebb8190f28ed78f27c2cdfe8cf60e0a1f0d4c",
    "integration/src/wfg_latest/export.py": "fe9e6b65cb959cc341b13c55bfd15a1ca8e610e06cd7b57e24ec2883e2ac5686",
    "integration/src/wfg_latest/radiation/heat.py": "f52b4c31ba83d59c9a9b29e669c738e94d7de3b8bff723b1108ebcc11984acfb",
    "integration/src/wfg_latest/radiation/coordinates.py": "9a9f56a60083bdb9e2990ca710280bfd75b7c004f2648d0af3d45a4f5c5a3dd3",
    "integration/src/wfg_latest/radiation/paths.py": "37c1a19a4ff191641d2980b7bd6576a1e738b6d7cf56876677b9ad650010d6fd",
}

# Frozen evaluated inputs (tools/fetch_routing_inputs.py, release research-final-20261015).
INPUT_ARCHIVE_SHA256 = "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"
INPUT_FILES_JSON_SHA256 = "5d820b97740d879d2bc78a76d1b5854420793c927c6315f656dc1c2927b35235"


class FrozenIdentityError(RuntimeError):
    pass


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def verify_pins(keys=None) -> dict:
    out = {}
    for rel, expected in PINNED.items():
        if keys is not None and rel not in keys:
            continue
        actual = sha256_file(REPO / rel)
        if actual != expected:
            raise FrozenIdentityError("frozen source changed: %s (%s != %s)" % (rel, actual, expected))
        out[rel] = actual
    return out


_INSTALLED = {}


def install():
    """Put the frozen kit on sys.path and the vendored radiation operator under the name `wildfire` (idempotent)."""
    if _INSTALLED:
        return _INSTALLED
    verify_pins()
    if "wildfire" in sys.modules and getattr(sys.modules["wildfire"], "__path__", None) != [str(WFG_LATEST / "radiation")]:
        raise FrozenIdentityError("a different `wildfire` package is already imported; run routing-side code in its own process")
    if "wildfire" not in sys.modules:
        pkg = types.ModuleType("wildfire")
        pkg.__path__ = [str(WFG_LATEST / "radiation")]
        sys.modules["wildfire"] = pkg
    for p in (str(KIT / "phaseB"), str(SRC / "search"), str(SRC / "baseline"), str(SRC / "baseline" / "routing-package")):
        if p not in sys.path:
            sys.path.insert(0, p)
    if str(WFG_LATEST) not in sys.path:      # appended last: its requests.py must not shadow the HTTP library
        sys.path.append(str(WFG_LATEST))
    routing = importlib.import_module("routing")
    if Path(routing.__file__).resolve().parent != (SRC / "baseline" / "routing-package" / "routing").resolve():
        raise FrozenIdentityError("`routing` resolved to an unexpected location: %s" % routing.__file__)
    _INSTALLED.update(
        core=importlib.import_module("routing.core"),
        independent=importlib.import_module("routing.independent"),
        validation=importlib.import_module("routing.validation"),
        zsweep=importlib.import_module("zsweep"),
        road_core=importlib.import_module("road_core"),
        bridge=importlib.import_module("bridge"),
        packets=importlib.import_module("packets"),
        contract=importlib.import_module("contract"),
        requests=_load_requests(),
    )
    return _INSTALLED


def _load_requests():
    spec = importlib.util.spec_from_file_location("wfg_latest_requests_frozen", WFG_LATEST / "requests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------------------------------------ frozen inputs
def input_root() -> Path:
    """Location of the verified frozen inputs: $WFG_ROUTING_INPUTS, else <repo>/data/routing, else the shared host copy."""
    for candidate in (os.environ.get("WFG_ROUTING_INPUTS"), REPO / "data" / "routing", "/home/user/wfg-shared/routing-inputs"):
        if candidate and (Path(candidate) / "INPUT_FILES.json").is_file():
            return Path(candidate)
    raise FileNotFoundError("frozen routing inputs not found; run tools/fetch_routing_inputs.py or set WFG_ROUTING_INPUTS")


def inputs_available() -> bool:
    try:
        input_root()
        return True
    except FileNotFoundError:
        return False


def verify_inputs(root=None) -> dict:
    root = Path(root or input_root())
    actual = sha256_file(root / "INPUT_FILES.json")
    if actual != INPUT_FILES_JSON_SHA256:
        raise FrozenIdentityError("INPUT_FILES.json differs from the evaluated input listing")
    return {"root": str(root), "input_files_json_sha256": actual, "archive_sha256": INPUT_ARCHIVE_SHA256}


# The 15 windows and 20 missions of the frozen Korean panel (region, cutoff tag, event, mission suffixes).
PANEL = [
    ("hongseong_2023", "20230402T070000Z", "KFS_05", ["FN1", "FX1"]),
    ("hongseong_2023", "20230402T140000Z", "KFS_05", ["FW2"]),
    ("hongseong_2023", "20230402T230000Z", "KFS_05", ["FD1"]),
    ("miryang_2022", "20220531T100000Z", "KFS_11", ["FN1"]),
    ("miryang_2022", "20220601T020000Z", "KFS_11", ["FW1"]),
    ("miryang_2022", "20220601T080000Z", "KFS_11", ["FD1", "FX1"]),
    ("uiseong_andong_2025", "20250323T010000Z", "KFS_01", ["FD1", "FX2"]),
    ("uiseong_andong_2025", "20250324T090000Z", "KFS_01", ["FL2"]),
    ("uiseong_andong_2025", "20250325T170000Z", "KFS_01", ["FW1"]),
    ("uljin_2022", "20220304T030000Z", "KFS_02", ["FD1", "FX1"]),
    ("uljin_2022", "20220304T060000Z", "KFS_02", ["FL1"]),
    ("uljin_2022", "20220304T120000Z", "KFS_02", ["FW2"]),
    ("yeongdeok_2025", "20250325T190000Z", "KFS_01", ["FD1", "FX2"]),
    ("yeongdeok_2025", "20250325T230000Z", "KFS_01", ["FL2"]),
    ("yeongdeok_2025", "20250326T080000Z", "KFS_01", ["FW1"]),
]
PARENT_FIRE = {"hongseong_2023": "Hongseong 2023", "miryang_2022": "Miryang 2022", "uljin_2022": "Uljin 2022",
               "uiseong_andong_2025": "Gyeongbuk 2025", "yeongdeok_2025": "Gyeongbuk 2025"}


def missions():
    return [(region, tag, event, m) for region, tag, event, ms in PANEL for m in ms]


def paths(region, tag, event=None, mission=None, root=None):
    root = Path(root or input_root())
    base = root / "latest_inputs_try02"
    out = {"graph": root / "graphs" / region / "graph.json", "packet": base / "packets" / region / tag}
    if event is not None:
        out["export_npz"] = base / "exports" / event / ("FORECAST_%s.npz" % tag)
        out["export_record"] = base / "exports" / event / ("FORECAST_RECORD_%s.json" % tag)
    if mission is not None:
        out["request"] = base / "requests" / region / ("%s_%s.json" % (tag, mission))
    return out


def cutoff_iso(tag) -> str:
    return "%s-%s-%sT%s:%s:%sZ" % (tag[0:4], tag[4:6], tag[6:8], tag[9:11], tag[11:13], tag[13:15])
