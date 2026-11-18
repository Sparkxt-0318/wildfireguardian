"""Fonts for the KCF scene: planner/public/kcf-scene/data/fonts.js (window.KCF.fonts).

* glyphs: MapLibre SDF glyph ranges of "Noto Sans Regular" (0-255 and 8192-8447) from the planner basemap
  (planner/public/basemap/fonts/, provenance in planner/public/basemap/ATTRIBUTION.md and SOURCES.json), base64.
  Hangul map labels are not in these ranges; MapLibre draws them with localIdeographFontFamily = the ui family below.
* ui: one variable woff2 face (wght axis of the source), a subset of PretendardVariable.ttf (SIL OFL 1.1) to
  printable ASCII, Latin-1 punctuation (U+00A0-00BF, U+00D7, U+00F7) and EVERY character that occurs in the scene's
  index.html, app.js, style.css, data/scene.js and data/basemap.js (whichever exist; JS/JSON \\u escapes, HTML
  entities and CSS escapes are decoded first). Re-run this script after those files change.
  Pretendard declares the Reserved Font Name "Pretendard"; a subset is a Modified Version (OFL section 3), so the
  subset is renamed in its name table and served under the family "KCF UI Sans". The copyright, trademark,
  designer and license records are kept, and the OFL text is copied to vendor/LICENSE-pretendard.txt.

Usage: pip install fonttools brotli; python3 research/kcf-replay/scene/build_fonts.py
"""
from __future__ import annotations

import base64, hashlib, html, io, json, re, shutil, subprocess, unicodedata
from pathlib import Path

import fontTools
from fontTools import subset

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SCENE = "planner/public/kcf-scene"
OUT = ROOT / SCENE / "data/fonts.js"
SCRIPT = "research/kcf-replay/scene/build_fonts.py"
GLYPH_STACK = "Noto Sans Regular"
GLYPH_DIR = "planner/public/basemap/fonts/Noto Sans Regular"
GLYPH_RANGES = ["0-255", "8192-8447"]
PRET_PKG = "planner/node_modules/pretendard"
PRET_TTF = f"{PRET_PKG}/dist/public/variable/PretendardVariable.ttf"
PRET_LICENSE = f"{PRET_PKG}/dist/LICENSE.txt"
LICENSE_OUT = f"{SCENE}/vendor/LICENSE-pretendard.txt"
SCAN = [f"{SCENE}/index.html", f"{SCENE}/app.js", f"{SCENE}/style.css", f"{SCENE}/data/scene.js",
        f"{SCENE}/data/basemap.js"]
FAMILY = "KCF UI Sans"
PS_FAMILY = "KCFUISans"
BASE_CHARS = ([chr(c) for c in range(0x20, 0x7F)] + [chr(c) for c in range(0xA0, 0xC0)] + ["\u00d7", "\u00f7"])
FEATURES = sorted(set(subset.Options().layout_features) | {"tnum"})  # tnum: fixed-width clock digits


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rec(rel, b, inputs, **extra):
    inputs.append({"path": rel, "bytes": len(b), "sha256": sha(b), **extra})


def decode_escapes(text, kind):
    """Characters a browser would render from this text, in addition to the raw ones."""
    out = []
    # JS / JSON \\uXXXX (with surrogate pairs) and \\u{X...}
    s = re.sub(r"\\u\{([0-9a-fA-F]{1,6})\}", lambda m: chr(int(m.group(1), 16)), text)
    s = re.sub(r"\\u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})",
               lambda m: chr(0x10000 + ((int(m.group(1), 16) - 0xD800) << 10) + (int(m.group(2), 16) - 0xDC00)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    out.append(s)
    if kind in (".html", ".js"):
        out.append(html.unescape(text))
    if kind == ".css":
        out.append(re.sub(r"\\([0-9a-fA-F]{1,6}) ?", lambda m: chr(int(m.group(1), 16)), text))
    return "".join(out)


def wanted(c):
    cat = unicodedata.category(c)
    return not (cat in ("Cc", "Cs", "Co", "Cn") or (cat.startswith("Z") and c not in (" ", "\u00a0")))


def rename(font):
    """Remove the Reserved Font Name from every naming record of the subset (OFL section 3)."""
    name = font["name"]
    keep = {0, 7, 8, 9, 10, 11, 12, 13, 14}  # copyright, trademark, manufacturer, designer, description, urls, license
    changed = []
    for r in list(name.names):
        s = r.toUnicode()
        if r.nameID in keep or "retendard" not in s:
            continue
        if r.nameID in (1, 16):
            new = FAMILY
        elif r.nameID == 3:
            new = s.replace("PretendardVariable", PS_FAMILY + "-Subset")
        elif r.nameID == 4:
            new = FAMILY
        else:  # 6, 25 and the named-instance PostScript names
            new = s.replace("PretendardVariable", PS_FAMILY).replace("Pretendard", PS_FAMILY)
        name.setName(new, r.nameID, r.platformID, r.platEncID, r.langID)
        changed.append([r.nameID, s, new])
    left = [(r.nameID, r.toUnicode()) for r in name.names if r.nameID not in keep and "retendard" in r.toUnicode()]
    if left:
        raise SystemExit(f"reserved font name still present in {left}")
    return changed


def main():
    inputs = []
    # ---- MapLibre glyph ranges ----
    glyphs = {}
    for rng in GLYPH_RANGES:
        rel = f"{GLYPH_DIR}/{rng}.pbf"
        p = ROOT / rel
        if not p.exists():
            print(f"  glyph range {rng} not present, skipped")
            continue
        b = p.read_bytes()
        rec(rel, b, inputs)
        glyphs[rng] = base64.b64encode(b).decode("ascii")

    # ---- character set ----
    chars = set(BASE_CHARS)
    scanned = []
    for rel in SCAN:
        p = ROOT / rel
        if not p.exists():
            scanned.append({"path": rel, "exists": False})
            continue
        b = p.read_bytes()
        rec(rel, b, inputs, role="scanned for characters")
        t = b.decode("utf-8")
        found = {c for c in t + decode_escapes(t, p.suffix) if wanted(c)}
        scanned.append({"path": rel, "exists": True, "chars": len(found)})
        chars |= found

    # ---- Pretendard subset ----
    src = (ROOT / PRET_TTF).read_bytes()
    rec(PRET_TTF, src, inputs)
    pkg = json.loads((ROOT / PRET_PKG / "package.json").read_text())
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = FEATURES
    opts.hinting = False
    opts.name_IDs = ["*"]
    opts.recalc_timestamp = False
    font = subset.load_font(str(ROOT / PRET_TTF), opts)
    cmap = font.getBestCmap()
    axes = {a.axisTag: [a.minValue, a.defaultValue, a.maxValue] for a in font["fvar"].axes}
    have = sorted(c for c in chars if ord(c) in cmap)
    missing = sorted(c for c in chars if ord(c) not in cmap)
    ss = subset.Subsetter(opts)
    ss.populate(unicodes=[ord(c) for c in have])
    ss.subset(font)
    renamed = rename(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, opts)
    woff2 = buf.getvalue()
    wmin, _, wmax = axes["wght"]
    weight = f"{int(wmin)} {int(wmax)}"

    lic = (ROOT / PRET_LICENSE).read_bytes()
    rec(PRET_LICENSE, lic, inputs)
    (ROOT / LICENSE_OUT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / PRET_LICENSE, ROOT / LICENSE_OUT)

    for rel in ("planner/public/basemap/ATTRIBUTION.md", "planner/public/basemap/SOURCES.json"):
        rec(rel, (ROOT / rel).read_bytes(), inputs, role="glyph provenance")

    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    obj = {
        "glyphs": {GLYPH_STACK: glyphs},
        "glyphs_info": {
            "fontstack": GLYPH_STACK, "ranges": sorted(glyphs),
            "missing_range": "return an empty ArrayBuffer",
            "from": GLYPH_DIR,
            "provenance": ["planner/public/basemap/ATTRIBUTION.md", "planner/public/basemap/SOURCES.json"],
            "upstream": "https://protomaps.github.io/basemaps-assets/fonts/{fontstack}/{range}.pbf",
            "license": "Noto Sans: SIL Open Font License 1.1 (no Noto license text in the repository; see provenance)"},
        "ui": {
            "family": FAMILY,
            "faces": [{"weight": weight, "style": "normal", "axes": axes,
                       "src": "data:font/woff2;base64," + base64.b64encode(woff2).decode("ascii")}],
            "woff2_bytes": len(woff2),
            "chars": "".join(have),
            "char_count": len(have),
            "missing": "".join(missing),
            "scanned": scanned,
            "derived_from": f"Pretendard {pkg['version']} ({PRET_TTF}), SIL OFL 1.1, Reserved Font Name 'Pretendard'",
            "modification": "subset (fontTools); renamed in the name table so the Reserved Font Name is not used",
            "renamed": renamed,
            "features": FEATURES,
            "license": "SIL OFL 1.1, " + LICENSE_OUT,
        },
        "built": {"script": SCRIPT, "commit": commit, "fonttools": fontTools.version, "inputs": inputs},
    }
    js = f"// built by {SCRIPT} (do not edit)\n(window.KCF=window.KCF||{{}}).fonts=" + \
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + ";\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(js, encoding="ascii")
    print(f"wrote {OUT.relative_to(ROOT)}: {OUT.stat().st_size} bytes")
    print(f"  glyph ranges {sorted(glyphs)}: " + ", ".join(f"{k} {len(base64.b64decode(v))} B" for k, v in sorted(glyphs.items())))
    hangul = sum(1 for c in have if 0xAC00 <= ord(c) <= 0xD7A3)
    print(f"  ui face '{FAMILY}' weight {weight}: woff2 {len(woff2)} B, {len(have)} chars ({hangul} Hangul syllables)")
    print(f"  not in Pretendard ({len(missing)}): {' '.join(f'U+{ord(c):04X}' for c in missing)}")
    print("  scanned: " + ", ".join(f"{s['path'].split('/')[-1]}={s.get('chars', 'absent')}" for s in scanned))
    print(f"  copied {PRET_LICENSE} -> {LICENSE_OUT}")


if __name__ == "__main__":
    main()
