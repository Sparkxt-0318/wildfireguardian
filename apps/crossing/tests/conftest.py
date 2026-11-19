import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]          # apps/crossing
REPO = ROOT.parents[1]                               # repository root
VU = REPO / "hardware" / "vehicle-unit"              # wfgvu (protocol, synth, replay)
for p in (ROOT, VU):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
