#!/usr/bin/env python3
"""S0 of the independent part-a rerun: check every pinned source at its commit, and report PENDING inputs.

Exit 0: all pins match and nothing is pending. Exit 1: a pin mismatch or a missing commit/file.
Exit 3: pins match but inputs are still PENDING (the harness is not yet runnable end to end).
"""
import hashlib, json, subprocess, sys
from pathlib import Path


def main():
    repo, pins = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
    bad = []
    for s in pins["sources"]:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{s['rev']}:{s['path']}"], capture_output=True)
        got = hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else None
        status = "ok" if got == s["sha256"] else ("MISSING" if got is None else "MISMATCH")
        print(f"S0 {status:8s} {s['sha256'][:12]} {s['rev'][:10]}:{s['path']}")
        if status != "ok":
            bad.append(s["path"])
    pend = {k: v for k, v in pins.get("pending", {}).items() if v}
    for k, v in pend.items():
        print(f"S0 PENDING {k}: {v}")
    if bad:
        print("S0 FAIL:", bad); sys.exit(1)
    sys.exit(3 if pend else 0)


if __name__ == "__main__":
    main()
