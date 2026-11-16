"""Test process-family guard, deadlines, and fail-closed publication controls."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import run_guarded
from run_guarded import supervise


class GuardBehavior(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.out = Path(temp.name)

    def run_worker(self, script, **limits):
        return supervise([sys.executable, "-c", script, str(self.out)], self.out,
                         os.environ.copy(), **limits)

    def test_normal_completion_and_result(self):
        receipt = self.run_worker(
            "import pathlib,sys,time; time.sleep(0.2); "
            "(pathlib.Path(sys.argv[1])/'RESULT.json').write_text('{}')",
            wall_s=5, rss_mib=512,
        )
        self.assertTrue(receipt["accepted_execution"], receipt)
        self.assertEqual(receipt["cleanup"]["status"], "CLEAN")
        self.assertGreater(receipt["samples"], 0)
        self.assertTrue((self.out / "rss_samples.json").exists())

    def test_missing_result_is_not_accepted(self):
        receipt = self.run_worker("import time; time.sleep(0.2)", wall_s=5, rss_mib=512)
        self.assertFalse(receipt["accepted_execution"])
        self.assertEqual(receipt["cause"], "MISSING_RESULT")

    def test_deadline_stops_child_and_process_group(self):
        script = (
            "import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); "
            "open(sys.argv[1]+'/child.pid','w').write(str(child.pid)); "
            "time.sleep(20)"
        )
        receipt = self.run_worker(script, wall_s=0.5, rss_mib=512)
        self.assertFalse(receipt["accepted_execution"])
        self.assertEqual(receipt["cause"], "DEADLINE")
        self.assertEqual(receipt["cleanup"]["status"], "CLEAN")
        self.assertGreaterEqual(max(len(s["pids"]) for s in receipt["cleanup"]["census"]), 1)

    def test_changed_job_never_accepted(self):
        job = self.out / "job.json"
        job.write_text('{"original": true}')
        before = hashlib.sha256(job.read_bytes()).hexdigest()
        script = (
            "import pathlib,sys,time; time.sleep(0.2); root=pathlib.Path(sys.argv[1]); "
            "(root/'job.json').write_text('changed'); (root/'RESULT.json').write_text('{}')"
        )
        receipt = self.run_worker(script, wall_s=5, rss_mib=512,
                                  bound_job=job, job_sha256=before)
        self.assertFalse(receipt["accepted_execution"])
        self.assertEqual(receipt["cause"], "JOB_CHANGED_DURING_EXECUTION")

    def test_changed_worker_never_accepted(self):
        worker = self.out / "worker.py"
        worker.write_text("original")
        before = hashlib.sha256(worker.read_bytes()).hexdigest()
        script = (
            "import pathlib,sys,time; time.sleep(0.2); root=pathlib.Path(sys.argv[1]); "
            "(root/'worker.py').write_text('changed'); (root/'RESULT.json').write_text('{}')"
        )
        receipt = self.run_worker(script, wall_s=5, rss_mib=512,
                                  bound_worker=worker, worker_sha256=before)
        self.assertFalse(receipt["accepted_execution"])
        self.assertEqual(receipt["cause"], "WORKER_CHANGED_DURING_EXECUTION")

    def test_unavailable_worker_never_accepted(self):
        worker = self.out / "worker.py"
        worker.write_text("original")
        before = hashlib.sha256(worker.read_bytes()).hexdigest()
        script = (
            "import pathlib,sys,time; time.sleep(0.2); root=pathlib.Path(sys.argv[1]); "
            "(root/'worker.py').unlink(); (root/'RESULT.json').write_text('{}')"
        )
        receipt = self.run_worker(script, wall_s=5, rss_mib=512,
                                  bound_worker=worker, worker_sha256=before)
        self.assertFalse(receipt["accepted_execution"])
        self.assertEqual(receipt["cause"], "WORKER_UNAVAILABLE_AFTER_EXECUTION")

    def test_run_validates_worker_identity_before_start(self):
        worker = self.out / "update.py"
        worker.write_text("original")
        before = hashlib.sha256(worker.read_bytes()).hexdigest()
        job = self.out / "job.json"
        content = {
            "output_path": str(self.out), "complete_budget_s": 30,
            "memory_guard_mib": 3072, "preparation_mode": "COLD_FAST",
            "worker": str(worker), "actual_worker_sha256": before,
        }
        with patch.object(run_guarded, "HERE", self.out), patch.object(run_guarded, "supervise") as mocked:
            job.write_text(json.dumps(content))
            mocked.return_value = {"accepted_execution": True}
            self.assertTrue(run_guarded.run(job)["accepted_execution"])
            self.assertEqual(mocked.call_args.kwargs["bound_worker"], worker.resolve())
            self.assertEqual(mocked.call_args.kwargs["worker_sha256"], before)
            mocked.reset_mock()
            content["actual_worker_sha256"] = "0" * 64
            job.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                run_guarded.run(job)
            mocked.assert_not_called()
            content["actual_worker_sha256"] = before
            other = self.out / "other_worker.py"
            other.write_text("original")
            content["worker"] = str(other)
            job.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "does not match"):
                run_guarded.run(job)
            mocked.assert_not_called()

    def test_run_rejects_job_change_during_loading(self):
        worker = self.out / "update.py"
        worker.write_text("original")
        job = self.out / "job.json"
        content = {
            "output_path": str(self.out), "complete_budget_s": 30,
            "memory_guard_mib": 3072, "preparation_mode": "COLD_FAST",
            "worker": str(worker),
            "actual_worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        }
        job.write_text(json.dumps(content))

        def change_during_read(path):
            path.write_text(json.dumps({**content, "preparation_mode": "changed"}))
            return content

        with patch.object(run_guarded, "HERE", self.out), \
             patch.object(run_guarded, "read", side_effect=change_during_read), \
             patch.object(run_guarded, "supervise") as mocked:
            with self.assertRaisesRegex(ValueError, "changed during loading"):
                run_guarded.run(job)
            mocked.assert_not_called()

    def test_process_family_memory_limit(self):
        script = (
            "import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c',"
            "'import time; data=bytearray(100*1024*1024); time.sleep(20)']); "
            "open(sys.argv[1]+'/child.pid','w').write(str(child.pid)); "
            "time.sleep(20)"
        )
        receipt = self.run_worker(script, wall_s=8, rss_mib=60)
        self.assertFalse(receipt["accepted_execution"], receipt)
        self.assertEqual(receipt["cause"], "MEMORY", receipt)
        self.assertEqual(receipt["cleanup"]["status"], "CLEAN")
        self.assertGreater(receipt["sampled_peak_mib"], 60)


if __name__ == "__main__":
    unittest.main()
