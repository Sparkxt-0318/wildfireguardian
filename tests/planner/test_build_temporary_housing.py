"""Optional 임시주거시설 importer (data.go.kr 15139148): imports only records with coordinates, labels them
임시주거시설, never 대피소, and writes nothing when the response has no coordinates."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'planner' / 'tools' / 'import_temporary_housing.py'
OUT = ROOT / 'planner' / 'public' / 'data' / 'regions' / 'uiseong_andong_2025' / 'temporary_housing.geojson'

sys.path.insert(0, str(ROOT / 'planner' / 'tools'))
import planner_common as pc  # noqa: E402

pytestmark = pytest.mark.skipif(not pc.assets_present(), reason='planner/.assets missing (run fetch_planner_assets.sh)')


def run(tmp_path, payload, *extra):
    f = tmp_path / 'resp.json'
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return subprocess.run([sys.executable, str(TOOL), '--file', str(f), '--regions', 'uiseong_andong_2025', *extra],
                          capture_output=True, text=True)


def test_no_coordinates_imports_nothing(tmp_path):
    existed = OUT.exists()
    payload = {'response': {'body': {'items': [{'fcltyNm': 'TEST 시설 A', 'mngSn': 'T1', 'rnAdres': 'x', 'cap': 10}]}}}
    r = run(tmp_path, payload)
    assert r.returncode != 0 and 'NOT imported' in (r.stderr + r.stdout)
    assert OUT.exists() == existed


def test_coordinates_imported_and_labelled(tmp_path):
    payload = {'response': {'body': {'items': [
        {'fcltyNm': 'TEST 시설 B', 'mngSn': 'TEST-1', 'rnAdres': 'synthetic', 'lat': 36.42, 'lot': 128.70},
        {'fcltyNm': 'TEST 시설 C', 'mngSn': 'TEST-2', 'rnAdres': 'synthetic', 'lat': 37.90, 'lot': 127.00}]}}}
    try:
        r = run(tmp_path, payload)
        assert r.returncode == 0, r.stderr
        fc = json.loads(OUT.read_text(encoding='utf-8'))
        assert len(fc['features']) == 1                      # the second record is outside the region
        p = fc['features'][0]['properties']
        assert p['category'] == 'temporary_housing' and p['label_ko'] == '임시주거시설'
        assert '대피소' not in json.dumps(p, ensure_ascii=False)
        assert p['source_tag'] == '15139148 TEST-1' and p['entry']['node'].startswith('osm:')
    finally:
        if OUT.exists():
            OUT.unlink()


def test_projected_coordinates_require_crs(tmp_path):
    payload = {'items': [{'fcltyNm': 'TEST', 'mngSn': 'T3', 'x': 1100000.0, 'y': 1830000.0, 'z': 1}]}
    r = run(tmp_path, payload)
    assert r.returncode != 0 and '--crs' in (r.stderr + r.stdout)
