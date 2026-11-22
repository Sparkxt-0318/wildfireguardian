"""D0_RULE P-b: 시군구 polygons (boundary=administrative, admin_level=6) from the OSM snapshot of 2025-01-01.

Assembles multipolygon areas with pyosmium and writes a GeoJSON FeatureCollection (WGS84) with name, name:en and
the OSM relation id. Run with python -I, the pbf path as an argument (data kept outside the repository).

    python -I extract_sigungu_osm.py PBF OUT.geojson
"""
import json
import sys

import osmium


class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.f = osmium.geom.GeoJSONFactory()
        self.out = []
        self.failed = []

    def area(self, a):
        t = a.tags
        if t.get('boundary') != 'administrative' or t.get('admin_level') != '6':
            return
        try:
            geom = json.loads(self.f.create_multipolygon(a))
        except Exception as e:                       # noqa: BLE001 - broken rings are reported, not repaired
            self.failed.append({'orig_id': a.orig_id(), 'from_way': a.from_way(), 'name': t.get('name'), 'error': str(e)[:120]})
            return
        self.out.append({'type': 'Feature', 'geometry': geom,
                         'properties': {'name': t.get('name'), 'name_en': t.get('name:en'), 'ref': t.get('ref'),
                                        'osm_relation': a.orig_id() if not a.from_way() else None,
                                        'osm_way': a.orig_id() if a.from_way() else None}})


def main():
    pbf, out = sys.argv[1], sys.argv[2]
    h = H()
    h.apply_file(pbf, locations=True, idx='flex_mem')
    json.dump({'type': 'FeatureCollection',
               'label': 'OpenStreetMap administrative boundaries, snapshot 2025-01-01 (admin_level=6); ODbL',
               'features': h.out, 'failed': h.failed}, open(out, 'w'), ensure_ascii=False)
    print(json.dumps({'features': len(h.out), 'failed': len(h.failed)}))


if __name__ == '__main__':
    main()
