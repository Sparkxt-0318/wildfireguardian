"""Fixture test (no network) for find_exposed_ir_folders.py v2. Run: python3 -I test_find_exposed_ir_folders.py"""
import io, contextlib, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_exposed_ir_folders as F

R = 'https://ftp.example/public/incident_specific_data/'
def page(*names):
    rows = ''.join(f'<a href="{n}">{n}</a> 2021-08-01 12:34 4.0K\n' for n in names)
    return f'<html><body><a href="?C=N">Name</a><a href="/public/">Parent</a>\n{rows}</body></html>'.encode()

PAGES = {
    R: page('calif_n/', 'n_rockies/', 'pacific_nw/'),
    # GACC pages exist on the real server and list 2025/2026; they must never be fetched
    R + 'calif_n/': page('2021/', '2025/', '2026/', 'CA-NEW-000001_Current/'),
    R + 'calif_n/2021/': page('CA-BTU-009205_Dixie/', 'CA-SECRET-000111_Sealedfire/', 'Statefires/',
                              'CA-XXX-009205_Dixie/', '2021_Federal_Incidents/', 'Creek/', 'Complex/'),
    R + 'calif_n/2021/2021_Federal_Incidents/': page('Hiddenname/', 'CA-KNF-006454_Antelope/'),
    R + 'n_rockies/' + urllib.parse.quote('Historic_archived NIROPS/2021_fires/'): page('2021_AlderCreek/', '2021_Otherfire/'),
    # Hannah's homonym: a non-exposed River Complex in another GACC, with no number
    R + 'pacific_nw/Z_2021_HISTORIC/': page('2021_RiverComplex/', 'OR-ABC-000777_Unrelated/'),
}
fetched = []
def fetch(u):
    fetched.append(u)
    if u in PAGES:
        return PAGES[u]
    raise F.Absent()

rows = [dict(Incident_C='CA-BTU-009205_Dixie', year='2021'), dict(Incident_C='CA-KNF-006454_Antelope', year='2021'),
        dict(Incident_C='MT-BDF-006269_AlderCreek', year='2021'), dict(Incident_C='OR-UPF-000265_Jack', year='2021'),
        dict(Incident_C='CA-KNF-006385_RiverComplex_RiverComplex', year='2021'),
        dict(Incident_C='CA-SNF-001391_Creek', year='2020')]
err = io.StringIO()
with contextlib.redirect_stderr(err):
    res = F.run(rows, R, fetch)
out = ''.join(f'{i}\t{s}\t{v}\n' for i, s, v in res)
everything = out + err.getvalue()
for secret in ['Sealedfire', 'SECRET', 'Hiddenname', 'Otherfire', 'Current', 'Unrelated', 'XXX', 'Statefires',
               'RiverComplex/', '2021_RiverComplex', 'pacific_nw', 'AlderCreek/', '2025', '2026', '12:34', '4.0K']:
    assert secret not in everything, secret
# exact fetched set: ROOT + constructed URLs + one group page; never a GACC page; never 2025+
gaccs = ['calif_n/', 'n_rockies/', 'pacific_nw/']
expected = {R} | {R + g + urllib.parse.quote(t.format(y=y)) for g in gaccs for y in ('2020', '2021') for t in F.TEMPLATES}
expected |= {R + 'calif_n/2021/2021_Federal_Incidents/'}
assert set(fetched) == expected, sorted(set(fetched) ^ expected)
assert not any(R + g == u for g in gaccs for u in fetched), 'GACC page fetched'
assert not any(y in u for y in ('2025', '2026') for u in fetched)
st = {i: (s, v) for i, s, v in res}
assert st['CA-BTU-009205_Dixie'] == ('FOUND', R + 'calif_n/2021/CA-BTU-009205_Dixie/'), st
assert st['CA-KNF-006454_Antelope'] == ('FOUND', R + 'calif_n/2021/2021_Federal_Incidents/CA-KNF-006454_Antelope/'), st
assert st['MT-BDF-006269_AlderCreek'] == ('NAME_ONLY', 1), st          # no number: never FOUND, no URL
assert st['CA-KNF-006385_RiverComplex_RiverComplex'] == ('NAME_ONLY', 1), st  # homonym in pacific_nw: no URL
assert st['OR-UPF-000265_Jack'] == ('NOT_FOUND', 0), st
assert st['CA-SNF-001391_Creek'] == ('NOT_FOUND', 0), st              # 2020 pages absent; generic 'Creek/' is 2021
assert st['TOTAL'] == ('FOUND=2 NAME_ONLY=2 AMBIGUOUS=0 NOT_FOUND=2', 6), st
# a single generic token never yields NAME_ONLY for a multi-token name
assert F.classify('Complex', *F.keys('CA-KNF-006385_RiverComplex_RiverComplex')) is None
assert F.classify('2021_River', *F.keys('CA-KNF-006385_RiverComplex_RiverComplex')) is None
# year refusal and ROOT abort
BAD = [([dict(Incident_C='X', year='2025')], None),
       (rows, {R: page('calif_n/', '2025/')}),
       (rows, {R: page('calif_n/', 'CA-BTU-009205_Dixie/')}),
       (rows, {R: page('calif_n/', 'readme.txt')})]
for bad_rows, bad_pages in BAD:
    e2 = io.StringIO()
    try:
        with contextlib.redirect_stderr(e2):
            F.run(bad_rows, R, (lambda u, P=bad_pages: P[u]) if bad_pages else fetch)
        raise AssertionError('not refused')
    except SystemExit as ex:
        assert 'Dixie' not in str(ex) and '2025/' not in str(ex) and 'readme' not in str(ex)
print('PASS: fetched', len(fetched), 'URLs (ROOT + constructed + 1 group page), stderr lines', len(err.getvalue().splitlines()))
