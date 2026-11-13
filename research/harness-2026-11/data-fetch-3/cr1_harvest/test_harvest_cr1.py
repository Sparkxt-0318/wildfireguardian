#!/usr/bin/env python3
"""Synthetic-fixture tests for harvest_cr1.py. No network. Run: python3 -I test_harvest_cr1.py"""
import json, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harvest_cr1 as H  # noqa: E402

SALT = 'test-salt-only'


def make_fixture(root):
    def put(rel, data=b'x'):
        p = Path(root, rel); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    put('nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270715/fake_heat_perimeter.shp', b'shp1')
    put('nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270715/fake_heat_perimeter.dbf', b'dbf1')
    put('nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270715/notes.docx', b'skip')
    put('nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270716/fake.kmz', b'kmz1')
    put('nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/misc/fake.kmz', b'skip')
    put('nrcc/2027/2027_FAKETWO_ID-YYY-000002/GIS/fake.shp', b'no ir')
    put('nrcc/2026/2026_OFFLIMITS/IR/20260701/must_not_read.shp', b'never')
    put('nrcc/2027/protected/IR/20270701/must_not_read.shp', b'never')


def run(root, out, year=2027):
    return H.main(['--root', str(root), '--year', str(year), '--regions', 'nrcc,gbcc', '--out', str(out), '--spacing', '0'])


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
        for y in (2025, 2026, 2024):
            check('refuses year %d' % y, run(root, Path(td, 'o%d' % y), year=y) == 2 and not Path(td, 'o%d' % y).exists())
        del os.environ['CR1_LOG_SALT']
        check('refuses without salt', run(root, Path(td, 'nosalt')) == 2)
        os.environ['CR1_LOG_SALT'] = SALT
        check('refuses out inside repo', H.main(['--root', str(root), '--year', '2027', '--regions', 'nrcc',
                                                 '--out', str(Path(__file__).resolve().parent / 'tmp_out')]) == 2)
        check('first run exit 0', run(root, out) == 0)
        state = json.loads((out / 'state.json').read_text())
        keys = sorted(state)
        check('takes exactly 3 IR files', keys == sorted([
            'nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270715/fake_heat_perimeter.dbf',
            'nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270715/fake_heat_perimeter.shp',
            'nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270716/fake.kmz']))
        check('never touches 2026 or protected', not any('2026' in k.split('/')[1] or 'protected' in k for k in keys))
        logtxt = (out / 'run_log.txt').read_text()
        # 'protected' appears only as the refusal reason label, checked below; path tokens must never appear.
        check('log has no clear paths or names', not any(s in logtxt for s in ('FAKEONE', 'FAKETWO', 'OFFLIMITS', 'nrcc', '.shp', '.kmz', 'IR/', '2027/')))
        check('log reports protected as REFUSED', 'REFUSED protected segment' in logtxt)
        check('salt never written', SALT not in logtxt and SALT not in (out / 'state.json').read_text())
        check('second run exit 0', run(root, out) == 0)
        last = [l for l in (out / 'run_log.txt').read_text().splitlines() if ' RUN ' in l][-1]
        check('re-run is idempotent (no new)', '"new"' not in last and '"unchanged": 3' in last)
        Path(root, 'nrcc/2027/2027_FAKEONE_MT-XXX-000001/IR/20270716/fake.kmz').write_bytes(b'kmz2')
        run(root, out)
        state = json.loads((out / 'state.json').read_text())
        check('changed file kept as .v2, original kept', any(k.endswith('fake.kmz.v2') for k in state)
              and any(k.endswith('fake.kmz') for k in state))
        src = H.Source(str(root), 2027, 0)
        for bad in ('../etc', 'nrcc/2026/x', 'nrcc/2027/protected/x', '/abs'):
            try:
                src.guard(bad); ok = False
            except H.Refused:
                ok = True
            check('guard refuses %s' % bad, ok)
    print('ALL PASS' if not fails else 'FAILURES: %d' % len(fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
