import csv, io, sys, collections
rows = list(csv.reader(io.StringIO(open(sys.argv[1], 'rb').read().decode('cp949'))))
h, body = rows[0], rows[1:]
ix = [h.index(k) for k in ('북쪽위도', '북위분', '북위초', '동경도', '동경분', '동경초')]
def status(r):
    v = [r[i].strip() for i in ix]
    if not all(v): return 'blank'
    try: f = [float(x) for x in v]
    except ValueError: return 'invalid'
    ld, lm, ls, od, om, os_ = f
    lat, lon = ld + lm/60 + ls/3600, od + om/60 + os_/3600
    ok = 33 <= lat <= 39 and 124 <= lon <= 132 and lm < 60 and ls < 60 and om < 60 and os_ < 60
    return 'valid' if ok else 'invalid'
gb = [r for r in body if r[0].startswith(('경북', '경상북도'))]
print('경북 rows', len(gb), dict(collections.Counter(status(r) for r in gb)))
for sgg in ('의성', '안동', '청송', '영양', '영덕', '울진'):
    sel = [r for r in gb if (r[0].split() + ['', ''])[1].startswith(sgg)]
    print(sgg, len(sel), dict(collections.Counter(status(r) for r in sel)))
other = collections.Counter((r[0].split() + ['', ''])[1] for r in gb)
print('all 경북 시군구 tokens:', dict(other))
