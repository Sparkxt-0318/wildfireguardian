"""Clean-clone CLI contract and fail-closed input provenance tests."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
STACK = PACKAGE.parents[1] / "experimental" / "window-routing" / "stack"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepareJobCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet = self.root / "packet"
        self.packet.mkdir()
        self.graph = self.root / "graph.json"
        self.request = self.root / "request.json"
        self.hazard = self.packet / "HAZARD.json"
        self.source = self.packet / "SOURCE.json"
        for path in (self.graph, self.request, self.hazard, self.source):
            path.write_text(json.dumps({"fixture": path.name}))
        baseline = STACK / "routing_candidate" / "baseline"
        phase = STACK / "phaseB"
        self.template = self.root / "template.json"
        self.template.write_text(json.dumps({
            "worker": "/previous/worker.py",
            "actual_worker_sha256": "a" * 64,
            "input_sha256": {
                "graph_path": digest(self.graph),
                "request_path": digest(self.request),
                "hazard_path": digest(self.hazard),
            },
            "source_sha256": {"SOURCE.json": digest(self.source)},
            "checker_sha256": {},
            "phaseB_sha256": {"rda_worker_v1_1.py": digest(phase / "rda_worker_v1_1.py")},
            "core_sha256": digest(baseline / "routing-package" / "routing" / "core.py"),
            "preparation_mode_sha256": digest(phase / "preparation_mode.py"),
        }))
        self.output = self.root / "output"

    def call(self, *extra):
        return subprocess.run(
            [sys.executable, "-B", str(PACKAGE / "prepare_job.py"),
             "--template", str(self.template), "--template-sha256", digest(self.template), "--graph", str(self.graph),
             "--request", str(self.request), "--packet", str(self.packet),
             "--output", str(self.output), *extra],
            capture_output=True, text=True,
        )

    def test_success_rebinds_job_without_starting_worker(self):
        result = self.call()
        self.assertEqual(result.returncode, 0, result.stderr)
        job = json.loads((self.output / "job.json").read_text())
        self.assertEqual(job["graph_path"], str(self.graph.resolve()))
        self.assertEqual(job["source_root"], str(STACK / "routing_candidate"))
        self.assertEqual(job["worker"], str(PACKAGE / "update.py"))
        self.assertEqual(job["actual_worker_sha256"], digest(PACKAGE / "update.py"))
        self.assertEqual(job["rebind_provenance"], {
            "template_sha256": digest(self.template),
            "template_worker": "/previous/worker.py",
            "template_worker_sha256": "a" * 64,
        })
        self.assertEqual(job["preparation_mode"], "COLD_FAST")
        self.assertFalse((self.output / "RESULT.json").exists())

    def test_rejects_template_digest_mismatch(self):
        result = subprocess.run(
            [sys.executable, "-B", str(PACKAGE / "prepare_job.py"),
             "--template", str(self.template), "--template-sha256", "0" * 64,
             "--graph", str(self.graph), "--request", str(self.request),
             "--packet", str(self.packet), "--output", str(self.output)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("checksum", result.stderr.lower())
        self.assertFalse(self.output.exists())

    def test_rejects_mismatched_graph_without_output(self):
        self.graph.write_text('{"changed": true}')
        result = self.call()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Input checksum mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    def test_rejects_mismatched_packet_without_output(self):
        self.source.write_text('{"changed": true}')
        result = self.call()
        self.assertEqual(result.returncode, 2)
        self.assertIn("Packet checksum mismatch", result.stderr)
        self.assertFalse(self.output.exists())

    def test_preexisting_output_is_never_replaced(self):
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_text("retained")
        result = self.call()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(sentinel.read_text(), "retained")

    def test_cache_mode_requires_existing_directory(self):
        result = self.call("--cache", str(self.root / "missing"))
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())
        cache = self.root / "cache"
        cache.mkdir()
        result = self.call("--cache", str(cache))
        self.assertEqual(result.returncode, 0, result.stderr)
        job = json.loads((self.output / "job.json").read_text())
        self.assertEqual(job["preparation_mode"], "AUTHENTICATED_ARTIFACT")


if __name__ == "__main__":
    unittest.main()
