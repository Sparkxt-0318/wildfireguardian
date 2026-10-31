"""Verify the recorded pre-repair artifacts without decoding scientific data."""
from pathlib import Path
import json,subprocess
R=Path(__file__).resolve().parents[1]
m=json.loads((R/"research/postmerge-fixes-20261031/FROZEN_GIT_BLOBS.json").read_text())
for path,expected in m["files"].items():
    actual=subprocess.check_output(["git","-C",str(R),"hash-object",str(R/path)],text=True).strip()
    if actual!=expected:raise SystemExit("Frozen artifact changed: "+path)
print("PASS:",len(m["files"]),"frozen artifacts byte-identical")
