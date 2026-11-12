"""Router regression 2: waiting at non-waitable nodes (Marcus, F-BASE 6f0925fa, approved by the orchestrator).

The 24 F-DYN v3.3 failure rows of F-BASE RESULTS_fdyn.json "failures": a one-earliest-label shortcut is wrong on all
of them, always through waiting at non-waitable nodes. Each row's integer instance is a committed fixture
(fixtures/nonwaitable/<instance_sha256>.instance.xz, the exact INSTANCE text F-3.2's generate.instance_text writes),
rebuilt here from Leo's v3.3 packets and requests (requests.py @ 20b29ce) with routing-next's build_instance; every
fixture's sha256 equals Marcus's recorded instance_sha256 (cases.json records the check).

Solvers: the router (wfg_sipp.sipp.solve) and F-BASE (vendor/fbase_a9065591.py, verbatim from a9065591, sha pinned):
solve_exact, solve_n1 (wait anywhere, WB ignored) and solve_n2 (one label, waiting rules respected).

Assertions per row (monotone form agreed with Marcus):
  (a) unmutated: router == recorded exact == fbase.solve_exact; and the row's shortcut (n1 or n2) reproduces the
      recorded wrong answer, so the fixture really exercises the failure;
  (b) all_wait mutation (every node waitable, WB unchanged, i.e. newly waitable nodes have an EMPTY wait block --
      an ablation that allows waiting at a burning node, not a model variant): router == fbase.solve_n1 ==
      recorded all_wait.exact;
  (c) all_wait: fbase.solve_n2 == router (the shortcut becomes correct once every node is waitable);
  (d) mutated arrival <= unmutated arrival (NO_ROUTE = +inf): adding waiting only adds options.
Scope: router behaviour on HAZARD-derived instances of the v3.3 packets. Packet consistency (P1: HAZARD vs
ContactModel vs raw arrays) is recorded per packet in cases.json; it is not X1 rule 3.
"""
import lzma
import hashlib
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "nonwaitable"
VENDOR = HERE / "vendor" / "fbase_a9065591.py"
FBASE_SHA = "f065362617f3ef987d15ac48db1f005c143e6ab55be206fd709c9ea8efa517cb"


def load_fbase():
    if hashlib.sha256(VENDOR.read_bytes()).hexdigest() != FBASE_SHA:
        raise AssertionError("vendored fbase.py differs from a9065591")
    spec = importlib.util.spec_from_file_location("fbase_a9065591", VENDOR)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses need the module registered before exec
    spec.loader.exec_module(mod)
    return mod


def router(fb_inst):
    """Run wfg_sipp.sipp.solve on the same integer instance."""
    from wfg_sipp import sipp as S
    inst = S.make_instance(n_nodes=fb_inst.nV, tail=list(fb_inst.tail), head=list(fb_inst.head), D=list(fb_inst.D),
                           origin=fb_inst.origin, start_state=fb_inst.s0, forbidden=set(fb_inst.forbid),
                           waitable=[n in fb_inst.waitable for n in range(fb_inst.nV)],
                           edge_block=dict(fb_inst.EB), wait_block=dict(fb_inst.WB), accept=dict(fb_inst.AC),
                           departure=fb_inst.dep, horizon=fb_inst.H)
    r = S.solve(inst)
    if r["status"] == "FOUND":
        return ["ROUTE", r["arrival"]]
    if r["status"] == "EXHAUSTED":
        return ["NO_ROUTE", None]
    raise AssertionError("router did not finish: %s" % r["status"])


def all_wait(fb, inst):
    import copy
    i = copy.deepcopy(inst)
    i.waitable = set(range(i.nV))
    return i


def arrival(x):
    return math.inf if x[0] == "NO_ROUTE" else x[1]


class NonWaitableRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fb = load_fbase()
        cls.cases = json.loads((FIX / "cases.json").read_text())["rows"]
        cls._inst = {}

    def inst(self, sha):
        if sha not in self._inst:
            data = lzma.decompress((FIX / (sha + ".instance.xz")).read_bytes())
            self.assertEqual(hashlib.sha256(data).hexdigest(), sha, "fixture bytes differ from recorded instance sha")
            self._inst[sha] = self.fb.parse_instance("WFGC 1\n" + data.decode())
        return self._inst[sha]

    def test_count(self):
        self.assertEqual(len(self.cases), 24)
        self.assertTrue(all(c["request_sha_ok"] and c["instance_sha_ok"] for c in self.cases))

    def test_rows(self):
        for c in self.cases:
            with self.subTest(packet=c["packet"], origin=c["origin"], departure=c["departure"], solver=c["solver"]):
                I = self.inst(c["instance_sha256"])
                exact = list(self.fb.solve_exact(I)[:2])
                r0 = router(I)
                # (a)
                self.assertEqual(r0, c["exact"])
                self.assertEqual(exact, c["exact"])
                naive = list(getattr(self.fb, "solve_" + c["solver"])(I))
                self.assertEqual(naive, c["naive"])
                self.assertNotEqual(naive, r0)
                # (b)
                J = all_wait(self.fb, I)
                r1 = router(J)
                self.assertEqual(r1, list(self.fb.solve_n1(J)))
                self.assertEqual(r1, c["all_wait"]["exact"])
                # (c)
                self.assertEqual(list(self.fb.solve_n2(J)), r1)
                # (d)
                self.assertLessEqual(arrival(r1), arrival(r0))


if __name__ == "__main__":
    unittest.main()
