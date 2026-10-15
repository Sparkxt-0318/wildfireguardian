"""The "Become an ember" phone page (booth/ember/index.html), checked without a browser: one
self-contained file with no network requests, the instruction overlay in both languages with
its 3 s fade, the wake lock with its video fallback, and the look the booth's synthetic phones copy."""
import base64
import re
from html.parser import HTMLParser

import av
import numpy as np
import pytest

from wfglink import PROJECT_ROOT

PAGE = PROJECT_ROOT / "booth" / "ember" / "index.html"
README = PROJECT_ROOT / "booth" / "ember" / "README.md"
DATA_URI_RE = re.compile(r"data:[\w/+.\-]+(?:;[\w\-]+=[\w\-]+)*;base64,[A-Za-z0-9+/=]+")


class _Parsed(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict]] = []
        self.text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: (v or "") for k, v in attrs}))
        if tag in ("script", "style", "title"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "title"):
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.text.append(" ".join(data.split()))


@pytest.fixture(scope="module")
def html() -> str:
    return PAGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed(html) -> _Parsed:
    p = _Parsed()
    p.feed(html)
    return p


def _css(html: str) -> str:
    return re.search(r"<style>(.*?)</style>", html, re.S).group(1)


def _keyframes(css: str, name: str) -> list[tuple[float, float, float]]:
    block = re.search(r"@keyframes %s\s*\{(.*?)\n\}" % name, css, re.S).group(1)
    rows = re.findall(r"([\d.]+)%\s*\{\s*opacity:\s*([\d.]+);\s*transform:\s*scale\(([\d.]+)\);\s*\}", block)
    return [(float(p), float(o), float(s)) for p, o, s in rows]


def test_page_is_one_small_file_with_no_network_requests(html, parsed):
    assert len(PAGE.read_bytes()) < 100_000
    # Every src or href is a data URI: no http, https, protocol-relative or relative paths.
    for tag, attrs in parsed.tags:
        for key in ("src", "href", "srcset", "poster", "data", "action"):
            if key in attrs:
                assert attrs[key].startswith("data:"), (tag, key, attrs[key][:40])
        assert tag not in ("iframe", "img", "object", "embed", "base", "form", "audio")
        if tag == "script":
            assert "src" not in attrs
        if tag == "link":
            assert attrs.get("rel") in ("icon", "apple-touch-icon")
    # Both icons are inline, so a phone that bookmarks the page asks the host for no icon file.
    assert {a.get("rel") for t, a in parsed.tags if t == "link"} == {"icon", "apple-touch-icon"}
    # Outside the data URIs, no URL at all, in markup, CSS or script.
    rest = DATA_URI_RE.sub("DATA", html)
    assert not re.search(r"https?:", rest)
    assert not re.search(r"""["'(]\s*//""", rest)                 # protocol-relative URL
    assert not re.search(r"url\(\s*(?!['\"]?DATA)", rest)         # CSS url() other than a data URI
    for banned in ("@import", "fetch(", "XMLHttpRequest", "serviceWorker", "import(", "WebSocket",
                   "EventSource", "sendBeacon", "localStorage", "@font-face"):
        assert banned not in rest, banned
    # The browser enforces it too.
    csp = next(a["content"] for t, a in parsed.tags if t == "meta" and a.get("http-equiv") == "Content-Security-Policy")
    assert "default-src 'none'" in csp
    assert not re.search(r"(?:img|media|style|script)-src[^;]*(?:https?:|\*|'self')", csp)


def test_head_viewport_theme_and_title(html, parsed):
    metas = {a.get("name"): a.get("content", "") for t, a in parsed.tags if t == "meta" and a.get("name")}
    vp = metas["viewport"].replace(" ", "")
    for part in ("width=device-width", "initial-scale=1", "maximum-scale=1", "user-scalable=no", "viewport-fit=cover"):
        assert part in vp.split(","), part
    theme = metas["theme-color"].lstrip("#")
    assert len(theme) == 6 and max(int(theme[i:i + 2], 16) for i in (0, 2, 4)) <= 0x20   # dark
    assert metas["color-scheme"] == "dark"
    html_tag = next(a for t, a in parsed.tags if t == "html")
    assert html_tag.get("lang") == "ko"
    title = html.split("<title>")[1].split("</title>")[0]
    assert 0 < len(title.split()) <= 4 and "Ember" in title and "불티" in title


def test_overlay_text_in_both_languages_fades_after_3_s(html, parsed):
    shown = " | ".join(parsed.text)
    for line in ("휴대폰 화면을 카메라 쪽으로 들고 움직여 보세요",
                 "Hold your screen toward the camera and move it",
                 "화면 밝기를 최대로 · Turn brightness up"):
        assert line in shown, line
    assert len(parsed.text) == 3                                   # nothing else on screen, ever
    css = _css(html)
    m = re.search(r"\.hint-body\s*\{[^}]*animation:\s*hint-out\s+([\d.]+)s\s+[\w\-]+\s+([\d.]+)s\s+forwards", css)
    assert m and float(m.group(2)) == 3.0 and 0.3 <= float(m.group(1)) <= 1.0
    out = re.search(r"@keyframes hint-out\s*\{(.*?)\n\}", css, re.S).group(1)
    assert re.search(r"to\s*\{\s*opacity:\s*0;\s*visibility:\s*hidden;", out)
    # A tap hides it at once and it leaves the page once gone; a timer covers browsers without animations.
    assert re.search(r"\.hint\.off\s*\{\s*opacity:\s*0;", css)
    assert 'e.animationName === "hint-out"' in html and "setTimeout(dropHint, 4500)" in html


def test_wake_lock_with_reacquire_and_video_fallback(html):
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    assert re.search(r"""wakeLock\.request\(\s*["']screen["']\s*\)""", js)
    assert re.search(r"""addEventListener\(\s*["']visibilitychange["']\s*,\s*keepAwake\s*\)""", js)
    assert re.search(r"""addEventListener\(\s*["']release["']""", js)
    assert "keepAwake();" in js                                   # asked for at load, and on every tap
    # Fallback where the API is missing or refuses: a muted, inline, looping video from a data URI.
    for attr in ('"muted"', '"loop"', '"playsinline"', '"webkit-playsinline"'):
        assert f"video.setAttribute({attr}" in js, attr
    assert "video.muted = true" in js and "video.loop = true" in js
    assert re.search(r'var MP4 = "data:video/mp4;base64,', js) and re.search(r'var WEBM = "data:video/webm;base64,', js)
    # Fullscreen on a tap where allowed, and no scrolling, zoom, pull-to-refresh or selection.
    assert "requestFullscreen" in js and "webkitRequestFullscreen" in js
    css = _css(html)
    for rule in ("overflow: hidden", "overscroll-behavior: none", "touch-action: none", "user-select: none",
                 "-webkit-user-select: none", "-webkit-touch-callout: none"):
        assert rule in css, rule
    assert re.search(r"""addEventListener\(\s*["']touchmove["']\s*,\s*stop\s*,\s*\{\s*passive:\s*false""", js)


@pytest.mark.parametrize("kind", ["mp4", "webm"])
def test_embedded_keep_awake_videos_decode(html, tmp_path, kind):
    m = re.search(r"data:video/%s;base64,([A-Za-z0-9+/=]+)" % kind, html)
    path = tmp_path / f"awake.{kind}"
    path.write_bytes(base64.b64decode(m.group(1)))
    with av.open(str(path)) as c:
        assert len(c.streams.video) == 1 and len(c.streams.audio) == 1   # NoSleep keeps an audio track
        frames = [f.to_ndarray(format="gray") for f in c.decode(video=0)]
        dur = float(c.duration) / av.time_base if c.duration else None
    assert frames and max(float(np.mean(f)) for f in frames) < 20   # black
    assert dur is not None and 0.5 <= dur <= 2.0
    codec = {"mp4": "avc1.42C01E", "webm": "vp8, opus"}[kind]
    assert codec in html                                           # the <source> type names what is there


def test_ember_look_matches_the_contract(html):
    css = _css(html)
    # A centred disc of radius 0.36 x the shorter side, with the contract's gradient.
    assert "--ember: 72vmin;" in css and "--ember: 72dvmin;" in css
    assert re.search(r"radial-gradient\(circle closest-side,\s*#FFF1D6 0%,\s*#FFC266 18%,\s*#FF8A1F 45%,\s*"
                     r"rgba\(255, 90, 0, 0\.35\) 70%,\s*(?:transparent|rgba\(255, 90, 0, 0\)) 100%\)", css)
    assert re.search(r":root\s*\{[^}]*background:\s*#000", css) and "background: #000;" in css
    # Flicker: brightness 0.85 to 1.0 and scale 0.97 to 1.0 even when both layers dip together,
    # smooth (eased, looping without a jump) at about 2 to 6 Hz.
    periods = dict(re.findall(r"animation-name:\s*(\w+);\s*animation-duration:\s*([\d.]+)s", css))
    lo_op, lo_sc = 1.0, 1.0
    for name in ("flicker", "drift"):
        kf = _keyframes(css, name)
        pct = [k[0] for k in kf]
        assert pct[0] == 0 and pct[-1] == 100 and pct == sorted(pct)
        assert kf[0][1:] == kf[-1][1:]
        assert all(0.85 <= o <= 1.0 and 0.97 <= s <= 1.0 for _, o, s in kf)
        lo_op *= min(o for _, o, _ in kf)
        lo_sc *= min(s for _, _, s in kf)
        if name == "flicker":
            ops = [o for _, o, _ in kf]
            turns = sum(1 for a, b, c in zip(ops, ops[1:], ops[2:]) if (b - a) * (c - b) < 0)
            hz = (turns + 1) / 2 / float(periods[name])
            assert 2.0 <= hz <= 6.0, hz
    assert lo_op >= 0.85 and lo_sc >= 0.97
    assert "animation-timing-function: ease-in-out" in css


def test_page_and_readme_have_no_long_dashes():
    for path in (PAGE, README):
        text = path.read_text(encoding="utf-8")
        assert "—" not in text and "–" not in text, path.name
    readme = README.read_text(encoding="utf-8")
    assert "booth.ember_page_url" in readme and "GitHub Pages" in readme
