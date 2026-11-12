#!/usr/bin/env python3
"""Custodian script: find the NIFC FTP IR folders of the EXPOSED incidents only (version 3).

To be run ONCE, by the custodian (Hannah), not by Daniel.
- v3: fetches NO root page and NO GACC page. Every URL is CONSTRUCTED from frozen lists (ROOTS x GACCS x TEMPLATES)
  for the 2020-2024 years in EXPOSED.csv; 404 = absent. No URL with 2025-2029 is ever fetched.
- Inside a fetched year page it descends at most one level into grouping folders (name contains 'incidents', no
  unit-number pattern). A fire's own folder is never opened.
- Pages are parsed in memory for <a href> values only; link text, modification times and sizes are never read.

Output (stdout, or --out FILE): one line per exposed incident, then one TOTAL line:
  <Incident_C>\tFOUND\t<folder URL>    exactly one folder carrying the unit code + incident number + fire name
  <Incident_C>\tAMBIGUOUS\t<n>        more than one such folder (no URLs)
  <Incident_C>\tNAME_ONLY\t<n>        no numbered folder; n folders with no incident number whose name equals the
                                      FULL fire name (no URLs: may be a homonym of another fire)
  <Incident_C>\tNOT_FOUND\t0
  TOTAL\tFOUND=a NAME_ONLY=b AMBIGUOUS=c NOT_FOUND=d\t<n incidents>
Log (stderr): per URL tried, a template (R<r>/GACC[i]/T<k>/<year>[/GROUP[j]], never a folder name) and either ABSENT or
the sha256 of the response.

Usage: python3 -I find_exposed_ir_folders.py EXPOSED.csv [--root URL ...] [--out FILE]
Stdlib only.
"""
import argparse, csv, hashlib, html.parser, re, sys, time, urllib.error, urllib.parse, urllib.request

# v3: no page is ever fetched to DISCOVER a root or a GACC. Every URL is constructed from frozen lists:
# ROOTS from documentation (incident_specific_data: Magstadt NIROPS.ipynb cell 0 and the FRESH_HOLDOUT.md W4/W5/W42/W43
# links; incident_specific_maps: the tree Sofia's 12 Nov crawl started at). The server returned 404 for the
# incident_specific_data/ index itself (Hannah's run, 15:38:41Z); subpaths are still tried.
ROOTS = ['https://ftp.wildfire.gov/public/incident_specific_data/',
         'https://ftp.wildfire.gov/public/incident_specific_maps/']
# GACC folders: the seven areas in Magstadt's region list (NIROPS.ipynb cell 5), with the FTP spellings documented in
# NIROPS.ipynb cell 0 (rocky_mtn) and FRESH_HOLDOUT.md W4/W5/W42/W43 (pacific_nw, n_rockies, southwest, great_basin);
# calif_n and calif_s are the conventional spellings (not verified from a document).
GACCS = ['calif_n/', 'calif_s/', 'great_basin/', 'n_rockies/', 'pacific_nw/', 'rocky_mtn/', 'southwest/']
YEARS = {'2020', '2021', '2022', '2023', '2024'}  # never 2025+
# Frozen URL templates under each GACC; layouts from FRESH_HOLDOUT.md section 2.1 and its links W4 and W5
# (pacific_nw/2024_Incidents_Washington/..., pacific_nw/Z_2022_HISTORIC/2022_Incidents_Oregon/...).
TEMPLATES = ['{y}/', 'Z_{y}_HISTORIC/', 'GACC_Incidents/{y}/', 'Historic_archived NIROPS/{y}_fires/',
             'pre2015-great_basin_w/{y}/', '{y}_Incidents_Oregon/', '{y}_Incidents_Washington/',
             'Z_{y}_HISTORIC/{y}_Incidents_Oregon/', 'Z_{y}_HISTORIC/{y}_Incidents_Washington/']
UNIT_NUM = r'[A-Z]{2}[-_][A-Z0-9]+[-_]\d{3,}'


class Absent(Exception):
    pass


class Links(html.parser.HTMLParser):
    """Collects href values of <a> tags only; text, times and sizes are never stored."""
    def __init__(self):
        super().__init__(); self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for k, v in attrs:
                if k == 'href' and v:
                    self.hrefs.append(v)


def links_under(page_bytes, base):
    p = Links(); p.feed(page_bytes.decode('utf-8', 'replace'))
    out = []
    for h in p.hrefs:
        u = urllib.parse.urljoin(base, h)
        if u.startswith(base) and u != base and '?' not in h:
            out.append(u)
    return out


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def keys(incident):
    """((unit, number), name set, joined name), e.g. (('btu', '9205'), {'dixie'}, 'dixie')."""
    m = re.match(r'^[A-Z]{2}[-_]([A-Z0-9]+)[-_](\d+)[a-z]?_(.+)$', incident)
    num = (norm(m.group(1)), str(int(m.group(2)))) if m else None
    names = [n for n in (m.group(3) if m else incident).split('_') if n]
    joined = norm(''.join(dict.fromkeys(names)))  # repeated tokens once: RiverComplex_RiverComplex -> rivercomplex
    return num, {norm(n) for n in names} | {joined}, joined


def classify(folder_name, num, names, joined):
    """'FOUND' only for unit code + incident number + fire name. 'NAME_ONLY' when the folder has no incident
    number and, after stripping a leading year, equals the FULL joined fire name (never a single token)."""
    raw = urllib.parse.unquote(folder_name)
    f = norm(raw)
    if num is not None and re.search(num[0] + '0*' + num[1] + r'(?!\d)', f) and any(n and n in f for n in names):
        return 'FOUND'
    nums = [d for d in re.findall(r'\d+', raw) if not re.fullmatch(r'20\d\d', d)]
    if not nums and re.sub(r'^20\d\d', '', f) == joined:
        return 'NAME_ONLY'
    return None


def looks_like_group(folder_name):
    """A grouping folder (e.g. '2021_Federal_Incidents'): name contains 'incidents' and no unit-number pattern."""
    n = folder_name.strip('/')
    return not re.search(UNIT_NUM, n) and bool(re.search(r'incidents', n, re.I))


def run(rows, roots, fetch, gaccs=GACCS):
    want = {}
    for r in rows:
        y = str(r['year'])
        if y not in YEARS:
            raise SystemExit(f'refused: year {y} outside 2020-2024')
        want.setdefault(y, []).append((r['Incident_C'],) + keys(r['Incident_C']))
    found = {r['Incident_C']: [] for r in rows}
    name_only = {r['Incident_C']: 0 for r in rows}

    def get(url, template):
        if re.search(r'202[5-9]', url):
            raise SystemExit('refused: 2025+ URL')
        try:
            body = fetch(url)
        except Absent:
            body = None
        print(f'page {template} ' + ('ABSENT' if body is None else f'sha256={hashlib.sha256(body).hexdigest()}'),
              file=sys.stderr)
        return body

    def scan(urls, y, base):
        for u in urls:
            if u.endswith('/'):
                name = u[len(base):].strip('/')
                for inc, num, names, joined in want[y]:
                    c = classify(name, num, names, joined)
                    if c == 'FOUND':
                        found[inc].append(u)
                    elif c == 'NAME_ONLY':
                        name_only[inc] += 1

    for ri, root in enumerate(roots):
        for gi, gname in enumerate(gaccs):
            g = root + gname
            for y in sorted(want):
                for ti, tpl in enumerate(TEMPLATES):
                    yu = g + urllib.parse.quote(tpl.format(y=y))
                    body = get(yu, f'R{ri}/GACC[{gi}]/T{ti}/{y}')
                    if body is None:
                        continue
                    level1 = links_under(body, yu); del body
                    scan(level1, y, yu)
                    for k, u in enumerate(level1):
                        if u.endswith('/') and looks_like_group(urllib.parse.unquote(u[len(yu):])):
                            b2 = get(u, f'R{ri}/GACC[{gi}]/T{ti}/{y}/GROUP[{k}]')
                            if b2 is not None:
                                scan(links_under(b2, u), y, u)
                            del b2
                    del level1
    out, tally = [], dict.fromkeys(['FOUND', 'NAME_ONLY', 'AMBIGUOUS', 'NOT_FOUND'], 0)
    for inc, urls in found.items():
        urls = sorted(set(urls))
        row = ((inc, 'FOUND', urls[0]) if len(urls) == 1 else (inc, 'AMBIGUOUS', len(urls)) if urls else
               (inc, 'NAME_ONLY', name_only[inc]) if name_only[inc] else (inc, 'NOT_FOUND', 0))
        out.append(row); tally[row[1]] += 1
    out.append(('TOTAL', ' '.join(f'{k}={v}' for k, v in tally.items()), len(found)))
    return out


def fetch_url(url):
    time.sleep(0.3)  # polite: about 500 constructed URLs in a full run
    req = urllib.request.Request(url, headers={'User-Agent': 'wfg-custodian/1'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise Absent()
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('exposed'); ap.add_argument('--root', action='append', help='override ROOTS (repeatable)')
    ap.add_argument('--out')
    a = ap.parse_args()
    res = run(list(csv.DictReader(open(a.exposed))), a.root or ROOTS, fetch_url)
    text = ''.join(f'{i}\t{s}\t{v}\n' for i, s, v in res)
    (open(a.out, 'w').write(text) if a.out else sys.stdout.write(text))


if __name__ == '__main__':
    main()
