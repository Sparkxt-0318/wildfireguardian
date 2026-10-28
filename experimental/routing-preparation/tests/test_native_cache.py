"""Small, source-bound checks for native-aware owner-local graph reuse.

All graphs are labelled fixtures and all private cache directories are temporary.
This suite does not run regional inputs, searches, or physical-fire checks.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import math
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))
from wfg_routing_experimental import fixture, validation, native_backend, prepared_reuse
from wfg_routing_experimental.prepared_reuse import (ArtifactPreparedStore, LocalPreparedStore,
                                    CacheAuthorityError, source_identity)

@unittest.skipUnless((SRC / 'wfg_routing_experimental' / ('wfg_native_cell' + (__import__('sysconfig').get_config_var('EXT_SUFFIX') or ''))).is_file(), 'build native extension to run native-cache controls')
class CacheIdentityControls(unittest.TestCase):
    def setUp(self):
        self.original = fixture.example()
        self.graph = self.original['graph']
        self.tmp = tempfile.TemporaryDirectory(prefix='cache-control-')
        self.cache = Path(self.tmp.name).resolve() / 'private'

    def tearDown(self):
        self.tmp.cleanup()

    def test_backend_authority_separates_python_and_native(self):
        python_id = source_identity('python')
        native_id = source_identity('native')
        self.assertNotEqual(python_id, native_id)
        p = ArtifactPreparedStore(self.cache, backend='python')
        n = ArtifactPreparedStore(self.cache, backend='native')
        self.assertEqual(p.authority, python_id)
        self.assertEqual(n.authority, native_id)
        self.assertFalse(p.get(self.graph)[1].cache_hit)
        self.assertFalse(n.get(self.graph)[1].cache_hit)
        self.assertTrue(p.get(self.graph)[1].cache_hit)
        restored, receipt = n.get(self.graph)
        self.assertTrue(receipt.cache_hit)
        self.assertTrue(restored.backend_receipt()['admission_reused'])
        self.assertIsNone(restored.backend_receipt()['node_hits'])
        self.assertEqual(restored.snapshot(), self.graph)
        self.assertEqual(len(list(self.cache.glob('*.wfggraph'))), 2)

    def test_full_graph_contents_not_revision_alone(self):
        store = ArtifactPreparedStore(self.cache, backend='native')
        store.get(self.graph)
        altered = copy.deepcopy(self.graph)
        altered['unused_metadata'] = {'changed': True}
        self.assertEqual(altered['revision'], self.graph['revision'])
        changed_graph, receipt = store.get(altered)
        self.assertFalse(receipt.cache_hit)
        self.assertEqual(changed_graph.snapshot(), altered)
        self.assertTrue(store.get(self.graph)[1].cache_hit)

    def test_hazard_and_request_always_revalidated(self):
        store = LocalPreparedStore(backend='native')
        pg, first = store.get(self.graph)
        self.assertFalse(first.cache_hit)
        hazard = copy.deepcopy(self.original['hazard'])
        request = copy.deepcopy(self.original['request'])
        valid_h = validation.validate_hazard(pg.snapshot(), hazard, request['as_of'], _graph_validated=True)
        valid_r = validation.validate_request(pg.snapshot(), valid_h, request, _validated_inputs=True)
        changed_h = copy.deepcopy(hazard)
        changed_h['version'] = 2
        changed_h['members'][0]['flux'][0][0] += 0.5
        changed_r = copy.deepcopy(request)
        changed_r['hazard_version'] = 2
        pg2, second = store.get(self.graph)
        self.assertTrue(second.cache_hit)
        # The local-store API preserves object identity.  Its immutable
        # backend receipt describes initial construction; the separate
        # PreparationReceipt is authoritative for this lookup's cache hit.
        self.assertIs(pg2, pg)
        self.assertFalse(pg.backend_receipt()['admission_reused'])
        valid_h2 = validation.validate_hazard(pg2.snapshot(), changed_h, changed_r['as_of'], _graph_validated=True)
        valid_r2 = validation.validate_request(pg2.snapshot(), valid_h2, changed_r, _validated_inputs=True)
        self.assertNotEqual(valid_h, valid_h2)
        self.assertNotEqual(valid_r, valid_r2)
        with self.assertRaises(validation.ValidationError):
            validation.validate_request(pg2.snapshot(), valid_h2, request, _validated_inputs=True)

    def test_changed_graph_admission_hooks_fail_closed_on_hit(self):
        store = ArtifactPreparedStore(self.cache, backend='native')
        store.get(self.graph)
        with mock.patch.object(validation, 'cell_at', lambda *args: 0):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)
        with mock.patch.dict(copy._deepcopy_dispatch, {list: lambda value, memo: value}):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)
        self.assertTrue(store.get(self.graph)[1].cache_hit)

    def test_tampered_artifact_does_not_silent_rebuild(self):
        store = ArtifactPreparedStore(self.cache, backend='native')
        store.get(self.graph)
        path = store.artifact_path(self.graph)
        content = bytearray(path.read_bytes()); content[-1] ^= 1
        path.write_bytes(content)
        with self.assertRaises(CacheAuthorityError):
            store.get(self.graph)
        self.assertEqual(path.read_bytes(), content)

    def test_tampered_or_removed_key_invalidates_live_store(self):
        store = ArtifactPreparedStore(self.cache, backend='native')
        store.get(self.graph)
        key = self.cache / 'authority.key'
        original = key.read_bytes()
        key.write_bytes(b'X' * len(original))
        with self.assertRaises(CacheAuthorityError):
            store.get(self.graph)
        key.unlink()
        with self.assertRaises(CacheAuthorityError):
            store.get(self.graph)

    def test_changing_runtime_identity_invalidates_existing_store(self):
        store = LocalPreparedStore(backend='native')
        store.get(self.graph)
        original = native_backend.backend_identity
        def altered(mode=None):
            info = dict(original(mode)); info['soabi'] = str(info['soabi']) + '-changed'
            return info
        with mock.patch.object(native_backend, 'backend_identity', altered):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)

    def test_actual_abi_and_machine_changes_invalidate_store(self):
        store = LocalPreparedStore(backend='native')
        store.get(self.graph)
        original = native_backend.sysconfig.get_config_var
        def altered(name):
            return str(original(name)) + '-changed' if name == 'SOABI' else original(name)
        with mock.patch.object(native_backend.sysconfig, 'get_config_var', altered):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)
        with mock.patch.object(native_backend.platform, 'machine', return_value='different-cpu'):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)

    def test_mid_build_identity_change_prevents_artifact_publication(self):
        store = ArtifactPreparedStore(self.cache, backend='native')
        original = prepared_reuse.source_identity
        calls = 0
        def changed(mode=None):
            nonlocal calls
            calls += 1
            value = original(mode)
            return value if calls == 1 else '0' * 64
        with mock.patch.object(prepared_reuse, 'source_identity', changed):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)
        self.assertEqual(list(self.cache.glob('*.wfggraph')), [])

    def test_replacing_loaded_native_function_fails_closed(self):
        store = LocalPreparedStore(backend='native')
        store.get(self.graph)
        module = sys.modules['wfg_routing_experimental.wfg_native_cell']
        with mock.patch.object(module, 'cell_at', math.floor):
            with self.assertRaises(CacheAuthorityError):
                store.get(self.graph)

    def test_expected_source_pin_mismatch(self):
        with self.assertRaises(CacheAuthorityError):
            ArtifactPreparedStore(self.cache, backend='native', expected_source_sha256='0' * 64)

    def test_spoofed_native_preload_rejected(self):
        script = r'''
import sys, math, types, importlib.util
from pathlib import Path
sys.path.insert(0, sys.argv[1]); import wfg_routing_experimental
name='wfg_routing_experimental.wfg_native_cell'; spec=importlib.util.find_spec(name)
assert spec and spec.origin
fake=types.ModuleType(name); fake.__file__=spec.origin; fake.__spec__=spec
fake.cell_at=math.floor; fake.same_cell=math.ceil; sys.modules[name]=fake
from wfg_routing_experimental.prepared_reuse import ArtifactPreparedStore, CacheAuthorityError
try: ArtifactPreparedStore(sys.argv[2], backend='native')
except CacheAuthorityError: pass
else: raise AssertionError('fake native module was accepted')
assert not Path(sys.argv[2]).exists(), 'untrusted native created a cache root'
'''
        process = subprocess.run([sys.executable, '-B', '-c', script,
                                  str(SRC), str(self.cache)],
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

    def test_native_artifact_reused_across_fresh_processes(self):
        script = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from wfg_routing_experimental import fixture
from wfg_routing_experimental.prepared_reuse import ArtifactPreparedStore
mode=sys.argv[3]; s=ArtifactPreparedStore(sys.argv[2], backend=mode)
g=fixture.example()['graph']; pg, receipt=s.get(g)
assert pg.snapshot()==g
print(json.dumps({'hit':receipt.cache_hit,'source':s.authority,
                  'backend':pg.backend_receipt()['identity']['effective_mode'],
                  'reused':pg.backend_receipt()['admission_reused']}))
'''
        rows=[]
        for mode in ('native','native','python','python'):
            process=subprocess.run([sys.executable,'-B','-c',script,str(SRC),
                                    str(self.cache),mode],capture_output=True,text=True,timeout=20)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            rows.append(json.loads(process.stdout))
        self.assertEqual([row['hit'] for row in rows],[False,True,False,True])
        self.assertEqual([row['reused'] for row in rows],[False,True,False,True])
        self.assertEqual([row['backend'] for row in rows],['native','native','python','python'])
        self.assertNotEqual(rows[0]['source'],rows[2]['source'])

    def test_real_native_file_changes_and_missing_extension_fail_closed(self):
        clone = Path(self.tmp.name) / 'clone'
        shutil.copytree(SRC / 'wfg_routing_experimental', clone / 'wfg_routing_experimental',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        script = r'''
import os, sys, sysconfig
from pathlib import Path
sys.path.insert(0, sys.argv[1]); mutation=sys.argv[2]
from wfg_routing_experimental import fixture, native_backend
from wfg_routing_experimental.prepared_reuse import LocalPreparedStore, CacheAuthorityError, source_identity
root=Path(sys.argv[1])/'wfg_routing_experimental'; ext=root/('wfg_native_cell'+sysconfig.get_config_var('EXT_SUFFIX'))
if mutation=='missing':
    ext.unlink()
    assert source_identity('python')
    try: source_identity('native')
    except CacheAuthorityError: pass
    else: raise AssertionError('missing native extension was accepted')
    raise SystemExit(0)
store=LocalPreparedStore(backend='native'); graph=fixture.example()['graph']; store.get(graph)
if mutation=='source':
    with (root/'native_cell.c').open('ab') as f: f.write(b'\n/* changed source */\n')
elif mutation=='binary':
    # Replace the directory entry, leaving the already-loaded mapped inode
    # intact, so we test a changed binary without corrupting the process image.
    replacement=ext.with_suffix(ext.suffix+'.replacement')
    replacement.write_bytes(ext.read_bytes()+b'changed'); os.replace(replacement,ext)
else: raise AssertionError(mutation)
try: store.get(graph)
except CacheAuthorityError: pass
else: raise AssertionError('changed native '+mutation+' was accepted')
'''
        # Each mutation gets an independent package copy and subprocess.
        for mutation in ('source', 'binary', 'missing'):
            if mutation != 'source':
                shutil.rmtree(clone / 'wfg_routing_experimental')
                shutil.copytree(SRC / 'wfg_routing_experimental', clone / 'wfg_routing_experimental',
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            process = subprocess.run([sys.executable, '-B', '-c', script, str(clone), mutation],
                                     capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 0, mutation + ': ' + process.stdout + process.stderr)

    def test_concurrent_same_graph_and_two_backends(self):
        stores = {'python': ArtifactPreparedStore(self.cache, backend='python'),
                  'native': ArtifactPreparedStore(self.cache, backend='native')}
        barrier = threading.Barrier(8)
        def call(i):
            mode = 'native' if i % 2 else 'python'
            barrier.wait(timeout=10)
            pg, receipt = stores[mode].get(self.graph)
            return mode, pg.fingerprint, receipt.cache_hit, pg.snapshot()
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(call, range(8)))
        self.assertEqual(len({row[1] for row in records}), 1)
        self.assertTrue(all(row[3] == self.graph for row in records))
        for mode in ('python', 'native'):
            hits = [row[2] for row in records if row[0] == mode]
            self.assertEqual(hits.count(False), 1)
            self.assertEqual(hits.count(True), 3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
