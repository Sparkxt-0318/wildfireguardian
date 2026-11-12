"""p1_check.require_routable_arrays / from_raw refuse HAZARD-only packets (Leo 588f74e) and never skip cells.
Run: [WFG_REAL_PACKET=<real packet dir>] python test_raw_guard.py  (or pytest; the env var adds the end-to-end check)"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import p1_check as P  # noqa: E402

REAL = os.environ.get("WFG_REAL_PACKET")  # a real packet dir; argv is not used, so pytest and unittest both work


def npz(**arrs):
    d = tempfile.mkdtemp(); p = Path(d) / "a.npz"; np.savez(p, **arrs)
    return np.load(p), d


class Guard(unittest.TestCase):
    def _ok(self, **arrs):
        a, d = npz(**arrs)
        try:
            P.require_routable_arrays(a, "pk")
        finally:
            a.close(); shutil.rmtree(d)

    def _bad(self, **arrs):
        with self.assertRaises(ValueError):
            self._ok(**arrs)

    def test_inf_never_ignites_is_valid(self):
        self._ok(ignition_time_s=np.array([[[0.0, np.inf, 300.0]]]))

    def test_nan_birth_refused(self):
        self._bad(ignition_time_s=np.array([[[0.0, np.nan, np.inf]]]))

    def test_minus_inf_birth_refused(self):
        self._bad(ignition_time_s=np.array([[[-np.inf, 0.0]]]))

    def test_marker_refused_even_with_finite_births(self):
        self._bad(ignition_time_s=np.array([[[0.0]]]), per_cell_law_HAZARD_only=np.array(True))

    def test_marker_false_is_fine(self):
        self._ok(ignition_time_s=np.array([[[0.0]]]), per_cell_law_HAZARD_only=np.array(False))


@unittest.skipUnless(REAL, "set WFG_REAL_PACKET to a real packet directory to run the end-to-end check")
class EndToEnd(unittest.TestCase):
    def test_from_raw_refuses_marker_and_nan_but_reads_the_real_packet(self):
        n = len(P.from_raw(REAL, 18000))
        self.assertGreater(n, 0)
        for mutate in ("marker", "nan"):
            with tempfile.TemporaryDirectory() as t:
                d = Path(t) / "pk"; shutil.copytree(REAL, d)
                z = dict(np.load(d / "constructed_arrays.npz"))
                if mutate == "marker":
                    z["per_cell_law_HAZARD_only"] = np.array(True)
                else:
                    z["ignition_time_s"] = z["ignition_time_s"].copy(); z["ignition_time_s"].flat[0] = np.nan
                np.savez(d / "constructed_arrays.npz", **z)
                with self.assertRaises(ValueError):
                    P.from_raw(d, 18000)


if __name__ == "__main__":
    unittest.main()
