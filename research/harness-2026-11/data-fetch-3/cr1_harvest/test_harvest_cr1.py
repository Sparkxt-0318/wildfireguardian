#!/usr/bin/env python3
"""Synthetic-fixture tests for harvest_cr1.py. No external network: local directories and a 127.0.0.1 test server only.
Run: python3 -I test_harvest_cr1.py"""
import http.server, json, os, sys, tempfile, threading
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harvest_cr1 as H  # noqa: E402

SALT = 'test-salt-only'
INC1 = 'nrcc/2027/2027_FAKEONE_MT-XXX-000001'


def make_fixture(root):
    def put(rel, data=b'x'):
        p = Path(root, rel); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    put(INC1 + '/IR/20270715/fake_heat_perimeter.shp', b'shp1')
    put(INC1 + '/IR/20270715/fake_heat_perimeter.dbf', b'dbf1')
    put(INC1 + '/IR/20270715/notes.docx', b'skip')
    put(INC1 + '/IR/20270716/fake.kmz', b'kmz1')
    put(INC1 + '/IR/misc/fake.kmz', b'skip')
    put('nrcc/2027/2027_FAKETWO_ID-YYY-000002/GIS/fake.shp', b'no ir')
    put('nrcc/2026/2026_OFFLIMITS/IR/20260701/must_not_read.shp', b'never')
    put('nrcc/2027/protected/IR/20270701/must_not_read.shp', b'never')


class Handler(http.server.SimpleHTTPRequestHandler):
    """Fixture server. Records every request path. Special routes simulate a 302 to /protected and a 500."""
    seen = []
    redirect_dir = None
    error_dir = None
    truncate_file = None   # D': GET sends Content-Length 100 but only 5 bytes, then closes
    nocl_file = None       # N: HEAD answers 200 without Content-Length

    def log_message(self, *a):
        pass

    def _special(self):
        Handler.seen.append((self.command, self.path))
        if Handler.redirect_dir and self.path.rstrip('/').endswith(Handler.redirect_dir):
            self.send_response(302); self.send_header('Location', '/protected/IR/'); self.end_headers(); return True
        if Handler.error_dir and self.path.rstrip('/').endswith(Handler.error_dir):
            self.send_response(500); self.end_headers(); return True
        if Handler.truncate_file and self.command == 'GET' and self.path.endswith(Handler.truncate_file):
            self.send_response(200); self.send_header('Content-Length', '100'); self.end_headers()
            self.wfile.write(b'short'); self.wfile.flush(); self.close_connection = True; return True
        if Handler.nocl_file and self.command == 'HEAD' and self.path.endswith(Handler.nocl_file):
            self.send_response(200); self.end_headers(); return True
        return False

    def do_GET(self):
        if not self._special():
            super().do_GET()

    def do_HEAD(self):
        if not self._special():
            super().do_HEAD()


def serve(root):
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d' % srv.server_address[1]


def run(root, out, year=2027, regions='nrcc,gbcc'):
    return H.main(['--root', str(root), '--year', str(year), '--regions', regions, '--out', str(out), '--spacing', '0'])


def last_run(out):
    return [l for l in (out / 'run_log.txt').read_text().splitlines() if ' RUN ' in l][-1]


def main():
    os.environ['CR1_LOG_SALT'] = SALT
    fails = []

    def check(name, cond):
        print(('PASS ' if cond else 'FAIL ') + name)
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        root, out = Path(td, 'tree'), Path(td, 'out')
        make_fixture(root)
        # --- refusals before any request
        for y in (2025, 2026, 2024):
            check('refuses year %d' % y, run(root, Path(td, 'o%d' % y), year=y) == 2 and not Path(td, 'o%d' % y).exists())
        del os.environ['CR1_LOG_SALT']
        check('refuses without salt', run(root, Path(td, 'nosalt')) == 2)
        os.environ['CR1_LOG_SALT'] = SALT
        rr = H.repo_root()
        check('B: repo root is the git top level', (rr / '.git').exists())
        check('B: refuses --out at <repo>/zz_out', run(root, rr / 'zz_out') == 2 and not (rr / 'zz_out').exists())
        check('refuses --out inside script dir', run(root, Path(__file__).resolve().parent / 'tmp_out') == 2)
        # --- local-directory mode
        check('first run exit 0', run(root, out) == 0)
        st = json.loads((out / 'state.json').read_text())
        keys = sorted(st['files'])
        check('takes exactly 3 IR files', keys == sorted([INC1 + '/IR/20270715/fake_heat_perimeter.dbf',
                                                          INC1 + '/IR/20270715/fake_heat_perimeter.shp',
                                                          INC1 + '/IR/20270716/fake.kmz']))
        check('never touches 2026 or protected', not any(k.split('/')[1] == '2026' or 'protected' in k for k in keys))
        logtxt = (out / 'run_log.txt').read_text()
        # 'protected' appears only as the refusal reason label, checked below; path tokens must never appear.
        check('log has no clear paths or names',
              not any(s in logtxt for s in ('FAKEONE', 'FAKETWO', 'OFFLIMITS', 'nrcc', '.shp', '.kmz', 'IR/', '2027/')))
        check('log reports protected as REFUSED', 'REFUSED protected segment' in logtxt)
        check('salt never written', SALT not in logtxt and SALT not in (out / 'state.json').read_text())
        check('second run exit 0', run(root, out) == 0)
        check('re-run is idempotent (no new)', '"new"' not in last_run(out) and '"unchanged": 3' in last_run(out))
        # --- A: one change then 3 unchanged re-runs -> only .v2
        Path(root, INC1 + '/IR/20270716/fake.kmz').write_bytes(b'kmz22')
        run(root, out)
        for _ in range(3):
            run(root, out)
        st = json.loads((out / 'state.json').read_text())
        kmz = sorted(k for k in st['files'] if 'fake.kmz' in k)
        check('A: change + 3 re-runs keeps exactly original + .v2', kmz == [INC1 + '/IR/20270716/fake.kmz',
                                                                          INC1 + '/IR/20270716/fake.kmz.v2'])
        check('A: latest pointer is .v2', st['latest'][INC1 + '/IR/20270716/fake.kmz'].endswith('.v2'))
        check('A: last re-run all unchanged', '"unchanged": 3' in last_run(out) and '"changed"' not in last_run(out))
        # --- guards
        src = H.Source(str(root), 2027, 0)
        for bad in ('../etc', 'nrcc/2026/x', 'nrcc/2027/protected/x', '/abs'):
            try:
                src.guard(bad); ok = False
            except H.Refused:
                ok = True
            check('guard refuses %s' % bad, ok)
        # --- http mode on 127.0.0.1
        srv, url = serve(root)
        try:
            hout = Path(td, 'hout')
            Handler.seen.clear()
            check('http: first run exit 0', run(url, hout, regions='nrcc') == 0)
            hst = json.loads((hout / 'state.json').read_text())
            check('http: takes the same 3 files', sorted(hst['files']) == sorted([INC1 + '/IR/20270715/fake_heat_perimeter.dbf',
                                                                                  INC1 + '/IR/20270715/fake_heat_perimeter.shp',
                                                                                  INC1 + '/IR/20270716/fake.kmz']))
            check('http: no request ever reached 2026 or protected',
                  not any('/2026/' in p or 'protected' in p for _, p in Handler.seen))
            check('http: no 301 needed (dirs requested with trailing /)', all(
                p.endswith('/') for m, p in Handler.seen if m == 'GET' and not Path(p).suffix))
            # F: unchanged re-run downloads nothing
            Handler.seen.clear()
            check('F: re-run exit 0', run(url, hout, regions='nrcc') == 0)
            gets = [p for m, p in Handler.seen if m == 'GET' and Path(p).suffix]
            check('F: unchanged re-run makes zero file GETs (HEAD only)', gets == [] and
                  any(m == 'HEAD' for m, _ in Handler.seen))
            # E: same-host 302 to /protected is never followed
            Handler.seen.clear(); Handler.redirect_dir = '2027_FAKEONE_MT-XXX-000001/IR'
            rc = run(url, Path(td, 'eout'), regions='nrcc')
            check('E: 302 -> BLOCKED, exit 3', rc == 3 and 'BLOCKED' in last_run(Path(td, 'eout')))
            check('E: server never saw a /protected request', not any('protected' in p for _, p in Handler.seen))
            Handler.redirect_dir = None
            # D: HTTP 500 -> ERROR, not ALL DONE
            Handler.error_dir = '2027_FAKEONE_MT-XXX-000001/IR'
            rc = run(url, Path(td, 'dout'), regions='nrcc')
            lr = last_run(Path(td, 'dout'))
            check('D: 500 -> ERROR (HTTP 500), exit 3, not ALL DONE', rc == 3 and 'ERROR (HTTP 500)' in lr and 'ALL DONE' not in lr)
            Handler.error_dir = None
            # D': truncated body -> ERROR, never ALL DONE
            Handler.truncate_file = 'fake_heat_perimeter.shp'
            rc = run(url, Path(td, 'tout'), regions='nrcc')
            lr = last_run(Path(td, 'tout'))
            check("D': truncated body -> ERROR (body read: IncompleteRead), exit 3", rc == 3 and 'ERROR (body read:' in lr and 'ALL DONE' not in lr)
            Handler.truncate_file = None
            # N: new file whose HEAD has no Content-Length is downloaded, not logged as 404
            Handler.nocl_file = 'fake.kmz'
            nout = Path(td, 'nout')
            rc = run(url, nout, regions='nrcc')
            nst = json.loads((nout / 'state.json').read_text())
            check('N: HEAD without Content-Length -> new file still downloaded', rc == 0 and
                  any(k.endswith('fake.kmz') for k in nst['files']) and '"404"' not in last_run(nout))
            Handler.seen.clear()
            rc = run(url, nout, regions='nrcc')
            kmz_gets = [p for m, p in Handler.seen if m == 'GET' and p.endswith('fake.kmz')]
            nst = json.loads((nout / 'state.json').read_text())
            check('N: unknown size re-run downloads, sha matches latest -> UNCHANGED, no .v2', rc == 0 and len(kmz_gets) == 1
                  and not any(k.endswith('.v2') for k in nst['files']) and '"unchanged": 3' in last_run(nout))
            Handler.nocl_file = None
        finally:
            srv.shutdown()
            srv.server_close()  # close the listening socket so the next request is refused, not left hanging
        # D: connection refused (server down) -> ERROR
        rc = run(url, Path(td, 'cout'), regions='nrcc')
        check('D: URLError -> ERROR, exit 3', rc == 3 and 'ERROR (URLError)' in last_run(Path(td, 'cout')))
    print('ALL PASS' if not fails else 'FAILURES: %d' % len(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
