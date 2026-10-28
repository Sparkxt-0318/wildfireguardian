"""Synthetic fixture checks; they do not establish real-world fire safety."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))
from wfg_routing_experimental import fixture
from wfg_routing_experimental.core import solve
from wfg_routing_experimental.prepared_reuse import (
    ArtifactPreparedStore, LocalPreparedStore, CacheAuthorityError,
)


class PythonCacheControls(unittest.TestCase):
    def setUp(self):
        self.data = fixture.example()
        self.tmp = tempfile.TemporaryDirectory(prefix='wfg-cache-test-')
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_reuse_rechecks_new_hazard_and_request(self):
        store = LocalPreparedStore(backend='python')
        prepared, first = store.get(self.data['graph'])
        self.assertFalse(first.cache_hit)
        first_route = solve(prepared, self.data['hazard'], self.data['request'])
        self.assertEqual((first_route['status'], first_route['arrival']),
                         ('CONDITIONAL_OPTIMUM', 4.0))
        hazard = copy.deepcopy(self.data['hazard'])
        hazard['version'] = 2
        hazard['members'][0]['flame'][0] = [True] * len(hazard['members'][0]['flame'][0])
        request = copy.deepcopy(self.data['request'])
        request['hazard_version'] = 2
        again, receipt = store.get(self.data['graph'])
        self.assertTrue(receipt.cache_hit)
        self.assertIs(again, prepared)
        blocked = solve(again, hazard, request)
        self.assertEqual(blocked['status'], 'AT_ISSUE_FAILURE')
        stale = solve(again, hazard, self.data['request'])
        self.assertEqual((stale['status'], stale['reason']), ('INVALID_INPUT', 'HAZARD_VERSION'))

    def test_same_revision_graph_mutation_is_a_miss(self):
        store = ArtifactPreparedStore(self.root / 'private', backend='python')
        graph = self.data['graph']
        original, first = store.get(graph)
        self.assertFalse(first.cache_hit)
        changed = copy.deepcopy(graph)
        changed['unused_metadata'] = {'revision_was_not_changed': True}
        updated, receipt = store.get(changed)
        self.assertFalse(receipt.cache_hit)
        self.assertNotEqual(updated.fingerprint, original.fingerprint)
        self.assertTrue(store.get(graph)[1].cache_hit)

    def test_corrupt_artifact_and_changed_key_fail_closed(self):
        for kind in ('artifact', 'key'):
            with self.subTest(kind=kind):
                root = self.root / kind
                store = ArtifactPreparedStore(root, backend='python')
                store.get(self.data['graph'])
                path = store.artifact_path(self.data['graph']) if kind == 'artifact' else root / 'authority.key'
                contents = bytearray(path.read_bytes())
                contents[-1] ^= 1
                path.write_bytes(contents)
                with self.assertRaises(CacheAuthorityError):
                    store.get(self.data['graph'])

    def test_parallel_python_store_preserves_single_admission(self):
        store = ArtifactPreparedStore(self.root / 'parallel', backend='python')
        barrier = threading.Barrier(8)
        def get_one(_):
            barrier.wait(timeout=10)
            graph, receipt = store.get(self.data['graph'])
            return graph.snapshot(), receipt.cache_hit
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(get_one, range(8)))
        self.assertEqual([hit for _, hit in rows].count(False), 1)
        self.assertEqual([hit for _, hit in rows].count(True), 7)
        self.assertTrue(all(snapshot == self.data['graph'] for snapshot, _ in rows))

    def test_symlinked_cache_parent_is_rejected(self):
        target = self.root / 'actual'
        target.mkdir()
        alias = self.root / 'alias'
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(CacheAuthorityError, 'CACHE_DIRECTORY_SYMLINK'):
            ArtifactPreparedStore(alias / 'private', backend='python')

    def test_experimental_import_does_not_shadow_existing_routing(self):
        script = """
import sys, types
existing = types.ModuleType('routing')
sys.modules['routing'] = existing
import wfg_routing_experimental.prepared_reuse
import wfg_routing_experimental.core
assert sys.modules['routing'] is existing
"""
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(SRC),
                   WFG_GRAPH_BACKEND='python')
        completed = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_native_extension_present_when_explicitly_required(self):
        if os.environ.get('WFG_TEST_REQUIRE_NATIVE') == '1':
            from wfg_routing_experimental.native_backend import backend_identity
            self.assertEqual(backend_identity('native')['effective_mode'], 'native')

    def test_unbuilt_extension_has_explicit_python_fallback(self):
        clone = self.root / 'copy'
        shutil.copytree(SRC / 'wfg_routing_experimental', clone / 'wfg_routing_experimental',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.so', '*.pyd', '*.dylib'))
        script = '''
from wfg_routing_experimental.fixture import example
from wfg_routing_experimental.prepared import PreparedGraph
from wfg_routing_experimental.native_backend import NativeBackendError
assert PreparedGraph(example()['graph'], backend='python').backend_receipt()['identity']['effective_mode'] == 'python'
try:
    PreparedGraph(example()['graph'], backend='native')
except NativeBackendError:
    pass
else:
    raise AssertionError('explicit native request silently succeeded without an extension')
'''
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(clone),
                   WFG_GRAPH_BACKEND='python')
        completed = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
