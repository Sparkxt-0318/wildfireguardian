"""Fixture test (no network) for find_exposed_ir_folders.py v3. Run: python3 -I test_find_exposed_ir_folders.py"""
import io, contextlib, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_exposed_ir_folders as F

R = 'https://ftp.example/public/incident_specific_data/'
R2 = 'https://ftp.example/public/incident_specific_maps/'
q = urllib.parse.quote
def page(*names):
    rows = ''.join(f'<a href="{n}">{n}</a> 2021-08-01 12:34 4.0K\n' for n in names)
    return f'<html><body><a href="?C=N">Name</a><a href="/public/">Parent</a>\n{rows}</body></html>'.encode()

PAGES = {
    # root and GACC index pages exist on this fixture server and list 2025/2026; they must never be fetched
    R: page('calif_n/', 'n_rockies/', 'pacific_nw/'),
    R + 'calif_n/': page('2021/', '2025/', '2026/', 'CA-NEW-000001_Current/'),
    R + 'calif_n/2021/': page('CA-BTU-009205_Dixie/', 'CA-SECRET-000111_Sealedfire/', 'Statefires/',
                              'CA-XXX-009205_Dixie/', '2021_Federal_Incidents/', 'Creek/', 'Complex/'),
    R + 'calif_n/2021/2021_Federal_Incidents/': page('Hiddenname/', 'CA-KNF-006454_Antelope/'),
    R + 'n_rockies/' + q('Historic_archived NIROPS/2021_fires/'): page('2021_AlderCreek/', '2021_Otherfire/'),
    # Hannah's homonym: a non-exposed River Complex in another GACC, with no number
    R + 'pacific_nw/Z_2021_HISTORIC/': page('2021_RiverComplex/', 'OR-ABC-000777_Unrelated/', '2021_Incidents_Oregon/'),
    R + 'pacific_nw/Z_2021_HISTORIC/2021_Incidents_Oregon/': page('2021_Jack_ORUPF000265/', '2021_Sealed_ORXYZ000999/'),
    # documented W4 layout: pacific_nw/2024_Incidents_Washington/2024_Pioneer_WASES000173/
    R2 + 'pacific_nw/2024_Incidents_Washington/': page('2024_Pioneer_WASES000173/', '2024_Hidden_WAXYZ000123/'),
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
        dict(Incident_C='CA-SNF-001391_Creek', year='2020'), dict(Incident_C='WA-SES-000173_Pioneer', year='2024'),
        dict(Incident_C='OR-WIF-220180_CedarCreek', year='2022')]
gaccs = ['calif_n/', 'n_rockies/', 'pacific_nw/']
err = io.StringIO()
with contextlib.redirect_stderr(err):
    res = F.run(rows, [R, R2], fetch, gaccs=gaccs)
out = ''.join(f'{i}\t{s}\t{v}\n' for i, s, v in res)
everything = out + err.getvalue()
assert 'pacific_nw' not in err.getvalue() and 'calif_n' not in err.getvalue(), 'GACC name on stderr'
for secret in ['Sealedfire', 'SECRET', 'Hiddenname', 'Otherfire', 'Current', 'Unrelated', 'XXX', 'XYZ', 'Statefires',
               'Sealed', 'Hidden', '2021_RiverComplex', 'AlderCreek/', '2025', '2026', '12:34', '4.0K']:
    assert secret not in everything, secret
# exact fetched set: constructed URLs only (2 roots x 3 GACCs x 4 years x 9 templates) + 3 group pages;
# never a root or GACC index page; never 2025+
years = ('2020', '2021', '2022', '2024')
expected = {r + g + q(t.format(y=y)) for r in (R, R2) for g in gaccs for y in years for t in F.TEMPLATES}
expected |= {R + 'calif_n/2021/2021_Federal_Incidents/', R + 'pacific_nw/Z_2021_HISTORIC/2021_Incidents_Oregon/'}
assert set(fetched) == expected, sorted(set(fetched) ^ expected)
assert not any(u in (R, R2) or u in [r + g for r in (R, R2) for g in gaccs] for u in fetched), 'index page fetched'
assert not any(y in u for y in ('2025', '2026') for u in fetched)
st = {i: (s, v) for i, s, v in res}
assert st['CA-BTU-009205_Dixie'] == ('FOUND', R + 'calif_n/2021/CA-BTU-009205_Dixie/'), st
assert st['CA-KNF-006454_Antelope'] == ('FOUND', R + 'calif_n/2021/2021_Federal_Incidents/CA-KNF-006454_Antelope/'), st
assert st['MT-BDF-006269_AlderCreek'] == ('NAME_ONLY', 1), st
assert st['CA-KNF-006385_RiverComplex_RiverComplex'] == ('NAME_ONLY', 1), st
assert st['OR-UPF-000265_Jack'] == ('FOUND', R + 'pacific_nw/Z_2021_HISTORIC/2021_Incidents_Oregon/2021_Jack_ORUPF000265/'), st
assert st['WA-SES-000173_Pioneer'] == ('FOUND', R2 + 'pacific_nw/2024_Incidents_Washington/2024_Pioneer_WASES000173/'), st
assert st['CA-SNF-001391_Creek'] == ('NOT_FOUND', 0), st
assert st['OR-WIF-220180_CedarCreek'] == ('NOT_FOUND', 0), st
assert st['TOTAL'] == ('FOUND=4 NAME_ONLY=2 AMBIGUOUS=0 NOT_FOUND=2', 8), st
assert F.classify('Complex', *F.keys('CA-KNF-006385_RiverComplex_RiverComplex')) is None
assert F.classify('2021_River', *F.keys('CA-KNF-006385_RiverComplex_RiverComplex')) is None
# year refusal
try:
    F.run([dict(Incident_C='X', year='2025')], [R], fetch, gaccs=gaccs); raise AssertionError('2025 accepted')
except SystemExit:
    pass
print('PASS: fetched', len(fetched), 'constructed URLs (no index page), stderr lines', len(err.getvalue().splitlines()))
