"""Static checks: the vendored decoder, wording (test 5), language files, colours and contrast (test 8), git-ignored
private data (test 6) and what the app never sends (test 13)."""
import ast
import hashlib
import json
import re

from conftest import ROOT

OWN_TEXT = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in (".py", ".js", ".css", ".html", ".json", ".md", ".sh", ".txt")
            and "vendor" not in p.parts and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
            and "out" not in p.parts and "logs" not in p.parts and "devices" not in p.parts]
VENDOR_TEXT = [p for p in list((ROOT / "web" / "vendor").rglob("*")) + list((ROOT / "app" / "vendor").glob("*"))
               if p.is_file() and p.suffix in (".py", ".js", ".css", ".md", ".txt")]


def test_vendored_usb_export_is_unmodified():
    sha = hashlib.sha256((ROOT / "app" / "vendor" / "usb_export.py").read_bytes()).hexdigest()
    readme = (ROOT / "app" / "vendor" / "README.md").read_text(encoding="utf-8")
    assert sha in readme, "app/vendor/usb_export.py changed; re-vendor from the planning package and record the SHA-256"


def test_vendored_maplibre_has_only_the_recorded_change():
    """web/vendor/README.md: the release file with its two dash keys written as escapes, nothing else."""
    sha = hashlib.sha256((ROOT / "web" / "vendor" / "maplibre-gl" / "maplibre-gl.js").read_bytes()).hexdigest()
    assert sha in (ROOT / "web" / "vendor" / "README.md").read_text(encoding="utf-8")


def test_forbidden_word_and_dashes():
    word = "".join(chr(c) for c in (0xC2E4, 0xC2DC, 0xAC04))      # built from code points: this file stays clean
    bad_word, bad_dash = [], []
    for p in OWN_TEXT + VENDOR_TEXT:                                 # vendored files too (web/vendor/README.md)
        text = p.read_text(encoding="utf-8", errors="replace")
        if word in text:
            bad_word.append(str(p.relative_to(ROOT)))
        if chr(0x2014) in text or chr(0x2013) in text:
            bad_dash.append(str(p.relative_to(ROOT)))
    assert not bad_word, bad_word
    assert not bad_dash, bad_dash


def test_language_files_have_the_same_keys_and_every_used_key_exists():
    ko = json.loads((ROOT / "web" / "i18n" / "ko.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "web" / "i18n" / "en.json").read_text(encoding="utf-8"))
    assert set(ko) == set(en)
    assert all(ko[k].strip() and en[k].strip() for k in ko)
    used = set()
    for p in (ROOT / "web" / "js").glob("*.js"):
        used |= set(re.findall(r"""\bth?\(\s*['"]([a-z][a-zA-Z0-9_.]+)['"]""", p.read_text(encoding="utf-8")))
    missing = sorted(k for k in used if k not in ko)
    assert not missing, missing
    # the app's own stream lines (backend codes) all have both texts
    src = (ROOT / "app" / "device" / "manager.py").read_text() + (ROOT / "app" / "device" / "conncheck.py").read_text()
    codes = set(re.findall(r'app_line\("([a-z_]+)"', src))
    assert codes and all("stream." + c in ko for c in codes), sorted(c for c in codes if "stream." + c not in ko)
    # the placeholders match between the languages
    for k in ko:
        assert set(re.findall(r"\{(\w+)\}", ko[k])) == set(re.findall(r"\{(\w+)\}", en[k])), k


def test_korean_sentences_end_politely():
    ko = json.loads((ROOT / "web" / "i18n" / "ko.json").read_text(encoding="utf-8"))
    for k, v in ko.items():
        for sentence in re.split(r"(?<=[.?])\s+", v):
            s = sentence.strip()
            if s.endswith(".") and re.search(r"[가-힣]\.$", s):
                assert re.search(r"(니다|십시오|세요)\.$", s) or s.endswith("음.") or "(" in s, (k, s)


HEX = re.compile(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(")
NAMED = re.compile(r"\b(?:white|black|red|green|blue|gray|grey|transparent|orange|yellow|purple)\b")


def test_no_colour_literals_outside_tokens():
    """CSS: every declaration value; JS and HTML: hex, rgb() and hsl() anywhere outside comments."""
    hits = []
    for p in (ROOT / "web" / "css").glob("*.css"):
        if p.name == "tokens.css":
            continue
        css = re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.S)
        for m in re.finditer(r"([\w-]+)\s*:\s*([^;{}]+);", css):
            value = re.sub(r"var\(--[\w-]+\)", "", m.group(2))
            if HEX.search(value) or FUNC.search(value) or NAMED.search(value):
                hits.append("%s: %s: %s" % (p.name, m.group(1), value.strip()))
    for p in list((ROOT / "web" / "js").glob("*.js")) + [ROOT / "web" / "index.html"]:
        text = re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.S)
        text = re.sub(r"(?m)^\s*//.*$|(?<=[;{}),])\s*//.*$", "", text)
        for m in list(HEX.finditer(text)) + list(FUNC.finditer(text)):
            hits.append("%s: %s" % (p.name, text[max(0, m.start() - 20):m.end() + 10].replace("\n", " ")))
    assert not hits, hits


def _hex(c):
    c = c.strip()
    if c.startswith("#"):
        c = c[1:]
        return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)), 1.0
    m = re.match(r"rgba?\(([^)]*)\)", c)
    vals = [float(x) for x in m.group(1).split(",")]
    return tuple(v / 255 for v in vals[:3]), (vals[3] if len(vals) > 3 else 1.0)


def _lum(rgb):
    lin = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _blend(fg, alpha, bg):
    return tuple(f * alpha + b * (1 - alpha) for f, b in zip(fg, bg))


def _tokens(block):
    return {m.group(1): m.group(2) for m in re.finditer(r"--([\w-]+):\s*([^;]+);", block)}


def test_text_tokens_meet_wcag_aa():
    css = (ROOT / "web" / "css" / "tokens.css").read_text()
    dark = _tokens(css.split("body.light")[0])
    light = dict(dark, **_tokens(css.split("body.light")[1]))
    for theme, tk in (("dark", dark), ("light", light)):
        bg = _hex(tk["bg"])[0]
        surface = _hex(tk["surface"])[0]
        glass_rgb, glass_a = _hex(tk["glass"])
        glass = _blend(glass_rgb, glass_a, _hex(tk["map-land"])[0])
        pairs = [("text-1", bg), ("text-2", bg), ("text-3", bg), ("text-1", surface), ("text-2", surface), ("text-1", glass), ("text-2", glass)]
        if theme == "dark":
            pairs += [("text-4", bg), ("text-dim", bg), ("text-hex", bg), ("green-text", bg), ("green-text", surface), ("text-3", surface), ("error", bg)]
        else:
            pairs += [("green-text", bg), ("text-body", bg)]
        for name, back in pairs:
            r = _ratio(_hex(tk[name])[0], back)
            assert r >= 4.5, "%s %s on its background: %.2f" % (theme, name, r)
        # large text (the summary's hero number, 56 px) may use 3:1
        assert _ratio(_hex(tk["green-text-lg"])[0], bg) >= 3.0


def test_private_data_is_git_ignored():
    gi = (ROOT / ".gitignore").read_text()
    for entry in ("sessions/real/", "sessions/privacy.json", "sessions/zone_secret", "out/", "logs/", "devices/"):
        assert entry in gi.splitlines(), entry


def _string_constants(path):
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.append((node.name, sub.value))
    return out


def test_app_never_sends_delete_confirm_or_format_and_calvbat_only_from_the_form():
    for p in (ROOT / "app" / "device").glob("*.py"):
        if p.name in ("double.py", "notes.py"):
            continue                         # the double plays the device; notes only read lines
        for fn, s in _string_constants(p):
            if re.match(r"^(DELETE|CONFIRM|FORMAT)\b", s):
                raise AssertionError("%s sends %r in %s()" % (p.name, s, fn))
            if s.startswith("CALVBAT"):
                assert p.name == "manager.py" and fn == "calibrate", (p.name, fn, s)
    for p in (ROOT / "web" / "js").glob("*.js"):
        text = p.read_text()
        assert not re.search(r"['\"`](DELETE|CONFIRM|FORMAT)\s", text), p.name
