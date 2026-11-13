"""Step 2 amendment E, test 4 (Thomas 17:55 UTC): the edge-blocked distance is byte-identical to the parent's.

Function level: edge_source_dist vs the parent's literal expression, at 1 row, the 64 MiB cap, unchunked, E not a
multiple of the block, and E = 0.
Model level (synthetic, parent fixtures): v2 RoadBoundModel vs the parent RoadBoundModel: dist and n_default bytes at
1 row, the cap and unchunked; the full_pot.size = 0 (inf) branch; a graph with no edges behaves as the parent does.
Real packets (WFG_V2_KIT; F-DYN data WFG_FDYN_DATA): 1-hour Yeongdeok and Uiseong, and the 4 F-DYN packets; each
packet in its own process: parent build vs v2 builds at 1 row, the cap and unchunked.
"""
import hashlib, importlib.util, json, os, subprocess, sys, tempfile, unittest
from fractions import Fraction as Q
from pathlib import Path
from unittest import mock
import numpy as np

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
REPO = V2.parents[1]
PSTACK = REPO / 'experimental/window-routing/stack'
KIT = Path(os.environ['WFG_V2_KIT']).resolve() if os.environ.get('WFG_V2_KIT') else None
FDYN = Path(os.environ['WFG_FDYN_DATA']).resolve() if os.environ.get('WFG_FDYN_DATA') else None


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    sys.modules[name] = m; s.loader.exec_module(m); return m


sys.path[:0] = [str(PSTACK / 'routing_candidate/baseline'), str(PSTACK / 'routing_candidate/baseline/routing-package')]
P = load('parent_road_bounds', PSTACK / 'phaseB/road_bounds.py')
N = load('v2_road_bounds', V2 / 'stack-v2/phaseB/road_bounds.py')
from hybrid_radiation import HybridRadiationBounds  # noqa: E402


def parent_dist(U, V, sr):
    """The parent's literal expression (road_bounds.py, parent lines 269-274)."""
    bx0 = np.minimum(U[:, 0], V[:, 0])[:, None]; bx1 = np.maximum(U[:, 0], V[:, 0])[:, None]
    by0 = np.minimum(U[:, 1], V[:, 1])[:, None]; by1 = np.maximum(U[:, 1], V[:, 1])[:, None]
    gx = np.maximum(0, np.maximum(sr[None, :, 0] - bx1, bx0 - sr[None, :, 1]))
    gy = np.maximum(0, np.maximum(sr[None, :, 2] - by1, by0 - sr[None, :, 3]))
    return np.sqrt(gx * gx + gy * gy).min(axis=1)


class FunctionLevel(unittest.TestCase):
    def test_random_shapes_and_block_sizes(self):
        rng = np.random.default_rng(20261112)
        for E in (0, 1, 7, 1000, 1303):
            for S in (1, 3, 50):
                U = rng.uniform(-5e3, 5e3, (E, 2)); V = U + rng.uniform(-300, 300, (E, 2))
                lo = rng.uniform(-5e3, 5e3, (S, 2)); w = rng.uniform(1, 200, (S, 2))
                sr = np.column_stack([lo[:, 0], lo[:, 0] + w[:, 0], lo[:, 1], lo[:, 1] + w[:, 1]])
                ref = parent_dist(U, V, sr)
                cap = N.dist_block_rows(E, S)
                for rows in sorted({1, 3, 64, cap, max(1, E), max(1, E) + 5}):
                    with self.subTest(E=E, S=S, rows=rows):
                        got = N.edge_source_dist(U, V, sr, rows)
                        self.assertEqual(got.dtype, ref.dtype); self.assertEqual(got.shape, ref.shape)
                        self.assertEqual(got.tobytes(), ref.tobytes())

    def test_overlapping_and_touching_boxes_give_exact_zeros(self):
        U = np.array([[0., 0.], [10., 10.], [5., 5.]]); V = np.array([[10., 10.], [20., 20.], [5., 5.]])
        sr = np.array([[10., 20., 10., 20.], [-1., 0., -1., 0.]])
        for rows in (1, 2, 3):
            self.assertEqual(N.edge_source_dist(U, V, sr, rows).tobytes(), parent_dist(U, V, sr).tobytes())
        self.assertFalse(np.signbit(N.edge_source_dist(U, V, sr, 1)).any())   # no -0.0 that a min could order

    def test_cap_rule(self):
        self.assertEqual(N.dist_block_rows(111924, 513), (64 * 2 ** 20) // (8 * 513))
        self.assertEqual(N.dist_block_rows(10, 10 ** 9), 1)


CONFIG = dict(version='wfg.hazard.construction/1', fuel_load_kg_m2=1, heat_of_combustion_j_kg=80000, consumed_fraction=1,
              burning_duration_s=4, initial_remaining_s=4, radiative_fraction=1, atmospheric_transmissivity=1,
              emission_height_m=4, receiver_height_m=1, horizon_s=30)
IDS = ['a', 'b', 'c', 'd']


def synthetic(module, *, empty_sources=False, n_edges=3, window=(6, 10)):
    """The parent's inherited fixture pattern (inherited_request_window_controls.fixture), with a few more edges."""
    x0 = y0 = 1000
    arr = np.full((4, 2, 3), np.inf); current = np.zeros((2, 3), dtype=bool)
    if not empty_sources:
        current[0, 0] = True
        for s, last in enumerate((20, 21, 22, 7)):
            arr[s].flat[1:] = [2, 10, 6, 11, last]
    rb = HybridRadiationBounds(arr, current, CONFIG, (10, 0, x0, 0, -10, y0 + 20), IDS, np.ones((2, 3), dtype=bool),
                               evidence_class='RESEARCH_CONSTRUCTION')
    nodes = [dict(id='n%d' % i, x=x0 + 5 + 3 * i, y=y0 + 5 + (i % 2) * 7) for i in range(n_edges + 1)]
    edges = [dict(id='e%d' % i, u='n%d' % i, v='n%d' % (i + 1), travel_ticks=1) for i in range(n_edges)]
    graph = dict(grid=dict(x0=x0, y0=y0, resolution=10, width=3, height=2), nodes=nodes, edges=edges)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); (p / 'constructed_arrays.npz').write_bytes(b'fixture'); (p / 'REPORT.json').write_text('{}')
        with mock.patch.object(HybridRadiationBounds, 'from_case', return_value=rb):
            return module.RoadBoundModel(graph, p, active_window=window)


class ModelLevel(unittest.TestCase):
    def tearDown(self):
        N.DIST_BLOCK_ROWS_OVERRIDE = None

    def test_dist_and_n_default_identical(self):
        for n_edges in (1, 3, 7):
            ref = synthetic(P, n_edges=n_edges)
            for rows in (1, None, 10 ** 9, 2):
                N.DIST_BLOCK_ROWS_OVERRIDE = rows
                m = synthetic(N, n_edges=n_edges)
                with self.subTest(n_edges=n_edges, rows=rows):
                    self.assertEqual(m.dist.tobytes(), ref.dist.tobytes())
                    self.assertEqual(m.n_default.tobytes(), ref.n_default.tobytes())
                    self.assertEqual(m.identity, ref.identity)
                    self.assertEqual(m.dist_sha256, hashlib.sha256(ref.dist.tobytes()).hexdigest())

    def test_no_potential_sources_inf_branch(self):
        ref = synthetic(P, empty_sources=True); m = synthetic(N, empty_sources=True)
        self.assertEqual(ref.full_pot.size, 0)
        self.assertEqual(m.dist.tobytes(), ref.dist.tobytes()); self.assertTrue(np.isinf(m.dist).all())
        self.assertEqual(m.n_default.tobytes(), ref.n_default.tobytes()); self.assertIsNone(m.dist_block_rows)

    def test_no_edges_behaves_as_parent(self):
        outcome = {}
        for name, mod in (('parent', P), ('v2', N)):
            try:
                m = synthetic(mod, n_edges=0)
                outcome[name] = ('ok', m.dist.tobytes(), m.n_default.tobytes())
            except Exception as exc:
                outcome[name] = ('raised', type(exc).__name__, str(exc))
        self.assertEqual(outcome['parent'], outcome['v2'])


PACKET_PROBE = r'''
import json, sys, hashlib
from fractions import Fraction as F
from pathlib import Path
kit, graph_p, packet, dep, hor, which = sys.argv[1:7]
kit = Path(kit)
q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
phase = sys.argv[7]
sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), phase]
import road_bounds
if which != 'parent':
    road_bounds.DIST_BLOCK_ROWS_OVERRIDE = None if which == 'cap' else (1 if which == 'one' else 10 ** 12)
g = json.loads(Path(graph_p).read_text())
M = road_bounds.RoadBoundModel(g, packet, active_window=(F(dep), F(hor)))
print(json.dumps({'dist': hashlib.sha256(M.dist.tobytes()).hexdigest(), 'n_default': hashlib.sha256(M.n_default.tobytes()).hexdigest(),
                  'identity': M.identity, 'rows': getattr(M, 'dist_block_rows', 'parent'), 'E': len(g['edges']), 'S': int(M.full_pot.size),
                  'file': road_bounds.__file__}))
'''


def packets():
    data = REPO / 'data/routing'
    out = []
    for region, cutoff in (('yeongdeok_2025', '20250325T190000Z'), ('uiseong_andong_2025', '20250325T170000Z')):
        req = sorted((data / 'latest_inputs_try02/requests' / region).glob(cutoff + '_*.json'))[0]
        r = json.loads(req.read_text())
        out.append(('1h ' + region, data / 'graphs' / region / 'graph.json', data / 'latest_inputs_try02/packets' / region / cutoff,
                    str(r['departure']), str(r['horizon'])))
    if FDYN is not None:
        for region, name in (('yeongdeok_2025', '20250325T230000Z_h5_firms_early_central_q300'),
                             ('yeongdeok_2025', '20250325T230000Z_h5_kriged_mean_central_q300'),
                             ('uiseong_andong_2025', '20250325T170000Z_h5_firms_early_central_q300'),
                             ('uiseong_andong_2025', '20250325T170000Z_h5_kriged_mean_central_q300')):
            out.append(('fdyn ' + name, FDYN / 'graphs_interim' / region / 'graph.json', FDYN / 'packets_v31' / region / name, '0', '18000'))
    return out


@unittest.skipIf(KIT is None, 'set WFG_V2_KIT (and WFG_FDYN_DATA for the F-DYN packets)')
class RealPackets(unittest.TestCase):
    def build(self, which, g, pk, dep, hor):
        phase = PSTACK / 'phaseB' if which == 'parent' else KIT / 'phaseB'
        p = subprocess.run([sys.executable, '-B', '-c', PACKET_PROBE, str(KIT), str(g), str(pk), dep, hor, which, str(phase)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr[-3000:])
        return json.loads(p.stdout.strip().splitlines()[-1])

    def test_byte_identity_on_packets(self):
        rows = []
        for label, g, pk, dep, hor in packets():
            ref = self.build('parent', g, pk, dep, hor)
            self.assertTrue(ref['file'].startswith(str(PSTACK)))
            for which in ('one', 'cap', 'unchunked'):
                got = self.build(which, g, pk, dep, hor)
                self.assertTrue(got['file'].startswith(str(KIT)))
                with self.subTest(packet=label, rows=which):
                    for k in ('dist', 'n_default', 'identity'):
                        self.assertEqual(got[k], ref[k], (label, which, k))
                rows.append({'packet': label, 'which': which, 'rows': got['rows'], 'E': got['E'], 'S': got['S'],
                             'dist_sha256': got['dist'], 'n_default_sha256': got['n_default']})
        out = os.environ.get('WFG_STEP2_DIST_OUT')
        if out:
            Path(out).write_text(json.dumps(rows, indent=1) + '\n')


if __name__ == '__main__':
    unittest.main()
