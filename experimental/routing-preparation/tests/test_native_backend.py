"""Independent small-fixture differential and mixed-thread backend controls."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'src'
sys.path.insert(0, str(SRC))
from wfg_routing_experimental import admission_geometry, validation
from wfg_routing_experimental.fixture import example
from wfg_routing_experimental.prepared import PreparedGraph
from wfg_routing_experimental.native_backend import NativeBackendError, backend_identity, resolve_mode


def graph_with_same_cell():
    graph = example()['graph']
    origin = graph['nodes'][0]
    node = {'id': 'inside', 'x': 6.0, 'y': 6.0, 'waitable': False}
    graph['nodes'].append(node)
    for eid, u, v, reverse in [('inside_out', origin, node, 'inside_back'),
                                ('inside_back', node, origin, 'inside_out')]:
        graph['edges'].append({'id': eid, 'u': u['id'], 'v': v['id'],
            'travel_ticks': 1, 'reverse_edge': reverse,
            'segments': validation.chord_segments(graph['grid'], u, v)})
    return graph


def result(fn, *args, **kwargs):
    try:
        out = fn(*args, **kwargs)
        return ('ok', out.fingerprint, out.snapshot()) if isinstance(out, PreparedGraph) else ('ok', out)
    except BaseException as exc:
        return ('error', type(exc).__name__, getattr(exc, 'code', None), str(exc))


@unittest.skipUnless((SRC / 'wfg_routing_experimental' / ('wfg_native_cell' + (__import__('sysconfig').get_config_var('EXT_SUFFIX') or ''))).is_file(), 'build native extension to run native-backend controls')
class TestBackend(unittest.TestCase):
    def test_identity_and_owned_receipt(self):
        graph = graph_with_same_cell()
        native = PreparedGraph(graph, backend='native')
        python = PreparedGraph(graph, backend='python')
        self.assertEqual(native.snapshot(), python.snapshot())
        self.assertEqual(native.fingerprint, python.fingerprint)
        receipt = native.backend_receipt()
        self.assertEqual(receipt['identity'], backend_identity('native'))
        self.assertGreater(receipt['node_hits'], 0)
        self.assertGreater(receipt['chord_hits'], 0)
        self.assertNotEqual(receipt['identity'], python.backend_receipt()['identity'])
        receipt['identity']['effective_mode'] = 'mutated'
        self.assertEqual(native.backend_receipt()['identity']['effective_mode'], 'native')
        original = native.snapshot()
        graph['nodes'][0]['x'] += 100
        snapshot = native.snapshot(); snapshot['nodes'].clear()
        self.assertEqual(native.snapshot(), original)

    def test_mixed_threads_have_no_shared_hooks(self):
        graph = graph_with_same_cell()
        original_cell = validation.cell_at
        original_factory = admission_geometry.make_variants
        expected = result(PreparedGraph, graph, backend='python')
        def task(i):
            mode = 'native' if i % 2 else 'python'
            obj = PreparedGraph(copy.deepcopy(graph), backend=mode)
            self.assertEqual(('ok', obj.fingerprint, obj.snapshot()), expected)
            receipt = obj.backend_receipt()
            self.assertEqual(receipt['identity']['effective_mode'], mode)
            if mode == 'native': self.assertGreater(receipt['chord_hits'], 0)
            else: self.assertEqual(receipt['chord_hits'], 0)
            # Public validator still returns its independent mutable copy.
            published = validation.validate_graph(copy.deepcopy(graph))
            self.assertEqual(published, graph)
            return receipt
        with ThreadPoolExecutor(max_workers=12) as pool:
            receipts = list(pool.map(task, range(240)))
        self.assertEqual(len(receipts), 240)
        self.assertIs(validation.cell_at, original_cell)
        self.assertIs(admission_geometry.make_variants, original_factory)

    def test_invalid_graphs_and_boundaries(self):
        graph = graph_with_same_cell()
        mutations = [
            lambda g:g.update(crs='EPSG:4326'),
            lambda g:g['grid'].update(resolution=0),
            lambda g:g['nodes'][0].update(x=-1),
            lambda g:g['edges'][0]['segments'][0].update(cell=999),
            lambda g:g['edges'][0].update(reverse_edge='missing'),
            lambda g:g['edges'][0].update(travel_ticks=0),
            lambda g:g['nodes'].append(copy.deepcopy(g['nodes'][0])),
            lambda g:g['forbidden_turns'].append(['not-an-edge','also-not-an-edge']),
            lambda g:g.update(mid_edge_reversal='yes'),
        ]
        for mutate in mutations:
            candidate = copy.deepcopy(graph); mutate(candidate)
            self.assertEqual(result(PreparedGraph, candidate, backend='native'),
                             result(PreparedGraph, candidate, backend='python'))
        grid = {'x0': -1.0, 'y0': -1.0, 'resolution': 0.5, 'width': 4, 'height': 4}
        from wfg_routing_experimental.native_backend import NativeOperations
        operations = NativeOperations(validation.cell_at)
        rng = random.Random(14307)
        for _ in range(3000):
            x = rng.choice([rng.uniform(-1.1,1.1), -1.0, -0.5, 0.0, 0.5, 1.0, 2**-1074])
            y = rng.choice([rng.uniform(-1.1,1.1), -1.0, -0.5, 0.0, 0.5, 1.0, -0.0])
            self.assertEqual(result(operations.cell_at, grid, x, y), result(validation.cell_at, grid, x, y))

    def test_native_rejects_changed_validation_hook(self):
        graph = graph_with_same_cell()
        saved = validation.cell_at
        try:
            validation.cell_at = lambda *_: 0
            with self.assertRaisesRegex(NativeBackendError, 'GRAPH_VALIDATION_HOOK_CHANGED'):
                PreparedGraph(graph, backend='native')
        finally:
            validation.cell_at = saved

    def test_missing_and_mutated_binary_fail_closed(self):
        # All tampering is confined to a fresh temporary copy of our own pilot.
        script = r'''import json, sys
from pathlib import Path
from wfg_routing_experimental.fixture import example
from wfg_routing_experimental.prepared import PreparedGraph
from wfg_routing_experimental.native_backend import NativeBackendError, backend_identity
mode=sys.argv[1]
if mode=='missing':
    try: PreparedGraph(example()['graph'], backend='native')
    except NativeBackendError: pass
    else: raise AssertionError('missing binary accepted')
    assert PreparedGraph(example()['graph'],backend='python').backend_receipt()['identity']['effective_mode']=='python'
else:
    identity=backend_identity('native')
    path=Path(identity['native_binary_path'] if mode=='binary' else __import__('wfg_routing_experimental.native_backend',fromlist=['x']).__file__).parent
    target=Path(identity['native_binary_path']) if mode=='binary' else path/'native_cell.c'
    with target.open('ab') as f: f.write(b'\n')
    try: backend_identity('native')
    except NativeBackendError: pass
    else: raise AssertionError('changed identity accepted')
    assert backend_identity('python')['effective_mode']=='python'
'''
        with tempfile.TemporaryDirectory(prefix='wfg-native-controls-') as temp:
            destination = Path(temp) / 'wfg_routing_experimental'
            shutil.copytree(SRC / 'wfg_routing_experimental', destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=temp, WFG_GRAPH_BACKEND='python')
            for mode in ['binary', 'source']:
                # Restore a clean copy after each intentional mutation.
                if mode == 'source':
                    shutil.rmtree(destination)
                    shutil.copytree(SRC / 'wfg_routing_experimental', destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                p = subprocess.run([sys.executable, '-B', '-c', script, mode], env=env,
                                   capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            for p in destination.glob('wfg_native_cell*.so'): p.unlink()
            p = subprocess.run([sys.executable, '-B', '-c', script, 'missing'], env=env,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_invalid_mode(self):
        with self.assertRaises(NativeBackendError): resolve_mode('native-if-available')
        with self.assertRaises(NativeBackendError): PreparedGraph(example()['graph'], backend='bogus')

    def test_changed_live_native_callable_fails_closed(self):
        import math
        backend_identity('native')
        module = sys.modules['wfg_routing_experimental.wfg_native_cell']
        saved = module.same_cell
        try:
            module.same_cell = math.ceil
            with self.assertRaises(NativeBackendError): backend_identity('native')
        finally:
            module.same_cell = saved

    def test_preloaded_forged_native_module_fails_closed(self):
        script = r'''import importlib.machinery,importlib.util,math,sys,sysconfig,types
from pathlib import Path
from wfg_routing_experimental.native_backend import backend_identity,NativeBackendError
import wfg_routing_experimental.native_backend as backend
fullname='wfg_routing_experimental.wfg_native_cell'
binary=Path(backend.__file__).parent / ('wfg_native_cell'+sysconfig.get_config_var('EXT_SUFFIX'))
fake=types.ModuleType(fullname);fake.__file__=str(binary)
fake.__spec__=importlib.util.spec_from_file_location(fullname,binary,loader=importlib.machinery.ExtensionFileLoader(fullname,str(binary)))
fake.cell_at=math.floor;fake.same_cell=math.ceil
sys.modules[fullname]=fake
try: backend_identity('native')
except NativeBackendError as error: assert str(error)=='NATIVE_PREEXISTING_MODULE_UNTRUSTED'
else: raise AssertionError('forged module accepted')
assert backend_identity('python')['effective_mode']=='python'
'''
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(SRC), WFG_GRAPH_BACKEND='python')
        p = subprocess.run([sys.executable, '-B', '-c', script], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_default_mode_is_import_time_and_per_call_override_isolated(self):
        script = r'''import os
from wfg_routing_experimental.fixture import example
from wfg_routing_experimental.prepared import PreparedGraph
from wfg_routing_experimental.native_backend import resolve_mode
assert resolve_mode()=='native'
os.environ['WFG_GRAPH_BACKEND']='python'
assert resolve_mode()=='native'
assert PreparedGraph(example()['graph']).backend_receipt()['identity']['effective_mode']=='native'
assert PreparedGraph(example()['graph'], backend='python').backend_receipt()['identity']['effective_mode']=='python'
'''
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(SRC), WFG_GRAPH_BACKEND='native')
        p = subprocess.run([sys.executable, '-B', '-c', script], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == '__main__': unittest.main(verbosity=2)
