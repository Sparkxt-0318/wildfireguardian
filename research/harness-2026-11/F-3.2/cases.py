"""Map the 26 native-panel cases to local frozen inputs (data/routing) and verify their sha256 identities."""
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PANEL = ROOT / "research/sipp-routing/native-panel-20261030"
DATA = ROOT / "data/routing"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def korean_cases():
    out = []
    for i in range(26):
        c = json.loads((PANEL / ("case_%02d.json" % i)).read_text())
        if c["panel"] != "Korean":
            continue
        region, mission = c["region"], c["mission"]
        local = dict(graph=DATA / "graphs" / region / "graph.json",
                     request=DATA / "latest_inputs_try02/requests" / region / (mission + ".json"),
                     packet=DATA / "latest_inputs_try02/packets" / region / mission.split("_")[0])
        for k in ("graph", "request"):
            if sha(local[k]) != c["input_sha256"][k]:
                raise RuntimeError("INPUT_IDENTITY_MISMATCH %s %s" % (mission, k))
        for name in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz", "HAZARD.json"):
            if sha(local["packet"] / name) != c["input_sha256"][name]:
                raise RuntimeError("INPUT_IDENTITY_MISMATCH %s %s" % (mission, name))
        out.append(dict(index=i, region=region, mission=mission, **{k: str(v) for k, v in local.items()}))
    return out
