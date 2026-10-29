"""Write SOURCE_SHA256.json for this overlay (its own files, the 1C-1 modules it imports, the pinned frozen files).
`--check` verifies instead."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MEMBERS = REPO / "experimental" / "scenario-members"
sys.path.insert(0, str(MEMBERS / "src"))
from wfg_members.kit import PINNED  # noqa: E402

IMPORTED_1C1 = ["src/wfg_members/__init__.py", "src/wfg_members/kit.py", "src/wfg_members/planner.py", "src/wfg_members/contact.py",
                "src/wfg_members/figures.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest():
    own = sorted(p for p in HERE.rglob("*") if p.is_file() and p.suffix in (".py", ".txt", ".md")
                 and "__pycache__" not in p.parts and p.name != "SOURCE_SHA256.json")
    return {"overlay": {str(p.relative_to(REPO)): sha(p) for p in own},
            "imported_from_track_1c1": {str((MEMBERS / r).relative_to(REPO)): sha(MEMBERS / r) for r in IMPORTED_1C1},
            "frozen_imports_pinned": dict(PINNED),
            "documents": {r: sha(REPO / r) for r in ("docs/SIPP_EQUIVALENCE.md", "docs/JOURNEY_SAFETY_PREDICATE.md")}}


if __name__ == "__main__":
    out = HERE / "SOURCE_SHA256.json"
    m = manifest()
    if "--check" in sys.argv:
        old = json.loads(out.read_text())
        bad = [k for sec in m for k in m[sec] if old.get(sec, {}).get(k) != m[sec][k]]
        raise SystemExit("MISMATCH %s" % bad if bad else 0)
    out.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print("wrote", out, sum(len(v) for v in m.values()), "entries")
