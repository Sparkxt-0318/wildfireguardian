"""Step 2 amendment F (STEP2_ACCEPTANCE F1/F3 with Mira's R1-R7), the controller's PSS guard, tests written before the
panel. The overlay controller (stack-v2/runner/wfg_controller.py) is loaded by path.

M3(a) (R4 revised): a family whose PARENT holds a touched 1 GiB array and whose forked CHILD shares it (as a worker and
      its forked check): the family RSS sum exceeds a 1,536 MiB guard, the family PSS does not.
M3(b) the child also allocates its own 1 GiB: the family PSS exceeds the 1,536 MiB guard.
R3    sampling-error rules: a vanished pid is skipped and counted; an unreadable LIVE pid makes the whole sample RSS
      (pss None); no smaps_rollup -> RSS for every sample (pss None); never a mixed sample.
"""
import importlib.util, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
spec = importlib.util.spec_from_file_location('v2_wfg_controller', V2 / 'stack-v2/runner/wfg_controller.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
MiB = 2 ** 20
GUARD = 1536 * MiB

FAMILY = r'''
import os, sys, time, numpy as np
own = sys.argv[1] == 'own'
big = np.ones(1024 * 2**20 // 8)                  # parent: 1 GiB, every page touched
pid = os.fork()
if pid == 0:
    s = float(big.sum())                           # child: reads (maps) the shared pages
    if own:
        mine = np.ones(1024 * 2**20 // 8); mine.sum()   # child: its own 1 GiB
    open(sys.argv[2], 'w').write('ready')
    time.sleep(60); os._exit(0)
time.sleep(60)
'''


@unittest.skipUnless(C.SMAPS_ROLLUP, 'no /proc/self/smaps_rollup on this host')
class FamilyPss(unittest.TestCase):
    def family(self, own):
        d = Path(tempfile.mkdtemp()); flag = d / 'ready'
        p = subprocess.Popen([sys.executable, '-c', FAMILY, 'own' if own else 'shared', str(flag)], start_new_session=True)
        t0 = time.time()
        while not flag.exists() and time.time() - t0 < 60:
            time.sleep(0.1)
        time.sleep(0.5)
        try:
            rss, pss, vanished = C.family_mem(p.pid, {})
            return rss, pss, vanished
        finally:
            os.killpg(p.pid, signal.SIGKILL); p.wait()

    def test_M3a_shared_parent_pages_do_not_trip_pss_guard(self):
        rss, pss, v = self.family(own=False)
        self.assertGreater(rss, GUARD, (rss / MiB, pss / MiB))          # the RSS sum counts the shared GiB twice
        self.assertIsNotNone(pss); self.assertLess(pss, GUARD, (rss / MiB, pss / MiB))
        self.assertGreater(pss, 900 * MiB)                               # but the GiB is counted once

    def test_M3b_child_own_allocation_trips_pss_guard(self):
        rss, pss, v = self.family(own=True)
        self.assertIsNotNone(pss); self.assertGreater(pss, GUARD, (rss / MiB, pss / MiB))


class SamplingErrors(unittest.TestCase):
    def setUp(self):
        self.real = C._pss_kib; self.real_sm = C.SMAPS_ROLLUP
        self.p = subprocess.Popen([sys.executable, '-c', 'import os,time\nif os.fork()==0: time.sleep(30)\nelse: time.sleep(30)'],
                                  start_new_session=True)
        time.sleep(0.5)

    def tearDown(self):
        C._pss_kib = self.real; C.SMAPS_ROLLUP = self.real_sm
        os.killpg(self.p.pid, signal.SIGKILL); self.p.wait()

    def test_vanished_pid_is_skipped_and_counted(self):
        first = {}
        def fake(pid):
            if not first:
                first['pid'] = pid; raise FileNotFoundError(pid)
            return self.real(pid)
        C._pss_kib = fake; C.SMAPS_ROLLUP = True
        rss, pss, vanished = C.family_mem(self.p.pid, {})
        self.assertEqual(vanished, 1); self.assertIsNotNone(pss)

    def test_unreadable_live_pid_makes_whole_sample_rss(self):
        def fake(pid):
            raise PermissionError(pid)
        C._pss_kib = fake; C.SMAPS_ROLLUP = True
        rss, pss, vanished = C.family_mem(self.p.pid, {})
        self.assertIsNone(pss); self.assertGreater(rss, 0)

    def test_no_smaps_rollup_means_rss_every_sample(self):
        C.SMAPS_ROLLUP = False
        rss, pss, vanished = C.family_mem(self.p.pid, {})
        self.assertIsNone(pss); self.assertGreater(rss, 0); self.assertEqual(vanished, 0)

    def test_receipt_fields_named_in_source(self):
        src = (V2 / 'stack-v2/runner/wfg_controller.py').read_text()
        for k in ("'guard_measure'", "'rss_fallback_no_smaps_rollup'", "'sampled_family_peak_pss_bytes'", "'pss_samples'",
                  "'pss_fallback_samples'", "'pss_vanished_pids'"):
            self.assertIn(k, src)


if __name__ == '__main__':
    unittest.main()
