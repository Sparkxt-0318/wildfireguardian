"""Step 2 amendment F (STEP2_ACCEPTANCE F1/F3 with Mira's R1-R7), the controller's PSS guard, tests written before the
panel. The overlay controller (stack-v2/runner/wfg_controller.py) is loaded by path.

M3(a) (R4 revised): a family whose PARENT holds a touched 1 GiB array and whose forked CHILD shares it (as a worker and
      its forked check): the family RSS sum exceeds a 1,536 MiB guard, the family PSS does not.
M3(b) the child also allocates its own 1 GiB: the family PSS exceeds the 1,536 MiB guard.
N3    (Mira 122) controller level: run_attempt with a 1,536 MiB guard on the same two families as a worker; the shared
      family does not trip, the own-allocation family trips, and the receipt's PSS counts are checked.
N2    (Mira 122) the harness sampler (tools/harness_mem.py): vanished pids counted; a sample with a live unreadable pid
      is not measured (counted, excluded from peaks).
R3    sampling-error rules: a vanished pid is skipped and counted; an unreadable LIVE pid makes the whole sample RSS
      (pss None); no smaps_rollup -> RSS for every sample (pss None); never a mixed sample.
"""
import importlib.util, json, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
spec = importlib.util.spec_from_file_location('v2_wfg_controller', V2 / 'stack-v2/runner/wfg_controller.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
hspec = importlib.util.spec_from_file_location('v2_harness_mem', V2 / 'tools/harness_mem.py')
HM = importlib.util.module_from_spec(hspec); hspec.loader.exec_module(HM)
import threading  # noqa: E402
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


WORKER = r'''
import json, os, sys, time, numpy as np
job = json.load(open(sys.argv[sys.argv.index('--job-file') + 1]))
own = job['mode'] == 'own'
big = np.ones(1024 * 2**20 // 8)                  # the worker: 1 GiB, every page touched
pid = os.fork()
if pid == 0:
    s = float(big.sum())                           # the forked check: maps the shared pages
    if own:
        mine = np.ones(1024 * 2**20 // 8); mine.sum()   # its own 1 GiB
    time.sleep(4); os._exit(0)
os.waitpid(pid, 0); sys.exit(0)
'''


@unittest.skipUnless(C.SMAPS_ROLLUP, 'no /proc/self/smaps_rollup on this host')
@unittest.skipUnless(os.path.exists('/usr/bin/time'), 'controller needs /usr/bin/time')
class ControllerGuard(unittest.TestCase):
    """Mira 122 N3: the controller loop itself, not family_mem alone."""
    def attempt(self, mode):
        root = Path(tempfile.mkdtemp()); (root / 'w.py').write_text(WORKER)
        job = {'label': 'n3_' + mode, 'case_id': 'n3', 'arm': 'TEST', 'output_path': 'out/' + mode, 'worker': 'w.py',
               'complete_budget_s': 40, 'memory_guard_mib': GUARD // MiB, 'mode': mode}
        rec = C.run_attempt(root, job, sys.executable, {'test': True})
        self.assertEqual(json.loads((root / 'out' / mode / 'COMPLETE_PROCESS_RECEIPT.json').read_text())['job_id'], job['label'])
        return rec

    def counts(self, rec):
        self.assertEqual(rec['guard_measure'], 'family_pss')
        self.assertGreater(rec['pss_samples'], 0)
        self.assertEqual(rec['pss_fallback_samples'], 0)
        self.assertEqual(rec['rss_sample_errors'], 0)
        self.assertGreaterEqual(rec['pss_vanished_pids'], 0)
        self.assertEqual(rec['cleanup_state'], 'CLEAN')

    def test_N3_shared_family_does_not_trip(self):
        rec = self.attempt('shared')
        self.counts(rec)
        self.assertFalse(rec['memory_guard_triggered'], rec)
        self.assertGreater(rec['sampled_family_peak_rss_bytes'], GUARD)          # RSS alone would have tripped
        self.assertLess(rec['sampled_family_peak_pss_bytes'], GUARD)
        self.assertGreater(rec['sampled_family_peak_pss_bytes'], 900 * MiB)
        self.assertEqual(rec['exit_code'], 0)

    def test_N3_own_allocation_trips(self):
        rec = self.attempt('own')
        self.counts(rec)
        self.assertTrue(rec['memory_guard_triggered'], rec)
        self.assertGreater(rec['sampled_family_peak_pss_bytes'], GUARD)
        self.assertNotEqual(rec['exit_code'], 0)


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


@unittest.skipUnless(C.SMAPS_ROLLUP, 'no /proc/self/smaps_rollup on this host')
class HarnessSampler(unittest.TestCase):
    """Mira 122 N2: the harness sampler is the reference for M1 and M3(d); it must never lower a peak unseen."""
    def setUp(self):
        self.real = HM.rollup
        for k in HM.MEM:
            HM.MEM[k] = 0
        HM.STOP[0] = False
        self.p = subprocess.Popen([sys.executable, '-c', 'import time; b = bytearray(64 * 2**20); time.sleep(30)'])
        time.sleep(0.5)

    def tearDown(self):
        HM.rollup = self.real; HM.STOP[0] = True
        self.p.kill(); self.p.wait()

    def run_sampler(self, s=0.4):
        th = threading.Thread(target=HM.sample, args=(os.getpid(),), daemon=True); th.start()
        time.sleep(s); HM.STOP[0] = True; th.join(2)

    def test_N2_measured(self):
        self.run_sampler()
        self.assertGreater(HM.MEM['measured_samples'], 0); self.assertEqual(HM.MEM['unmeasured_samples'], 0)
        self.assertGreater(HM.MEM['pss_peak'], 50 * MiB)

    def test_N2_vanished_pid_is_counted(self):
        HM.rollup = lambda pid: None
        self.run_sampler()
        self.assertGreater(HM.MEM['vanished_pids'], 0); self.assertEqual(HM.MEM['unmeasured_samples'], 0)
        self.assertEqual(HM.MEM['pss_peak'], 0)

    def test_N2_live_unreadable_sample_is_not_measured(self):
        def fake(pid):
            raise HM.Unreadable(pid)
        HM.rollup = fake
        self.run_sampler()
        self.assertGreater(HM.MEM['unmeasured_samples'], 0); self.assertEqual(HM.MEM['measured_samples'], 0)
        self.assertEqual(HM.MEM['pss_peak'], 0); self.assertEqual(HM.MEM['rss_peak'], 0)

    def test_N2_real_rollup_unreadable_live_pid_raises(self):
        real_open = open
        def deny(path, *a, **k):
            if str(path).endswith('smaps_rollup'):
                raise PermissionError(path)
            return real_open(path, *a, **k)
        import builtins
        builtins.open = deny
        try:
            with self.assertRaises(HM.Unreadable):
                self.real(self.p.pid)
        finally:
            builtins.open = real_open
        self.assertIsNone(self.real(2 ** 22 + 12345))                  # a pid that does not exist: vanished


if __name__ == '__main__':
    unittest.main()
