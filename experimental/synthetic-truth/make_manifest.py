"""Write SOURCE_SHA256.json for this overlay: its own files, the 1C-1 and 1C-2 modules it imports, the pinned frozen
files, and the identities of external material it consulted or used. `--check` verifies instead."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXP = REPO / "experimental"
sys.path.insert(0, str(EXP / "scenario-members" / "src"))
from wfg_members.kit import PINNED  # noqa: E402

IMPORTED = ["scenario-members/bridge_v2.py"] + ["scenario-members/src/wfg_members/%s.py" % m for m in
            ("__init__", "kit", "contact", "planner", "check", "decide", "acceptance", "coverage", "reduction", "figures")] + \
           ["sipp-routing/src/wfg_sipp/%s.py" % m for m in ("__init__", "intervals", "sipp", "frontend")]
EXTERNAL = {
    "zenodo_21788344_archive_sha256": "612edf5f879d8fe874ae20e9d49d0be5de477e6f8c3101b434f1642d5b19ebad",
    "zenodo_21788344_doi": "10.5281/zenodo.21788344 (CC-BY-4.0); Korean time-of-arrival rasters, byte-identical to the export records",
    "wildfireguardian_osse_repository": "Sparkxt-0318/wildfireguardian-osse at 69f3b7ec77aa40a69fbafeb8e39a41288f2eaceb (read-only clone)",
    "wildfireguardian_osse_files_consulted_sha256": {
        "README.md": "1c7f63225c4fe29cf1c74e6d92cb03705c836f9a4eff225ae6eb1f3bb0b8f3b8",
        "src/wildfireguardian_osse/observations/missingness.py": "b31f3bdbdb15083638f172422fdf761844b0119a63248fbec9edd6c5466d8a7e",
        "src/wildfireguardian_osse/validation/leakage.py": "6306190d349e0a5a595101c46ec58b7b8cba75261ac112b3fefde564e8e07df5"},
    "wildfireguardian_osse_reuse": "concepts only (truth never reaches the planner; closed-open outage intervals; informative missingness); no code copied",
    "farsite": {"repository": "https://github.com/mbedward/farsite.git", "revision": "4537d60ab013fa91d0b49d8efb385ffb1b3ddd13",
                "built_with": "forecast/wildfire/farsite_build.py", "executable_sha256_this_host": "b6ee69a21a33e7d737a2bc3a5532a51eb3ca7580b028752e81569bda6b3b9232"},
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest():
    own = sorted(p for p in HERE.rglob("*") if p.is_file() and p.suffix in (".py", ".txt", ".md")
                 and "__pycache__" not in p.parts and p.name != "SOURCE_SHA256.json")
    return {"overlay": {str(p.relative_to(REPO)): sha(p) for p in own},
            "imported_from_tracks_1c1_1c2": {"experimental/" + r: sha(EXP / r) for r in IMPORTED},
            "frozen_imports_pinned": dict(PINNED), "external": EXTERNAL}


if __name__ == "__main__":
    out = HERE / "SOURCE_SHA256.json"
    m = manifest()
    if "--check" in sys.argv:
        old = json.loads(out.read_text())
        bad = [k for sec in ("overlay", "imported_from_tracks_1c1_1c2", "frozen_imports_pinned") for k in m[sec]
               if old.get(sec, {}).get(k) != m[sec][k]]
        raise SystemExit("MISMATCH %s" % bad if bad else 0)
    out.write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print("wrote", out)
