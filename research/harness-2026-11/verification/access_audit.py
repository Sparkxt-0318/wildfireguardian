#!/usr/bin/env python3
"""Mechanical access audit over Claude Code session transcripts (owner-runnable; stdlib only).

Why: the S-D9 sealed-data audit (verification ledger rows 38, 45 and 46) rests partly on session declarations.
This script checks those declarations against what the transcripts record.

Input: Claude Code transcript files (*.jsonl), or directories containing them.
- A session's transcript lives in its own container under ~/.claude/projects/<project>/<session-uuid>.jsonl.
- Subagent transcripts live under <session-uuid>/subagents/*.jsonl.
- The owner collects them; see "Access" below.

Output: one TSV row per session (sessionId from the records, else the file stem), with counts and the first UTC time
for each category below. Fire names are never printed: name matching uses hash lists only.

Categories:
  F1..F5    tool calls whose INPUT names the file (an access attempt), and tool results that contain its path
  nirops    tool calls reading the raw NIROPS shapefile/dbf (pyogrio/fiona/ogr/geopandas/unzip). An unfiltered read is
            one with no where=, no fids= and no Incident_C-only column list
  gofer     tool calls reading raw GOFER files (GOFER zip, fireProg, fireLine, GOFERC_fireIg)
  web       WebSearch/WebFetch/web-fetch agent calls, and curl/wget/requests/urllib calls; external hosts are listed
  ftp2526   any tool input or result naming ftp.wildfire.gov together with a 2025 or 2026 path segment
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
READ = re.compile(r'read_dataframe|read_info|pyogrio|fiona|ogr\.|ogrinfo|gpd\.read_file|geopandas|unzip|read_file\(', re.I)
FILTERED = re.compile(r"where\s*=|fids\s*=|columns\s*=\s*\[\s*['\"]Incident_C['\"]\s*\]|nirops_access", re.I)
GOFER = re.compile(r'GOFER[^\s\'"]*\.zip|fireProg|fireLine|GOFERC_fireIg', re.I)
NETCMD = re.compile(r'\b(curl|wget)\b|requests\.(get|post)|urlopen|urllib\.request', re.I)
URL = re.compile(r'https?://[^\s\'"<>)\]]+', re.I)
FTP2526 = re.compile(r'ftp\.wildfire\.gov[^\s\'"]*(?:/|_)(2025|2026)(?:/|_)', re.I)
WEBTOOLS = {'WebSearch', 'WebFetch'}


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
    """Yields (field, tool_name, text) for tool inputs, tool results and assistant text."""
    m = rec.get('message')
    if not isinstance(m, dict):
        return
    c = m.get('content')
    if isinstance(c, str):
        yield ('text' if rec.get('type') == 'assistant' else 'user_text', None, c)
        return
    for b in c or []:
        if not isinstance(b, dict):
            continue
        t = b.get('type')
        if t == 'tool_use':
            yield 'input', b.get('name'), json.dumps(b.get('input'), ensure_ascii=False)
        elif t == 'tool_result':
            cc = b.get('content')
            if isinstance(cc, list):
                cc = ' '.join(x.get('text', '') for x in cc if isinstance(x, dict))
            yield 'result', None, str(cc)
        elif t == 'text' and rec.get('type') == 'assistant':
            yield 'text', None, b.get('text', '')


def audit(paths, name_sets):
    S = collections.defaultdict(lambda: {'counts': collections.Counter(), 'first': {}, 'hosts': collections.Counter()})

    def hit(sess, key, ts, n=1):
        S[sess]['counts'][key] += n
        S[sess]['first'].setdefault(key, ts)

    for f in iter_files(paths):
        stem = os.path.splitext(os.path.basename(f))[0]
        for line in open(f, encoding='utf-8', errors='replace'):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            sess = rec.get('sessionId') or stem
            ts = rec.get('timestamp', '')
            for field, tool, text in blocks(rec):
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
                    if tool in WEBTOOLS or (tool or '').lower() == 'agent' and 'web-fetch' in text:
                        hit(sess, 'web_tool', ts)
                    if NETCMD.search(text):
                        hit(sess, 'net_cmd', ts)
                        for u in URL.findall(text):
                            S[sess]['hosts'][urlparse(u).netloc.lower()] += 1
                elif field == 'result':
                    for k, rx in FILES.items():
                        if re.search(rx, text):
                            hit(sess, k + '_in_result', ts)
                if FTP2526.search(text):
                    hit(sess, 'ftp2526_' + field, ts)
                if name_sets:
                    hs = ngram_hashes(text)
                    for label, hset in name_sets.items():
                        n = len(hs & hset)
                        if n:
                            hit(sess, f'names:{label}_{field}', ts, n)
    return S


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--names', action='append', default=[], help='LABEL=hash_list.txt (sha256 per line)')
    ap.add_argument('--make-hashes', help='plain name list -> sha256 list on stdout (custodian only)')
    a = ap.parse_args()
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
    print('\t'.join(['session'] + [f'{k}(n|first)' for k in keys] + ['external_hosts']))
    for sess in sorted(S):
        s = S[sess]
        cells = [f"{s['counts'][k]}|{s['first'].get(k, '')}" if s['counts'][k] else '' for k in keys]
        hosts = ','.join(f'{h}:{n}' for h, n in s['hosts'].most_common())
        print('\t'.join([sess] + cells + [hosts]))


if __name__ == '__main__':
    main()
