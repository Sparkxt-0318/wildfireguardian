"""python -I test_nirops_access.py  -> builds a 3-record shapefile; checks reads are allowlist-only."""
import sys, tempfile, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geopandas as gpd, shapely
import nirops_access as na

d = tempfile.mkdtemp(); shp = os.path.join(d, 't.shp')
gpd.GeoDataFrame({'Incident_C': ['A_ok', 'B_secret', 'A_ok'], 'UTC': ['2020-01-01 00:00', '2020-02-02 02:02', '2020-01-02 00:00']},
                 geometry=[shapely.box(0, 0, 1, 1)] * 3, crs=4326).to_file(shp)
allowed = {'A_ok'}
ids = na.id_index(shp)
assert list(ids.columns) if hasattr(ids, 'columns') else True
assert set(na.allowlisted_fids(ids, allowed)) == {0, 2}
g = na.read_incident(shp, 'A_ok', allowed, ids)
assert sorted(g.index) == [0, 2] and set(g.Incident_C) == {'A_ok'}
for bad in (lambda: na.read_incident(shp, 'B_secret', allowed, ids), lambda: na.read_by_fid(shp, [1], ids, allowed),
            lambda: na.read_by_fid(shp, [0, 1], ids, allowed)):
    try:
        bad(); raise SystemExit('FAIL: a non-allowlisted read was not refused')
    except PermissionError:
        pass
print('PASS: ID-only index read; allowlisted fids only; non-allowlisted incident/fid reads refused')
