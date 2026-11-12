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

REAL = os.environ.get("WFG_REAL_PACKET")  # a real ROUTABLE packet dir (not a HAZARD-only one, which from_raw refuses by design); argv is not used


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


class PacketDir(unittest.TestCase):
    def test_failed_or_unfinished_write_refused(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            with self.assertRaises(ValueError):
                P.require_complete_packet_dir(d)                       # no BUILD_SUMMARY.json
            (d / "BUILD_SUMMARY.json").write_text("{}")
            P.require_complete_packet_dir(d)                           # complete
            (d / "SUPPORT_WRITE_FAILED").write_text("")
            with self.assertRaises(ValueError):
                P.require_complete_packet_dir(d)                       # failed support write


@unittest.skipUnless(REAL, "set WFG_REAL_PACKET to a real routable (non-HAZARD-only) packet directory to run the end-to-end check")
class Support(unittest.TestCase):
    """CERTIFICATE_SPEC 5.3 via require_full_support (F-9.3 masked packets differ only in `support`)."""
    def _check(self, **arrs):
        a, d = npz(**arrs)
        try:
            P.require_full_support(a, "pk")
        finally:
            a.close(); shutil.rmtree(d)

    def test_full_support_accepted(self):
        self._check(support=np.ones((2, 3, 3), dtype=bool))

    def test_one_unsupported_cell_refused(self):
        s = np.ones((2, 3, 3), dtype=bool); s[1, 2, 0] = False
        with self.assertRaises(ValueError):
            self._check(support=s)

    def test_missing_support_refused(self):
        with self.assertRaises(ValueError):
            self._check(ignition_time_s=np.zeros((1, 2, 2)))

    def test_non_boolean_support_refused(self):
        with self.assertRaises(ValueError):
            self._check(support=np.ones((3, 3), dtype=np.uint8))


MASKED = os.environ.get("WFG_MASKED_PACKET")      # an F-9.3 support-masked packet dir (e.g. c651_unknown/1)


@unittest.skipUnless(MASKED, "set WFG_MASKED_PACKET to an F-9.3 masked packet to run the masked-packet check")
class MaskedPacket(unittest.TestCase):
    def test_wrapper_refuses_masked_packet_but_opt_out_reads_it(self):
        with self.assertRaises(ValueError):
            P.routable_contact_model(MASKED)
        self.assertGreater(len(P.routable_contact_model(MASKED, allow_unsupported=True).cell_intervals), 0)


class EndToEnd(unittest.TestCase):
    def test_from_raw_refuses_marker_and_nan_but_reads_the_real_packet(self):
        n = len(P.from_raw(REAL, 18000))
        self.assertGreater(n, 0)
        for mutate in ("marker", "nan", "failed_write", "no_summary"):
            with tempfile.TemporaryDirectory() as t:
                d = Path(t) / "pk"; shutil.copytree(REAL, d)
                z = dict(np.load(d / "constructed_arrays.npz"))
                if mutate == "failed_write":
                    (d / "SUPPORT_WRITE_FAILED").write_text("")
                elif mutate == "no_summary":
                    (d / "BUILD_SUMMARY.json").unlink()
                elif mutate == "marker":
                    z["per_cell_law_HAZARD_only"] = np.array(True)
                else:
                    z["ignition_time_s"] = z["ignition_time_s"].copy(); z["ignition_time_s"].flat[0] = np.nan
                np.savez(d / "constructed_arrays.npz", **z)
                with self.assertRaises(ValueError):
                    P.from_raw(d, 18000)
                with self.assertRaises(ValueError):
                    P.routable_contact_model(d)
                if mutate == "marker":
                    # Mira: ContactModel itself does not read the marker (contact.py is hash-pinned); the wrapper must
                    from wfg_scenario_members.contact import ContactModel
                    self.assertGreater(len(ContactModel.from_packet(d).cell_intervals), 0)


if __name__ == "__main__":
    unittest.main()
