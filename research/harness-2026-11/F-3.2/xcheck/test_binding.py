"""Binding tests T1-T6 (BINDING_RULE.md rev 2.1) on both checkers, using the existing checker test bundles.

Every case runs through BOTH checkers as subprocesses (check_py.py and checker_c/wfgc_check) and requires the same
ACCEPT/REJECT verdict and exit status from each. T7-T9 need real inputs (panel / packets) and live in
test_binding_inputs.py; T10 is checker_c/tests/test_sha256.py.
"""
import glob
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
F32 = HERE.parent
sys.path.insert(0, str(F32))
import bind_bundle  # noqa: E402

C_BIN = F32 / "checker_c" / "wfgc_check"
TESTS = sorted(glob.glob(str(F32 / "checker_c" / "tests" / "*.wfgc")))
DG = {f: hashlib.sha256(("digest-" + f).encode()).hexdigest() for f in "GAWQ"}


def expect_arg(dg):
    return ",".join("%s=%s" % (f, dg[f]) for f in "GAWQ")


def run_both(path, expect=None):
    extra = [] if expect is None else ["--expect", expect_arg(expect)]
    out = {}
    for name, cmd in (("py", [sys.executable, str(F32 / "check_py.py")]), ("c", [str(C_BIN)])):
        r = subprocess.run(cmd + [str(path)] + extra, capture_output=True, text=True)
        out[name] = (r.stdout.strip(), r.returncode)
    return out


def flip_bit(hexd, bit=0):
    b = bytearray(bytes.fromhex(hexd)); b[bit // 8] ^= 1 << (bit % 8)
    return b.hex()


class Binding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["make", "-s", "-C", str(F32 / "checker_c")], check=True)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return p

    def v2(self, src, dg=DG):
        text, I = bind_bundle.to_v2(Path(src).read_text(), dg)
        return self.write("v2_" + os.path.basename(src), text), I

    def both(self, path, expect, verdict, code, reason_py=None, reason_c=None):
        r = run_both(path, expect)
        for name, (out, rc) in r.items():
            self.assertEqual(out.split()[0], verdict, (name, path.name, out))
            self.assertEqual(rc, code, (name, path.name, out))
        if reason_py:
            self.assertEqual(r["py"][0], "REJECT " + reason_py)
        if reason_c:
            self.assertEqual(r["c"][0], "REJECT " + reason_c)
        return r

    # T6 positive / same verdicts: every existing case in v2 form with the correct --expect
    def test_t6_existing_suite_bound(self):
        self.assertEqual(len(TESTS), 30)
        for src in TESTS:
            p, I = self.v2(src)
            want = ("ACCEPT", 0) if os.path.basename(src).startswith("accept_") else ("REJECT", 1)
            r = self.both(p, DG, *want)
            if want[0] == "ACCEPT":
                for name in ("py", "c"):
                    toks = r[name][0].split()
                    self.assertEqual(toks[-2:], ["BOUND", I[:16]], (name, src))
                self.assertEqual(r["py"][0], r["c"][0])

    # T5: v2 without --expect -> ACCEPT ... UNBOUND (both); v1 output unchanged
    def test_t5_unbound(self):
        src = F32 / "checker_c" / "tests" / "accept_route_wait.wfgc"
        p, _ = self.v2(src)
        r = self.both(p, None, "ACCEPT", 0)
        self.assertEqual(r["py"][0], "ACCEPT ROUTE 7 UNBOUND")
        self.assertEqual(r["c"][0], "ACCEPT ROUTE 7 UNBOUND")
        r1 = self.both(src, None, "ACCEPT", 0)
        self.assertEqual(r1["py"][0], "ACCEPT ROUTE 7")
        self.assertEqual(r1["c"][0], "ACCEPT ROUTE 7")

    # T1 (synthetic form): a bundle bound to request A, checked with request B's digests
    def test_t1_swap(self):
        src = F32 / "checker_c" / "tests" / "accept_no_route.wfgc"
        p, _ = self.v2(src)
        other = dict(DG, Q=hashlib.sha256(b"another request").hexdigest())
        self.both(p, other, "REJECT", 1, "BIND_Q", "bind_Q")

    # T2: one bit flipped in each digest field
    def test_t2_single_digest_mutation(self):
        src = F32 / "checker_c" / "tests" / "accept_route_wait.wfgc"
        for f in "GAWQ":
            for bit in (0, 255):
                p, _ = self.v2(src)
                self.both(p, dict(DG, **{f: flip_bit(DG[f], bit)}), "REJECT", 1, "BIND_" + f, "bind_" + f)
        # the I field itself, in the file
        text, I = bind_bundle.to_v2(src.read_text(), DG)
        words = " ".join(str(int(I[8 * i:8 * i + 8], 16)) for i in range(8))
        bad = flip_bit(I, 3)
        bad_words = " ".join(str(int(bad[8 * i:8 * i + 8], 16)) for i in range(8))
        p = self.write("t2_I.wfgc", text.replace("I " + words, "I " + bad_words, 1))
        self.both(p, DG, "REJECT", 1, "BIND_INSTANCE_DIGEST", "bind_instance_digest")
        self.both(p, None, "REJECT", 1, "BIND_INSTANCE_DIGEST", "bind_instance_digest")

    # T3: an instance edit that leaves the certificate valid must still fail on the digest
    def test_t3_instance_edit(self):
        src = F32 / "checker_c" / "tests" / "accept_no_route.wfgc"
        text, _ = bind_bundle.to_v2(src.read_text(), DG)
        a, b = bind_bundle.instance_span(text)
        inst = text[a:b]
        # a semantically neutral edit: extra space inside the instance (whitespace runs are legal tokens separators)
        edited = text[:a] + inst.replace("\n", " \n", 1) + text[b:]
        p = self.write("t3_ws.wfgc", edited)
        self.both(p, DG, "REJECT", 1, "BIND_INSTANCE_DIGEST", "bind_instance_digest")
        # and the same edit in a v1 bundle is accepted (it is not a certificate error): the digest is what catches it
        v1 = src.read_text()
        a1, b1 = bind_bundle.instance_span(v1)
        p1 = self.write("t3_ws_v1.wfgc", v1[:a1] + v1[a1:b1].replace("\n", " \n", 1) + v1[b1:])
        self.both(p1, None, "ACCEPT", 0)

    # T4: malformed BIND, and v1 + --expect
    def test_t4_malformed(self):
        src = F32 / "checker_c" / "tests" / "accept_route_wait.wfgc"
        text, I = bind_bundle.to_v2(src.read_text(), DG)
        cases = {
            "no_bind": text[:text.index("BIND\n")] + text[text.index("END_BIND\n") + len("END_BIND\n"):],
            "field_order": text.replace("\nG ", "\nX ", 1).replace("\nA ", "\nG ", 1).replace("\nX ", "\nA ", 1),
            "word_range": text.replace("\nW ", "\nW 4294967296 ", 1),
            "bind_after_claim": (text[:text.index("BIND\n")] + text[text.index("CLAIM"):text.index("WITNESS")]
                                 + text[text.index("BIND\n"):text.index("END_BIND\n") + len("END_BIND\n")]
                                 + text[text.index("WITNESS"):]),
            "layout_no_newline": text.replace("END_INSTANCE\n", "END_INSTANCE BIND\n", 1).replace("BIND\nBIND\n", "BIND\n", 1),
        }
        for name, t in cases.items():
            p = self.write("t4_%s.wfgc" % name, t)
            self.both(p, DG, "REJECT", 1)
            self.both(p, None, "REJECT", 1)
        # format 1 with --expect -> BIND_MISSING
        self.both(src, DG, "REJECT", 1, "BIND_MISSING", "bind_missing")


if __name__ == "__main__":
    unittest.main()
