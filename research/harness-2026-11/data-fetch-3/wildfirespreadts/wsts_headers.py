"""For each WildfireSpreadTS fire folder, read only the GeoTIFF header of its first day (partial inflate of ~64 KB)."""
import csv, struct, sys, zlib, json, urllib.request
from concurrent.futures import ThreadPoolExecutor
URL = 'https://zenodo.org/api/records/8006177/files/WildfireSpreadTS.zip/content'
sys.path.insert(0, '/home/user/wildfireguardian/research/harness-2026-11/data-fetch-3')
import remote_zip as rz
total, members = rz.central_directory(URL)
first = {}
for m in members:
    p = m['name'].split('/')
    if len(p) == 3 and p[2].endswith('.tif'):
        k = (p[0], p[1]); first.setdefault(k, []).append(m)
def tiff_tags(buf):
    bo = '<' if buf[:2] == b'II' else '>'
    off = struct.unpack(bo + 'I', buf[4:8])[0]; n = struct.unpack(bo + 'H', buf[off:off + 2])[0]
    tags = {}
    for i in range(n):
        e = buf[off + 2 + 12 * i: off + 14 + 12 * i]
        tag, typ, cnt = struct.unpack(bo + 'HHI', e[:8])
        sz = {1: 1, 2: 1, 3: 2, 4: 4, 12: 8, 16: 8}.get(typ, 4) * cnt
        data = e[8:8 + sz] if sz <= 4 else buf[struct.unpack(bo + 'I', e[8:12])[0]:][:sz]
        fmt = {3: 'H', 4: 'I', 12: 'd', 16: 'Q'}.get(typ)
        tags[tag] = struct.unpack(bo + fmt * cnt, data) if fmt and len(data) == sz else data
    return tags
def geokey(k, key):
    for i in range(4, len(k), 4):
        if k[i] == key and k[i + 1] == 0: return k[i + 3]
    return None
def one(item):
    (y, f), ms = item
    ms = sorted(ms, key=lambda m: m['name']); m = ms[0]
    head = rz.get(URL, m['offset'], m['offset'] + 30 + len(m['name']) + 1024 + 65536)
    ln, le = struct.unpack('<HH', head[26:30]); raw = head[30 + ln + le:]
    buf = zlib.decompressobj(-15).decompress(raw)
    t = tiff_tags(buf)
    w, h = t[256][0], t[257][0]; scale = t.get(33550); tie = t.get(33922); bands = t.get(277, (None,))[0]
    x0, y0 = tie[3], tie[4]; sx, sy = scale[0], scale[1]
    return dict(year=y, fire=f, days=len(ms), first=ms[0]['name'].split('/')[-1][:10], last=ms[-1]['name'].split('/')[-1][:10],
                width=w, height=h, bands=bands, x0=x0, y1=y0, x1=x0 + w * sx, y0=y0 - h * sy, epsg=geokey(t.get(34735, ()), 3072) or geokey(t.get(34735, ()), 2048))
with ThreadPoolExecutor(4) as pool:
    rows = list(pool.map(one, sorted(first.items())))
with open(sys.argv[1], 'w', newline='') as fh:
    w = csv.DictWriter(fh, rows[0].keys()); w.writeheader(); w.writerows(rows)
print(len(rows), rows[0])
