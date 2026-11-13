#!/usr/bin/env python3
"""CR1 in-season IR harvest, implementing HARVEST_RULE.md (commit 42906d99).

usage: CR1_LOG_SALT=... harvest_cr1.py --root URL_OR_DIR --year 2027 --regions R1,R2 --out DIR [--spacing 2.0]

Run only on the synthetic fixture (test_harvest_cr1.py) until the 2027 season, Hannah's review and the
orchestrator's go. --root may be an http(s) URL or a local directory (fixture mode); both are walked the same way.
"""
import argparse, hashlib, html.parser, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ALLOWED_YEAR = 2027
TAKE = {'.shp', '.shx', '.dbf', '.prj', '.cpg', '.kmz', '.kml', '.zip', '.pdf'}
UA = 'wfg-cr1-harvest/1'


class Blocked(Exception):
    pass


class Refused(Exception):
    pass


class _Hrefs(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v:
                    self.hrefs.append(v)


def utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Source:
    """Lists and reads under a root; local dir (fixture) or http(s). Every relative path is guarded first."""

    def __init__(self, root, year, spacing):
        self.root, self.year, self.spacing = root, year, spacing
        self.http = root.startswith(('http://', 'https://'))
        self.host = urllib.parse.urlsplit(root).netloc if self.http else None
        self._last = 0.0

    def guard(self, rel):
        parts = PurePosixPath(rel).parts
        if any(p in ('..', '') for p in parts) or rel.startswith('/'):
            raise Refused('path escapes root')
        if any(p.lower() == 'protected' for p in parts):
            raise Refused('protected segment')
        if len(parts) >= 2 and parts[1] != str(self.year):
            raise Refused('year segment is not %d' % self.year)

    def _wait(self):
        if self.http:
            d = self.spacing - (time.monotonic() - self._last)
            if d > 0:
                time.sleep(d)
            self._last = time.monotonic()

    def _get(self, rel):
        self.guard(rel)
        if not self.http:
            return Path(self.root, rel)
        self._wait()
        url = self.root.rstrip('/') + '/' + urllib.parse.quote(rel)
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        try:
            r = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise Blocked('HTTP %d' % e.code)
            if e.code == 404:
                return None
            raise
        final = urllib.parse.urlsplit(r.geturl())
        if final.netloc != self.host or 'login' in final.path.lower() or 'protected' in final.path.lower():
            raise Blocked('redirected off the public tree')
        return r

    def listdir(self, rel):
        """Return (dirs, files) names directly under rel, or None if absent."""
        got = self._get(rel)
        if got is None:
            return None
        if not self.http:
            if not got.is_dir():
                return None
            return (sorted(p.name for p in got.iterdir() if p.is_dir()),
                    sorted(p.name for p in got.iterdir() if p.is_file()))
        p = _Hrefs()
        p.feed(got.read().decode('utf-8', 'replace'))
        dirs, files = [], []
        for h in p.hrefs:
            if h.startswith(('?', '/', '#')) or '://' in h or h.startswith('..'):
                continue
            name = urllib.parse.unquote(h)
            (dirs if name.endswith('/') else files).append(name.rstrip('/'))
        return sorted(set(dirs)), sorted(set(files))

    def read(self, rel):
        got = self._get(rel)
        if got is None:
            return None
        return got.read_bytes() if not self.http else got.read()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--year', type=int, required=True)
    ap.add_argument('--regions', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--spacing', type=float, default=2.0)
    a = ap.parse_args(argv)
    if a.year != ALLOWED_YEAR:
        print('REFUSED: --year %d; only %d is allowed (2025 and 2026 are off limits)' % (a.year, ALLOWED_YEAR),
              file=sys.stderr)
        return 2
    salt = os.environ.get('CR1_LOG_SALT')
    if not salt:
        print('REFUSED: CR1_LOG_SALT is not set', file=sys.stderr)
        return 2
    out = Path(a.out).resolve()
    repo = Path(__file__).resolve().parents[3]
    if out == repo or repo in out.parents:
        print('REFUSED: --out is inside the repository', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    statef = out / 'state.json'
    state = json.loads(statef.read_text()) if statef.exists() else {}
    logf = (out / 'run_log.txt').open('a')

    def log(rel, action, extra=''):
        h = hashlib.sha256((salt + rel).encode()).hexdigest()[:16]
        logf.write('%s %s %s %s\n' % (utc(), h, action, extra))

    src = Source(a.root, a.year, a.spacing)
    counts = {}
    status = 'ALL DONE'

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    try:
        for region in [r for r in a.regions.split(',') if r]:
            ry = '%s/%d' % (region, a.year)
            top = src.listdir(ry)
            if top is None:
                log(ry, 'ABSENT'); bump('absent_region_year'); continue
            for inc in top[0]:
                irr = '%s/%s/IR' % (ry, inc)
                try:
                    ir = src.listdir(irr)
                except Refused as e:
                    log(irr, 'REFUSED', str(e)); bump('refused'); continue
                if ir is None:
                    log(irr, 'NO_IR'); bump('no_ir'); continue
                for d in ir[0]:
                    if not (len(d) == 8 and d.isdigit()):
                        log(irr + '/' + d, 'NOT_TAKEN', 'dir'); bump('not_taken'); continue
                    dd = '%s/%s' % (irr, d)
                    try:
                        listing = src.listdir(dd)
                    except Refused as e:
                        log(dd, 'REFUSED', str(e)); bump('refused'); continue
                    for f in (listing or ((), ()))[1]:
                        rel = '%s/%s' % (dd, f)
                        if PurePosixPath(f).suffix.lower() not in TAKE:
                            log(rel, 'NOT_TAKEN'); bump('not_taken'); continue
                        data = src.read(rel)
                        if data is None:
                            log(rel, 'HTTP_404'); bump('404'); continue
                        h = hashlib.sha256(data).hexdigest()
                        prev = state.get(rel)
                        if prev and prev['sha256'] == h:
                            log(rel, 'UNCHANGED'); bump('unchanged'); continue
                        dest_rel = rel
                        if prev:
                            n = 2
                            while ('%s.v%d' % (rel, n)) in state:
                                n += 1
                            dest_rel = '%s.v%d' % (rel, n)
                        dest = out / 'files' / dest_rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
                        state[dest_rel] = {'sha256': h, 'size': len(data), 'first_seen_utc': utc()}
                        log(rel, 'NEW' if not prev else 'CHANGED_KEPT_BOTH'); bump('new' if not prev else 'changed')
    except Blocked as e:
        status = 'BLOCKED (%s)' % e
    finally:
        statef.write_text(json.dumps(state, indent=1, sort_keys=True))
        logf.write('%s RUN %s %s\n' % (utc(), status, json.dumps(counts, sort_keys=True)))
        logf.close()
    print(status, json.dumps(counts, sort_keys=True))
    return 0 if status == 'ALL DONE' else 3


if __name__ == '__main__':
    sys.exit(main())
