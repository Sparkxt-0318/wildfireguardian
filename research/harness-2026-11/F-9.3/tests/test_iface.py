"""F-9.3 regression and third-source tests (DESIGN.md acceptance):
1. c651 through the interface == direct build_packet (byte-identical HAZARD in one environment); vs the frozen packet:
   ids, breakpoints, flame, support exact; flux within relative 1e-9.
2. zones (sampled) through the interface == the API adapter's own build_packet (byte-identical HAZARD).
3. a perimeter sequence (third source) is ingested with no routing-code change; per-cell [lo, hi] follows the rule;
   cells outside the declared domain are flagged known = False in the interface metadata.
Slow (packet builds): run with  python3 -m pytest -q research/harness-2026-11/F-9.3/tests
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from hazard_iface import adapters, scenario  # noqa: E402

INPUTS = REPO / 'data' / 'routing' / 'latest_inputs_try02'
FDYN_DATA = REPO / 'research' / 'harness-2026-11' / 'F-DYN' / '_data'
needs_inputs = pytest.mark.skipif(not INPUTS.exists(), reason='needs data/routing')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@needs_inputs
def test_c651_through_interface_equals_direct_and_frozen(tmp_path):
    region, tag = 'yeongdeok_2025', '20250325T190000Z'
    sc = adapters.from_c651(region, tag)
    scenario.build(sc, tmp_path / 'iface')
    md = json.loads((INPUTS / 'packets' / region / tag / 'NATIVE_METADATA.json').read_text())
    win = md['regional']['window_rows_cols_north_up']
    r = subprocess.run([sys.executable, '-I', '-B', str(REPO / 'integration/src/wfg_latest/build_packet.py'),
                        '--graph', str(REPO / 'data/routing/graphs' / region / 'graph.json'),
                        '--export-dir', str(INPUTS / 'exports/KFS_01'), '--event', 'KFS_01',
                        '--cutoff', '2025-03-25T19:00:00Z', '--region', region, '--window-json', json.dumps(win),
                        '--out', str(tmp_path / 'direct')], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    assert sha(tmp_path / 'iface' / 'HAZARD.json') == sha(tmp_path / 'direct' / 'HAZARD.json')
    a = json.loads((tmp_path / 'iface' / 'HAZARD.json').read_text())
    b = json.loads((INPUTS / 'packets' / region / tag / 'HAZARD.json').read_text())
    for ma, mb in zip(a['members'], b['members']):
        assert ma['id'] == mb['id'] and ma['breakpoints'] == mb['breakpoints']
        assert ma['flame'] == mb['flame'] and ma['support'] == mb['support']
        fa, fb = np.array(ma['flux']), np.array(mb['flux'])
        assert np.all(np.abs(fa - fb) <= 1e-9 * np.maximum(np.abs(fb), 1e-12) + 1e-15)
    meta = json.loads((tmp_path / 'iface' / 'F93_INTERFACE.json').read_text())
    assert meta['known_flags']['known_burned_state']['unknown_cells'] == 2570       # Iris's U_state, measured


@needs_inputs
def test_zones_through_interface_equals_api_adapter(tmp_path):
    from api.adapters import spread_zones as SZ
    from api.config import Settings, load_settings
    from api.regions import Registry, to_5179
    s = load_settings()
    reg = Registry(Settings(data_root=INPUTS.parent, runtime_dir=tmp_path / 'rt', workers=1, python=s.python,
                            host=s.host, port=s.port)).load()
    region = reg.regions['hongseong_2023']
    sset = region.scenario_sets['20230402T230000Z']
    md = json.loads((sset.packet_dir / 'NATIVE_METADATA.json').read_text())
    with np.load(sset.packet_dir / 'constructed_arrays.npz') as z:
        present = z['current_active'].copy()
    zone = {'type': 'Feature', 'properties': {'arrival_h_max': 5},
            'geometry': {'type': 'Polygon', 'coordinates': [[[126.49, 36.55], [126.51, 36.55], [126.51, 36.57],
                                                             [126.49, 36.57], [126.49, 36.55]]]}}
    fi = {'type': 'spread_zones', 'issued_at': '2023-04-02T23:00:00Z',
          'zones': {'type': 'FeatureCollection', 'features': [zone]}}
    plan = SZ.plan(region=region, sset=sset, fire_input=fi, to_5179=to_5179, horizon_s=sset.horizon_s,
                   active_duration_s=md['construction']['assumptions']['burning_duration_s'], present_fire=present,
                   window=md['regional']['window_rows_cols_north_up'])
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    SZ.build_packet(plan, graph_path=region.graph_path, out_dir=tmp_path / 'a' / 'packet', python=sys.executable)
    scenario.build(adapters.from_zones_plan(plan, 'hongseong_2023', '20230402T230000Z'), tmp_path / 'b' / 'packet')
    assert sha(tmp_path / 'a' / 'packet' / 'HAZARD.json') == sha(tmp_path / 'b' / 'packet' / 'HAZARD.json')


@needs_inputs
@pytest.mark.skipif(not (FDYN_DATA / 'graphs_interim' / 'yeongdeok_2025' / 'graph.json').exists(),
                    reason='needs the F-DYN interim full-grid graph (fdyn/regrid_graph.py)')
def test_perimeter_sequence_is_ingested_without_routing_change(tmp_path):
    # two nested rectangles inland of the Yeongdeok coast, valid at +2 h and +4 h after the 23:00Z start
    sq = lambda a, b, c, d: {'type': 'Polygon', 'coordinates': [[[a, b], [c, b], [c, d], [a, d], [a, b]]]}
    polys = [('2025-03-26T01:00:00Z', sq(129.30, 36.40, 129.33, 36.42)),
             ('2025-03-26T03:00:00Z', sq(129.28, 36.38, 129.35, 36.44))]
    domain = sq(129.20, 36.33, 129.45, 36.55)
    sc = adapters.from_perimeter_sequence(polys, '2025-03-25T23:00:00Z', 'yeongdeok_2025', '20250325T230000Z',
                                          FDYN_DATA / 'graphs_interim' / 'yeongdeok_2025' / 'graph.json',
                                          horizon_h=5, domain=domain, rule='envelope')
    h = lambda iso: adapters._hours(adapters.dt.datetime.fromisoformat(iso.replace('Z', '+00:00')))
    inner = np.isfinite(sc.arrival_lo_h) & (sc.arrival_hi_h == h('2025-03-26T01:00:00Z'))
    ring = np.isfinite(sc.arrival_lo_h) & (sc.arrival_hi_h == h('2025-03-26T03:00:00Z'))
    assert inner.sum() > 0 and ring.sum() > inner.sum()
    assert np.all(sc.arrival_lo_h[inner] == h('2025-03-25T23:00:00Z'))
    assert np.all(sc.arrival_lo_h[ring] == h('2025-03-26T01:00:00Z'))
    meta = scenario.build(sc, tmp_path / 'packet')
    hz = json.loads((tmp_path / 'packet' / 'HAZARD.json').read_text())
    assert hz['valid_until'] == 18000.0 and len(hz['members']) == 1
    unknown = meta['known_flags']['inside_declared_domain']['unknown_cells']
    assert 0 < unknown < 79 * 237
    nm = json.loads((tmp_path / 'packet' / 'NATIVE_METADATA.json').read_text())
    assert nm['settings']['source_law_version'] == 'wfg.fdyn.envelope-per-cell/1'
    # no routing/checker code changed by this work
    diff = subprocess.run(['git', 'diff', '--stat', 'origin/Main', '--', 'integration/', 'routing-package/',
                           'routing-api/', 'api/'], cwd=REPO, capture_output=True, text=True).stdout
    assert diff.strip() == ''
