import csv, io, sys, re, collections
raw = open(sys.argv[1], 'rb').read()
res = {}
for enc in ('utf-8', 'cp949', 'euc-kr'):
    try: raw.decode(enc); res[enc] = 'ok'
    except UnicodeDecodeError as e: res[enc] = 'fail at %d' % e.start
print('decode test:', res)
text = raw.decode('cp949')
print('BOM:', raw[:3] == b'\xef\xbb\xbf', 'CRLF:', b'\r\n' in raw)
rows = list(csv.reader(io.StringIO(text)))
hdr, body = rows[0], [r for r in rows[1:] if any(c.strip() for c in r)]
print('header (%d):' % len(hdr), hdr)
print('data rows:', len(body), 'ragged:', sum(len(r) != len(hdr) for r in body))
for i, h in enumerate(hdr):
    vals = [r[i] for r in body if i < len(r)]
    sample = vals[:3]
    print('  %-20s sample=%s' % (h, sample))
dms = re.compile(r"^\s*\d{2,3}\s*[°도]\s*\d{1,2}\s*['분′]\s*\d{1,2}(\.\d+)?\s*[\"초″]?\s*$")
for i, h in enumerate(hdr):
    vals = [r[i] for r in body if i < len(r) and r[i].strip()]
    if vals and sum(bool(dms.match(v)) for v in vals) > 0.5 * len(vals):
        print('DMS-like column:', h, 'matches', sum(bool(dms.match(v)) for v in vals), '/', len(vals), 'non-matching sample:', [v for v in vals if not dms.match(v)][:3])
