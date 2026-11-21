import csv, io, sys
rows = list(csv.reader(io.StringIO(open(sys.argv[1], 'rb').read().decode('cp949'))))
h, body = rows[0], rows[1:]
ix = {k: h.index(k) for k in ('북쪽위도', '북위분', '북위초', '동경도', '동경분', '동경초')}
bad, blank, nonint, ok, lats, lons = [], 0, 0, 0, [], []
for n, r in enumerate(body, 2):
    v = [r[ix[k]].strip() for k in ix]
    if not all(v): blank += 1; continue
    try: f = [float(x) for x in v]
    except ValueError: bad.append((n, v)); continue
    if any(x != int(x) for x in f): nonint += 1
    ld, lm, ls, od, om, os_ = f
    lat, lon = ld + lm / 60 + ls / 3600, od + om / 60 + os_ / 3600
    if not (33 <= lat <= 39 and 124 <= lon <= 132 and lm < 60 and ls < 60 and om < 60 and os_ < 60): bad.append((n, v)); continue
    ok += 1; lats.append(lat); lons.append(lon)
print('rows', len(body), 'valid DMS', ok, 'blank', blank, 'invalid', len(bad), 'fractional seconds rows', nonint)
print('lat range %.4f..%.4f lon range %.4f..%.4f' % (min(lats), max(lats), min(lons), max(lons)))
print('invalid sample:', bad[:5])
gb = sum(1 for r in body if r[0].startswith(('경북', '경상북도')))
print('경북 rows:', gb, '| datum stated in file: none (no datum column/header)')
dates = sorted(r[h.index('점검일')] for r in body if r[h.index('점검일')].strip())
print('점검일 range:', dates[0], '..', dates[-1])
