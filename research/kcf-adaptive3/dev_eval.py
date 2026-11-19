#!/usr/bin/env python3
"""Score one method or tracker configuration on CA-DEV by 4-fold by-fire CV (PROTOCOL section 4). Appends to derived/dev_log.jsonl.

    python3 dev_eval.py NAME '{"cfg": {...}, "update": true, "fc": true}'   # tracker variant
    python3 dev_eval.py FIXED | QUANTILE
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"
import json, sys, time
import numpy as np
from lib3 import *

def main():
    name = sys.argv[1]
    spec = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    D = load()
    if name == "FIXED":
        from methods_base import Fixed; m = Fixed()
    elif name == "QUANTILE":
        from methods2 import Quantile; m = Quantile()
    else:
        m = Tracker(name, spec.get("cfg"), spec.get("update", True), spec.get("fc", True))
    t = time.time()
    r = dev_cv(D, m)
    r.update(name=name, spec=spec, seconds=round(time.time() - t, 1))
    os.makedirs(HERE / "derived", exist_ok=True)
    with open(HERE / "derived" / "dev_log.jsonl", "a") as fh:
        fh.write(json.dumps(r) + "\n")
    print(json.dumps(r))

if __name__ == "__main__":
    main()
