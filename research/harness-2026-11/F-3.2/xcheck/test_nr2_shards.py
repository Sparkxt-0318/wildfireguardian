"""NR2_CERT_RULE note 2: sharding changes scheduling only.

Needs the real inputs (skipped otherwise):
  NR2_LEO       Leo's v3.7 worktree
  NR2_REQUESTS  requests.py output dir
  NR2_CHECKPOINT the sequential run's --out dir (ROWS.jsonl + bundles/)
  NR2_PACKETS   file with the packet list (one per line), NR2_GATE_ONLY optional substring for gate-only packets

(1) For the full plan and N in {2, 3, 4}: shard index sets are disjoint and cover every row.
(2) End to end through the CLI: a temp --out holds the sequential checkpoint's rows of one packet (bundles linked)
    minus a sample of S rows; `--shard 0/2` and `--shard 1/2` recompute exactly the sample between them, and each
    recomputed row equals the sequential record in claim, T, I, verdict and bundle sha256. `--merge` then reports 0
    duplicates.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ENV = ("NR2_LEO", "NR2_REQUESTS", "NR2_CHECKPOINT", "NR2_PACKETS")
S = 4
FIELDS = ("claim", "T", "I", "verdict", "bundle_sha256")


@unittest.skipUnless(all(os.environ.get(v) for v in ENV), "needs " + ", ".join(ENV))
class Shards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import nr2_certs
        cls.m = nr2_certs
        cls.leo, cls.req, cls.ck = (Path(os.environ[v]) for v in ENV[:3])
        cls.packets = Path(os.environ["NR2_PACKETS"]).read_text().split()
        g = os.environ.get("NR2_GATE_ONLY", "_h5_envelope_central")
        cls.gate_only = [p for p in cls.packets if g in p]
        cls.seq = [r for r in nr2_certs.read_rows([cls.ck / "ROWS.jsonl"]) if r["kind"] == "row"]

    def test_partition(self):
        plan = self.m.row_plan(self.leo, self.req, self.packets, [0, 7200], self.gate_only)
        keys = [(rel, o, d) for rel, o, d, _ in plan]
        self.assertEqual(len(keys), len(set(keys)))
        for N in (2, 3, 4):
            parts = [{x for i, x in enumerate(keys) if i % N == k} for k in range(N)]
            self.assertEqual(sum(map(len, parts)), len(keys))
            self.assertEqual(set().union(*parts), set(keys))

    def test_sharded_equals_sequential(self):
        rel = self.packets[0]                       # first packet: complete in the sequential checkpoint
        rows = [r for r in self.seq if r["packet"] == rel]
        self.assertEqual(len(rows), len(self.m.row_plan(self.leo, self.req, [rel], [0, 7200])))
        sample = random.Random(20261113).sample(rows, S)
        skeys = {(r["origin"], r["departure"]) for r in sample}
        with tempfile.TemporaryDirectory() as td:
            out = Path(td); (out / "bundles").mkdir()
            keep = [r for r in self.m.read_rows([self.ck / "ROWS.jsonl"])
                    if r["packet"] == rel and (r["kind"] == "packet" or (r["origin"], r["departure"]) not in skeys)]
            (out / "ROWS.jsonl").write_text("".join(json.dumps(r) + "\n" for r in keep))
            for r in keep:
                if r["kind"] == "row":
                    (out / "bundles" / r["bundle"]).symlink_to(self.ck / "bundles" / r["bundle"])
            base = [sys.executable, str(HERE / "nr2_certs.py"), "--leo", str(self.leo), "--requests", str(self.req),
                    "--out", str(out), "--packets", rel]
            for k in (0, 1):
                subprocess.run(base + ["--shard", "%d/2" % k], check=True, capture_output=True)
            new = self.m.read_rows(sorted(out.glob("ROWS.shard*.jsonl")))
            self.assertEqual({(r["origin"], r["departure"]) for r in new}, skeys)
            self.assertEqual(len(new), S)
            ref = {(r["origin"], r["departure"]): r for r in sample}
            for r in new:
                with self.subTest(origin=r["origin"], departure=r["departure"]):
                    self.assertEqual({f: r[f] for f in FIELDS}, {f: ref[(r["origin"], r["departure"])][f] for f in FIELDS})
            mg = subprocess.run([sys.executable, str(HERE / "nr2_certs.py"), "--out", str(out), "--merge"],
                                capture_output=True, text=True)
            self.assertEqual(mg.returncode, 0, mg.stdout + mg.stderr)
            self.assertIn("0 duplicates", mg.stdout)


if __name__ == "__main__":
    unittest.main()
