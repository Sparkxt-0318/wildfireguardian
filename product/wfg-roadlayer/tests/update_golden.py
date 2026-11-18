"""Regenerate golden/ from a fresh run of the worked example. Only after a deliberate, reviewed change:
the golden test exists to catch every unintended one.

    python3 tests/update_golden.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from wfg_roadlayer import cli  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "ex"
        assert cli.main(["example", "--out", str(out)]) == 0
        golden = PRODUCT / "golden"
        if golden.exists():
            shutil.rmtree(golden)
        for case in sorted(p for p in out.iterdir() if p.is_dir()):
            run = json.loads((case / "run.json").read_text(encoding="utf-8"))
            g = golden / case.name
            for rel in run["files_sha256"]:
                if rel.endswith(".csv"):
                    (g / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(case / rel, g / rel)
            keep = {k: run[k] for k in ("counts", "villages", "certificates", "sheets", "files_sha256", "fire_input", "region")}
            keep["model"] = {"instance_sha256_uncompressed": run["model"]["instance_sha256_uncompressed"]}
            keep["versions"] = {"reportlab": run["versions"]["reportlab"]}
            (g / "MANIFEST.json").parent.mkdir(parents=True, exist_ok=True)
            (g / "MANIFEST.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            print("golden", case.name, len(run["files_sha256"]), "files")


if __name__ == "__main__":
    main()
