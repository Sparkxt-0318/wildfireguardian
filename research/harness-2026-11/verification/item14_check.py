#!/usr/bin/env python3
"""Independent check of the item-14 weather comparison (Hannah, verifier). Read-only, stdlib only, no network.

Run UNMODIFIED in the container that holds both the owner's files and the rebuild:
    python3 -I item14_check.py --owner DIR_WITH_OWNER_WEATHER --rebuild DIR_WITH_REBUILD_WEATHER \
        [--requests weather_requests.csv] [--event MT-BDF-006269_AlderCreek] > item14_check_out.json

For every file present in either directory it prints: size, full sha256, mtime (UTC) and whether the two paths are
the SAME file on disk (same device+inode, i.e. a hardlink or the same path). Byte-identical files that are the same
inode, or rebuild files older than the event's first logged request, would mean the "rebuild" is a copy, not a rebuild.
From the request log it prints, for the event only: row count, HTTP status counts and first/last request time.
It prints no file content.
"""
import argparse, csv, datetime, hashlib, json, os, sys


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def info(p):
    st = os.stat(p)
    return {'bytes': st.st_size, 'sha256': sha(p),
            'mtime_utc': datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc).isoformat(timespec='seconds'),
            'dev_ino': [st.st_dev, st.st_ino], 'nlink': st.st_nlink}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--owner', required=True)
    ap.add_argument('--rebuild', required=True)
    ap.add_argument('--requests')
    ap.add_argument('--event', default='MT-BDF-006269_AlderCreek')
    a = ap.parse_args()
    out = {'script': 'item14_check.py (Hannah)', 'owner_dir': os.path.abspath(a.owner), 'rebuild_dir': os.path.abspath(a.rebuild),
           'owner_dir_is_rebuild_dir': os.path.realpath(a.owner) == os.path.realpath(a.rebuild)}
    names = sorted(set(os.listdir(a.owner)) | set(os.listdir(a.rebuild)))
    files = {}
    for n in names:
        po, pr = os.path.join(a.owner, n), os.path.join(a.rebuild, n)
        o = info(po) if os.path.isfile(po) else None
        r = info(pr) if os.path.isfile(pr) else None
        files[n] = {'owner': o, 'rebuild': r,
                    'identical': bool(o and r and o['sha256'] == r['sha256']),
                    'same_file_on_disk': bool(o and r and os.path.samefile(po, pr))}
    out['files'] = files
    if a.requests:
        rows = [row for row in csv.DictReader(open(a.requests, newline='')) if a.event in ' '.join(str(v) for v in row.values())]
        st = {}
        for row in rows:
            k = next((row[c] for c in row if 'status' in c.lower()), '?')
            st[k] = st.get(k, 0) + 1
        tcol = next((c for c in (rows[0] if rows else {}) if 'time' in c.lower()), None)
        times = sorted(row[tcol] for row in rows) if tcol else []
        out['requests'] = {'columns': list(rows[0].keys()) if rows else [], 'rows_for_event': len(rows), 'status_counts': st,
                           'first': times[0] if times else None, 'last': times[-1] if times else None}
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == '__main__':
    main()
