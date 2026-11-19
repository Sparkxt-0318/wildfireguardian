"""Parallel HTTP range download through curl (the network path here gives ~8 KB/s per connection).

    python pdl.py URL OUT [--par 32] [--chunk-mb 1]
"""
import argparse, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("out")
ap.add_argument("--par", type=int, default=32); ap.add_argument("--chunk-mb", type=float, default=1)
a = ap.parse_args()
if os.path.exists(a.out):
    print("exists", a.out); sys.exit(0)
head = subprocess.run(["curl", "-sIL", "--max-time", "120", a.url], capture_output=True, text=True).stdout
n = [int(l.split(":")[1]) for l in head.splitlines() if l.lower().startswith("content-length")]
if not n:
    sys.exit(f"no length for {a.url}")
L = n[-1]; ch = int(a.chunk_mb * 1048576); parts = a.out + ".parts"; os.makedirs(parts, exist_ok=True)
jobs = [(i, s, min(s + ch, L) - 1) for i, s in enumerate(range(0, L, ch))]


def get(j):
    i, s, e = j
    f = os.path.join(parts, f"{i:06d}")
    for _ in range(10):
        if os.path.exists(f) and os.path.getsize(f) == e - s + 1:
            return True
        subprocess.run(["curl", "-sL", "--max-time", "1200", "-r", f"{s}-{e}", "-o", f, a.url])
    return False


with ThreadPoolExecutor(a.par) as ex:
    ok = list(ex.map(get, jobs))
if not all(ok):
    sys.exit(f"failed parts: {ok.count(False)}")
with open(a.out + ".tmp", "wb") as w:
    for i, _, _ in jobs:
        with open(os.path.join(parts, f"{i:06d}"), "rb") as r:
            w.write(r.read())
assert os.path.getsize(a.out + ".tmp") == L
os.replace(a.out + ".tmp", a.out)
for f in os.listdir(parts):
    os.remove(os.path.join(parts, f))
os.rmdir(parts)
print("ok", a.out, L)
