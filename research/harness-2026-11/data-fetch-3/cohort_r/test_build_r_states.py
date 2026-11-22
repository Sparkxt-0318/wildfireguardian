#!/usr/bin/env python3
"""Fixture test for build_r_states.py (Hannah's condition 6). No real NIROPS data.
A tiny shapefile has one allowlisted record (R-like) and one non-allowlisted record. A spy on pyogrio.read_dataframe
(the only reader nirops_access uses) proves: the non-allowlisted fid is never read with geometry or attributes; the
only all-record read is the Incident_C column alone; the output holds only the R event.
Run: python -I test_build_r_states.py"""
import csv, hashlib, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
import pyogrio  # noqa: E402
import geopandas as gpd  # noqa: E402
from shapely.geometry import box  # noqa: E402
import build_r_states as B  # noqa: E402

ACCESS = HERE.parent / 'nirops_access' / 'nirops_access.py'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    fails = []
    def check(name, ok):
        print(('PASS ' if ok else 'FAIL ') + name); (fails.append(name) if not ok else None)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # two records, EPSG:4326 boxes; R one at two survey times
        gdf = gpd.GeoDataFrame({'Incident_C': ['XX-TST-000001_Alpha', 'XX-TST-000001_Alpha', 'XX-TST-000002_Beta'],
                                'UTC': ['2024-08-01 05:00:00', '2024-08-02 05:00:00', '2024-08-01 05:00:00'],
                                'SECRET': ['a', 'a', 'must-not-be-read']},
                               geometry=[box(-115.20, 44.14, -115.19, 44.15), box(-115.20, 44.14, -115.18, 44.16),
                                         box(-110.0, 43.0, -109.9, 43.1)], crs=4326)
        shp = td / 'fix' / 'fix.shp'; shp.parent.mkdir(); gdf.to_file(shp)
        allow = td / 'R.csv'
        with open(allow, 'w', newline='') as f:
            w = csv.writer(f, lineterminator='\n'); w.writerow(['Incident_C', 'irwinid']); w.writerow(['XX-TST-000001_Alpha', 'x'])
        # event grid (EPSG:5070) around the R box
        from pyproj import Transformer
        x, y = Transformer.from_crs(4326, 5070, always_xy=True).transform(-115.19, 44.15)
        x0, y1 = np.floor(x / 375) * 375 - 3000, np.ceil(y / 375) * 375 + 3000
        ev = [dict(id='XX-TST-000001_Alpha', epsg=5070, width=24, height=24, transform=[375.0, 0, x0, 0, -375.0, y1]),
              dict(id='XX-TST-000002_Beta', epsg=5070, width=4, height=4, transform=[375.0, 0, 0, 0, -375.0, 0])]
        ws = td / 'ws'; (ws / 'environment').mkdir(parents=True)
        evp = ws / 'environment' / 'events.json'; evp.write_text(json.dumps(ev))
        pins = td / 'pins.json'; pins.write_text(json.dumps({'environment/events.json': sha(evp)}))
        out = td / 'out'

        seen = []
        real = pyogrio.read_dataframe
        def spy(path, *a, **k):
            seen.append(dict(fids=None if k.get('fids') is None else sorted(map(int, k['fids'])), columns=k.get('columns'),
                             read_geometry=k.get('read_geometry', True), where=k.get('where')))
            return real(path, *a, **k)
        pyogrio.read_dataframe = spy
        try:
            rc = B.main(['--shp', str(shp), '--allowlist', str(allow), '--nirops-access', str(ACCESS), '--events', str(evp),
                         '--pins', str(pins), '--pins-root', str(ws), '--out', str(out),
                         '--expect-allowlist-sha', sha(allow), '--expect-pins-sha', sha(pins)])
        finally:
            pyogrio.read_dataframe = real
        check('exit 0', rc == 0)
        beta_fid = 2
        full_reads = [s for s in seen if s['fids'] is None]
        check('only full-table read is Incident_C alone, no geometry, no where',
              all(s['columns'] == ['Incident_C'] and s['read_geometry'] is False and s['where'] is None for s in full_reads) and len(full_reads) == 1)
        check('non-allowlisted fid never read', all(beta_fid not in (s['fids'] or []) for s in seen))
        check('R fids read by fid', any(s['fids'] == [0, 1] for s in seen))
        man = json.loads((out / 'PERIMETER_MANIFEST.json').read_text())
        check('output holds only the R event', sorted(man['events']) == ['XX-TST-000001_Alpha'] and not (out / 'XX-TST-000002_Beta').exists())
        st = np.load(out / 'XX-TST-000001_Alpha' / 'states.npz', allow_pickle=False)
        check('2 survey times, cumulative, non-empty', st['states'].shape[0] == 2 and st['states'][1].sum() >= st['states'][0].sum() > 0)
        check('states sha recorded', man['events']['XX-TST-000001_Alpha']['states_sha256'] == sha(out / 'XX-TST-000001_Alpha' / 'states.npz'))
        logtxt = (out / 'access_log.txt').read_text()
        check('log lists id_index and the R read with its fids', 'id_index' in logtxt and 'Incident_C=XX-TST-000001_Alpha' in logtxt and 'fids=0,1' in logtxt)
        check('log never names the non-allowlisted record', 'Beta' not in logtxt and 'must-not-be-read' not in logtxt)
        # refusals
        check('refuses wrong allowlist sha', _exit(lambda: B.main(['--shp', str(shp), '--allowlist', str(allow), '--nirops-access', str(ACCESS),
              '--events', str(evp), '--pins', str(pins), '--pins-root', str(ws), '--out', str(td / 'o2'), '--expect-pins-sha', sha(pins)])))
        check('refuses non-empty out', _exit(lambda: B.main(['--shp', str(shp), '--allowlist', str(allow), '--nirops-access', str(ACCESS),
              '--events', str(evp), '--pins', str(pins), '--pins-root', str(ws), '--out', str(out),
              '--expect-allowlist-sha', sha(allow), '--expect-pins-sha', sha(pins)])))
        check('refuses out inside the pinned workspace', _exit(lambda: B.main(['--shp', str(shp), '--allowlist', str(allow), '--nirops-access', str(ACCESS),
              '--events', str(evp), '--pins', str(pins), '--pins-root', str(ws), '--out', str(ws / 'x'),
              '--expect-allowlist-sha', sha(allow), '--expect-pins-sha', sha(pins)])))
        evp.write_text(json.dumps(ev) + ' ')
        check('refuses when a pinned file changed (pins check before)', _exit(lambda: B.main(['--shp', str(shp), '--allowlist', str(allow),
              '--nirops-access', str(ACCESS), '--events', str(evp), '--pins', str(pins), '--pins-root', str(ws), '--out', str(td / 'o3'),
              '--expect-allowlist-sha', sha(allow), '--expect-pins-sha', sha(pins)])))
    print('ALL PASS' if not fails else f'FAILURES: {len(fails)}')
    return 1 if fails else 0


def _exit(fn):
    try:
        fn(); return False
    except SystemExit as e:
        return e.code not in (0, None)


if __name__ == '__main__':
    sys.exit(main())
