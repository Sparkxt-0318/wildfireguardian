#!/usr/bin/env python3
"""Custodian script: find the NIFC FTP IR folders of the EXPOSED incidents only.

To be run ONCE, by the custodian (Hannah), not by Daniel. It fetches the directory pages of the NIFC FTP
(incident_specific_data/<gacc>/<year>/... for years 2020-2024 only), parses each page IN MEMORY, keeps only
the links that match one of the exposed incidents, and discards everything else immediately: other folder
names, modification times and sizes are never printed, logged or written.

Output (stdout, or --out FILE): one line per exposed incident:
  <Incident_C>\tFOUND\t<folder URL>        exactly one matching folder
  <Incident_C>\tAMBIGUOUS\t<n>            n > 1 matching folders (no URLs given; the custodian resolves by hand)
  <Incident_C>\tNOT_FOUND\t0
Log (stderr): per fetched page, only the URL TEMPLATE (gacc/year/level, never a folder name) and the sha256 of
the response bytes.

Usage: find_exposed_ir_folders.py EXPOSED.csv [--root URL] [--out FILE]
EXPOSED.csv has the columns Incident_C and year (e.g. the forecast_v2 rows of nirops_incidents_allowed.csv).
Stdlib only. Folder names under <gacc>/<year>/ may be grouped one level deeper (e.g. "<year>_Federal_Incidents");
the script descends at most one such grouping level, again in memory only.
"""
import argparse, csv, hashlib, html.parser, re, sys, urllib.parse, urllib.request

ROOT = 'https://ftp.wildfire.gov/public/incident_specific_data/'
YEARS = {'2020', '2021', '2022', '2023', '2024'}  # never 2025+


class Links(html.parser.HTMLParser):
    """Collects href values of <a> tags only; text, times and sizes are never stored."""
    def __init__(self):
        super().__init__(); self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v:
                    self.hrefs.append(v)


def subdirs(page_bytes, base):
    p = Links(); p.feed(page_bytes.decode('utf-8', 'replace'))
    out = []
    for h in p.hrefs:
        u = urllib.parse.urljoin(base, h)
        if u.startswith(base) and u.endswith('/') and u != base and '?' not in h:
            out.append(u)
    return out


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def keys(incident):
    """((unit, number), names), e.g. ('btu', '9205'); names: the parts after the unit-number prefix."""
    m = re.match(r'^[A-Z]{2}[-_]([A-Z0-9]+)[-_](\d+)[a-z]?_(.+)$', incident)
    num = (norm(m.group(1)), str(int(m.group(2)))) if m else None
    names = [n for n in (m.group(3) if m else incident).split('_') if n]
    return num, {norm(n) for n in names} | {norm(''.join(names))}


def matches(folder_name, num, names):
    f = norm(urllib.parse.unquote(folder_name))
    digits = re.findall(r'\d+', urllib.parse.unquote(folder_name))
    name_hit = any(n and (f.endswith(n) or n in f) for n in names)
    # unit code AND incident number must both appear, e.g. 'BTU' and 009205 in 'CA-BTU-009205_Dixie'
    num_hit = num is not None and bool(re.search(num[0] + '0*' + num[1] + r'(?!\d)', f))
    if num_hit and name_hit:
        return True
    # no incident number in the folder name at all (only a year, or nothing): exact name equality
    nums = [d for d in digits if not re.fullmatch(r'20\d\d', d)]
    f_noyear = re.sub(r'^20\d\d', '', f)
    return not nums and f_noyear in names


def looks_like_group(folder_name):
    """A grouping folder (e.g. '2021_Federal_Incidents', '!CALFIRE_Incidents'): its name must contain 'incidents'
    and must NOT look like an incident (no unit-number pattern). Anything else is never opened, so a non-exposed
    fire's own folder is never listed."""
    n = folder_name.strip('/')
    if re.search(r'[A-Z]{2}[-_][A-Z0-9]+[-_]\d{3,}', n):
        return False
    return bool(re.search(r'incidents', n, re.I))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exposed'); ap.add_argument('--root', default=ROOT); ap.add_argument('--out')
    ap.add_argument('--fetch', help=argparse.SUPPRESS)  # tests inject a fetch function via fetch_with()
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.exposed)))
    res = run(rows, a.root, fetch_url)
    text = ''.join(f'{i}\t{s}\t{v}\n' for i, s, v in res)
    (open(a.out, 'w').write(text) if a.out else sys.stdout.write(text))


def fetch_url(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'wfg-custodian/1'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def run(rows, root, fetch):
    want = {}
    for r in rows:
        y = str(r['year'])
        if y not in YEARS:
            raise SystemExit(f'refused: year {y} outside 2020-2024')
        want.setdefault(y, []).append((r['Incident_C'],) + keys(r['Incident_C']))
    found = {r['Incident_C']: [] for r in rows}

    def log(template, body):
        print(f'page {template} sha256={hashlib.sha256(body).hexdigest()}', file=sys.stderr)

    body = fetch(root); log('ROOT', body)
    gaccs = subdirs(body, root); del body
    for gi, g in enumerate(gaccs):
        body = fetch(g); log(f'GACC[{gi}]', body)
        years = [u for u in subdirs(body, g) if urllib.parse.unquote(u[len(g):]).strip('/') in want]
        del body
        for yu in years:
            y = urllib.parse.unquote(yu[len(g):]).strip('/')
            body = fetch(yu); log(f'GACC[{gi}]/{y}', body)
            level1 = subdirs(body, yu); del body
            for k, u in enumerate(level1):
                name = u[len(yu):].strip('/')
                hit = False
                for inc, num, names in want[y]:
                    if matches(name, num, names):
                        found[inc].append(u); hit = True
                if not hit and looks_like_group(urllib.parse.unquote(name)):
                    body = fetch(u); log(f'GACC[{gi}]/{y}/GROUP[{k}]', body)
                    for v in subdirs(body, u):
                        n2 = v[len(u):].strip('/')
                        for inc, num, names in want[y]:
                            if matches(n2, num, names):
                                found[inc].append(v)
                    del body
            del level1
    out = []
    for inc, urls in found.items():
        urls = sorted(set(urls))
        out.append((inc, 'FOUND', urls[0]) if len(urls) == 1 else
                   (inc, 'AMBIGUOUS', len(urls)) if urls else (inc, 'NOT_FOUND', 0))
    return out


if __name__ == '__main__':
    main()
