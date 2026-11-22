import sys, osmium
r = osmium.io.Reader(sys.argv[1], osmium.osm.osm_entity_bits.NOTHING)
h = r.header()
print('generator', h.get('generator'))
for k in ('osmosis_replication_timestamp','osmosis_replication_sequence_number','osmosis_replication_base_url','timestamp'):
    print(k, h.get(k))
print('box', h.box())
r.close()
