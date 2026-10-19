"""planner/research-map: the committed region bundles stay tied to the recorded data they were built from.

Checks the travel-time-only comparison against the records' full_policy_check (README: 8 of 20 fail), the booth
summary against planner/cache with the planner's verdict rules, the region index, and that the offline page is
complete (vendored three.js, every region file, no synthetic hourly layer)."""
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RM = ROOT / 'planner' / 'research-map'
P = ROOT / 'planner'
REGIONS = ['uljin_2022', 'miryang_2022', 'hongseong_2023', 'uiseong_andong_2025', 'yeongdeok_2025']


def load_js(path):
    s = path.read_text()
    return json.loads(s[s.index('=', s.index(']')) + 1:].rstrip().rstrip(';'))


@pytest.fixture(scope='module')
def bundles():
    return {r: load_js(RM / 'site' / 'regions' / f'{r}.js') for r in REGIONS}


@pytest.fixture(scope='module')
def index():
    s = (RM / 'site' / 'regions' / 'index.js').read_text()
    return json.loads(s[s.index('=') + 1:].rstrip().rstrip(';'))


def test_travel_only_comparison_matches_records(bundles):
    fails, detour = 0, 0
    for rid, b in bundles.items():
        for q in b['rq3']:
            recs = {f.name.split('__')[1][:-5]: json.loads(f.read_text()) for f in (P / 'mock_api/fixtures/records' / rid).glob(f"{q['case']}__*.json")}
            assert q['travel_fails_full'] == (recs['travel_only']['full_policy_check']['pass'] is False), (rid, q['case'])
            assert q['full_verdict'] == recs['full']['outcome']['verdict'], (rid, q['case'])
            fails += q['travel_fails_full']
            detour += q['travel_fails_full'] and q['full_verdict'] == 'checked_route'
    assert (fails, detour) == (8, 3)


def test_booth_summary_matches_cache(bundles):
    for rid in ('uiseong_andong_2025', 'yeongdeok_2025'):
        b = bundles[rid]
        origins = {f['properties']['id'] for f in json.loads((P / 'public/data/regions' / rid / 'places.geojson').read_text())['features']
                   if f['properties']['role'] == 'origin'}
        for entry in b['booth']:
            doc = json.loads((P / 'cache' / rid / (entry['input_time'].replace('-', '').replace(':', '') + '.json')).read_text())
            planned = {o['origin_id']: o['best_verdict'] for p in doc['plans'] for o in p['result']['plans']}
            rows = {r['id']: r for r in entry['rows']}
            for oid, v in planned.items():
                assert rows[oid]['v'] == v, (rid, entry['input_time'], oid)
            for oid in origins - set(planned):
                assert rows[oid]['v'] == 'not_checkable', (rid, oid)
            for oid, j in doc['travel_only'].items():
                r = rows.get(oid)
                passes = ((j.get('result') or {}).get('full_policy_assessment') or {}).get('passes_full_centre_and_contact')
                if r and r.get('travel'):
                    assert r['travel']['passes'] == passes, (rid, oid)
                    assert r['dep'] is None or r['travel']['dep'] == r['dep'], (rid, oid)   # same departure as the best checked attempt
    # the planner's own count for 의성·안동 2025-03-23 10:00 KST: 85 checked · 1 model no-route · 2 unresolved (not checkable)
    first = bundles['uiseong_andong_2025']['booth'][0]
    assert Counter(r['v'] for r in first['rows']) == Counter({'checked_route': 85, 'model_no_route': 1, 'not_checkable': 2})


def test_region_index_and_page(bundles, index):
    assert [r['id'] for r in index] == REGIONS
    for r in index:
        b = bundles[r['id']]
        assert r['inputs'] == b['input_times'] and r['cases'] == sorted(b['policies'])
        hf = RM / 'site' / 'regions' / f"{r['id']}.hourly.js"     # hourly F(h) loads after the first view
        assert bool(b.get('hourly_meta')) == hf.exists() == r['hourly'] and 'hourly' not in b
        if hf.exists():
            assert '"synthetic":false' in hf.read_text()[:2000] or '"synthetic":false' in hf.read_text()
    page = (RM / 'site' / 'index.html').read_text()
    for n in ['three.min.js', 'OrbitControls.js', 'EffectComposer.js', 'UnrealBloomPass.js']:
        assert f'vendor/{n}' in page and (RM / 'site' / 'vendor' / n).is_file()
    assert 'cdnjs' not in page and 'jsdelivr' not in page and 'fonts.googleapis' not in page    # offline build
    assert len(list((RM / 'site' / 'logger').glob('fig*.png'))) == 10
    for rid in REGIONS:   # pre-built terrain (tools/bake_textures.mjs); the page ignores it when its key no longer matches the data
        t = (RM / 'site' / 'regions' / f'{rid}.tex.js').read_text()
        tex = json.loads(t[t.index('=', t.index(']')) + 1:].rstrip().rstrip(';'))
        assert tex['key'].split(':')[1] == rid
        # the first view loads <id>.js; the ring heights (<id>.ctx.js) and OSM vectors (<id>.osm.js) are separate files, and the
        # texture key is computed from their recorded sizes, so those must match the files
        b, ctx, osm = bundles[rid], load_js(RM / 'site' / 'regions' / f'{rid}.ctx.js'), load_js(RM / 'site' / 'regions' / f'{rid}.osm.js')
        assert 'osm' not in b and 'b64' not in b['context']
        assert b['parts'] == dict(ctx_b64=len(ctx), osm_roads=len(osm['roads']), osm_landuse=len(osm['landuse']))
        assert tex['key'] == ':'.join(map(str, [2, rid, b['dem']['w'], b['dem']['h'], len(b['dem']['b64']), len(ctx), len(osm['roads']), len(osm['landuse'])]))
        for k in ('ground', 'hs', 'ctxReal', 'ctxTopo', 'mask', 'poster'):
            assert tex[k].startswith(f'regions/{rid}/') and (RM / 'site' / tex[k]).stat().st_size > 1000


def test_navigation_view(bundles):
    """길 안내: each headline case named in src/nav.js is in the bundle with both routes, and the pass / fail the panel shows
    is the recorded full-risk check; the real 3D map's library is vendored (loaded only when that view opens)."""
    import re
    nav = (RM / 'src' / 'nav.js').read_text()
    i = nav.index('const NAV_CASES'); cases = dict(re.findall(r"(\w+): '(\d{8}T\d{6}Z_\w+)'", nav[i:nav.index('};', i)]))
    assert set(cases) == set(REGIONS)
    for rid, case in cases.items():
        pol = bundles[rid]['policies'][case]
        recs = {f.name.split('__')[1][:-5]: json.loads(f.read_text()) for f in (P / 'mock_api/fixtures/records' / rid).glob(f'{case}__*.json')}
        # the travel-time-only route fails the recorded full check; the checked route either passes it or is recorded as none
        assert recs['travel_only']['full_policy_check']['pass'] is False and not pol['travel_only']['full_check']['passed'], (rid, case)
        if pol['full'].get('pts'):
            assert recs['full']['full_policy_check']['pass'] is True and pol['full']['full_check']['passed'], (rid, case)
        else:
            assert recs['full']['outcome']['verdict'] == 'model_no_route', (rid, case)
        # baked road view photo IDs belong to this case and have one entry per 30 m stop
        pano = (RM / 'site' / 'regions' / f'{rid}.pano.js').read_text()
        assert f'"case":"{case}"' in pano, rid
    # road view: Kakao JavaScript keys (public by design, tied to registered addresses) live in site/kakao-keys.js only
    assert 'appkey=${encodeURIComponent(navKey())}' in nav and not re.search(r'[0-9a-f]{32}', nav)
    keys = (RM / 'site' / 'kakao-keys.js').read_text()     # JavaScript keys only, one per registered address
    assert 'WFG_KAKAO_KEYS' in keys and 'kakao-keys.js' in (RM / 'site' / 'index.html').read_text()
    page = (RM / 'site' / 'index.html').read_text()
    assert 'id="tabNav"' in page and "const NAV_ML = 'vendor/maplibre-gl.'" in page
    for f in ('maplibre-gl.js', 'maplibre-gl.css', 'maplibre-gl.LICENSE.txt'):
        assert (RM / 'site' / 'vendor' / f).is_file()
    assert 'MapLibre GL JS' in (RM / 'site' / 'vendor' / 'maplibre-gl.js').read_text()[:200]
    # the CDN copy (CDN fragment, single file) is the same release: its integrity hashes are the vendored files' hashes
    import base64, hashlib, importlib.util
    for k in ('js', 'css'):
        h = 'sha384-' + base64.b64encode(hashlib.sha384((RM / 'site' / 'vendor' / f'maplibre-gl.{k}').read_bytes()).digest()).decode()
        assert f"{k}: '{h}'" in nav, k
    spec = importlib.util.spec_from_file_location('build_viewer', RM / 'tools' / 'build_viewer.py'); bv = importlib.util.module_from_spec(spec); spec.loader.exec_module(bv)
    cdn = bv.build(True)
    assert '__MAPLIBRE__' not in cdn and "const NAV_ML = 'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.'" in cdn


def test_logger_page():
    """Route logger page: the web model has the plain FireBeetle stand-in (no vendor mesh), every part in the export's
    part list is a node of the model, and every manual picture the page links exists."""
    import base64, re, struct
    page = (RM / 'site' / 'logger.html').read_text()
    for n in ['three.min.js', 'OrbitControls.js', 'GLTFLoader.js', 'RoomEnvironment.js']:
        assert f'vendor/{n}' in page and (RM / 'site' / 'vendor' / n).is_file()
    js = (RM / 'site' / 'logger' / 'model.js').read_text()
    glb = base64.b64decode(js[js.index('"') + 1:js.rindex('"')])
    gltf = json.loads(glb[20:20 + struct.unpack('<I', glb[12:16])[0]])
    names = {n.get('name') for n in gltf['nodes']}
    fb = [n for n in names if n and n.startswith('firebeetle2_esp32e__')]
    assert sorted(fb) == ['firebeetle2_esp32e__standin_can', 'firebeetle2_esp32e__standin_pcb', 'firebeetle2_esp32e__standin_usb']
    assert not any(re.match(r'fb_', m.get('name', '')) for m in gltf['meshes'])
    d = (RM / 'site' / 'logger' / 'data.js').read_text()
    rl = json.loads(d[d.index('=') + 1:].rstrip().rstrip(';'))
    assert {p['node'] for p in rl['parts']} <= names and len(rl['parts']) == 21
    assert sum(s['step'] is not None for s in rl['manual']['slides']) == 37
    files = [im['file'] for s in rl['manual']['slides'] for im in s['images']] + list(rl['img'].values())
    assert all(files), 'a manual picture is missing from the export'
    for f in files:
        assert (RM / 'site' / f).stat().st_size > 1000, f
