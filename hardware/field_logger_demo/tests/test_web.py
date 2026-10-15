"""The page in headless Chromium (spec tests 1, 2, 4, 5, 6, 7, 9 and the automatic part of 11), offline: every request
that does not go to the local server is blocked, and any attempt fails the test.

Needs Playwright's Chromium (python -m playwright install chromium); skipped when it is missing."""
import json
import math
import re
import struct
import time
import urllib.request

import pytest

from app import library, privacy, replay
from app.vendor import usb_export as ux
from conftest import ROOT, SAMPLES, wait_for

pw = pytest.importorskip("playwright.sync_api")
GL = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
R_EARTH = 6371008.8
SIZES = [(1512, 982), (1728, 1117)]
LIB = json.loads((ROOT / "sessions" / "sessions.json").read_text(encoding="utf-8"))
KO = json.loads((ROOT / "web" / "i18n" / "ko.json").read_text(encoding="utf-8"))
HANGUL = re.compile(r"[가-힣]")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=GL)
        except pw.Error as ex:
            pytest.skip("Playwright's Chromium is not installed (python -m playwright install chromium): %s" % ex)
        yield b
        b.close()


class Tab:
    """A page that may only talk to the local server."""

    def __init__(self, browser, base, size=SIZES[0]):
        self.base = base
        self.blocked, self.errors = [], []
        self.page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        self.page.route("**/*", self._route)
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))

    def _route(self, route):
        url = route.request.url
        if url.startswith(self.base + "/"):
            route.continue_()
        else:
            self.blocked.append(url)
            route.abort()

    def open(self, query="?test", wait="#scr-start.on .sc"):
        self.page.goto(self.base + "/" + query)
        if wait:
            self.page.wait_for_selector(wait, timeout=10000)
        return self.page

    def js(self, expr, arg=None):
        return self.page.evaluate(expr, arg)

    def close(self):
        assert not self.blocked, "requests outside the local server: %s" % self.blocked[:5]
        assert not self.errors, "errors in the page: %s" % self.errors[:5]
        self.page.close()


@pytest.fixture
def tab(browser, server):
    t = Tab(browser, server["base"])
    yield t
    t.close()


def _get(base, path):
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(base + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def mmss(s):
    s = max(0, math.floor(s + 1e-6))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)


def ppm(zoom, lat):
    return 512 * 2 ** zoom / (2 * math.pi * R_EARTH * math.cos(math.radians(lat)))


def _play_to_end(t, key, speed=60, sample=None, timeout=120):
    """Press the key, play at the given speed until the summary (or the end, for a session without movement)."""
    t.page.keyboard.press(str(key))
    t.page.wait_for_function("window.__app && window.__app.booth.payload && window.__app.booth.playing", timeout=15000)
    t.js("(s) => { window.__app.booth.speed = s; }", speed)
    end = time.monotonic() + timeout
    samples = []
    while time.monotonic() < end:
        if sample:
            samples.append(t.js(sample))
        if t.js("document.querySelector('#scr-summary').classList.contains('on') || window.__app.booth.ended"):
            break
        time.sleep(0.25)
    else:
        raise AssertionError("the replay did not end")
    return samples


def _hidden_needles(entry):
    """What a hidden position would look like in the page: the console's 'lat, lon' pair with 7 decimals, and the
    record's lat/lon bytes as the console prints hex (two 8-character words)."""
    s = library.load(library.safe_path(entry["file"]))
    zones = privacy.zones_for(s, entry.get("privacy"))
    pts = [(r["lat"], r["lon"]) for r in s.rows if r["fix"] and privacy.inside(zones, r["lat"], r["lon"])]
    pts += [(e["lat"], e["lon"]) for e in s.events if e["located"] and privacy.inside(zones, e["lat"], e["lon"])]
    out = set()
    for lat, lon in pts:
        out.add("%.7f, %.7f" % (lat, lon))
        hx = struct.pack("<ii", int(round(lat * 1e7)), int(round(lon * 1e7))).hex()
        out.add(hx[:8] + " " + hx[8:])
    return pts, out


# ------------------------------------------------------------------ 1. offline, fast start
def test_start_screen_offline_within_5_s(browser, server):
    t = Tab(browser, server["base"])
    t0 = time.monotonic()
    t.open()
    took = time.monotonic() - t0
    assert took < 5.0, took
    assert t.page.locator("#scr-start .sc").count() == len(LIB)
    text = t.js("document.body.innerText")
    leaked = sorted(k for k in KO if "." in k and re.search(r"(?<![\w.])%s(?![\w.])" % re.escape(k), text))
    assert not leaked, leaked                           # an i18n key shown instead of its text
    t.close()


# ------------------------------------------------------------------ 2, 6, 7. replay to summary
SAMPLE = """() => { const b = window.__app.booth; const me = document.querySelector('#scr-booth .mk-me');
  const r = me && !me.querySelector('.mk-cpill') ? me.getBoundingClientRect() : null;
  const st = document.querySelector('#scr-booth .mk-stop'); const sr = st ? st.getBoundingClientRect() : null;
  return { lens: !b.$.lens.classList.contains('off'), ppm: b.camera.ppm(), tau: b.tau, moving: b.view.isMoving(),
    ended: b.ended, me: r && [r.width, r.height], stop: sr && [sr.width, sr.height], zoom: b.view.getZoom() }; }"""


def test_replay_to_summary_numbers_camera_and_privacy(tab, server):
    entry = next(e for e in LIB if e["key"] == 1)
    payload = _get(server["base"], "/api/session?key=1")
    num = replay.summary_numbers(payload)
    tab.open()
    samples = _play_to_end(tab, 1, sample=SAMPLE)
    tab.page.wait_for_selector("#scr-summary.on .tile", timeout=15000)
    # the numbers on the summary are the numbers of summary.json
    M = num["metrics"]
    tiles = tab.js("[...document.querySelectorAll('#scr-summary .tiles .tile')].map(e => [e.querySelector('b').textContent, "
                   "e.querySelector('span').textContent])")
    assert tiles == [["%.2f km" % (M["distance"] / 1000), KO["distance"]], [mmss(M["moving"]), KO["moving"]],
                     ["%.2f m/s" % M["avg_speed"], KO["avg"]],
                     [KO["stats.count"].format(n=len(num["stops"]), d=mmss(M["stopped"])), KO["stops"]],
                     [mmss(M["longest"]), KO["longest"]], [mmss(M["gap"]), KO["gap"]]]
    assert tab.js("document.querySelector('#scr-summary .pct').textContent") == "+%d%%" % math.floor(M["pct_added"] * 100 + 0.5)
    rows = tab.js("[...document.querySelectorAll('#scr-summary table.st tr')].slice(1).map(tr => [...tr.children].map(td => td.textContent))")
    assert [r[2] for r in rows] == [mmss(s["duration_s"]) for s in num["stops"]]
    assert [r[0] for r in rows] == [str(s["n"]) for s in num["stops"]]
    v = num["validation"]
    method = tab.js("document.querySelector('#scr-summary .method').textContent")
    assert KO["validation"].format(m=v["presses"], d=v["detected"], k=v["matched"], g=round(abs(v["median_gap"]))) in method
    # camera (test 7): no zoom change under 0.15 levels, none during a stop
    log = tab.js("window.__cameraLog")
    assert log and any(e["reason"] == "final" for e in log)
    for e in log:
        if e["reason"] in ("zoom", "leave"):
            dz = abs(e["zoom"] - e["from"])
            assert dz < 1e-3 or dz >= 0.15 - 1e-3, e
            assert not any(s["td"] <= e["t"] <= s["t1"] for s in payload["stops"]), e
    # the close-up only by the 2.5x rule (each change is logged with the scale the page saw when it decided)
    lens = [e for e in log if e["reason"] == "lens"]
    assert any(e["on"] for e in lens), "the close-up never appeared on a 1.6 km walk"
    for e in lens:
        if e["on"]:
            assert e["ppm"] < 1.5 and e["me"] and e["mode"] == "overview", e
        elif e["me"] and e["mode"] == "overview":
            assert e["ppm"] >= 1.5 or e["t"] >= payload["meta"]["t_end"] - 1e-6, e
    # markers keep their size at every zoom
    zooms = {round(s["zoom"], 1) for s in samples if s["me"]}
    sizes = {tuple(round(x) for x in s["me"]) for s in samples if s["me"]}
    assert len(zooms) >= 2 and len(sizes) == 1, (zooms, sizes)
    stop_sizes = {tuple(round(x) for x in s["stop"]) for s in samples if s["stop"]}
    assert len(stop_sizes) <= 1, stop_sizes
    # privacy (test 6): no hidden position in the page, in what the stream would show for every record either
    pts, needles = _hidden_needles(entry)
    assert pts
    all_lines = tab.js("""async () => { const { recordLines } = await import('/js/console.js'); const p = window.__app.booth.payload;
      return p.records.map(r => recordLines(r, p, true).map(x => x[0]).join('\\n')).join('\\n'); }""")
    dom = tab.js("document.documentElement.outerHTML") + tab.js("document.body.innerText")
    for where, text in (("stream", all_lines), ("DOM", dom)):
        found = [n for n in needles if n in text]
        assert not found, (where, found[:3])
    vis = [r for r in payload["rows"] if r["la"] is not None]
    assert "%.7f, %.7f" % (vis[len(vis) // 2]["la"], vis[len(vis) // 2]["lo"]) in all_lines   # it sees a shown one


def test_small_loop_keeps_the_60_m_minimum_and_the_drive_fits_whole(tab, server):
    tab.open()
    _play_to_end(tab, 3)
    log = tab.js("window.__cameraLog")
    for e in log:
        if e.get("pads"):
            short = min(e["size"]["w"] - e["pads"]["l"] - e["pads"]["r"], e["size"]["h"] - e["pads"]["t"] - e["pads"]["b"])
            assert short / ppm(e["zoom"], e["center"][1]) >= 60.0 - 0.5, e
    fin = [e for e in log if e["reason"] == "final"][-1]
    short = min(fin["size"]["w"] - fin["pads"]["l"] - fin["pads"]["r"], fin["size"]["h"] - fin["pads"]["t"] - fin["pads"]["b"])
    assert abs(short / ppm(fin["zoom"], fin["center"][1]) - 60.0) < 0.5      # the 30 m loop fills the 60 m span
    # the 10 km drive: at the end every shown fix is on the map, clear of the stats card
    tab.page.keyboard.press("Escape")                                  # Esc: from the summary to the start screen
    tab.page.wait_for_selector("#scr-start.on")
    _play_to_end(tab, 4)
    tab.page.wait_for_function("!window.__app.booth.view.isMoving()", timeout=10000)
    res = tab.js("""() => { const b = window.__app.booth; b.view.map.resize(); const s = b.view.size();
      const mapR = b.$.map.getBoundingClientRect(), c = b.$.stats.getBoundingClientRect();
      const card = { x: c.left - mapR.left, y: c.top - mapR.top, w: c.width, h: c.height };
      const pts = b.payload.rows.filter(r => r.f && !r.h && r.la !== null).map(r => b.view.project([r.lo, r.la]));
      return { s, card, out: pts.filter(q => q.x < 0 || q.y < 0 || q.x > s.w || q.y > s.h).length,
        under: pts.filter(q => q.x > card.x && q.x < card.x + card.w && q.y > card.y && q.y < card.y + card.h).length, n: pts.length }; }""")
    assert res["n"] > 500 and res["out"] == 0 and res["under"] == 0, res


# ------------------------------------------------------------------ 4. integrity in the stream
def test_corrupted_record_and_missing_seq_are_shown(tab, server):
    src = (ROOT / "sessions" / "sim" / "sim_walk_4_crossings.wfg").read_bytes()
    d = server["root"] / "sessions" / "real" / "itest"
    d.mkdir(parents=True, exist_ok=True)
    bad = bytearray(src)
    bad[50 * 48 + 30] ^= 0x5A
    (d / "S000101.wfg").write_bytes(bytes(bad))
    (d / "S000102.wfg").write_bytes(src[:60 * 48] + src[61 * 48:])
    tab.open()
    tab.page.keyboard.press("1")                       # the booth screen, then the damaged file in it
    tab.page.wait_for_function("window.__app && window.__app.booth.payload && window.__app.booth.playing", timeout=15000)
    tab.js("async () => { await window.__app.booth.load('file=real/itest/S000101.wfg'); }")
    t50 = ux.decode(src[50 * 48:51 * 48])["mono"]
    t0 = ux.decode(src[:48])["mono"]
    tab.js("(tt) => { const b = window.__app.booth; b.pause(); b.tau = tt; b._rebuildConsole(); b._render(true, true); b.console.flush(); }",
           (t50 - t0) / 1000 + 2)
    tab.page.wait_for_selector("#scr-booth .ln.corrupt")
    line = tab.js("document.querySelector('#scr-booth .ln.corrupt').textContent")
    assert "CORRUPT" in line
    colour = tab.js("getComputedStyle(document.querySelector('#scr-booth .ln.corrupt')).color")
    err = tab.js("""() => { const d = document.createElement('div'); d.style.color = 'var(--error)'; document.body.appendChild(d);
      const c = getComputedStyle(d).color; d.remove(); return c; }""")
    assert colour == err                                  # red, the error colour
    chip = tab.js("[document.querySelector('#scr-booth .crc').textContent, document.querySelector('#scr-booth .crc').className]")
    assert re.match(r"^CRC [\d,]+/[\d,]+ ✕$", chip[0]) and "bad" in chip[1]
    ok, total = (int(x.replace(",", "")) for x in re.findall(r"[\d,]+", chip[0])[:2])
    assert total - ok == 1
    tab.js("async () => { await window.__app.booth.load('file=real/itest/S000102.wfg'); }")
    t60 = ux.decode(src[61 * 48:62 * 48])["mono"]
    tab.js("(tt) => { const b = window.__app.booth; b.pause(); b.tau = tt; b._rebuildConsole(); b._render(true, true); b.console.flush(); }",
           (t60 - t0) / 1000 + 2)
    tab.page.wait_for_selector("#scr-booth .ln.seqgap")
    gap = tab.js("document.querySelector('#scr-booth .ln.seqgap').textContent")
    assert "#0059" in gap and "#0061" in gap and KO["console.seq_gap"].split(" · ")[1].format(n=1) in gap


def test_a_gpx_track_is_labelled_and_claims_no_crc(tab, server):
    gpx = SAMPLES / "S000001_WALK.gpx"
    if not gpx.exists():
        pytest.skip("sample GPX not available")
    d = server["root"] / "sessions" / "real" / "itest"
    d.mkdir(parents=True, exist_ok=True)
    (d / "phone.gpx").write_bytes(gpx.read_bytes())
    tab.open()
    tab.page.keyboard.press("1")
    tab.page.wait_for_function("window.__app && window.__app.booth.payload && window.__app.booth.playing", timeout=15000)
    tab.js("async () => { await window.__app.booth.load('file=real/itest/phone.gpx'); }")
    tab.js("() => { const b = window.__app.booth; b.pause(); b.tau = b.tEnd / 2; b._rebuildConsole(); b._render(true, true); b.console.flush(); }")
    chip = tab.js("[document.querySelector('#scr-booth .crc').textContent, document.querySelector('#scr-booth .crc').className]")
    assert chip[0] == KO["crc.none"] and "ok" not in chip[1].split() and "bad" not in chip[1].split()
    assert KO["gpx.label"] in tab.js("document.querySelector('#scr-booth .stats').textContent")
    assert "✓" not in tab.js("[...document.querySelectorAll('#scr-booth .ln.fix')].map(l => l.textContent).join('')")
    tab.js("() => { const b = window.__app.booth; b.tau = b.tEnd; b._render(true); b._end(); }")
    tab.page.wait_for_selector("#scr-summary.on .tile", timeout=15000)
    foot = tab.js("document.querySelector('#scr-summary .foot').textContent")
    assert "CRC" in KO["summary.source_gpx"] and KO["summary.gpx_mark"] in foot and KO["summary.source"][-8:] not in foot
    assert "GPX" in foot and tab.js("!!document.querySelector('#scr-summary .wm')")
    tab.page.keyboard.press("Escape")
    tab.page.wait_for_selector("#scr-start.on")


# ------------------------------------------------------------------ 5. language
def test_l_switches_every_label(tab, server):
    tab.open()
    tab.page.keyboard.press("1")
    tab.page.wait_for_function("window.__app && window.__app.booth.payload && window.__app.booth.playing", timeout=15000)
    tab.js("() => { const b = window.__app.booth; b.pause(); b.tau = 400; b._rebuildConsole(); b._render(true, true); b.console.flush(); }")
    ko_text = tab.js("document.querySelector('#scr-booth').innerText")
    assert HANGUL.search(ko_text)
    tab.page.keyboard.press("l")
    tab.page.wait_for_function("document.documentElement.lang === 'en'")
    tab.js("window.__app.booth.console.flush()")         # the stream is rebuilt in English on the next frame
    en_text = tab.js("document.querySelector('#scr-booth').innerText")
    en_text = re.sub(r"한\s*[/·]\s*EN", "", en_text)   # the language key's own label names both languages
    left = sorted(set(HANGUL.findall(en_text)))
    assert not left, [ln for ln in en_text.splitlines() if HANGUL.search(ln)][:5]
    assert "Log stream" in en_text and "Records" in en_text and " sats " in en_text     # labels and the stream's notes
    tab.page.keyboard.press("l")
    tab.page.wait_for_function("document.documentElement.lang === 'ko'")


# ------------------------------------------------------------------ 11 (automatic part). nothing clipped
CLIP = """(root) => {
  const out = [];
  for (const el of document.querySelectorAll(root + ' *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || !el.offsetParent) continue;
    if (el.closest('.lines, .maplibregl-map, .wm, .sheet-back')) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const clipX = ['hidden', 'clip'].includes(cs.overflowX) && el.scrollWidth > el.clientWidth + 1;
    const clipY = ['hidden', 'clip'].includes(cs.overflowY) && el.scrollHeight > el.clientHeight + 2;
    if (clipX || clipY) { out.push('clipped ' + (el.className || el.tagName) + ': ' + el.textContent.trim().slice(0, 60)); continue; }
    // text that runs out of its card, tile, button or chip, or out of the window
    const box = el.closest('.card, .tile, .t4, .dcard, .rcard, .sc, .sheet, .tl3, .btn, .chip, .prow, .step, .rr, .ck');
    const r = el.getBoundingClientRect();
    const range = document.createRange(); range.selectNodeContents(el); const tr = range.getBoundingClientRect();
    const right = Math.max(r.right, tr.right), left = Math.min(r.left, tr.left);
    if (right > innerWidth + 1 || left < -1) { out.push('outside window ' + (el.className || el.tagName) + ': ' + el.textContent.trim().slice(0, 60)); continue; }
    if (box && box !== el) {
      const b = box.getBoundingClientRect();
      if (tr.width && (tr.right > b.right + 1 || tr.left < b.left - 1 || tr.bottom > b.bottom + 2))
        out.push('spills ' + (el.className || el.tagName) + ': ' + el.textContent.trim().slice(0, 60));
    }
  }
  return out; }"""


@pytest.mark.parametrize("size", SIZES, ids=["1512x982", "1728x1117"])
@pytest.mark.parametrize("lang", ["ko", "en"])
def test_no_clipped_text(browser, server, size, lang):
    t = Tab(browser, server["base"], size)
    t.open("?test&lang=" + lang)
    clipped = t.js(CLIP, "#scr-start")
    t.page.keyboard.press("1")
    t.page.wait_for_function("window.__app && window.__app.booth.payload && window.__app.booth.playing", timeout=15000)
    for tau in ("370", "b.tEnd - 2"):                 # early, and near the end where the record counts are widest
        t.js("() => { const b = window.__app.booth; b.pause(); b.tau = %s; b._rebuildConsole(); b._render(true, true); b.console.flush(); }" % tau)
        time.sleep(0.3)
        clipped += t.js(CLIP, "#scr-booth")
    t.js("() => { const b = window.__app.booth; b.tau = b.tEnd; b._render(true); b._end(); }")
    t.page.wait_for_selector("#scr-summary.on .tile", timeout=15000)
    time.sleep(0.5)
    clipped += t.js(CLIP, "#scr-summary")
    t.page.keyboard.press("d")
    t.page.wait_for_selector("#scr-device.on .cwrap", timeout=10000)
    clipped += t.js(CLIP, "#scr-device")
    assert not clipped, clipped[:8]
    t.close()


# ------------------------------------------------------------------ the device page with the simulated logger
def test_device_page_test_recording_and_result(tab, server):
    base = server["base"]
    tab.open()
    tab.page.keyboard.press("d")
    tab.page.wait_for_selector("#scr-device.on .prow", timeout=10000)
    assert KO["connect.simulated"] in tab.js("document.querySelector('#scr-device .prow').textContent")
    tab.page.keyboard.press("Enter")
    tab.page.wait_for_selector("#scr-device .dpage .dname", timeout=15000)
    assert tab.js("document.querySelector('#scr-device .dname').textContent") == "WFG-00000000"
    assert tab.js("!document.querySelector('#scr-device .dleft .wm').classList.contains('hidden')")
    tab.page.keyboard.press("t")
    tab.page.wait_for_selector("#scr-device .tcard .step.now", timeout=5000)
    states = lambda: tab.js("[...document.querySelectorAll('#scr-device .tcard .step')].map(s => s.className.split(' ')[1])")
    assert states()[0] == "now"
    _post(base, "/api/device/double/press", {"kind": "long"})
    assert wait_for(lambda: states()[0] == "done", 8), states()
    _post(base, "/api/device/double/press", {"kind": "short"})
    assert wait_for(lambda: states()[1] == "done", 8), states()
    assert not tab.js(CLIP, "#scr-device")                            # the test in progress: nothing clipped
    _post(base, "/api/device/double/press", {"kind": "long"})          # stop early: straight to the pull
    tab.page.wait_for_selector("#scr-device .rcard", timeout=15000)
    rows = tab.js("[...document.querySelectorAll('#scr-device .rcard .rr')].map(r => r.querySelector('.n').textContent)")
    assert len(rows) == 11 and rows[0] == KO["res.file.title"]
    assert not tab.js(CLIP, "#scr-device")                            # the result card: nothing clipped
    lay = tab.js("""() => { const r = s => document.querySelector(s).getBoundingClientRect();
      return { card: r('#scr-device .rcard').bottom, act: r('#scr-device .ract').bottom, note: r('#scr-device .bnote').top,
               noteEnd: r('#scr-device .bnote').bottom, h: innerHeight }; }""")
    assert lay["act"] <= lay["card"] <= lay["note"] and lay["noteEnd"] <= lay["h"], lay   # buttons, then the note, in view
    tab.page.click("#scr-device .b-scr[data-v='1']")
    assert wait_for(lambda: tab.js("!document.querySelector('#scr-device .b-scr')"), 5)
    tab.page.keyboard.press("Enter")                                   # replay the pulled test
    tab.page.wait_for_selector("#scr-booth.on", timeout=10000)
    tab.page.wait_for_function("window.__app.booth.payload && window.__app.booth.payload.meta.sim_kind === 'double'")
    assert KO["double.label"] in tab.js("document.querySelector('#scr-booth .stats').textContent")
    _post(base, "/api/device/disconnect", {})


def test_shift_p_downloads_again_when_the_library_has_the_same_file(tab, server):
    """Spec section 8: P replays the local copy when the SHA-256 matches; Shift+P forces a fresh download."""
    base = server["base"]
    tab.open()
    tab.page.keyboard.press("d")
    tab.page.wait_for_selector("#scr-device.on .prow", timeout=10000)
    tab.page.keyboard.press("Enter")
    tab.page.wait_for_selector("#scr-device .dpage .dname", timeout=15000)
    _post(base, "/api/device/double/samples", {})         # the SIM files: the library already has the same bytes
    dumps = lambda: tab.js("[...document.querySelectorAll('#scr-device .lines .ln')].filter(l => /→ +DUMP S[0-9]{6}[.]wfg/.test(l.textContent)).length")
    n0 = dumps()
    for force in (False, True):
        tab.page.keyboard.press("Shift+P" if force else "p")
        tab.page.wait_for_selector(".sheet .ptable", timeout=15000)
        sub = tab.js("document.querySelector('.sheet .sub').textContent")
        assert sub == (KO["pull.sub_force"] if force else KO["pull.sub"])
        tab.page.click(".sheet .ptable tr:has-text('9,072 B')")             # the 30 m loop, the smallest
        tab.page.keyboard.press("Enter")
        tab.page.wait_for_selector(".sheet-back", state="detached", timeout=30000)
        if not force:
            assert dumps() == n0                                         # the same SHA-256: no download
    assert wait_for(lambda: dumps() == n0 + 1, 30)
    _post(base, "/api/device/disconnect", {})


def test_live_map_and_i_shows_the_device_page(browser, server_live):
    base = server_live["base"]
    t = Tab(browser, base)
    try:
        t.open()
        t.page.keyboard.press("d")
        t.page.wait_for_selector("#scr-device.on .prow", timeout=10000)
        t.page.keyboard.press("Enter")
        t.page.wait_for_selector("#scr-device .mapwrap .stats", timeout=15000)
        _post(base, "/api/device/double/gnss", {"mode": "fix"})
        _post(base, "/api/device/double/press", {"kind": "long"})
        assert wait_for(lambda: t.js("(window.__app.live.rows || []).length") >= 3, 10)
        # F and R work on the LIVE map as in REPLAY (spec 3B): F follows, R resumes the auto-fit a manual move paused
        assert t.js("window.__app.live.camera.mode") == "overview"
        t.page.keyboard.press("f")
        assert t.js("window.__app.live.camera.mode") == "follow"
        t.page.keyboard.press("f")
        assert t.js("window.__app.live.camera.mode") == "overview"
        t.js("() => window.__app.live.view.onUserMove()")                 # what a drag or a scroll on the map does
        assert t.js("window.__app.live.camera.paused") is True
        assert t.js("document.querySelector('#scr-device .mapwrap .maptoast').textContent") == KO["autofit.paused"]
        t.page.keyboard.press("r")
        assert t.js("window.__app.live.camera.paused") is False
        assert t.js("document.querySelector('#scr-device .mapwrap .maptoast').textContent") == KO["autofit.on"]
        for _ in range(4):                   # I back and forth: the same two maps come back, no new WebGL contexts
            t.page.keyboard.press("i")
            t.page.wait_for_selector("#scr-device .dpage .dname", timeout=5000)
            t.page.keyboard.press("i")
            t.page.wait_for_selector("#scr-device .mapwrap .stats", timeout=5000)
        assert t.js("window.__app.live.builds") == 1
        lines = t.js("[...document.querySelectorAll('#scr-device .lines .ln.live')].length")
        assert lines > 3
        _post(base, "/api/device/double/press", {"kind": "long"})
        _post(base, "/api/device/disconnect", {})
    finally:
        t.close()


# ------------------------------------------------------------------ 9 (exports): the files hold no hidden position
def test_export_files(server):
    entry = next(e for e in LIB if e["key"] == 1)
    out = _post(server["base"], "/api/export", {"key": 1, "langs": ["ko"]})
    files = {p.split("/")[-1]: p for p in out["files"]}
    assert set(files) == {"stops.csv", "summary.json", "summary_ko.png"}
    from PIL import Image
    im = Image.open(files["summary_ko.png"])
    assert im.size == (3200, 2000)
    summ = json.loads(open(files["summary.json"], encoding="utf-8").read())
    payload = _get(server["base"], "/api/session?key=1")
    assert summ["metrics"] == payload["metrics"] and summ["simulated"] is True
    pts, _ = _hidden_needles(entry)
    text = open(files["stops.csv"], encoding="utf-8").read() + json.dumps(summ)
    for lat, lon in pts:
        assert not ("%.7f" % lat in text and "%.7f" % lon in text)


def test_indoor_recording_activity_without_a_path(browser, server_live):
    """Synthetic NO FIX records must grow the map card without inventing positions."""
    base = server_live["base"]
    t = Tab(browser, base)
    try:
        t.open('?test&lang=en')
        t.page.keyboard.press('d')
        t.page.wait_for_selector('#scr-device.on .prow')
        t.page.keyboard.press('Enter')
        t.page.wait_for_selector('#scr-device .live-activity')
        _post(base, '/api/device/double/gnss', {'mode': 'indoor'})
        _post(base, '/api/device/double/press', {'kind': 'long'})
        t.page.wait_for_function("document.querySelector('.activity-fix').textContent === 'NO FIX'")
        count = lambda: t.js("Number(document.querySelector('.activity-records').textContent.replaceAll(',', ''))")
        before = count()
        assert before > 0
        assert wait_for(lambda: count() > before, 8)
        assert t.js("document.querySelector('.activity-head b').textContent") == 'REC · recording'
        assert t.js("window.__app.live.activity.span") > 0
        assert t.js("window.__app.live.view.map.getSource('track')._data.features.length") == 0
        assert t.js("window.__app.live.rows.every(r => !r.f)")
        _post(base, '/api/device/double/press', {'kind': 'long'})
        t.page.wait_for_function("document.querySelector('.activity-head b').textContent === 'Recording stopped'")
        _post(base, '/api/device/disconnect', {})
    finally:
        t.close()
