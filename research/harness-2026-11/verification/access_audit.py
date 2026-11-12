#!/usr/bin/env python3
"""Mechanical access audit over Claude Code session transcripts (owner-runnable; stdlib only).

Why: the S-D9 sealed-data audit (verification ledger rows 38, 45 and 46) rests partly on session declarations.
This script checks those declarations against what the transcripts record.

Input: Claude Code transcript files (*.jsonl), or directories containing them.
- A session's transcript lives in its own container under ~/.claude/projects/<project>/<session-uuid>.jsonl.
- Subagent transcripts live under <session-uuid>/subagents/*.jsonl.
- The owner collects them; see "Access" below.

Output: one TSV row per session (sessionId from the records, else the file stem), with counts and the EARLIEST UTC time
for each category below (earliest timestamp across all files, not the first in file order). Fire names are never printed: name matching uses hash lists only.

Categories:
  F1..F5    tool calls whose INPUT names the file (an access attempt), and tool results that contain its path
  nirops    tool calls reading the raw NIROPS shapefile/dbf (pyogrio/fiona/ogr/geopandas/unzip). An unfiltered read is
            one with no where=, no fids= and no Incident_C-only column list
  gofer     tool calls reading raw GOFER files (GOFER zip, fireProg, fireLine, GOFERC_fireIg)
  wildfire_gov  every occurrence of 'wildfire.gov' in an input, result or text, whatever the year
  web/net   WebSearch/WebFetch/agent web calls; curl/wget/rsync/scp/lftp/git clone; requests/urllib/urllib3/http.client/
            httpx/aiohttp/ftplib/fsspec//vsicurl; read_*('http…'); fetch.py and remote_zip.py. Hosts MENTIONED in any URL (http, https, ftp, s3, gs)
            in any tool input are listed (mentioned, not necessarily fetched)
  ftp2526   a wildfire.gov URL with a 2025/2026 segment, or a tool input naming wildfire.gov and 2025/2026 anywhere
            (covers hosts in variables and ftplib cwd)
  net_result_2025_2026  the result of a net or wildfire.gov call that contains 2025 or 2026 (directory listings)
  names:<L> matches against hash list L. A hash is sha256 of the normalised name: lowercase, alphanumerics only,
            tokens joined with no separator. Text is tokenised on non-alphanumerics, and n-grams of 1..6 tokens are
            hashed (incident IDs such as XX-UNIT-000000_Name span 4-6 tokens). Counts are per field (tool input / tool result / assistant text).

Usage:
  python3 -I access_audit.py --names sealed=sealed_hashes.txt --names us2026=us2026_hashes.txt DIR_OR_JSONL ... > audit.tsv
  python3 -I access_audit.py --make-hashes plain_names.txt > hashes.txt    (custodian only; never commit the plain list)

Access: a session can read only the transcripts in its own container. The owner runs this over transcripts exported
from every session (for example, each session copies its own .jsonl and subagents/ into a shared, owner-held
location). Results are evidence for comparison with the declarations, not proof of absence: a model can know a name
from training without any tool call, and short or common names give false positives.
--ftp-detail lists every ftp.wildfire.gov URL written in a tool INPUT (root/gacc/year segment, rest hashed) and the
HTTP status codes found in the matching tool RESULT. URLs that a script constructs internally (for example the
custodian finder's 504 constructed URLs) do not appear in tool inputs; they are visible only in that script's own logs.
Give common-word names their own hash list (for example --names us2026_common=...) and judge them separately
from distinctive names and full incident IDs.
"""
import argparse, collections, hashlib, json, os, re, sys
from urllib.parse import urlparse

FILES = {
    'F1': r'data-fetch/nirops_incidents\.csv',
    'F2': r'nirops_incidents_v2\.csv',
    'F3': r'incident_metadata\.csv',
    'F4': r'GOFER_MATCH\.csv',
    'F5': r'camera-arrival/outputs/(gofer_fires\.csv|feasibility_daily_growth\.csv)',
}
NIROPS = re.compile(r'NIROPS_2020_2024|\.shp\b|\.dbf\b', re.I)
READ = re.compile(r'read_dataframe|read_info|pyogrio|fiona|ogr\.|ogrinfo|gpd\.read_file|geopandas|unzip|read_file\(|dbfread|shapefile\.Reader|struct\.unpack|open\([^)]*[\'"]rb[\'"]|dbf\.py|\.dbf[\'"]?\s*\)', re.I)
FILTERED = re.compile(r"where\s*=|fids\s*=|columns\s*=\s*\[\s*['\"]Incident_C['\"]\s*\]|nirops_access", re.I)
GOFER = re.compile(r'(?i:GOFER[^\s\'"]*\.zip)|GOFERC_fireIg|\bfireProg\b|\bfireLine\b')   # filenames are case-sensitive: 'fireline intensity' is not a hit
NETCMD = re.compile(r'\b(curl|wget|rsync|scp|lftp|sftp|aria2c)\b|git\s+clone|requests\.(get|post|head|Session)|urlopen'
                    r'|urllib\.request|urllib3|http\.client|httpx|aiohttp|ftplib|fsspec|/vsicurl|smart_open|boto3|gsutil'
                    r'|read_(csv|json|parquet|table|file|dataframe)\(\s*[\'"](?:https?|ftp|s3|gs)://|fetch\.py|remote_zip\.py'
                    r'|WebFetch|web-fetch', re.I)
URL = re.compile(r'(?:https?|ftp|s3|gs)://[^\s\'"<>)\]\\,]+', re.I)
WILDFIRE = re.compile(r'wildfire\.gov', re.I)
YEAR2526 = re.compile(r'(?<!\d)(2025|2026)(?!\d)')
FTP2526 = re.compile(r'wildfire\.gov[^\s\'"]*?(?<!\d)(2025|2026)(?!\d)', re.I)
WEBTOOLS = {'WebSearch', 'WebFetch'}


def safe_host(u):
    """Host of a URL-like string; never raises (urlparse rejects e.g. unbalanced '[' as an IPv6 literal)."""
    try:
        return urlparse(u).netloc.lower() or '<no-host>'
    except ValueError:
        return '<bad-url>'


def norm_tokens(text):
    return [t for t in re.split(r'[^a-z0-9]+', text.lower()) if t]


def name_hash(name):
    return hashlib.sha256(''.join(norm_tokens(name)).encode()).hexdigest()


def ngram_hashes(text, nmax=6):
    toks = norm_tokens(text)
    out = set()
    for n in range(1, nmax + 1):
        for i in range(len(toks) - n + 1):
            out.add(hashlib.sha256(''.join(toks[i:i + n]).encode()).hexdigest())
    return out


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if f.endswith('.jsonl'):
                        yield os.path.join(root, f)
        elif p.endswith('.jsonl'):
            yield p


def blocks(rec):
    """Yields (field, tool_name, tool_use_id, text) for tool inputs, tool results and assistant text."""
    m = rec.get('message')
    if not isinstance(m, dict):
        return
    c = m.get('content')
    if isinstance(c, str):
        yield ('text' if rec.get('type') == 'assistant' else 'user_text', None, None, c)
        return
    for b in c or []:
        if not isinstance(b, dict):
            continue
        t = b.get('type')
        if t == 'tool_use':
            yield 'input', b.get('name'), b.get('id'), json.dumps(b.get('input'), ensure_ascii=False)
        elif t == 'tool_result':
            cc = b.get('content')
            if isinstance(cc, list):
                cc = ' '.join(x.get('text', '') for x in cc if isinstance(x, dict))
            yield 'result', None, b.get('tool_use_id'), str(cc)
        elif t == 'text' and rec.get('type') == 'assistant':
            yield 'text', None, None, b.get('text', '')


def audit(paths, name_sets):
    S = collections.defaultdict(lambda: {'counts': collections.Counter(), 'first': {}, 'hosts': collections.Counter()})

    def hit(sess, key, ts, n=1):
        S[sess]['counts'][key] += n
        if ts and (key not in S[sess]['first'] or ts < S[sess]['first'][key]):   # earliest time, not file order
            S[sess]['first'][key] = ts

    for f in iter_files(paths):
        stem = os.path.splitext(os.path.basename(f))[0]
        net_calls = {}                                   # tool_use_id -> True if the call is a net/wildfire.gov call
        for line in open(f, encoding='utf-8', errors='replace'):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            sess = rec.get('sessionId') or stem
            ts = rec.get('timestamp', '')
            for field, tool, tid, text in blocks(rec):
                if WILDFIRE.search(text):
                    hit(sess, 'wildfire_gov_' + field, ts)
                if FTP2526.search(text) or (field == 'input' and WILDFIRE.search(text) and YEAR2526.search(text)):
                    hit(sess, 'ftp2526_' + field, ts)
                if field == 'input':
                    for k, rx in FILES.items():
                        if re.search(rx, text):
                            hit(sess, k + '_input', ts)
                    if NIROPS.search(text) and READ.search(text):
                        hit(sess, 'nirops_read', ts)
                        if not FILTERED.search(text):
                            hit(sess, 'nirops_unfiltered', ts)
                    if GOFER.search(text):
                        hit(sess, 'gofer_read', ts)
                    is_web = tool in WEBTOOLS or ((tool or '').lower() == 'agent' and re.search(r'web-fetch|https?://', text))
                    if is_web:
                        hit(sess, 'web_tool', ts)
                    is_net = bool(NETCMD.search(text)) or is_web
                    if is_net:
                        hit(sess, 'net_cmd', ts)
                    if is_net or WILDFIRE.search(text):
                        net_calls[tid] = True
                    for u in URL.findall(text):                       # hosts from EVERY tool input
                        S[sess]['hosts'][safe_host(u)] += 1
                elif field == 'result':
                    for k, rx in FILES.items():
                        if re.search(rx, text):
                            hit(sess, k + '_in_result', ts)
                    if net_calls.pop(tid, False) and YEAR2526.search(text):
                        hit(sess, 'net_result_2025_2026', ts)
                if name_sets:
                    hs = ngram_hashes(text)
                    for label, hset in name_sets.items():
                        n = len(hs & hset)
                        if n:
                            hit(sess, f'names:{label}_{field}', ts, n)
    return S


FTPURL = re.compile(r'(?:https?|ftp)://ftp\.wildfire\.gov(/[^\s\'"<>)\]\\,]*)', re.I)
STATUS = re.compile(r'\bHTTP/[\d.]+\s+(\d{3})\b|\bhttp_code[=:\s]+(\d{3})\b|\b(\d{3})\s+(?:Not Found|OK|Forbidden|Unauthorized|Moved)\b|^\s*([1-5]\d\d)\s*$', re.M)


SAFE_ROOTS = {'public/incident_specific_data', 'public/incident_specific_maps', 'public/nirops', 'protected/incident_specific_data'}
SAFE_GACCS = {'calif_n', 'calif_s', 'great_basin', 'n_rockies', 'pacific_nw', 'rocky_mtn', 'southwest', 'alaska',
              'eastern', 'southern', 'national'}
SAFE_YEAR = re.compile(r'(Z_)?20\d\d(_Incidents(_(Oregon|Washington|Idaho|Montana|California|Nevada|Utah|Arizona|NewMexico|Colorado|Wyoming|Alaska))?)?')


def h12(x):
    return hashlib.sha256(x.encode()).hexdigest()[:12]


def ftp_detail(paths):
    """Per session, every ftp.wildfire.gov URL in a tool INPUT, reduced to (root, gacc, year segment), each printed in
    clear ONLY when it equals a known layout token (else as h:<sha12>), plus the sha256 of the remaining path, and the HTTP status codes found in the matching tool RESULT."""
    rows = collections.Counter()
    for f in iter_files(paths):
        stem = os.path.splitext(os.path.basename(f))[0]
        pending = {}
        for line in open(f, encoding='utf-8', errors='replace'):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            sess = rec.get('sessionId') or stem
            m = rec.get('message')
            if not isinstance(m, dict) or not isinstance(m.get('content'), list):
                continue
            for b in m['content']:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'tool_use':
                    keys = []
                    for p in FTPURL.findall(json.dumps(b.get('input'), ensure_ascii=False)):
                        seg = [x for x in p.split('/') if x]
                        root = '/'.join(seg[:2])
                        if root not in SAFE_ROOTS:
                            root = 'h:' + h12(root)
                        gacc = seg[2] if len(seg) > 2 else ''
                        if gacc and gacc not in SAFE_GACCS:
                            gacc = 'h:' + h12(gacc)
                        year = seg[3] if len(seg) > 3 else ''
                        if year and not SAFE_YEAR.fullmatch(year):
                            year = 'h:' + h12(year)
                        rest = h12('/'.join(seg[4:])) if len(seg) > 4 else ''
                        keys.append((sess, rec.get('timestamp', '')[:16], root, gacc, year, rest))
                    if keys:
                        pending[b.get('id')] = keys
                elif b.get('type') == 'tool_result' and b.get('tool_use_id') in pending:
                    cc = b.get('content')
                    if isinstance(cc, list):
                        cc = ' '.join(x.get('text', '') for x in cc if isinstance(x, dict))
                    codes = sorted({next(g for g in t if g) for t in STATUS.findall(str(cc))}) or ['-']
                    for k in pending.pop(b.get('tool_use_id')):
                        rows[k + (','.join(codes),)] += 1
    print('session\tminute_utc\troot\tgacc\tyear_segment\trest_sha12\tstatus_codes_in_result\tn')
    for k, n in sorted(rows.items()):
        print('\t'.join(k) + f'\t{n}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--names', action='append', default=[], help='LABEL=hash_list.txt (sha256 per line)')
    ap.add_argument('--make-hashes', help='plain name list -> sha256 list on stdout (custodian only)')
    ap.add_argument('--ftp-detail', action='store_true',
                    help='list ftp.wildfire.gov requests as root/gacc/year + hashed rest + status codes (no names)')
    a = ap.parse_args()
    if a.ftp_detail:
        ftp_detail(a.paths)
        return
    if a.make_hashes:
        for line in open(a.make_hashes, encoding='utf-8'):
            if line.strip():
                print(name_hash(line.strip()))
        return
    name_sets = {}
    for spec in a.names:
        label, path = spec.split('=', 1)
        name_sets[label] = {l.strip() for l in open(path) if re.fullmatch(r'[0-9a-f]{64}', l.strip())}
    S = audit(a.paths, name_sets)
    keys = sorted({k for s in S.values() for k in s['counts']})
    print('\t'.join(['session'] + [f'{k}(n|first)' for k in keys] + ['mentioned_hosts_in_tool_inputs']))
    for sess in sorted(S):
        s = S[sess]
        cells = [f"{s['counts'][k]}|{s['first'].get(k, '')}" if s['counts'][k] else '' for k in keys]
        hosts = ','.join(f'{h}:{n}' for h, n in s['hosts'].most_common())
        print('\t'.join([sess] + cells + [hosts]))


if __name__ == '__main__':
    main()
