"""Unit tests for the versioned writer wrapper (DESIGN.md). The full rebuild regression is regress.py (REGRESSION.json).

    python3 -m pytest -q research/harness-2026-11/F-9.3/support_mask
"""
from __future__ import annotations

import json
import shutil
import sys
import types
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import packets_f93 as PF  # noqa: E402

PKT = REPO / 'data' / 'routing' / 'latest_inputs_try02' / 'packets' / 'yeongdeok_2025' / '20250325T190000Z'
GRAPH = REPO / 'data' / 'routing' / 'graphs' / 'yeongdeok_2025' / 'graph.json'
needs_data = pytest.mark.skipif(not PKT.exists() or not GRAPH.exists(), reason='recorded packet not present (data/ is not in git)')


@pytest.fixture
def fake_base(monkeypatch):
    calls = []
    mod = types.ModuleType('packets')

    def write_regional_packet(*args, **kw):
        calls.append((args, kw))
        return 'OUT', {'hz': 1}, {'summary': 1}
    mod.write_regional_packet = write_regional_packet
    monkeypatch.setitem(sys.modules, 'packets', mod)
    return calls


def test_no_mask_is_complete_handoff(fake_base):
    r = PF.write_regional_packet('g', 'gp', 'npz', {}, 'rs', 'c', 5179, 'o', event_id='e', region_id='r', window=None)
    assert r == ('OUT', {'hz': 1}, {'summary': 1})
    assert fake_base == [(('g', 'gp', 'npz', {}, 'rs', 'c', 5179, 'o'), {'event_id': 'e', 'region_id': 'r', 'window': None})]


@pytest.mark.parametrize('kw,err', [
    ({'support_rule': 'c651_unknown/1'}, 'SUPPORT_RULE_WITHOUT_MASK'),
    ({'support_mask': np.ones((2, 2), bool), 'support_rule': 'other'}, 'SUPPORT_RULE_UNKNOWN'),
    ({'support_mask': np.ones((2, 2), bool), 'support_rule': 'c651_unknown/1'}, 'SUPPORT_RULE_MISMATCH'),
    ({'support_mask': np.ones((2, 2), bool), 'support_rule': 'supplied/1'}, 'SUPPORT_PROVENANCE_MISSING'),
    ({'support_mask': np.ones((2, 2), int), 'support_rule': 'supplied/1', 'support_provenance': {'s': 1}}, 'SUPPORT_SHAPE'),
    ({'support_mask': np.ones(4, bool), 'support_rule': 'supplied/1', 'support_provenance': {'s': 1}}, 'SUPPORT_SHAPE'),
])
def test_refusals_before_writing(fake_base, kw, err):
    with pytest.raises(PF.SupportError, match=err):
        PF.write_regional_packet('g', 'o', **kw)
    assert fake_base == []          # refused before the frozen writer ran


def _copy(tmp_path):
    d = tmp_path / 'pkt'
    shutil.copytree(PKT, d)
    if 'routing' not in sys.modules:             # the router validator exactly as the build vendors it (pinned)
        sys.path.insert(0, str(REPO / 'integration' / 'src' / 'wfg_latest'))
        import build_packet as BP
        BP.install_namespace('routing', 'router_validation', BP.ROUTER_VALIDATION_SHA256)
    return d, json.loads(GRAPH.read_text())


@needs_data
def test_c651_rule_on_recorded_packet(tmp_path):
    d, graph = _copy(tmp_path)
    with np.load(d / 'constructed_arrays.npz') as z:
        a = {k: z[k] for k in z.files}
    m = PF.c651_unknown(a)
    assert int((~m).sum()) == 2570 + 315          # U_state + U_q (F-9.3 DESIGN.md measured counts, Yeongdeok 03-25 19Z)
    hz, summ = PF.apply_support(d, graph, {'files_sha256': {}}, 'c651_unknown/1', 'c651_unknown/1', None)
    ident = hz['provenance']['identity']
    assert ident['packet_writer_sha256'] == PF._sha(PF.HERE) != ident['base_packet_writer_sha256']
    assert summ['support_writer']['unsupported_cells'] == 2885
    assert PF.array_law_check(d)['consistent']


@needs_data
def test_conflict_with_asserted_fire_refused(tmp_path):
    d, graph = _copy(tmp_path)
    with np.load(d / 'constructed_arrays.npz') as z:
        cur = z['current_active']
    assert cur.any()
    mask = ~cur                                    # unsupported exactly where present fire is
    with pytest.raises(PF.SupportError, match='SUPPORT_CONFLICT'):
        PF.apply_support(d, graph, {}, mask, 'supplied/1', {'test': 'conflict'})
    assert PF._sha(d / 'HAZARD.json') == PF._sha(PKT / 'HAZARD.json')     # nothing rewritten on refusal


@needs_data
def test_supplied_mask_wrong_shape_refused(tmp_path):
    d, graph = _copy(tmp_path)
    with pytest.raises(PF.SupportError, match='SUPPORT_SHAPE'):
        PF.apply_support(d, graph, {}, np.ones((3, 3), bool), 'supplied/1', {'test': 'shape'})


@pytest.mark.parametrize('extra,err', [
    (['--support-rule', 'foo/1'], 'SUPPORT_RULE_UNKNOWN'),
    (['--support-rule', 'supplied/1'], 'SUPPORT_PROVENANCE_MISSING'),
    (['--support-rule', 'c651_unknown/1', '--support-provenance', '{}'], 'SUPPORT_RULE_MISMATCH'),
])
def test_cli_validates_rule_before_build(tmp_path, extra, err):
    """Hannah note 1: the CLI refuses an unknown rule or inconsistent arguments before anything is built."""
    import subprocess
    out = tmp_path / 'never'
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'build_packet_f93.py'), '--graph', 'g', '--export-dir', 'e',
                        '--event', 'KFS_01', '--cutoff', '2025-03-25T19:00:00Z', '--region', 'r', '--out', str(out), *extra],
                       capture_output=True, text=True)
    assert r.returncode != 0 and err in (r.stdout + r.stderr)
    assert not out.exists()
