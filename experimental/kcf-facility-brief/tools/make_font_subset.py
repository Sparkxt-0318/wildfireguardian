#!/usr/bin/env python3
"""Rebuild assets/fonts/NotoSansKR-subset-{400,700}.woff2 (see assets/fonts/README.md).

  npm pack @fontsource/noto-sans-kr@5.3.1 && tar -xzf fontsource-noto-sans-kr-5.3.1.tgz
  pip install fonttools brotli
  python3 tools/make_font_subset.py <extracted>/package . <outdir>

The name table is then renamed to "KCF Noto Sans KR Subset" (see README). Not run by verify.sh.
"""
import sys, glob, os, json
from fontTools.ttLib import TTFont
from fontTools.merge import Merger
from fontTools import subset
pkg, kdir, out = sys.argv[1], sys.argv[2], sys.argv[3]
# target characters
chars = set(chr(c) for c in range(0x20, 0x7f))
for lead in range(0xB0, 0xC9):
    for trail in range(0xA1, 0xFF):
        try: chars.add(bytes([lead, trail]).decode('cp949'))
        except UnicodeDecodeError: pass
chars |= set('·—–→←↔≠≤≥×÷~°′″…‘’“”「」『』【】○●□■☐☑✓※▶◀▲▼①②③④⑤')
for root in ('src', 'fixtures', 'docs', 'qa/planner-4169ccc/inputs'):
    for p in glob.glob(os.path.join(kdir, root, '**', '*'), recursive=True):
        if os.path.isfile(p) and p.endswith(('.js', '.json', '.html', '.md', '.css')):
            chars |= set(open(p, encoding='utf-8').read())
chars = {c for c in chars if ord(c) >= 0x20}
uni = sorted(ord(c) for c in chars)
print('target codepoints', len(uni))
os.makedirs(out, exist_ok=True)
for w in ('400', '700'):
    files = sorted(glob.glob(os.path.join(pkg, 'files', f'noto-sans-kr-*-{w}-normal.woff2')))
    files = [f for f in files if not any(s in f for s in ('cyrillic', 'vietnamese'))]
    tmp = []
    for i, f in enumerate(files):
        t = TTFont(f)
        cmap = set(t.getBestCmap() or {})
        keep = [u for u in uni if u in cmap]
        if not keep: continue
        o = subset.Options(); o.layout_features = ['*']; o.name_IDs = ['*']; o.notdef_outline = True
        s = subset.Subsetter(o); s.populate(unicodes=keep); s.subset(t)
        t.flavor = None
        p = os.path.join(out, f'_p{w}_{i}.otf'); t.save(p); tmp.append(p)
    m = Merger().merge(tmp)
    m.flavor = 'woff2'
    dst = os.path.join(out, f'NotoSansKR-subset-{w}.woff2'); m.save(dst)
    have = set(TTFont(dst).getBestCmap())
    missing = [hex(u) for u in uni if u not in have]
    print(w, len(tmp), 'parts ->', dst, os.path.getsize(dst), 'bytes; missing', len(missing), missing[:20])
    for p in tmp: os.remove(p)
