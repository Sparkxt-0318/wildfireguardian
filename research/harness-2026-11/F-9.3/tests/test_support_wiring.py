"""SUPPORT_WIRING_RULE.md acceptance tests (rule @82f025fa, correction 1 @4678c655). Slow: packet builds.

    python3 -m pytest -q research/harness-2026-11/F-9.3/tests/test_support_wiring.py
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
FDYN = REPO / 'research' / 'harness-2026-11' / 'F-DYN'
FDYN_DATA = FDYN / '_data'
needs_inputs = pytest.mark.skipif(not INPUTS.exists() or not FDYN_DATA.exists(), reason='needs data/routing and F-DYN _data')
FILES = ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz')
# Default-build HAZARD sha256 of v3.5 YD 25T11Z h5 kriged_mean, per numpy minor version (flux bytes are numpy-build
# dependent; Hannah row 50 note 1). Unknown versions: that one assertion is skipped and the run reports it.
V35_KRIGED_HAZARD = {'2.5': '6940f2939318126437b6109853033ab0b1534dd288f3775c6c0352ed44646f2f',   # Leo, Nora row 41, Hannah
                     '1.26': '5716c09e70b285ce10db54bc87ec37c89987d124ae7010438a02870dfe5d4326'}  # Hannah rows 50, 52


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest_cmd(region, start, h, variant, out):
    man = json.loads((FDYN / 'MANIFEST_v3_5.json').read_text())
    e = next(e for e in man['entries'] if (e['region'], e['start'], e['horizon_h'], e['variant']) == (region, start, h, variant))
    cmd = list(e['cmd'])
    cmd[cmd.index('--out') + 1] = str(out)
    if cmd[0] == 'python3':                         # Hannah row 50 note 2: the interpreter running the tests
        cmd[0] = sys.executable
    return cmd


def perimeter(horizon_h, rule='sampled'):
    sq = lambda a, b, c, d: {'type': 'Polygon', 'coordinates': [[[a, b], [c, b], [c, d], [a, d], [a, b]]]}
    polys = [('2025-03-26T01:00:00Z', sq(129.30, 36.40, 129.33, 36.42)),
             ('2025-03-26T03:00:00Z', sq(129.28, 36.38, 129.35, 36.44))]
    sc = adapters.from_perimeter_sequence(polys, '2025-03-25T23:00:00Z', 'yeongdeok_2025', '20250325T230000Z',
                                          FDYN_DATA / 'graphs_interim' / 'yeongdeok_2025' / 'graph.json',
                                          horizon_h=horizon_h, domain=None, rule=rule)
    # declared domain (raster): the whole export grid except a north-east corner box that holds no burned cell at
    # the start (rows 0-14, cols 200-236, north-up), so the domain contains all present fire
    dom = np.ones((79, 237), bool)
    dom[0:15, 200:237] = False
    sc.known = {'inside_declared_domain': dom}
    return sc


@needs_inputs
def test_1_and_3_fdyn_default_and_all_true_mask_unchanged(tmp_path):
    """1: build.py without support args == the v3.5 packet. 3: an all-true supplied mask is not applied."""
    plain = tmp_path / 'plain'
    r = subprocess.run(manifest_cmd('yeongdeok_2025', '20250325T110000Z', 5, 'kriged_mean', plain), cwd=REPO,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    expected = V35_KRIGED_HAZARD.get('.'.join(np.__version__.split('.')[:2]))
    if expected is not None:
        assert sha(plain / 'HAZARD.json').startswith(expected)
    else:
        print(f'v3.5 hash not recorded for numpy {np.__version__}: default-build hash assertion skipped')
    m = tmp_path / 'alltrue.npz'
    np.savez(m, support=np.ones((79, 237), bool))
    true_ = tmp_path / 'alltrue'
    cmd = manifest_cmd('yeongdeok_2025', '20250325T110000Z', 5, 'kriged_mean', true_) + [
        '--support-mask', str(m), '--support-rule', 'supplied/1', '--support-provenance', '{"test": "all-true"}']
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert {f: sha(true_ / f) for f in FILES} == {f: sha(plain / f) for f in FILES}
    rec = json.loads((true_ / 'BUILD_SUMMARY.json').read_text())['fdyn']['support']
    assert rec['applied'] is False and rec['unsupported_cells'] == 0


@needs_inputs
def test_2_c651_through_build_equals_wrapper_cli(tmp_path):
    sc = adapters.from_c651('yeongdeok_2025', '20250325T190000Z')
    sc.support = 'c651_unknown/1'
    scenario.build(sc, tmp_path / 'iface')
    win, md = scenario._recorded_window('yeongdeok_2025', '20250325T190000Z')
    event = md['construction']['parent_forecast']['event_id']
    cmd = [sys.executable, '-I', '-B', str(HERE / 'support_mask' / 'build_packet_f93.py'),
           '--graph', str(REPO / 'data/routing/graphs/yeongdeok_2025/graph.json'),
           '--export-dir', str(INPUTS / 'exports' / event), '--event', event, '--cutoff', '2025-03-25T19:00:00Z',
           '--region', 'yeongdeok_2025', '--out', str(tmp_path / 'direct'), '--support-rule', 'c651_unknown/1']
    if win is not None:
        cmd += ['--window-json', json.dumps(win)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert {f: sha(tmp_path / 'iface' / f) for f in FILES} == {f: sha(tmp_path / 'direct' / f) for f in FILES}
    sw = json.loads((tmp_path / 'iface' / 'HAZARD.json').read_text())['provenance']['identity']['support_writer']
    assert sw['rule'] == 'c651_unknown/1' and sw['unsupported_cells'] == 2885


@needs_inputs
def test_4_perimeter_masked_vs_unmasked(tmp_path):
    sc = perimeter(horizon_h=4)                     # t_n = +4 h = horizon: static mask is exact
    scenario.build(sc, tmp_path / 'plain')
    sc2 = perimeter(horizon_h=4)
    sc2.support = 'known'
    meta = scenario.build(sc2, tmp_path / 'masked')
    hp = json.loads((tmp_path / 'plain' / 'HAZARD.json').read_text())
    hm = json.loads((tmp_path / 'masked' / 'HAZARD.json').read_text())
    for a, b in zip(hp['members'], hm['members']):
        assert all(a[k] == b[k] for k in ('id', 'breakpoints', 'flame', 'flux'))
    ip, im = hp['provenance']['identity'], hm['provenance']['identity']
    assert 'support_writer' not in ip and im['support_writer']['rule'] == 'supplied/1'
    assert im['base_packet_writer_sha256'] == ip['packet_writer_sha256'] != im['packet_writer_sha256']
    expected = 15 * 37
    assert im['support_writer']['unsupported_cells'] == expected == meta['support']['unsupported_cells_export_grid']
    flat = np.flipud(sc2.known['inside_declared_domain']).ravel()
    assert all((np.asarray(m['support'], bool) == flat).all() for m in hm['members'])
    summ = json.loads((tmp_path / 'masked' / 'BUILD_SUMMARY.json').read_text())
    assert summ['fdyn']['support']['applied'] is True
    assert summ['fdyn']['packet_self_check']['consistent'] is True
    assert not (tmp_path / 'masked' / 'SUPPORT_WRITE_FAILED').exists()


@needs_inputs
def test_5_perimeter_time_dependent_refused(tmp_path):
    sc = perimeter(horizon_h=5)                     # t_n = +4 h < 5 h with in-domain no-polygon cells
    sc.support = 'known'
    with pytest.raises(ValueError, match='SUPPORT_TIME_DEPENDENT'):
        scenario.build(sc, tmp_path / 'p')
    assert not (tmp_path / 'p').exists()


@needs_inputs
def test_6_envelope_with_mask_refused_before_build(tmp_path):
    sc = perimeter(horizon_h=4, rule='envelope')
    sc.support = 'known'
    with pytest.raises(ValueError, match='SUPPORT_NOT_WIRED'):
        scenario.build(sc, tmp_path / 'p')
    assert not (tmp_path / 'p').exists()
    m = tmp_path / 'm.npz'
    np.savez(m, support=np.ones((79, 237), bool))
    out = tmp_path / 'env'
    cmd = manifest_cmd('yeongdeok_2025', '20250325T110000Z', 5, 'envelope', out) + [
        '--support-mask', str(m), '--support-rule', 'supplied/1', '--support-provenance', '{"t": 1}']
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    assert r.returncode != 0 and 'SUPPORT_ENVELOPE_UNSUPPORTED' in (r.stdout + r.stderr)
    assert not out.exists()
