#!/usr/bin/env python3
"""Read a large remote zip through HTTP Range requests, without downloading or storing the whole file.

The URL is NEVER stored in this file. Pass it with --url or through the environment variable REMOTE_ZIP_URL.
Google Drive share links (https://drive.google.com/file/d/<id>/view...) are turned into the direct download URL.

  remote_zip.py sha256  [--url URL]                         stream the whole file through sha256 (nothing written)
  remote_zip.py list    [--url URL] [--out listing.tsv]     central directory: name, size, compressed size, crc32, method
  remote_zip.py extract [--url URL] --dest DIR PATTERN...   extract the members matching any glob PATTERN (fnmatch on the
                                                      full member name), checking each CRC-32; writes DIR/<member name>

Stdlib only. Supports ZIP64, stored (0) and deflate (8) members. The script refuses member names that are absolute
or contain '..'.
"""
import argparse, fnmatch, hashlib, os, re, struct, sys, time, urllib.request, zlib

UA = {'User-Agent': 'wfg-data-fetch/1'}


def direct(url):
    m = re.search(r'drive\.google\.com/file/d/([^/?#]+)', url) or re.search(r'[?&]id=([^&#]+)', url)
    if m and 'google' in url:
        return f'https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t'
    return url


def get(url, start, end, attempts=6):
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=dict(UA, Range=f'bytes={start}-{end}'))
            with urllib.request.urlopen(req, timeout=300) as r:
                if r.status != 206:
                    raise RuntimeError(f'server ignored Range (HTTP {r.status})')
                return r.read()
        except Exception as ex:
            if i == attempts - 1:
                raise
            print(f'  retry {i + 1} ({type(ex).__name__}: {ex})', file=sys.stderr); time.sleep(2 ** (i + 1))


def size_of(url):
    req = urllib.request.Request(url, headers=dict(UA, Range='bytes=0-0'))
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.headers['Content-Range'].split('/')[-1])


def central_directory(url):
    total = size_of(url)
    tail = get(url, max(0, total - 66000), total - 1)
    i = tail.rfind(b'PK\x05\x06')
    if i < 0:
        sys.exit('no end-of-central-directory record')
    n, cd_size, cd_off = struct.unpack('<HII', tail[i + 10:i + 20])
    j = tail.rfind(b'PK\x06\x06')  # ZIP64 end record
    if j >= 0 and (n == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF):
        n, cd_size, cd_off = struct.unpack('<QQQ', tail[j + 32:j + 56])
    cd = get(url, cd_off, cd_off + cd_size - 1)
    out, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b'PK\x01\x02':
        (method, crc, csize, usize, ln, le, lc, off) = (struct.unpack('<H', cd[p + 10:p + 12])[0],
            *struct.unpack('<III', cd[p + 16:p + 28]), *struct.unpack('<HHH', cd[p + 28:p + 34]),
            struct.unpack('<I', cd[p + 42:p + 46])[0])
        name = cd[p + 46:p + 46 + ln].decode('utf-8', 'replace')
        extra = cd[p + 46 + ln:p + 46 + ln + le]
        q = 0
        while q + 4 <= len(extra):  # ZIP64 extended information
            hid, hl = struct.unpack('<HH', extra[q:q + 4]); body = extra[q + 4:q + 4 + hl]; k = 0
            if hid == 1:
                if usize == 0xFFFFFFFF: usize = struct.unpack('<Q', body[k:k + 8])[0]; k += 8
                if csize == 0xFFFFFFFF: csize = struct.unpack('<Q', body[k:k + 8])[0]; k += 8
                if off == 0xFFFFFFFF: off = struct.unpack('<Q', body[k:k + 8])[0]; k += 8
            q += 4 + hl
        out.append(dict(name=name, size=usize, csize=csize, crc=crc, method=method, offset=off))
        p += 46 + ln + le + lc
    return total, out


def extract(url, m, dest):
    name = m['name']
    if name.startswith('/') or '..' in name.split('/'):
        raise ValueError(f'unsafe member name {name!r}')
    path = os.path.join(dest, name)
    if name.endswith('/'):
        os.makedirs(path, exist_ok=True); return
    if os.path.exists(path) and os.path.getsize(path) == m['size']:
        return  # already extracted (resume); CRC was checked when it was written
    # One request for small members: local header + name + a generous extra field + the data.
    guess = 30 + len(name.encode()) + 1024
    head = get(url, m['offset'], m['offset'] + guess + (m['csize'] if m['csize'] < (8 << 20) else 0) - 1)
    ln, le = struct.unpack('<HH', head[26:30])
    start = m['offset'] + 30 + ln + le
    pre = head[30 + ln + le:30 + ln + le + m['csize']] if m['csize'] < (8 << 20) else b''
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    d = zlib.decompressobj(-15) if m['method'] == 8 else None
    if m['method'] not in (0, 8):
        raise ValueError(f'unsupported compression method {m["method"]} for {name}')
    crc, step, pos = 0, 64 << 20, start
    with open(path + '.part', 'wb') as f:
        if pre:
            data = d.decompress(pre) if d else pre
            crc = zlib.crc32(data, crc); f.write(data); pos += len(pre)
        while pos < start + m['csize']:
            chunk = get(url, pos, min(pos + step, start + m['csize']) - 1); pos += len(chunk)
            data = d.decompress(chunk) if d else chunk
            crc = zlib.crc32(data, crc); f.write(data)
        if d:
            data = d.flush(); crc = zlib.crc32(data, crc); f.write(data)
    if crc != m['crc']:
        os.remove(path + '.part'); raise ValueError(f'CRC mismatch for {name}')
    os.replace(path + '.part', path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['sha256', 'list', 'extract'])
    ap.add_argument('patterns', nargs='*')
    ap.add_argument('--url', default=os.environ.get('REMOTE_ZIP_URL'), help='or set REMOTE_ZIP_URL')
    ap.add_argument('--out'); ap.add_argument('--dest')
    ap.add_argument('--jobs', type=int, default=8, help='parallel member downloads (default 8)')
    a = ap.parse_args()
    if not a.url:
        sys.exit('give the URL as an argument or in REMOTE_ZIP_URL')
    url = direct(a.url)
    if a.cmd == 'sha256':
        total, h, pos, step = size_of(url), hashlib.sha256(), 0, 256 << 20
        while pos < total:
            chunk = get(url, pos, min(pos + step, total) - 1); h.update(chunk); pos += len(chunk)
            print(f'  {pos / total:6.1%}', file=sys.stderr, flush=True)
        print(f'{h.hexdigest()}  size={total}')
        return
    total, members = central_directory(url)
    if a.cmd == 'list':
        rows = ['name\tsize\tcompressed\tcrc32\tmethod'] + [
            f"{m['name']}\t{m['size']}\t{m['csize']}\t{m['crc']:08x}\t{m['method']}" for m in members]
        (open(a.out, 'w').write('\n'.join(rows) + '\n') if a.out else print('\n'.join(rows)))
        print(f'{len(members)} members, archive {total} bytes, uncompressed {sum(m["size"] for m in members)} bytes',
              file=sys.stderr)
        return
    if not a.dest or not a.patterns:
        sys.exit('extract needs --dest and at least one PATTERN')
    sel = [m for m in members if any(fnmatch.fnmatchcase(m['name'], p) for p in a.patterns)]
    print(f'{len(sel)} members, {sum(m["size"] for m in sel)} bytes uncompressed', file=sys.stderr)
    from concurrent.futures import ThreadPoolExecutor
    done = 0
    with ThreadPoolExecutor(a.jobs) as pool:
        for _ in pool.map(lambda m: extract(url, m, a.dest), sel):
            done += 1
            if done % 200 == 0:
                print(f'  {done}/{len(sel)}', file=sys.stderr, flush=True)
    print(f'extracted {len(sel)} members into {a.dest} (CRC-32 checked)')


if __name__ == '__main__':
    main()
