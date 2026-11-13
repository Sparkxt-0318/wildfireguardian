#!/usr/bin/env python3
"""Provenance check of an OSM .pbf (Hannah, verifier). Read-only, no network. Needs pyosmium.

Run UNMODIFIED where the pbf is:
    python3 -I pbf_provenance_check.py PBF [--sample 40] > pbf_check_out.json

Prints the file sha256 and md5 (Geofabrik publishes .md5), size, header fields, object counts, max ids,
the newest object timestamp, and a deterministic sample of ways and nodes (id, version, timestamp) chosen
by sha256(id) order, so the verifier can compare them with the OSM API's own history at the snapshot time.
No coordinates, names or tags are printed.
"""
import argparse, hashlib, json, sys
import osmium


def digests(path):
    s, m = hashlib.sha256(), hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            s.update(b); m.update(b)
    return s.hexdigest(), m.hexdigest()


class H(osmium.SimpleHandler):
    def __init__(self, sample):
        super().__init__()
        self.sample = sample
        self.n = {'node': 0, 'way': 0, 'relation': 0}
        self.maxid = {'node': 0, 'way': 0, 'relation': 0}
        self.newest = None
        self.objs = {'node': [], 'way': []}

    def _see(self, kind, o):
        self.n[kind] += 1
        self.maxid[kind] = max(self.maxid[kind], o.id)
        ts = o.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        if self.newest is None or ts > self.newest:
            self.newest = ts
        if kind in self.objs:
            k = hashlib.sha256(('%s/%d' % (kind, o.id)).encode()).hexdigest()
            L = self.objs[kind]
            L.append((k, o.id, o.version, ts))
            if len(L) > 20 * self.sample:      # bounded memory: keep the smallest sha256 keys only
                L.sort(); del L[self.sample:]

    def node(self, o): self._see('node', o)
    def way(self, o): self._see('way', o)
    def relation(self, o): self._see('relation', o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pbf')
    ap.add_argument('--sample', type=int, default=40)
    a = ap.parse_args()
    sha, md5 = digests(a.pbf)
    hdr = osmium.io.Reader(a.pbf, osmium.osm.osm_entity_bits.NOTHING).header()
    keys = ['generator', 'osmosis_replication_timestamp', 'osmosis_replication_sequence_number',
            'osmosis_replication_base_url', 'timestamp']
    h = H(a.sample)
    h.apply_file(a.pbf)
    out = {'script': 'pbf_provenance_check.py (Hannah)', 'sha256': sha, 'md5': md5,
           'header': {k: hdr.get(k, '') for k in keys}, 'counts': h.n, 'max_id': h.maxid,
           'newest_object_timestamp': h.newest}
    for kind in ('way', 'node'):
        sel = sorted(h.objs[kind])[:a.sample]
        out['sample_' + kind] = [{'id': i, 'version': v, 'timestamp': t} for _, i, v, t in sorted(sel, key=lambda x: x[1])]
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == '__main__':
    main()
