#!/usr/bin/env python3
"""CR1 in-season IR harvest, implementing HARVEST_RULE.md (commit 42906d99).

v2 (13 Nov): fixes Hannah's review FAIL (ledger row 68):
  E  redirects are never followed (no-redirect opener); any 3xx is BLOCKED; directories are requested with a trailing /.
  A  change detection compares against the LATEST stored version of each path, not the first.
  F  an unchanged tree makes no downloads: size comes from the listing (local) or HEAD Content-Length (http);
     a file is downloaded only when new or its size differs from the latest version.
  B  the --out guard uses the real repository root (git rev-parse --show-toplevel, fallback parents[4]).
  D  any other HTTP error (incl. 429), URLError or timeout stops the run with status ERROR (...); no retry.
v3 (13 Nov): fixes the row-73 re-review FAIL:
  D' body reads are wrapped too (http.client.HTTPException, OSError -> ERROR); a catch-all makes a crash end as
     ERROR (<class>), never ALL DONE.
  N  HEAD 404 means absent; HEAD 200 without Content-Length means size unknown -> download and compare sha with
     the latest version (idempotence kept by sha).

usage: CR1_LOG_SALT=... harvest_cr1.py --root URL_OR_DIR --year 2027 --regions R1,R2 --out DIR [--spacing 2.0]

Run only on the synthetic fixture (test_harvest_cr1.py) until the 2027 season, Hannah's review and the
orchestrator's go. --root may be an http(s) URL or a local directory (fixture mode); both are walked the same way.
"""
import argparse, hashlib, html.parser, http.client, json, os, socket, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ALLOWED_YEAR = 2027
TAKE = {'.shp', '.shx', '.dbf', '.prj', '.cpg', '.kmz', '.kml', '.zip', '.pdf'}
UA = 'wfg-cr1-harvest/1'


class Blocked(Exception):
    pass


class Stop(Exception):
    pass


class Refused(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # urllib then raises HTTPError(3xx); we never follow


_OPENER = urllib.request.build_opener(_NoRedirect())


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


def repo_root():
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.run(['git', '-C', str(here), 'rev-parse', '--show-toplevel'],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return Path(__file__).resolve().parents[4]


class Source:
    """Lists and reads under a root; local dir (fixture) or http(s). Every relative path is guarded first."""

    def __init__(self, root, year, spacing):
        self.root, self.year, self.spacing = root, year, spacing
        self.http = root.startswith(('http://', 'https://'))
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
        d = self.spacing - (time.monotonic() - self._last)
        if d > 0:
            time.sleep(d)
        self._last = time.monotonic()

    def _open(self, rel, method='GET', is_dir=False):
        self.guard(rel)
        self._wait()
        url = self.root.rstrip('/') + '/' + urllib.parse.quote(rel) + ('/' if is_dir else '')
        req = urllib.request.Request(url, method=method, headers={'User-Agent': UA})
        try:
            return _OPENER.open(req, timeout=120)
        except urllib.error.HTTPError as e:
            if 300 <= e.code < 400:
                raise Blocked('HTTP %d redirect not followed' % e.code)
            if e.code in (401, 403):
                raise Blocked('HTTP %d' % e.code)
            if e.code == 404:
                return None
            raise Stop('HTTP %d' % e.code)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            raise Stop(type(e).__name__)

    @staticmethod
    def _body(r):
        try:
            return r.read()
        except (http.client.HTTPException, OSError) as e:
            raise Stop('body read: %s' % type(e).__name__)

    def listdir(self, rel):
        """Return (dirs, files) names directly under rel, or None if absent."""
        if not self.http:
            self.guard(rel)
            p = Path(self.root, rel)
            if not p.is_dir():
                return None
            return (sorted(c.name for c in p.iterdir() if c.is_dir()),
                    sorted(c.name for c in p.iterdir() if c.is_file()))
        r = self._open(rel, is_dir=True)
        if r is None:
            return None
        p = _Hrefs()
        p.feed(self._body(r).decode('utf-8', 'replace'))
        dirs, files = [], []
        for h in p.hrefs:
            if h.startswith(('?', '/', '#')) or '://' in h or h.startswith('..'):
                continue
            name = urllib.parse.unquote(h)
            (dirs if name.endswith('/') else files).append(name.rstrip('/'))
        return sorted(set(dirs)), sorted(set(files))

    ABSENT = object()

    def size(self, rel):
        """Size without downloading: stat (local) or HEAD Content-Length (http).
        Returns Source.ABSENT if the file is absent (404), None if present but size unknown, else an int."""
        if not self.http:
            self.guard(rel)
            p = Path(self.root, rel)
            return p.stat().st_size if p.is_file() else Source.ABSENT
        r = self._open(rel, method='HEAD')
        if r is None:
            return Source.ABSENT
        cl = r.headers.get('Content-Length')
        return int(cl) if cl and cl.isdigit() else None

    def read(self, rel):
        if not self.http:
            self.guard(rel)
            p = Path(self.root, rel)
            return p.read_bytes() if p.is_file() else None
        r = self._open(rel)
        return None if r is None else self._body(r)


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
    repo = repo_root()
    if out == repo or repo in out.parents:
        print('REFUSED: --out is inside the repository', file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    statef = out / 'state.json'
    state = json.loads(statef.read_text()) if statef.exists() else {'files': {}, 'latest': {}}
    files, latest = state['files'], state['latest']
    logf = (out / 'run_log.txt').open('a')

    def log(rel, action, extra=''):
        h = hashlib.sha256((salt + rel).encode()).hexdigest()[:16]
        logf.write('%s %s %s %s\n' % (utc(), h, action, extra))

    src = Source(a.root, a.year, a.spacing)
    counts = {}
    status = 'ALL DONE'

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    def take(rel):
        prev = files.get(latest[rel]) if rel in latest else None
        size = src.size(rel)
        if size is Source.ABSENT:
            log(rel, 'HTTP_404'); bump('404'); return
        if size is not None and prev is not None and size == prev['size']:
            log(rel, 'UNCHANGED'); bump('unchanged'); return
        data = src.read(rel)
        if data is None:
            log(rel, 'HTTP_404'); bump('404'); return
        h = hashlib.sha256(data).hexdigest()
        if prev is not None and h == prev['sha256']:
            log(rel, 'UNCHANGED'); bump('unchanged'); return
        dest_rel = rel
        if prev is not None:
            n = 2
            while ('%s.v%d' % (rel, n)) in files:
                n += 1
            dest_rel = '%s.v%d' % (rel, n)
        dest = out / 'files' / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        files[dest_rel] = {'sha256': h, 'size': len(data), 'first_seen_utc': utc()}
        latest[rel] = dest_rel
        log(rel, 'NEW' if prev is None else 'CHANGED_KEPT_BOTH'); bump('new' if prev is None else 'changed')

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
                        take(rel)
    except Blocked as e:
        status = 'BLOCKED (%s)' % e
    except Stop as e:
        status = 'ERROR (%s)' % e
    except Exception as e:  # never report ALL DONE after an unexpected crash
        status = 'ERROR (%s)' % type(e).__name__
    finally:
        statef.write_text(json.dumps(state, indent=1, sort_keys=True))
        logf.write('%s RUN %s %s\n' % (utc(), status, json.dumps(counts, sort_keys=True)))
        logf.close()
    print(status, json.dumps(counts, sort_keys=True))
    return 0 if status == 'ALL DONE' else 3


if __name__ == '__main__':
    sys.exit(main())
