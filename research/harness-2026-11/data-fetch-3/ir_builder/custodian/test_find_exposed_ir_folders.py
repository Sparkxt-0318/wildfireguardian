"""Fixture test: no non-exposed name, time or size reaches stdout, stderr or the output. Run with python3 -I."""
import io, contextlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_exposed_ir_folders as F

R = 'https://ftp.example/public/incident_specific_data/'
def page(*names, times=True):
    rows = ''.join(f'<a href="{n}">{n}</a> {"2021-08-01 12:34" if times else ""} 4.0K\n' for n in names)
    return f'<html><body><a href="?C=N">Name</a><a href="/public/">Parent</a>\n{rows}</body></html>'.encode()
PAGES = {
    R: page('calif_n/', 'n_rockies/'),
    R + 'calif_n/': page('2021/', '2025/', '2026/'),
    R + 'calif_n/2021/': page('CA-BTU-009205_Dixie/', 'CA-SECRET-000111_Sealedfire/', 'Statefires/', 'CA-XXX-009205_Dixie/', 'Incidentfire_CA-XYZ-000222/', '2021_Federal_Incidents/'),
    R + 'calif_n/2021/2021_Federal_Incidents/': page('Hiddenname/', 'Antelope/'),
    R + 'calif_n/2025/': page('CA-NEW-000001_Future/'),
    R + 'n_rockies/': page('2021/'),
    R + 'n_rockies/2021/': page('2021_AlderCreek/', 'Otherfire/'),
}
fetched = []
def fetch(u):
    fetched.append(u); return PAGES[u]

rows = [dict(Incident_C='CA-BTU-009205_Dixie', year='2021'), dict(Incident_C='CA-KNF-006454_Antelope', year='2021'),
        dict(Incident_C='MT-BDF-006269_AlderCreek', year='2021'), dict(Incident_C='OR-UPF-000265_Jack', year='2021')]
err = io.StringIO()
with contextlib.redirect_stderr(err):
    res = F.run(rows, R, fetch)
out = ''.join(f'{i}\t{s}\t{v}\n' for i, s, v in res)
everything = out + err.getvalue()
for secret in ['Sealedfire', 'SECRET', 'Hiddenname', 'Otherfire', 'Future', 'Statefires', 'Incidentfire', 'XYZ', 'XXX', '2025', '2026', '12:34', '4.0K']:
    assert secret not in everything, secret
assert all(u in (R, R+'calif_n/', R+'calif_n/2021/', R+'calif_n/2021/2021_Federal_Incidents/', R+'n_rockies/', R+'n_rockies/2021/') for u in fetched), fetched
assert not any('2025' in u or '2026' in u for u in fetched), 'fetched a 2025+ page'
st = {i: (s, v) for i, s, v in res}
assert st['CA-BTU-009205_Dixie'] == ('FOUND', R + 'calif_n/2021/CA-BTU-009205_Dixie/'), st
assert st['CA-KNF-006454_Antelope'] == ('FOUND', R + 'calif_n/2021/2021_Federal_Incidents/Antelope/'), st
assert st['MT-BDF-006269_AlderCreek'] == ('FOUND', R + 'n_rockies/2021/2021_AlderCreek/'), st
assert st['OR-UPF-000265_Jack'] == ('NOT_FOUND', 0), st
try:
    F.run([dict(Incident_C='X', year='2025')], R, fetch); raise AssertionError('2025 accepted')
except SystemExit:
    pass
print('PASS', len(fetched), 'pages fetched in fixture; stderr lines:', len(err.getvalue().splitlines()))
